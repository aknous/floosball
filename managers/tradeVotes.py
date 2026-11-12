"""Fan approval votes on trades (owner, 2026-10-30).

The trade market (`tradeManager.runWeeklyPass`) still decides which trades the teams
agree. With votes on, an agreed trade is stored as a PROPOSAL instead of settling, every
signed-in user can vote yes or no on it from the Transactions page, and it settles only
if the vote passes when it closes (`verdict`). Constants and the full rule: `constants.py`
under "Fan approval votes on trades".

When a vote closes is the next roster event (`close_kind`):
    deadline      in season; the deadline day's first kickoff (week GM_ACTIVE_WEEK)
    rookie_draft  the offseason pass after the front office; the rookie draft
    season_start  the pass after the FA draft; the next season's start

⚠️ A TEAM IN AN OPEN PROPOSAL SITS OUT EVERY PASS UNTIL IT RESOLVES (`openTeamIds`). The
market settles a pass sequentially and re-validates each trade against the state the last
one left; a stored proposal settles hours later, so the only way to keep its assets and
roster slots from being promised twice is to keep its two teams out of the market.

⚠️ SETTLEMENT RUNS THE SAME CODE AS BEFORE. A proposal stores ids and numbers, and the
`Listing`/`PickListing`/`Bid` are rebuilt against the live rosters at close and handed to
`tradeManager.settleTrade` / `settlePickTrade`, which re-check everything and return None
if the trade is no longer possible.
"""
import logging
import math
from datetime import datetime

logger = logging.getLogger("floosball.tradeVotes")

OPEN, APPROVED, REJECTED, FAILED, EXPIRED = 'open', 'approved', 'rejected', 'failed', 'expired'

PHASE_IN_SEASON = 'in_season'
PHASE_OFFSEASON = 'offseason'        # after the front office, before the rookie draft
PHASE_POST_FA = 'post_fa'            # after the FA draft, before the next season

CLOSE_DEADLINE = 'deadline'
CLOSE_ROOKIE_DRAFT = 'rookie_draft'
CLOSE_SEASON_START = 'season_start'


# ─── the rule ───────────────────────────────────────────────────────────────────────────

def fanBar(fans: int) -> int:
    """Yes votes a team's own fans must give: `TRADE_VOTE_FAN_FRACTION` of its fans,
    at least 1. A team with no fans has no bar of its own (0)."""
    from constants import TRADE_VOTE_FAN_FRACTION
    fans = int(fans or 0)
    if fans <= 0:
        return 0
    return max(1, math.ceil(fans * float(TRADE_VOTE_FAN_FRACTION)))


def verdict(teamAId, teamBId, votes, fanCounts) -> dict:
    """Does the trade pass?

    votes: [(voterFavoriteTeamId or None, approve: bool)], one per voter.
    fanCounts: {teamId: how many ACTIVE fans it has} (`activeFanCounts`).

    Passes when the league-wide vote has more yes than no AND, for each team with fans,
    at least `fanBar` of its fans voted yes and its fans did not vote it down (more no
    than yes among them). A team with no fans adds no requirement beyond the league-wide
    yes, which already means somebody approved it.

    Returns {passed, reason, yes, no, teams: {teamId: {fans, need, yes, no}}};
    reason is None, 'no_votes', 'league_no', 'team_veto' or 'team_quorum'.
    """
    yes = sum(1 for _t, a in votes if a)
    no = sum(1 for _t, a in votes if not a)
    reason = None
    if yes == 0 and no == 0:
        reason = 'no_votes'
    elif yes <= no:
        reason = 'league_no'
    teams = {}
    for tid in (teamAId, teamBId):
        fans = int(fanCounts.get(tid, 0) or 0)
        tYes = sum(1 for t, a in votes if t == tid and a)
        tNo = sum(1 for t, a in votes if t == tid and not a)
        need = fanBar(fans)
        teams[tid] = {'fans': fans, 'need': need, 'yes': tYes, 'no': tNo}
        if reason is None and fans > 0:
            if tNo > tYes:
                reason = 'team_veto'
            elif tYes < need:
                reason = 'team_quorum'
    return {'passed': reason is None, 'reason': reason, 'yes': yes, 'no': no, 'teams': teams}


def tally(session, proposal) -> dict:
    """The proposal's votes as they stand, through `verdict`."""
    from database.models import TradeVote, User
    rows = (session.query(User.favorite_team_id, TradeVote.approve)
            .join(User, User.id == TradeVote.user_id)
            .filter(TradeVote.proposal_id == proposal.id).all())
    votes = [(int(t) if t is not None else None, bool(a)) for t, a in rows]
    return verdict(proposal.team_a_id, proposal.team_b_id, votes, activeFanCounts(session, proposal))


def activeFanCounts(session, proposal) -> dict:
    """{teamId: ACTIVE fans} for the proposal's two teams: users who favorite the team and
    signed in during the trade's season (`activitySince`; owner, 2026-11-11). An offseason
    trade runs under the number of the season that just ended, so its fans are the ones
    active in that season. A fan who voted on this proposal counts whenever they last signed
    in, so a yes vote can never outnumber the fans it is measured against. A team whose fans
    have all drifted away counts as fanless.

    ⚠️ It was signed in within `SUPPORTER_ACTIVITY_WINDOW_DAYS` (14). A season is about a
    week of real time, so that window took in fans who had stopped playing a season ago, and
    a team with lapsed fans needed more yes votes than its real fanbase could give.

    Counted fresh rather than through `sentiment_repository.teamFanCounts`, which caches
    for a minute and counts every favoriter: a vote is decided once, against the fanbase
    as it is when it closes."""
    from sqlalchemy import or_
    from database.models import TradeVote, User
    cutoff = activitySince(session, proposal.season)
    voters = session.query(TradeVote.user_id).filter(TradeVote.proposal_id == proposal.id)
    teamIds = (proposal.team_a_id, proposal.team_b_id)
    fans = {}
    for (tid,) in (session.query(User.favorite_team_id)
                   .filter(User.favorite_team_id.in_(teamIds),
                           or_(User.last_login_at >= cutoff, User.id.in_(voters))).all()):
        fans[int(tid)] = fans.get(int(tid), 0) + 1
    return fans


def activitySince(session, season) -> datetime:
    """When a fan must have signed in since to count for a trade in `season`: the season's
    start (`seasons.start_date`, naive UTC, the rollover anchor). `last_login_at` is the most
    recent sign-in, so any sign-in since then passes. Falls back to the last
    `SUPPORTER_ACTIVITY_WINDOW_DAYS` when the season has no start recorded, or its start is
    still ahead (a season created by an early rollover before its anchor)."""
    from datetime import timedelta
    from constants import SUPPORTER_ACTIVITY_WINDOW_DAYS
    from database.models import Season
    now = datetime.utcnow()
    try:
        row = session.get(Season, int(season)) if season is not None else None
        start = row.start_date if row is not None else None
    except Exception:
        start = None
    if start is not None and getattr(start, 'tzinfo', None) is not None:
        start = start.replace(tzinfo=None)
    if start is None or start > now:
        return now - timedelta(days=SUPPORTER_ACTIVITY_WINDOW_DAYS)
    return start


# ─── proposals ──────────────────────────────────────────────────────────────────────────

def openTeamIds(session=None) -> set:
    """Teams in a proposal still waiting on its vote. They sit out every trade pass."""
    from database.models import TradeProposal
    own = session is None
    if own:
        from database.connection import get_session
        session = get_session()
    try:
        ids = set()
        for a, b in session.query(TradeProposal.team_a_id, TradeProposal.team_b_id).filter(
                TradeProposal.status == OPEN).all():
            ids.update((a, b))
        return ids
    except Exception as e:
        logger.warning(f"Could not read open trade proposals: {e}")
        return set()
    finally:
        if own:
            session.close()


def _assetsOf(entry) -> dict:
    """The display manifest, in the same shape a settled `Trade.assets_json` has."""
    listing, winner = entry['listing'], entry['winner']
    if entry.get('kind') == 'pick':
        pick = listing.pick
        aGave = [{'kind': 'pick', 'id': pick.get('id'),
                  'name': f"S{pick.get('season')} R{pick.get('round')} pick",
                  'detail': f"slot {pick.get('slot')}"}]
    elif entry.get('kind') == 'prospect':
        p = listing.prospect
        aGave = [{'kind': 'prospect', 'id': getattr(p, 'id', None), 'name': p.name,
                  'detail': getattr(getattr(p, 'position', None), 'name', '')}]
    else:
        p = listing.player
        aGave = [{'kind': 'player', 'id': getattr(p, 'id', None), 'name': p.name,
                  'detail': getattr(getattr(p, 'position', None), 'name', '')}]
    bGave = []
    for piece in (winner.pieces or []):
        d = piece.get('detail')
        if not isinstance(d, str):
            # A pick's detail is the pick dict, a prospect's a dict of his window; the page
            # shows a string.
            d = f"slot {d.get('slot')}" if piece.get('kind') == 'pick' and isinstance(d, dict) \
                and d.get('slot') else None
        bGave.append({'kind': piece.get('kind'), 'id': piece.get('id'),
                      'name': piece.get('name'), 'detail': d})
    return {'aGave': aGave, 'bGave': bGave}


def _serialize(entry) -> tuple:
    listing, winner = entry['listing'], entry['winner']
    kind = entry.get('kind') if entry.get('kind') in ('pick', 'prospect') else 'player'
    listingJson = {'trigger': getattr(listing, 'trigger', None),
                   'ask': float(listing.ask or 0), 'floor': float(listing.floor or 0),
                   'why': getattr(listing, 'why', None)}
    if kind == 'pick':
        listingJson['pick'] = dict(listing.pick)
    elif kind == 'prospect':
        listingJson['prospectId'] = getattr(listing.prospect, 'id', None)
    else:
        listingJson['playerId'] = getattr(listing.player, 'id', None)
    bidJson = {'pieces': [dict(p) for p in (winner.pieces or [])],
               'value': float(winner.value or 0), 'why': getattr(winner, 'why', None)}
    return kind, listingJson, bidJson


def propose(seasonManager, entries, season: int, week, phase: str, closeKind: str,
            closesAt=None) -> list:
    """Store the market's agreed trades as proposals, publish them and tell the bot.

    A team takes part in at most one open proposal; a later entry involving a team that
    already has one is dropped (it would otherwise promise the same roster twice).
    Returns the new proposals as API dicts."""
    from database.connection import get_session
    from database.models import TradeProposal
    if not entries:
        return []
    busy = openTeamIds()
    made = []
    session = get_session()
    try:
        for entry in entries:
            seller, buyer = entry['listing'].team, entry['winner'].team
            sid, bid = getattr(seller, 'id', None), getattr(buyer, 'id', None)
            if sid in busy or bid in busy:
                continue
            # ⚠️ ONLY A TRADE THAT COULD SETTLE NOW GOES TO A VOTE. The market does not ask
            # whether the buyer can pay the fee to make room, or is allowed to cut the man
            # it would have to; settlement does, and refused those quietly when it ran on
            # agreement. With a vote in between, fans would approve a trade that was never
            # possible. So settlement's own checks run first, changing nothing.
            try:
                ok = settleEntry(seasonManager, entry, season,
                                 week if phase == PHASE_IN_SEASON else None,
                                 fillHoles=True if phase == PHASE_POST_FA else None,
                                 dryRun=True)
            except Exception as e:
                logger.warning(f"Trade pre-check failed: {e}")
                ok = False
            if not ok:
                continue
            kind, listingJson, bidJson = _serialize(entry)
            row = TradeProposal(
                season=int(season), week=int(week or 0), phase=phase, kind=kind,
                team_a_id=sid, team_b_id=bid, listing_json=listingJson, bid_json=bidJson,
                assets_json=_assetsOf(entry), status=OPEN, close_kind=closeKind,
                closes_at=closesAt)
            session.add(row)
            session.commit()
            busy.update((sid, bid))
            made.append((row, seller, buyer))
        result = [_summary(row, seller, buyer) for row, seller, buyer in made]
    except Exception as e:
        logger.error(f"Could not store trade proposals: {e}", exc_info=True)
        try:
            session.rollback()
        except Exception:
            pass
        return []
    finally:
        session.close()
    for s in result:
        _publish(s['season'], s['week'],
                 f"Trade vote: the {s['teamA']['name']} would send {_names(s['aGave'])} to the "
                 f"{s['teamB']['name']} for {_names(s['bGave'])}. Fans decide.",
                 s['teamA']['id'], 'trade_vote_open')
    if result:
        logger.info(f"Trade votes opened: {len(result)} ({phase}, closes at {closeKind})")
        _broadcastOpened(seasonManager, result)
    return result


def _names(assets) -> str:
    return ', '.join(a.get('name') or '?' for a in (assets or [])) or 'nothing'


def _teamBlob(team, teamId=None) -> dict:
    if team is None:
        return {'id': teamId, 'name': None, 'abbr': None}
    return {'id': getattr(team, 'id', teamId), 'name': team.name,
            'abbr': getattr(team, 'abbr', team.name[:3].upper())}


def _summary(row, seller, buyer) -> dict:
    assets = row.assets_json or {}
    return {'id': row.id, 'season': row.season, 'week': row.week, 'phase': row.phase,
            'teamA': _teamBlob(seller, row.team_a_id), 'teamB': _teamBlob(buyer, row.team_b_id),
            'aGave': assets.get('aGave') or [], 'bGave': assets.get('bGave') or [],
            'closeKind': row.close_kind,
            'closesAt': row.closes_at.isoformat() + 'Z' if row.closes_at else None}


def _broadcastOpened(seasonManager, proposals) -> None:
    """`trade_votes_open`: the Discord bot posts the trades and DMs reminders."""
    try:
        from api.game_broadcaster import broadcaster
        if not broadcaster.is_enabled():
            return
        from api.event_models import EventType
        broadcaster.broadcast_sync('season', {
            'event': EventType.TRADE_VOTES_OPEN.value,
            'season': proposals[0]['season'],
            'proposals': [{**p, 'aGave': [a.get('name') for a in p['aGave']],
                           'bGave': [a.get('name') for a in p['bGave']]} for p in proposals],
        })
    except Exception as e:
        logger.warning(f"trade_votes_open broadcast failed: {e}")


def _publish(season, week, text, teamId, eventType) -> None:
    """League news. ⚠️ `publish` is keyword-only camelCase (`test_publish_kwargs.py`)."""
    try:
        import league_news
        from database.connection import get_session
        league_news.publishSafe(get_session, season=season, week=week, category='trade',
                                text=text, eventType=eventType, teamId=teamId)
    except Exception as e:
        logger.warning(f"Could not publish trade vote news: {e}")


# ─── settling ───────────────────────────────────────────────────────────────────────────

def settleEntry(seasonManager, entry, season: int, week, fillHoles: bool = None,
                dryRun: bool = False):
    """Settle one agreed trade now. The path every trade takes, voted or not. With
    `dryRun`, True if it could settle now, nothing moved."""
    from managers import tradeManager
    if entry.get('kind') == 'pick':
        return tradeManager.settlePickTrade(seasonManager, entry['listing'], entry['winner'],
                                            season, dryRun=dryRun)
    if entry.get('kind') == 'prospect':
        return tradeManager.settleProspectTrade(seasonManager, entry['listing'], entry['winner'],
                                                season, week, dryRun=dryRun)
    return tradeManager.settleTrade(seasonManager, entry['listing'], entry['winner'], season,
                                    week, fillHoles=fillHoles, dryRun=dryRun)


def _rebuild(row, teamManager):
    """The market entry a proposal was made from, against the live rosters, or None."""
    from managers.tradeManager import Listing, PickListing, ProspectListing, Bid, _findRostered, _findProspect
    teams = {getattr(t, 'id', None): t for t in (getattr(teamManager, 'teams', None) or [])}
    seller, buyer = teams.get(row.team_a_id), teams.get(row.team_b_id)
    if seller is None or buyer is None:
        return None
    lj, bj = row.listing_json or {}, row.bid_json or {}
    if row.kind == 'pick':
        listing = PickListing(seller, dict(lj.get('pick') or {}), lj.get('ask', 0),
                              lj.get('floor', 0), why=lj.get('why'))
    elif row.kind == 'prospect':
        prospect = _findProspect(seller, lj.get('prospectId'))
        if prospect is None:
            return None
        listing = ProspectListing(seller, prospect, lj.get('ask', 0), lj.get('floor', 0),
                                  why=lj.get('why'),
                                  trigger=lj.get('trigger') or 'last_window_prospect')
    else:
        player = _findRostered(seller, lj.get('playerId'))
        if player is None:
            return None
        listing = Listing(seller, player, lj.get('trigger'), lj.get('ask', 0),
                          lj.get('floor', 0), why=lj.get('why'))
    winner = Bid(buyer, [dict(p) for p in (bj.get('pieces') or [])], bj.get('value', 0),
                 why=bj.get('why'))
    return {'listing': listing, 'winner': winner, 'kind': row.kind}


def resolve(seasonManager, closeKind: str) -> list:
    """Close every open proposal of this kind: settle what the fans approved, record the
    rest. Returns [{'proposal': id, 'status', 'manifest' (when settled)}].

    ⚠️ BEST-EFFORT PER PROPOSAL. Nothing here may break a week or an offseason step; a
    proposal that raises is marked failed and the next one still resolves."""
    from database.connection import get_session
    from database.models import TradeProposal
    teamManager = seasonManager.serviceContainer.getService('team_manager')
    out = []
    session = get_session()
    try:
        rows = (session.query(TradeProposal)
                .filter(TradeProposal.status == OPEN, TradeProposal.close_kind == closeKind)
                .order_by(TradeProposal.created_at, TradeProposal.id).all())
        for row in rows:
            v = tally(session, row)
            manifest, note = None, None
            if not v['passed']:
                status = REJECTED
            else:
                try:
                    entry = _rebuild(row, teamManager)
                    if entry is None:
                        note = 'a player in it is no longer where the trade needs him'
                    else:
                        fill = True if row.phase == PHASE_POST_FA else None
                        week = row.week if row.phase == PHASE_IN_SEASON else None
                        manifest = settleEntry(seasonManager, entry, row.season, week,
                                               fillHoles=fill)
                        if manifest is None:
                            note = 'the rosters no longer allow it'
                except Exception as e:
                    logger.error(f"Trade proposal {row.id} failed to settle: {e}", exc_info=True)
                    manifest, note = None, 'it could not be completed'
                status = APPROVED if manifest is not None else FAILED
            row.status = status
            row.resolved_at = datetime.utcnow()
            row.result_json = {**v, 'teams': {str(k): t for k, t in v['teams'].items()},
                               'note': note}
            if manifest is not None:
                row.trade_id = manifest.get('tradeId')
            session.commit()
            out.append({'proposal': row.id, 'status': status, 'manifest': manifest,
                        'phase': row.phase})
            if status != APPROVED:
                _publishOutcome(row, teamManager, v, note)
    except Exception as e:
        logger.error(f"Resolving trade votes ({closeKind}) failed: {e}", exc_info=True)
        try:
            session.rollback()
        except Exception:
            pass
    finally:
        session.close()
    if out:
        counts = {}
        for o in out:
            counts[o['status']] = counts.get(o['status'], 0) + 1
        logger.info(f"Trade votes closed ({closeKind}): {counts}")
    return out


def _publishOutcome(row, teamManager, v, note) -> None:
    teams = {getattr(t, 'id', None): t for t in (getattr(teamManager, 'teams', None) or [])}
    a = getattr(teams.get(row.team_a_id), 'name', 'one team')
    b = getattr(teams.get(row.team_b_id), 'name', 'another team')
    if row.status == REJECTED:
        if v['reason'] == 'no_votes':
            text = f"The {a} and {b} trade fell through: nobody voted on it."
        elif v['reason'] == 'team_quorum':
            text = f"The {a} and {b} trade fell through: not enough of their fans approved it."
        else:
            text = f"Fans voted down the {a} and {b} trade."
    else:
        text = f"The {a} and {b} trade fell through: {note or 'it could not be completed'}."
    _publish(row.season, row.week, text, row.team_a_id, 'trade_vote_result')


def expireStale(season: int) -> int:
    """Mark proposals left open from an earlier season as expired (a restart missed their
    close). Season-start proposals are resolved by `startNewSeason` before this runs."""
    from database.connection import get_session
    from database.models import TradeProposal
    session = get_session()
    try:
        rows = session.query(TradeProposal).filter(
            TradeProposal.status == OPEN, TradeProposal.season < int(season),
            TradeProposal.close_kind != CLOSE_SEASON_START).all()
        for row in rows:
            row.status = EXPIRED
            row.resolved_at = datetime.utcnow()
        session.commit()
        return len(rows)
    except Exception as e:
        logger.warning(f"Could not expire stale trade proposals: {e}")
        session.rollback()
        return 0
    finally:
        session.close()

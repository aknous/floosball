"""The free agency market: a signing period where players choose
(docs/FREE_AGENCY_MARKET_PLAN.md, owner 2026-11-01).

Replaces the worst-first FA draft once salaries charge (`marketActive`). Each team offers
contracts to the free agents it wants; each player HOLDS the offer that scores best for
him (salary plus his motive's pull toward that team) and signs nothing until the market
closes; a team whose offer is surpassed can match or beat it, up to its walk-away price, or
move on down its list. Nothing locks until no team has a move left, so losing a bidding war
never costs a team its backup. Leftover players then lower their asking salary and the
market reopens for teams that still want someone; holes still open after the last pass are
filled by the FA draft's machinery with upgrades off (`seasonManager._processFreeAgency`).

Two layers, like `payroll.py`:
  - `resolve` is PURE: asking salaries, motives, team lists, budgets and pulls in; held
    offers and an event log out. Tested on its own (test_fa_market.py).
  - `runSigningPeriod` is the adapter: it builds every team's lists off its GM's board,
    prices motives off the league, executes the signings and conditional releases, and
    returns events in the FA draft's shape so the live feed and recap record them.
"""
import hashlib
import logging
import math
import random
from dataclasses import dataclass, field

from constants import (FA_MARKET_ENABLED, FA_MARKET_ROUNDS, FA_ASK_DECAY, FA_MIN_RAISE,
                       FA_MAX_BID_EDGE, FA_LIST_LENGTH, FA_HOMETOWN_DISCOUNT, FA_WINNER_PULL,
                       FA_COMFORT_PULL, FA_OPPORTUNITY_ASK, FA_HISTORY_SEASONS,
                       FA_MOTIVE_PERSONALITY, FA_RESIGN_RESERVATION)

from logger_config import get_logger
logger = get_logger('floosball.faMarket')

MOTIVES = ('hometown', 'winner', 'comfort', 'opportunity')
SLOTS = ('qb', 'rb', 'wr1', 'wr2', 'te', 'k')
POS_SLOTS = {1: ('qb',), 2: ('rb',), 3: ('wr1', 'wr2'), 4: ('te',), 5: ('k',)}


def marketActive() -> bool:
    """The signing period replaces the FA draft once salaries charge: without money a
    player has nothing to choose between."""
    from managers import payroll
    return bool(FA_MARKET_ENABLED) and payroll.salariesActive()


# ─── Motives ─────────────────────────────────────────────────────────────────────────────

def rollMotive(personality, rng) -> str:
    """Every motive starts at weight 1; a personality adds to the motives it leans toward."""
    weights = [1.0 + FA_MOTIVE_PERSONALITY.get(m, {}).get(personality or '', 0) for m in MOTIVES]
    return rng.choices(MOTIVES, weights=weights, k=1)[0]


def motiveOf(player) -> str:
    """This player's motive, rolled the first time it is needed on a seed fixed by his id,
    so every process gives him the same one. Persisted with the player (`fa_motive`)."""
    motive = getattr(player, 'faMotive', None)
    if motive in MOTIVES:
        return motive
    seed = int(hashlib.md5(f"fa_motive:{getattr(player, 'id', id(player))}".encode())
               .hexdigest()[:12], 16)
    personality = getattr(getattr(player, 'attributes', None), 'personality', None)
    motive = rollMotive(personality, random.Random(seed))
    try:
        player.faMotive = motive
    except Exception:
        pass
    return motive


def motivePull(motive: str, ask: int, *, isHome: bool, success: float, comfort: float) -> float:
    """Floobits of salary this player would give up to sign with a team: his motive is
    literally the discount he offers the teams he likes. `success` and `comfort` are the
    team's standing relative to the league, 0-1."""
    if motive == 'hometown':
        return FA_HOMETOWN_DISCOUNT * ask if isHome else 0.0
    if motive == 'winner':
        return FA_WINNER_PULL * ask * max(0.0, min(1.0, success))
    if motive == 'comfort':
        return FA_COMFORT_PULL * ask * max(0.0, min(1.0, comfort))
    return 0.0


# ─── The re-sign head start (owner, 2026-11-01) ──────────────────────────────────────────
#
# "teams should still get a head start on re-signing their own players though. players can
# choose to accept or go to free agency. teams can also decline to make an offer". Before
# the market opens, a team offers the walk-year players its GM wants to keep (or offers
# nothing); each player accepts or tests free agency, where his old team can still bid.

def reservation(player, season: int) -> float:
    """What this player thinks he is worth this offseason, as a share of his asking
    salary: drawn from his motive's range, on a seed fixed by player and season so the
    same offseason always gives the same answer."""
    motive = motiveOf(player)
    lo, hi = FA_RESIGN_RESERVATION.get(motive, (1.0, 1.0))
    seed = int(hashlib.md5(f"fa_reservation:{getattr(player, 'id', id(player))}:{season}".encode())
               .hexdigest()[:12], 16)
    return lo + (hi - lo) * random.Random(seed).random()


def teamPull(player, team, ask: int, standing: tuple) -> float:
    """This player's pull toward `team` (Floobits), with `standing` from `teamStanding`."""
    success, comfort = standing
    tid = getattr(team, 'id', None)
    return motivePull(motiveOf(player), ask,
                      isHome=getattr(player, 'homeTeamId', None) == tid,
                      success=success.get(tid, 0.5), comfort=comfort.get(tid, 0.5))


def resignOffer(player, team, standing: tuple, minimum: int) -> tuple:
    """(salary, pull): the team offers his asking salary less his pull toward it, since
    the GM knows his motive; never under the league minimum."""
    from managers import payroll
    ask = payroll.askingSalary(player)
    pull = teamPull(player, team, ask, standing)
    return max(int(minimum), int(math.ceil(ask - pull))), pull   # rounded up: a fair floor


def acceptsResign(player, salary: int, pull: float, season: int) -> bool:
    """Does he take his team's offer, or test free agency?"""
    from managers import payroll
    return salary + pull >= reservation(player, season) * payroll.askingSalary(player)


def teamStanding(teams, season: int, brain) -> tuple:
    return _teamStanding(teams, season, brain)


# ─── The pure market ─────────────────────────────────────────────────────────────────────

@dataclass
class Want:
    """One slot a team is shopping: an open slot, or an upgrade over `release`."""
    wid: int
    teamId: int
    slot: str
    posVal: int
    candidates: list = field(default_factory=list)   # [(playerId, maxBid)], best first
    release: object = None                           # incumbent id released if signed
    releaseSalary: int = 0
    term: int = None                                 # forced term (a prospect's window)


def resolve(asks: dict, motives: dict, wants: list, rank: dict, pull, room: dict,
            minRaise: float = FA_MIN_RAISE, opportunityAsk: float = FA_OPPORTUNITY_ASK):
    """Run one market pass to its close.

    asks:    {playerId: asking salary}
    motives: {playerId: motive}
    wants:   [Want]
    rank:    {teamId: tie order}, lower = the worse team, which wins an exact tie
    pull:    pull(playerId, teamId) -> Floobits
    room:    {teamId: Floobits a season the team can add in new salary (net of releases)}

    Returns ({playerId: (wid, salary)}, events). An event is a dict with `kind`
    ('offer'), team, player, salary, and `over` (the team it displaced, or None).
    """
    byWid = {w.wid: w for w in wants}
    held = {}          # playerId -> (wid, salary, score)
    final = set()      # 'opportunity' players commit to the first good offer
    leading = {}       # wid -> playerId it currently holds
    pos = {w.wid: 0 for w in wants}
    done = set()
    outstanding = {}   # teamId -> committed Floobits a season across its held offers
    events = []

    def cost(w, salary):
        return salary - (w.releaseSalary if w.release is not None else 0)

    def winsTie(tid, holderTid, pid):
        a, b = pull(pid, tid), pull(pid, holderTid)
        if a != b:
            return a > b
        return rank.get(tid, 0) < rank.get(holderTid, 0)

    order = sorted(wants, key=lambda w: (rank.get(w.teamId, 0), w.wid))
    cap = 50 * max(1, sum(len(w.candidates) for w in wants)) + 100
    for _ in range(cap):
        changed = False
        for w in order:
            if w.wid in leading or w.wid in done:
                continue
            while pos[w.wid] < len(w.candidates):
                pid, maxBid = w.candidates[pos[w.wid]]
                ask = int(asks.get(pid, 0) or 0)
                cur = held.get(pid)
                if pid in final or (cur and byWid[cur[0]].teamId == w.teamId):
                    pos[w.wid] += 1        # committed elsewhere, or our own other slot
                    continue
                opening = ask * (opportunityAsk if motives.get(pid) == 'opportunity' else 1.0)
                p = pull(pid, w.teamId)
                if cur:
                    holderTid = byWid[cur[0]].teamId
                    needed = cur[2] - p + (0 if winsTie(w.teamId, holderTid, pid)
                                           else max(1.0, minRaise * ask))
                    salary = int(math.ceil(max(opening, needed)))
                else:
                    salary = int(math.ceil(opening))
                c = cost(w, salary)
                if salary > maxBid or outstanding.get(w.teamId, 0) + c > room.get(w.teamId, float('inf')):
                    pos[w.wid] += 1        # out of his price range: next on the list
                    continue
                over = None
                if cur:
                    loser = byWid[cur[0]]
                    over = loser.teamId
                    leading.pop(loser.wid, None)
                    outstanding[loser.teamId] = outstanding.get(loser.teamId, 0) - cost(loser, cur[1])
                held[pid] = (w.wid, salary, salary + p)
                leading[w.wid] = pid
                outstanding[w.teamId] = outstanding.get(w.teamId, 0) + c
                if motives.get(pid) == 'opportunity':
                    final.add(pid)
                events.append({'kind': 'offer', 'team': w.teamId, 'player': pid,
                               'salary': salary, 'over': over})
                changed = True
                break
            else:
                done.add(w.wid)
        if not changed:
            break
    else:
        logger.warning("FA market: hit its pass cap before closing")
    return {pid: (wid, salary) for pid, (wid, salary, _s) in held.items()}, events


def walkAwayPrice(ask: int, value: float, nextValue: float) -> int:
    """The most a team pays: the asking salary, scaled up by how much better this player
    is than its next option (`FA_MAX_BID_EDGE`)."""
    edge = max(0.0, (value - nextValue) / max(1.0, abs(nextValue)))
    return int(round(ask * (1.0 + FA_MAX_BID_EDGE * edge)))


# ─── The adapter: one signing period in a real league ────────────────────────────────────

def _teamStanding(teams, season: int, brain) -> tuple:
    """({teamId: recent success 0-1}, {teamId: Appeal 0-1}), each relative to the league."""
    def _recent(titles):
        n = 0
        for t in titles or []:
            try:
                s = int(str(t).split()[-1])
            except (ValueError, IndexError):
                continue
            if s > season - FA_HISTORY_SEASONS:
                n += 1
        return n

    raw, appeal = {}, {}
    for t in teams:
        stats = getattr(t, 'seasonTeamStats', None) or {}
        w, l = float(stats.get('wins', 0) or 0), float(stats.get('losses', 0) or 0)
        winPct = w / (w + l) if (w + l) else 0.5
        raw[t.id] = (3 * _recent(getattr(t, 'floosbowlChampionships', None))
                     + 2 * _recent(getattr(t, 'leagueChampionships', None))
                     + _recent(getattr(t, 'divisionTitles', None)) + 2 * winPct)
        try:
            appeal[t.id] = float(brain.teamAppeal(t))
        except Exception:
            appeal[t.id] = 0.0

    def _norm(d):
        lo, hi = min(d.values(), default=0), max(d.values(), default=0)
        return {k: ((v - lo) / (hi - lo) if hi > lo else 0.5) for k, v in d.items()}
    return _norm(raw), _norm(appeal)


def _room(team, payroll) -> float:
    """Floobits a season this team can add in new salary: the budget check
    (`payroll.maxAffordable`, facility upkeep counted) priced as one two-season deal.
    No finances (the budget fails open) means no limit."""
    tid = getattr(team, 'id', None)
    if not payroll.hasFinances(tid):
        return float('inf')
    income, upkeep = payroll.financesOf(tid)
    contracts = payroll.schedule(team)
    return max(0, payroll.maxAffordable(contracts, 2, payroll.balanceOf(tid), income, upkeep))


REASONS = {
    'hometown': 'returns to his hometown team',
    'winner': 'wants to win',
    'comfort': 'likes the facilities',
    'opportunity': 'jumps at the chance',
}


def runSigningPeriod(pm, teams: list, brain, season: int, freeAgencyOrder: list,
                     freeAgencyDict: dict, leagueHighlights: list) -> list:
    """Run the whole signing period on the live league. Returns events in the FA draft's
    shape ('pick', 'cut') plus 'market' lines for the log and feed. Rosters change in
    place; holes left at the end are the caller's to fill."""
    from managers import payroll
    from managers.playerManager import isCutProtected, signedThisOffseason, fanVerdict

    events = []
    rank = {}
    for i, t in enumerate(freeAgencyOrder or teams):
        rank[getattr(t, 'id', None)] = i
    for t in teams:
        rank.setdefault(t.id, len(rank))
        if getattr(t, '_draftFilledSlots', None) is None:
            t._draftFilledSlots = set()
    byId = {t.id: t for t in teams}
    success, comfort = _teamStanding(teams, season, brain)
    released = {t.id: set() for t in teams}        # players a team let go in this market
    asks = {}

    # The team's own prospect takes an open slot first when he beats the best free agent
    # it could sign there (`prospectTakesSlot`, unchanged from the FA draft).
    for team in teams:
        coach = getattr(team, 'coach', None)
        for posVal, slots in POS_SLOTS.items():
            for slot in slots:
                if team.rosterDict.get(slot) is not None:
                    continue
                pros = [p for p in (getattr(team, 'prospects', None) or [])
                        if getattr(p, 'is_prospect', False) and p.position.value == posVal]
                if not pros:
                    continue
                best = max(pros, key=lambda p: brain.seasonRating(p, coach, team))
                fas = [f for f in pm.freeAgents if f.position.value == posVal
                       and not getattr(f, 'willRetire', False)]
                bestFa = max(fas, key=lambda f: brain.decisionValue(f, coach, team=team), default=None)
                try:
                    takes = brain.prospectTakesSlot(best, bestFa, coach, team)
                except Exception:
                    takes = bestFa is None
                if takes:
                    pm._promoteProspectIntoSlot(team, best, slot, freeAgencyDict,
                                                leagueHighlights, events)

    for passNo in range(1, max(1, FA_MARKET_ROUNDS) + 1):
        pool = [f for f in pm.freeAgents if not getattr(f, 'willRetire', False)
                and getattr(f, 'id', None) is not None]
        if not pool:
            break
        for f in pool:
            if f.id not in asks:
                asks[f.id] = payroll.askingSalary(f)
        motives = {f.id: motiveOf(f) for f in pool}
        poolById = {f.id: f for f in pool}

        def pull(pid, tid):
            f = poolById[pid]
            return motivePull(motives[pid], asks[pid],
                              isHome=getattr(f, 'homeTeamId', None) == tid,
                              success=success.get(tid, 0.5), comfort=comfort.get(tid, 0.5))

        wants, wid = [], 0
        room = {}
        for team in teams:
            coach = getattr(team, 'coach', None)
            room[team.id] = _room(team, payroll)
            values = {}

            def value(p):
                if p.id not in values:
                    values[p.id] = float(brain.decisionValue(p, coach, team=team))
                return values[p.id]

            def eligible(f):
                if f.id in released[team.id]:
                    return False            # not back the same offseason he was let go
                if (getattr(f, 'previousTeam', None) == team.name and fanVerdict(f) == 'walk'):
                    return False            # his own fans wanted him gone
                return True

            for posVal, slots in POS_SLOTS.items():
                fas = sorted((f for f in pool if f.position.value == posVal and eligible(f)),
                             key=value, reverse=True)
                if not fas:
                    continue
                pros = [p for p in (getattr(team, 'prospects', None) or [])
                        if getattr(p, 'is_prospect', False) and p.position.value == posVal]
                for slot in slots:
                    inc = team.rosterDict.get(slot)
                    if inc is None:
                        # An open slot: anyone, best first. Signed over the team's own
                        # prospect, the deal covers the seasons left on his window.
                        cands = fas[:FA_LIST_LENGTH]
                        term = None
                        if pros:
                            from constants import PROSPECT_DEVELOPMENT_WINDOW
                            best = max(pros, key=lambda p: brain.seasonRating(p, coach, team))
                            term = max(1, int(PROSPECT_DEVELOPMENT_WINDOW)
                                       - int(getattr(best, 'prospect_seasons', 0) or 0))
                        baseline, release, relSal = None, None, 0
                    else:
                        # An upgrade: never anyone signed or re-signed this offseason,
                        # filled in this market, or cut-protected.
                        if (slot in team._draftFilledSlots or signedThisOffseason(inc)
                                or isCutProtected(inc, season)):
                            continue
                        baseline = value(inc) + float(brain.starterStanding(inc, team, coach))
                        bar = (getattr(pm, '_faCutBars', None) or {}).get(team.id, 6.0)
                        cands = [f for f in fas if value(f) - baseline >= bar][:FA_LIST_LENGTH]
                        term, release, relSal = None, inc.id, payroll.salaryOf(inc)
                    if not cands:
                        continue
                    ranked = []
                    for i, f in enumerate(cands):
                        nxt = (value(cands[i + 1]) if i + 1 < len(cands)
                               else (baseline if baseline is not None else value(f)))
                        ranked.append((f.id, walkAwayPrice(asks[f.id], value(f), nxt)))
                    wants.append(Want(wid=wid, teamId=team.id, slot=slot, posVal=posVal,
                                      candidates=ranked, release=release,
                                      releaseSalary=relSal, term=term))
                    wid += 1

        signings, offers = resolve(asks, motives, wants, rank, pull, room)
        for e in offers:
            f = poolById[e['player']]
            t = byId[e['team']]
            line = (f"{t.name} {'outbid the ' + byId[e['over']].name + ' for' if e['over'] else 'offered'} "
                    f"{f.name} ({f.position.name}, {round(f.playerRating)}): {e['salary']}F")
            events.append({'type': 'market', 'team': t.name, 'teamAbbr': getattr(t, 'abbr', ''),
                           'player': f.name, 'playerId': f.id, 'salary': e['salary'],
                           'over': byId[e['over']].name if e['over'] else None, 'text': line})
        if not signings:
            break

        byWid = {w.wid: w for w in wants}
        faLists = {k: [p for p in pm.freeAgents if p.position.value == v]
                   for k, v in (('qb', 1), ('rb', 2), ('wr', 3), ('te', 4), ('k', 5))}
        for pid, (wantId, salary) in sorted(signings.items(), key=lambda kv: rank.get(byWid[kv[1][0]].teamId, 0)):
            w = byWid[wantId]
            team, f = byId[w.teamId], poolById[pid]
            teamAbbr = getattr(team, 'abbr', team.name[:3].upper())
            if w.release is not None:
                inc = team.rosterDict.get(w.slot)
                if inc is not None and inc.id == w.release:
                    pm.releasePlayerToFreeAgency(inc, team, faLists)
                    inc.termRemaining = 0
                    released[team.id].add(inc.id)
                    events.append({'type': 'cut', 'team': team.name, 'teamAbbr': teamAbbr,
                                   'playerId': inc.id, 'player': inc.name,
                                   'position': inc.position.name,
                                   'rating': round(getattr(inc, 'playerRating', 0), 1),
                                   'tier': getattr(getattr(inc, 'playerTier', None), 'name', ''),
                                   'slot': w.slot, 'forPlayer': f.name})
            if team.rosterDict.get(w.slot) is not None:
                logger.warning(f"FA market: {team.name} {w.slot} not free for {f.name}; skipped")
                continue
            wasHome = getattr(f, 'previousTeam', None) == team.name
            if f in pm.freeAgents:
                pm.freeAgents.remove(f)
            f.team = team
            f.freeAgentYears = 0
            team.rosterDict[w.slot] = f
            team._draftFilledSlots.add(w.slot)
            team.assignPlayerNumber(f)
            f.term = w.term or payroll.contractTerm(pm, f, season)
            f.termRemaining = f.term
            f.salary = int(salary) if payroll.salariesActive() else 0
            motive = motives[pid]
            reason = REASONS[motive] if pull(pid, team.id) > 0 or motive == 'opportunity' else 'for the money'
            freeAgencyDict[f"{team.name}_{f.name}"] = {
                'name': f.name, 'pos': f.position.name, 'rating': f.attributes.skillRating,
                'tier': f.playerTier.value, 'term': f.term,
                'previousTeam': getattr(f, 'previousTeam', 'Rookie'), 'roster': 'Starting'}
            text = (f"{f.name} ({f.position.name}) {'re-signs with' if wasHome else 'signs with'} "
                    f"the {team.name}, {f.term} season(s) at {f.salary}F: {reason}")
            leagueHighlights.insert(0, {'event': {'text': text}})
            events.append({'type': 'pick', 'team': team.name, 'teamAbbr': teamAbbr,
                           'playerId': f.id, 'player': f.name, 'position': f.position.name,
                           'rating': round(f.playerRating, 1), 'tier': f.playerTier.name,
                           'slot': w.slot, 'salary': f.salary, 'motive': motive,
                           'reason': reason, 'isResign': wasHome, 'market': True})
            logger.info(f"FA market pass {passNo}: {text}")
        signedIds = set(signings)
        for f in pool:
            if f.id not in signedIds:
                asks[f.id] = max(payroll.minimumSalary(), int(round(asks[f.id] * (1.0 - FA_ASK_DECAY))))
        logger.info(f"FA market pass {passNo}: {len(signings)} signing(s), {len(offers)} offer(s)")
    return events

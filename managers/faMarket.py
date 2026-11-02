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
import json
import logging
import math
import random
from dataclasses import dataclass, field

from constants import (FA_MARKET_ENABLED, FA_MARKET_ROUNDS, FA_ASK_DECAY, FA_MIN_RAISE,
                       FA_MAX_BID_EDGE, FA_MAX_BID_CAP, FA_LIST_LENGTH, FA_HOMETOWN_DISCOUNT, FA_WINNER_PULL,
                       FA_COMFORT_PULL, FA_OPPORTUNITY_ASK, FA_HISTORY_SEASONS,
                       FA_MOTIVE_PERSONALITY, FA_RESIGN_RESERVATION, FA_LOYALTY_PER_SEASON,
                       FA_LOYALTY_MAX, FA_RESIGN_OFFER_REACH, FA_PLAN_TOP)

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


# ─── Loyalty (owner, 2026-11-01: favorite players should not jump teams every offseason) ──
#
# {playerId: (teamId, consecutive seasons there ending with the season just played)}, read
# from `player_season_stats` at the safe point the season manager reads finances
# (`_refreshPayrollFinances`), never inside a signing.
_tenure = {}


def loadTenure(season: int) -> None:
    """Each player's run of consecutive seasons with the team he played the latest one for.
    Call where no write is open."""
    global _tenure
    try:
        from sqlalchemy import text
        from database.connection import get_session
        session = get_session()
        try:
            rows = session.execute(text(
                "SELECT player_id, season, team_id FROM player_season_stats "
                "WHERE team_id IS NOT NULL AND season <= :s ORDER BY player_id, season DESC"),
                {'s': int(season)}).fetchall()
        finally:
            session.close()
        byPlayer = {}
        for pid, s, tid in rows:
            byPlayer.setdefault(pid, []).append((s, tid))
        out = {}
        for pid, seasons in byPlayer.items():
            team, n, expect = seasons[0][1], 0, seasons[0][0]
            for s, tid in seasons:
                if tid != team or s != expect:
                    break
                n += 1
                expect -= 1
            out[pid] = (team, n)
        _tenure = out
    except Exception as e:
        logger.warning(f"FA market: could not load tenure: {e}")


def tenureWith(player, teamId) -> int:
    team, n = _tenure.get(getattr(player, 'id', None), (None, 0))
    return n if team == teamId and teamId is not None else 0


def loyaltyPull(player, teamId, ask: int) -> float:
    """Floobits of salary he gives up to stay with the team he has played for: a share of
    his ask per consecutive season there, capped."""
    return ask * min(float(FA_LOYALTY_MAX), float(FA_LOYALTY_PER_SEASON) * tenureWith(player, teamId))


def teamPull(player, team, ask: int, standing: tuple) -> float:
    """This player's pull toward `team` (Floobits): his motive plus his loyalty to the team
    he has played for, with `standing` from `teamStanding`."""
    success, comfort = standing
    tid = getattr(team, 'id', None)
    return motivePull(motiveOf(player), ask,
                      isHome=getattr(player, 'homeTeamId', None) == tid,
                      success=success.get(tid, 0.5), comfort=comfort.get(tid, 0.5)) \
        + loyaltyPull(player, tid, ask)


def resignOffer(player, team, standing: tuple, minimum: int) -> tuple:
    """(salary, pull): what a team offers a walk-year player it wants to keep, and his whole
    pull toward it (motive plus loyalty), which his decision weighs.

    It knows his motive and the range his sense of worth falls in, and offers enough to cover
    `FA_RESIGN_OFFER_REACH` of the way up that range, less what his MOTIVE gives it (a
    hometown discount is his to give), at least his ask less that and never more than
    `FA_MAX_BID_CAP` times his ask; never under the league minimum. ⚠️ LOYALTY IS NOT
    DISCOUNTED: taking it off the offer made loyalty a pay cut rather than a reason to stay,
    and retention did not move; it sits on top, on his side of the decision."""
    from managers import payroll
    ask = payroll.askingSalary(player)
    success, comfort = standing
    tid = getattr(team, 'id', None)
    motive = motivePull(motiveOf(player), ask, isHome=getattr(player, 'homeTeamId', None) == tid,
                        success=success.get(tid, 0.5), comfort=comfort.get(tid, 0.5))
    lo, hi = FA_RESIGN_RESERVATION.get(motiveOf(player), (1.0, 1.0))
    target = (lo + float(FA_RESIGN_OFFER_REACH) * (hi - lo)) * ask - motive
    salary = max(ask - motive, min(target, float(FA_MAX_BID_CAP) * ask))
    return max(int(minimum), int(math.ceil(salary))), motive + loyaltyPull(player, tid, ask)


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
    releaseFee: int = 0                              # the cut fee that release costs
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
        # A release frees his salary and costs the cut fee (counted here against the same
        # budget, a conservative read of a one-off charge).
        if w.release is None:
            return salary
        return salary - w.releaseSalary + w.releaseFee

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


# ─── Roster planning (owner, 2026-11-01) ─────────────────────────────────────────────────
#
# "how do they know they shouldnt go after an expensive player because they will only be
# able to afford league minimum after that?" Before bidding, each team weighs its slots
# together: one option per slot it is shopping (a candidate, or nobody), the combination
# worth the most that fits its budget. The plan orders its lists (the planned target first)
# and caps each bid so it cannot spend what the other slots were planned to use.

def planRoster(options: list, budget: float, top: int = FA_PLAN_TOP, enumCap: int = 4000) -> list:
    """options: per slot, [(playerId, gain, cost)]: gain is how much better the roster gets
    (in the GM's board value), cost the budget it uses. Returns, per slot, (playerId or None,
    cost) for the combination with the most total gain whose cost fits `budget`, never the
    same player for two slots. Small: an exhaustive search over each slot's best `top`
    options; a greedy fill by gain per Floobit past `enumCap` combinations."""
    import itertools
    opts = [[(None, 0.0, 0.0)] + sorted((o for o in slot if o[1] > 0), key=lambda o: -o[1])[:top]
            for slot in options]
    combos = 1
    for o in opts:
        combos *= len(o)
    best, bestKey = [(None, 0.0)] * len(opts), (0.0, 0.0)
    if combos <= enumCap:
        for choice in itertools.product(*opts):
            pids = [c[0] for c in choice if c[0] is not None]
            if len(pids) != len(set(pids)):
                continue
            cost = sum(c[2] for c in choice)
            if cost > budget:
                continue
            key = (sum(c[1] for c in choice), -cost)
            if key > bestKey:
                bestKey, best = key, [(c[0], c[2]) for c in choice]
        return best
    chosen = [(None, 0.0, 0.0)] * len(opts)
    while True:
        spent = sum(c[2] for c in chosen)
        used = {c[0] for c in chosen if c[0] is not None}
        pick, pickRatio = None, 0.0
        for i, slot in enumerate(opts):
            for o in slot[1:]:
                if o[0] in used:
                    continue
                dGain, dCost = o[1] - chosen[i][1], o[2] - chosen[i][2]
                if dGain <= 0 or spent + dCost > budget:
                    continue
                ratio = dGain / max(1.0, dCost)
                if ratio > pickRatio:
                    pick, pickRatio = (i, o), ratio
        if pick is None:
            return [(c[0], c[2]) for c in chosen]
        chosen[pick[0]] = pick[1]


def walkAwayPrice(ask: int, value: float, nextValue: float) -> int:
    """The most a team pays: the asking salary, scaled up by how much better this player
    is than its next option (`FA_MAX_BID_EDGE`), never past `FA_MAX_BID_CAP` times it."""
    edge = max(0.0, (value - nextValue) / max(1.0, abs(nextValue)))
    return int(round(ask * min(float(FA_MAX_BID_CAP), 1.0 + FA_MAX_BID_EDGE * edge)))


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
    from managers.frontOfficeBrain import cutFeeFor
    from managers.facilitiesManager import chargeCutFee

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
    unsignedPasses = {}                            # passes a player has gone unsigned

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

    def sign(team, f, slot, salary, term, releaseId, passLabel, motive, pullValue, ask):
        """Sign `f` into `slot` (releasing `releaseId` there first, cut fee charged). False,
        and nothing changed, if the fee cannot be paid or the slot is not free."""
        teamAbbr = getattr(team, 'abbr', team.name[:3].upper())
        releasedName = None
        if releaseId is not None:
            inc = team.rosterDict.get(slot)
            if inc is not None and inc.id == releaseId:
                fee = int(cutFeeFor(inc))
                if not chargeCutFee(team.id, fee):
                    logger.info(f"FA market: {team.name} cannot pay the {fee}F cut fee to "
                                f"release {inc.name}; {f.name} stays on the market")
                    return False
                faLists = {k: [p for p in pm.freeAgents if p.position.value == v]
                           for k, v in (('qb', 1), ('rb', 2), ('wr', 3), ('te', 4), ('k', 5))}
                pm.releasePlayerToFreeAgency(inc, team, faLists)
                inc.termRemaining = 0
                released[team.id].add(inc.id)
                releasedName = inc.name
                events.append({'type': 'cut', 'team': team.name, 'teamAbbr': teamAbbr,
                               'playerId': inc.id, 'player': inc.name,
                               'position': inc.position.name,
                               'rating': round(getattr(inc, 'playerRating', 0), 1),
                               'tier': getattr(getattr(inc, 'playerTier', None), 'name', ''),
                               'slot': slot, 'forPlayer': f.name, 'fee': fee})
        if team.rosterDict.get(slot) is not None:
            logger.warning(f"FA market: {team.name} {slot} not free for {f.name}; skipped")
            return False
        wasHome = getattr(f, 'previousTeam', None) == team.name
        if f in pm.freeAgents:
            pm.freeAgents.remove(f)
        f.team = team
        f.freeAgentYears = 0
        team.rosterDict[slot] = f
        team._draftFilledSlots.add(slot)
        team.assignPlayerNumber(f)
        f.term = int(term)
        f.termRemaining = f.term
        f.salary = int(salary) if payroll.salariesActive() else 0
        # A comparable contract, measured against his CURVE price (85% of it for an
        # 'opportunity' player, who takes that by choice), so prices move both ways: a
        # bidding war pushes players like him up, a star who only signs at a reduced price
        # pulls them down. The shrink toward 1.0 in `payroll.marketRate` anchors it to the
        # curve, so it cannot run away in either direction.
        reference = payroll.baseAskingSalary(f) * (FA_OPPORTUNITY_ASK if motive == 'opportunity' else 1.0)
        payroll.recordContract(f, f.salary, 'lastcall' if passLabel == 'last call' else 'market',
                               season, ask=reference)
        if passLabel == 'last call':
            reason = 'one-season deal'
        else:
            reason = REASONS[motive] if pullValue > 0 or motive == 'opportunity' else 'for the money'
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
                       'slot': slot, 'salary': f.salary, 'motive': motive,
                       'reason': reason, 'isResign': wasHome, 'market': True})
        logger.info(f"FA market {passLabel}: {text}")
        logger.info("FA market signing: " + json.dumps({
            'season': season, 'pass': passLabel, 'team': teamAbbr, 'playerId': f.id, 'player': f.name,
            'position': f.position.name, 'rating': round(f.playerRating, 1), 'motive': motive,
            'ask': int(ask), 'salary': f.salary, 'term': f.term, 'reason': reason,
            'returning': wasHome, 'released': releasedName}))
        return True

    for passNo in range(1, max(1, FA_MARKET_ROUNDS) + 1):
        pool = [f for f in pm.freeAgents if not getattr(f, 'willRetire', False)
                and getattr(f, 'id', None) is not None]
        if not pool:
            break
        # Re-priced every pass: the curve price times the market rate of comparable
        # contracts, which this market's own signings have just moved (an overpay raises
        # the players like him), less what he has dropped for going unsigned.
        for f in pool:
            asks[f.id] = max(payroll.minimumSalary(), int(round(
                payroll.askingSalary(f) * (1.0 - FA_ASK_DECAY) ** unsignedPasses.get(f.id, 0))))
        motives = {f.id: motiveOf(f) for f in pool}
        poolById = {f.id: f for f in pool}

        def pull(pid, tid):
            f = poolById[pid]
            return motivePull(motives[pid], asks[pid],
                              isHome=getattr(f, 'homeTeamId', None) == tid,
                              success=success.get(tid, 0.5), comfort=comfort.get(tid, 0.5)) \
                + loyaltyPull(f, tid, asks[pid])

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

            drafts = []

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
                        baseline, release, relSal, relFee = None, None, 0, 0
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
                        relFee = int(cutFeeFor(inc))
                    if not cands:
                        continue
                    if baseline is None:
                        # Skipping an open slot leaves it to the fill step after the market,
                        # which signs the cheapest player left: that is what a signing beats.
                        cheapest = min(fas, key=lambda f: asks[f.id])
                        floor = value(cheapest)
                    drafts.append({'slot': slot, 'posVal': posVal, 'cands': cands, 'term': term,
                                   'release': release, 'relSal': relSal, 'relFee': relFee,
                                   'base': baseline if baseline is not None else floor,
                                   'open': baseline is None})

            # THE ROSTER PLAN: one option per slot, the most gain that fits the budget once
            # every open slot has its minimum held back.
            if drafts:
                minimum = payroll.minimumSalary()
                openSlots = sum(1 for s in SLOTS if team.rosterDict.get(s) is None)
                budget = room[team.id] - minimum * openSlots

                def costOf(d, f, salary):
                    if d['open']:
                        return salary - minimum
                    return salary - d['relSal'] + d['relFee']

                plan = planRoster([[(f.id, value(f) - d['base'], costOf(d, f, asks[f.id])) for f in d['cands']]
                                   for d in drafts], budget)
                slack = budget - sum(c for _p, c in plan)
                logger.info("FA market plan: " + json.dumps({
                    'season': season, 'pass': passNo, 'team': getattr(team, 'abbr', team.name),
                    'budget': None if budget == float('inf') else int(budget),
                    'slots': [{'slot': d['slot'], 'upgrade': not d['open'],
                               'target': poolById[t].name if t is not None else None,
                               'cost': int(c)} for d, (t, c) in zip(drafts, plan)]}))
                for d, (target, plannedCost) in zip(drafts, plan):
                    # This slot may spend what the plan gave it plus whatever no slot was
                    # planned to use; never what the team's other slots were planned to.
                    avail = plannedCost + slack
                    byValue = d['cands']
                    ranked = []
                    for i, f in enumerate(byValue):
                        nxt = value(byValue[i + 1]) if i + 1 < len(byValue) else d['base']
                        walk = walkAwayPrice(asks[f.id], value(f), nxt)
                        cap = asks[f.id] + (avail - costOf(d, f, asks[f.id]))
                        floorAsk = asks[f.id] * (FA_OPPORTUNITY_ASK if motives[f.id] == 'opportunity' else 1.0)
                        maxBid = int(min(walk, cap)) if cap != float('inf') else walk
                        gain = value(f) - d['base']
                        if gain <= 0 or maxBid < floorAsk:
                            continue
                        ranked.append((f.id, maxBid, gain / max(1.0, costOf(d, f, asks[f.id]))))
                    # The planned target first, then the rest by value per Floobit.
                    ranked.sort(key=lambda r: (r[0] != target, -r[2]))
                    if not ranked:
                        continue
                    wants.append(Want(wid=wid, teamId=team.id, slot=d['slot'], posVal=d['posVal'],
                                      candidates=[(pid, mb) for pid, mb, _r in ranked],
                                      release=d['release'], releaseSalary=d['relSal'],
                                      releaseFee=d['relFee'], term=d['term']))
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
            # One structured line per offer, so a run can be read back offer by offer.
            logger.info("FA market offer: " + json.dumps({
                'season': season, 'pass': passNo, 'team': getattr(t, 'abbr', t.name), 'playerId': f.id,
                'player': f.name, 'position': f.position.name, 'rating': round(f.playerRating, 1),
                'motive': motives[f.id], 'ask': asks[f.id], 'salary': e['salary'],
                'over': getattr(byId[e['over']], 'abbr', None) if e['over'] else None}))
        # ⚠️ NO EARLY EXIT ON A QUIET PASS. It used to stop at the first pass with no
        # signings, before the decay below ran, so a star too dear in pass 1 never got the
        # cheaper passes and sat unsigned (a 96 kicker and a 94 QB, synthetic-fan run).

        byWid = {w.wid: w for w in wants}
        for pid, (wantId, salary) in sorted(signings.items(), key=lambda kv: rank.get(byWid[kv[1][0]].teamId, 0)):
            w = byWid[wantId]
            team, f = byId[w.teamId], poolById[pid]
            sign(team, f, w.slot, salary, w.term or payroll.contractTerm(pm, f, season), w.release,
                 passNo, motives[pid], pull(pid, team.id), asks[pid])
        signedIds = set(signings)
        for f in pool:
            if f.id not in signedIds:
                unsignedPasses[f.id] = unsignedPasses.get(f.id, 0) + 1
        logger.info(f"FA market pass {passNo}: {len(signings)} signing(s), {len(offers)} offer(s)")
    # THE LAST CALL (owner, 2026-11-01: "we really need to fix the problem of high skill
    # players not getting signed. we cant just have rosters get filled with cheap mid
    # talent"). Every unsigned player rated FA_LAST_CALL_MIN_RATING or more, best first, gets
    # a one-season offer from each team with a hole at his position or that he would
    # upgrade (the market's own rules: the GM's bar, nobody signed this offseason, no
    # protected player, the cut fee), at what its budget can spend after holding a minimum
    # salary back for its other open slots, never above his ask and never under
    # FA_LAST_CALL_FLOOR of his curve price. He takes the best offer by salary plus his
    # pull, an exact tie to the worse team. Next offseason he is back at his full price.
    from constants import FA_LAST_CALL_ENABLED, FA_LAST_CALL_MIN_RATING, FA_LAST_CALL_FLOOR
    if FA_LAST_CALL_ENABLED:
        minimum = payroll.minimumSalary()
        lcValues = {}

        def lcValue(team, p):
            key = (team.id, p.id)
            if key not in lcValues:
                lcValues[key] = float(brain.decisionValue(p, getattr(team, 'coach', None), team=team))
            return lcValues[key]

        leftovers = sorted((f for f in pm.freeAgents if not getattr(f, 'willRetire', False)
                            and getattr(f, 'id', None) is not None
                            and float(getattr(f, 'playerRating', 0) or 0) >= FA_LAST_CALL_MIN_RATING),
                           key=lambda f: -float(f.playerRating))
        for f in leftovers:
            ask = payroll.askingSalary(f)
            floor = max(minimum, int(round(FA_LAST_CALL_FLOOR * payroll.baseAskingSalary(f))))
            motive = motiveOf(f)
            best = None
            for team in teams:
                if f.id in released[team.id] or (
                        getattr(f, 'previousTeam', None) == team.name and fanVerdict(f) == 'walk'):
                    continue
                slots = POS_SLOTS[f.position.value]
                openHere = [sl for sl in slots if team.rosterDict.get(sl) is None]
                coach = getattr(team, 'coach', None)
                if openHere:
                    slot, releaseId, relSal, fee = openHere[0], None, 0, 0
                else:
                    held = [(sl, team.rosterDict.get(sl)) for sl in slots
                            if sl not in team._draftFilledSlots
                            and not signedThisOffseason(team.rosterDict.get(sl))
                            and not isCutProtected(team.rosterDict.get(sl), season)]
                    if not held:
                        continue
                    slot, inc = min(held, key=lambda h: lcValue(team, h[1]))
                    baseline = lcValue(team, inc) + float(brain.starterStanding(inc, team, coach))
                    bar = (getattr(pm, '_faCutBars', None) or {}).get(team.id, 6.0)
                    if lcValue(team, f) - baseline < bar:
                        continue
                    releaseId, relSal, fee = inc.id, payroll.salaryOf(inc), int(cutFeeFor(inc))
                otherOpen = sum(1 for sl in SLOTS if team.rosterDict.get(sl) is None) - (1 if releaseId is None else 0)
                spend = _room(team, payroll) - minimum * max(0, otherOpen) + (relSal - fee if releaseId else 0)
                offer = int(min(ask, spend)) if spend != float('inf') else int(ask)
                if offer < floor:
                    continue
                p = teamPull(f, team, ask, (success, comfort))
                key = (offer + p, -rank.get(team.id, 0))
                if best is None or key > best[0]:
                    best = (key, team, slot, offer, releaseId, p)
            if best is not None:
                _key, team, slot, offer, releaseId, p = best
                sign(team, f, slot, offer, 1, releaseId, 'last call', motive, p, ask)

    # Whoever the market could not place keeps the price he fell to for the hole-filling
    # step that follows (`payroll.askingSalary` honors `_marketAsk`), instead of jumping
    # back to his full price: a star nobody could afford signs cheaper rather than sitting.
    for f in pm.freeAgents:
        if getattr(f, 'id', None) in unsignedPasses:
            f._marketAsk = max(payroll.minimumSalary(), int(round(
                payroll.askingSalary(f) * (1.0 - FA_ASK_DECAY) ** unsignedPasses[f.id])))
    return events

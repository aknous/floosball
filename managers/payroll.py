"""Payroll: player salaries paid from the team Treasury (docs/TREASURY_PAYROLL_PLAN.md §5).

A contract carries a salary in Floobits a season, LOCKED when it is signed and paid at
every offseason payment run for the contract's term (`facilitiesManager.applyPaymentRun`
pays payroll before upkeep). Salary 0 means no salary: contracts signed before payroll
shipped are grandfathered, and so are the rosters a fresh league is created with.

The asking salary is share-denominated at signing, so new contracts track the league's
income, and convex in rating, so each point of roster quality costs more than the last.
That convexity is the main source of diminishing returns on money (G1).

⚠️ `player.salary` MEANS SOMETHING ONLY WHILE THE PLAYER IS ROSTERED. A player who walks
or is cut keeps the number until his next contract stamps a new one; everything that
reads payroll sums ROSTERED players, and the API shows a salary only for them.
"""
import logging

from constants import (POSITION_VALUE, SALARY_ENABLED, SALARY_MIN_SHARES, SALARY_FLOOR_RATING,
                       SALARY_TOP_SHARES, SALARY_EXPONENT, SALARY_PROSPECT_FRACTION)

logger = logging.getLogger(__name__)

ROSTER_SLOTS = ('qb', 'rb', 'wr1', 'wr2', 'te', 'k')

# The share unit new contracts are priced against. Set by the season manager at season
# start (last season's faucet, what everything in-season is priced against) and at
# offseason start (the season just finished, which next season is priced against).
_shareUnit = None


def setShareUnit(value: float) -> None:
    global _shareUnit
    _shareUnit = float(value) if value else None


def shareUnit() -> float:
    """The share unit for a signing made now. Falls back to the facility floor when the
    season manager has not set one (tests, tools), never to zero: a zero share unit
    would make every contract free."""
    if _shareUnit:
        return _shareUnit
    from constants import FACILITY_SHARE_UNIT_FLOOR
    return float(FACILITY_SHARE_UNIT_FLOOR)


def _positionKey(player) -> str:
    pos = getattr(player, 'position', None)
    return getattr(pos, 'name', None) or str(pos or '')


def salaryShares(rating: float, positionKey: str) -> float:
    """Asking salary in shares for a player of this rating at this position.

    minimum + top x position value x ((rating - floor) / (100 - floor)) ** exponent.
    The position term is the GM's own `POSITION_VALUE`, so a kicker asks what a kicker
    is worth to a team rather than a quarterback's price. The minimum is not scaled:
    it is the floor every roster spot costs.
    """
    span = max(1.0, 100.0 - float(SALARY_FLOOR_RATING))
    x = max(0.0, min(1.0, (float(rating or 0) - float(SALARY_FLOOR_RATING)) / span))
    posScale = float(POSITION_VALUE.get(positionKey, 1.0))
    return float(SALARY_MIN_SHARES) + float(SALARY_TOP_SHARES) * posScale * (x ** float(SALARY_EXPONENT))


def leagueBaseline(unit: float = None) -> int:
    """What the league pays every team at season start (docs/TREASURY_PAYROLL_PLAN.md §9,
    decision 7). Flat for every team, so every Floobit a fan brings lands on top. With
    payroll on it is share-denominated (`FUNDING_BASELINE_SHARES`), sized to a
    minimum-salary roster plus a modest facility set, and never under the old flat
    `FUNDING_BASELINE_PER_TEAM`."""
    from constants import FUNDING_BASELINE_PER_TEAM, FUNDING_BASELINE_SHARES
    flat = int(FUNDING_BASELINE_PER_TEAM)
    if not SALARY_ENABLED:
        return flat
    return max(flat, int(round(float(FUNDING_BASELINE_SHARES) * float(unit or shareUnit()))))


def minimumSalary(unit: float = None) -> int:
    """What the cheapest roster spot costs a season (G6: the league baseline covers six)."""
    return max(1, int(round(float(SALARY_MIN_SHARES) * float(unit or shareUnit()))))


def askingSalary(player, unit: float = None, prospect: bool = False) -> int:
    """The salary this player asks for a contract signed now, in Floobits a season.

    A prospect promoted onto the roster signs a cheap deal (`SALARY_PROSPECT_FRACTION`
    of his asking salary, never under the minimum): the draft stays the poor team's
    route to talent.
    """
    unit = float(unit or shareUnit())
    shares = salaryShares(getattr(player, 'playerRating', 0) or 0, _positionKey(player))
    floobits = int(round(shares * unit))
    if prospect:
        floobits = int(round(floobits * float(SALARY_PROSPECT_FRACTION)))
    return max(minimumSalary(unit), floobits)


def stampSalary(player, unit: float = None, prospect: bool = False) -> int:
    """Lock a salary onto a contract being signed now. With payroll off it stamps 0."""
    player.salary = askingSalary(player, unit, prospect) if SALARY_ENABLED else 0
    return player.salary


def salaryOf(player) -> int:
    return int(getattr(player, 'salary', 0) or 0)


def rosterPlayers(team) -> list:
    roster = getattr(team, 'rosterDict', None) or {}
    return [roster.get(s) for s in ROSTER_SLOTS if roster.get(s) is not None]


def seasonPayroll(team) -> int:
    """This season's payroll: the salaries of everyone on the roster."""
    return sum(salaryOf(p) for p in rosterPlayers(team))


def committedPayroll(team, seasonsAhead: int = 1, exclude=None) -> int:
    """Salary the roster is already committed to over the next `seasonsAhead` paid
    seasons, counting each contract only for the seasons it still runs.

    Read at the payment run (contracts already decremented for the offseason), a
    contract with `termRemaining` k is paid k more times, this run included.
    `exclude` is a set of player ids to leave out (a player being replaced).
    """
    exclude = exclude or set()
    total = 0
    for p in rosterPlayers(team):
        if id(p) in exclude or getattr(p, 'id', None) in exclude:
            continue
        runs = max(0, int(getattr(p, 'termRemaining', 0) or 0))
        total += salaryOf(p) * min(runs, int(seasonsAhead))
    return total


# ─── Budget: can a team afford a contract? (plan §5 "Budget") ───────────────────────────
#
# A team signs or re-signs a player only if its balance plus a cautious estimate of its
# income covers every committed salary for the rest of every contract AND the upkeep of
# its current facility levels. Paid season s (s = 1 is this offseason's payment run)
# must satisfy
#     sum(salary x min(runs, s)) + upkeep x s  <=  balance + income x (s - 1)
# because the balance is all the first run has; each later season adds a season of
# income before its run. Counting upkeep stops a signing from knocking a facility down
# by accident: a shortfall can then only come from income really dropping.

# {teamId: (incomeEstimate, upkeepPerSeason)}, set by the season manager each offseason.
_finances = {}


def setFinances(finances: dict) -> None:
    global _finances
    _finances = dict(finances or {})


def financesOf(teamId) -> tuple:
    return _finances.get(teamId, (0, 0))


def hasFinances(teamId) -> bool:
    """Whether this team's budget is known. ⚠️ FAILS OPEN: with no finances (they could
    not be read, or nothing has set them) the budget check is skipped rather than
    refusing every contract. Overspending is still caught: a payroll the season-end
    balance cannot cover forces cuts, and the payment run never pays into debt."""
    return teamId in _finances


def balanceOf(teamId) -> int:
    """The team's Treasury right now (cut fees move it during the offseason)."""
    try:
        from database.connection import get_session
        from managers.facilitiesManager import getTreasury
        session = get_session()
        try:
            return int(getTreasury(session, teamId))
        finally:
            session.close()
    except Exception:
        return 0


def contractRuns(player, preDecrement: bool = False) -> int:
    """How many more payment runs a contract is paid at. Before the offseason's contract
    decrement (the re-sign step), the season just played still counts in termRemaining."""
    t = int(getattr(player, 'termRemaining', 0) or 0)
    return max(0, t - 1) if preDecrement else max(0, t)


def schedule(team, preDecrement: bool = False, exclude=None, skipRetiring: bool = True) -> list:
    """[(salary, runs)] for the roster's standing contracts."""
    exclude = exclude or set()
    out = []
    for p in rosterPlayers(team):
        if id(p) in exclude:
            continue
        if skipRetiring and getattr(p, 'willRetire', False):
            continue
        sal = salaryOf(p)
        runs = contractRuns(p, preDecrement)
        if sal > 0 and runs > 0:
            out.append((sal, runs))
    return out


def maxAffordable(contracts: list, term: int, balance: int, income: float, upkeep: float,
                  includeUpkeep: bool = True) -> int:
    """The largest salary a new contract of `term` seasons can carry on top of
    `contracts` ([(salary, runs)]) and still fit every paid season. Negative when the
    standing commitments already do not fit."""
    term = max(1, int(term))
    horizon = max([term] + [r for _s, r in contracts])
    best = None
    for s in range(1, horizon + 1):
        need = sum(sal * min(r, s) for sal, r in contracts)
        if includeUpkeep:
            need += upkeep * s
        have = balance + income * (s - 1)
        cap = (have - need) / min(term, s)
        best = cap if best is None else min(best, cap)
    return int(best if best is not None else balance)


def fits(contracts: list, balance: int, income: float, upkeep: float,
         includeUpkeep: bool = True) -> bool:
    """Whether standing contracts fit every paid season."""
    horizon = max([1] + [r for _s, r in contracts])
    for s in range(1, horizon + 1):
        need = sum(sal * min(r, s) for sal, r in contracts)
        if includeUpkeep:
            need += upkeep * s
        if need > balance + income * (s - 1):
            return False
    return True


def contractTerm(playerManager, player, season: int) -> int:
    """The term a contract signed now runs, rolled from a seed fixed by the player and
    the season, so the re-sign decision (and the Front Office desk, which projects it)
    prices the same deal step 3 then signs."""
    import hashlib
    import random
    seed = int(hashlib.md5(f"contract:{getattr(player, 'id', id(player))}:{season}".encode())
               .hexdigest()[:12], 16)
    try:
        return int(playerManager._getPlayerTerm(player, rng=random.Random(seed)))
    except TypeError:
        return int(playerManager._getPlayerTerm(player))    # a term roll with no seed hook


# ─── When a team can't make payroll (plan §5) ───────────────────────────────────────────

def nextSeasonPayroll(team) -> int:
    """At season end (before the offseason's contract decrement): the salaries the
    coming payment run will owe for players who stay under contract. Walk-year and
    retiring players are not owed; their slots are refilled in the offseason."""
    return sum(sal for sal, _runs in schedule(team, preDecrement=True))


def chooseForcedCuts(entries: list, gap: int) -> list:
    """Who a team that cannot cover next season's payroll cuts to close `gap`.

    entries: [{'player', 'salary', 'value', 'protected'}] (value = the GM's own value).

    The fewest unprotected players, with the least value lost, whose salaries close the
    gap; usually one expensive player, sometimes two cheaper ones if that costs less.
    When every unprotected player together cannot close it, protected players are added
    from least to most valuable until it closes. Then nobody whose salary is no longer
    needed is cut: protected players are kept back first, most valuable first, then
    unprotected ones the same way. Returns the entries to cut.
    """
    if gap <= 0:
        return []
    paid = [e for e in entries if int(e.get('salary', 0) or 0) > 0]
    unprotected = [e for e in paid if not e.get('protected')]
    protected = [e for e in paid if e.get('protected')]

    best = None
    n = len(unprotected)
    for mask in range(1, 1 << n):
        chosen = [unprotected[i] for i in range(n) if (mask >> i) & 1]
        if sum(e['salary'] for e in chosen) < gap:
            continue
        key = (len(chosen), sum(e['value'] for e in chosen))
        if best is None or key < best[0]:
            best = (key, chosen)
    if best is not None:
        return best[1]

    # Last resort: everyone unprotected, then protected players least valuable first.
    cut = list(unprotected)
    total = sum(e['salary'] for e in cut)
    for e in sorted(protected, key=lambda e: e['value']):
        if total >= gap:
            break
        cut.append(e)
        total += e['salary']

    # No unneeded cuts.
    for group in ([e for e in cut if e.get('protected')], [e for e in cut if not e.get('protected')]):
        for e in sorted(group, key=lambda e: -e['value']):
            if total - e['salary'] >= gap:
                cut.remove(e)
                total -= e['salary']
    return cut

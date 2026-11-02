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

from logger_config import get_logger
logger = get_logger('floosball.payroll')

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


def baseAskingSalary(player, unit: float = None) -> int:
    """The curve price alone: what the asking salary would be with no comparables."""
    unit = float(unit or shareUnit())
    shares = salaryShares(getattr(player, 'playerRating', 0) or 0, _positionKey(player))
    return max(minimumSalary(unit), int(round(shares * unit)))


def askingSalary(player, unit: float = None, prospect: bool = False) -> int:
    """The salary this player asks for a contract signed now, in Floobits a season: the
    curve price times the market rate of comparable contracts (`marketRate`).

    A prospect promoted onto the roster signs a cheap deal (`SALARY_PROSPECT_FRACTION`
    of the curve price, never under the minimum, comparables ignored): the draft stays the
    poor team's route to talent.

    `player._marketAsk`, set by the free agency market for a player it could not place,
    caps the ask for the rest of that FA step, so the hole-filling step after it signs him
    at the price he had fallen to rather than his full price.
    """
    base = baseAskingSalary(player, unit)
    minimum = minimumSalary(unit)
    if prospect:
        return max(minimum, int(round(base * float(SALARY_PROSPECT_FRACTION))))
    ask = int(round(base * marketRate(_positionKey(player), getattr(player, 'playerRating', 0) or 0)))
    capped = getattr(player, '_marketAsk', None)
    if capped is not None:
        ask = min(ask, int(capped))
    return max(minimum, ask)


# ─── Comparable contracts (owner, 2026-11-01) ───────────────────────────────────────────
#
# "if a player signs for that high of a price, shouldnt that drive prices for other players?
# ... contracts are based on what a comparable player recently received. this should be an
# incentive to not overspend because that will make players more expensive"
#
# Every free agency market signing records its PREMIUM: the salary over the asking price he
# was offered against. The market never opens below that ask, so an uncontested signing is
# 1.0 and a bidding war is above it, up to the bid cap. The market rate is 1 plus the recency- and rating-weighted average premium of
# recent comparables, shrunk toward 1.0. ⚠️ MEASURED AGAINST THE ASK, NOT THE CURVE: a ratio
# to the curve feeds the market rate back into itself (a signing at today's rate reads as
# today's rate, and every discount compounds), which drifted prices down every offseason
# on the first run. Against the ask nothing compounds: overpaying raises prices, and they
# return to the curve as those contracts age out. Re-signs and hole fills sign at their
# ask by definition and carry no signal, so only market signings are recorded.
#
# Kept in memory as (season, position, rating, premium): loaded from `contract_signings` at
# the safe points the season manager already reads finances (`_refreshPayrollFinances`),
# appended live, written back after the FA step. ⚠️ NEVER a database read inside a signing:
# those run inside other open writes, and SQLite has one writer. Not loaded means no
# comparables, a market rate of 1.0.

_comps = []            # [(season, position, rating, premium)]
_compSeason = 0
_pendingContracts = []


def marketRate(positionKey: str, rating: float) -> float:
    """1 plus the weighted average premium recent comparable contracts paid over their ask,
    shrunk toward 1.0 by `FA_COMP_PRIOR` contracts at exactly the ask, and capped."""
    from constants import (FA_COMP_RECENCY, FA_COMP_RATING_WINDOW, FA_COMP_PRIOR,
                           FA_COMP_MIN, FA_COMP_MAX)
    num, den = 0.0, float(FA_COMP_PRIOR)
    for season, pos, r, premium in _comps:
        if pos != positionKey:
            continue
        near = 1.0 - abs(float(rating) - float(r)) / float(FA_COMP_RATING_WINDOW)
        if near <= 0:
            continue
        w = near * float(FA_COMP_RECENCY) ** max(0, _compSeason - season)
        num += w * (premium - 1.0)
        den += w
    return max(float(FA_COMP_MIN), min(float(FA_COMP_MAX), 1.0 + num / den))


def recordContract(player, salary: int, kind: str, season: int, ask: float = None) -> None:
    """A market contract was signed: its premium over `ask` counts as a comparable."""
    global _compSeason
    if not salariesActive() or not salary or not ask:
        return
    premium = float(salary) / max(1.0, float(ask))
    pos, rating = _positionKey(player), float(getattr(player, 'playerRating', 0) or 0)
    _compSeason = max(_compSeason, int(season or 0))
    _comps.append((int(season or 0), pos, rating, premium))
    _pendingContracts.append({'season': int(season or 0), 'player_id': getattr(player, 'id', None),
                              'position': pos, 'rating': rating, 'salary': int(salary),
                              'ask': int(round(ask)), 'premium': premium, 'kind': kind})


def flushContracts() -> int:
    """Write the contracts recorded since the last flush. Call where no write is open."""
    global _pendingContracts
    if not _pendingContracts:
        return 0
    rows, _pendingContracts = _pendingContracts, []
    try:
        from database.connection import get_session
        from database.models import ContractSigning
        session = get_session()
        try:
            session.add_all([ContractSigning(**r) for r in rows])
            session.commit()
        finally:
            session.close()
        return len(rows)
    except Exception as e:
        logger.warning(f"Payroll: could not save {len(rows)} contract(s): {e}")
        return 0


def loadContracts(season: int) -> None:
    """Load the comparables for an offseason running under `season` (its own contracts
    and the ones before it within `FA_COMP_SEASONS`). Flushes first so nothing recorded is
    lost. Call where no write is open."""
    global _comps, _compSeason
    from constants import FA_COMP_SEASONS
    flushContracts()
    try:
        from database.connection import get_session
        from database.models import ContractSigning
        session = get_session()
        try:
            rows = (session.query(ContractSigning)
                    .filter(ContractSigning.season > int(season) - int(FA_COMP_SEASONS),
                            ContractSigning.season <= int(season)).all())
            _comps = [(r.season, r.position, float(r.rating), float(r.premium)) for r in rows]
            _compSeason = int(season)
        finally:
            session.close()
    except Exception as e:
        logger.warning(f"Payroll: could not load comparable contracts: {e}")


# ─── When salaries start (owner, 2026-11-01) ───────────────────────────────────────────
#
# Salaries are charged only after the new funding (the share-denominated league baseline,
# gate revenue and the donation match) has run through one full season, so Treasuries are
# not still the old flat-baseline balances the first time payroll is due. The first season
# that creates its funding records under this code is stamped FIRST_FUNDED_KEY; its season
# end stamps SALARIES_FROM_KEY, and from that offseason on contracts carry a salary, the
# budget applies, the season-end check can cut and the re-sign limit comes off.
# `SALARY_ENABLED` stays the feature flag: the league baseline is share-denominated from
# the first funded season, since building Treasuries is that season's whole point.

FIRST_FUNDED_KEY = 'treasury_first_funded_season'
SALARIES_FROM_KEY = 'salaries_start_season'
_activeCache = (0.0, None)


def _readSetting(key):
    from database.connection import get_session
    from database.models import AppSetting
    session = get_session()
    try:
        row = session.query(AppSetting).filter_by(key=key).first()
        return row.value if row else None
    finally:
        session.close()


def salariesActive() -> bool:
    """Whether contracts carry salaries yet. Cached for a few seconds: an FA draft asks
    this for every signing. ⚠️ FAILS CLOSED to "not yet" when the setting cannot be read,
    which is the pre-payroll behavior every path already handles."""
    global _activeCache
    if not SALARY_ENABLED:
        return False
    import time
    at, value = _activeCache
    if value is not None and time.time() - at < 5.0:
        return value
    try:
        value = _readSetting(SALARIES_FROM_KEY) is not None
    except Exception:
        value = False
    _activeCache = (time.time(), value)
    return value


def resetSalariesActiveCache() -> None:
    global _activeCache
    _activeCache = (0.0, None)


def markFundedSeasonStarted(season: int, session) -> None:
    """A season created its funding records under this code. Only the first is kept.

    ⚠️ WRITES ON THE CALLER'S SESSION, which commits. The caller
    (`_initializeTeamFunding`) holds an open write, and SQLite has one writer: a second
    session here waits out the 30s busy_timeout and fails "database is locked" (measured on
    the first run), which also freezes the event loop the API shares."""
    if not SALARY_ENABLED:
        return
    from database.models import AppSetting
    if session.query(AppSetting).filter_by(key=FIRST_FUNDED_KEY).first() is None:
        session.add(AppSetting(key=FIRST_FUNDED_KEY, value=str(int(season))))
        session.flush()
        logger.info(f"Payroll: season {season} is the first funded season; salaries start at its end")


def markSalariesStartIfDue(completedSeason: int) -> bool:
    """Season end: once the first funded season has been played through, salaries start.
    Returns True the moment they do."""
    if not SALARY_ENABLED or _readSetting(SALARIES_FROM_KEY) is not None:
        return False
    first = _readSetting(FIRST_FUNDED_KEY)
    if first is None or int(completedSeason) < int(first):
        return False
    from game_rules import _writeAppSetting
    _writeAppSetting(SALARIES_FROM_KEY, str(int(completedSeason)))
    resetSalariesActiveCache()
    logger.info(f"Payroll: salaries start this offseason (after season {completedSeason})")
    return True


def stampSalary(player, unit: float = None, prospect: bool = False) -> int:
    """Lock a salary onto a contract being signed now. Stamps 0 until salaries start."""
    player.salary = askingSalary(player, unit, prospect) if salariesActive() else 0
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
                  includeUpkeep: bool = True, seasons: int = None) -> int:
    """The largest salary a new contract of `term` seasons can carry on top of
    `contracts` ([(salary, runs)]) and still fit every paid season, or only the first
    `seasons` of them. Negative when the standing commitments already do not fit."""
    term = max(1, int(term))
    horizon = max([term] + [r for _s, r in contracts])
    if seasons:
        horizon = min(horizon, max(1, int(seasons)))
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


# ─── The in-season warning (plan §5, "Warn fans during the season") ─────────────────────
#
# The season-end check (`seasonManager._enforcePayrollAtSeasonEnd`) cuts players when the
# balance cannot cover `nextSeasonPayroll`. It runs right after the season-end fan
# deposit, so the balance it reads is today's Treasury plus the gate revenue still to
# come this regular season plus that deposit (and the league's match on it). The warning
# projects exactly that, so it fires only where the check would.

def projectSeasonEndBalance(balance: int, gateSoFar: int, gateWeeks: int, weeksLeft: int,
                            deposit: int) -> int:
    """Today's Treasury, plus the rest of this season's gate at the rate earned so far,
    plus the season-end deposit."""
    rate = (float(gateSoFar) / gateWeeks) if gateWeeks > 0 else 0.0
    return int(round(int(balance) + rate * max(0, int(weeksLeft)) + int(deposit)))


def seasonEndDeposit(session, teamId: int, season: int, shareUnit: float) -> int:
    """What this team's fans would deposit at season end at their CURRENT Floobit
    balances (`team_funding_pct` of each), plus the league's match on it. An estimate:
    fans earn and spend before then."""
    import math
    from constants import DEFAULT_FUNDING_PCT, DONATION_MATCH_ENABLED
    from database.models import User
    from database.repositories.card_repositories import CurrencyRepository
    from managers import gateRevenue
    repo = CurrencyRepository(session)
    total = 0
    for user in session.query(User).filter(User.favorite_team_id == teamId).all():
        pct = getattr(user, 'team_funding_pct', DEFAULT_FUNDING_PCT)
        pct = max(0, min(100, DEFAULT_FUNDING_PCT if pct is None else pct))
        currency = repo.getByUser(user.id)
        amount = math.floor((currency.balance if currency else 0) * pct / 100.0)
        if amount <= 0:
            continue
        total += amount
        if DONATION_MATCH_ENABLED:
            _basis, match = gateRevenue.matchFor(
                amount, gateRevenue.matchedBasisThisSeason(session, user.id, season), shareUnit)
            total += match
    return int(total)


def payrollOutlook(session, team, season: int, regularSeasonWeeks: int,
                   shareUnit: float) -> dict:
    """Whether this team is on course to fall short of next season's payroll at the
    season-end check. None with payroll off or nothing owed."""
    if not salariesActive() or team is None:
        return None
    owed = nextSeasonPayroll(team)
    if owed <= 0:
        return None
    from database.models import TreasuryIncome
    from managers import facilitiesManager, gateRevenue
    balance = int(facilitiesManager.getTreasury(session, team.id))
    gateSoFar = gateRevenue.gateThisSeason(session, team.id, season)
    gateWeeks = session.query(TreasuryIncome).filter_by(
        team_id=team.id, season=season, kind='gate').count()
    weeksLeft = max(0, int(regularSeasonWeeks) - gateWeeks)
    deposit = seasonEndDeposit(session, team.id, season, shareUnit)
    projected = projectSeasonEndBalance(balance, gateSoFar, gateWeeks, weeksLeft, deposit)
    return {
        'owedNextSeason': owed,
        'projectedBalance': projected,
        'shortBy': max(0, owed - projected),
    }

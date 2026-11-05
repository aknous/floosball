"""Facility economy engine (Markets→Facilities system).

Share-denominated costs, direct contributions, fans' ranked ballots, and the
offseason PAYMENT RUN (upkeep first, then projects in the team's ranked order,
one upgrade per facility per year), plus decay/construction.

The core resolver (`resolvePaymentRun`) is a PURE function over plain dicts so it
can be validated without a DB. The DB-bound helpers below wrap it for live use.
See docs/MARKETS_FACILITIES_PLAN.md and docs/TREASURY_PAYROLL_PLAN.md §3.

⚠️ ONE UPGRADE PER FACILITY PER YEAR (owner, 2026-10-22). A "year" runs from one
payment run to the next. A facility built by the run cannot be built again by fan
funding until the next run; a facility fans built mid-season is skipped by the run
that follows. Projects record who built them in `built_by` ('run' | 'fans'), which
is what lets the two halves of that rule be told apart. Legacy rows (NULL) were
all season-end or mid-season builds under the old system and are read as 'fans'.
"""
from logging import getLogger
from constants import (FACILITY_CATALOG, FACILITY_MAX_LEVEL,
                       FACILITY_UPGRADE_COST_SHARES, FACILITY_UPKEEP_SHARES,
                       FACILITY_DECAY_LEVELS, APPEAL_LEVEL_WEIGHTS,
                       FACILITY_SHARE_UNIT_FLOOR, FACILITY_SHARE_CAP_PERCENTILE,
                       FACILITY_SHARE_CAP_MIN_USERS)

logger = getLogger("floosball.facilities")


# ─── Cost model (share-denominated) ──────────────────────────────────────────

def upkeepCostFloobits(level: int, shareUnit: float) -> int:
    """Floobits to maintain a facility at `level` for one season."""
    level = max(0, min(FACILITY_MAX_LEVEL, level))
    return int(round(FACILITY_UPKEEP_SHARES[level] * shareUnit))


def upgradeCostFloobits(currentLevel: int, shareUnit: float) -> int:
    """Floobits to take a facility from `currentLevel` to currentLevel+1.
    Returns 0 when already at max (no further upgrade)."""
    target = currentLevel + 1
    if target > FACILITY_MAX_LEVEL:
        return 0
    return int(round(FACILITY_UPGRADE_COST_SHARES[target] * shareUnit))


def projectCostFloobits(cost_shares: float, shareUnit: float) -> int:
    """Live Floobit target for an open project (costs float with the economy)."""
    return int(round(cost_shares * shareUnit))


def computeAppeal(facilities: dict) -> float:
    """Appeal = weighted sum of facility levels — a facility-quality readout.
    (Historically set FA draft order; that's now worst-first by record, so Appeal
    no longer affects the draft.) `facilities` = {facility_key: level}."""
    return sum((facilities or {}).get(k, 0) * APPEAL_LEVEL_WEIGHTS.get(k, 1.0)
               for k in FACILITY_CATALOG)


# ─── Ranked ballots ──────────────────────────────────────────────────────────

def fallbackOrder(levels: dict) -> list:
    """Weakest facility first, ties in catalog order. The order a team with no
    ballots builds in, and the tie-break for the combined ranking."""
    catalog = list(FACILITY_CATALOG)
    return sorted(catalog, key=lambda k: ((levels or {}).get(k, 0), catalog.index(k)))


def normalizeBallot(ballot, levels: dict) -> list:
    """A fan's ranking as a full ordering of the catalog: unknown keys and repeats
    dropped, anything they left out appended in the fallback order."""
    seen, out = set(), []
    for k in (ballot or []):
        if k in FACILITY_CATALOG and k not in seen:
            out.append(k)
            seen.add(k)
    out.extend(k for k in fallbackOrder(levels) if k not in seen)
    return out


def combinedOrder(levels: dict, ballots: list) -> list:
    """The team's build order from its fans' ranked ballots (owner, 2026-10-22).

    A points count: with n facilities, a fan's first choice scores n, the last 1.
    Ties go to the facility the team is weakest in, then catalog order. With no
    ballots this is exactly `fallbackOrder`. A team with one fan follows that
    fan's list.
    """
    n = len(FACILITY_CATALOG)
    points = {k: 0 for k in FACILITY_CATALOG}
    for ballot in (ballots or []):
        for i, k in enumerate(normalizeBallot(ballot, levels)):
            points[k] += n - i
    tieBreak = {k: i for i, k in enumerate(fallbackOrder(levels))}
    return sorted(FACILITY_CATALOG, key=lambda k: (-points[k], tieBreak[k]))


# ─── The pure payment-run resolver ───────────────────────────────────────────

def resolvePaymentRun(facilities: list, projects: list, treasury: int, shareUnit: float,
                      order: list = None, waivedKeys=None, blockedKeys=None,
                      payroll: int = 0) -> dict:
    """Resolve one team's offseason payment run. PURE — no DB, no mutation of
    inputs; returns the new state + a log.

    facilities: [{'key','level','upkeep_funded'}]  (upkeep_funded = direct fan funding this season)
    projects:   [{'id','facility_key','target_level','cost_shares','funded'}]  (OPEN only, at most one per facility)
    treasury:   Floobits available to the run.
    order:      the team's build order (`combinedOrder`); defaults to the fallback order.
    waivedKeys: facilities whose upkeep is waived this run — those fans built mid-season
                this year (under construction the year they completed).
    blockedKeys: facilities that may not be upgraded by this run (built mid-season this
                year: one upgrade per facility per year).
    payroll:    the coming season's salaries (`payroll.seasonPayroll`), paid FIRST.

    Steps: (0) payroll; (1) upkeep, choosing the affordable set that preserves the most value;
    (2) decay of anything unpaid; (3) projects in ranked order, at most one level per
    facility, a project whose facility decayed retargeting to the level it lost.

    Returns {'facilities':[{key,level,upkeepMet,upkeepPaid,upkeepCost}],
             'projects':[{id,facility_key,funded,built,target_level,cost_shares}],
             'payrollPaid':int, 'payrollShort':int, 'leftover':int, 'log':[...]}.
    """
    pot = int(treasury)
    log = []

    # 0. PAYROLL — PLAYERS GET FIRST CLAIM (docs/TREASURY_PAYROLL_PLAN.md §5). A team
    # short of money pays its players and lets its facilities go unpaid. A shortfall here
    # should not happen (signings are checked for affordability and a payroll the
    # season-end balance cannot cover forces cuts before the offseason), so if one does it
    # pays what it can and logs it: the balance never goes negative.
    owed = max(0, int(payroll or 0))
    payrollPaid = min(owed, pot)
    pot -= payrollPaid
    payrollShort = owed - payrollPaid
    if owed:
        log.append(f"payroll {payrollPaid}/{owed}")
    if payrollShort:
        log.append(f"PAYROLL SHORT by {payrollShort}")
    waivedKeys = set(waivedKeys or [])
    blockedKeys = set(blockedKeys or [])

    # 1. UPKEEP — SAVE THE MOST VALUE THE POT CAN ACTUALLY BUY.
    #
    # ⚠️ A PARTIAL PAYMENT SAVES NOTHING AND IS NOT BANKED. A facility decays unless its
    # upkeep is met IN FULL, and `prepareSeasonStart` resets `upkeep_funded` to 0 every
    # season — so Floobits poured into a shortfall the pot cannot close are simply gone.
    # This used to pay highest-level-first in full-shortfall order, which in a genuine
    # shortfall spent the entire pot on the most expensive bill and then let it decay
    # anyway. Measured on production: Pinecones, 200F against 383F owed, put all 200F into
    # a 247F locker room, lost it regardless, and lost the three cheaper facilities too —
    # 136F would have saved all three. Four levels gone and nothing bought.
    #
    # So the choice is made over SUBSETS rather than in sequence: pick the affordable set
    # of facilities that preserves the most value, and pay those in full. Anything not
    # chosen is paid NOTHING, because part of a bill is worth exactly zero.
    #
    # Value of saving a facility = what it would cost to rebuild the level it is about to
    # lose (`upgradeCostFloobits(level - 1)`), so a level-3 building is worth more than a
    # level-1 and the trade-off is priced in real Floobits rather than by counting levels.
    #
    # ⚠️ EXACT, NOT GREEDY. This is a knapsack, and greedy by value density is not optimal
    # on one — but a club has at most FACILITY_MAX_LEVEL-ish facilities (5 today), so all
    # 2**n subsets are enumerable and the answer is exact. Ordering by level is kept only
    # as the tie-break, so "most investment protected first" still decides between sets of
    # equal value.
    #
    # ⚠️ AN OPEN PROJECT NO LONGER WAIVES UPKEEP. Under the single vote a project was a
    # deliberate choice and its facility was "under construction"; with ranked ballots
    # every facility below the top level always has its next level open, so that rule
    # would waive every bill. Only a facility fans actually BUILT this year is waived.
    facState = []
    candidates = []          # (key, level, cost, funded, shortfall, value)
    for f in facilities:
        if f['key'] in waivedKeys:
            facState.append({'key': f['key'], 'level': f['level'], 'upkeepMet': True,
                             'upkeepCost': 0, 'upkeepPaid': 0})
            continue
        cost = upkeepCostFloobits(f['level'], shareUnit)
        funded = int(f.get('upkeep_funded', 0))
        shortfall = max(0, cost - funded)
        # Rebuild cost of the level at risk. Level 0 cannot decay further, and a bill
        # already covered by direct fan funding costs the pot nothing.
        value = upgradeCostFloobits(max(0, f['level'] - 1), shareUnit) if f['level'] > 0 else 0
        candidates.append((f['key'], f['level'], cost, funded, shortfall, value))

    # Best affordable subset by preserved value; ties broken toward the higher level.
    bestKeys, bestValue, bestLevel = set(), -1, -1
    for mask in range(1 << len(candidates)):
        spend = 0
        value = 0
        levelSum = 0
        keys = set()
        for i, (key, level, cost, funded, shortfall, val) in enumerate(candidates):
            if not (mask >> i) & 1:
                continue
            spend += shortfall
            if spend > pot:
                break
            value += val
            levelSum += level
            keys.add(key)
        else:
            if (value, levelSum) > (bestValue, bestLevel):
                bestKeys, bestValue, bestLevel = keys, value, levelSum

    for key, level, cost, funded, shortfall, value in candidates:
        if key in bestKeys:
            pot -= shortfall
            funded += shortfall
        met = funded >= cost
        facState.append({'key': key, 'level': level, 'upkeepMet': met,
                         'upkeepCost': cost, 'upkeepPaid': funded})
        if not met:
            log.append(f"upkeep short on {key} (Lv{level}): {funded}/{cost}")

    # 2. DECAY — anything whose upkeep went unpaid drops a level.
    newLevels = {}
    for f in facState:
        lvl = f['level']
        if not f['upkeepMet'] and lvl > 0:
            lvl = max(0, lvl - FACILITY_DECAY_LEVELS)
            log.append(f"DECAY {f['key']}: Lv{f['level']}→Lv{lvl}")
        newLevels[f['key']] = lvl

    # 3. PROJECTS IN RANKED ORDER, ONE LEVEL PER FACILITY.
    # Every project is visited even once the pot is empty, because one fans already
    # funded in full needs nothing from it and still builds.
    projByKey = {p['facility_key']: p for p in projects}
    projState = []
    for key in (order or fallbackOrder(newLevels)):
        p = projByKey.get(key)
        if p is None or key not in newLevels:
            continue
        lvl = newLevels[key]
        funded = int(p.get('funded', 0))
        target, costShares = p['target_level'], p['cost_shares']
        if lvl >= FACILITY_MAX_LEVEL:
            projState.append({'id': p['id'], 'facility_key': key, 'funded': funded, 'built': False,
                              'target_level': target, 'cost_shares': costShares})
            continue
        # A facility that decayed rebuilds the level it lost rather than the one above it.
        if target != lvl + 1:
            target, costShares = lvl + 1, FACILITY_UPGRADE_COST_SHARES[lvl + 1]
        targetF = projectCostFloobits(costShares, shareUnit)
        if funded > targetF:
            pot += funded - targetF       # a retarget made it cheaper: the excess goes back
            funded = targetF
        built = False
        if key not in blockedKeys:
            pay = min(max(0, targetF - funded), pot)
            funded += pay
            pot -= pay
            built = funded >= targetF
            if built:
                newLevels[key] = target
                log.append(f"BUILT {key}→Lv{target}")
        projState.append({'id': p['id'], 'facility_key': key, 'funded': funded, 'built': built,
                          'target_level': target, 'cost_shares': costShares})

    facByKey = {f['key']: f for f in facState}
    outFac = [{'key': k, 'level': newLevels[k],
               'upkeepMet': facByKey.get(k, {}).get('upkeepMet', True),
               'upkeepPaid': facByKey.get(k, {}).get('upkeepPaid', 0),
               'upkeepCost': facByKey.get(k, {}).get('upkeepCost', 0)}
              for k in newLevels]
    return {'facilities': outFac, 'projects': projState, 'payrollPaid': payrollPaid,
            'payrollShort': payrollShort, 'leftover': max(0, pot), 'log': log}


# ─── DB-bound helpers (live use) ─────────────────────────────────────────────

def computeShareUnit(session, lastSeason: int, numTeams: int = None) -> float:
    """1 share = (total Floobits DISTRIBUTED to users last season) / numTeams.
    Distributed = sum of POSITIVE currency grants (the faucet); excludes spends.

    ⚠️ NEVER RETURNS ZERO. It used to, whenever there was no previous season, and the
    docstring called the result "inert" — but a zero share unit does not disable the
    facility economy, it makes it FREE. Season 1 showed 0F upkeep and 0F to build, and
    every team could max every facility for nothing. `FACILITY_SHARE_UNIT_FLOOR` is the
    floor a league runs on until it has a season of its own to price against.

    ⚠️ The team count is COUNTED, not assumed. It defaulted to 24 and no caller ever
    passed it, so after the league grew to 32 every share was 33% too large and every
    facility 33% too expensive.

    ⚠️ EACH USER'S CONTRIBUTION IS CAPPED BEFORE SUMMING, because this is a MEAN and a
    mean is exactly what one outlier breaks. Measured on the season-1 production database:
    ONE user earned 79,237F of a 212,614F faucet — 37% of the league's entire season — and
    89% of that was a single week (1,453,601 FP in week 27, a Criticality week where Pyre's
    Equation and Amplify stacked). That one week raised the price of every facility for all
    32 teams by 50%: a full level-5 build went 7,195F -> 10,764F and a season of level-5
    upkeep 1,777F -> 2,658F. Nobody else got any richer.

    The cap is what the estimator needs to survive that. A windfall is real income for the
    user who earned it, but it does not give the other 31 teams a single extra Floobit to
    spend, and the share unit exists to express what a typical team can afford. Measured
    over the same data, one user moves the raw total by +59.4% and the capped sum by
    +10.2%. `FACILITY_SHARE_CAP_PERCENTILE` (95) clips roughly the top user or two while
    still SUMMING everyone's real contribution, so the unit still tracks genuine league-wide
    growth — unlike a median, which discards the whole upper half of the distribution.

    ⚠️ Do not "fix" this by dropping the single largest earner: it is arbitrary, and it
    fails the moment two users spike in the same season.

    ⚠️ This is the second line of defence, not the first. `constants.weeklyFpFloobits` has a
    knee past which each doubling of FP pays far less; that alone would have turned this
    grant from 70,486F into 7,288F and left the faucet within 5% of clean. The cap is what
    catches a windfall the curve still lets through.
    """
    from sqlalchemy import text
    if numTeams is None:
        try:
            numTeams = session.execute(text("SELECT COUNT(*) FROM teams")).scalar() or 0
        except Exception:
            numTeams = 0
    numTeams = max(1, int(numTeams or 0))

    total = 0
    if lastSeason is not None and lastSeason >= 1:
        try:
            perUser = [float(r[0]) for r in session.execute(text(
                "SELECT COALESCE(SUM(amount), 0) FROM currency_transactions "
                "WHERE season = :s AND amount > 0 GROUP BY user_id"), {'s': lastSeason})
                if r[0]]
            total = _cappedFaucetTotal(perUser)
        except Exception as e:
            logger.warning(f"computeShareUnit failed: {e}")
            total = 0
    return max(FACILITY_SHARE_UNIT_FLOOR, float(total) / numTeams)


def _cappedFaucetTotal(perUser: list) -> float:
    """Sum per-user season earnings with each user clipped to the Pth percentile.

    Small leagues are left alone: below `FACILITY_SHARE_CAP_MIN_USERS` a percentile is
    computed from too few points to mean anything, and clipping there would simply lower
    the unit rather than de-skew it.
    """
    n = len(perUser)
    if n < FACILITY_SHARE_CAP_MIN_USERS:
        return float(sum(perUser))
    ordered = sorted(perUser)
    k = (n - 1) * (FACILITY_SHARE_CAP_PERCENTILE / 100.0)
    lo, hi = int(k), min(int(k) + 1, n - 1)
    capValue = ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)
    return float(sum(min(v, capValue) for v in perUser))


def getTreasury(session, teamId: int) -> int:
    from database.models import TeamTreasury
    row = session.query(TeamTreasury).filter_by(team_id=teamId).first()
    return int(row.balance) if row else 0


def canPayCutFee(teamId, fee: int) -> bool:
    """Whether `chargeCutFee` would succeed, charging nothing."""
    if fee <= 0 or teamId is None:
        return True
    from database.connection import get_session
    session = get_session()
    try:
        return getTreasury(session, teamId) >= fee
    except Exception:
        return False
    finally:
        session.close()


def chargeCutFee(teamId, fee: int) -> bool:
    """Debit a team's Treasury for a cut (`frontOfficeBrain.cutFeeFor`). False, with
    nothing charged, when it cannot cover it: ⚠️ the fee never goes into debt, because a
    broke team with a debt line has unlimited roster churn, the opposite of what the fee
    is for. One implementation for every cut path (prospect cuts, trades, the free agency
    market's releases, the FA draft's upgrade cut)."""
    if fee <= 0 or teamId is None:
        return True
    from database.connection import get_session
    session = get_session()
    try:
        balance = getTreasury(session, teamId)
        if balance < fee:
            return False
        setTreasury(session, teamId, balance - fee)
        session.commit()
        return True
    except Exception as e:
        logger.warning(f"Could not charge a cut fee to team {teamId}: {e}")
        try:
            session.rollback()
        except Exception:
            pass
        return False
    finally:
        session.close()


def setTreasury(session, teamId: int, balance: int) -> None:
    from database.models import TeamTreasury
    bal = max(0, int(balance))
    row = session.query(TeamTreasury).filter_by(team_id=teamId).first()
    if row:
        row.balance = bal
    else:
        session.add(TeamTreasury(team_id=teamId, balance=bal))


def addTreasury(session, teamId: int, amount: int) -> None:
    """Credit (or debit, if negative) a team's Treasury. Floored at 0."""
    setTreasury(session, teamId, getTreasury(session, teamId) + int(amount))


def prepareSeasonStart(session, teamIds: list, carriedByTeam: dict, baseline: int) -> None:
    """Season-start facility bookkeeping: reset every facility's upkeep_funded
    to 0 (new season's direct-funding tally) and top up Treasuries.

    First activation (no TeamTreasury row yet) seeds the Treasury from the 50%
    carry (carriedByTeam) — the contributions that bought the grandfathered
    facilities are NOT re-credited (no double-dip). Every season then adds the
    league baseline so even a fanless team can hold a minimal facility set.
    """
    from database.models import TeamFacility, TeamTreasury
    session.query(TeamFacility).update({TeamFacility.upkeep_funded: 0})
    for tid in teamIds:
        row = session.query(TeamTreasury).filter_by(team_id=tid).first()
        if row is None:
            session.add(TeamTreasury(team_id=tid, balance=max(0, int(carriedByTeam.get(tid, 0)) + baseline)))
        else:
            row.balance = max(0, int(row.balance) + baseline)


def _builtKeys(session, teamId: int, season: int, builtBy) -> set:
    """Facility keys this team built in `season` by the given builder(s)."""
    from database.models import FacilityProject
    from sqlalchemy import or_
    q = session.query(FacilityProject.facility_key).filter_by(
        team_id=teamId, status='built', built_season=season)
    if 'fans' in builtBy:
        q = q.filter(or_(FacilityProject.built_by.in_(builtBy), FacilityProject.built_by.is_(None)))
    else:
        q = q.filter(FacilityProject.built_by.in_(builtBy))
    return {r[0] for r in q.all()}


def fanBuiltThisYear(session, teamId: int, season: int) -> set:
    """Facilities fans built mid-season `season`. The payment run that follows skips
    their upgrade (one per year) and waives their upkeep (under construction)."""
    return _builtKeys(session, teamId, season, ('fans',))


PAYMENT_RUN_KEY = 'facility_payment_due'


def paymentRunDone(session, season: int) -> bool:
    """Whether this season's offseason payment run has already happened."""
    from database.models import AppSetting
    row = session.query(AppSetting).filter_by(key=PAYMENT_RUN_KEY).first()
    return bool(row and row.value == f"done:{season}")


def midSeasonBlocked(session, teamId: int, facilityKey: str, season: int) -> bool:
    """Whether fans may NOT build `facilityKey` now, during season `season` or its
    offseason: the payment run upgraded it last offseason (which runs under season - 1),
    fans already built it this season, or this season's payment run has happened.

    ⚠️ AFTER THE RUN, EVERY FAN BUILD WAITS FOR SEASON START. A build then would be
    stamped with this season's number, which the NEXT run and next season's builds
    would not see, so a facility could take two upgrades between one run and the next.
    `buildPendingProjects` builds it at season start instead.
    """
    return (facilityKey in _builtKeys(session, teamId, season - 1, ('run',))
            or facilityKey in _builtKeys(session, teamId, season, ('fans',))
            or paymentRunDone(session, season))


def ensureOpenProjects(session, teamId: int, levels: dict, season: int) -> None:
    """Every facility below the top level always has its next level open for funding
    (ranked ballots replace the vote that used to open one project a season). A project
    whose facility moved under it (a decay) is retargeted to the level above where the
    facility actually is; its funding carries over."""
    from database.models import FacilityProject
    openRows = session.query(FacilityProject).filter_by(team_id=teamId, status='open').all()
    byKey = {}
    for p in openRows:
        if p.facility_key in byKey:
            # Duplicates cannot be created here; fold any legacy one into the first.
            byKey[p.facility_key].funded = (byKey[p.facility_key].funded or 0) + (p.funded or 0)
            session.delete(p)
        else:
            byKey[p.facility_key] = p
    for key in FACILITY_CATALOG:
        lvl = (levels or {}).get(key, 0)
        p = byKey.get(key)
        if lvl >= FACILITY_MAX_LEVEL:
            if p is not None:
                if p.funded:
                    addTreasury(session, teamId, p.funded)
                session.delete(p)
            continue
        target = lvl + 1
        if p is None:
            session.add(FacilityProject(
                team_id=teamId, facility_key=key, kind=('new' if lvl == 0 else 'upgrade'),
                target_level=target, cost_shares=FACILITY_UPGRADE_COST_SHARES[target],
                funded=0, opened_season=season, status='open'))
        elif p.target_level != target:
            p.target_level = target
            p.kind = 'new' if lvl == 0 else 'upgrade'
            p.cost_shares = FACILITY_UPGRADE_COST_SHARES[target]
    session.flush()


def teamBallots(session, teamId: int) -> list:
    """The ranked ballots of the team's CURRENT fans (a fan who switched teams no
    longer counts here), each a list of facility keys."""
    import json
    from database.models import FacilityRanking, User
    rows = (session.query(FacilityRanking.ranking_json)
            .join(User, User.id == FacilityRanking.user_id)
            .filter(FacilityRanking.team_id == teamId, User.favorite_team_id == teamId).all())
    out = []
    for (raw,) in rows:
        try:
            ballot = json.loads(raw or '[]')
        except Exception:
            continue
        if isinstance(ballot, list):
            out.append(ballot)
    return out


def getRanking(session, teamId: int, userId: int):
    """The fan's saved ranking for this team, or None."""
    import json
    from database.models import FacilityRanking
    row = session.query(FacilityRanking).filter_by(team_id=teamId, user_id=userId).first()
    if not row:
        return None
    try:
        ballot = json.loads(row.ranking_json or '[]')
    except Exception:
        return None
    return ballot if isinstance(ballot, list) else None


def setRanking(session, teamId: int, userId: int, ranking: list) -> list:
    """Save a fan's ranking. It must be an ordering of every facility. It persists
    across seasons until the fan changes it."""
    import json
    import datetime
    from database.models import FacilityRanking
    if (not isinstance(ranking, list) or len(ranking) != len(FACILITY_CATALOG)
            or set(ranking) != set(FACILITY_CATALOG)):
        raise ValueError("Ranking must list every facility exactly once")
    row = session.query(FacilityRanking).filter_by(team_id=teamId, user_id=userId).first()
    now = datetime.datetime.utcnow()
    if row:
        row.ranking_json = json.dumps(ranking)
        row.updated_at = now
    else:
        session.add(FacilityRanking(team_id=teamId, user_id=userId,
                                    ranking_json=json.dumps(ranking), updated_at=now))
        session.flush()
    return ranking


def teamOrder(session, teamId: int, levels: dict) -> list:
    return combinedOrder(levels, teamBallots(session, teamId))


def parseTreasuryInjection(spec: str) -> dict:
    """Parse FLOOS_TREASURY_INJECT: comma-separated `even=N`, `odd=N`, `all=N` or
    `<teamId>=N`, applied in that order of specificity (a team id beats even/odd beats
    all). Returns {'all': n, 'even': n, 'odd': n, 'ids': {teamId: n}}."""
    out = {'all': 0, 'even': None, 'odd': None, 'ids': {}}
    for tok in (spec or '').split(','):
        tok = tok.strip()
        if not tok or '=' not in tok:
            continue
        k, v = tok.split('=', 1)
        k, v = k.strip().lower(), int(float(v))
        if k in ('all', 'even', 'odd'):
            out[k] = v
        else:
            out['ids'][int(k)] = v
    return out


def treasuryInjectionFor(teamId: int, parsed: dict) -> int:
    if teamId in parsed['ids']:
        return parsed['ids'][teamId]
    side = 'even' if teamId % 2 == 0 else 'odd'
    if parsed[side] is not None:
        return parsed[side]
    return parsed['all']


def applyTreasuryInjection(session, teamObjs: list) -> dict:
    """Calibration switch for `treasury_harness.py` (FLOOS_TREASURY_INJECT): credit each
    team's Treasury with a fixed amount right before the payment run, so the harness can
    give half the league more money and measure what it buys. Off unless set. Returns
    {teamId: amount added}."""
    import os
    spec = os.environ.get('FLOOS_TREASURY_INJECT')
    if not spec:
        return {}
    parsed = parseTreasuryInjection(spec)
    added = {}
    for team in teamObjs:
        amt = treasuryInjectionFor(team.id, parsed)
        if amt:
            addTreasury(session, team.id, amt)
            added[team.id] = amt
    return added


def applyPaymentRun(session, teamObjs: list, season: int, shareUnit: float) -> list:
    """Run the offseason payment run for every team and PERSIST the result (facility
    levels, project funding/builds, Treasury leftover, in-memory team.facilities).
    `season` is the season whose offseason this is. Returns per-team logs."""
    from database.models import TeamFacility, FacilityProject
    logs = []
    for team in teamObjs:
        facRows = session.query(TeamFacility).filter_by(team_id=team.id).all()
        if not facRows:
            # No facilities to keep up, but the players still get paid.
            from managers import payroll
            owed = payroll.seasonPayroll(team)
            if owed:
                bal = getTreasury(session, team.id)
                setTreasury(session, team.id, bal - min(owed, bal))
                logs.append((getattr(team, 'name', team.id), [f"payroll {min(owed, bal)}/{owed}"]))
            continue
        levels = {f.facility_key: f.level for f in facRows}
        ensureOpenProjects(session, team.id, levels, season)
        projRows = session.query(FacilityProject).filter_by(team_id=team.id, status='open').all()
        fanBuilt = fanBuiltThisYear(session, team.id, season)
        treasury = getTreasury(session, team.id)
        facilities = [{'key': f.facility_key, 'level': f.level, 'upkeep_funded': f.upkeep_funded}
                      for f in facRows]
        projects = [{'id': p.id, 'facility_key': p.facility_key, 'target_level': p.target_level,
                     'cost_shares': p.cost_shares, 'funded': p.funded} for p in projRows]
        from managers import payroll
        res = resolvePaymentRun(facilities, projects, treasury, shareUnit,
                                order=teamOrder(session, team.id, levels),
                                waivedKeys=fanBuilt, blockedKeys=fanBuilt,
                                payroll=payroll.seasonPayroll(team))
        levelByKey = {f['key']: f['level'] for f in res['facilities']}
        paidByKey = {f['key']: f.get('upkeepPaid', 0) for f in res['facilities']}
        for f in facRows:
            f.level = levelByKey.get(f.facility_key, f.level)
            # Reflect the treasury-paid upkeep on the row so the facility reads as
            # funded through the rest of the offseason (the season-start reset zeroes it).
            f.upkeep_funded = paidByKey.get(f.facility_key, f.upkeep_funded)
        projById = {p['id']: p for p in res['projects']}
        for p in projRows:
            r = projById.get(p.id)
            if r is None:
                continue
            p.funded = r['funded']
            p.target_level = r['target_level']
            p.cost_shares = r['cost_shares']
            if r['built']:
                p.status = 'built'
                p.built_season = season
                p.built_by = 'run'
        setTreasury(session, team.id, res['leftover'])
        session.flush()
        levels = {f.facility_key: f.level for f in facRows}
        ensureOpenProjects(session, team.id, levels, season)   # the next level up opens
        team.facilities = levels  # refresh in-memory
        if res['log']:
            logs.append((getattr(team, 'name', team.id), res['log']))
    return logs


def buildProjectNow(session, teamId: int, project, teamObj=None, season: int = None,
                    builtBy: str = 'fans') -> int:
    """Apply a just-completed project IMMEDIATELY (mid-season): bump the facility
    to the target level, mark the project built, and refresh the in-memory
    team.facilities so the new perks take effect from the team's next game.
    The caller checks `midSeasonBlocked` first. A facility built this way counts as
    its one upgrade for the year: the next payment run skips it and waives its
    upkeep. Returns the new level."""
    from database.models import TeamFacility
    newLevel = project.target_level
    fac = session.query(TeamFacility).filter_by(
        team_id=teamId, facility_key=project.facility_key).first()
    if fac:
        fac.level = newLevel
    project.status = 'built'
    project.built_by = builtBy
    if season is not None:
        project.built_season = season
    if teamObj is not None:
        facilities = dict(teamObj.facilities or {})
        facilities[project.facility_key] = newLevel
        teamObj.facilities = facilities  # reassign so the effects engine reads the new level
    if fac is not None:
        session.flush()
        ensureOpenProjects(session, teamId,
                           {f.facility_key: f.level for f in
                            session.query(TeamFacility).filter_by(team_id=teamId).all()},
                           season if season is not None else project.opened_season)
    return newLevel


def buildPendingProjects(session, teamObjs: list, season: int, shareUnit: float) -> list:
    """At season start, build any project fans funded in full while its facility was
    blocked (it had already had its upgrade that year). Returns [(team, key, level)]."""
    from database.models import FacilityProject
    built = []
    for team in teamObjs:
        for p in session.query(FacilityProject).filter_by(team_id=team.id, status='open').all():
            if (p.funded or 0) < projectCostFloobits(p.cost_shares, shareUnit):
                continue
            if midSeasonBlocked(session, team.id, p.facility_key, season):
                continue
            lvl = buildProjectNow(session, team.id, p, team, season)
            built.append((getattr(team, 'name', team.id), p.facility_key, lvl))
    return built


def projectBuildTiming(session, teamId: int, facilityKey: str, season: int) -> str:
    """When a fully funded project for this facility would build, for the UI:
    'now' (builds the moment it is fully funded), 'payment_run' (built by the run
    last offseason, so it waits for the next run), or 'next_season' (fans already
    built it this season, or this season's run has happened)."""
    if (facilityKey in _builtKeys(session, teamId, season, ('fans',))
            or paymentRunDone(session, season)):
        return 'next_season'
    if facilityKey in _builtKeys(session, teamId, season - 1, ('run',)):
        return 'payment_run'
    return 'now'

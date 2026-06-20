"""Facility economy engine (Markets→Facilities system, Phase 2).

Share-denominated costs, direct contributions, and the season-end waterfall
(upkeep first, then the oldest open project), plus offseason decay/construction.

The core resolver (`resolveSeasonEnd`) is a PURE function over plain dicts so it
can be exhaustively validated by the economy harness without a DB. The DB-bound
helpers below wrap it for live use. See docs/MARKETS_FACILITIES_PLAN.md §3/§5.
"""
from logging import getLogger
from constants import (FACILITY_CATALOG, FACILITY_MAX_LEVEL,
                       FACILITY_UPGRADE_COST_SHARES, FACILITY_UPKEEP_SHARES,
                       FACILITY_DECAY_LEVELS, APPEAL_LEVEL_WEIGHTS)

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
    """Appeal = weighted sum of facility levels (drives FA order, Phase 4).
    `facilities` = {facility_key: level}."""
    return sum((facilities or {}).get(k, 0) * APPEAL_LEVEL_WEIGHTS.get(k, 1.0)
               for k in FACILITY_CATALOG)


# ─── The pure season-end resolver ────────────────────────────────────────────

def resolveSeasonEnd(facilities: list, projects: list, treasury: int,
                     shareUnit: float, season: int) -> dict:
    """Resolve one season-end for a single team. PURE — no DB, no mutation of
    inputs; returns the new state + a log.

    facilities: [{'key','level','upkeep_funded'}]  (upkeep_funded = direct funding so far this season)
    projects:   [{'id','facility_key','target_level','cost_shares','funded','opened_season'}]  (OPEN only)
    treasury:   Floobits available at season end (carried + baseline + deposits), BEFORE the waterfall.
    Returns {'facilities':[{key,level,upkeepMet}], 'projects':[{id,funded,built}],
             'leftover':int, 'log':[...]}.
    """
    pot = int(treasury)
    log = []

    # 1. UPKEEP WATERFALL — cover each facility's upkeep shortfall from the pot.
    #    Highest-level facilities are protected first (most investment at stake);
    #    a fan can pre-protect any specific facility via direct upkeep funding.
    facState = []
    for f in sorted(facilities, key=lambda x: -x['level']):
        cost = upkeepCostFloobits(f['level'], shareUnit)
        funded = int(f.get('upkeep_funded', 0))
        shortfall = max(0, cost - funded)
        pay = min(shortfall, pot)
        funded += pay
        pot -= pay
        met = funded >= cost
        facState.append({'key': f['key'], 'level': f['level'], 'upkeepMet': met,
                         'upkeepCost': cost, 'upkeepPaid': funded})
        if not met:
            log.append(f"upkeep short on {f['key']} (Lv{f['level']}): {funded}/{cost}")

    # 2. REMAINING POT → OLDEST OPEN PROJECT(S) (FIFO by opened_season, then id).
    projState = []
    for p in sorted(projects, key=lambda x: (x['opened_season'], x['id'])):
        target = projectCostFloobits(p['cost_shares'], shareUnit)
        funded = int(p.get('funded', 0))
        need = max(0, target - funded)
        pay = min(need, pot) if pot > 0 else 0
        funded += pay
        pot -= pay
        projState.append({'id': p['id'], 'facility_key': p['facility_key'],
                          'target_level': p['target_level'], 'funded': funded,
                          'target': target, 'built': funded >= target})

    # 3. OFFSEASON RESOLUTION — decay then construction (construction wins ties).
    newLevels = {}
    for f in facState:
        lvl = f['level']
        if not f['upkeepMet'] and lvl > 0:
            lvl = max(0, lvl - FACILITY_DECAY_LEVELS)
            log.append(f"DECAY {f['key']}: Lv{f['level']}→Lv{lvl}")
        newLevels[f['key']] = lvl
    builtProjects = []
    for p in projState:
        if p['built']:
            newLevels[p['facility_key']] = p['target_level']
            builtProjects.append(p['id'])
            log.append(f"BUILT {p['facility_key']}→Lv{p['target_level']}")

    outFac = [{'key': k, 'level': newLevels[k], 'upkeepMet': next(f['upkeepMet'] for f in facState if f['key'] == k)}
              for k in newLevels]
    outProj = [{'id': p['id'], 'funded': p['funded'], 'built': p['built']} for p in projState]
    return {'facilities': outFac, 'projects': outProj, 'leftover': max(0, pot), 'log': log}


# ─── DB-bound helpers (live use) ─────────────────────────────────────────────

def computeShareUnit(session, lastSeason: int, numTeams: int = 24) -> float:
    """1 share = (total Floobits DISTRIBUTED to users last season) / numTeams.
    Distributed = sum of POSITIVE currency grants (the faucet); excludes spends.
    Returns 0.0 if no data (e.g. fresh league) — costs then read as 0 (inert)."""
    from sqlalchemy import text
    if lastSeason is None or lastSeason < 1:
        return 0.0
    try:
        total = session.execute(text(
            "SELECT COALESCE(SUM(amount), 0) FROM currency_transactions "
            "WHERE season = :s AND amount > 0"), {'s': lastSeason}).scalar() or 0
        return float(total) / max(1, numTeams)
    except Exception as e:
        logger.warning(f"computeShareUnit failed: {e}")
        return 0.0


def getTreasury(session, teamId: int) -> int:
    from database.models import TeamTreasury
    row = session.query(TeamTreasury).filter_by(team_id=teamId).first()
    return int(row.balance) if row else 0


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


def applySeasonEnd(session, teamObjs: list, season: int, shareUnit: float) -> list:
    """Run the season-end waterfall + offseason construction for every team and
    PERSIST the result (facility levels, project funding/builds, Treasury
    leftover, in-memory team.facilities). Treasury is assumed already credited
    with this season's deposit/contributions. Returns per-team logs.
    """
    from database.models import TeamFacility, FacilityProject
    logs = []
    for team in teamObjs:
        facRows = session.query(TeamFacility).filter_by(team_id=team.id).all()
        projRows = session.query(FacilityProject).filter_by(team_id=team.id, status='open').all()
        if not facRows:
            continue
        treasury = getTreasury(session, team.id)
        facilities = [{'key': f.facility_key, 'level': f.level, 'upkeep_funded': f.upkeep_funded}
                      for f in facRows]
        projects = [{'id': p.id, 'facility_key': p.facility_key, 'target_level': p.target_level,
                     'cost_shares': p.cost_shares, 'funded': p.funded, 'opened_season': p.opened_season}
                    for p in projRows]
        res = resolveSeasonEnd(facilities, projects, treasury, shareUnit, season)
        levelByKey = {f['key']: f['level'] for f in res['facilities']}
        for f in facRows:
            f.level = levelByKey.get(f.facility_key, f.level)
        builtIds = {p['id'] for p in res['projects'] if p['built']}
        fundedById = {p['id']: p['funded'] for p in res['projects']}
        for p in projRows:
            p.funded = fundedById.get(p.id, p.funded)
            if p.id in builtIds:
                p.status = 'built'
                p.built_season = season
        setTreasury(session, team.id, res['leftover'])
        team.facilities = {f.facility_key: f.level for f in facRows}  # refresh in-memory
        if res['log']:
            logs.append((getattr(team, 'name', team.id), res['log']))
    return logs


def openProject(session, teamId: int, facilityKey: str, currentLevel: int, season: int):
    """Open a build/upgrade project for the next level of a facility. No-op if
    already maxed or an open project for this facility exists. Returns the row or None."""
    from database.models import FacilityProject
    target = currentLevel + 1
    if facilityKey not in FACILITY_CATALOG or target > FACILITY_MAX_LEVEL:
        return None
    existing = session.query(FacilityProject).filter_by(
        team_id=teamId, facility_key=facilityKey, status='open').first()
    if existing:
        return existing
    proj = FacilityProject(
        team_id=teamId, facility_key=facilityKey,
        kind=('new' if currentLevel == 0 else 'upgrade'),
        target_level=target, cost_shares=FACILITY_UPGRADE_COST_SHARES[target],
        funded=0, opened_season=season, status='open')
    session.add(proj)
    return proj

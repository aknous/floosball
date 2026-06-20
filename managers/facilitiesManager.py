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

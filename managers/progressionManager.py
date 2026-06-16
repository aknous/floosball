"""progressionManager — turns achievement data into player-facing progression.

A pure READ-LAYER over UserAchievement (no new tables, no XP-event plumbing):
  • Per-activity RANK   = the primary tiered family's highest completed tier THIS
                          season, shown as the achievement name verbatim ("Oracle II").
                          Per-season (the families are per_season), so it resets.
  • Permanent OVERALL LEVEL = lifetime achievement "points" (every completed
                          achievement across every season, weighted by category/tier)
                          mapped to a level via a deep, never-resetting curve.
  • TROPHY CASE         = capstone (top-tier) completions across all seasons + secret
                          unlocks. Per-season achievement rows aren't wiped, so a
                          capstone earned in S12 persists forever.

The whole module is derived state — it doesn't write anything.
"""
from typing import Optional
from sqlalchemy.orm import Session

from database.models import Achievement, UserAchievement


# Which tiered family is THE rank for each activity (each activity has several
# families; only the primary one surfaces as a rank). Tier keys low→high; the last
# is the capstone whose completion becomes a permanent trophy.
RANK_FAMILIES = [
    {"activity": "Prognostication",
     "tierKeys": ["oracle_i", "oracle_ii", "oracle_iii", "oracle_iv"]},
    {"activity": "Fantasy",
     "tierKeys": ["dynamo_i", "dynamo_ii", "dynamo_iii", "dynamo_iv"]},
    # Cards / GM / Supporter primary families added here later.
]

# Overall level: lifetime achievement points → level. Harder/deeper achievements
# weigh more so the level reflects real accomplishment, not raw count. Tunable.
_GUIDANCE_TIER_POINTS = {1: 3, 2: 5, 3: 8, 4: 12}
_CATEGORY_BASE_POINTS = {"onboarding": 2, "guidance": 5, "secret": 15}
_OVERALL_LEVEL_CAP = 60
# points = SCALE × level^EXP (deep, permanent curve). Calibrated against real prod
# achievement data (2026-06): a ~9-season heavy user (~2k lifetime pts) lands ~Veteran
# (Lv28), a new user Rookie, and Legend (Lv50, ~4.8k pts) is a genuine long-haul.
_OVERALL_SCALE = 10.0
_OVERALL_EXP = 1.6
# Title bands over the level range (minLevel, title), descending.
_OVERALL_TITLE_BANDS = [
    (50, "Legend"), (40, "Stalwart"), (30, "Sharp"),
    (20, "Veteran"), (10, "Regular"), (1, "Rookie"),
]
_ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8}


def _tierFromKey(key: str) -> Optional[int]:
    """oracle_iv → 4; returns None when the key has no roman-numeral tier suffix."""
    if not key or "_" not in key:
        return None
    return _ROMAN.get(key.rsplit("_", 1)[-1])


def achievementPoints(ach: Achievement) -> int:
    """Point weight of a single achievement for the overall level."""
    tier = _tierFromKey(ach.key)
    if tier is not None and ach.category == "guidance":
        return _GUIDANCE_TIER_POINTS.get(tier, 3 + tier)
    return _CATEGORY_BASE_POINTS.get(ach.category, 3)


def pointsForLevel(level: int) -> int:
    return int(round(_OVERALL_SCALE * (max(1, level) ** _OVERALL_EXP)))


def overallLevelFromPoints(points: int) -> int:
    if points <= 0:
        return 1
    lvl = int((points / _OVERALL_SCALE) ** (1.0 / _OVERALL_EXP))
    return max(1, min(_OVERALL_LEVEL_CAP, lvl))


def overallTitle(level: int) -> str:
    for minLevel, title in _OVERALL_TITLE_BANDS:
        if level >= minLevel:
            return title
    return "Rookie"


def _completedRows(session: Session, userId: int):
    """All of a user's COMPLETED achievements, joined to the template.
    Returns list of (UserAchievement, Achievement)."""
    return (
        session.query(UserAchievement, Achievement)
        .join(Achievement, Achievement.id == UserAchievement.achievement_id)
        .filter(UserAchievement.user_id == userId,
                UserAchievement.completed_at.isnot(None))
        .all()
    )


def getOverallLevel(session: Session, userId: int) -> dict:
    """Permanent career level from lifetime achievement points."""
    points = sum(achievementPoints(ach) for _ua, ach in _completedRows(session, userId))
    level = overallLevelFromPoints(points)
    floor = pointsForLevel(level)
    nextLevel = min(_OVERALL_LEVEL_CAP, level + 1)
    ceil = pointsForLevel(nextLevel)
    return {
        "level": level,
        "title": overallTitle(level),
        "points": points,
        "pointsThisLevel": max(0, points - floor),
        "pointsToNext": max(0, ceil - points) if level < _OVERALL_LEVEL_CAP else 0,
        "isMax": level >= _OVERALL_LEVEL_CAP,
    }


def getActivityRanks(session: Session, userId: int, currentSeason: int) -> list:
    """Per-activity rank = highest completed tier of the primary family THIS season.
    Returns one entry per rank family (rankName None when unranked this season)."""
    # Map every rank-family tier key → its Achievement (for name) once.
    allTierKeys = [k for fam in RANK_FAMILIES for k in fam["tierKeys"]]
    achByKey = {a.key: a for a in
                session.query(Achievement).filter(Achievement.key.in_(allTierKeys)).all()}
    achIds = {a.id for a in achByKey.values()}
    # Completed-this-season set (per_season rows carry season == currentSeason).
    completedThisSeason = {
        ua.achievement_id for ua in session.query(UserAchievement).filter(
            UserAchievement.user_id == userId,
            UserAchievement.achievement_id.in_(achIds) if achIds else False,
            UserAchievement.season == currentSeason,
            UserAchievement.completed_at.isnot(None),
        ).all()
    } if achIds else set()

    out = []
    for fam in RANK_FAMILIES:
        rankName, tier, capstoneKey = None, 0, fam["tierKeys"][-1]
        for idx, key in enumerate(fam["tierKeys"], start=1):
            ach = achByKey.get(key)
            if ach and ach.id in completedThisSeason:
                rankName, tier = ach.name, idx  # keep climbing to the highest
        out.append({
            "activity": fam["activity"],
            "rankName": rankName,                 # "Oracle II" or None (unranked)
            "tier": tier,                          # 0 = unranked this season
            "maxTier": len(fam["tierKeys"]),
            "maxed": rankName == (achByKey.get(capstoneKey).name if achByKey.get(capstoneKey) else None),
        })
    return out


def getTrophyCase(session: Session, userId: int) -> list:
    """Permanent trophies: capstone (top-tier) completions across ALL seasons, plus
    secret unlocks. Each capstone earned in a season is its own durable trophy."""
    capstoneKeys = {fam["tierKeys"][-1] for fam in RANK_FAMILIES}
    trophies = []
    for ua, ach in _completedRows(session, userId):
        if ach.key in capstoneKeys:
            trophies.append({"type": "capstone", "name": ach.name,
                             "season": ua.season, "key": ach.key})
        elif ach.category == "secret":
            trophies.append({"type": "secret", "name": ach.name,
                             "season": ua.season, "key": ach.key})
    # Newest first; capstones before secrets within a season.
    trophies.sort(key=lambda t: (-(t["season"] or 0), 0 if t["type"] == "capstone" else 1))
    return trophies


def getProfile(session: Session, userId: int, currentSeason: int) -> dict:
    """Assemble the full profile payload (overall level + season ranks + trophies)."""
    return {
        "userId": userId,
        "overall": getOverallLevel(session, userId),
        "ranks": getActivityRanks(session, userId, currentSeason),
        "trophies": getTrophyCase(session, userId),
    }

"""Card Showcase — seasonal collection payout engine.

A user features up to SHOWCASE_SLOTS vaulted cards. The selection is scored into
a hidden numeric value that maps to a letter grade (F→S); the grade pays out flat
Floobits at season end, then the showcase clears (season-scoped rows).

The score is deliberately NEVER exposed to the client — same hidden-but-legible
philosophy as the anomaly Criticality status. The frontend gets the grade, the
estimated payout, the named sets currently boosting it ("Active"), and the sets
it's one or two cards away from ("Almost"). Curation reads as a hand of cards,
not a spreadsheet.

Scoring (all weights in constants.py, tune via /simcheck):
  per-card  = (EDITION × recency + Σ CLASSIFICATION) × (1 + (tier−1) × tierStep)
  recency   = max(FLOOR, 1 − STEP × seasonsOld)   # newer cards pay more
  total     = Σ per-card × (1 + min(Σ set bonuses, MAX_SET_BONUS))
  grade     = first threshold the total meets (high→low) → flat payout

SET_RULES is an extensible list: each rule is a detector that returns the number
of cards still needed (0 = the set is active). Add a rule = add an entry.
"""

from constants import (
    SHOWCASE_SLOTS,
    SHOWCASE_EDITION_POINTS,
    SHOWCASE_CLASSIFICATION_POINTS,
    SHOWCASE_RECENCY_FLOOR,
    SHOWCASE_RECENCY_STEP,
    SHOWCASE_TIER_BONUS_PER_LEVEL,
    SHOWCASE_MAX_SET_BONUS,
    SHOWCASE_GRADE_THRESHOLDS,
    SHOWCASE_GRADE_PAYOUT,
)


# ─── Per-card value ──────────────────────────────────────────────────────────

def _recency(seasonCreated: int, currentSeason: int) -> float:
    """Newer cards are worth more; floored so old cards still count."""
    seasonsOld = max(0, (currentSeason or 0) - (seasonCreated or 0))
    return max(SHOWCASE_RECENCY_FLOOR, 1.0 - SHOWCASE_RECENCY_STEP * seasonsOld)


def _classificationPoints(classification) -> int:
    if not classification:
        return 0
    return sum(pts for key, pts in SHOWCASE_CLASSIFICATION_POINTS.items()
               if key in classification)


def _cardPoints(card: dict, currentSeason: int) -> float:
    """card = {edition, classification, tier, seasonCreated}."""
    editionPts = SHOWCASE_EDITION_POINTS.get(card.get("edition"), 0)
    rec = _recency(card.get("seasonCreated", currentSeason), currentSeason)
    base = editionPts * rec + _classificationPoints(card.get("classification"))
    tier = card.get("tier", 1) or 1
    tierMult = 1.0 + (tier - 1) * SHOWCASE_TIER_BONUS_PER_LEVEL
    return base * tierMult


# ─── Set detectors (return cards still needed; 0 = active) ───────────────────

def _hasTag(card: dict, tag: str) -> bool:
    c = card.get("classification")
    return bool(c) and tag in c


def _distFullSpectrum(cards):
    byPlayer = {}
    for c in cards:
        byPlayer.setdefault(c.get("playerId"), set()).add(c.get("edition"))
    best = max((len(eds) for eds in byPlayer.values()), default=0)
    return max(0, 4 - best)


def _distOneClub(cards):
    counts = {}
    for c in cards:
        tid = c.get("teamId")
        if tid:
            counts[tid] = counts.get(tid, 0) + 1
    return max(0, 6 - max(counts.values(), default=0))


def _distChampionSquad(cards):
    counts = {}
    for c in cards:
        tid = c.get("teamId")
        if tid and _hasTag(c, "champion"):
            counts[tid] = counts.get(tid, 0) + 1
    return max(0, 6 - max(counts.values(), default=0))


def _distAllProLine(cards):
    n = sum(1 for c in cards if _hasTag(c, "all_pro"))
    return max(0, 5 - n)


def _distHallOfFame(cards):
    n = sum(1 for c in cards
            if _hasTag(c, "mvp") or _hasTag(c, "champion") or _hasTag(c, "all_pro"))
    return max(0, SHOWCASE_SLOTS - n)


def _distDiamondVault(cards):
    n = sum(1 for c in cards if c.get("edition") == "diamond")
    return max(0, SHOWCASE_SLOTS - n)


def _distRainbow(cards):
    eds = {c.get("edition") for c in cards}
    present = sum(1 for e in ("base", "holographic", "prismatic", "diamond") if e in eds)
    return max(0, 4 - present)


# key, name, bonus, detector, and singular/plural units for the "almost" hint
SET_RULES = [
    {"key": "full_spectrum",  "name": "Full Spectrum",  "bonus": 0.5, "fn": _distFullSpectrum,  "one": "edition of one player",        "many": "editions of one player"},
    {"key": "one_club",       "name": "One Club",       "bonus": 0.6, "fn": _distOneClub,       "one": "card from one team",           "many": "cards from one team"},
    {"key": "champion_squad", "name": "Champion Squad", "bonus": 0.8, "fn": _distChampionSquad, "one": "champion from one team",       "many": "champions from one team"},
    {"key": "all_pro_line",   "name": "All-Pro Line",   "bonus": 0.5, "fn": _distAllProLine,    "one": "All-Pro card",                 "many": "All-Pro cards"},
    {"key": "hall_of_fame",   "name": "Hall of Fame",   "bonus": 0.7, "fn": _distHallOfFame,    "one": "MVP/Champion/All-Pro card",    "many": "MVP/Champion/All-Pro cards"},
    {"key": "diamond_vault",  "name": "Diamond Vault",  "bonus": 1.0, "fn": _distDiamondVault,  "one": "Diamond",                      "many": "Diamonds"},
    {"key": "rainbow",        "name": "Rainbow",        "bonus": 0.3, "fn": _distRainbow,       "one": "edition",                      "many": "editions"},
]


# ─── Grade + evaluation ──────────────────────────────────────────────────────

def _grade(score: float) -> str:
    for grade, threshold in SHOWCASE_GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return "F"


def evaluate(cards, currentSeason: int) -> dict:
    """Score a showcase. `cards` = list of card-info dicts (≤ SHOWCASE_SLOTS).

    Returns grade, payout (the grade's flat Floobits), the active named sets, the
    'almost' sets (1–2 cards away), and the raw score (callers strip it from any
    client-facing payload)."""
    score = sum(_cardPoints(c, currentSeason) for c in cards)
    active, almost, totalBonus = [], [], 0.0
    for rule in SET_RULES:
        dist = rule["fn"](cards)
        if dist == 0 and cards:
            active.append({"key": rule["key"], "name": rule["name"]})
            totalBonus += rule["bonus"]
        elif cards and 1 <= dist <= 2:
            unit = rule["one"] if dist == 1 else rule["many"]
            almost.append({
                "key": rule["key"],
                "name": rule["name"],
                "need": dist,
                "hint": f"{dist} more {unit}",
            })
    totalBonus = min(totalBonus, SHOWCASE_MAX_SET_BONUS)
    finalScore = score * (1.0 + totalBonus)
    grade = _grade(finalScore)
    return {
        "grade": grade,
        "payout": SHOWCASE_GRADE_PAYOUT.get(grade, 0),
        "activeSets": active,
        "almostSets": almost,
        "score": round(finalScore, 1),  # internal only — strip before returning to client
    }


# ─── DB helpers ──────────────────────────────────────────────────────────────

def cardInfo(userCard) -> dict:
    """Extract the scoring-relevant fields from a UserCard + its template."""
    t = userCard.card_template
    return {
        "userCardId": userCard.id,
        "edition": t.edition,
        "classification": t.classification,
        "tier": getattr(userCard, "tier", 1) or 1,
        "seasonCreated": t.season_created,
        "playerId": t.player_id,
        "teamId": t.team_id,
    }


SHOWCASE_PAYOUT_TX = "showcase_payout"


def awardSeasonPayouts(session, season: int) -> dict:
    """Grade every user's featured showcase for the season and pay out Floobits.
    Idempotent: a per-season transaction guard prevents double payment. Does NOT
    commit — the caller owns the transaction. Returns a summary including per-user
    results so the caller can log / broadcast.
    """
    from database.models import CurrencyTransaction, ShowcaseSlot
    from database.repositories.card_repositories import CurrencyRepository

    already = session.query(CurrencyTransaction.id).filter(
        CurrencyTransaction.transaction_type == SHOWCASE_PAYOUT_TX,
        CurrencyTransaction.season == season,
    ).first()
    if already:
        return {"paid": 0, "alreadyAwarded": True, "results": []}

    userIds = [r[0] for r in session.query(ShowcaseSlot.user_id).filter(
        ShowcaseSlot.season == season).distinct().all()]
    cur = CurrencyRepository(session)
    results = []
    for userId in userIds:
        infos = loadShowcaseCardInfos(session, userId, season)
        if not infos:
            continue
        ev = evaluate(infos, season)
        results.append({"userId": userId, "grade": ev["grade"], "payout": ev["payout"]})
        if ev["payout"] > 0:
            cur.addFunds(userId, ev["payout"], SHOWCASE_PAYOUT_TX,
                         f"Showcase payout (grade {ev['grade']})", season)
    return {"paid": sum(1 for r in results if r["payout"] > 0), "alreadyAwarded": False, "results": results}


def loadShowcaseCardInfos(session, userId: int, season: int) -> list:
    """All card-infos a user has featured this season, ordered by slot."""
    from database.models import ShowcaseSlot, UserCard
    rows = (
        session.query(ShowcaseSlot)
        .filter(ShowcaseSlot.user_id == userId, ShowcaseSlot.season == season)
        .order_by(ShowcaseSlot.slot_number)
        .all()
    )
    infos = []
    for row in rows:
        uc = session.get(UserCard, row.user_card_id)
        if uc and uc.card_template:
            infos.append(cardInfo(uc))
    return infos

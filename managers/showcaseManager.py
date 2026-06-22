"""Card Showcase — collection dividend engine.

A user features up to SHOWCASE_SLOTS vaulted cards. The selection is scored into
a numeric value that maps to a letter grade (F→S) AND drives a WEEKLY DIVIDEND:
each regular-season week the live showcase is re-graded and pays out Floobits
scaled by its score, then the showcase clears at season end (season-scoped rows).

Scoring was once hidden ("a hand of cards, not a spreadsheet"), but the dividend
is now TRANSPARENT — users can see exactly why a showcase pays what it does. The
frontend gets the grade, the weekly dividend, a per-card breakdown (each card's
multipliers + its Floobit share of the dividend), the set-bonus multiplier, and
the named Active / Almost sets.

Scoring (all weights in constants.py, tune via /simcheck):
  per-card  = (EDITION + Σ CLASSIFICATION) × recency × (1 + (tier−1) × tierStep)
  recency   = max(FLOOR, 1 − STEP × seasonsOld)   # newer cards pay more (prestige decays too)
  setBonus  = Σ baseBonus of each completed set  # FLAT — completion reward, card
              # quality already lives in per-card (edition/recency/tier); no extra scaling
  finalScore= Σ per-card × (1 + min(Σ setBonus, MAX_SET_BONUS))
  grade     = first threshold finalScore meets (high→low) — a LABEL only
  dividend  = round(SHOWCASE_DIVIDEND_RATE × finalScore)   # paid per regular-season week
  cardShare = round(SHOWCASE_DIVIDEND_RATE × per-card × (1 + setBonus))  # sums to dividend

SET_RULES is an extensible list: each rule is a detector that returns the number
of cards still needed (0 = the set is active). Add a rule = add an entry.
"""

from constants import (
    SHOWCASE_SLOTS,
    SHOWCASE_EDITION_POINTS,
    SHOWCASE_CLASSIFICATION_POINTS,
    SHOWCASE_RECENCY_BY_AGE,
    SHOWCASE_RECENCY_FLOOR,
    SHOWCASE_TIER_BONUS_PER_LEVEL,
    SHOWCASE_MAX_SET_BONUS,
    SHOWCASE_GRADE_THRESHOLDS,
    SHOWCASE_DIVIDEND_RATE,
)


# ─── Per-card value ──────────────────────────────────────────────────────────

def _recency(seasonCreated: int, currentSeason: int) -> float:
    """Newer cards are worth more; gentle for one season, then a steep cliff."""
    seasonsOld = max(0, (currentSeason or 0) - (seasonCreated or 0))
    return SHOWCASE_RECENCY_BY_AGE.get(seasonsOld, SHOWCASE_RECENCY_FLOOR)


_CLASSIFICATION_LABELS = {"rookie": "Rookie", "all_pro": "All-Pro", "champion": "Champion", "mvp": "MVP"}


def _classificationPoints(classification) -> int:
    if not classification:
        return 0
    return sum(pts for key, pts in SHOWCASE_CLASSIFICATION_POINTS.items()
               if key in classification)


def _classificationTags(classification) -> list:
    """Per-tag breakdown so the client can name a card's badges (Champion, All-Pro,
    MVP, Rookie) instead of a single opaque 'Classification' lump."""
    if not classification:
        return []
    return [{"name": _CLASSIFICATION_LABELS.get(key, key), "points": pts}
            for key, pts in SHOWCASE_CLASSIFICATION_POINTS.items()
            if key in classification]


def _cardBreakdown(card: dict, currentSeason: int) -> dict:
    """Per-card scoring breakdown. card = {edition, classification, tier, seasonCreated}.

    Returns the raw multipliers AND the card's pre-set-bonus point contribution
    (`points`), so the client can show exactly why a card pays what it does. The
    Floobit share is filled in by `evaluate` once the set-bonus multiplier is known.
    """
    editionPts = SHOWCASE_EDITION_POINTS.get(card.get("edition"), 0)
    classificationPts = _classificationPoints(card.get("classification"))
    rec = _recency(card.get("seasonCreated", currentSeason), currentSeason)
    tier = card.get("tier", 1) or 1
    tierMult = 1.0 + (tier - 1) * SHOWCASE_TIER_BONUS_PER_LEVEL
    # Recency decays the WHOLE base — prestige (MVP/champ/all-pro) included — so an
    # old trophy card doesn't let a collector coast; the showcase rewards hunting
    # for new cards every season.
    points = (editionPts + classificationPts) * rec * tierMult
    return {
        "userCardId": card.get("userCardId"),
        "editionPoints": editionPts,
        "classificationPoints": classificationPts,
        "classifications": _classificationTags(card.get("classification")),
        "recency": round(rec, 3),
        "tierMult": round(tierMult, 3),
        "points": round(points, 2),
    }


def _cardPoints(card: dict, currentSeason: int) -> float:
    """The card's pre-set-bonus point contribution (thin wrapper over the breakdown)."""
    return _cardBreakdown(card, currentSeason)["points"]


# ─── Set detectors (return (cards-still-needed, member-cards); 0 dist = active) ─
# Each detector returns how many cards the set still needs AND the cards that form
# it. A completed set adds its FLAT bonus (no edition scaling) — card quality is
# already priced into per-card scoring.

def _hasTag(card: dict, tag: str) -> bool:
    c = card.get("classification")
    return bool(c) and tag in c


def _distFullSpectrum(cards):
    byPlayer = {}
    for c in cards:
        byPlayer.setdefault(c.get("playerId"), {})[c.get("edition")] = c
    bestCards, bestN = [], 0
    for edMap in byPlayer.values():
        if len(edMap) > bestN:
            bestN, bestCards = len(edMap), list(edMap.values())
    return max(0, 4 - bestN), bestCards


def _distOneClub(cards):
    byTeam = {}
    for c in cards:
        tid = c.get("teamId")
        if tid:
            byTeam.setdefault(tid, []).append(c)
    best = max(byTeam.values(), key=len, default=[])
    return max(0, 6 - len(best)), best


def _distChampionSquad(cards):
    byTeam = {}
    for c in cards:
        tid = c.get("teamId")
        if tid and _hasTag(c, "champion"):
            byTeam.setdefault(tid, []).append(c)
    best = max(byTeam.values(), key=len, default=[])
    return max(0, 6 - len(best)), best


def _distAllProLine(cards):
    members = [c for c in cards if _hasTag(c, "all_pro")]
    return max(0, 5 - len(members)), members


def _distHallOfFame(cards):
    members = [c for c in cards
               if _hasTag(c, "mvp") or _hasTag(c, "champion") or _hasTag(c, "all_pro")]
    return max(0, SHOWCASE_SLOTS - len(members)), members


def _distDiamondVault(cards):
    members = [c for c in cards if c.get("edition") == "diamond"]
    return max(0, SHOWCASE_SLOTS - len(members)), members


def _distRainbow(cards):
    byEd = {}
    for c in cards:
        byEd.setdefault(c.get("edition"), c)
    present = [byEd[e] for e in ("base", "holographic", "prismatic", "diamond") if e in byEd]
    return max(0, 4 - len(present)), present


# key, name, bonus, detector, a human "requirement" line for the paytable, and
# singular/plural units for the "almost" hint.
SET_RULES = [
    {"key": "full_spectrum",  "name": "Full Spectrum",  "bonus": 0.5, "fn": _distFullSpectrum,  "req": "All 4 editions of one player",     "one": "edition of one player",        "many": "editions of one player"},
    {"key": "one_club",       "name": "One Club",       "bonus": 0.6, "fn": _distOneClub,       "req": "6 cards from one team",            "one": "card from one team",           "many": "cards from one team"},
    {"key": "champion_squad", "name": "Champion Squad", "bonus": 0.8, "fn": _distChampionSquad, "req": "6 champions from one team",        "one": "champion from one team",       "many": "champions from one team"},
    {"key": "all_pro_line",   "name": "All-Pro Line",   "bonus": 0.5, "fn": _distAllProLine,    "req": "5 All-Pro cards",                  "one": "All-Pro card",                 "many": "All-Pro cards"},
    {"key": "hall_of_fame",   "name": "Hall of Fame",   "bonus": 0.7, "fn": _distHallOfFame,    "req": "8 MVP / Champion / All-Pro cards", "one": "MVP/Champion/All-Pro card",    "many": "MVP/Champion/All-Pro cards"},
    {"key": "diamond_vault",  "name": "Diamond Vault",  "bonus": 1.0, "fn": _distDiamondVault,  "req": "8 Diamonds",                       "one": "Diamond",                      "many": "Diamonds"},
    {"key": "rainbow",        "name": "Rainbow",        "bonus": 0.3, "fn": _distRainbow,       "req": "One card of each edition",         "one": "edition",                      "many": "editions"},
]


def setsCatalog() -> list:
    """Static reference of every set (the 'paytable'): name, requirement, and the
    base bonus it adds at full (all-Diamond) edition quality. The realized bonus on
    a live showcase scales down with the set's mean edition quality — see evaluate.
    """
    return [{
        "key": r["key"],
        "name": r["name"],
        "req": r["req"],
        "bonus": round(r["bonus"], 2),
    } for r in SET_RULES]


# ─── Grade + evaluation ──────────────────────────────────────────────────────

def _grade(score: float) -> str:
    for grade, threshold in SHOWCASE_GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return "F"


def weeklyDividend(finalScore: float) -> int:
    """Floobits paid per regular-season week for a showcase scoring `finalScore`."""
    return round(SHOWCASE_DIVIDEND_RATE * finalScore)


def evaluate(cards, currentSeason: int) -> dict:
    """Score a showcase. `cards` = list of card-info dicts (≤ SHOWCASE_SLOTS).

    Returns the grade (a label), the weekly Floobit dividend, the active named
    sets, the 'almost' sets (1–2 cards away), a transparent per-card breakdown
    (each card's multipliers + its Floobit share of the dividend), and the raw
    scores (`baseScore`, `score`, `setBonus`). Everything here is now client-safe
    — the dividend is deliberately legible."""
    breakdowns = [_cardBreakdown(c, currentSeason) for c in cards]
    baseScore = sum(b["points"] for b in breakdowns)
    # `sets` is the full paytable with each set's LIVE status (active / almost /
    # locked); `active` and `almost` are kept as filtered convenience views.
    active, almost, sets, totalBonus = [], [], [], 0.0
    for rule in SET_RULES:
        dist, members = rule["fn"](cards)
        entry = {
            "key": rule["key"],
            "name": rule["name"],
            "req": rule["req"],
            "bonus": round(rule["bonus"], 2),   # base bonus at all-Diamond quality
        }
        if dist == 0 and cards:
            # FLAT completion bonus — a set adds its full bonus regardless of the
            # editions in it. Card quality is already priced into baseScore (edition /
            # recency / tier), so the set bonus is a pure completion reward. No edition
            # scaling (it double-taxed quality and made the payout confusing).
            totalBonus += rule["bonus"]
            entry.update(status="active")
            active.append({"key": rule["key"], "name": rule["name"]})
        elif cards and 1 <= dist <= 2:
            unit = rule["one"] if dist == 1 else rule["many"]
            hint = f"{dist} more {unit}"
            entry.update(status="almost", need=dist, hint=hint)
            almost.append({"key": rule["key"], "name": rule["name"], "need": dist, "hint": hint})
        else:
            entry.update(status="locked", need=dist)
        sets.append(entry)
    totalBonus = min(totalBonus, SHOWCASE_MAX_SET_BONUS)
    finalScore = baseScore * (1.0 + totalBonus)
    dividend = weeklyDividend(finalScore)
    # Each card's Floobit share = its points carried through the same set-bonus
    # multiplier and dividend rate. Shares sum to (very near) the dividend; any
    # rounding remainder is harmless (display only).
    for b in breakdowns:
        b["dividend"] = round(SHOWCASE_DIVIDEND_RATE * b["points"] * (1.0 + totalBonus))
    return {
        "grade": _grade(finalScore),
        "weeklyDividend": dividend,
        "activeSets": active,
        "almostSets": almost,
        "sets": sets,                        # full paytable w/ live per-set status
        "maxSetBonus": round(SHOWCASE_MAX_SET_BONUS, 2),
        "cardBreakdown": breakdowns,
        "baseScore": round(baseScore, 1),
        "setBonus": round(totalBonus, 3),   # e.g. 0.45 → sets add +45%
        "dividendRate": SHOWCASE_DIVIDEND_RATE,  # weekly payout = rate × score × (1+setBonus)
        # Scoring "manual" — the point tables, so the client can render the rules.
        "scoring": {
            "edition": SHOWCASE_EDITION_POINTS,
            "classification": SHOWCASE_CLASSIFICATION_POINTS,
            "recencyByAge": {str(k): v for k, v in SHOWCASE_RECENCY_BY_AGE.items()},
            "recencyFloor": SHOWCASE_RECENCY_FLOOR,
            "tierBonusPerLevel": SHOWCASE_TIER_BONUS_PER_LEVEL,
            "grades": [[g, t] for g, t in SHOWCASE_GRADE_THRESHOLDS],  # [grade, minScore]
        },
        "score": round(finalScore, 1),      # drives the grade + leaderboard ranking
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


# Weekly dividend transaction type. (The old once-a-season "showcase_payout" type
# is retired — historical rows are still readable, but nothing writes it anymore.)
SHOWCASE_DIVIDEND_TX = "showcase_dividend"


def awardWeeklyDividends(session, season: int, week: int) -> dict:
    """Grade every user's featured showcase for the week and pay its dividend.
    Idempotent: a per-(season, week) transaction guard prevents double payment on
    a resume/replay. Does NOT commit — the caller owns the transaction. Returns a
    summary including per-user results so the caller can log / notify.
    """
    from database.models import CurrencyTransaction, ShowcaseSlot
    from database.repositories.card_repositories import CurrencyRepository

    already = session.query(CurrencyTransaction.id).filter(
        CurrencyTransaction.transaction_type == SHOWCASE_DIVIDEND_TX,
        CurrencyTransaction.season == season,
        CurrencyTransaction.week == week,
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
        dividend = ev["weeklyDividend"]
        results.append({"userId": userId, "grade": ev["grade"], "dividend": dividend})
        if dividend > 0:
            cur.addFunds(userId, dividend, SHOWCASE_DIVIDEND_TX,
                         f"Showcase dividend (grade {ev['grade']}, week {week})",
                         season, week)
    return {"paid": sum(1 for r in results if r["dividend"] > 0),
            "alreadyAwarded": False, "results": results}


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

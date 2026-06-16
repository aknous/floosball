"""Calibrate Showcase grade thresholds via Monte Carlo.

Simulates collectors at several engagement levels (collection size), builds each
one's best 8-card showcase, scores it through the real showcaseManager engine,
and reports the score distribution. Use the percentiles to set
SHOWCASE_GRADE_THRESHOLDS so grades map onto achievable showcases.

Run: python3 tune_showcase.py
"""
import random
from managers import showcaseManager

random.seed(42)
SEASON = 9

# Realistic vault age spread: most cards are recent (packs are opened every
# season), with a thinning tail of older cards. Drives the recency decay so the
# tuner reflects real collections, not an all-current best case.
AGE_SPREAD = [(0, 0.40), (1, 0.24), (2, 0.15), (3, 0.10), (4, 0.06), (5, 0.03), (6, 0.02)]

# Proposed grade thresholds to evaluate (independent of constants.py so we can
# iterate before committing). Set to None to use the live constants.
PROPOSED_THRESHOLDS = None


def drawSeasonsOld():
    r = random.random()
    acc = 0.0
    for old, p in AGE_SPREAD:
        acc += p
        if r <= acc:
            return old
    return AGE_SPREAD[-1][0]

# Pack rarity weights (paid packs, from card seed) -> normalized probabilities.
EDITION_WEIGHTS = {"base": 82, "holographic": 28, "prismatic": 5, "diamond": 1}
_total = sum(EDITION_WEIGHTS.values())
EDITION_P = [(e, w / _total) for e, w in EDITION_WEIGHTS.items()]

NUM_TEAMS = 24
# Classification odds: mvp/champion/all_pro only on holo+; rookie on any.
HOLO_CLASS_CHANCE = 0.15   # chance a holo+ card carries a marquee classification
ROOKIE_CHANCE = 0.10       # chance any card is a rookie (if not already classified)


def drawEdition():
    r = random.random()
    acc = 0.0
    for e, p in EDITION_P:
        acc += p
        if r <= acc:
            return e
    return "base"


def drawCard(idx):
    edition = drawEdition()
    classification = None
    if edition != "base" and random.random() < HOLO_CLASS_CHANCE:
        classification = random.choice(["mvp", "champion", "all_pro"])
    elif random.random() < ROOKIE_CHANCE:
        classification = "rookie"
    return {
        "edition": edition,
        "classification": classification,
        "tier": 1,
        "seasonCreated": SEASON - drawSeasonsOld(),   # realistic age spread
        "playerId": idx,
        "teamId": random.randint(1, NUM_TEAMS),
    }


def cardPoints(c):
    return showcaseManager._cardPoints(c, SEASON)


def buildShowcase(collectionSize, setAware=True):
    cards = [drawCard(i) for i in range(collectionSize)]
    if not setAware:
        return sorted(cards, key=cardPoints, reverse=True)[:8]
    # Light set-aware pick: try the most common team for a One Club lean, then
    # fill the rest with the highest-value cards. Approximates a thoughtful user.
    byTeam = {}
    for c in cards:
        byTeam.setdefault(c["teamId"], []).append(c)
    bestTeam = max(byTeam.values(), key=len)
    pick = []
    if len(bestTeam) >= 5:  # worth chasing One Club
        pick = sorted(bestTeam, key=cardPoints, reverse=True)[:6]
    chosen = {id(c) for c in pick}
    rest = sorted((c for c in cards if id(c) not in chosen), key=cardPoints, reverse=True)
    pick += rest[: 8 - len(pick)]
    return pick


def pct(sortedVals, p):
    if not sortedVals:
        return 0
    i = min(len(sortedVals) - 1, int(p / 100 * len(sortedVals)))
    return sortedVals[i]


LEVELS = [
    ("casual (15)", 15),
    ("regular (40)", 40),
    ("dedicated (100)", 100),
    ("whale (250)", 250),
]
N = 4000

def gradeFor(score, thresholds):
    for g, t in thresholds:
        if score >= t:
            return g
    return "F"


LIVE_THRESHOLDS = showcaseManager.SHOWCASE_GRADE_THRESHOLDS
THRESH = PROPOSED_THRESHOLDS or LIVE_THRESHOLDS
label_thresh = "PROPOSED" if PROPOSED_THRESHOLDS else "live"

print(f"Monte Carlo: {N} collectors per level, best-8 set-aware showcase, realistic age spread")
print(f"Thresholds under test ({label_thresh}): {THRESH}\n")
allScores = []
for label, size in LEVELS:
    scores = []
    grades = {}
    for _ in range(N):
        sc = buildShowcase(size)
        ev = showcaseManager.evaluate(sc, SEASON)
        scores.append(ev["score"])
        g = gradeFor(ev["score"], THRESH)
        grades[g] = grades.get(g, 0) + 1
    scores.sort()
    allScores += scores
    gradeStr = " ".join(f"{g}:{grades.get(g,0)*100//N}%" for g in ["F", "D", "C", "B", "A", "S"])
    print(f"{label:>16}  p25={pct(scores,25):6.0f}  p50={pct(scores,50):6.0f}  "
          f"p75={pct(scores,75):6.0f}  p90={pct(scores,90):6.0f}  p99={pct(scores,99):6.0f}")
    print(f"{'':>16}  grades ({label_thresh}): {gradeStr}")

allScores.sort()
print("\nOverall score percentiles (all levels pooled):")
for p in [10, 25, 50, 70, 85, 95, 99]:
    print(f"  p{p}: {pct(allScores, p):.0f}")

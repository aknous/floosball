"""Playoff bracket-challenge core logic: seeding/matchup projection + scoring.

The playoffs RE-SEED every round (NFL-style): each round the surviving teams
are sorted by regular-season record and paired top-vs-bottom. Seeds are frozen
at lock, so given any set of predicted survivors the next round's matchups are
fully determined. This module is the single source of truth for that rule —
used to (a) project the matchup tree for the fill-out UI and (b) score a
submitted bracket against actual results. It MUST mirror
seasonManager._simulatePlayoffRounds' pairing, or the displayed tree drifts
from reality.

Pure functions only (no DB / no I/O) so they're trivially testable and shared.

A "seed entry" is a dict: {"teamId": int, "winPct": float, "scoreDiff": int,
"conference": str, "seed": int}. The frozen playoff field is a list of these.
"""
from typing import Dict, List, Tuple

# Round indices (match game.playoff_round 1..4) and the game's own round names.
ROUND_1 = 1
ROUND_2 = 2
ROUND_LEAGUE_CHAMPIONSHIP = 3
ROUND_FLOOSBOWL = 4
ROUND_KEYS = {ROUND_1: "round1", ROUND_2: "round2",
              ROUND_LEAGUE_CHAMPIONSHIP: "league_championship", ROUND_FLOOSBOWL: "floosbowl"}
ROUND_LABELS = {ROUND_1: "Round 1", ROUND_2: "Round 2",
                ROUND_LEAGUE_CHAMPIONSHIP: "League Championship", ROUND_FLOOSBOWL: "Floos Bowl"}

# Points awarded per correctly-predicted advancer, by round (doubling, MM-style).
ROUND_POINTS = {ROUND_1: 1, ROUND_2: 2, ROUND_LEAGUE_CHAMPIONSHIP: 4, ROUND_FLOOSBOWL: 8}
CHAMPION_BONUS = 5


def _seedSort(entries: List[Dict]) -> List[Dict]:
    """Engine's ordering: best record first (winPct, then scoreDiff), with a
    stable teamId tiebreak so projection never diverges from the sim on ties."""
    return sorted(entries, key=lambda e: (e["winPct"], e["scoreDiff"], -e["teamId"]), reverse=True)


def pairTopVsBottom(survivors: List[Dict]) -> List[Tuple[Dict, Dict]]:
    """Re-seed a set of survivors into matchups: 1v(n), 2v(n-1)… — exactly the
    engine's `hiSeed vs lowSeed` pairing. Returns (higherSeed, lowerSeed) pairs."""
    ordered = _seedSort(survivors)
    pairs = []
    lo, hi = len(ordered) - 1, 0
    while lo > hi:
        pairs.append((ordered[hi], ordered[lo]))
        hi += 1
        lo -= 1
    return pairs


def projectRound(field: List[Dict], roundIndex: int,
                 survivorIdsByConf: Dict[str, List[int]]) -> Dict[str, List[Tuple[Dict, Dict]]]:
    """Project a round's matchups from the surviving teams entering it.

    survivorIdsByConf: {conference: [teamId,...]} — teams still alive entering
    this round (for round 1, the non-bye seeds 3-6; later rounds, byes + prior
    winners). Floosbowl (round 4) is cross-conference: the two conference
    champions. Returns {conference_or_'floosbowl': [(hi, lo), ...]}.
    """
    byId = {e["teamId"]: e for e in field}
    if roundIndex == ROUND_FLOOSBOWL:
        champs = [byId[tid] for ids in survivorIdsByConf.values() for tid in ids if tid in byId]
        return {"floosbowl": pairTopVsBottom(champs)} if len(champs) >= 2 else {"floosbowl": []}
    out = {}
    for conf, ids in survivorIdsByConf.items():
        entries = [byId[t] for t in ids if t in byId]
        out[conf] = pairTopVsBottom(entries)
    return out


def scoreBracket(predictions: Dict[str, List[int]],
                 actualAdvancers: Dict[str, List[int]],
                 championId: int = None) -> Dict:
    """Score a submitted bracket against actual results (per-advancer).

    predictions / actualAdvancers: {round_key: [teamId,...]} — teams predicted
    to / that actually advanced PAST that round (i.e. won that round). A pick
    scores its round's points if that team genuinely advanced past that round,
    independent of which matchup it came through (re-seeding-agnostic).
    championId: the actual Floosbowl winner, for the exact-champion bonus.
    """
    points = 0
    correct = 0
    perRound = {}
    for rnd, key in ROUND_KEYS.items():
        predicted = set(predictions.get(key, []) or [])
        actual = set(actualAdvancers.get(key, []) or [])
        hits = predicted & actual
        roundPts = len(hits) * ROUND_POINTS[rnd]
        points += roundPts
        correct += len(hits)
        perRound[key] = {"correct": len(hits), "predicted": len(predicted), "points": roundPts}
    # Exact-champion bonus (the floosbowl pick that actually won it all).
    champBonus = 0
    predChamp = (predictions.get("floosbowl") or [None])
    if championId is not None and championId in set(predChamp):
        champBonus = CHAMPION_BONUS
        points += champBonus
    return {"points": points, "correctCount": correct, "perRound": perRound, "championBonus": champBonus}

"""Test win probability algorithm with various close, late-game situations."""

import numpy as np
from unittest.mock import MagicMock


def calculateExpectedPoints(down, yardsToFirstDown, yardsToEndzone, scoreChange=False):
    """Standalone EP calculation matching floosball_game.py logic."""
    if scoreChange:
        return 0.0

    field_position = 100 - yardsToEndzone
    _ep_positions = [0,   5,   20,  40,  50,  60,  70,  80,  90,  100]
    _ep_values    = [-1.5, -1.0, 0.0, 1.0, 2.0, 2.5, 3.0, 3.5, 4.5, 5.5]
    base_ep = float(np.interp(field_position, _ep_positions, _ep_values))

    inFgRange = field_position >= 60
    ytfd = yardsToFirstDown
    if down == 1:
        down_factor = 1.0
    elif down == 2:
        down_factor = float(np.interp(ytfd, [1, 3, 7, 10, 15], [0.95, 0.92, 0.82, 0.70, 0.60]))
        if inFgRange:
            down_factor = max(down_factor, 0.85)
    elif down == 3:
        down_factor = float(np.interp(ytfd, [1, 3, 7, 10, 15], [0.85, 0.70, 0.40, 0.25, 0.15]))
        if inFgRange:
            down_factor = max(down_factor, 0.75)
    else:  # 4th down
        if inFgRange:
            down_factor = 0.65
        else:
            down_factor = float(np.interp(ytfd, [1, 3, 7, 10], [0.15, 0.10, 0.05, 0.03]))

    return base_ep * down_factor


def calculateWinProbability(homeScore, awayScore, quarter, clockSeconds,
                             down, yardsToFirstDown, yardsToEndzone,
                             offenseIsHome=True, homeElo=1500, awayElo=1500,
                             scoreChange=False, gameOver=False):
    """Standalone WP calculation matching floosball_game.py logic."""
    # Total seconds remaining
    if quarter == 1:
        total_seconds = clockSeconds + (3 * 900)
    elif quarter == 2:
        total_seconds = clockSeconds + (2 * 900)
    elif quarter == 3:
        total_seconds = clockSeconds + 900
    elif quarter == 4:
        total_seconds = clockSeconds
    else:
        total_seconds = clockSeconds

    eloDiff = homeElo - awayElo
    eloHomeWp = 100 / (1 + 10 ** (-eloDiff / 400))

    totalGameTime = 3600
    timeElapsed = totalGameTime - total_seconds
    gameProgress = min(1.0, timeElapsed / totalGameTime)

    eloWeight = max(0.05, 1.0 - gameProgress * 0.95)

    scoreDiff = homeScore - awayScore

    expectedPoints = calculateExpectedPoints(down, yardsToFirstDown, yardsToEndzone, scoreChange)

    if offenseIsHome:
        homeExpected = expectedPoints
        awayExpected = 0
    else:
        homeExpected = 0
        awayExpected = expectedPoints

    estimatedPossessions = max(1.0, total_seconds / 150.0)
    epWeight = 1.0 / estimatedPossessions
    epDampener = 1.0 / (1.0 + (abs(scoreDiff) / 7.0) ** 1.5)
    adjustedScoreDiff = scoreDiff + (homeExpected - awayExpected) * epWeight * epDampener

    k = 0.06 + (gameProgress ** 0.8) * 0.34

    scoreWp = 100 / (1 + np.exp(-k * adjustedScoreDiff))

    homeWinProb = eloWeight * eloHomeWp + (1 - eloWeight) * scoreWp
    awayWinProb = 100 - homeWinProb

    if quarter >= 5:
        if scoreDiff == 0:
            if offenseIsHome:
                homeWinProb = 52 + (expectedPoints * 2)
            else:
                awayWinProb = 52 + (expectedPoints * 2)
            homeWinProb = min(100, max(0, homeWinProb))
            awayWinProb = 100 - homeWinProb

    if not gameOver:
        homeWinProb = max(0.1, min(99.9, homeWinProb))
        awayWinProb = max(0.1, min(99.9, awayWinProb))
    else:
        if homeScore > awayScore:
            homeWinProb, awayWinProb = 100, 0
        elif awayScore > homeScore:
            homeWinProb, awayWinProb = 0, 100
        else:
            homeWinProb, awayWinProb = 50, 50

    return {'home': round(homeWinProb, 1), 'away': round(awayWinProb, 1)}


def fmt(wp):
    return f"Home {wp['home']:5.1f}% | Away {wp['away']:5.1f}%"


def run_scenario(title, situations):
    """Run a list of situations and print results."""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")
    prev_wp = None
    for label, kwargs in situations:
        if kwargs is None:
            print()
            prev_wp = None
            continue
        wp = calculateWinProbability(**kwargs)
        delta = ""
        if prev_wp is not None:
            d = wp['home'] - prev_wp['home']
            delta = f"  (Δ {d:+.1f}%)"
        print(f"  {label:<52s} {fmt(wp)}{delta}")
        prev_wp = wp


# =============================================================================
# SCENARIO 1: Tied game, Q4 — home team drives down field
# =============================================================================
run_scenario("TIED GAME 14-14, Q4 5:00 left — Home team drives", [
    ("1st & 10 at own 25 (5:00 left)",
     dict(homeScore=14, awayScore=14, quarter=4, clockSeconds=300,
          down=1, yardsToFirstDown=10, yardsToEndzone=75, offenseIsHome=True)),
    ("Incomplete pass → 2nd & 10 at own 25 (4:55)",
     dict(homeScore=14, awayScore=14, quarter=4, clockSeconds=295,
          down=2, yardsToFirstDown=10, yardsToEndzone=75, offenseIsHome=True)),
    ("3-yard run → 3rd & 7 at own 28 (4:25)",
     dict(homeScore=14, awayScore=14, quarter=4, clockSeconds=265,
          down=3, yardsToFirstDown=7, yardsToEndzone=72, offenseIsHome=True)),
    ("6-yard pass → 4th & 1 at own 34 (4:15)",
     dict(homeScore=14, awayScore=14, quarter=4, clockSeconds=255,
          down=4, yardsToFirstDown=1, yardsToEndzone=66, offenseIsHome=True)),
    ("First down! 1st & 10 at own 35 (4:10)",
     dict(homeScore=14, awayScore=14, quarter=4, clockSeconds=250,
          down=1, yardsToFirstDown=10, yardsToEndzone=65, offenseIsHome=True)),
    ("12-yard pass → 1st & 10 at own 47 (3:45)",
     dict(homeScore=14, awayScore=14, quarter=4, clockSeconds=225,
          down=1, yardsToFirstDown=10, yardsToEndzone=53, offenseIsHome=True)),
    ("5-yard run → 2nd & 5 at opp 48 (3:15)",
     dict(homeScore=14, awayScore=14, quarter=4, clockSeconds=195,
          down=2, yardsToFirstDown=5, yardsToEndzone=48, offenseIsHome=True)),
    ("8-yard pass → 1st & 10 at opp 40 (2:50)",
     dict(homeScore=14, awayScore=14, quarter=4, clockSeconds=170,
          down=1, yardsToFirstDown=10, yardsToEndzone=40, offenseIsHome=True)),
    ("3-yard run → 2nd & 7 at opp 37 (2:20)",
     dict(homeScore=14, awayScore=14, quarter=4, clockSeconds=140,
          down=2, yardsToFirstDown=7, yardsToEndzone=37, offenseIsHome=True)),
    ("15-yard pass → 1st & 10 at opp 22 (1:55)",
     dict(homeScore=14, awayScore=14, quarter=4, clockSeconds=115,
          down=1, yardsToFirstDown=10, yardsToEndzone=22, offenseIsHome=True)),
    ("5-yard run → 2nd & 5 at opp 17 (1:25)",
     dict(homeScore=14, awayScore=14, quarter=4, clockSeconds=85,
          down=2, yardsToFirstDown=5, yardsToEndzone=17, offenseIsHome=True)),
    ("Incomplete → 3rd & 5 at opp 17 (1:20)",
     dict(homeScore=14, awayScore=14, quarter=4, clockSeconds=80,
          down=3, yardsToFirstDown=5, yardsToEndzone=17, offenseIsHome=True)),
    ("2-yard run → 4th & 3 at opp 15 (FG range) (0:50)",
     dict(homeScore=14, awayScore=14, quarter=4, clockSeconds=50,
          down=4, yardsToFirstDown=3, yardsToEndzone=15, offenseIsHome=True)),
    ("FG is GOOD! 17-14 (score change)",
     dict(homeScore=17, awayScore=14, quarter=4, clockSeconds=47,
          down=1, yardsToFirstDown=10, yardsToEndzone=65, offenseIsHome=True, scoreChange=True)),
])


# =============================================================================
# SCENARIO 2: Home leads by 3, Q4 2:00 — Away team 2-minute drill
# =============================================================================
run_scenario("HOME LEADS 21-18, Q4 2:00 — Away 2-minute drill", [
    ("Kickoff: 1st & 10 at away 25 (2:00)",
     dict(homeScore=21, awayScore=18, quarter=4, clockSeconds=120,
          down=1, yardsToFirstDown=10, yardsToEndzone=75, offenseIsHome=False)),
    ("8-yard pass → 2nd & 2 at away 33 (1:52)",
     dict(homeScore=21, awayScore=18, quarter=4, clockSeconds=112,
          down=2, yardsToFirstDown=2, yardsToEndzone=67, offenseIsHome=False)),
    ("3-yard run → 1st & 10 at away 36 (1:45)",
     dict(homeScore=21, awayScore=18, quarter=4, clockSeconds=105,
          down=1, yardsToFirstDown=10, yardsToEndzone=64, offenseIsHome=False)),
    ("Incomplete → 2nd & 10 at away 36 (1:40)",
     dict(homeScore=21, awayScore=18, quarter=4, clockSeconds=100,
          down=2, yardsToFirstDown=10, yardsToEndzone=64, offenseIsHome=False)),
    ("5-yard pass → 3rd & 5 at away 41 (1:30)",
     dict(homeScore=21, awayScore=18, quarter=4, clockSeconds=90,
          down=3, yardsToFirstDown=5, yardsToEndzone=59, offenseIsHome=False)),
    ("20-yard pass → 1st & 10 at home 39 (1:20)",
     dict(homeScore=21, awayScore=18, quarter=4, clockSeconds=80,
          down=1, yardsToFirstDown=10, yardsToEndzone=39, offenseIsHome=False)),
    ("Sack! Loss of 7 → 2nd & 17 at home 46 (1:10)",
     dict(homeScore=21, awayScore=18, quarter=4, clockSeconds=70,
          down=2, yardsToFirstDown=17, yardsToEndzone=46, offenseIsHome=False)),
    ("12-yard pass → 3rd & 5 at home 34 (0:55)",
     dict(homeScore=21, awayScore=18, quarter=4, clockSeconds=55,
          down=3, yardsToFirstDown=5, yardsToEndzone=34, offenseIsHome=False)),
    ("Incomplete → 4th & 5 at home 34 (FG range) (0:50)",
     dict(homeScore=21, awayScore=18, quarter=4, clockSeconds=50,
          down=4, yardsToFirstDown=5, yardsToEndzone=34, offenseIsHome=False)),
    ("FG is GOOD! Tied 21-21 (score change)",
     dict(homeScore=21, awayScore=21, quarter=4, clockSeconds=47,
          down=1, yardsToFirstDown=10, yardsToEndzone=65, offenseIsHome=False, scoreChange=True)),
])


# =============================================================================
# SCENARIO 3: Home leads by 7, Q4 1:30 — Away needs TD
# =============================================================================
run_scenario("HOME LEADS 28-21, Q4 1:30 — Away needs TD to tie", [
    ("1st & 10 at away 30 (1:30)",
     dict(homeScore=28, awayScore=21, quarter=4, clockSeconds=90,
          down=1, yardsToFirstDown=10, yardsToEndzone=70, offenseIsHome=False)),
    ("Incomplete → 2nd & 10 (1:25)",
     dict(homeScore=28, awayScore=21, quarter=4, clockSeconds=85,
          down=2, yardsToFirstDown=10, yardsToEndzone=70, offenseIsHome=False)),
    ("15-yard pass → 1st & 10 at away 45 (1:15)",
     dict(homeScore=28, awayScore=21, quarter=4, clockSeconds=75,
          down=1, yardsToFirstDown=10, yardsToEndzone=55, offenseIsHome=False)),
    ("6-yard pass → 2nd & 4 at home 49 (1:00)",
     dict(homeScore=28, awayScore=21, quarter=4, clockSeconds=60,
          down=2, yardsToFirstDown=4, yardsToEndzone=49, offenseIsHome=False)),
    ("5-yard pass → 1st & 10 at home 44 (0:50)",
     dict(homeScore=28, awayScore=21, quarter=4, clockSeconds=50,
          down=1, yardsToFirstDown=10, yardsToEndzone=44, offenseIsHome=False)),
    ("Incomplete → 2nd & 10 at home 44 (0:45)",
     dict(homeScore=28, awayScore=21, quarter=4, clockSeconds=45,
          down=2, yardsToFirstDown=10, yardsToEndzone=44, offenseIsHome=False)),
    ("25-yard pass → 1st & 10 at home 19 (0:35)",
     dict(homeScore=28, awayScore=21, quarter=4, clockSeconds=35,
          down=1, yardsToFirstDown=10, yardsToEndzone=19, offenseIsHome=False)),
    ("Incomplete → 2nd & 10 at home 19 (0:30)",
     dict(homeScore=28, awayScore=21, quarter=4, clockSeconds=30,
          down=2, yardsToFirstDown=10, yardsToEndzone=19, offenseIsHome=False)),
    ("INT by home team (0:28)",
     dict(homeScore=28, awayScore=21, quarter=4, clockSeconds=28,
          down=1, yardsToFirstDown=10, yardsToEndzone=70, offenseIsHome=True)),
    ("TD! Away ties it 28-28 (score change, alt reality)",
     dict(homeScore=28, awayScore=28, quarter=4, clockSeconds=25,
          down=1, yardsToFirstDown=10, yardsToEndzone=65, offenseIsHome=True, scoreChange=True)),
])


# =============================================================================
# SCENARIO 4: Close game, mundane plays — checking for erratic swings
# =============================================================================
run_scenario("TIED 10-10, Q4 3:00 — Mundane plays (swing check)", [
    ("1st & 10 at own 40 (3:00)",
     dict(homeScore=10, awayScore=10, quarter=4, clockSeconds=180,
          down=1, yardsToFirstDown=10, yardsToEndzone=60, offenseIsHome=True)),
    ("2-yard run → 2nd & 8 at own 42 (2:35)",
     dict(homeScore=10, awayScore=10, quarter=4, clockSeconds=155,
          down=2, yardsToFirstDown=8, yardsToEndzone=58, offenseIsHome=True)),
    ("1-yard run → 3rd & 7 at own 43 (2:10)",
     dict(homeScore=10, awayScore=10, quarter=4, clockSeconds=130,
          down=3, yardsToFirstDown=7, yardsToEndzone=57, offenseIsHome=True)),
    ("Incomplete → 4th & 7 at own 43 (2:05)",
     dict(homeScore=10, awayScore=10, quarter=4, clockSeconds=125,
          down=4, yardsToFirstDown=7, yardsToEndzone=57, offenseIsHome=True)),
    ("Punt — Away 1st & 10 at own 30 (2:00)",
     dict(homeScore=10, awayScore=10, quarter=4, clockSeconds=120,
          down=1, yardsToFirstDown=10, yardsToEndzone=70, offenseIsHome=False)),
    ("3-yard run → 2nd & 7 at own 33 (1:35)",
     dict(homeScore=10, awayScore=10, quarter=4, clockSeconds=95,
          down=2, yardsToFirstDown=7, yardsToEndzone=67, offenseIsHome=False)),
    ("Incomplete → 3rd & 7 at own 33 (1:30)",
     dict(homeScore=10, awayScore=10, quarter=4, clockSeconds=90,
          down=3, yardsToFirstDown=7, yardsToEndzone=67, offenseIsHome=False)),
    ("4-yard pass → 4th & 3 at own 37 (1:15)",
     dict(homeScore=10, awayScore=10, quarter=4, clockSeconds=75,
          down=4, yardsToFirstDown=3, yardsToEndzone=63, offenseIsHome=False)),
    ("Punt — Home 1st & 10 at own 20 (1:10)",
     dict(homeScore=10, awayScore=10, quarter=4, clockSeconds=70,
          down=1, yardsToFirstDown=10, yardsToEndzone=80, offenseIsHome=True)),
])


# =============================================================================
# SCENARIO 5: One-score game, Q4 final minute — possession changes
# =============================================================================
run_scenario("HOME LEADS 17-14, Q4 0:45 — Possession swings", [
    ("Home 1st & 10 at midfield — trying to run out clock (0:45)",
     dict(homeScore=17, awayScore=14, quarter=4, clockSeconds=45,
          down=1, yardsToFirstDown=10, yardsToEndzone=50, offenseIsHome=True)),
    ("3-yard run → 2nd & 7 (0:05)",
     dict(homeScore=17, awayScore=14, quarter=4, clockSeconds=5,
          down=2, yardsToFirstDown=7, yardsToEndzone=47, offenseIsHome=True)),
    ("Game over! Home wins 17-14",
     dict(homeScore=17, awayScore=14, quarter=4, clockSeconds=0,
          down=2, yardsToFirstDown=7, yardsToEndzone=47, offenseIsHome=True, gameOver=True)),
])


# =============================================================================
# SCENARIO 6: Big play swings in close game
# =============================================================================
run_scenario("TIED 7-7, Q4 4:00 — Big play swings", [
    ("Home 1st & 10 at own 20 (4:00)",
     dict(homeScore=7, awayScore=7, quarter=4, clockSeconds=240,
          down=1, yardsToFirstDown=10, yardsToEndzone=80, offenseIsHome=True)),
    ("FUMBLE! Away recovers at home 20 (3:55)",
     dict(homeScore=7, awayScore=7, quarter=4, clockSeconds=235,
          down=1, yardsToFirstDown=10, yardsToEndzone=20, offenseIsHome=False)),
    ("TD! Away scores → 7-14 (score change)",
     dict(homeScore=7, awayScore=14, quarter=4, clockSeconds=230,
          down=1, yardsToFirstDown=10, yardsToEndzone=65, offenseIsHome=True, scoreChange=True)),
    ("Home 1st & 10 at own 25 after kickoff (3:25)",
     dict(homeScore=7, awayScore=14, quarter=4, clockSeconds=205,
          down=1, yardsToFirstDown=10, yardsToEndzone=75, offenseIsHome=True)),
    ("50-yard bomb → 1st & 10 at opp 25 (3:15)",
     dict(homeScore=7, awayScore=14, quarter=4, clockSeconds=195,
          down=1, yardsToFirstDown=10, yardsToEndzone=25, offenseIsHome=True)),
    ("TD! Home ties it → 14-14 (score change)",
     dict(homeScore=14, awayScore=14, quarter=4, clockSeconds=190,
          down=1, yardsToFirstDown=10, yardsToEndzone=65, offenseIsHome=False, scoreChange=True)),
])


# =============================================================================
# SCENARIO 7: ELO mismatch — underdog leading
# =============================================================================
run_scenario("UNDERDOG LEADS: Away (1350 ELO) leads Home (1650 ELO) 10-7, Q4", [
    ("Away has ball, 1st & 10 at midfield (5:00)",
     dict(homeScore=7, awayScore=10, quarter=4, clockSeconds=300,
          down=1, yardsToFirstDown=10, yardsToEndzone=50,
          offenseIsHome=False, homeElo=1650, awayElo=1350)),
    ("Away 1st & 10 at midfield (2:00)",
     dict(homeScore=7, awayScore=10, quarter=4, clockSeconds=120,
          down=1, yardsToFirstDown=10, yardsToEndzone=50,
          offenseIsHome=False, homeElo=1650, awayElo=1350)),
    ("Away 1st & 10 at midfield (0:30)",
     dict(homeScore=7, awayScore=10, quarter=4, clockSeconds=30,
          down=1, yardsToFirstDown=10, yardsToEndzone=50,
          offenseIsHome=False, homeElo=1650, awayElo=1350)),
])


# =============================================================================
# SCENARIO 8: Down-and-distance sensitivity check
# =============================================================================
run_scenario("TIED 14-14, Q4 2:00 — Down & distance sensitivity (same spot)", [
    ("1st & 10 at opp 35 (home has ball)",
     dict(homeScore=14, awayScore=14, quarter=4, clockSeconds=120,
          down=1, yardsToFirstDown=10, yardsToEndzone=35, offenseIsHome=True)),
    ("2nd & 10 at opp 35",
     dict(homeScore=14, awayScore=14, quarter=4, clockSeconds=120,
          down=2, yardsToFirstDown=10, yardsToEndzone=35, offenseIsHome=True)),
    ("2nd & 3 at opp 35",
     dict(homeScore=14, awayScore=14, quarter=4, clockSeconds=120,
          down=2, yardsToFirstDown=3, yardsToEndzone=35, offenseIsHome=True)),
    ("3rd & 10 at opp 35",
     dict(homeScore=14, awayScore=14, quarter=4, clockSeconds=120,
          down=3, yardsToFirstDown=10, yardsToEndzone=35, offenseIsHome=True)),
    ("3rd & 1 at opp 35",
     dict(homeScore=14, awayScore=14, quarter=4, clockSeconds=120,
          down=3, yardsToFirstDown=1, yardsToEndzone=35, offenseIsHome=True)),
    ("4th & 10 at opp 35",
     dict(homeScore=14, awayScore=14, quarter=4, clockSeconds=120,
          down=4, yardsToFirstDown=10, yardsToEndzone=35, offenseIsHome=True)),
    ("4th & 1 at opp 35 (FG range)",
     dict(homeScore=14, awayScore=14, quarter=4, clockSeconds=120,
          down=4, yardsToFirstDown=1, yardsToEndzone=35, offenseIsHome=True)),
])


# =============================================================================
# SCENARIO 9: 3-yard run in various late-game contexts (mundane play check)
# =============================================================================
run_scenario("3-YARD RUN: Same play, different contexts", [
    ("Tied 14-14, 1st&10 own 30, Q4 2:00",
     dict(homeScore=14, awayScore=14, quarter=4, clockSeconds=120,
          down=1, yardsToFirstDown=10, yardsToEndzone=70, offenseIsHome=True)),
    ("  After 3-yd run: 2nd&7 own 33, Q4 1:30",
     dict(homeScore=14, awayScore=14, quarter=4, clockSeconds=90,
          down=2, yardsToFirstDown=7, yardsToEndzone=67, offenseIsHome=True)),
    ("", None),
    ("Home up 3, 1st&10 own 30, Q4 2:00",
     dict(homeScore=17, awayScore=14, quarter=4, clockSeconds=120,
          down=1, yardsToFirstDown=10, yardsToEndzone=70, offenseIsHome=True)),
    ("  After 3-yd run: 2nd&7 own 33, Q4 1:30",
     dict(homeScore=17, awayScore=14, quarter=4, clockSeconds=90,
          down=2, yardsToFirstDown=7, yardsToEndzone=67, offenseIsHome=True)),
    ("", None),
    ("Home down 3, 1st&10 own 30, Q4 2:00",
     dict(homeScore=14, awayScore=17, quarter=4, clockSeconds=120,
          down=1, yardsToFirstDown=10, yardsToEndzone=70, offenseIsHome=True)),
    ("  After 3-yd run: 2nd&7 own 33, Q4 1:30",
     dict(homeScore=14, awayScore=17, quarter=4, clockSeconds=90,
          down=2, yardsToFirstDown=7, yardsToEndzone=67, offenseIsHome=True)),
])

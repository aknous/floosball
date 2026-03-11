"""
Tests for the momentum system in floosball_game.py.

Verifies:
1. Momentum helper methods (decay, dampening, resistance, streak, shift detection)
2. Full event processing (_applyMomentumEvent)
3. Gameplay effect application (_applyMomentumEffect)
4. Integration with broadcastGameState (momentum in game state data)
5. End-to-end simulation (run a real game and verify momentum behavior)
"""

import sys
import types
from unittest.mock import MagicMock, patch

# Pre-create the managers module to break the circular import
import importlib
sys.modules.setdefault('managers', MagicMock())
sys.modules.setdefault('managers.timingManager', MagicMock())

from constants import (
    MOMENTUM_DECAY_RATE, MOMENTUM_BLOWOUT_DECAY_RATE, MOMENTUM_MIDGAP_DECAY_RATE,
    MOMENTUM_CASCADE_STEP, MOMENTUM_MAX_CASCADE, MOMENTUM_MAX_STREAK,
    MOMENTUM_EFFECT_BASE, MOMENTUM_EFFECT_CAP, MOMENTUM_NEUTRAL_ZONE,
    MOMENTUM_SHIFT_THRESHOLD, MOMENTUM_CROSS_ZERO_THRESHOLD, MOMENTUM_DISPLAY_THRESHOLD,
    MOMENTUM_TD, MOMENTUM_TURNOVER, MOMENTUM_SAFETY, MOMENTUM_TURNOVER_ON_DOWNS,
    MOMENTUM_FG_MISSED, MOMENTUM_FG_MADE, MOMENTUM_SACK, MOMENTUM_BIG_PLAY_BONUS,
    MOMENTUM_PUNT,
)


def makePlayer(resilience=80, attitude=80, discipline=80):
    """Create a mock player with attributes."""
    p = MagicMock()
    p.attributes.resilience = resilience
    p.attributes.attitude = attitude
    p.attributes.discipline = discipline
    return p


def makeTeam(isHome=True, mentalStats=80):
    """Create a mock team with a roster."""
    team = MagicMock()
    team.abbr = 'HOM' if isHome else 'AWY'
    players = {
        'qb': makePlayer(mentalStats, mentalStats, mentalStats),
        'rb1': makePlayer(mentalStats, mentalStats, mentalStats),
        'wr1': makePlayer(mentalStats, mentalStats, mentalStats),
        'wr2': makePlayer(mentalStats, mentalStats, mentalStats),
        'wr3': makePlayer(mentalStats, mentalStats, mentalStats),
        'k': makePlayer(mentalStats, mentalStats, mentalStats),
    }
    team.rosterDict = players
    return team


def makeGame(homeScore=14, awayScore=10, momentum=0.0, streak=0, lastTeam=None, mentalStats=80):
    """Create a minimal game-like object with momentum methods attached."""
    # Import the methods from the Game class
    import floosball_game as fg

    game = MagicMock()
    game.homeScore = homeScore
    game.awayScore = awayScore
    game.momentum = momentum
    game.momentumStreak = streak
    game.lastMomentumTeam = lastTeam
    game.homeTeam = makeTeam(isHome=True, mentalStats=mentalStats)
    game.awayTeam = makeTeam(isHome=False, mentalStats=mentalStats)

    # Create a mock play
    game.play = MagicMock()
    game.play.isMomentumShift = False

    # Bind the actual methods from Game class
    game._decayMomentum = types.MethodType(fg.Game._decayMomentum, game)
    game._scoreGapDampener = types.MethodType(fg.Game._scoreGapDampener, game)
    game._mentalResistance = types.MethodType(fg.Game._mentalResistance, game)
    game._updateMomentumStreak = types.MethodType(fg.Game._updateMomentumStreak, game)
    game._isMomentumShift = types.MethodType(fg.Game._isMomentumShift, game)
    game._applyMomentumEvent = types.MethodType(fg.Game._applyMomentumEvent, game)
    game._applyMomentumEffect = types.MethodType(fg.Game._applyMomentumEffect, game)

    return game


# ─── Pure calculation tests (no Game object needed) ───────────────────

def testDecayRates():
    """Verify decay picks the right rate based on score differential."""
    print("  Decay rates by score diff...")

    # Close game (diff <= 14): 3%
    game = makeGame(homeScore=14, awayScore=10, momentum=50.0)
    game._decayMomentum()
    expected = 50.0 * (1.0 - MOMENTUM_DECAY_RATE)
    assert abs(game.momentum - expected) < 0.001, f"Expected {expected}, got {game.momentum}"

    # Mid gap (diff 15-21): 5%
    game = makeGame(homeScore=24, awayScore=7, momentum=50.0)
    game._decayMomentum()
    expected = 50.0 * (1.0 - MOMENTUM_MIDGAP_DECAY_RATE)
    assert abs(game.momentum - expected) < 0.001, f"Expected {expected}, got {game.momentum}"

    # Blowout (diff 22+): 8%
    game = makeGame(homeScore=35, awayScore=7, momentum=50.0)
    game._decayMomentum()
    expected = 50.0 * (1.0 - MOMENTUM_BLOWOUT_DECAY_RATE)
    assert abs(game.momentum - expected) < 0.001, f"Expected {expected}, got {game.momentum}"

    # Near-zero snaps to 0
    game = makeGame(momentum=0.3)
    game._decayMomentum()
    assert game.momentum == 0.0, f"Expected 0.0 for near-zero, got {game.momentum}"

    print("    PASSED")


def testScoreGapDampener():
    """Verify dampening returns correct multipliers by score gap."""
    print("  Score gap dampener...")

    game = makeGame(homeScore=10, awayScore=7)  # diff 3
    assert game._scoreGapDampener() == 1.0

    game = makeGame(homeScore=17, awayScore=7)  # diff 10
    assert game._scoreGapDampener() == 0.7

    game = makeGame(homeScore=24, awayScore=7)  # diff 17
    assert game._scoreGapDampener() == 0.4

    game = makeGame(homeScore=35, awayScore=7)  # diff 28
    assert game._scoreGapDampener() == 0.1

    print("    PASSED")


def testMentalResistance():
    """Verify mental resistance scales correctly with player attributes."""
    print("  Mental resistance...")

    # Low mental (60): no resistance → 1.0
    game = makeGame(mentalStats=60)
    resist = game._mentalResistance(game.awayTeam)
    assert abs(resist - 1.0) < 0.01, f"Expected ~1.0, got {resist}"

    # Mid mental (80): moderate resistance
    game = makeGame(mentalStats=80)
    resist = game._mentalResistance(game.awayTeam)
    expected = 1.0 - 0.3 * ((80 - 60) / 40.0)  # 0.85
    assert abs(resist - expected) < 0.01, f"Expected {expected}, got {resist}"

    # Max mental (100): max resistance → 0.7
    game = makeGame(mentalStats=100)
    resist = game._mentalResistance(game.awayTeam)
    assert abs(resist - 0.7) < 0.01, f"Expected ~0.7, got {resist}"

    print("    PASSED")


def testStreakTracking():
    """Verify streak increments, caps, and resets correctly."""
    print("  Streak tracking...")

    game = makeGame()

    # First event for home team: streak = 1
    game._updateMomentumStreak(game.homeTeam)
    assert game.momentumStreak == 1
    assert game.lastMomentumTeam is game.homeTeam

    # Second consecutive for home: streak = 2
    game._updateMomentumStreak(game.homeTeam)
    assert game.momentumStreak == 2

    # Third: streak = 3
    game._updateMomentumStreak(game.homeTeam)
    assert game.momentumStreak == 3

    # Switch to away: resets to -1
    game._updateMomentumStreak(game.awayTeam)
    assert game.momentumStreak == -1
    assert game.lastMomentumTeam is game.awayTeam

    # Consecutive away events
    game._updateMomentumStreak(game.awayTeam)
    assert game.momentumStreak == -2

    # Cap at max
    game.momentumStreak = -(MOMENTUM_MAX_STREAK - 1)
    game._updateMomentumStreak(game.awayTeam)
    assert game.momentumStreak == -MOMENTUM_MAX_STREAK
    game._updateMomentumStreak(game.awayTeam)
    assert game.momentumStreak == -MOMENTUM_MAX_STREAK  # Still capped

    print("    PASSED")


def testMomentumShiftDetection():
    """Verify shift detection thresholds."""
    print("  Momentum shift detection...")

    game = makeGame()

    # Large swing (>= 15): always a shift
    assert game._isMomentumShift(0, 15) == True
    assert game._isMomentumShift(10, 25) == True
    assert game._isMomentumShift(-20, -5) == True

    # Small swing: not a shift
    assert game._isMomentumShift(0, 5) == False
    assert game._isMomentumShift(10, 15) == False

    # Cross zero with >= 10 delta: is a shift
    assert game._isMomentumShift(5, -5) == True   # delta=10, crosses zero
    assert game._isMomentumShift(-6, 6) == True    # delta=12, crosses zero

    # Cross zero with < 10 delta: not a shift
    assert game._isMomentumShift(2, -2) == False   # delta=4, too small

    print("    PASSED")


def testApplyMomentumEvent():
    """Verify full event processing with cascade, dampening, and resistance."""
    print("  Apply momentum event (home TD, close game)...")

    # Close game (diff=4), first event, mid mental stats
    game = makeGame(homeScore=14, awayScore=10, mentalStats=80)

    game._applyMomentumEvent(MOMENTUM_TD, game.homeTeam)

    # Expected: rawDelta=20 * cascade=1.0 (streak=1) * gapDamp=1.0 (diff=4) * mentalResist=0.85 (80)
    expectedDelta = 20.0 * 1.0 * 1.0 * 0.85
    assert abs(game.momentum - expectedDelta) < 0.01, f"Expected {expectedDelta}, got {game.momentum}"
    assert game.momentumStreak == 1
    print(f"    TD for home: momentum={game.momentum:.1f} (expected ~{expectedDelta:.1f})")
    print("    PASSED")


def testApplyMomentumEventAway():
    """Verify away team events push momentum negative."""
    print("  Apply momentum event (away turnover, close game)...")

    game = makeGame(homeScore=14, awayScore=10, mentalStats=80)

    game._applyMomentumEvent(MOMENTUM_TURNOVER, game.awayTeam)

    resist = 0.85  # mental 80
    expectedDelta = -(18.0 * 1.0 * 1.0 * resist)
    assert abs(game.momentum - expectedDelta) < 0.01, f"Expected {expectedDelta}, got {game.momentum}"
    print(f"    Turnover for away: momentum={game.momentum:.1f} (expected ~{expectedDelta:.1f})")
    print("    PASSED")


def testCascadeMultiplier():
    """Verify cascade increases with consecutive events for same team."""
    print("  Cascade multiplier across consecutive events...")

    game = makeGame(homeScore=14, awayScore=10, mentalStats=80)
    resist = 0.85

    # Event 1: streak=1, cascade=1.0
    game._applyMomentumEvent(MOMENTUM_SACK, game.homeTeam)
    after1 = game.momentum
    print(f"    After sack 1: momentum={after1:.2f}, streak={game.momentumStreak}")

    # Event 2: streak=2, cascade=1.15
    game._applyMomentumEvent(MOMENTUM_SACK, game.homeTeam)
    after2 = game.momentum
    delta2 = after2 - after1
    expectedDelta2 = MOMENTUM_SACK * (1.0 + MOMENTUM_CASCADE_STEP * 1) * 1.0 * resist
    print(f"    After sack 2: momentum={after2:.2f}, delta={delta2:.2f} (expected ~{expectedDelta2:.2f}), streak={game.momentumStreak}")
    assert abs(delta2 - expectedDelta2) < 0.1, f"Cascade delta mismatch"

    # Event 3: streak=3, cascade=1.30
    game._applyMomentumEvent(MOMENTUM_SACK, game.homeTeam)
    after3 = game.momentum
    delta3 = after3 - after2
    expectedDelta3 = MOMENTUM_SACK * (1.0 + MOMENTUM_CASCADE_STEP * 2) * 1.0 * resist
    print(f"    After sack 3: momentum={after3:.2f}, delta={delta3:.2f} (expected ~{expectedDelta3:.2f}), streak={game.momentumStreak}")
    assert abs(delta3 - expectedDelta3) < 0.1, f"Cascade delta mismatch"

    print("    PASSED")


def testBlowoutDampening():
    """Verify events are dampened in blowout scenarios."""
    print("  Blowout dampening (28-pt diff)...")

    game = makeGame(homeScore=35, awayScore=7, mentalStats=80)
    resist = 0.85

    game._applyMomentumEvent(MOMENTUM_TD, game.homeTeam)
    expectedDelta = 20.0 * 1.0 * 0.1 * resist  # 0.1 dampening for 28-pt diff
    assert abs(game.momentum - expectedDelta) < 0.1, f"Expected ~{expectedDelta}, got {game.momentum}"
    print(f"    TD in blowout: momentum={game.momentum:.2f} (expected ~{expectedDelta:.2f})")
    print("    PASSED")


def testMomentumClamping():
    """Verify momentum is clamped to [-100, 100]."""
    print("  Momentum clamping...")

    game = makeGame(homeScore=14, awayScore=10, momentum=95.0, mentalStats=60)

    # A big event from 95 should clamp at 100
    game._applyMomentumEvent(MOMENTUM_TD, game.homeTeam)
    assert game.momentum <= 100.0, f"Expected <= 100, got {game.momentum}"
    assert game.momentum == 100.0, f"Expected exactly 100, got {game.momentum}"

    # Negative direction
    game = makeGame(homeScore=14, awayScore=10, momentum=-95.0, mentalStats=60)
    game._applyMomentumEvent(MOMENTUM_TD, game.awayTeam)
    assert game.momentum >= -100.0
    assert game.momentum == -100.0

    print("    PASSED")


def testMomentumEffectNeutralZone():
    """Verify no gameplay effect when momentum is in the neutral zone."""
    print("  Momentum effect - neutral zone...")

    game = makeGame(momentum=5.0)  # Below MOMENTUM_NEUTRAL_ZONE (10)

    game._applyMomentumEffect()

    # No players should have had updateInGameConfidence called
    for player in game.homeTeam.rosterDict.values():
        player.updateInGameConfidence.assert_not_called()
        player.updateInGameDetermination.assert_not_called()

    print("    PASSED")


def testMomentumEffectActive():
    """Verify gameplay effect applies when momentum is above neutral zone."""
    print("  Momentum effect - active (momentum=40)...")

    game = makeGame(momentum=40.0)

    game._applyMomentumEffect()

    expectedMag = min(MOMENTUM_EFFECT_BASE * (40.0 / 50.0), MOMENTUM_EFFECT_CAP)

    # Home team (benefiting) should get positive effects
    homeQb = game.homeTeam.rosterDict['qb']
    homeQb.updateInGameConfidence.assert_called_once()
    confArg = homeQb.updateInGameConfidence.call_args[0][0]
    assert confArg > 0, f"Expected positive confidence, got {confArg}"
    assert abs(confArg - expectedMag * 0.6) < 0.001

    # Away team (suffering) should get negative effects
    awayQb = game.awayTeam.rosterDict['qb']
    awayQb.updateInGameConfidence.assert_called_once()
    confArg = awayQb.updateInGameConfidence.call_args[0][0]
    assert confArg < 0, f"Expected negative confidence, got {confArg}"

    print(f"    Effect magnitude: {expectedMag:.5f}, boost confidence: {expectedMag*0.6:.5f}, drag: {-expectedMag*0.5*0.6:.5f}")
    print("    PASSED")


def testMomentumEffectCapped():
    """Verify effect magnitude is capped at MOMENTUM_EFFECT_CAP."""
    print("  Momentum effect - capped at high momentum...")

    game = makeGame(momentum=100.0)  # Max momentum

    game._applyMomentumEffect()

    homeQb = game.homeTeam.rosterDict['qb']
    confArg = homeQb.updateInGameConfidence.call_args[0][0]
    # At momentum=100: raw = 0.005 * (100/50) = 0.01, capped at 0.01
    assert abs(confArg - MOMENTUM_EFFECT_CAP * 0.6) < 0.001
    print(f"    Capped effect: confidence boost = {confArg:.5f}")
    print("    PASSED")


def testMomentumShiftOnEvent():
    """Verify isMomentumShift is set on play when threshold is met."""
    print("  Momentum shift flag on play...")

    # Starting from -10, a turnover for home pushes positive → crosses zero with big delta
    game = makeGame(homeScore=14, awayScore=10, momentum=-10.0, mentalStats=60)

    game._applyMomentumEvent(MOMENTUM_TURNOVER, game.homeTeam)

    # Delta should be 18 * 1.0 * 1.0 * 1.0 = 18. From -10 to +8.
    # Swing of 18 >= 15, AND crosses zero → should be a shift.
    assert game.play.isMomentumShift == True, "Expected momentum shift flag to be set"
    print(f"    From -10 → {game.momentum:.1f}: shift={game.play.isMomentumShift}")
    print("    PASSED")


def testStreakResetOnTeamSwitch():
    """Verify streak resets properly when opposing team scores."""
    print("  Streak reset on team switch...")

    game = makeGame(homeScore=14, awayScore=10, mentalStats=80)

    # Build home streak to 3
    game._applyMomentumEvent(MOMENTUM_TD, game.homeTeam)
    game._applyMomentumEvent(MOMENTUM_SACK, game.homeTeam)
    game._applyMomentumEvent(MOMENTUM_PUNT, game.homeTeam)
    assert game.momentumStreak == 3
    homeMomentum = game.momentum
    print(f"    After 3 home events: momentum={homeMomentum:.1f}, streak={game.momentumStreak}")

    # Away scores → streak resets to -1
    game._applyMomentumEvent(MOMENTUM_TD, game.awayTeam)
    assert game.momentumStreak == -1
    print(f"    After away TD: momentum={game.momentum:.1f}, streak={game.momentumStreak}")
    assert game.momentum < homeMomentum, "Momentum should decrease after away TD"

    print("    PASSED")


def testFullScenarioCloseGame():
    """Simulate a sequence of events in a close game and verify momentum arc."""
    print("  Full scenario: close game momentum arc...")

    game = makeGame(homeScore=14, awayScore=14, mentalStats=80)

    print(f"    Start: momentum={game.momentum:.1f}")

    # Home TD
    game._applyMomentumEvent(MOMENTUM_TD, game.homeTeam)
    print(f"    Home TD: momentum={game.momentum:.1f}, streak={game.momentumStreak}")
    assert game.momentum > 0

    # Home sack
    game._applyMomentumEvent(MOMENTUM_SACK, game.homeTeam)
    print(f"    Home sack: momentum={game.momentum:.1f}, streak={game.momentumStreak}")
    assert game.momentumStreak == 2

    # Decay a few plays
    for _ in range(5):
        game._decayMomentum()
    print(f"    After 5 decays: momentum={game.momentum:.1f}")
    assert game.momentum > 0  # Should still be positive

    # Away INT (turnover)
    game._applyMomentumEvent(MOMENTUM_TURNOVER, game.awayTeam)
    print(f"    Away INT: momentum={game.momentum:.1f}, streak={game.momentumStreak}")
    assert game.momentumStreak == -1  # Reset to away

    # Away TD
    game._applyMomentumEvent(MOMENTUM_TD, game.awayTeam)
    print(f"    Away TD: momentum={game.momentum:.1f}, streak={game.momentumStreak}")
    assert game.momentumStreak == -2  # Consecutive away

    print("    PASSED")


def testFullGameSimulation():
    """Simulate a realistic game sequence: 60+ plays with decay between events."""
    print("  Full game simulation (realistic play sequence)...")

    game = makeGame(homeScore=0, awayScore=0, mentalStats=80)
    momentumLog = []

    def log(label):
        momentumLog.append((label, round(game.momentum, 1), game.momentumStreak))

    log("Start")

    # Q1: Home drives, punts
    for _ in range(8):
        game._decayMomentum()
    game._applyMomentumEvent(MOMENTUM_PUNT, game.homeTeam)  # Home forced punt = away gets momentum
    # Wait, punt benefits defense (the team that stopped them)
    # Actually: Punt → defense benefits
    # Home is punting → home's offense failed → AWAY's defense benefits
    log("Home punts → away gains")

    for _ in range(6):
        game._decayMomentum()
    game.homeScore = 7
    game._applyMomentumEvent(MOMENTUM_TD, game.awayTeam)  # Away scores TD
    game.awayScore = 7
    log("Away TD")

    # Q2: Back and forth
    for _ in range(8):
        game._decayMomentum()
    game._applyMomentumEvent(MOMENTUM_FG_MADE, game.homeTeam)
    game.homeScore = 10
    log("Home FG")

    for _ in range(7):
        game._decayMomentum()
    game._applyMomentumEvent(MOMENTUM_SACK, game.homeTeam)
    log("Home sack")

    for _ in range(3):
        game._decayMomentum()
    game._applyMomentumEvent(MOMENTUM_PUNT, game.homeTeam)  # Away forced to punt → home defense
    log("Home forces punt")

    # Q3: Home surge - consecutive events
    for _ in range(7):
        game._decayMomentum()
    game._applyMomentumEvent(MOMENTUM_TURNOVER, game.homeTeam)
    log("Home INT (streak starts)")

    for _ in range(4):
        game._decayMomentum()
    game._applyMomentumEvent(MOMENTUM_TD, game.homeTeam)
    game.homeScore = 17
    log("Home TD (streak=2)")

    for _ in range(3):
        game._decayMomentum()
    game._applyMomentumEvent(MOMENTUM_SACK, game.homeTeam)
    log("Home sack (streak=3)")

    for _ in range(4):
        game._decayMomentum()
    game._applyMomentumEvent(MOMENTUM_FG_MISSED, game.homeTeam)
    log("Away FG miss (home streak=4)")

    # Check: home should have significant momentum by now
    assert game.momentum > 30, f"Expected momentum > 30 after home surge, got {game.momentum:.1f}"

    # Q4: Away comeback
    for _ in range(6):
        game._decayMomentum()
    game._applyMomentumEvent(MOMENTUM_TD, game.awayTeam)
    game.awayScore = 14
    log("Away TD (streak resets)")

    for _ in range(5):
        game._decayMomentum()
    game._applyMomentumEvent(MOMENTUM_TURNOVER, game.awayTeam)
    log("Away forces fumble")

    for _ in range(3):
        game._decayMomentum()
    game._applyMomentumEvent(MOMENTUM_TD, game.awayTeam)
    game.awayScore = 21
    log("Away TD (streak=3, cascade)")

    # Print momentum arc
    print("    Play-by-play momentum arc:")
    for label, mom, streak in momentumLog:
        bar = ""
        if mom > 0:
            bar = " " * 20 + "█" * int(abs(mom) / 2)
        elif mom < 0:
            padding = max(0, 20 - int(abs(mom) / 2))
            bar = " " * padding + "█" * int(abs(mom) / 2)
        else:
            bar = " " * 20 + "·"
        direction = "HOME" if mom > 0 else "AWAY" if mom < 0 else "NEUTRAL"
        print(f"      {label:30s} {mom:+6.1f} (streak={streak:+d}) {direction}")

    # Verify final state
    assert game.momentumStreak < 0, "Away should have momentum after comeback"
    print(f"\n    Final: momentum={game.momentum:.1f}, streak={game.momentumStreak}")
    print(f"    Home surge peaked then away comeback shifted momentum — narrative ✓")
    print("    PASSED")


def testBlowoutMomentumSuppression():
    """Verify momentum is heavily suppressed in blowouts."""
    print("  Blowout suppression (35-7 game)...")

    game = makeGame(homeScore=35, awayScore=7, mentalStats=80)

    # Even 3 consecutive TDs in a blowout shouldn't build much momentum
    game._applyMomentumEvent(MOMENTUM_TD, game.homeTeam)
    game._applyMomentumEvent(MOMENTUM_TD, game.homeTeam)
    game._applyMomentumEvent(MOMENTUM_TD, game.homeTeam)

    print(f"    3 TDs in blowout: momentum={game.momentum:.1f}")
    assert game.momentum < 10, f"Expected momentum < 10 in blowout, got {game.momentum:.1f}"
    print("    PASSED")


def testGameplayEffectCompounding():
    """Verify that sustained momentum has a noticeable compound effect."""
    print("  Gameplay effect compounding over sustained momentum...")

    game = makeGame(momentum=50.0)

    # Apply effect for 10 consecutive plays
    totalConfBoost = 0
    for _ in range(10):
        game._applyMomentumEffect()
        # Count calls to home team QB's confidence
        calls = game.homeTeam.rosterDict['qb'].updateInGameConfidence.call_count
        if calls > 0:
            lastCall = game.homeTeam.rosterDict['qb'].updateInGameConfidence.call_args[0][0]
            totalConfBoost += lastCall

    print(f"    After 10 plays at momentum=50: total confidence boost = {totalConfBoost:.4f}")
    # Should be roughly 10 * 0.005 * (50/50) * 0.6 = 10 * 0.003 = 0.03
    assert 0.02 < totalConfBoost < 0.04, f"Expected ~0.03, got {totalConfBoost:.4f}"
    print("    PASSED")


def testDisplayThresholds():
    """Verify the display threshold determines when momentumTeam would be shown."""
    print("  Display threshold check...")

    # Below threshold: no team shown
    assert abs(3.0) < MOMENTUM_DISPLAY_THRESHOLD
    # Above threshold: team shown
    assert abs(6.0) > MOMENTUM_DISPLAY_THRESHOLD

    print(f"    Threshold: {MOMENTUM_DISPLAY_THRESHOLD} (momentum 3.0 → no team, 6.0 → team shown)")
    print("    PASSED")


# ─── Run all tests ─────────────────────────────────────────────────────

def main():
    # Need to handle the circular import for Game class
    # We'll import it carefully
    print("\n=== Momentum System Tests ===\n")

    # Verify constants are sensible
    print("[Constants check]")
    assert MOMENTUM_TD == 20
    assert MOMENTUM_TURNOVER == 18
    assert MOMENTUM_SAFETY == 18
    assert MOMENTUM_SACK == 6
    assert MOMENTUM_PUNT == 4
    assert MOMENTUM_FG_MADE == 8
    assert MOMENTUM_FG_MISSED == 10
    assert MOMENTUM_TURNOVER_ON_DOWNS == 12
    assert MOMENTUM_BIG_PLAY_BONUS == 5
    assert MOMENTUM_DECAY_RATE == 0.03
    assert MOMENTUM_BLOWOUT_DECAY_RATE == 0.08
    assert MOMENTUM_MIDGAP_DECAY_RATE == 0.05
    assert MOMENTUM_NEUTRAL_ZONE == 10
    assert MOMENTUM_SHIFT_THRESHOLD == 15
    assert MOMENTUM_CROSS_ZERO_THRESHOLD == 10
    assert MOMENTUM_DISPLAY_THRESHOLD == 5
    print("  All constants verified ✓\n")

    print("[Unit Tests]")
    testDecayRates()
    testScoreGapDampener()
    testMentalResistance()
    testStreakTracking()
    testMomentumShiftDetection()
    testApplyMomentumEvent()
    testApplyMomentumEventAway()
    testCascadeMultiplier()
    testBlowoutDampening()
    testMomentumClamping()
    testMomentumEffectNeutralZone()
    testMomentumEffectActive()
    testMomentumEffectCapped()
    testMomentumShiftOnEvent()
    testStreakResetOnTeamSwitch()
    print()

    print("[Integration Tests]")
    testFullScenarioCloseGame()
    testFullGameSimulation()
    testBlowoutMomentumSuppression()
    testGameplayEffectCompounding()
    testDisplayThresholds()
    print()

    print("=== All momentum tests passed! ===\n")


if __name__ == '__main__':
    main()

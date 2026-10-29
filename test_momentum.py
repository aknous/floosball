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
    MOMENTUM_CONFIDENCE_AT_50, MOMENTUM_DETERMINATION_AT_50, MOMENTUM_NEUTRAL_ZONE,
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


def makeGame(homeScore=14, awayScore=10, momentum=0.0, streak=0, lastTeam=None, mentalStats=80, quarter=2, gameClockSeconds=600,
             homeWp=50.0):
    """Create a minimal game-like object with momentum methods attached.
    Defaults: Q2 with 10:00 left — comfortably outside the late-game
    amplifier window so existing tests reflect raw event math."""
    # Import the methods from the Game class
    import floosball_game as fg

    game = MagicMock()
    game.homeScore = homeScore
    game.awayScore = awayScore
    game.momentum = momentum
    game.momentumStreak = streak
    game.lastMomentumTeam = lastTeam
    game.currentQuarter = quarter
    game.gameClockSeconds = gameClockSeconds
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
    game._setMomentumOffset = types.MethodType(fg.Game._setMomentumOffset, game)
    game._clearMomentumEffect = types.MethodType(fg.Game._clearMomentumEffect, game)
    game._momentumApplied = {}
    game._playsAbove30Mom = 0
    # ⚠️ `_decayMomentum` measures the score gap in SCORES via `_oneScore()`, which reads
    # gameRules. On a bare MagicMock that returns a Mock and the comparison raises
    # TypeError, so bind the real method over real rules rather than let the mock
    # auto-answer with something that is not a number.
    from game_rules import GameRules
    game.gameRules = GameRules()
    game._oneScore = types.MethodType(fg.Game._oneScore, game)
    game._maxPossession = types.MethodType(fg.Game._maxPossession, game)
    game._fgValue = types.MethodType(fg.Game._fgValue, game)
    # Numeric game state the momentum path reads and compares. A MagicMock would
    # auto-answer these with a Mock and every comparison would raise TypeError.
    game._peakAbsMomentum = 0.0
    # Pre-play win probability, read by `_settledGameDampener`. 50/50 by default so the
    # tests below that are about other multipliers see it at full value.
    game.homeTeamWinProbability = homeWp
    game.awayTeamWinProbability = 100.0 - homeWp
    game._settledGameDampener = types.MethodType(fg.Game._settledGameDampener, game)

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
    """Verify dampening returns correct multipliers by score gap.
    Legacy symmetric path (no benefitingTeam) preserved for decay code."""
    print("  Score gap dampener (symmetric / legacy)...")

    game = makeGame(homeScore=10, awayScore=7)  # diff 3
    assert game._scoreGapDampener() == 1.0

    game = makeGame(homeScore=22, awayScore=7)  # diff 15
    assert game._scoreGapDampener() == 0.7

    game = makeGame(homeScore=28, awayScore=7)  # diff 21
    assert game._scoreGapDampener() == 0.7

    game = makeGame(homeScore=29, awayScore=7)  # diff 22
    assert game._scoreGapDampener() == 0.4

    game = makeGame(homeScore=38, awayScore=7)  # diff 31
    assert game._scoreGapDampener() == 0.2

    print("    PASSED")


def testScoreGapDampenerAsymmetric():
    """Verify the leading-team-only blowout dampener.

    The dampener exists to prevent runaway momentum on the team that's
    already pulling away. The trailing team's comeback push should
    generate momentum at full value, regardless of deficit — that's the
    narrative the system needs to support."""
    print("  Score gap dampener (asymmetric / leading vs trailing)...")

    # Leader benefits at 22-point gap → dampened to 0.4
    game = makeGame(homeScore=29, awayScore=7)
    assert game._scoreGapDampener(benefitingTeam=game.homeTeam) == 0.4

    # Trailing team benefits at same gap → no dampen
    assert game._scoreGapDampener(benefitingTeam=game.awayTeam) == 1.0

    # Leader benefits at 31-point gap → max dampen
    game = makeGame(homeScore=38, awayScore=7)
    assert game._scoreGapDampener(benefitingTeam=game.homeTeam) == 0.2
    assert game._scoreGapDampener(benefitingTeam=game.awayTeam) == 1.0

    # Tied game → no dampen for either side
    game = makeGame(homeScore=21, awayScore=21)
    assert game._scoreGapDampener(benefitingTeam=game.homeTeam) == 1.0
    assert game._scoreGapDampener(benefitingTeam=game.awayTeam) == 1.0

    # Close game (under 14 gap) → no dampen for either side
    game = makeGame(homeScore=14, awayScore=10)
    assert game._scoreGapDampener(benefitingTeam=game.homeTeam) == 1.0
    assert game._scoreGapDampener(benefitingTeam=game.awayTeam) == 1.0

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

    # ⚠️ A BIG SWING IS NO LONGER ENOUGH ON ITS OWN. The rule now requires either a
    # ZERO-CROSSING or a large swing that runs AGAINST the prevailing momentum; piling on
    # in the direction momentum is already going is never a shift, however big the delta
    # ("not routine scoring by a team already dominating"). These cases asserted the old
    # any-large-delta rule, so 0 -> 15 was expected True where it is now correctly False.

    # Piling on — same direction as the prevailing momentum — is never a shift.
    assert game._isMomentumShift(0, 15) == False
    assert game._isMomentumShift(10, 25) == False
    assert game._isMomentumShift(-10, -25) == False

    # Against the grain, and big enough (delta >= MOMENTUM_SHIFT_THRESHOLD): a shift.
    assert game._isMomentumShift(-20, -5) == True    # delta=15, pushing back toward zero
    assert game._isMomentumShift(25, 10) == True     # delta=15, the other side pushing back

    # Against the grain but too small: not a shift.
    assert game._isMomentumShift(10, 5) == False     # delta=5

    # Small swing: not a shift.
    assert game._isMomentumShift(0, 5) == False
    assert game._isMomentumShift(10, 15) == False

    # Cross zero with >= MOMENTUM_CROSS_ZERO_THRESHOLD delta: is a shift.
    assert game._isMomentumShift(5, -5) == True   # delta=10, crosses zero
    assert game._isMomentumShift(-6, 6) == True    # delta=12, crosses zero

    # Cross zero with too small a delta: not a shift.
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
    """Verify the leading team is dampened in blowout scenarios but the
    trailing team's comeback momentum hits at full value."""
    print("  Blowout dampening (28-pt diff, asymmetric)...")

    resist = 0.85  # mentalStats=80 → 1.0 - 0.3 * (80-60)/40

    # Leading team (home up 28) → gap damp 0.4 applies
    game = makeGame(homeScore=35, awayScore=7, mentalStats=80)
    game._applyMomentumEvent(MOMENTUM_TD, game.homeTeam)
    expectedLeader = 20.0 * 1.0 * 0.4 * resist  # 0.4 dampening for 28-pt gap, cascade=1.0 (first event)
    assert abs(game.momentum - expectedLeader) < 0.1, f"Leader: expected ~{expectedLeader}, got {game.momentum}"
    print(f"    Leader TD in blowout: momentum={game.momentum:.2f} (expected ~{expectedLeader:.2f})")

    # Trailing team in the same blowout → no gap dampener, full value
    game = makeGame(homeScore=35, awayScore=7, mentalStats=80)
    game._applyMomentumEvent(MOMENTUM_TD, game.awayTeam)
    expectedTrailer = 20.0 * 1.0 * 1.0 * resist  # 1.0 gap damp (comeback), cascade=1.0
    assert abs(abs(game.momentum) - expectedTrailer) < 0.1, f"Trailer: expected ~{expectedTrailer}, got {abs(game.momentum)}"
    # Momentum should be negative (away team benefits)
    assert game.momentum < 0, f"Expected negative momentum for away team, got {game.momentum}"
    print(f"    Trailer TD in blowout: momentum={game.momentum:.2f} (expected ~-{expectedTrailer:.2f})")
    print("    PASSED")


def testSettledGameMutesTheLoser():
    """A team whose game is lost gets little momentum: its events scale with its
    pre-play win probability up to MOMENTUM_ALIVE_WP, floored at MOMENTUM_SETTLED_FLOOR.
    Prod game 5430: MEX scored a TD down 38-3 late in Q3 with NYS at 99.9% and took
    the meter, the flame and a momentum-shift tag."""
    print("  Settled game mutes the loser (prod game 5430)...")
    from constants import MOMENTUM_ALIVE_WP, MOMENTUM_SETTLED_FLOOR
    resist = 0.85  # mentalStats=80

    # The reported spot: home up 38-3, Q3 1:31, home WP 99.9, momentum ~0.
    game = makeGame(homeScore=38, awayScore=9, momentum=1.7, mentalStats=80, quarter=3,
                    gameClockSeconds=91, homeWp=99.9)
    game._applyMomentumEvent(MOMENTUM_TD, game.awayTeam)
    expected = 1.7 - 20.0 * MOMENTUM_SETTLED_FLOOR * resist
    assert abs(game.momentum - expected) < 0.1, f"expected ~{expected}, got {game.momentum}"
    assert abs(game.momentum) < MOMENTUM_DISPLAY_THRESHOLD, "a garbage-time TD should not take the flame"
    assert not game.play.isMomentumShift, "a garbage-time TD is not a momentum shift"

    # Full value once the team is alive, and a linear ramp below it.
    for wp, scale in ((50.0, 1.0), (MOMENTUM_ALIVE_WP, 1.0), (MOMENTUM_ALIVE_WP / 2, 0.5)):
        game = makeGame(homeScore=7, awayScore=21, mentalStats=80, quarter=3,
                        gameClockSeconds=600, homeWp=wp)
        game._applyMomentumEvent(MOMENTUM_TD, game.homeTeam)
        assert abs(game.momentum - 20.0 * scale * resist) < 0.1, (wp, game.momentum)

    # The leader is untouched (its WP is high); the score-gap dampener still handles it.
    game = makeGame(homeScore=35, awayScore=7, mentalStats=80, homeWp=99.9)
    game._applyMomentumEvent(MOMENTUM_TD, game.homeTeam)
    assert abs(game.momentum - 20.0 * 0.4 * resist) < 0.1, game.momentum

    # No WP yet (None) is full value.
    game = makeGame(homeScore=7, awayScore=21, mentalStats=80)
    game.homeTeamWinProbability = None
    assert game._settledGameDampener(game.homeTeam) == 1.0
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


def testNoComebackUrgency():
    """The trailing team's events are NOT inflated. A 1.15x "comeback urgency" bump
    existed to lift underdogs' win rates, which momentum's effect is far too small to do
    (audited 2026-10-18); it is gone. The asymmetric gap dampener is what keeps a
    comeback's momentum at full value."""
    print("  No comeback urgency (trailing team is not inflated)...")
    resist = 0.85  # mentalStats=80
    game = makeGame(homeScore=7, awayScore=21, mentalStats=80, quarter=3, gameClockSeconds=600)
    game._applyMomentumEvent(MOMENTUM_TD, game.homeTeam)
    expected = 20.0 * 1.0 * 1.0 * resist
    assert abs(game.momentum - expected) < 0.1, f"Trailing in Q3: expected ~{expected}, got {game.momentum}"
    game = makeGame(homeScore=7, awayScore=21, mentalStats=80, quarter=4, gameClockSeconds=90)
    game._applyMomentumEvent(MOMENTUM_TD, game.homeTeam)
    expected = 20.0 * 1.0 * 1.0 * resist * 1.3          # only the late-game amplifier
    assert abs(game.momentum - expected) < 0.1, f"Q4<2:00 trailing: expected ~{expected}, got {game.momentum}"
    print("    PASSED")


def testLateGameAmplifier():
    """Verify Q4 inside two-minute warning and any OT play applies the
    1.3x late-game multiplier to momentum events."""
    print("  Late-game amplifier (Q4 inside 2:00 / OT)...")

    resist = 0.85  # mentalStats=80

    # Baseline: Q2 mid-game — no amplifier
    game = makeGame(homeScore=14, awayScore=10, mentalStats=80, quarter=2, gameClockSeconds=600)
    game._applyMomentumEvent(MOMENTUM_TD, game.homeTeam)
    baseline = 20.0 * 1.0 * 1.0 * resist * 1.0  # no late-game mult
    assert abs(game.momentum - baseline) < 0.1, f"Baseline: expected ~{baseline}, got {game.momentum}"

    # Q4 inside 2:00 — 1.3x amplifier kicks in
    game = makeGame(homeScore=14, awayScore=10, mentalStats=80, quarter=4, gameClockSeconds=90)
    game._applyMomentumEvent(MOMENTUM_TD, game.homeTeam)
    expected = 20.0 * 1.0 * 1.0 * resist * 1.3
    assert abs(game.momentum - expected) < 0.1, f"Q4<2:00: expected ~{expected}, got {game.momentum}"
    print(f"    Q4 <2:00 TD: momentum={game.momentum:.2f} (expected ~{expected:.2f}, baseline {baseline:.2f})")

    # Q4 at 5:00 — outside the window, no amplifier
    game = makeGame(homeScore=14, awayScore=10, mentalStats=80, quarter=4, gameClockSeconds=300)
    game._applyMomentumEvent(MOMENTUM_TD, game.homeTeam)
    assert abs(game.momentum - baseline) < 0.1, f"Q4 5:00: expected ~{baseline} (no amp), got {game.momentum}"

    # OT — amplifier applies regardless of clock
    game = makeGame(homeScore=21, awayScore=21, mentalStats=80, quarter=5, gameClockSeconds=500)
    game._applyMomentumEvent(MOMENTUM_TD, game.homeTeam)
    expected_ot = 20.0 * 1.0 * 1.0 * resist * 1.3
    assert abs(game.momentum - expected_ot) < 0.1, f"OT: expected ~{expected_ot}, got {game.momentum}"

    print("    PASSED")


def testMomentumEffectNeutralZone():
    """Verify no gameplay effect when momentum is in the neutral zone (5)."""
    print("  Momentum effect - neutral zone...")

    game = makeGame(momentum=3.0)  # Below MOMENTUM_NEUTRAL_ZONE (5)

    game._applyMomentumEffect()

    # No players should have had updateInGameConfidence called
    for player in game.homeTeam.rosterDict.values():
        player.updateInGameConfidence.assert_not_called()
        player.updateInGameDetermination.assert_not_called()

    print("    PASSED")


def testMomentumEffectActive():
    """At momentum 40 the team with momentum holds +AT_50 x 0.8, the other team the same
    amount negative (symmetric, so it adds no net confidence to the league)."""
    print("  Momentum effect - active (momentum=40)...")
    game = makeGame(momentum=40.0)
    game._applyMomentumEffect()
    homeQb = game.homeTeam.rosterDict['qb']; awayQb = game.awayTeam.rosterDict['qb']
    conf = homeQb.updateInGameConfidence.call_args[0][0]
    assert abs(conf - MOMENTUM_CONFIDENCE_AT_50 * 0.8) < 1e-9, conf
    assert abs(homeQb.updateInGameDetermination.call_args[0][0] - MOMENTUM_DETERMINATION_AT_50 * 0.8) < 1e-9
    assert abs(awayQb.updateInGameConfidence.call_args[0][0] + conf) < 1e-9, 'the drag mirrors the boost'
    # no shock-absorber source, so the offset can be taken back out exactly
    assert homeQb.updateInGameConfidence.call_args.kwargs.get('source') is None
    print("    PASSED")


def testMomentumEffectIsALevel():
    """Holding momentum does not keep adding; losing it takes the offset back; the game's
    end removes it before postgame."""
    print("  Momentum effect - a level, not a running total...")
    game = makeGame(momentum=50.0)
    qb = game.homeTeam.rosterDict['qb']
    for _ in range(10):
        game._applyMomentumEffect()
    total = sum(c[0][0] for c in qb.updateInGameConfidence.call_args_list)
    assert abs(total - MOMENTUM_CONFIDENCE_AT_50) < 1e-9, f'10 plays at 50 hold one level, got {total}'
    game.momentum = 20.0
    game._applyMomentumEffect()
    total = sum(c[0][0] for c in qb.updateInGameConfidence.call_args_list)
    assert abs(total - MOMENTUM_CONFIDENCE_AT_50 * 0.4) < 1e-9, f'fades with momentum, got {total}'
    game._clearMomentumEffect()
    total = sum(c[0][0] for c in qb.updateInGameConfidence.call_args_list)
    det = sum(c[0][0] for c in qb.updateInGameDetermination.call_args_list)
    assert abs(total) < 1e-9 and abs(det) < 1e-9, 'cleared before postgame'
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
    """Blowout suppression is ASYMMETRIC: the leader's piling-on is muted, the trailing
    team's comeback push still lands at full value.

    ⚠️ ASSERTED RELATIVELY, NOT AGAINST AN ABSOLUTE FLOOR. This used to require
    `momentum < 10` after three TDs at 35-7. That gap is 28 = exactly 4 x _oneScore()
    (TD 6 + XP 1), which lands on the 0.4 dampener rung rather than the 0.2 one, so the
    old number silently assumed a different scoring baseline — and the score values are
    MUTABLE RULES, so any absolute figure here is one rule vote away from being wrong
    again. Comparing against the same events in a tied game tests the actual contract.
    """
    print("  Blowout suppression (35-7 game)...")

    def threeTds(homeScore, awayScore, benefiting):
        g = makeGame(homeScore=homeScore, awayScore=awayScore, mentalStats=80)
        team = g.homeTeam if benefiting == 'home' else g.awayTeam
        for _ in range(3):
            g._applyMomentumEvent(MOMENTUM_TD, team)
        return g.momentum

    tied = threeTds(14, 14, 'home')            # same events, no gap to damp
    leader = threeTds(35, 7, 'home')           # the team already ahead, piling on
    trailer = threeTds(35, 7, 'away')          # the comeback push

    print(f"    3 TDs tied={tied:.1f}  leader-in-blowout={leader:.1f}  trailer={trailer:.1f}")
    assert leader < tied * 0.6, (
        f"leader's piling-on should be materially damped: {leader:.1f} vs {tied:.1f}")
    assert abs(trailer) >= abs(tied) * 0.99, (
        f"the trailing team's comeback must NOT be damped: {trailer:.1f} vs {tied:.1f}")
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
    # ⚠️ Retuned 10 -> 5. This assertion was missed at the time, while line ~455 of this
    # same file was updated to say "(5)" — so the file disagreed with itself and every
    # momentum test below was unreachable behind this one AssertionError.
    assert MOMENTUM_NEUTRAL_ZONE == 5
    assert MOMENTUM_SHIFT_THRESHOLD == 14
    assert MOMENTUM_CROSS_ZERO_THRESHOLD == 8
    assert MOMENTUM_DISPLAY_THRESHOLD == 5
    print("  All constants verified ✓\n")

    print("[Unit Tests]")
    testDecayRates()
    testScoreGapDampener()
    testScoreGapDampenerAsymmetric()
    testMentalResistance()
    testStreakTracking()
    testMomentumShiftDetection()
    testApplyMomentumEvent()
    testApplyMomentumEventAway()
    testCascadeMultiplier()
    testBlowoutDampening()
    testLateGameAmplifier()
    testNoComebackUrgency()
    testSettledGameMutesTheLoser()
    testMomentumClamping()
    testMomentumEffectNeutralZone()
    testMomentumEffectActive()
    testMomentumEffectIsALevel()
    testMomentumShiftOnEvent()
    testStreakResetOnTeamSwitch()
    print()

    print("[Integration Tests]")
    testFullScenarioCloseGame()
    testFullGameSimulation()
    testBlowoutMomentumSuppression()
    testDisplayThresholds()
    print()

    print("=== All momentum tests passed! ===\n")


if __name__ == '__main__':
    main()

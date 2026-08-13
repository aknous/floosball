"""A cut must be a bet the club can actually WIN — not a bet on one player.

⚠️ THE BUG THIS EXISTS TO PREVENT. The cut decision used to price ONE free agent
(`bestReplacementValue`, the pickDepth-th best) and cut if that player beat the
incumbent by FO_CUT_UPGRADE_MARGIN. Measured over 3 simulated seasons and 51
cuts, the club then signed that exact player **8% of the time** — 92% were taken
by somebody else, because deciding and acquiring are separate phases with a
worst-first draft between them and `_leftThisTeamThisOffseason` blocks a club
from re-signing its own cut player, so a correct decision had no fallback.

The result: cut outcomes were a coin flip (44% better / 46% worse, mean -1.1
rating points) **regardless of how good the valuation was**. Correcting the
valuation's winner's curse cut volume 66 -> 50 and moved the hit rate not at all,
which is what proved the estimate was never the binding constraint.

A club does not need the man it wants. It needs someone better than the man it
has. So the gate is now P(at least one upgrade survives to my pick).

Run: .venv/bin/python test_upgrade_confidence.py
"""

import logging

logging.disable(logging.CRITICAL)

from managers.frontOfficeBrain import FrontOfficeBrain, _atLeastOneSurvives
from constants import (FO_CUT_UPGRADE_MARGIN, FO_CUT_MIN_CONFIDENCE,
                       FO_FA_CONTENTION)
from floosball_player import Position
from test_front_office_brain import FakePlayer, FakeCoach, FakePlayerManager


# ------------------------------------------------------- the survival maths

def test_no_one_picks_ahead_means_certainty():
    """With nobody on the clock before you, whatever exists is yours."""
    assert _atLeastOneSurvives(1, 0, FO_FA_CONTENTION) == 1.0
    print("PASS an unopposed club is certain of its pick")


def test_chasing_only_the_top_of_the_board_is_near_hopeless():
    """⚠️ THE MEASURED FAILURE. When the only player who beats your incumbent is
    the best free agent available, 31 clubs pick before you and he is gone."""
    p = _atLeastOneSurvives(1, 31, FO_FA_CONTENTION)
    assert p < 0.05, p
    print(f"PASS chasing one player from last in line is hopeless ({p:.1%})")


def test_more_upgrades_than_picks_is_certainty():
    """You cannot lose them all if there aren't enough picks to take them."""
    assert _atLeastOneSurvives(40, 31, FO_FA_CONTENTION) == 1.0
    print("PASS a pool deeper than the draft cannot be exhausted")


def test_nothing_better_is_zero_not_a_gamble():
    """No upgrade exists, so there is no move to make — distinct from 'unlikely'."""
    assert _atLeastOneSurvives(0, 10, FO_FA_CONTENTION) == 0.0
    print("PASS no upgrade in the pool reads as zero, not as a long shot")


def test_confidence_rises_with_the_number_of_upgrades():
    prev = -1.0
    for upgrades in (1, 3, 6, 10, 20):
        p = _atLeastOneSurvives(upgrades, 31, FO_FA_CONTENTION)
        assert p >= prev, (upgrades, p, prev)
        prev = p
    print("PASS the more players beat your man, the safer the cut")


def test_confidence_falls_as_more_clubs_pick_first():
    prev = 2.0
    for ahead in (0, 5, 12, 20, 31):
        p = _atLeastOneSurvives(5, ahead, FO_FA_CONTENTION)
        assert p <= prev, (ahead, p, prev)
        prev = p
    print("PASS a later slot is less sure of the same market")


# ------------------------------------------------------ the brain's read

def _pool(count, rating, position=Position.QB):
    return [FakePlayer(f"FA{i}", rating, position=position) for i in range(count)]


def test_a_poor_starter_can_be_cut_confidently():
    """The behavior that should FALL OUT rather than be scripted: when much of
    the market beats your man, a run on the position cannot take all of it."""
    incumbent = FakePlayer("Weak", 55)
    pool = _pool(25, 80)
    brain = FrontOfficeBrain(FakePlayerManager(freeAgents=pool))
    c = brain.upgradeConfidence(incumbent, coach=FakeCoach(scouting=100),
                                teamsAhead=31)
    assert c >= FO_CUT_MIN_CONFIDENCE, c
    print(f"PASS a poor starter is safe to cut ({c:.0%} confident)")


def test_a_good_starter_cannot_be_cut_confidently():
    """Only the very top of the board beats him, and the top always goes."""
    incumbent = FakePlayer("Solid", 88)
    pool = _pool(24, 70) + [FakePlayer("Star", 96)]
    brain = FrontOfficeBrain(FakePlayerManager(freeAgents=pool))
    c = brain.upgradeConfidence(incumbent, coach=FakeCoach(scouting=100),
                                teamsAhead=31)
    assert c < FO_CUT_MIN_CONFIDENCE, c
    print(f"PASS a good starter is not cuttable from the back of the queue ({c:.0%})")


def test_the_same_good_starter_is_cuttable_when_picking_first():
    """Same club, same market — only the draft slot changes. This is the half
    of the decision the old point estimate could not express."""
    incumbent = FakePlayer("Solid", 88)
    pool = _pool(24, 70) + [FakePlayer("Star", 96)]
    brain = FrontOfficeBrain(FakePlayerManager(freeAgents=pool))
    c = brain.upgradeConfidence(incumbent, coach=FakeCoach(scouting=100),
                                teamsAhead=0)
    assert c == 1.0, c
    print("PASS picking first, the same cut becomes a certainty")


def test_a_retiring_free_agent_is_not_an_upgrade():
    incumbent = FakePlayer("Weak", 55)
    pool = [FakePlayer(f"Done{i}", 90, willRetire=True) for i in range(20)]
    brain = FrontOfficeBrain(FakePlayerManager(freeAgents=pool))
    assert brain.upgradeConfidence(incumbent, coach=FakeCoach(),
                                   teamsAhead=0) == 0.0
    print("PASS a market of retirees offers no upgrade")


def test_only_the_same_position_counts():
    incumbent = FakePlayer("Weak", 55, position=Position.QB)
    pool = _pool(25, 90, position=Position.RB)
    brain = FrontOfficeBrain(FakePlayerManager(freeAgents=pool))
    assert brain.upgradeConfidence(incumbent, coach=FakeCoach(),
                                   teamsAhead=0) == 0.0
    print("PASS running backs are not quarterback upgrades")


# ------------------------------------------------------------- the gate

def test_the_gate_blocks_a_cut_that_clears_the_margin_but_not_the_odds():
    """⚠️ THE REGRESSION, end to end. The margin says the move is worth making;
    confidence says it is likely to survive contact with the draft. Clearing the
    first alone is exactly what produced a coin flip in the sim."""
    incumbent = FakePlayer("Solid", 88)
    incumbent.termRemaining = 3          # under contract, so cuttable at all
    pool = _pool(24, 70) + [FakePlayer("Star", 99)]
    brain = FrontOfficeBrain(FakePlayerManager(freeAgents=pool))

    class Team:
        id = 1
        name = 'Test'
        rosterDict = {'qb': incumbent}

    sharp = FakeCoach(scouting=100)
    # The margin IS cleared — the star is far enough ahead to qualify.
    star = brain.decisionValue(FakePlayer("Star", 99), sharp)
    assert star - brain.decisionValue(incumbent, sharp) >= FO_CUT_UPGRADE_MARGIN

    assert brain.chooseCuts(Team(), coach=sharp, teamsAhead=31) == [], \
        "a cut resting on one player nobody survives to sign must not fire"
    assert len(brain.chooseCuts(Team(), coach=sharp, teamsAhead=0)) == 1, \
        "picking first, the same cut is a real opportunity"
    print("PASS the gate separates 'worth doing' from 'likely to work'")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for fn in tests:
        fn()
    print(f"\nAll {len(tests)} upgrade-confidence tests passed.")

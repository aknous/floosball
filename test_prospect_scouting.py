"""The scouted view of a draft prospect — `prospect_scouting`.

A prospect must not show his true numbers. The uncertainty IS the feature: it is what
makes a pick worth arguing about, what gives the Scouting Department a job, and what
makes trading a pick a real decision rather than an arithmetic one.

See docs/PROSPECT_DRAFT_PLAN.md §1b.
"""

import subprocess
import sys

import prospect_scouting as ps
from constants import (SCOUTING_BANDS, SCOUT_BAND_EARLY, SCOUT_BAND_LATE,
                       FO_SCOUT_VISION_FLOOR, FO_SCOUT_VISION_CEILING, GM_ACTIVE_WEEK)


def _visionFor(accuracy):
    """Invert `scoutingVision`'s normalisation, so a test can name an accuracy tier."""
    return (accuracy - FO_SCOUT_VISION_FLOOR) / (FO_SCOUT_VISION_CEILING - FO_SCOUT_VISION_FLOOR)


TEN_POINT_TIER = _visionFor(70)     # the ±10 band the plan's worked table uses


class FakeProspect:
    def __init__(self, pid, rating, ceiling):
        self.id = pid
        self.playerRating = rating
        self._ceiling = ceiling

    def computeCeilingRating(self):
        return self._ceiling


# ------------------------------------------------------- the band table

def test_band_follows_the_scouting_tiers():
    """`SCOUTING_BANDS` is keyed on the 60-100 ATTRIBUTE scale while `scoutingVision`
    returns 0..1 — the two have to be reconciled in ONE place or every call site
    reconciles them differently."""
    assert ps.bandFor(_visionFor(96)) == 0        # elite: the exact number
    assert ps.bandFor(_visionFor(85)) == 5
    assert ps.bandFor(_visionFor(70)) == 10
    assert ps.bandFor(_visionFor(60)) == 15
    print("PASS band tiers: 0 / 5 / 10 / 15")


def test_the_plans_worked_table_reproduces():
    """±14 / ±10.7 / ±7.3 / ±4 at weeks 1 / 8 / 15 / 22 on the ±10 tier."""
    got = [round(ps.bandWidth(TEN_POINT_TIER, wk), 1) for wk in (1, 8, 15, 22)]
    assert got == [14.0, 10.7, 7.3, 4.0], got
    print(f"PASS worked table reproduces: {got}")


def test_the_ramp_ends_at_the_trade_deadline():
    """⚠️ AT `GM_ACTIVE_WEEK`, NOT WEEK 28, and the difference is the whole reason the
    ramp exists: a pick traded in week 3 is speculation on a blurry class and the same
    pick at week 22 is a priced asset both clubs can see. Anchored four weeks later, the
    band would still be ±6.2 at the deadline — after which nobody can act on it."""
    assert ps.seasonProgress(GM_ACTIVE_WEEK) == 1.0
    assert ps.bandWidth(TEN_POINT_TIER, GM_ACTIVE_WEEK) == 10 * SCOUT_BAND_LATE
    print(f"PASS the band is fully sharpened at week {GM_ACTIVE_WEEK}")


def test_the_band_only_ever_narrows():
    """Monotone, so a club's read never gets vaguer as it watches more football."""
    widths = [ps.bandWidth(TEN_POINT_TIER, wk) for wk in range(1, 33)]
    assert all(b >= a - 1e-9 for a, b in zip(widths[1:], widths)), widths
    assert widths[0] > widths[-1]
    print("PASS the band never widens")


def test_the_playoffs_and_offseason_do_not_un_sharpen_it():
    """Both sit past the deadline, and a club that has watched a prospect all year does
    not un-learn him."""
    late = ps.bandWidth(TEN_POINT_TIER, GM_ACTIVE_WEEK)
    for wk in (28, 32, 40, 0, -3):
        assert ps.bandWidth(TEN_POINT_TIER, wk) in (late, ps.bandWidth(TEN_POINT_TIER, 1))
    assert ps.bandWidth(TEN_POINT_TIER, 32) == late
    print("PASS clamped at both ends")


def test_a_perfect_scout_is_unaffected_by_time():
    """✅ `SCOUTING_BANDS` gives ±0 at accuracy >= 95, and zero times any scale is still
    zero — so an elite scouting operation sees the exact number in week 1 and has
    nothing to gain from waiting. That is the Department's ceiling being worth having."""
    elite = _visionFor(96)
    assert ps.bandWidth(elite, 1) == 0
    assert ps.bandWidth(elite, 22) == 0
    view = ps.scoutedView(FakeProspect(1, 70, 88), 5, 3, elite, 1)
    assert view == {"low": 88, "high": 88, "exact": 88, "band": 0.0}, view
    print("PASS a perfect scout reads the exact number in week 1")


# ------------------------------------------------- the standing opinion

def test_the_opinion_is_held_not_re_rolled():
    """⚠️ A GM WHO OVERRATES A PLAYER MUST OVERRATE HIM CONSISTENTLY — on the board, at
    the pick, and in a trade. Re-rolling makes an opinion a fresh dice throw at every
    question."""
    draws = {ps.standingDraw(5, 123, 3) for _ in range(50)}
    assert len(draws) == 1
    print("PASS one club's opinion of one prospect is a single number")


def test_clubs_disagree():
    """Two clubs looking at the same prospect must see different things, or there is
    nothing to argue about and no reason for a trade to exist."""
    draws = {round(ps.standingDraw(club, 123, 3), 6) for club in range(1, 33)}
    assert len(draws) > 25, len(draws)
    print(f"PASS {len(draws)} distinct opinions across 32 clubs")


def test_the_season_is_in_the_seed():
    """⚠️ ON PURPOSE: a club's read should reset for next year's class, not inherit last
    year's luck."""
    assert ps.standingDraw(5, 123, 3) != ps.standingDraw(5, 123, 4)
    print("PASS a new season is a new read")


def test_the_draw_survives_a_restart():
    """⚠️ NOT THE BUILT-IN `hash()`, WHICH IS PROCESS-RANDOMISED. `PYTHONHASHSEED` is
    random per interpreter for str and bytes, so `Random(hash(seed))` hands every deploy
    a different set of opinions — and a supporter checking the class on Monday and again
    on Thursday would be shown different numbers.

    ⚠️ THIS IS INVISIBLE IN A SINGLE-PROCESS TEST, which is why this one shells out to a
    SEPARATE interpreter rather than calling the function twice."""
    code = ("import prospect_scouting as ps;"
            "print(repr([round(ps.standingDraw(5, 123, 3), 12),"
            "            round(ps.standingDraw(9, 400, 7), 12)]))")
    runs = {subprocess.run([sys.executable, '-c', code], capture_output=True,
                           text=True, cwd='.').stdout.strip() for _ in range(3)}
    assert len(runs) == 1, runs
    inProcess = repr([round(ps.standingDraw(5, 123, 3), 12),
                      round(ps.standingDraw(9, 400, 7), 12)])
    assert runs.pop() == inProcess
    print("PASS opinions are identical across separate interpreters")


# ---------------------------------------------------------- the view

def test_belief_converges_on_the_truth():
    """✅ The BELIEF converges as well as the range, because the error scales with the
    band and the club's draw is fixed. Early it is confidently wrong-ish and openly
    unsure; late it is close and knows it. Nothing ever jumps."""
    truth = 88
    errors = [abs(ps.believedPotential(truth, 5, 123, 3, TEN_POINT_TIER, wk) - truth)
              for wk in (1, 8, 15, 22)]
    assert errors == sorted(errors, reverse=True), errors
    assert errors[-1] < errors[0]
    print(f"PASS error shrinks {errors[0]:.1f} -> {errors[-1]:.1f} over the season")


def test_the_range_usually_contains_the_truth():
    """Each club may be wrong, but its stated range must be HONEST ABOUT HOW WRONG.

    ⚠️ NOT 100%, AND IT SHOULD NOT BE — a scout who is never wrong is not a scout, and a
    range guaranteed to contain the truth would be a guarantee the truth is findable by
    reading enough team pages. What it must not be is the coin-flip it was: drawing the
    error at the FULL band width puts the truth inside `belief ± band` exactly when
    |draw| <= 1, so ONE CLUB IN THREE was shown a range the real number fell outside.
    At half the band it is a ~2-sigma interval."""
    hits = 0
    total = 0
    for club in range(1, 33):
        for wk in (1, 8, 15, 22):
            view = ps.scoutedView(FakeProspect(77, 70, 88), club, 3, TEN_POINT_TIER, wk)
            total += 1
            hits += (view['low'] <= 88 <= view['high'])
    rate = hits / total
    assert rate >= 0.85, f"only {rate:.0%} of stated ranges contain the truth"
    assert rate < 1.0, "a range that is ALWAYS right is not a scouting read"
    print(f"PASS {rate:.0%} of stated ranges contain the truth")


def test_the_ceiling_clamp_is_informative():
    """⚠️ NOT JUST A CORRECTNESS FIX. Near the top of the scale the range goes
    ASYMMETRIC, and that asymmetry is real information — "could be maxed" is exactly the
    signal a scout would have. An elite prospect still LOOKS elite through a wide band,
    which is what makes the top of a class legible to a fan in week 1."""
    saw = False
    for club in range(1, 33):
        view = ps.scoutedView(FakeProspect(77, 83, 97), club, 3, TEN_POINT_TIER, 1)
        # ⚠️ BOTH ends, not just the top. A one-sided clamp printed a low of 106 for a
        # club that rated him a superstar — the repair step for one extreme broke the
        # other, which is why both are now clamped into the same interval.
        assert view['high'] <= ps.RATING_CEILING, view
        assert view['low'] <= ps.RATING_CEILING, view
        assert view['low'] <= view['high'], view
        if view['high'] == ps.RATING_CEILING:
            saw = True
    assert saw, "no club ever reads an elite prospect as possibly maxed"
    print("PASS the range goes asymmetric at the ceiling rather than printing 105")


def test_the_low_end_cannot_go_below_what_he_already_is():
    """Potential is `trueSkill + headroom` and trueSkill is at or above current by
    construction, so a ceiling BELOW his current rating is not an uncertain read — it is
    an impossible one."""
    for club in range(1, 33):
        view = ps.scoutedView(FakeProspect(77, 83, 85), club, 3, _visionFor(60), 1)
        assert view['low'] >= 83, view
    print("PASS the displayed floor is his current rating")


def test_the_view_never_leaks_the_exact_number_to_a_fallible_scout():
    """⚠️ THE BAND IS APPLIED SERVER-SIDE. Sending true potential and hiding it in the UI
    leaks it to anyone who opens the network tab — and potential is the one number this
    whole feature is built on not knowing. `exact` is populated ONLY at ±0."""
    for tier in (60, 70, 85):
        view = ps.scoutedView(FakeProspect(77, 70, 88), 5, 3, _visionFor(tier), 1)
        assert view['exact'] is None, (tier, view)
    assert ps.scoutedView(FakeProspect(77, 70, 88), 5, 3, _visionFor(96), 1)['exact'] == 88
    print("PASS only a perfect scout is handed the exact value")

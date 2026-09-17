"""The rare prospect who is drafted low and develops into a star.

⚠️ WITHOUT THIS THE STORY IS IMPOSSIBLE, NOT RARE. Measured over 4,000 generated
prospects before it existed: `corr(draft rating, ceiling) = 0.918` and ceiling minus draft
was a band of median +9, **sd 3.0**. Of 1,275 drafted at 66 or below, NOT ONE could ever
reach 90. `potential = trueSkill + randint(0, HEADROOM)` is drawn per attribute and the
composite averages three or four of those, so the central limit removes the tail.
"""
import os
import tempfile

os.environ.setdefault('DATABASE_DIR', tempfile.mkdtemp(prefix='floos_bloom_'))

import floosball_player as FP
import constants as C


# ⚠️ A LOW SEED, because that is the player this feature exists for and because a high one
# hides the effect: attributes clip at 100, so a +14 bloom on a seed-78 prospect moved the
# ceiling only 7 points. Testing the feature on a player it was not built for measures the
# clip, not the bloom.
def _prospect(seed=66):
    p = FP.PlayerWR(seed, seed)
    p.applyEntryDiscount(C.PROSPECT_ENTRY_DISCOUNT)
    p.seasonsPlayed = 0
    p.is_prospect = True
    return p


def test_thePendingBloomLivesOnThePlayerNotTheAttributes():
    """⚠️ IT FIRST WENT ON THE ATTRIBUTES OBJECT, beside the trueSkill fields it is related
    to. `player.lateBloomPending` then read 0 forever, so the bloom could never fire and
    nothing reported it — the feature would have shipped inert.

    Bite check: move the field back to Attributes and this fails.
    """
    p = _prospect()
    assert hasattr(p, 'lateBloomPending'), 'the player carries the pending bloom'
    assert not hasattr(p.attributes, 'lateBloomPending'), \
        'it must not sit on attributes, where the development hook cannot see it'


def test_aPendingBloomIsInvisibleToScouting():
    """⚠️ THE WHOLE POINT. `prospect_scouting` derives its band from `computeCeilingRating`,
    which reads `potentialX`. If the bloom were folded in at generation every team would
    see it, the player would go first overall, and "nobody saw it coming" would be false.

    Bite check: apply the bloom at generation instead of storing it and this fails.
    """
    plain = _prospect()
    before = plain.computeCeilingRating()
    plain.lateBloomPending = C.LATE_BLOOM_MAX
    assert plain.computeCeilingRating() == before, \
        'a pending bloom changed the scouted ceiling; it is no longer a surprise'


def test_theBloomRaisesBothTiersByOneSharedAmount():
    """⚠️ ONE AMOUNT ACROSS EVERY ATTRIBUTE, because a per-attribute roll is what the
    composite averages away. ⚠️ AND BOTH TIERS: growth is capped at trueSkill and only a
    gated overshoot reaches potential, so raising potential alone gives a ceiling the
    player almost never touches."""
    p = _prospect()
    beforeExpected = p.computeExpectedRating()
    beforeCeil = p.computeCeilingRating()
    p.lateBloomPending = 20
    applied = p.applyLateBloom()
    assert applied == 20
    assert p.lateBloomPending == 0, 'the bloom is one-shot'
    # `computeExpectedRating` is the trueSkill-targeted read; growth is capped there, so it
    # rising is what makes the new ceiling actually reachable rather than decorative.
    assert p.computeExpectedRating() > beforeExpected, \
        'trueSkill must rise, or growth still caps at the old target'
    assert p.computeCeilingRating() > beforeCeil, 'the ceiling must rise too'


def test_theBloomIsBigEnoughToMatter():
    """⚠️ SIZED AGAINST THE COMPOSITE, NOT THE ATTRIBUTES. `playerRating` is
    `(skillRating*3 + playMaking + xFactor)/5` and playMaking/xFactor are NOT trained, so a
    bloom reaches three fifths of the displayed number: +14 per attribute moved the ceiling
    only +8, which is indistinguishable from the ordinary development band (median +9) and
    therefore invisible. The smallest bloom has to clear that band to be the story.

    Bite check: set LATE_BLOOM_MIN back to 14 and this fails.
    """
    p = _prospect()
    before = p.computeCeilingRating()
    p.lateBloomPending = C.LATE_BLOOM_MIN
    p.applyLateBloom()
    gain = p.computeCeilingRating() - before
    assert gain >= 10, (
        f'the smallest bloom moves the ceiling only +{gain}, inside the ordinary band')


def test_theEnvironmentDecidesTheOdds():
    """⚠️ LESS PROBABLE WITH A POOR COACH AND POOR FACILITIES (owner), never impossible.
    The chance rides `devBias`, which is the coach's playerDevelopment plus the Training
    Facility bonus — the quantity the sim already computes for this."""
    base, per = C.LATE_BLOOM_FIRE_BASE, C.LATE_BLOOM_FIRE_PER_BIAS
    assert 0 < base < 0.25, 'a poorly-run team must be a long shot, not a wall'
    assert per > 0, 'a better environment has to raise the odds'
    poor, elite = base + 0 * per, base + 6 * per
    assert elite >= poor * 3, 'the environment should matter a lot, not a little'
    assert poor > 0, 'never impossible'


def test_itIsRare():
    assert 0 < C.LATE_BLOOM_CHANCE <= 0.05, \
        'measured at 0.02 this adds ~1pp to the 84+ share and nothing to 90+; much higher inflates'

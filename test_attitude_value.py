"""Attitude reaches the front office — `frontOfficeBrain.attitudeAdjustment`,
and fan sentiment moves to the departure BAR — `sentimentBarScale`.

⚠️ THE SIM MODELLED THE DAMAGE AND THE GM COULD NOT SEE IT.
`seasonManager._propagateAttitudeContagion` runs EVERY WEEK, dragging each
starter's confidence and determination toward the room's average attitude — its
own docstring says "a toxic veteran genuinely poisons teammates' confidence".
`frontOfficeBrain` never read `attitude`. Not once.

And sentiment: raising a beloved player's own club's VALUATION leaves every
buyer's clearing price identical across the full tilt range, because the selling
club's constraint never binds. It has to raise the bar the move must clear.

See docs/TRADING_PLAN.md §2.
"""

from constants import (FO_ATTITUDE_NEUTRAL, FO_ATTITUDE_PENALTY_PER_POINT,
                       FO_ATTITUDE_ROOM_MIN, FO_ATTITUDE_ROOM_MAX,
                       FO_CUT_UPGRADE_MARGIN, SENTIMENT_MAX_VALUE_SWING,
                       SENTIMENT_BAR_MIN_SCALE)
from managers.frontOfficeBrain import FrontOfficeBrain
from floosball_player import Position


class FakeAttrs:
    def __init__(self, attitude):
        self.attitude = attitude


class FakePlayer:
    def __init__(self, name, rating, attitude=80, position=Position.TE,
                 termRemaining=3, willRetire=False):
        self.name = name
        self.playerRating = rating
        self.position = position
        self.attributes = FakeAttrs(attitude)
        self.termRemaining = termRemaining
        self.willRetire = willRetire

    def computeExpectedRating(self):
        return self.playerRating

    def computeCeilingRating(self):
        return self.playerRating


class FakeCoach:
    def __init__(self, scouting=80, playerDevelopment=80, fanTrust=80, attitude=80):
        self.scouting = scouting
        self.playerDevelopment = playerDevelopment
        self.fanTrust = fanTrust
        self.attitude = attitude


class FakeTeam:
    def __init__(self, roomAttitudes, coachAttitude=80, name='Melons'):
        self.name = name
        self.id = 3
        self.coach = FakeCoach(attitude=coachAttitude)
        self.rosterDict = {
            slot: FakePlayer(f'{slot}', 80, attitude=a)
            for slot, a in zip(('qb', 'rb', 'wr1', 'wr2', 'te', 'k'), roomAttitudes)
        }


class FakePlayerManager:
    def __init__(self, freeAgents=None):
        self.freeAgents = freeAgents or []

    def computeRetirementOdds(self, player):
        return (0, False, -5)


class NoNoise:
    """⚠️ An injected rng BYPASSES the scout-belief cache — the deterministic path
    the existing brain tests already use. Without it these fakes carry no `id`, so
    every call re-rolls a fresh ~1-point error and a 2-point gap flips at random."""

    @staticmethod
    def gauss(mu, sigma):
        return 0.0


def _brain(**kw):
    return FrontOfficeBrain(FakePlayerManager(**kw))


NEUTRAL_ROOM = [80] * 6


# ----------------------------------------------------------- the penalty

def test_attitude_is_read_at_all():
    """The bug, stated as a test: the brain valued a 45-attitude player exactly
    like a 95-attitude one."""
    brain = _brain()
    toxic = FakePlayer('Chud', 85, attitude=45)
    clean = FakePlayer('Pro', 85, attitude=85)
    rng = NoNoise()
    assert brain.attitudeAdjustment(toxic) < brain.attitudeAdjustment(clean)
    assert brain.decisionValue(toxic, rng=rng) < brain.decisionValue(clean, rng=rng)
    print("PASS attitude now moves a valuation")


def test_the_anchor_table():
    """0.20/pt below 80, anchored on Chud Bumpington (TE, 85, attitude 45):
    85.0 -> 78.0, the point his rank on his own roster actually changes."""
    brain = _brain()
    hit = brain.attitudeAdjustment(FakePlayer('Chud', 85, attitude=45))
    assert abs(hit - -(80 - 45) * 0.20) < 1e-9, hit
    assert abs(hit - -7.0) < 1e-9
    print("PASS 45-attitude costs exactly 7.0 points (85.0 -> 78.0)")


def test_it_is_one_sided():
    """⚠️ PENALTY ONLY. A leader who lifts the room is real, but only the penalty
    half has a measured anchor, and a symmetric bonus would inflate the whole
    league's value scale on no evidence."""
    brain = _brain()
    assert brain.attitudeAdjustment(FakePlayer('Neutral', 80, attitude=80)) == 0.0
    assert brain.attitudeAdjustment(FakePlayer('Leader', 80, attitude=100)) == 0.0
    print("PASS neutral and above cost nothing, and earn nothing")


def test_unknown_attitude_reads_as_neutral_not_toxic():
    """A player whose attitude is missing must not be valued as a headcase —
    prospects, stubs and legacy rows all pass through here."""
    brain = _brain()
    blank = FakePlayer('Blank', 80)
    blank.attributes = None
    assert brain.attitudeAdjustment(blank) == 0.0
    zeroed = FakePlayer('Zeroed', 80, attitude=0)
    assert zeroed.attributes.attitude == 0
    assert brain.attitudeAdjustment(zeroed) == 0.0
    print("PASS missing / zero attitude is neutral")


def test_it_is_soft_not_a_veto():
    """⚠️ THE LESSON THE APPEAL GATE ALREADY TAUGHT. Discount difficult players
    hard enough and they pool in free agency, never get signed, and the supply
    floor generates replacements around them. The worst attitude in the league on
    the best player must still out-value a clearly worse clean player."""
    brain = _brain()
    star = FakePlayer('Difficult star', 92, attitude=35)
    filler = FakePlayer('Clean filler', 70, attitude=95)
    rng = NoNoise()
    assert brain.decisionValue(star, rng=rng) > brain.decisionValue(filler, rng=rng)
    print("PASS a difficult star still beats a clean filler")


# ------------------------------------------------------------- the room

def test_the_room_scales_the_penalty():
    """⚠️ THE TRADE COMES FROM THE ROOM, NOT FROM BLINDNESS. Exoticos (room 82.8)
    can take a headcase Grillmeisters (62.7) cannot — change of scenery as
    arithmetic, and it makes a good locker room a tradeable asset in itself."""
    brain = _brain()
    chud = FakePlayer('Chud', 85, attitude=45)
    good = FakeTeam([83] * 6, coachAttitude=82, name='Exoticos')
    bad = FakeTeam([63] * 6, coachAttitude=63, name='Grillmeisters')
    inGood = brain.attitudeAdjustment(chud, good)
    inBad = brain.attitudeAdjustment(chud, bad)
    assert inBad < inGood, (inBad, inGood)
    print(f"PASS same player costs {-inBad:.1f} in a toxic room vs {-inGood:.1f} in a strong one")


def test_a_neutral_room_reproduces_the_anchor():
    """⚠️ The room may only ever SCALE a penalty that is already correct. If a
    neutral room moved the number, the anchor table above would be describing a
    calculation that never happens."""
    brain = _brain()
    chud = FakePlayer('Chud', 85, attitude=45)
    assert brain.attitudeAdjustment(chud, FakeTeam(NEUTRAL_ROOM)) == \
           brain.attitudeAdjustment(chud)
    print("PASS a neutral room is exactly 1.0x")


def test_the_room_is_bounded():
    """The room must never dominate the attribute — a perfect room cannot make a
    headcase free, and a dreadful one cannot make him unsignable."""
    brain = _brain()
    chud = FakePlayer('Chud', 85, attitude=45)
    flat = brain.attitudeAdjustment(chud)
    best = brain.attitudeAdjustment(chud, FakeTeam([100] * 6, coachAttitude=100))
    worst = brain.attitudeAdjustment(chud, FakeTeam([20] * 6, coachAttitude=20))
    assert abs(best - flat * FO_ATTITUDE_ROOM_MIN) < 1e-9
    assert abs(worst - flat * FO_ATTITUDE_ROOM_MAX) < 1e-9
    print(f"PASS room clamped to [{FO_ATTITUDE_ROOM_MIN}, {FO_ATTITUDE_ROOM_MAX}]x")


# ------------------------------- it reaches cuts and re-signs, not only trades

def test_attitude_reaches_cuts_and_resigns():
    """⚠️ IT GOES IN `decisionValue`, WHICH IS THE ONE NUMBER EVERY FRONT-OFFICE
    DECISION CONSUMES — so a single term covers rankCutCandidates,
    rankResignCandidates, buildDraftBoard and prospect promotion alike. This is
    therefore a LIVE front-office change, not a trade-only feature.

    The sharpest expression of it, and the one this asserts: a clean free agent
    twelve rating points WORSE now out-values a 40-attitude incumbent, so the
    incumbent reads as replaceable and loses his re-sign slot. Without the term
    the incumbent is simply the better player and keeps it.
    """
    brain = _brain()
    toxic = FakePlayer('Toxic', 82, attitude=40, termRemaining=3)
    clean = FakePlayer('Clean', 82, attitude=90, termRemaining=3)
    replacement = FakePlayer('Clean FA', 70, attitude=80)

    rng = NoNoise()
    assert brain.decisionValue(replacement, rng=rng) > brain.decisionValue(toxic, rng=rng)
    assert brain.decisionValue(replacement, rng=rng) < brain.decisionValue(clean, rng=rng)

    team = FakeTeam(NEUTRAL_ROOM)
    ranked = brain.rankResignCandidates([toxic, clean], coach=team.coach,
                                        pool=[replacement], rng=rng)
    kept = [p.name for p, _ in ranked]
    assert 'Clean' in kept
    assert 'Toxic' not in kept, kept
    print("PASS a 40-attitude 82 loses his re-sign slot to a clean 70")


def test_attitude_reaches_the_cut_ranking():
    """The other live decision the same term has to reach."""
    brain = _brain()
    pool = [FakePlayer('FA', 84, attitude=80)]
    team = FakeTeam(NEUTRAL_ROOM)

    def cutsFor(incumbent):
        team.rosterDict = {'qb': None, 'rb': None, 'wr1': None, 'wr2': None,
                           'te': incumbent, 'k': None}
        return brain.rankCutCandidates(team, coach=team.coach, pool=pool,
                                       rng=NoNoise())

    toxicUpgrade = cutsFor(FakePlayer('Toxic', 82, attitude=40, termRemaining=3))
    cleanUpgrade = cutsFor(FakePlayer('Clean', 82, attitude=90, termRemaining=3))
    toxicGap = toxicUpgrade[0][2] if toxicUpgrade else 0.0
    cleanGap = cleanUpgrade[0][2] if cleanUpgrade else 0.0
    assert toxicGap > cleanGap, (toxicGap, cleanGap)
    print(f"PASS cutting a headcase reads as a {toxicGap:.1f}-point upgrade "
          f"against {cleanGap:.1f} for the same rating clean")


# --------------------------------------------- sentiment on the bar

def test_sentiment_scales_the_departure_bar():
    """⚠️ THE FINDING: raising the seller's VALUATION does nothing where the
    seller's constraint does not bind. Sentiment raises the surplus the move must
    clear instead."""
    brain = _brain()
    darling = FakePlayer('Darling', 80)
    darling.id = 11
    hated = FakePlayer('Hated', 80)
    hated.id = 12
    plain = FakePlayer('Plain', 80)
    plain.id = 13
    brain.sentimentMap = {11: 1.0, 12: -1.0}
    coach = FakeCoach(fanTrust=100)

    assert brain.sentimentBarScale(plain, coach) == 1.0
    assert brain.sentimentBarScale(darling, coach) > 1.0
    assert brain.sentimentBarScale(hated, coach) < 1.0
    print("PASS a favourite raises the bar, an unpopular player lowers it")


def test_the_bar_is_floored_above_zero():
    """An unpopular player must never be FREE to move — the modifier is a price,
    never a veto and never a giveaway. Same rule as every other modifier here."""
    brain = _brain()
    hated = FakePlayer('Hated', 80)
    hated.id = 9
    brain.sentimentMap = {9: -1.0}
    scale = brain.sentimentBarScale(hated, FakeCoach(fanTrust=100))
    assert scale >= SENTIMENT_BAR_MIN_SCALE > 0.0
    print(f"PASS unpopular bar floored at {scale}")


def test_a_gm_who_ignores_fans_ignores_the_bar_too():
    """`fanTrust` 60 means this GM trusts its own read. The bar must respect that
    exactly as the value tilt does, or sentiment would reach a populist and an
    independent alike through the back door."""
    brain = _brain()
    darling = FakePlayer('Darling', 80)
    darling.id = 5
    brain.sentimentMap = {5: 1.0}
    assert brain.sentimentBarScale(darling, FakeCoach(fanTrust=60)) == 1.0
    assert brain.sentimentBarScale(darling, FakeCoach(fanTrust=100)) > 1.0
    print("PASS fanTrust gates the bar the same way it gates the tilt")


def test_sentiment_is_not_counted_twice_on_a_cut():
    """⚠️ `rankCutCandidates` puts sentiment on the BAR, so it must take the value
    WITHOUT the tilt. Counting it in both places prices one fan opinion twice."""
    import inspect
    src = inspect.getsource(FrontOfficeBrain.rankCutCandidates)
    assert 'includeSentiment=False' in src
    assert 'sentimentBarScale' in src
    print("PASS the cut site takes the bar and drops the tilt")


def test_the_resign_ordering_keeps_the_value_tilt():
    """⚠️ THE ASYMMETRY IS THE POINT AND MERGING THE TWO WOULD BE A REGRESSION.
    Where a club chooses AMONG players the ORDER is the decision, and a bar there
    is nearly inert — FO_RESIGN_SURPLUS_MARGIN is 0.5 and essentially everything
    clears it. Sentiment has to stay on the value for that question."""
    brain = _brain()
    darling = FakePlayer('Darling', 80)
    darling.id = 21
    plain = FakePlayer('Plain', 80)
    plain.id = 22
    brain.sentimentMap = {21: 1.0}
    coach = FakeCoach(fanTrust=100)
    pool = [FakePlayer('FA', 70)]
    ranked = brain.rankResignCandidates([plain, darling], coach=coach, pool=pool,
                                        rng=NoNoise())
    assert [p.name for p, _ in ranked][0] == 'Darling'
    print("PASS a fan favourite still outranks an identical player for a re-sign slot")

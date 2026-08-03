"""Fan sentiment — storage, aggregation, and the GM tilt (AFO plan Part D).

Asserts what the design promises: net one rating per fan, a rater floor so one
loud voice can't move a roster decision, and a tilt that scales with the GM's
own fanTrust while never being large enough to force a clearly-bad move.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base, PlayerSentimentRating
from database.repositories.sentiment_repository import (
    SentimentRepository, normalizeSentiment,
)
from managers.frontOfficeBrain import FrontOfficeBrain
from constants import SENTIMENT_MIN_RATERS, SENTIMENT_MAX_VALUE_SWING
from test_front_office_brain import FakePlayer, FakeCoach, FakePlayerManager
from floosball_player import Position


def _session():
    """In-memory DB with just the tables we need."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[PlayerSentimentRating.__table__])
    return sessionmaker(bind=engine)()


def _repo():
    return SentimentRepository(_session())


# ------------------------------------------------------------- storage

def test_rating_is_net_one_per_fan():
    """Anti-brigade: re-rating replaces, it never stacks."""
    r = _repo()
    r.setRating(userId=1, playerId=7, rating=5)
    r.setRating(userId=1, playerId=7, rating=1)
    r.session.commit()

    avg, raters = r.getAggregate(7)
    assert raters == 1, raters
    assert avg == 1.0, avg
    print("PASS re-rating replaces rather than stacking")


def test_rating_bounds_are_enforced():
    r = _repo()
    for bad in (0, 6, -1, 99):
        try:
            r.setRating(1, 7, bad)
        except ValueError:
            continue
        raise AssertionError(f"accepted out-of-range rating {bad}")
    print("PASS out-of-range ratings are rejected")


def test_withdrawing_a_rating():
    r = _repo()
    r.setRating(1, 7, 4)
    r.session.commit()
    assert r.clearRating(1, 7) is True
    r.session.commit()
    assert r.getAggregate(7) == (0.0, 0)
    assert r.clearRating(1, 7) is False   # idempotent
    print("PASS a rating can be withdrawn, and withdrawing twice is safe")


# --------------------------------------------------------- aggregation

def test_rater_floor_gates_the_signal():
    """The whole anti-brigade point: below the floor a player reads NEUTRAL, so
    one loud fan cannot move a roster decision."""
    r = _repo()
    for uid in range(SENTIMENT_MIN_RATERS - 1):
        r.setRating(uid, 7, 5)
    r.session.commit()
    assert r.getSentiment(7) == 0.0, "below floor must read neutral"

    r.setRating(999, 7, 5)
    r.session.commit()
    assert r.getSentiment(7) > 0.0, "at the floor the signal engages"
    print(f"PASS sentiment is gated until {SENTIMENT_MIN_RATERS} distinct raters")


def test_normalization_maps_onto_minus_one_to_one():
    assert normalizeSentiment(3.0) == 0.0        # neutral midpoint
    assert normalizeSentiment(5.0) == 1.0        # adored
    assert normalizeSentiment(1.0) == -1.0       # hated
    assert normalizeSentiment(None) == 0.0       # unrated
    assert -1.0 <= normalizeSentiment(4.2) <= 1.0
    print("PASS 1-5 ratings normalize onto -1..+1 with 3 as neutral")


def test_bulk_map_matches_per_player():
    """The sweep uses the bulk map; it must not disagree with the single read."""
    r = _repo()
    for pid, rating in ((1, 5), (2, 1), (3, 3)):
        for uid in range(SENTIMENT_MIN_RATERS):
            r.setRating(uid, pid, rating)
    r.session.commit()

    bulk = r.getSentimentMap()
    for pid in (1, 2, 3):
        assert abs(bulk.get(pid, 0.0) - r.getSentiment(pid)) < 1e-9, pid
    print("PASS bulk sentiment map matches per-player reads")


def test_boards_exclude_under_rated_players():
    r = _repo()
    for uid in range(SENTIMENT_MIN_RATERS):
        r.setRating(uid, 10, 5)        # genuinely loved
        r.setRating(uid, 11, 1)        # genuinely hated
    r.setRating(50, 12, 5)             # one rater only — must not appear
    r.session.commit()

    loved = r.getBoard(10, mostLoved=True)
    hated = r.getBoard(10, mostLoved=False)
    assert [e['playerId'] for e in loved][0] == 10
    assert [e['playerId'] for e in hated][0] == 11
    assert 12 not in {e['playerId'] for e in loved + hated}
    print("PASS boards are rater-gated and ordered correctly")


# ---------------------------------------------------------- brain tilt

def _brain(sentimentMap):
    return FrontOfficeBrain(FakePlayerManager(), sentimentMap=sentimentMap)


def _player(pid, rating=80):
    p = FakePlayer('Guy', rating, position=Position.TE)
    p.id = pid
    return p


def test_tilt_scales_with_fan_trust():
    """The design's whole point: fanTrust 60 ignores the fans, 100 is a populist."""
    brain = _brain({1: 1.0})
    player = _player(1)

    independent = brain.sentimentTilt(player, FakeCoach(fanTrust=60))
    populist = brain.sentimentTilt(player, FakeCoach(fanTrust=100))

    assert independent == 0.0, independent
    assert abs(populist - SENTIMENT_MAX_VALUE_SWING) < 1e-9, populist
    print(f"PASS tilt scales with fanTrust (60 -> {independent:.1f}, 100 -> {populist:.1f})")


def test_tilt_direction_follows_sentiment():
    loved, hated = _brain({1: 1.0}), _brain({1: -1.0})
    coach = FakeCoach(fanTrust=100)
    assert loved.sentimentTilt(_player(1), coach) > 0
    assert hated.sentimentTilt(_player(1), coach) < 0
    print("PASS a darling is valued up, a villain down")


def test_tilt_cannot_force_a_clearly_bad_move():
    """Sentiment tips close calls only. A maximally-hated star must still
    out-value a mediocrity — otherwise fans can wreck a roster."""
    brain = _brain({1: -1.0})
    coach = FakeCoach(fanTrust=100, scouting=100)

    star = _player(1, rating=95)
    scrub = _player(2, rating=70)

    assert brain.decisionValue(star, coach) > brain.decisionValue(scrub, coach)
    print("PASS a hated star still out-values a beloved scrub")


def test_no_sentiment_layer_is_a_clean_noop():
    """A league where nobody has rated anything must behave exactly as before."""
    brain = FrontOfficeBrain(FakePlayerManager())
    # scouting 100 => no scouting error, so the two reads are directly
    # comparable (perceivedValue is otherwise randomised per call).
    coach = FakeCoach(fanTrust=100, scouting=100)
    player = _player(1)
    assert brain.sentimentTilt(player, coach) == 0.0
    assert brain.decisionValue(player, coach) == brain.perceivedValue(player, coach)
    print("PASS an unrated league is unaffected")


def test_unknown_player_reads_neutral():
    brain = _brain({999: 1.0})
    assert brain.sentimentTilt(_player(1), FakeCoach(fanTrust=100)) == 0.0

    class NoId:
        playerRating = 80
        position = Position.TE
    assert brain.sentimentTilt(NoId(), FakeCoach(fanTrust=100)) == 0.0
    print("PASS players absent from the map (or with no id) read neutral")




def test_quorum_scales_with_the_active_fanbase():
    """The floor is for a small league; a busier one should need more turnout
    before a public average is trustworthy."""
    import math
    from constants import SENTIMENT_MIN_RATERS, SENTIMENT_QUORUM_ACTIVE_FRACTION

    def required(active):
        return max(SENTIMENT_MIN_RATERS, math.ceil(active * SENTIMENT_QUORUM_ACTIVE_FRACTION))

    assert required(0) == SENTIMENT_MIN_RATERS      # empty league -> the floor
    assert required(18) == SENTIMENT_MIN_RATERS     # small league -> still the floor
    assert required(140) > SENTIMENT_MIN_RATERS     # busy league -> more turnout
    assert required(400) > required(140)            # monotonic
    print(f"PASS quorum scales (0/18 -> {required(0)}, 140 -> {required(140)}, 400 -> {required(400)})")


def test_quorum_never_drops_below_the_floor():
    """However tiny the base, one or two fans must never set a public number."""
    from database.repositories.sentiment_repository import requiredRaters
    from constants import SENTIMENT_MIN_RATERS

    class DeadSession:
        def query(self, *a, **k): raise RuntimeError('no db')

    # An unavailable count must fall back to the floor, never to zero.
    assert requiredRaters(DeadSession()) == SENTIMENT_MIN_RATERS
    print("PASS an unavailable user count falls back to the floor, not to zero")


def test_ratings_stay_hidden_until_quorum():
    """End to end: the aggregate is withheld until the scaled quorum is met."""
    from database.repositories.sentiment_repository import requiredRaters
    r = _repo()
    need = requiredRaters(r.session)
    for uid in range(need - 1):
        r.setRating(uid, 7, 5)
    r.session.commit()
    assert r.getSentiment(7) == 0.0
    r.setRating(9999, 7, 5)
    r.session.commit()
    assert r.getSentiment(7) > 0.0
    print(f"PASS aggregate stays hidden until {need} raters, then counts")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for fn in tests:
        fn()
    print(f"\nAll {len(tests)} fan sentiment tests passed.")

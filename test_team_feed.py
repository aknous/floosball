"""Team social feed — manual posts and rating-generated auto posts (Part D).

Asserts the design's promises: no free text, only general team lines are
manually postable, rating a player or voting on the GM echoes into the feed in
the fan's own voice, and changing your mind REPLACES that echo rather than
stacking a contradiction.
"""

from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base, TeamFeedPost, PlayerSentimentRating
from database.repositories.feed_repository import (
    FeedRepository, FeedError, renderPost, catalogEntry,
)
from database.repositories.sentiment_repository import (
    SentimentRepository, CoachSentimentRepository, buildSentimentMap,
)
from database.models import CoachSentimentVote
from constants import (
    FEED_POST_CATALOG, FEED_POST_TTL_HOURS, FEED_MAX_POSTS_PER_WINDOW,
    SENTIMENT_MIN_RATERS, FEED_AUTOPOST_BY_RATING, GM_SENTIMENT_MIN_VOTERS,
)

NOW = datetime(2026, 7, 28, 12, 0, 0)


def _session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[TeamFeedPost.__table__,
                                             PlayerSentimentRating.__table__,
                                             CoachSentimentVote.__table__])
    return sessionmaker(bind=engine)()


def _repo(session=None, now=NOW):
    return FeedRepository(session or _session(), now=now)


# ------------------------------------------------------------- catalog

def test_every_catalog_entry_is_well_formed():
    """A malformed entry would surface as a blank or crashing post."""
    for key, entry in FEED_POST_CATALOG.items():
        assert len(entry) == 3, key
        text, target, valence = entry
        assert text and isinstance(text, str), key
        assert target in ('player', 'gm', 'team'), key
        assert valence in (-1, 0, 1), key
    print(f"PASS all {len(FEED_POST_CATALOG)} catalog entries are well-formed")


def test_only_catalog_posts_are_accepted():
    """No free text anywhere — that's what removes the moderation surface."""
    r = _repo()
    for bogus in ('you stink', '', 'DROP TABLE players', 'not_a_key'):
        try:
            r.addPost(1, 1, bogus)
        except FeedError:
            continue
        raise AssertionError(f"accepted non-catalog post {bogus!r}")
    print("PASS only pre-made catalog posts are accepted")


def test_no_post_implies_a_mechanic_that_doesnt_exist():
    """Floosball has no trades. Vocabulary must stay inside the moves that
    actually exist: cut, re-sign, sign a free agent, fire the GM."""
    import re
    banned = re.compile(r'\btrade[sd]?\b|\buntouchable\b', re.I)
    offenders = [k for k, (text, _t, _v) in FEED_POST_CATALOG.items() if banned.search(text)]
    assert not offenders, f"posts imply a trade: {offenders}"
    print("PASS no catalog line implies a trade")


def test_name_token_is_rendered():
    assert renderPost('in_trust', 'Vince Lombardi') == 'In Vince Lombardi we trust'
    assert '{name}' not in renderPost('in_trust', None)   # graceful fallback
    assert renderPost('cut_them', None) == 'Cut them'
    print("PASS {name} tokens render, with a sane fallback")


# ---------------------------------------------------------- rate limit

def test_rate_limit_bounds_the_spam():
    r = _repo()
    for _ in range(FEED_MAX_POSTS_PER_WINDOW):
        r.addPost(1, 1, 'believe')
    r.session.commit()
    assert r.remainingPosts(1) == 0
    try:
        r.addPost(1, 1, 'believe')
        raise AssertionError("rate limit not enforced")
    except FeedError:
        pass
    # a DIFFERENT fan is unaffected
    assert r.remainingPosts(2) == FEED_MAX_POSTS_PER_WINDOW
    print(f"PASS rate limited to {FEED_MAX_POSTS_PER_WINDOW} per window, per fan")


# --------------------------------------------------------------- decay

def test_purge_removes_expired_posts():
    session = _session()
    FeedRepository(session, now=NOW - timedelta(hours=FEED_POST_TTL_HOURS + 5)).addPost(1, 1, 'believe')
    FeedRepository(session, now=NOW).addPost(2, 1, 'believe')
    session.commit()
    removed = FeedRepository(session, now=NOW).purgeExpired()
    session.commit()
    assert removed == 1, removed
    assert len(FeedRepository(session, now=NOW).getFeed(1)) == 1
    print("PASS purge drops only expired posts")


# ------------------------------------------------- manual vs auto split

def test_player_and_gm_lines_cannot_be_posted_manually():
    """Those lines are the AUTO vocabulary. Letting a fan post them directly
    would double-count an opinion they can only hold once."""
    r = _repo()
    for autoOnly in ('cut_them', 'cornerstone', 'fire_the_gm', 'in_trust'):
        try:
            r.addPost(1, 1, autoOnly)
        except FeedError:
            continue
        raise AssertionError(f"{autoOnly} was manually postable")
    print("PASS player/GM lines are auto-only, not manually postable")


def test_general_lines_are_postable():
    r = _repo()
    for key in ('believe', 'not_good'):
        r.addPost(1, 1, key)
    r.session.commit()
    assert len(r.getFeed(1)) == 2
    print("PASS general support/frustration lines post fine")


# --------------------------------------------------------- auto posts

def test_rating_echoes_into_the_feed():
    r = _repo()
    r.autoPostForRating(userId=1, teamId=1, playerId=42, rating=5)
    r.session.commit()
    feed = r.getFeed(1)
    assert len(feed) == 1, feed
    assert feed[0].is_auto and feed[0].target_type == 'player'
    assert feed[0].target_player_id == 42
    assert catalogEntry(feed[0].post_key)[2] == 1, "a 5 must produce a POSITIVE post"
    print(f"PASS a 5-star rating echoes as: {renderPost(feed[0].post_key)!r}")


def test_low_rating_echoes_negatively():
    r = _repo()
    r.autoPostForRating(1, 1, 42, 1)
    r.session.commit()
    assert catalogEntry(r.getFeed(1)[0].post_key)[2] == -1
    print("PASS a 1-star rating echoes as a negative post")


def test_a_shrug_says_nothing():
    """A 3 is a shrug — not worth a post, and the feed stays signal."""
    assert FEED_AUTOPOST_BY_RATING[3] is None
    r = _repo()
    r.autoPostForRating(1, 1, 42, 3)
    r.session.commit()
    assert r.getFeed(1) == []
    print("PASS a 3-star rating generates no post")


def test_changing_your_mind_replaces_the_echo():
    """The bug this guards: loving then hating a player would otherwise leave
    the same fan visibly contradicting themselves in the feed."""
    r = _repo()
    r.autoPostForRating(1, 1, 42, 5)
    r.session.commit()
    r.autoPostForRating(1, 1, 42, 1)
    r.session.commit()

    feed = r.getFeed(1)
    assert len(feed) == 1, [f.post_key for f in feed]
    assert catalogEntry(feed[0].post_key)[2] == -1
    print("PASS re-rating replaces the previous echo instead of stacking")


def test_rating_down_to_neutral_withdraws_the_echo():
    r = _repo()
    r.autoPostForRating(1, 1, 42, 5)
    r.session.commit()
    r.autoPostForRating(1, 1, 42, 3)      # shrug
    r.session.commit()
    assert r.getFeed(1) == []
    print("PASS moving to a 3 withdraws the earlier post")


def test_each_fan_keeps_their_own_echo():
    r = _repo()
    r.autoPostForRating(1, 1, 42, 5)
    r.autoPostForRating(2, 1, 42, 1)
    r.session.commit()
    assert len(r.getFeed(1)) == 2, "one fan's re-rate must not clear another's"
    print("PASS echoes are per fan, not per player")


def test_gm_rating_echoes_into_the_feed():
    r = _repo()
    r.autoPostForCoachRating(userId=1, teamId=1, rating=1)
    r.session.commit()
    feed = r.getFeed(1)
    assert len(feed) == 1 and feed[0].target_type == 'gm' and feed[0].is_auto
    assert catalogEntry(feed[0].post_key)[2] == -1
    print(f"PASS a low GM rating echoes as: {renderPost(feed[0].post_key, 'Lombardi')!r}")


def test_withdrawing_a_gm_rating_clears_the_echo():
    r = _repo()
    r.autoPostForCoachRating(1, 1, 5)
    r.session.commit()
    r.autoPostForCoachRating(1, 1, None)      # withdrawn
    r.session.commit()
    assert r.getFeed(1) == []
    print("PASS withdrawing a GM rating removes its post")


def test_a_middling_gm_rating_says_nothing():
    """A 3 is a shrug for a GM exactly as it is for a player."""
    r = _repo()
    r.autoPostForCoachRating(1, 1, 3)
    r.session.commit()
    assert r.getFeed(1) == []
    print("PASS a 3-star GM rating generates no post")


def test_auto_posts_bypass_the_rate_limit():
    """Ratings are net-one-per-target so they're self-limiting; they must not
    consume the fan's hourly allowance for general posts."""
    r = _repo()
    for pid in range(20):
        r.autoPostForRating(1, 1, pid, 5)
    r.session.commit()
    assert r.remainingPosts(1) >= 0
    r.addPost(1, 1, 'believe')           # must still be allowed
    print("PASS auto posts don't consume the manual post allowance")


# ------------------------------------------------------- GM sentiment

def _coachRepo():
    return CoachSentimentRepository(_session())


def test_gm_rating_replaces_not_stacks():
    r = _coachRepo()
    r.setRating(1, 7, 5)
    r.setRating(1, 7, 1)
    r.session.commit()
    avg, raters = r.getAggregate(7)
    assert raters == 1 and avg == 1.0, (avg, raters)
    assert r.clearRating(1, 7) is True
    r.session.commit()
    assert r.getAggregate(7) == (0.0, 0)
    print("PASS GM rating replaces on re-rate and can be withdrawn")


def test_gm_uses_the_same_scale_as_players():
    """One rating model. A GM must not be judged on a different curve."""
    from database.repositories.sentiment_repository import normalizeSentiment
    r = _coachRepo()
    for uid in range(GM_SENTIMENT_MIN_VOTERS):
        r.setRating(uid, 7, 5)
    r.session.commit()
    avg, _ = r.getAggregate(7)
    assert r.getStanding(7) == normalizeSentiment(avg) == 1.0
    print("PASS GM standing uses the same normalization as players")


def test_gm_standing_is_gated_and_normalized():
    r = _coachRepo()
    for uid in range(GM_SENTIMENT_MIN_VOTERS - 1):
        r.setRating(uid, 7, 1)
    r.session.commit()
    assert r.getStanding(7) == 0.0, "below the floor a GM reads neutral"

    r.setRating(99, 7, 1)
    r.session.commit()
    assert r.getStanding(7) == -1.0, "unanimous 1-star is -1"
    print(f"PASS GM standing gated until {GM_SENTIMENT_MIN_VOTERS} voters, then normalized")





def test_gm_standing_map_matches_per_coach():
    r = _coachRepo()
    for uid in range(4):
        r.setRating(uid, 7, 1)
        r.setRating(uid, 8, 5)
    r.session.commit()
    bulk = r.getStandingMap()
    for cid in (7, 8):
        assert abs(bulk[cid] - r.getStanding(cid)) < 1e-9
    print("PASS bulk GM standing map matches per-coach reads")


def test_gm_boards_rank_both_ends():
    r = _coachRepo()
    for uid in range(4):
        r.setRating(uid, 7, 5)      # well regarded
        r.setRating(uid, 8, 1)      # under fire
    r.session.commit()
    assert r.getBoard(5, mostLiked=True)[0]['coachId'] == 7
    assert r.getBoard(5, mostLiked=False)[0]['coachId'] == 8
    print("PASS GM boards rank backed and under-fire correctly")


def test_sentiment_map_is_ratings_only():
    """Auto posts are a display artifact — they must never feed the model
    again, or every rating would count twice."""
    session = _session()
    sent = SentimentRepository(session)
    for uid in range(SENTIMENT_MIN_RATERS):
        sent.setRating(uid, 42, 5)
    feed = FeedRepository(session, now=NOW)
    for uid in range(SENTIMENT_MIN_RATERS):
        feed.autoPostForRating(uid, 1, 42, 5)
    session.commit()

    ratingOnly = SentimentRepository(session).getSentimentMap()
    assert buildSentimentMap(session, now=NOW) == ratingOnly
    print("PASS the brain's map is ratings only; auto posts don't double-count")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for fn in tests:
        fn()
    print(f"\nAll {len(tests)} team feed tests passed.")

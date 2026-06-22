"""Validate the weekly Showcase dividend against an in-memory DB.

Builds a couple of showcases, runs showcaseManager.awardWeeklyDividends across two
weeks, and checks the dividends landed, match the grade, accumulate week over
week, and are idempotent per week (no double-pay on a replay).
Run: python3 test_showcase_payout.py
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import (
    Base, User, CardTemplate, UserCard, ShowcaseSlot, UserCurrency, CurrencyTransaction,
)
from managers import showcaseManager

SEASON = 8


def mkTemplate(s, i, edition, classification, season=SEASON, team_id=1):
    t = CardTemplate(
        player_id=100 + i, edition=edition, season_created=season,
        is_rookie=False, classification=classification,
        player_name=f"Player{i}", team_id=team_id, player_rating=90, position=1,
        effect_config={}, rarity_weight=1, sell_value=10,
    )
    s.add(t); s.flush()
    return t


def feature(s, userId, season, cards):
    """cards: list of (edition, classification). Vault + feature each in a slot."""
    for slot, (edition, cls) in enumerate(cards, start=1):
        t = mkTemplate(s, userId * 100 + slot, edition, cls, season)
        uc = UserCard(user_id=userId, card_template_id=t.id, vaulted=True, acquired_via="test")
        s.add(uc); s.flush()
        s.add(ShowcaseSlot(user_id=userId, season=season, slot_number=slot, user_card_id=uc.id))


def main():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()

    # User 1: a monster showcase (8 diamonds, all MVP, same team) -> top grade
    s.add(User(id=1, username="whale", email="whale@test.local")); s.flush()
    feature(s, 1, SEASON, [("diamond", "mvp")] * 8)

    # User 2: a modest showcase (8 base, no classification) -> low/zero grade
    s.add(User(id=2, username="casual", email="casual@test.local")); s.flush()
    feature(s, 2, SEASON, [("base", None)] * 8)

    # User 3: featured nothing this season -> never paid
    s.add(User(id=3, username="ghost", email="ghost@test.local")); s.flush()
    s.commit()

    # Expected dividends from the engine itself (so the test tracks tuning)
    exp1 = showcaseManager.evaluate(showcaseManager.loadShowcaseCardInfos(s, 1, SEASON), SEASON)
    exp2 = showcaseManager.evaluate(showcaseManager.loadShowcaseCardInfos(s, 2, SEASON), SEASON)
    div1, div2 = exp1["weeklyDividend"], exp2["weeklyDividend"]
    print(f"User1 expected grade={exp1['grade']} dividend/wk={div1}")
    print(f"User2 expected grade={exp2['grade']} dividend/wk={div2}")

    # Pay weeks 1 and 2; replay week 1 to prove the per-week guard.
    summaryW1 = showcaseManager.awardWeeklyDividends(s, SEASON, 1); s.commit()
    replayW1 = showcaseManager.awardWeeklyDividends(s, SEASON, 1); s.commit()
    summaryW2 = showcaseManager.awardWeeklyDividends(s, SEASON, 2); s.commit()
    print(f"Week1: {summaryW1}")
    print(f"Week1 replay (guarded): {replayW1}")
    print(f"Week2: {summaryW2}")

    def bal(uid):
        c = s.query(UserCurrency).filter_by(user_id=uid).first()
        return int(c.balance) if c else 0

    ok = True
    # Two weeks paid -> balance = 2 × weekly dividend.
    if bal(1) != div1 * 2:
        print(f"FAIL: user1 balance {bal(1)} != {div1 * 2}"); ok = False
    if bal(2) != div2 * 2:
        print(f"FAIL: user2 balance {bal(2)} != {div2 * 2}"); ok = False
    if bal(3) != 0:
        print(f"FAIL: user3 (no showcase) got {bal(3)}"); ok = False

    # Per-week idempotency: the week-1 replay must not pay again.
    if not replayW1.get("alreadyAwarded"):
        print(f"FAIL: week-1 replay not guarded: {replayW1}"); ok = False

    # User1 should have exactly 2 dividend transactions (one per distinct week).
    txn = s.query(CurrencyTransaction).filter_by(
        user_id=1, transaction_type=showcaseManager.SHOWCASE_DIVIDEND_TX).count()
    if div1 > 0 and txn != 2:
        print(f"FAIL: user1 has {txn} dividend transactions (expected 2)"); ok = False

    print("PASS" if ok else "FAILURES ABOVE")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Validate the end-of-season Showcase payout against an in-memory DB.

Builds a couple of showcases, runs showcaseManager.awardSeasonPayouts, and
checks the payouts landed, match the grade, and are idempotent (no double-pay).
Run: python3 test_showcase_payout.py
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import (
    Base, User, CardTemplate, UserCard, ShowcaseSlot, UserCurrency, CurrencyTransaction,
)
from managers import showcaseManager
from constants import SHOWCASE_GRADE_PAYOUT

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

    # User 3: featured nothing this season -> not in payout at all
    s.add(User(id=3, username="ghost", email="ghost@test.local")); s.flush()
    s.commit()

    # Expected grades from the engine itself (so the test tracks tuning)
    exp1 = showcaseManager.evaluate(showcaseManager.loadShowcaseCardInfos(s, 1, SEASON), SEASON)
    exp2 = showcaseManager.evaluate(showcaseManager.loadShowcaseCardInfos(s, 2, SEASON), SEASON)
    print(f"User1 expected grade={exp1['grade']} payout={exp1['payout']}")
    print(f"User2 expected grade={exp2['grade']} payout={exp2['payout']}")

    summary = showcaseManager.awardSeasonPayouts(s, SEASON)
    s.commit()
    print(f"Payout summary: {summary}")

    def bal(uid):
        c = s.query(UserCurrency).filter_by(user_id=uid).first()
        return int(c.balance) if c else 0

    ok = True
    if bal(1) != exp1["payout"]:
        print(f"FAIL: user1 balance {bal(1)} != {exp1['payout']}"); ok = False
    if bal(2) != exp2["payout"]:
        print(f"FAIL: user2 balance {bal(2)} != {exp2['payout']}"); ok = False
    if bal(3) != 0:
        print(f"FAIL: user3 (no showcase) got {bal(3)}"); ok = False

    # Idempotency: a second run must not pay again
    summary2 = showcaseManager.awardSeasonPayouts(s, SEASON)
    s.commit()
    if not summary2.get("alreadyAwarded"):
        print(f"FAIL: second run not guarded: {summary2}"); ok = False
    if bal(1) != exp1["payout"]:
        print(f"FAIL: user1 double-paid -> {bal(1)}"); ok = False

    # Transaction count for user1 should be exactly 1
    txn = s.query(CurrencyTransaction).filter_by(
        user_id=1, transaction_type=showcaseManager.SHOWCASE_PAYOUT_TX).count()
    if exp1["payout"] > 0 and txn != 1:
        print(f"FAIL: user1 has {txn} payout transactions (expected 1)"); ok = False

    print("PASS" if ok else "FAILURES ABOVE")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

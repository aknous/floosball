"""A FLEX card stops counting when Accession expires.

Reported (2026-11-04): a user bought Accession (temp_card_slot), and after it expired the
card in the FLEX slot kept counting toward their score. The game-start carry-forward
(`SeasonManager._carryForwardEquippedCards`) copied the FLEX row into the new week with no
entitlement check, `lockAllForWeek` locked it, and `_processWeekCardEffects` scored every
locked row, so the expired FLEX card went into the banked breakdown, which the snapshot
then counts. The live snapshot already skipped it, so the score only moved at the bank.

Now `EquippedCardRepository.flexEntitledUserIds` is the one check (MVP card equipped, or
an Accession still running), game start drops a stale FLEX row before the lock, and
week-end scoring and the projection skip one.

Run: .venv/bin/python test_flex_expiry.py
"""
import sys
sys.path.insert(0, '/Users/andrew/Projects/floosball')
import logging; logging.disable(logging.CRITICAL)
import sqlalchemy
from sqlalchemy.orm import sessionmaker
from database.models import Base, Player, CardTemplate, UserCard, EquippedCard, ShopPurchase
from database.repositories.card_repositories import EquippedCardRepository
from managers.seasonManager import SeasonManager

failures = []
def expect(desc, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {desc}")
    if not cond:
        failures.append(desc)

SEASON = 12
eng = sqlalchemy.create_engine("sqlite://")
Base.metadata.create_all(eng)
s = sessionmaker(bind=eng)()

def card(cid, classification=None):
    s.add(Player(id=cid, name=f"P{cid}", team_id=1, position=2))
    s.add(CardTemplate(id=cid, player_id=cid, player_name=f"P{cid}", position=2, edition="base",
                       player_rating=80, season_created=SEASON, rarity_weight=1.0, sell_value=1,
                       classification=classification, effect_config={"effectName": "none"}))
    s.add(UserCard(id=cid, user_id=cid // 10, card_template_id=cid, acquired_via="pack"))

def equip(user, week, slotNumber, slot, cardId):
    s.add(EquippedCard(user_id=user, season=SEASON, week=week, slot_number=slotNumber,
                       slot=slot, user_card_id=cardId, locked=False))

# User 1: Accession weeks 2-5, FLEX card equipped in week 5 (last active week).
card(11); card(12)
s.add(ShopPurchase(user_id=1, item_slug="temp_card_slot", season=SEASON, week=2,
                   price_paid=200, expires_at_week=5))
equip(1, 5, 2, 'RB', 11); equip(1, 5, 7, 'FLEX', 12)
# User 2: same, but an MVP card in the lineup keeps the FLEX open.
card(21, classification="mvp"); card(22)
s.add(ShopPurchase(user_id=2, item_slug="temp_card_slot", season=SEASON, week=2,
                   price_paid=200, expires_at_week=5))
equip(2, 5, 2, 'RB', 21); equip(2, 5, 7, 'FLEX', 22)
# User 3: Accession still running in week 6.
card(31); card(32)
s.add(ShopPurchase(user_id=3, item_slug="temp_card_slot", season=SEASON, week=4,
                   price_paid=200, expires_at_week=7))
equip(3, 5, 2, 'RB', 31); equip(3, 5, 7, 'FLEX', 32)
s.commit()

repo = EquippedCardRepository(s)

print("1. Entitlement")
expect("week 5 (last Accession week): all three entitled",
       repo.flexEntitledUserIds(SEASON, 5, {1, 2, 3}) == {1, 2, 3})

print("2. Game start of week 6: carry forward, then drop the stale FLEX")
SeasonManager._carryForwardEquippedCards(None, s, repo, SEASON, 6)
s.commit()
expect("carry-forward copied every FLEX row (the old leak)",
       s.query(EquippedCard).filter_by(season=SEASON, week=6, slot_number=7).count() == 3)
expect("week 6: user 1 not entitled, users 2 (MVP) and 3 (active) are",
       repo.flexEntitledUserIds(SEASON, 6, {1, 2, 3}) == {2, 3})
removed = repo.dropStaleFlex(SEASON, 6)
s.commit()
expect(f"dropStaleFlex removed exactly one row (got {removed})", removed == 1)
wk6 = {(e.user_id, e.slot_number) for e in s.query(EquippedCard).filter_by(season=SEASON, week=6)}
expect("user 1 keeps RB, loses FLEX", (1, 2) in wk6 and (1, 7) not in wk6)
expect("users 2 and 3 keep FLEX", (2, 7) in wk6 and (3, 7) in wk6)
expect("a second run removes nothing", repo.dropStaleFlex(SEASON, 6) == 0)

print("3. Edge cases")
expect("empty user set -> empty", repo.flexEntitledUserIds(SEASON, 6, set()) == set())
expect("no FLEX rows -> nothing removed", repo.dropStaleFlex(SEASON, 99) == 0)

s.close()
print()
if failures:
    print(f">>> {len(failures)} FAILURE(S): {failures}")
    sys.exit(1)
print("PASS — an expired Accession's FLEX card leaves the lineup at game start.")

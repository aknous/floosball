"""Anomaly: equipped cards (the fusion fantasy lineup) actually drive attention.

Owner-reported (2026-07-29): 15 games into a live season, ZERO awakened players. Prod
queries showed every player's attention came only from fav-team fans / follows (top score
~40, below the 90 awaken bar); the equipped-card source contributed nothing all season.

Root cause: the weekly tick scoped equipped cards to `week=<tick week> AND locked=True`.
But the tick runs at week START — before the new week's cards are carried-forward or locked
— and a COMPLETED week's cards are UNLOCKED again. So the filter matched zero rows every
tick. Post-fusion the equipped cards ARE the fantasy roster, so this silently removed the
PRIMARY attention source (pre-fusion it came from FantasyRosterPlayer, never lock-gated).

Fix: count the latest equipped lineup that EXISTS at tick time (max week <= tick week),
without the locked gate. This test proves an equipped player on a completed UNLOCKED week
now accrues ATTENTION_PER_CARD_EQUIPPED, and sustained equipping reaches the awaken bar.

Run: .venv/bin/python test_anomaly_equipped_attention.py
"""
import sys
sys.path.insert(0, '/Users/andrew/Projects/floosball')
import logging; logging.disable(logging.CRITICAL)
import sqlalchemy
from sqlalchemy.orm import sessionmaker
from database.models import Base, Player, CardTemplate, UserCard, EquippedCard, PlayerAttention
import managers.anomalyManager as am

failures = []
def expect(desc, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {desc}")
    if not cond:
        failures.append(desc)

SEASON = 16
eng = sqlalchemy.create_engine("sqlite://")
Base.metadata.create_all(eng)
s = sessionmaker(bind=eng)()

# One player, depicted by one equipped card, fielded on a COMPLETED week (5) whose row is
# UNLOCKED — exactly the prod state the old filter missed.
s.add(Player(id=1, name="Star QB", team_id=1, position=1))
s.add(CardTemplate(id=1, player_id=1, player_name="Star QB", position=1, edition="base",
                   player_rating=90, season_created=SEASON, rarity_weight=1.0, sell_value=1,
                   effect_config={"effectName": "none"}))
s.add(UserCard(id=1, user_id=1, card_template_id=1, acquired_via="pack"))
s.add(EquippedCard(id=1, user_id=1, season=SEASON, week=5, slot_number=1,
                   user_card_id=1, locked=False))
s.commit()

print("1. An equipped card on a completed, UNLOCKED week contributes attention")
am._applyWeeklyContributions(s, SEASON, 6)   # tick for wk6 -> latest lineup = wk5
s.commit()
row = s.query(PlayerAttention).filter_by(player_id=1, season=SEASON).first()
got = row.score if row else 0.0
expect(f"one equipped card -> +{am.ATTENTION_PER_CARD_EQUIPPED} attention (got {got:.1f}, was 0 pre-fix)",
       abs(got - am.ATTENTION_PER_CARD_EQUIPPED) < 1e-6)

print("2. Sustained equipping climbs to the awaken bar")
for wk in range(7, 16):
    am._applyDecay(s, SEASON)
    am._applyWeeklyContributions(s, SEASON, wk)
    s.commit()
row = s.query(PlayerAttention).filter_by(player_id=1, season=SEASON).first()
expect(f"reaches the awaken bar {am.AWAKEN_THRESHOLD} after sustained fielding (got {row.score:.1f})",
       row.score >= am.AWAKEN_THRESHOLD)

print("3. No equipped lineup at all -> no equipped attention (no crash)")
s2 = sessionmaker(bind=eng)()
# A season with no equipped rows: max-week lookup returns None, loop is skipped cleanly.
am._applyWeeklyContributions(s2, 99, 3)
s2.commit()
expect("empty season ticks without error and grants no equipped attention",
       s2.query(PlayerAttention).filter_by(season=99).count() == 0)
s2.close()
s.close()

print()
if failures:
    print(f">>> {len(failures)} FAILURE(S): {failures}")
    sys.exit(1)
print("PASS — equipped cards drive attention again; players can awaken.")

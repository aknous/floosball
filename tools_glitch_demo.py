"""End-to-end glitch card demo against a DB copy.

Running a sim with Criticalities enabled is NOT enough to see glitch cards, and the reason
is easy to lose an afternoon to: a Criticality marks one of each user's EQUIPPED cards, and
`equipped_cards` is a per-(season, week) snapshot. A replayed prod copy has snapshots for
the weeks its users were actually playing — not for whatever week the sim has since reached
— so `markCardsForCriticality` correctly finds nothing and marks nothing.

This supplies the missing half: it equips a user for the current week, fires a Criticality
at that week, and then scores the week so the glitch line has something to render.

    .venv/bin/python tools_glitch_demo.py                  # uses a prod copy
    PROBE_DB=path/to.db .venv/bin/python tools_glitch_demo.py

Read-only against your real data — it copies the DB first and never touches the original.
"""
import os, shutil, sys, tempfile

SRC = os.environ.get('PROBE_DB', 'data/floosball_prod_latest.db')
tmp = tempfile.mkdtemp(prefix='floos_glitch_')
shutil.copy(SRC, os.path.join(tmp, 'floosball.db'))
os.environ['DATABASE_DIR'] = tmp
import logging
logging.disable(logging.WARNING)

from database.connection import get_session, init_db
init_db()
from database.models import (AnomalyState, CardTemplate, EquippedCard, UserCard)
from managers.glitchCards import (anomalyContextFor, markCardsForCriticality,
                                  rollSurge, surgePayout, triggerChance)
from sqlalchemy import func

s = get_session()
season = s.query(func.max(CardTemplate.season_created)).scalar()
week = 14

print(f"source: {SRC}")
print(f"season {season}, week {week}\n")

# ── 1. equip a user for this week ────────────────────────────────────────────
userId = s.query(UserCard.user_id).group_by(UserCard.user_id).order_by(
    func.count(UserCard.id).desc()).limit(1).scalar()
s.query(EquippedCard).filter_by(user_id=userId, season=season, week=week).delete()
s.flush()

cards = (s.query(UserCard).join(CardTemplate, UserCard.card_template_id == CardTemplate.id)
         .filter(UserCard.user_id == userId, CardTemplate.season_created == season)
         .limit(6).all())
if not cards:
    print("no current-season cards for any user in this DB — nothing to equip")
    sys.exit(1)
for i, uc in enumerate(cards):
    s.add(EquippedCard(user_id=userId, season=season, week=week,
                       slot_number=i + 1, user_card_id=uc.id, streak_count=1))
s.commit()
print(f"equipped {len(cards)} cards for user {userId}:")
for uc in cards:
    t = uc.card_template
    print(f"   {t.player_name:22} {t.edition:12} {(t.effect_config or {}).get('effectName','')}")

# ── 2. fire the Criticality ──────────────────────────────────────────────────
marked = markCardsForCriticality(s, season, week)
print(f"\nCriticality at S{season}W{week} -> marked {marked} card(s)")

glitched = (s.query(UserCard).filter(UserCard.user_id == userId,
                                     UserCard.glitched.is_(True)).all())
if not glitched:
    print("nothing was marked — check that the user has equipped cards for THIS week")
    sys.exit(1)

# ── 3. what the marked card will do ──────────────────────────────────────────
print("\nwhat the glitched card does from here:")
for uc in glitched:
    t = uc.card_template
    ctxm = anomalyContextFor([t.player_id], season, week)
    state, events = ctxm.get(t.player_id, ('stable', {}))
    print(f"\n   {t.player_name} ({t.edition}) — player is {state.upper()}"
          f"{', events this week: ' + str(dict(events)) if events else ', no events this week'}")
    print(f"   {'week':>6}{'chance':>9}{'result':>12}{'on a 28.3 FP card':>20}")
    for wk in range(week, week + 8):
        ctxw = anomalyContextFor([t.player_id], season, wk)
        st, ev = ctxw.get(t.player_id, ('stable', {}))
        chance = triggerChance(st, ev, 1.0)
        fired, outcome, mult = rollSurge(userId, season, wk, uc.id, chance)
        extraFp, _ = surgePayout(mult, 28.3, 0.0) if fired else (0.0, 0.0)
        res = outcome if fired else '—'
        print(f"   {wk:>6}{chance:>8.0%}{res:>12}{('+%.1f FP' % extraFp) if fired else '':>20}")

print(f"\nDB copy left at {tmp} if you want to poke at it.")

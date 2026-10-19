"""/api/bot/unsubmitted: who gets a Discord DM reminder, including the Showcase.

A user with reminders on and nothing featured in this season's Showcase is listed in
showcaseMissing; featuring even one card takes them off it. Only the current season's
Showcase counts (it starts empty every season).

Exercises the real handler via TestClient with bot auth and the season stubbed. Uses
the dev DB under a made-up season (9999), restores the two borrowed users' Discord
fields and deletes the showcase rows it adds.

Run: .venv/bin/python test_bot_unsubmitted.py   (exits non-zero on any failure)
"""
import sys, types
sys.path.insert(0,'/Users/andrew/Projects/floosball')
import logging; logging.disable(logging.CRITICAL)
if 'floosball_game' not in sys.modules:
    _s=types.ModuleType('floosball_game'); _s.Game=type('G',(),{})
    sys.modules['floosball_game']=_s
    import managers.timingManager  # noqa
    del sys.modules['floosball_game']
from fastapi.testclient import TestClient
import api.main as M
from database.connection import get_session
from database.models import User, ShowcaseSlot, UserCard

fails=[]
def expect(d,c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)

M.app.dependency_overrides[M._checkBotAuth] = lambda: None

SEASON = 9999
class FakeSeason: seasonNumber = SEASON; schedule = []; currentWeek = 1
class FakeSM:
    currentSeason = FakeSeason()
    def _getPickemWeek(self): return 1
class FakeApp: seasonManager = FakeSM()
M.floosball_app = FakeApp()

EMPTY, FILLED = '999000777001', '999000777002'
s = get_session()
for d in (EMPTY, FILLED):
    for u in s.query(User).filter(User.discord_id==d).all(): u.discord_id = None
s.commit()
users = s.query(User).order_by(User.id).limit(2).all()
saved = [(u.id, u.discord_id, u.discord_dm_reminders) for u in users]
users[0].discord_id, users[0].discord_dm_reminders = EMPTY, True
users[1].discord_id, users[1].discord_dm_reminders = FILLED, True
s.commit()
anyCard = s.query(UserCard).first()
c = TestClient(M.app)

def get():
    r = c.get('/api/bot/unsubmitted')
    return r.status_code, (r.json().get('data') or {})

try:
    print("1. Nobody has featured anything")
    code, d = get()
    expect(f"200 with a showcaseMissing list ({code})", code == 200 and isinstance(d.get('showcaseMissing'), list))
    expect("both reminder users are listed", {EMPTY, FILLED} <= set(d.get('showcaseMissing', [])))

    print("2. One user features a card")
    if anyCard is None:
        expect("dev DB has at least one user_card to feature", False)
    else:
        s.add(ShowcaseSlot(user_id=users[1].id, season=SEASON, slot_number=1, user_card_id=anyCard.id))
        s.commit()
        code, d = get()
        miss = set(d.get('showcaseMissing', []))
        expect("the user with a featured card drops off", FILLED not in miss)
        expect("the empty one is still listed", EMPTY in miss)
        expect("roster/picks lists unaffected", EMPTY in d.get('rosterMissing', []) and FILLED in d.get('picksMissing', []))

    print("3. Only this season's Showcase counts")
    FakeSeason.seasonNumber = SEASON + 1
    code, d = get()
    expect("last season's featured card doesn't count", FILLED in d.get('showcaseMissing', []))
    FakeSeason.seasonNumber = SEASON

    print("4. Reminders off → not listed")
    users[0].discord_dm_reminders = False; s.commit()
    code, d = get()
    expect("opted-out user isn't reminded", EMPTY not in d.get('showcaseMissing', []))
finally:
    s.query(ShowcaseSlot).filter(ShowcaseSlot.season.in_([SEASON, SEASON + 1])).delete(synchronize_session=False)
    for uid, did, dm in saved:
        u = s.get(User, uid); u.discord_id = did; u.discord_dm_reminders = dm
    s.commit(); s.close()

print(f"\n{'ALL PASSED' if not fails else f'{len(fails)} FAILED'}")
sys.exit(1 if fails else 0)

"""/api/bot/favorite-teams: linked Discord users and their favorite team (team roles).

Every linked user is listed, with team None when they have no favorite; a pending
(next-season) switch isn't reported; discordId narrows to one user; the bot key is
required.

Exercises the real handler via TestClient. Uses the dev DB, borrowing two users and
restoring their Discord and favorite-team fields afterwards.

Run: .venv/bin/python test_bot_favorite_teams.py   (exits non-zero on any failure)
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
from database.models import User, Team

fails=[]
def expect(d,c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)

FAN, NOFAV = '999000888001', '999000888002'
s = get_session()
for d in (FAN, NOFAV):
    for u in s.query(User).filter(User.discord_id==d).all(): u.discord_id = None
s.commit()
users = s.query(User).order_by(User.id).limit(2).all()
saved = [(u.id, u.discord_id, u.favorite_team_id, u.pending_favorite_team_id) for u in users]
teams = s.query(Team).order_by(Team.id).limit(2).all()
users[0].discord_id, users[0].favorite_team_id, users[0].pending_favorite_team_id = FAN, teams[0].id, teams[1].id
users[1].discord_id, users[1].favorite_team_id, users[1].pending_favorite_team_id = NOFAV, None, None
s.commit()
c = TestClient(M.app)

try:
    print("1. Bot key required")
    r = c.get('/api/bot/favorite-teams')
    expect(f"no key → rejected ({r.status_code})", r.status_code in (401, 403, 422))  # 422: required header missing

    M.app.dependency_overrides[M._checkBotAuth] = lambda: None
    print("2. All linked users")
    r = c.get('/api/bot/favorite-teams')
    rows = {x['discordId']: x for x in (r.json().get('data') or [])}
    expect(f"200 ({r.status_code})", r.status_code == 200)
    expect("fan listed with their favorite (not the pending switch)",
           (rows.get(FAN) or {}).get('team') == {'id': teams[0].id, 'name': teams[0].name, 'city': teams[0].city})
    expect("linked user without a favorite → team None", NOFAV in rows and rows[NOFAV]['team'] is None)
    expect("only linked users", all(x['discordId'] for x in rows.values()))

    print("3. discordId narrows to one user")
    r = c.get('/api/bot/favorite-teams', params={'discordId': FAN})
    data = r.json().get('data') or []
    expect("just that user", [x['discordId'] for x in data] == [FAN])
    r = c.get('/api/bot/favorite-teams', params={'discordId': '999000888999'})
    expect("unlinked id → empty list", r.json().get('data') == [])
finally:
    M.app.dependency_overrides.pop(M._checkBotAuth, None)
    for uid, did, fav, pend in saved:
        u = s.get(User, uid)
        u.discord_id, u.favorite_team_id, u.pending_favorite_team_id = did, fav, pend
    s.commit(); s.close()

print(f"\n{'ALL PASSED' if not fails else f'{len(fails)} FAILED'}")
sys.exit(1 if fails else 0)

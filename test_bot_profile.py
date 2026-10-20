"""/api/bot/profile: a linked Discord user's season at a glance (/me).

Ranks match the site's boards: fantasy from the tracker snapshot, pick'em from the
season board with its activity filter (logged in within the window), Showcase from
_showcaseStandings. A section is null when the user isn't on that board. Also checks
the refactored Showcase and pick'em leaderboards still answer.

Exercises the real handler via TestClient with bot auth and the season stubbed. Uses
the dev DB under a made-up season (9999); restores the two borrowed users' Discord and
last-login fields and deletes the picks it adds.

Run: .venv/bin/python test_bot_profile.py   (exits non-zero on any failure)
"""
import sys, types
from datetime import datetime, timedelta
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
from database.models import User, PickEmPick, UserCurrency, UserCard

fails=[]
def expect(d,c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)

M.app.dependency_overrides[M._checkBotAuth] = lambda: None

SEASON = 9999
s = get_session()
users = s.query(User).order_by(User.id).limit(3).all()
me, rival, gone = users
saved = [(u.id, u.discord_id, u.last_login_at) for u in users]
DID = '999000999101'
for u in s.query(User).filter(User.discord_id == DID).all(): u.discord_id = None
s.commit()
me.discord_id = DID
now = datetime.utcnow()
me.last_login_at = rival.last_login_at = now
gone.last_login_at = now - timedelta(days=365)   # off the live pick'em board
s.commit()

class FakeTracker:
    entries = []
    def getSnapshot(self, seasonNum=None): return {"entries": self.entries}
class FakeSeason: seasonNumber = SEASON; currentWeek = 5; activeGames = None
class FakeSM:
    currentSeason = FakeSeason()
    def _getPickemWeek(self): return 5
class FakeApp: seasonManager = FakeSM(); fantasyTracker = FakeTracker()
M.floosball_app = FakeApp()
M._isRegularSeason = lambda: True
realStandings = M._showcaseStandings

def pick(uid, correct, points):
    s.add(PickEmPick(user_id=uid, season=SEASON, week=1, game_index=len(s.new), home_team_id=1,
                     away_team_id=2, picked_team_id=1, correct=correct, points_earned=points))

c = TestClient(M.app)
def get(did=DID):
    r = c.get('/api/bot/profile', params={'discordId': did})
    return r.status_code, (r.json().get('data') or {})

try:
    print("1. Basics")
    expect("unlinked → 404", get('999000999199')[0] == 404)
    M._showcaseStandings = lambda session, season: []
    code, d = get()
    expect(f"200 with the user's name ({code})", code == 200 and d['username'] == me.username)
    cur = s.query(UserCurrency).filter_by(user_id=me.id).first()
    expect("floobits = wallet balance", d['floobits'] == (int(cur.balance) if cur else 0))
    owned = s.query(UserCard).filter_by(user_id=me.id).count()
    expect("card counts", d['cards']['owned'] == owned and 0 <= d['cards']['vaulted'] <= owned)
    expect("no boards yet → fantasy/pickem null, showcase empty",
           d['fantasy'] is None and d['pickem'] is None
           and d['showcase'] == {'featured': 0, 'slots': 8, 'grade': None, 'weeklyDividend': 0, 'rank': None, 'of': 0})
    a = d['achievements']
    expect("achievements completed ≤ total", isinstance(a['total'], int) and 0 <= a['completed'] <= a['total'])
    expect("supporter tier label", isinstance(d['supporter']['tier'], str) and d['supporter']['tier'])

    print("2. Fantasy from the tracker snapshot")
    FakeTracker.entries = [{"userId": rival.id, "rank": 1, "seasonTotal": 300.04, "weekTotal": 40},
                           {"userId": me.id, "rank": 2, "seasonTotal": 250.26, "weekTotal": 31.94}]
    f = get()[1]['fantasy']
    expect(f"rank 2 of 2, rounded points ({f})", f == {"rank": 2, "of": 2, "seasonPoints": 250.3, "weekPoints": 31.9})
    M._isRegularSeason = lambda: False
    expect("no week points outside the regular season", get()[1]['fantasy']['weekPoints'] is None)

    print("3. Pick'em: live board with the activity filter")
    pick(gone.id, True, 99); pick(gone.id, True, 99)
    pick(rival.id, True, 20)
    pick(me.id, True, 10); pick(me.id, False, 0); pick(me.id, None, 0)  # unresolved doesn't count
    s.commit()
    p = get()[1]['pickem']
    expect(f"inactive user dropped: rank 2 of 2 ({p})",
           p == {"rank": 2, "of": 2, "points": 10, "correct": 1, "total": 2, "accuracy": 50.0})

    print("4. Showcase standings")
    M._showcaseStandings = lambda session, season: [
        {"userId": rival.id, "rank": 1, "grade": "A", "weeklyDividend": 50, "cardCount": 8, "activeSets": []},
        {"userId": me.id, "rank": 2, "grade": "B", "weeklyDividend": 20, "cardCount": 5, "activeSets": []}]
    expect("rank, grade, dividend, featured", get()[1]['showcase'] ==
           {"featured": 5, "slots": 8, "grade": "B", "weeklyDividend": 20, "rank": 2, "of": 2})

    print("5. Refactored site leaderboards still answer")
    M._showcaseStandings = realStandings
    M.app.dependency_overrides[M._getCurrentUser] = lambda: me
    r = c.get('/api/cards/showcase/leaderboard')
    expect(f"showcase leaderboard 200 ({r.status_code})", r.status_code == 200 and r.json()['data']['leaderboard'] == [])
    r = c.get('/api/pickem/leaderboard')
    ents = r.json()['data']['season']['entries']
    expect(f"pick'em board drops the inactive user ({[e['userId'] for e in ents]})",
           [e['userId'] for e in ents] == [rival.id, me.id])
finally:
    M.app.dependency_overrides.pop(M._getCurrentUser, None)
    s.rollback()
    s.query(PickEmPick).filter(PickEmPick.season == SEASON).delete(synchronize_session=False)
    for uid, did, last in saved:
        u = s.get(User, uid); u.discord_id = did; u.last_login_at = last
    s.commit(); s.close()

print(f"\n{'ALL PASSED' if not fails else f'{len(fails)} FAILED'}")
sys.exit(1 if fails else 0)

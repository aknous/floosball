"""/api/bot/unvoted: open votes and which ones each reminder user hasn't cast.

Rule vote while its window is fired and unresolved; HoF from week 22 (only with an
active ballot) into the offseason; MVP from week 28 until the season completes. A
vote's key names its window/season. Users with reminders off aren't listed.

Exercises the real handler via TestClient with bot auth and the season stubbed. Uses
the dev DB under a made-up season (9999); restores the two borrowed users' Discord
fields and deletes the window and votes it adds.

Run: .venv/bin/python test_bot_unvoted.py   (exits non-zero on any failure)
"""
import sys, types
from datetime import datetime
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
from database.models import User, RuleVoteWindow, RuleVote, AwardVote, Player
from database.repositories.award_repository import HofBallotRepository

fails=[]
def expect(d,c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)

M.app.dependency_overrides[M._checkBotAuth] = lambda: None
SEASON = 9999
class FakeSeason: seasonNumber = SEASON; currentWeek = 10; isComplete = False
class FakeSM: currentSeason = FakeSeason(); _offseasonFlowPhase = None
class FakeApp: seasonManager = FakeSM()
M.floosball_app = FakeApp()
hofBallot = [object()]
HofBallotRepository.getActive = lambda self: hofBallot

A, B = '999000777101', '999000777102'
s = get_session()
for d in (A, B):
    for u in s.query(User).filter(User.discord_id == d).all(): u.discord_id = None
s.commit()
users = s.query(User).order_by(User.id).limit(2).all()
saved = [(u.id, u.discord_id, u.discord_dm_reminders) for u in users]
users[0].discord_id, users[0].discord_dm_reminders = A, True
users[1].discord_id, users[1].discord_dm_reminders = B, True
s.commit()
closes = datetime(2026, 10, 21, 16, 0)
window = RuleVoteWindow(season=SEASON, day_index=1, fired=True, kind='change', core='aris', closes_at=closes)
s.add(window); s.commit()
s.add(RuleVote(user_id=users[0].id, window_id=window.id, option_key='none'))
s.add(AwardVote(user_id=users[1].id, season=SEASON, award_type='mvp', target_player_id=s.query(Player.id).first()[0]))
s.commit()
RULE = f"rule:{window.id}"
c = TestClient(M.app)

def get():
    r = c.get('/api/bot/unvoted')
    return r.status_code, (r.json().get('data') or {})

try:
    print("1. Mid-season: just the rule vote")
    code, d = get()
    expect(f"200 ({code})", code == 200)
    expect("one vote: rule, labelled with its Core, closing at kickoff",
           [v['key'] for v in d['votes']] == [RULE] and d['votes'][0]['closesAt'] == '2026-10-21T16:00:00Z'
           and d['votes'][0]['label'].startswith('the rule change vote'))
    expect("A voted, B hasn't", A not in d['missing'] and d['missing'].get(B) == [RULE])

    print("2. Week 22: Hall of Fame opens")
    FakeSeason.currentWeek = 22
    d = get()[1]
    expect("A owes HoF, B owes rule + HoF", d['missing'].get(A) == [f"hof:{SEASON}"]
           and d['missing'].get(B) == [RULE, f"hof:{SEASON}"])
    hofBallot.clear()
    expect("empty HoF ballot → no HoF vote", f"hof:{SEASON}" not in [v['key'] for v in get()[1]['votes']])
    hofBallot.append(object())

    print("3. Week 28: MVP opens; B already voted MVP")
    FakeSeason.currentWeek = 28
    d = get()[1]
    expect("A owes HoF + MVP", sorted(d['missing'].get(A, [])) == sorted([f"hof:{SEASON}", f"mvp:{SEASON}"]))
    expect("B's MVP vote counts", f"mvp:{SEASON}" not in d['missing'].get(B, []))

    print("4. Rule window resolved; season complete (offseason)")
    window.resolved = True; s.commit()
    FakeSeason.isComplete = True; FakeSM._offseasonFlowPhase = 'frontoffice'
    d = get()[1]
    expect("only HoF stays open into the offseason", [v['kind'] for v in d['votes']] == ['hof'])
    FakeSM._offseasonFlowPhase = 'training'
    expect("closed once training starts", get()[1]['votes'] == [])

    print("5. Reminders off")
    FakeSM._offseasonFlowPhase = 'frontoffice'
    users[0].discord_dm_reminders = False; s.commit()
    expect("opted-out user isn't listed", A not in get()[1]['missing'])
finally:
    s.query(RuleVote).filter(RuleVote.window_id == window.id).delete(synchronize_session=False)
    s.query(AwardVote).filter(AwardVote.season == SEASON).delete(synchronize_session=False)
    s.delete(window)
    for uid, did, dm in saved:
        u = s.get(User, uid); u.discord_id = did; u.discord_dm_reminders = dm
    s.commit(); s.close()

print(f"\n{'ALL PASSED' if not fails else f'{len(fails)} FAILED'}")
sys.exit(1 if fails else 0)

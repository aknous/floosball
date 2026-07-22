"""Discord name-submission flow: bot endpoint -> review queue -> admin approve/reject.

A name suggested with /name must NOT reach the usable pool on its own — it waits in
`name_submissions` until an admin approves it, at which point it goes through the same
vetting as a name typed into the admin box. Rejected rows are kept (not deleted) so the
same name can't be resubmitted on a loop.

Exercises the real FastAPI handlers via TestClient with the auth dependencies stubbed.
Uses the dev DB but confines itself to 'ZZTest%' rows and cleans up after itself.

Run: .venv/bin/python test_name_submissions.py   (exits non-zero on any failure)
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
from database.models import User, NameSubmission, UnusedName

fails=[]
def expect(d,c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)

# Stub auth so we exercise the real handlers without real secrets
M.app.dependency_overrides[M._checkBotAuth] = lambda: None
M.app.dependency_overrides[M._checkAdminAuth] = lambda: None

class FakePM:
    def __init__(self): self.unusedNames=[]; self.name_repo=None; self.db_session=None
    def isNameInUse(self, n): return n.lower() == 'taken mcgee'
class FakeApp: playerManager = FakePM()
M.floosball_app = FakeApp()

s = get_session()
s.query(NameSubmission).filter(NameSubmission.name.like('ZZTest%')).delete(synchronize_session=False)
s.query(UnusedName).filter(UnusedName.name.like('ZZTest%')).delete(synchronize_session=False)
s.commit()
DISCORD='999000111222'
user = s.query(User).filter(User.discord_id==DISCORD).first()
created=False
if not user:
    user = s.query(User).first()
    prev = user.discord_id; user.discord_id = DISCORD; s.commit(); created=True
c = TestClient(M.app)

print("1. Submitting from Discord")
r = c.post('/api/bot/names', json={'discordId': DISCORD, 'name': '  ZZTest  Alpha  '})
expect(f"linked user can submit (got {r.status_code})", r.status_code == 200)
expect("whitespace collapsed to 'ZZTest Alpha'",
       (r.json().get('data') or {}).get('name') == 'ZZTest Alpha')
expect("it did NOT go straight into the pool", 'ZZTest Alpha' not in FakeApp.playerManager.unusedNames)

r = c.post('/api/bot/names', json={'discordId': 'not_linked_at_all', 'name': 'ZZTest Beta'})
expect(f"unlinked discord user is refused ({r.status_code})", r.status_code == 404)

print("2. Submit-time validation")
for nm, why, code in [('Z','too short',400), ('12345','no letters',400),
                      ('Taken McGee','already a live player/coach',409),
                      ('ZZTest Alpha','already suggested',409)]:
    rr = c.post('/api/bot/names', json={'discordId': DISCORD, 'name': nm})
    expect(f"rejects {why} ({rr.status_code})", rr.status_code == code)

print("3. Admin queue")
r = c.get('/api/admin/names/submissions?status=pending')
names = [x['name'] for x in r.json()['submissions']]
expect("submission appears in the pending queue", 'ZZTest Alpha' in names)
row = next(x for x in r.json()['submissions'] if x['name']=='ZZTest Alpha')
expect(f"attributed to the submitter ({row['submittedBy']})", bool(row['submittedBy']))

print("4. Approve -> enters the pool")
r = c.post('/api/admin/names/submissions/review', json={'ids':[row['id']], 'action':'approve'})
expect(f"approve reports 1 ({r.json()})", r.json().get('approved') == 1)
expect("name is now in the pool", 'ZZTest Alpha' in FakeApp.playerManager.unusedNames)
r = c.get('/api/admin/names/submissions?status=pending')
expect("and left the pending queue",
       'ZZTest Alpha' not in [x['name'] for x in r.json()['submissions']])

print("5. Reject -> kept on record, blocks resubmission")
c.post('/api/bot/names', json={'discordId': DISCORD, 'name': 'ZZTest Gamma'})
r = c.get('/api/admin/names/submissions?status=pending')
gid = next(x['id'] for x in r.json()['submissions'] if x['name']=='ZZTest Gamma')
r = c.post('/api/admin/names/submissions/review', json={'ids':[gid], 'action':'reject'})
expect(f"reject reports 1 ({r.json()})", r.json().get('rejected') == 1)
expect("rejected name did NOT enter the pool", 'ZZTest Gamma' not in FakeApp.playerManager.unusedNames)
r = c.get('/api/admin/names/submissions?status=rejected')
expect("row is kept with status rejected",
       'ZZTest Gamma' in [x['name'] for x in r.json()['submissions']])
rr = c.post('/api/bot/names', json={'discordId': DISCORD, 'name': 'ZZTest Gamma'})
expect(f"cannot be resubmitted ({rr.status_code})", rr.status_code == 409)

print("6. Name taken while queued stays pending (not silently lost)")
c.post('/api/bot/names', json={'discordId': DISCORD, 'name': 'ZZTest Delta'})
r = c.get('/api/admin/names/submissions?status=pending')
did = next(x['id'] for x in r.json()['submissions'] if x['name']=='ZZTest Delta')
FakeApp.playerManager.isNameInUse = lambda n: n.lower() in ('taken mcgee','zztest delta')
r = c.post('/api/admin/names/submissions/review', json={'ids':[did], 'action':'approve'})
expect(f"reported as unavailable ({r.json().get('unavailable')})",
       'ZZTest Delta' in (r.json().get('unavailable') or []))
r = c.get('/api/admin/names/submissions?status=pending')
expect("stays PENDING for a human decision",
       'ZZTest Delta' in [x['name'] for x in r.json()['submissions']])

# cleanup
s.query(NameSubmission).filter(NameSubmission.name.like('ZZTest%')).delete(synchronize_session=False)
s.query(UnusedName).filter(UnusedName.name.like('ZZTest%')).delete(synchronize_session=False)
if created: user.discord_id = prev
s.commit(); s.close()
print()
print("FAILURES:", fails if fails else "none")
raise SystemExit(1 if fails else 0)

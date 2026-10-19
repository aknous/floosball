"""Discord /link verification: request a code -> it lands in the account's notifications ->
only that code, from that Discord user, links the account.

Linking used to trust any username, so anyone could claim anyone's account. This checks
the code is required, single-use, bound to the Discord user who asked for it, expires,
locks out after repeated wrong guesses, and that the request is rate-limited per account.

Exercises the real FastAPI handlers via TestClient with bot auth stubbed. Uses the dev DB
but restores the borrowed user's Discord fields and deletes the notifications it creates.

Run: .venv/bin/python test_discord_link.py   (exits non-zero on any failure)
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
from database.models import User, UserNotification

fails=[]
def expect(d,c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)

M.app.dependency_overrides[M._checkBotAuth] = lambda: None

ME='999000333444'
STRANGER='999000555666'
s = get_session()
for d in (ME, STRANGER):
    for u in s.query(User).filter(User.discord_id==d).all(): u.discord_id = None
s.commit()
user = s.query(User).order_by(User.id).first()
prevId, prevDm = user.discord_id, user.discord_dm_reminders
user.discord_id = None; s.commit()
uid, uname = user.id, user.username
c = TestClient(M.app)

def latestCode():
    s.expire_all()
    n = (s.query(UserNotification).filter_by(user_id=uid, type='discord_link')
         .order_by(UserNotification.id.desc()).first())
    return n.title.rsplit(' ', 1)[-1] if n else None

def resetLimits():
    M._pendingLinkCodes.clear(); M._linkCodeLastIssued.clear()

def linkedTo():
    s.expire_all()
    return s.get(User, uid).discord_id

try:
    resetLimits()
    print("1. Requesting a code")
    r = c.post('/api/bot/link/request', json={'discordId': ME, 'username': 'zz_no_such_user_zz'})
    expect(f"unknown username is 404 ({r.status_code})", r.status_code == 404)
    r = c.post('/api/bot/link/request', json={'discordId': ME, 'username': '%'})
    expect(f"'%' is not a wildcard ({r.status_code})", r.status_code == 404)
    r = c.post('/api/bot/link/request',
               json={'discordId': ME, 'username': uname.upper(), 'discordName': 'tester'})
    expect(f"request for a real user works, case-insensitively ({r.status_code})", r.status_code == 200)
    code = latestCode()
    expect(f"a 6-character code landed in that user's notifications ({code})",
           bool(code) and len(code) == 6)
    expect("the request alone did not link anything", linkedTo() is None)
    r = c.post('/api/bot/link/request', json={'discordId': ME, 'username': uname})
    expect(f"a second request inside a minute is 429 ({r.status_code})", r.status_code == 429)

    print("2. Using the code")
    r = c.post('/api/bot/link', json={'discordId': ME, 'username': uname})
    expect(f"old code-less body is rejected ({r.status_code})", r.status_code == 422)
    r = c.post('/api/bot/link', json={'discordId': ME, 'username': uname, 'code': 'ZZZZZZ'})
    expect(f"wrong code is 400 ({r.status_code})", r.status_code == 400 and linkedTo() is None)
    r = c.post('/api/bot/link', json={'discordId': STRANGER, 'username': uname, 'code': code})
    expect(f"right code from a different Discord user is 400 ({r.status_code})",
           r.status_code == 400 and linkedTo() is None)
    r = c.post('/api/bot/link', json={'discordId': ME, 'username': uname, 'code': f' {code.lower()} '})
    expect(f"right code links, ignoring case/whitespace ({r.status_code})",
           r.status_code == 200 and linkedTo() == ME)
    r = c.post('/api/bot/link', json={'discordId': ME, 'username': uname, 'code': code})
    expect(f"the code is single-use ({r.status_code})", r.status_code == 400)
    r = c.post('/api/bot/link/request', json={'discordId': ME, 'username': uname})
    expect(f"requesting while already linked is 409 ({r.status_code})", r.status_code == 409)

    print("3. Guessing and expiry")
    resetLimits()
    r = c.post('/api/bot/link/request', json={'discordId': STRANGER, 'username': uname})
    code = latestCode()
    for _ in range(M._LINK_CODE_MAX_ATTEMPTS):
        c.post('/api/bot/link', json={'discordId': STRANGER, 'username': uname, 'code': 'ZZZZZZ'})
    r = c.post('/api/bot/link', json={'discordId': STRANGER, 'username': uname, 'code': code})
    expect(f"after {M._LINK_CODE_MAX_ATTEMPTS} wrong guesses even the right code fails ({r.status_code})",
           r.status_code == 400 and linkedTo() == ME)
    resetLimits()
    c.post('/api/bot/link/request', json={'discordId': STRANGER, 'username': uname})
    code = latestCode()
    M._pendingLinkCodes[(uid, STRANGER)]['expires'] = 0
    r = c.post('/api/bot/link', json={'discordId': STRANGER, 'username': uname, 'code': code})
    expect(f"an expired code fails ({r.status_code})", r.status_code == 400 and linkedTo() == ME)
finally:
    resetLimits()
    s.query(UserNotification).filter_by(user_id=uid, type='discord_link').delete(synchronize_session=False)
    u = s.get(User, uid); u.discord_id = prevId; u.discord_dm_reminders = prevDm
    s.commit(); s.close()

print(f"\n{'ALL PASSED' if not fails else f'{len(fails)} FAILED'}")
sys.exit(1 if fails else 0)

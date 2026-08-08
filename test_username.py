"""User-chosen usernames: validation, case-insensitive uniqueness, one rename a season.

The endpoint always accepted an arbitrary string — it was the frontend that only ever
offered four GENERATED candidates — so opening this up was never about the transport. What
was missing were the rules:

  - no format validation at all (spaces, punctuation, any length);
  - uniqueness was case-SENSITIVE, so "Andrew" and "andrew" were two accounts, which is an
    impersonation route rather than a convenience;
  - no way to change a name once set, at all.

Exercises the real FastAPI handler via TestClient with auth stubbed, against the dev DB,
confined to 'zzTest%' rows and cleaned up after itself.

Run: .venv/bin/python test_username.py   (exits non-zero on any failure)
"""
import sys, types
sys.path.insert(0, '/Users/andrew/Projects/floosball')
import logging; logging.disable(logging.CRITICAL)
if 'floosball_game' not in sys.modules:
    _s = types.ModuleType('floosball_game'); _s.Game = type('G', (), {})
    sys.modules['floosball_game'] = _s
    import managers.timingManager  # noqa
    del sys.modules['floosball_game']
from fastapi.testclient import TestClient
import api.main as M
from api.auth import validateUsername, usernameTaken
from database.connection import get_session
from database.models import User

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)


# ── the validator, no DB needed ─────────────────────────────────────────────
for bad, why in [("ab", "too short"), ("x" * 21, "too long"), ("1abc", "leading digit"),
                 ("_abc", "leading underscore"), ("Andrew Knous", "space"),
                 ("bob@home", "punctuation"), ("", "empty")]:
    v, e = validateUsername(bad)
    expect(f"rejects {why}: {bad!r}", v is None and e)

for good in ("Andrew", "good_name7", "aB3", "x" * 20):
    v, e = validateUsername(good)
    expect(f"accepts {good!r}", v == good and e is None)

# Impersonation is the reason these are blocked, not tone: a user called "Cassian" posting
# in a feed that also carries real Cores lines is indistinguishable from the Core.
for reserved in ("admin", "ADMIN", "Cassian", "vera", "floosball"):
    v, e = validateUsername(reserved)
    expect(f"reserves {reserved!r}", v is None and "reserved" in (e or ""))

v, e = validateUsername("shitlord")
expect("blocks the obvious slurs", v is None)

# ── the endpoint ────────────────────────────────────────────────────────────
M.app.dependency_overrides[M._getCurrentUser] = lambda: _stubUser
client = TestClient(M.app)

session = get_session()
session.query(User).filter(User.email.like('zzTest%')).delete(synchronize_session=False)
session.commit()

u1 = User(email='zzTest1@example.com', username=None)
u2 = User(email='zzTest2@example.com', username='zzTaken')
session.add_all([u1, u2]); session.commit()
u1Id, u2Id = u1.id, u2.id
_stubUser = u1


def post(name):
    return client.post("/api/users/me/username", json={"username": name})


try:
    r = post("Andrew Knous")
    expect("endpoint rejects an invalid name with 400", r.status_code == 400)

    r = post("zzFirstPick")
    expect(f"first pick succeeds ({r.status_code})", r.status_code == 200)
    expect("first pick is not counted as a change", r.json().get("changed") is False)

    # Case-insensitive: this is the impersonation guard, and the column's own unique
    # constraint does NOT provide it.
    _stubUser = session.get(User, u1Id)
    r = post("ZZTAKEN")
    expect(f"a name differing only in case is taken ({r.status_code})", r.status_code == 409)
    expect("...and the case-insensitive helper agrees", usernameTaken(session, "zztaken"))

    # Rename, then the season limit.
    r = post("zzRenamed")
    expect(f"a rename succeeds ({r.status_code})", r.status_code == 200)
    expect("...and IS counted as a change", r.json().get("changed") is True)

    _stubUser = session.get(User, u1Id)
    r = post("zzAgain")
    expect(f"a second rename in the same season is refused ({r.status_code})",
           r.status_code == 429)

    # Re-submitting the SAME name is a no-op, not a spent rename — otherwise an
    # idempotent client retry burns the user's one change for the season.
    _stubUser = session.get(User, u1Id)
    r = post("zzRenamed")
    expect(f"re-submitting the current name is a no-op ({r.status_code})",
           r.status_code == 200 and r.json().get("changed") is False)

    session.expire_all()
    expect("the name actually persisted",
           session.get(User, u1Id).username == "zzRenamed")
finally:
    session.query(User).filter(User.email.like('zzTest%')).delete(synchronize_session=False)
    session.commit()
    session.close()

print("\nPASS — names are validated, unique regardless of case, and renameable once a season."
      if not fails else f"\n{len(fails)} FAILED")
sys.exit(1 if fails else 0)

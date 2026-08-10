"""The admin grant tool must not mint a position-exclusive effect onto the wrong player.

A QB-only effect on a receiver is a PERMANENTLY DEAD card: it reads a stat that position
never records, so it scores zero forever and no amount of production fixes it. Worse, the
detail line can come out with an unresolved {placeholder}, which is the one condition that
makes the calculator rebuild stored params at score time.

The transplant path has always guarded this (`effectValidPositions`, cardManager:1221).
The grant tool never did, so `forceEffect` walked straight past the position pool. It was
found the honest way: three granted cards landed on a WR, a WR and an RB.

Exercises the real FastAPI handler via TestClient with auth stubbed. Touches no DB rows —
every rejection path returns before the session opens.

Run: .venv/bin/python test_admin_grant_position.py   (exits non-zero on any failure)
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
from managers.cardEffects import effectValidPositions, EFFECT_EDITION_TIER

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)

M.app.dependency_overrides[M._checkAdminAuth] = lambda: None


class FakePos:
    def __init__(self, v): self.value = v

class FakeTeam:
    id = 3

class FakePlayer:
    def __init__(self, pid, name, pos, rating=92):
        self.id = pid; self.name = name; self.position = FakePos(pos)
        self.playerRating = rating; self.team = FakeTeam()
        self.is_prospect = False; self.drafting_team_id = None
        self.is_upcoming_rookie = False

ROSTER = {1: FakePlayer(1, 'Arm Strongman', 1),
          3: FakePlayer(3, 'Mustang Hotfuss', 3),
          2: FakePlayer(2, 'Nimble Postcards', 2)}

class FakePM:
    activePlayers = list(ROSTER.values())
    def getPlayerById(self, pid): return ROSTER.get(pid)

class FakeSM:
    currentSeason = type('S', (), {'seasonNumber': 1})()

class FakeApp:
    playerManager = FakePM(); seasonManager = FakeSM()

M.floosball_app = FakeApp()
client = TestClient(M.app)


def grant(**kw):
    body = {"email": "nobody@example.com"}
    body.update(kw)
    return client.post("/api/admin/grant-card", json=body)


# ── the reported bug ─────────────────────────────────────────────────────────
for eff, ed in (("bombardier", "metallic"), ("salvo", "holographic"), ("barrage", "prismatic")):
    r = grant(playerId=3, edition=ed, effectName=eff)
    expect(f"{eff} onto a WR is refused",
           r.status_code == 400 and "only works on QB" in r.json().get("detail", ""))

# The message must name the player and say WHY, or the admin just retries.
r = grant(playerId=3, edition="metallic", effectName="bombardier")
d = r.json().get("detail", "")
expect("rejection names the player and the consequence",
       "Mustang Hotfuss" in d and "score zero" in d)

# ── it is not just the new cards: shipped exclusives had the same hole ───────
for eff, pos, who in (("gunslinger", 3, "WR"), ("workhorse", 3, "WR"), ("pinpoint", 2, "RB")):
    r = grant(playerId=pos if pos != 3 else 3, edition=EFFECT_EDITION_TIER[eff], effectName=eff)
    expect(f"{eff} onto a {who} is refused", r.status_code == 400)

# ── the valid case still works up to the point of the DB ────────────────────
r = grant(playerId=1, edition="metallic", effectName="bombardier")
expect("bombardier onto a QB passes the position guard",
       "only works on" not in r.json().get("detail", ""))

# ── a shared effect is unconstrained ────────────────────────────────────────
r = grant(playerId=3, edition="metallic", effectName="freebie")
expect("a shared effect still goes on any position",
       "only works on" not in r.json().get("detail", ""))

# ── no playerId: the random pick must respect the forced effect ─────────────
# Without this the tool silently hands back a dead card instead of erroring, which is
# how the three bad grants happened in the first place.
for _ in range(12):
    r = grant(edition="metallic", effectName="bombardier")
    if "only works on" in r.json().get("detail", ""):
        expect("random pick never lands a QB effect on a non-QB", False); break
else:
    expect("random pick never lands a QB effect on a non-QB", True)

# ── card-options tells the UI which positions each effect allows ────────────
opts = client.get("/api/admin/card-options").json()["data"]["effects"]
allEffects = [e for group in opts.values() for e in group]
expect("card-options reports validPositions",
       all("validPositions" in e for e in allEffects))
byName = {e["name"]: e for e in allEffects}
expect("bombardier is advertised as QB-only", byName.get("bombardier", {}).get("validPositions") == [1])
# A shared effect reports all five rather than an empty list — same shape cardManager:915
# already returns for the transplant UI, so the picker can filter on it uniformly.
expect("a shared effect advertises every position",
       byName.get("freebie", {}).get("validPositions") == [1, 2, 3, 4, 5])

print("\nPASS — a position-exclusive effect cannot be granted onto a player who can't feed it."
      if not fails else f"\n{len(fails)} FAILED")
sys.exit(1 if fails else 0)

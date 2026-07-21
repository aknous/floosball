"""Innings conversion-gated continuation regression suite (docs/INNINGS_REDESIGN_PLAN.md).

Locks in the correctness invariants (not balance): a TD whose TOP conversion is MADE
keeps the batting team's at-bat alive without consuming a try; a kick / lesser rung /
miss consumes a try; a per-at-bat safety cap bounds continuations; and full games under
ladder OFF and ladder ON always terminate with continuations self-limiting.

Run: .venv/bin/python test_innings_continuation.py   (exits non-zero on any failure)
"""
import sys, types, asyncio, random
sys.path.insert(0, '/Users/andrew/Projects/floosball')
import logging; logging.disable(logging.CRITICAL)
if 'floosball_game' not in sys.modules:
    _stub = types.ModuleType('floosball_game'); _stub.Game = type('G', (), {})
    sys.modules['floosball_game'] = _stub
    import managers.timingManager  # noqa
    del sys.modules['floosball_game']
import floosball_game as FG
import game_formats as GFMT
import constants
from types import SimpleNamespace
from managers.timingManager import TimingManager, TimingMode
from game_rules import GameRules
from scenario import Scenario, _makeTeam

failures = []
def expect(desc, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {desc}")
    if not cond:
        failures.append(desc)


# ── 1. possessionReceiver continuation semantics (unit) ──────────────────
print("1. possessionReceiver: a made-top-conversion continuation skips the try")
fmt = GFMT.InningsFormat()
def mkStub():
    g = SimpleNamespace(_inningsTries=0, _inningsContinue=False, _inningsContinues=0,
                        _inningsHalf='top', _inningsNumber=1, gameFeed=[],
                        gameRules=SimpleNamespace(triesPerInning=3, inningsPerGame=3),
                        homeTeam='H', awayTeam='A')
    g._maybeReadjustGameplans = lambda _x: None
    return g

# continuation: try NOT consumed, ball stays with the batting team (giver)
g = mkStub(); g._inningsTries = 1; g._inningsContinue = True
r = fmt.possessionReceiver(g, 'BAT', 'FIELD')
expect("continuation keeps the ball with the batting team", r == 'BAT')
expect("continuation does NOT consume a try (tries stays 1)", g._inningsTries == 1)
expect("continuation increments the continuation counter", g._inningsContinues == 1)
expect("continuation clears the one-shot flag", g._inningsContinue is False)

# a NON-continuation (flag off) consumes a try
g = mkStub(); g._inningsTries = 0; g._inningsContinue = False
r = fmt.possessionReceiver(g, 'BAT', 'FIELD')
expect("non-continuation consumes a try (0 -> 1)", g._inningsTries == 1 and r == 'BAT')

# the safety cap: once continuations hit the cap, a would-be continuation consumes a try
g = mkStub(); g._inningsTries = 0
g._inningsContinues = constants.INNINGS_MAX_CONTINUATIONS   # cap already reached
g._inningsContinue = True
r = fmt.possessionReceiver(g, 'BAT', 'FIELD')
expect("at the cap, a continuation instead consumes a try (bounded at-bat)", g._inningsTries == 1)

# 3rd try consumed → at-bat flips to the other team AND resets the continuation counter
g = mkStub(); g._inningsTries = 2; g._inningsContinues = 4; g._inningsContinue = False
r = fmt.possessionReceiver(g, 'BAT', 'FIELD')
expect("at-bat over (3rd try) flips to the fielding team", r == 'FIELD')
expect("at-bat flip resets the continuation counter", g._inningsContinues == 0)


# ── 2. Full games terminate + self-limit, ladder OFF and ON ──────────────
def playSome(n, ladder, seed0=0):
    random.seed(seed0)
    conts = 0; maxCap = 0; completed = 0
    orig = GFMT.InningsFormat.possessionReceiver
    box = {'c': 0}
    def wrap(self, game, giver, receiver):
        was = getattr(game, '_inningsContinue', False)
        tb = getattr(game, '_inningsTries', 0)
        r = orig(self, game, giver, receiver)
        if was and r is giver and getattr(game, '_inningsTries', 0) == tb:
            box['c'] += 1
        return r
    GFMT.InningsFormat.possessionReceiver = wrap
    try:
        for i in range(n):
            rr = random.Random(seed0 * 1000 + i)
            home = _makeTeam('H', 'HOM', 1000 + i*10, phys=rr.randint(74, 92), ment=rr.randint(74, 92))
            away = _makeTeam('A', 'AWY', 5000 + i*10, phys=rr.randint(74, 92), ment=rr.randint(74, 92))
            gr = GameRules(); gr.gameFormat = 'innings'
            if ladder:
                gr.conversionLadderEnabled = True
            g = FG.Game(home, away, gameRules=gr, timingManager=TimingManager(TimingMode.FAST))
            g.id = i
            asyncio.run(asyncio.wait_for(g.playGame(), timeout=30))
            completed += 1
            maxCap = max(maxCap, getattr(g, '_inningsContinues', 0))
        conts = box['c']
    finally:
        GFMT.InningsFormat.possessionReceiver = orig
    return completed, conts, maxCap

print("2. Full innings games terminate and self-limit — ladder OFF")
c, conts, mx = playSome(15, ladder=False, seed0=1)
expect(f"all 15 ladder-off games completed (no hang/crash)", c == 15)
expect(f"continuations occur ({conts} > 0)", conts > 0)
expect(f"at-bat continuations never exceed the cap (max {mx} <= {constants.INNINGS_MAX_CONTINUATIONS})",
       mx <= constants.INNINGS_MAX_CONTINUATIONS)

print("3. Full innings games terminate and self-limit — ladder ON")
c, conts, mx = playSome(15, ladder=True, seed0=2)
expect(f"all 15 ladder-on games completed (no hang/crash)", c == 15)
expect(f"continuations occur under the ladder ({conts} > 0)", conts > 0)
expect(f"at-bat continuations never exceed the cap (max {mx} <= {constants.INNINGS_MAX_CONTINUATIONS})",
       mx <= constants.INNINGS_MAX_CONTINUATIONS)


# ── 4. Mandatory conversion decision on the last scoring chance ──────────
print("4. Post-TD conversion is forced on the last try of the final at-bat")
def _irules():
    gr = GameRules(); gr.gameFormat = 'innings'; gr.inningsPerGame = 3; gr.triesPerInning = 3
    return gr
def goRate(*, half, home, away, tries=2, inning=3, offense='home', trials=40):
    """Fraction of trials the real _chooseConversion picks a go-for-it rung (vs the kick),
    with scores set AFTER the TD. Home bats bottom, away bats top."""
    s = Scenario(gameRules=_irules()); k = 0
    for _ in range(trials):
        s.situation(offense=offense, offScore=(home if offense == 'home' else away),
                    defScore=(away if offense == 'home' else home))
        g = s.g; g._inningsNumber = inning; g._inningsHalf = half; g._inningsTries = tries
        team = g.homeTeam if offense == 'home' else g.awayTeam
        if g._chooseConversion(team)['kind'] == 'go':
            k += 1
    return k / trials

# The reported bug: down 2 after the TD on the last try → a kick loses, the 2-pt ties → MUST go.
expect("last try, down 2 after TD (kick loses, 2pt ties) → ALWAYS goes for 2",
       goRate(half='bottom', home=28, away=30) == 1.0)
# Inverse: a safe kick that walks it off (bottom, takes the lead) → never gamble it.
expect("last try, tied after TD (kick walks it off) → NEVER gambles, kicks the win",
       goRate(half='bottom', home=30, away=30) == 0.0)
# Not forced when a kick already ties (down 1) — a genuine gamble-for-the-win vs safe-tie choice.
_r = goRate(half='bottom', home=29, away=30)
expect(f"last try, down 1 after TD (kick ties) → not forced either way (rate {_r:.2f})", 0.0 < _r < 1.0)
# Not the last chance → not forced (earlier try, same deficit).
_r0 = goRate(half='bottom', home=28, away=30, tries=0)
expect(f"NOT last try, down 2 → not forced (heuristic, rate {_r0:.2f})", _r0 < 1.0)
# Top of the last inning: taking the lead does NOT end the game (home still bats), so a
# 1-point lead after the TD isn't a walk-off → not forced-to-kick.
_rt = goRate(half='top', home=29, away=30, offense='away')
expect(f"top of last inning, away +1 after TD → not forced-kick (rate {_rt:.2f})", _rt > 0.0)


print()
if failures:
    print(f"FAILED: {len(failures)} check(s):")
    for f in failures:
        print("  -", f)
    raise SystemExit(1)
print("All innings continuation checks passed.")

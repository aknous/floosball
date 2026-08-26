"""A finished darts game says what IT was played under, not what the league is doing now.

`games.format_state` exists so a completed game can still describe its own format after a
restart — the state is only ever computed live, so there is no other source for it. Darts
wrote NOTHING: `BustFormat` had no `stateExtra()` and inherited the base `{}`, so
`_applyFormatStateToRow` had nothing to persist. Measured on production, the column was
NULL on all 192 darts games of the season, and it is not backfillable.

⚠️ THE DAMAGE IS WORSE THAN A MISSING BOX SCORE, because the client fell back to the
league's CURRENT ruleset for the target. Rules are votable. Vote the format away and the
darts row vanishes from the games played under it; vote the target from 24 to 18 and every
historical game claims it was chasing 18. A game has to carry its own win condition or it
misreports itself the moment the league moves on.

⚠️ `landed` is the fact the scores cannot carry. Ending ON the target is winning the
FORMAT; running out of clock is merely leading. Telling those apart afterwards means
comparing a final score against a target nobody wrote down — the same problem one layer
down. Overtime is flagged for the same reason: darts rules are OFF there, so a game that
reached OT was not decided by the target at all.

Run: .venv/bin/python test_darts_state_persisted.py   (exits non-zero on any failure)
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.WARNING)

from scenario import Scenario
from game_rules import GameRules
from constants import GAME_FORMAT_PRESETS
import game_formats as GF

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)

DARTS = next(p for p in GAME_FORMAT_PRESETS if 'Darts' in (p.get('label') or ''))

def game(homeScore, awayScore, quarter=4, target=None, hoops=(0, 0)):
    gr = GameRules()
    for k, v in DARTS['patch'].items():
        setattr(gr, k, v)
    if target is not None:
        gr.targetScore = target
    s = Scenario(gameRules=gr)
    g = s.game
    g.homeScore, g.awayScore, g.currentQuarter = homeScore, awayScore, quarter
    g.homeSidelineGoals, g.awaySidelineGoals = hoops
    return g

def info(g):
    return (g.format.stateExtra(g) or {}).get('gameFormatInfo')

# ── 1. it emits at all ──────────────────────────────────────────────────────
# ⚠️ The whole bug: inheriting the base `{}` means `_applyFormatStateToRow` skips the row
# (`if extra:`), so nothing is written and nothing raises.
print("\n-- darts emits a format block --")
g = game(24, 17)
expect("stateExtra is not empty", bool(g.format.stateExtra(g)))
expect("and carries a gameFormatInfo block", info(g) is not None)
expect("declaring the format by name", info(g).get('format') == 'bust')

# ── 2. the game carries its OWN target ──────────────────────────────────────
# ⚠️ Asserted at a NON-DEFAULT target, because reading the league's live rules gives the
# right answer by accident whenever they happen to match.
print("\n-- the target travels with the game, not with the league --")
g18 = game(18, 11, target=18)
expect(f"a game played at 18 reports 18 ({info(g18).get('targetScore')})",
       info(g18).get('targetScore') == 18)
expect("and its to-go figures are measured against ITS target",
       info(g18).get('homeToGo') == 0 and info(g18).get('awayToGo') == 7)

# ── 3. landed vs the clock ──────────────────────────────────────────────────
print("\n-- how the game was decided --")
expect("a winner sitting exactly on the target reports landed",
       info(game(24, 17)).get('landed') == 'home')
expect("from either side", info(game(17, 24)).get('landed') == 'away')
expect("and a game short of it reports no landing",
       info(game(22, 17)).get('landed') is None)
# ⚠️ Darts rules are off in overtime, so the target did not decide an OT game even if a
# score happens to sit on it.
expect("overtime is flagged, since darts rules are off there",
       info(game(24, 22, quarter=5)).get('overtime') is True
       and info(game(24, 22, quarter=4)).get('overtime') is False)

# ── 4. the hoops, which nothing else counts ─────────────────────────────────
# The 1-point hoop is the format's precision instrument (BustFormat.bundledRules), and the
# team box score has no column for it.
print("\n-- the hoops are recorded --")
h = info(game(24, 20, hoops=(3, 1)))
expect(f"per-side hoop counts survive ({h.get('homeHoops')}/{h.get('awayHoops')})",
       h.get('homeHoops') == 3 and h.get('awayHoops') == 1)

# ── 5. it survives the round trip the column actually takes ─────────────────
# ⚠️ Exercised through JSON, because that is what `_applyFormatStateToRow` writes and what
# the read path parses back. A block that cannot serialize is the same outage as no block.
print("\n-- it round-trips as JSON, the way the column stores it --")
try:
    blob = json.dumps(g.format.stateExtra(g))
    back = json.loads(blob).get('gameFormatInfo')
    ok = back == info(g)
except Exception as exc:
    blob, back, ok = None, None, False
    print("      serialization raised:", exc)
expect("the block serializes and parses back identically", ok)

# ── 6. every clock format still answers, and standard stays silent ──────────
# ⚠️ `_applyFormatStateToRow` treats an empty dict as "nothing to persist", which is
# CORRECT for standard (its breakdown is the quarter-score columns) and was the bug for
# darts. Pin both halves so the distinction stays deliberate.
print("\n-- and the distinction from a standard game is deliberate --")
std = Scenario(gameRules=GameRules()).game
expect("standard emits nothing, as its quarters already carry the breakdown",
       not std.format.stateExtra(std))
missing = [k for k in GF._FORMATS
           if k != 'standard' and not GF.getFormat(k).stateExtra.__qualname__.startswith(
               GF.getFormat(k).__class__.__name__)]
expect(f"no non-standard format is still inheriting the empty base ({missing})",
       not missing)

print()
if fails:
    print(f"FAIL — {len(fails)} problem(s):")
    for f in fails:
        print(f"  - {f}")
    sys.exit(1)
print("PASS — a darts final carries its own target, how it was won, and its hoops.")

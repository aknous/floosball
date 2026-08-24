"""The Showcase's rookie legacy premium counts two award lists that are DIFFERENT SHAPES.

⚠️ THE PRODUCTION 500 (2026-08-24). `buildLegacyLookup` filtered both lists with
`s > rookieSeason`. `players.all_pro_seasons` is a list of bare ints and that works; but
`players.mvp_awards` holds DICTS — `{'Season': N, 'team': abbr, 'teamColor': …}`, written
that way by `seasonManager` so the Hall of Fame can show which team a player won it with.
So the comparison raised:

    TypeError: '>' not supported between instances of 'dict' and 'int'

and took `/api/cards/showcase/leaderboard` down. The browser reported it as a CORS failure,
because FastAPI cannot attach CORS headers to an unhandled exception — the missing header
was the symptom, the TypeError was the fault.

⚠️ IT WAS LATENT FOR THE WHOLE LIFE OF THE FEATURE. Both conditions have to hold before
the comparison is reached: the card must be a ROOKIE print (so `rookieSeason` is truthy)
AND its player must have won an MVP since it was printed. Until someone put such a card in
their Showcase, the endpoint was fine. A test over the SHAPES rather than over live data is
the only thing that would have caught it early, which is what this is.

Run: .venv/bin/python test_showcase_legacy_awards.py   (exits non-zero on any failure)
"""
import sys
sys.path.insert(0, '/Users/andrew/Projects/floosball')
import logging; logging.disable(logging.CRITICAL)

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)

from managers.showcaseManager import _earnedAfter

# ── the shape that crashed ────────────────────────────────────────────────
MVP = {'Season': 12, 'team': 'GAC', 'teamColor': '#3F51B5'}

expect("an MVP dict earned AFTER the rookie season counts",
       _earnedAfter(MVP, 9) is True)
expect("an MVP dict earned BEFORE it does not",
       _earnedAfter(MVP, 14) is False)
expect("an MVP dict earned IN the rookie season does not (it is not a legacy)",
       _earnedAfter({'Season': 9}, 9) is False)

# ── the shape that always worked, and must keep working ───────────────────
expect("a bare All-Pro season after the rookie season counts",
       _earnedAfter(12, 9) is True)
expect("a bare All-Pro season before it does not",
       _earnedAfter(9, 12) is False)

# ── no rookie season means no filter at all ───────────────────────────────
expect("with no rookie season every accolade counts (dict)",
       _earnedAfter(MVP, 0) is True)
expect("with no rookie season every accolade counts (int)",
       _earnedAfter(3, 0) is True)

# ── malformed entries must not raise ──────────────────────────────────────
# ⚠️ The whole defect was an unhandled shape, so the fallback must never be another one.
for junk in (None, {}, {'season': 12}, 'twelve', [], {'Season': None}):
    try:
        result = _earnedAfter(junk, 9)
    except Exception as e:
        expect(f"a malformed entry {junk!r} does not raise", False)
    else:
        expect(f"a malformed entry {junk!r} is not counted as a legacy",
               result is False)

# ── the caller no longer compares raw entries ─────────────────────────────
# ⚠️ CHECKED WITH THE AST, NOT A SUBSTRING SEARCH. The fix's own docstring quotes the
# offending comparison in order to explain it, so `'s > rookieSeason' not in src` matches
# the EXPLANATION and reports the bug as still live. Parsing asks the real question: does
# the function body still compare an award entry to the rookie season directly?
import ast
src = open('/Users/andrew/Projects/floosball/managers/showcaseManager.py').read()
tree = ast.parse(src)
fn = next(n for n in ast.walk(tree)
          if isinstance(n, ast.FunctionDef) and n.name == 'buildLegacyLookup')
directCompares = [
    n for n in ast.walk(fn)
    if isinstance(n, ast.Compare)
    and any(isinstance(o, (ast.Gt, ast.GtE)) for o in n.ops)
    and any(isinstance(c, ast.Name) and c.id == 'rookieSeason'
            for c in n.comparators)
]
expect("buildLegacyLookup no longer compares an award entry directly",
       directCompares == [])
calls = [n for n in ast.walk(fn)
         if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
         and n.func.id == '_earnedAfter']
expect("both award lists go through the same reader", len(calls) == 2)

print("\nPASS — both award shapes are read, and a bad one cannot take the endpoint down."
      if not fails else f"\n{len(fails)} FAILED")
sys.exit(1 if fails else 0)

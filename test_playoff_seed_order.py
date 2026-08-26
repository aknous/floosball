"""The bracket honours the frozen seeds: division winners 1-4, wildcards 5-8.

Reported: playoff seeding looked like pure win% order. It was. The field is built
division-first -- `_applyDivisionSeeding` gives the four division winners seeds 1-4
whatever their records, then the best four remaining take 5-8 -- and `_freezePlayoffSeeds`
stamps exactly that. One screen later the round loop re-sorted the survivors by RECORD,
every round, which sorted those winners straight back out of the top seeds. A division
title was a label on the standings board and bought nothing in the bracket.

⚠️ THREE PLACES SORT THIS FIELD and they must agree, which is why CLAUDE.md recorded the
fix as all-or-nothing: the engine's round loop, `playoff_bracket._seedSort` (the
challenge's scoring/projection), and `utils/bracketProjection.ts` (the same projection in
the browser). Fixing one re-creates the projection-vs-sim divergence the mirror exists to
prevent.

Run: ./run_tests.sh playoff_seed_order
"""
import sys, os, re, io
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.WARNING)
from playoff_bracket import _seedSort, pairTopVsBottom

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)


def entry(seed, teamId, winPct, scoreDiff=0):
    return {'seed': seed, 'teamId': teamId, 'winPct': winPct,
            'scoreDiff': scoreDiff, 'teamName': f'T{teamId}'}


# A realistic field: a weak division winner seeded above strong wildcards. This is the
# whole point of division seeding and exactly what a record sort destroys.
field = [
    entry(1, 10, 0.750), entry(2, 20, 0.714), entry(3, 30, 0.679),
    entry(4, 40, 0.500),                      # weak division winner
    entry(5, 50, 0.714), entry(6, 60, 0.679), # wildcards with BETTER records than seed 4
    entry(7, 70, 0.607), entry(8, 80, 0.571),
]

ordered = _seedSort(field)
expect(f"the field sorts by seed, not by record ({[e['seed'] for e in ordered]})",
       [e['seed'] for e in ordered] == [1, 2, 3, 4, 5, 6, 7, 8])
expect("a weak division winner stays ahead of stronger wildcards",
       ordered[3]['teamId'] == 40)

# ⚠️ The pairing is what a reader actually sees: 1v8, 2v7, 3v6, 4v5.
pairs = pairTopVsBottom(field)
expect(f"round 1 pairs 1v8, 2v7, 3v6, 4v5 ({[(a['seed'], b['seed']) for a, b in pairs]})",
       [(a['seed'], b['seed']) for a, b in pairs] == [(1, 8), (2, 7), (3, 6), (4, 5)])

# Survivors re-seed by their ORIGINAL seed, which is what "re-seeds every round" means.
survivors = [e for e in field if e['seed'] in (1, 4, 6, 7)]
pairs = pairTopVsBottom(survivors)
expect(f"round 2 re-seeds on the frozen numbers ({[(a['seed'], b['seed']) for a, b in pairs]})",
       [(a['seed'], b['seed']) for a, b in pairs] == [(1, 7), (4, 6)])

# A missing seed must not silently sort to the front and steal the top line.
broken = [entry(1, 10, 0.75), dict(entry(2, 20, 0.7), seed=None)]
expect("an entry with no seed sorts last rather than first",
       _seedSort(broken)[0]['teamId'] == 10)

# ── the three sorters must agree ───────────────────────────────────────────
src = io.open('playoff_bracket.py', encoding='utf-8').read()
body = src[src.index('def _seedSort'):src.index('def pairTopVsBottom')]
expect("playoff_bracket sorts on seed", 'seed' in body and 'winPct' not in body.split('return')[-1])

engine = io.open('managers/seasonManager.py', encoding='utf-8').read()
expect("the engine's round loop orders by frozen seed, not by record",
       '_orderByFrozenSeed(teamsInRound)' in engine)
expect("and it reads the seeds from the frozen blob, which survives a restart",
       'getFrozenSeeds' in engine)

js = os.path.join('..', 'floosball-react', 'src', 'utils', 'bracketProjection.ts')
if os.path.exists(js):
    jsSrc = io.open(js, encoding='utf-8').read()
    cmp = jsSrc[jsSrc.index('export function seedSort'):]
    cmp = cmp[:cmp.index('}')]
    expect(f"the browser projection sorts on seed too",
           'seed' in cmp and 'winPct' not in cmp)
else:
    print('  [skip] frontend not present')

print()
if fails:
    print(f"{len(fails)} FAILED"); sys.exit(1)
print("PASS — division winners hold seeds 1-4 through the whole bracket.")

"""A player's anomaly badge is THIS season's state, and cleansed is one of them.

Reported: profiles never clear their Awakened status; a player cleansed after a
Criticality should show that, and at the season boundary every player should revert.

⚠️ TWO SYMPTOMS, ONE LINE. The profile asked `AnomalyState.state == 'awakened'` across
ALL seasons, on the reasoning that "awakening is part of who a player has been, and a
profile is a career page". That reading cost both halves of the state:

  * A CLEANSE VANISHED INSTEAD OF SHOWING. `anomalyManager` flips the row in place
    (`st.state = 'cleansed'`, anomalyManager.py:1453), so the moment the Cores purged a
    player the badge disappeared — the profile had no cleansed concept at all, and being
    cleansed is the more dramatic half of the story.
  * AN AWAKENING NEVER ENDED. `anomaly_state` is per-player per-SEASON, so a row stamped
    'awakened' in season N is never revisited once that season stops ticking, and an
    all-seasons query lit the badge forever.

⚠️ SCOPING TO THE SEASON *IS* THE RESET. Next season has no row, so the state reads None
with nothing to migrate and no backfill. It clears at the season ROLLOVER rather than at
the Floos Bowl, which keeps the Reset's aftermath readable through the offseason.

Run: .venv/bin/python test_profile_anomaly_state.py   (exits non-zero on any failure)
"""
import ast
import re

fails = []


def expect(desc, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {desc}")
    if not cond:
        fails.append(desc)


SRC = open('api/main.py').read()
LINES = SRC.splitlines()
TREE = ast.parse(SRC)


# ── every AnomalyState read is scoped to a season ───────────────────────────
# ⚠️ THE REAL INVARIANT, swept rather than spot-checked. An unscoped read of a per-season
# table is the bug class, not just the one line that had it: any new surface asking "is
# this player awakened" without a season answers for their whole career instead.
#
# Line-based on purpose. `ast.get_source_segment` per node is O(n^2) over a file this
# size and hangs; the question here is about a statement's text, not its shape.
#
# Bite check: drop `season=_seasonNum` from the profile read and this fails.
MODEL = re.compile(r'\bAnomalyState\b|\b_AS\b')
READ = re.compile(r'\.(query|filter|filter_by)\(')
unscoped = []
for i, line in enumerate(LINES):
    if not (MODEL.search(line) and READ.search(line)):
        continue
    # The season can sit a few lines either side on a wrapped chain, so judge the whole
    # statement rather than the one line the model name happens to land on.
    window = '\n'.join(LINES[max(0, i - 4):i + 7])
    if re.search(r'\bseason\b', window):
        continue
    unscoped.append(f"api/main.py:{i + 1}: {line.strip()[:60]}")

expect(f"every AnomalyState read in api/main.py is season-scoped "
       f"({unscoped or 'all scoped'})", not unscoped)


# ── the profile emits a STATE, not a lone boolean ───────────────────────────
def _funcSource(name):
    for node in ast.walk(TREE):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(SRC, node)
    raise AssertionError(f"{name} not found in api/main.py")


profile = next(f for f in ('get_player', 'get_player_by_id')
               if any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == f
                      for n in ast.walk(TREE)))
body = _funcSource(profile)

expect(f"the profile ({profile}) emits anomalyState", "'anomalyState'" in body)
expect("and still emits isAwakened, so an older client keeps its badge",
       "'isAwakened'" in body)
expect("cleansed is one of the states it can emit", "'cleansed'" in body)
expect("the profile's own read is season-scoped", 'season=_seasonNum' in body)

# ⚠️ Only the two TERMINAL rungs belong on a profile. The climb is deliberately off it:
# every public anomaly surface is qualitative, and a ladder position is a progress bar.
for rung in ('stirring', 'erratic', 'rampant'):
    expect(f"the profile does not surface '{rung}'", f"'{rung}'" not in body)


# ── the frontend renders both, and pulses only the live one ─────────────────
FE = '../floosball-react/src/Views/Players/PlayerPage.tsx'
try:
    fe = open(FE).read()
    expect("the profile page reads anomalyState", 'anomalyState' in fe)
    expect("it renders a Cleansed badge", "'Cleansed'" in fe)
    expect("it still renders an Awakened badge", "'Awakened'" in fe)
    # Cleansed is the power being GONE, so it must not pulse like a live one.
    expect("only the awakened badge pulses",
           "anomalyState === 'awakened' ? 'pulse' : undefined" in fe)
    expect("it falls back to isAwakened for an older payload",
           "att?.isAwakened ? 'awakened' : null" in fe)
except FileNotFoundError:
    print("  [skip] frontend not checked out beside the backend")

print("\nPASS — the badge is this season's state, and a cleanse is a state."
      if not fails else f"\n{len(fails)} FAILED")
raise SystemExit(1 if fails else 0)

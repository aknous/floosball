"""The 28-week season for 8 four-team divisions, and the home/away bug it uncovered.

Owner moved the league to 8 divisions of 4 (2026-08-07), which broke the old 14/8/6 split:
with only 3 rivals a home-and-away round is 6 games, not 14. The replacement is
12 division (3 x 4) + 12 rest-of-league + 4 interleague, chosen as "rivalry-heavy" over a
wider-interleague alternative that could not promise you played every club in your league.

⚠️ It also surfaced a PRE-EXISTING bug in _crossDivisionWeeks: the opponent index is
`j = (i + r) % n` and a mod-n shift preserves parity, so deciding home/away on `(i + r) % 2`
meant division B only ever hosted when j was ODD. Half of every B division got ZERO home
games, in the shipped 8-club format too.

Run: .venv/bin/python test_divisional_schedule.py   (exits non-zero on any failure)
"""
import sys, collections
sys.path.insert(0, '/Users/andrew/Projects/floosball')
import logging; logging.disable(logging.CRITICAL)
import managers
from managers.seasonManager import SeasonManager

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)


class T:
    def __init__(self, n): self.name = n; self.division = None
class L:
    def __init__(self, n, t): self.name = n; self.teamList = t
class LM:
    def __init__(self, lg): self.leagues = lg


def build(perLeague=16):
    sm = SeasonManager.__new__(SeasonManager)
    sm.leagueManager = LM([
        L("Corduroy League", [T(f"A{i:02d}") for i in range(perLeague)]),
        L("Flannel League", [T(f"B{i:02d}") for i in range(perLeague)]),
    ])
    return sm


# ── the bug, in isolation ───────────────────────────────────────────────────
sm = build()
a = [T(f"A{i}") for i in range(4)]
b = [T(f"B{i}") for i in range(4)]
home = collections.Counter()
for wk in sm._crossDivisionWeeks(a, b):
    for h, _ in wk:
        home[h.name] += 1
expect("every club hosts in a cross-division block (was: even-indexed B hosted zero)",
       all(home[t.name] == 2 for t in a + b))

# It must hold for the 8-club shape too, since that is where it shipped broken.
a8 = [T(f"A{i}") for i in range(8)]
b8 = [T(f"B{i}") for i in range(8)]
h8 = collections.Counter()
for wk in sm._crossDivisionWeeks(a8, b8):
    for h, _ in wk:
        h8[h.name] += 1
expect("...and in the 8-club shape", all(h8[t.name] == 4 for t in a8 + b8))

# ── the full season ─────────────────────────────────────────────────────────
sm = build()
sched = sm._generateDivisionalSchedule()
expect("builds a schedule at all", sched is not None)
expect(f"28 weeks ({len(sched)})", len(sched) == 28)

games, home, opp = collections.Counter(), collections.Counter(), collections.defaultdict(collections.Counter)
for wk in sched:
    seen = set()
    for h, aw in wk:
        games[h.name] += 1; games[aw.name] += 1; home[h.name] += 1
        opp[h.name][aw.name] += 1; opp[aw.name][h.name] += 1
        seen.add(h.name); seen.add(aw.name)
    expect_once = len(wk) == 16
    if not expect_once:
        fails.append("a week did not field all 32 clubs")

expect("every club plays 28 games", set(games.values()) == {28})
expect("every club has exactly 14 home games", set(home[n] for n in games) == {14})
expect("every club plays every week", len(sched[0]) == 16)

# ── the split is what was agreed ────────────────────────────────────────────
lg = sm.leagueManager.leagues[0]
t = lg.teamList[0]
div = {x.name for x in lg.teamList[:4]}
sameDiv = sum(v for k, v in opp[t.name].items() if k in div)
sameLg = sum(v for k, v in opp[t.name].items() if k.startswith('A') and k not in div)
inter = sum(v for k, v in opp[t.name].items() if k.startswith('B'))
expect(f"12 games vs division rivals ({sameDiv})", sameDiv == 12)
expect(f"12 vs the rest of the league ({sameLg})", sameLg == 12)
expect(f"4 interleague ({inter})", inter == 4)
expect("each division rival is played exactly 4 times",
       all(opp[t.name][d] == 4 for d in div if d != t.name))
# The alternative format could not promise this, which is why it lost.
expect("no club in your own league goes unplayed",
       all(opp[t.name][x.name] > 0 for x in lg.teamList if x is not t))

# ── divisions ───────────────────────────────────────────────────────────────
divs = collections.Counter(x.division for x in
                           sm.leagueManager.leagues[0].teamList + sm.leagueManager.leagues[1].teamList)
expect(f"8 divisions ({len(divs)})", len(divs) == 8)
expect("4 clubs in each", set(divs.values()) == {4})

# ── the run-in is division games, which is the point of the ordering ────────
lastDay = sched[-7:]
divGames = sum(1 for wk in lastDay for h, aw in wk
               if h.division == aw.division)
total = sum(len(wk) for wk in lastDay)
expect(f"the final game day is mostly division games ({divGames}/{total})",
       divGames / total > 0.8)

# ── a non-division-shaped league falls back rather than building nonsense ───
expect("an odd league size falls back to the round-robin",
       build(perLeague=15)._generateDivisionalSchedule() is None)

print("\nPASS — 28 weeks, 14 home each, and everyone hosts."
      if not fails else f"\n{len(fails)} FAILED")
sys.exit(1 if fails else 0)

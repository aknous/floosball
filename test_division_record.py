"""Division record is tracked, and is the first tiebreaker after win%.

Owner, 2026-08-07. With 12 of the 28 games played inside a four-club division, division
record is what a division race is actually decided on — and it separates clubs that a raw
score differential would not.

Run: .venv/bin/python test_division_record.py   (exits non-zero on any failure)
"""
import sys
sys.path.insert(0, '/Users/andrew/Projects/floosball')
import logging; logging.disable(logging.CRITICAL)
from seeding import orderTeams, _divisionWinPerc

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)


class T:
    _n = 0
    def __init__(self, name, winPerc, scoreDiff=0, divW=0, divL=0, divT=0, pts=0):
        T._n += 1
        self.id = T._n
        self.name = name
        self.seasonTeamStats = {
            'winPerc': winPerc, 'scoreDiff': scoreDiff,
            'divWins': divW, 'divLosses': divL, 'divTies': divT,
            'Offense': {'pts': pts},
        }
    def __repr__(self): return self.name


# ── the rate ────────────────────────────────────────────────────────────────
expect("no division games played reads as 0.0", _divisionWinPerc(T('x', .5)) == 0.0)
expect("8-4 in the division is .667",
       _divisionWinPerc(T('x', .5, divW=8, divL=4)) == 0.6667)
expect("a tie counts as half", _divisionWinPerc(T('x', .5, divW=1, divL=0, divT=1)) == 0.75)
# A RATE, not raw wins: two clubs can arrive having played a different number of division
# games, and raw wins would reward whoever had played more.
a = T('played more', .5, divW=6, divL=6)   # .500 over 12
b = T('played fewer', .5, divW=4, divL=2)  # .667 over 6
expect("a rate, so more games played is not itself an advantage",
       _divisionWinPerc(b) > _divisionWinPerc(a))

# ── it outranks score differential ──────────────────────────────────────────
weakDivBigDiff = T('BigDiff', 0.700, scoreDiff=180, divW=4, divL=8)
strongDivSmallDiff = T('DivKing', 0.700, scoreDiff=10, divW=10, divL=2)
order = orderTeams([weakDivBigDiff, strongDivSmallDiff])
expect(f"tied on win%, the better division record seeds higher ({order[0].name})",
       order[0] is strongDivSmallDiff)

# ── but win% still comes first ──────────────────────────────────────────────
betterOverall = T('Better', 0.800, scoreDiff=0, divW=0, divL=12)
worseOverall = T('Worse', 0.700, scoreDiff=0, divW=12, divL=0)
expect("a better overall record still outranks a better division record",
       orderTeams([worseOverall, betterOverall])[0] is betterOverall)

# ── score differential still breaks a division-record tie ───────────────────
c = T('SameDivWorseDiff', 0.600, scoreDiff=5, divW=6, divL=6)
d = T('SameDivBetterDiff', 0.600, scoreDiff=99, divW=6, divL=6)
expect("equal division records fall through to score differential",
       orderTeams([c, d])[0] is d)

# ── recorded only for genuine division games ────────────────────────────────
# Read as text rather than importing — floosball_game has a circular import with managers.
src = open('/Users/andrew/Projects/floosball/floosball_game.py').read()
expect("a game counts as divisional only when both clubs share a stamped division",
       "isDivisionGame = bool(hDiv) and hDiv == aDiv" in src)
# None == None must not read as a match, or every game in a flat league counts.
expect("an unstamped (None) division does not count as a match",
       "bool(hDiv)" in src)

sm = open('/Users/andrew/Projects/floosball/managers/seasonManager.py').read()
expect("the crash-recovery path records it too, or a crashed division game "
       "silently leaves the tiebreaker", "_w['divWins'] = _w.get('divWins', 0) + 1" in sm)

print("\nPASS — division record is tracked and seeds ahead of score differential."
      if not fails else f"\n{len(fails)} FAILED")
sys.exit(1 if fails else 0)

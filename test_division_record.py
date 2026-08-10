"""The tiebreaker after win% is CONTEXTUAL: division record for a division title,
league record for a wildcard.

Owner, 2026-08-07. Division record is only comparable between clubs that played the same
division slate — 12 of 28 games against the identical three opponents. An 8-4 division
record in one division against an 8-4 in another compares different opponents and means
little. So a division title settles on division record, and a wildcard race (tied clubs
from different divisions) falls to LEAGUE record, which they do share a basis for: 24 of
the 28 games are intra-league.

Run: .venv/bin/python test_division_record.py   (exits non-zero on any failure)
"""
import sys
sys.path.insert(0, '/Users/andrew/Projects/floosball')
import logging; logging.disable(logging.CRITICAL)
from seeding import orderTeams, _divisionWinPerc, _leagueWinPerc, _sharedDivision

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)


class T:
    _n = 0
    def __init__(self, name, winPerc, scoreDiff=0, divW=0, divL=0, divT=0, pts=0,
                 division='D1', lgW=0, lgL=0, lgT=0):
        T._n += 1
        self.id = T._n
        self.name = name
        self.division = division
        self.seasonTeamStats = {
            'winPerc': winPerc, 'scoreDiff': scoreDiff,
            'divWins': divW, 'divLosses': divL, 'divTies': divT,
            'lgWins': lgW, 'lgLosses': lgL, 'lgTies': lgT,
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

# ── SAME division: the division title, settled on division record ──────────
weakDivBigDiff = T('BigDiff', 0.700, scoreDiff=180, divW=4, divL=8, division='D1')
strongDivSmallDiff = T('DivKing', 0.700, scoreDiff=10, divW=10, divL=2, division='D1')
order = orderTeams([weakDivBigDiff, strongDivSmallDiff])
expect(f"same division: better division record wins the title ({order[0].name})",
       order[0] is strongDivSmallDiff)

# ── DIFFERENT divisions: a wildcard race, settled on LEAGUE record ──────────
# Division record is deliberately misleading here — the club with the far better division
# record must still lose the wildcard on league record, because the two division records
# come from different opponents.
wcBadLeague = T('FatDivRecord', 0.700, scoreDiff=50, divW=12, divL=0,
                lgW=12, lgL=12, division='D1')
wcGoodLeague = T('StrongInLeague', 0.700, scoreDiff=50, divW=6, divL=6,
                 lgW=20, lgL=4, division='D2')
order = orderTeams([wcBadLeague, wcGoodLeague])
expect(f"different divisions: league record decides, not division ({order[0].name})",
       order[0] is wcGoodLeague)

# A 3-way tie spanning divisions is a wildcard comparison, even though two share one.
a1 = T('A1', 0.6, divW=9, divL=3, lgW=10, lgL=14, division='D1')
a2 = T('A2', 0.6, divW=8, divL=4, lgW=11, lgL=13, division='D1')
b1 = T('B1', 0.6, divW=3, divL=9, lgW=20, lgL=4, division='D2')
expect("a tie group spanning divisions uses league record throughout",
       orderTeams([a1, a2, b1])[0] is b1)
expect("_sharedDivision only matches when EVERY club agrees",
       _sharedDivision([a1, a2]) == 'D1' and _sharedDivision([a1, b1]) is None)
expect("an unstamped division falls to the league tiebreak",
       _sharedDivision([T('x', .5, division=None), T('y', .5, division=None)]) is None)

# ── but win% still comes first ──────────────────────────────────────────────
betterOverall = T('Better', 0.800, scoreDiff=0, divW=0, divL=12, lgW=0, lgL=24)
worseOverall = T('Worse', 0.700, scoreDiff=0, divW=12, divL=0, lgW=24, lgL=0)
expect("a better overall record still outranks a better division record",
       orderTeams([worseOverall, betterOverall])[0] is betterOverall)

# ── score differential still breaks a tie the step-2 rate cannot ────────────
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

expect("league record is tracked at game end", "lgWins" in src)
# team.league is the league NAME (a string). Reaching for `.name` on it silently yields
# None and every game would read as non-league.
expect("league identity is read as a string, not an object",
       "getattr(self.homeTeam, 'league', None)" in src)
expect("a division game always counts as a league game too",
       "isLeagueGame = isDivisionGame or" in src)

sm = open('/Users/andrew/Projects/floosball/managers/seasonManager.py').read()
expect("the crash-recovery path records division record too",
       "_w['divWins'] = _w.get('divWins', 0) + 1" in sm)
expect("...and league record", "_w['lgWins'] = _w.get('lgWins', 0) + 1" in sm)

expect("league rate is a rate too", _leagueWinPerc(T('x', .5, lgW=12, lgL=12)) == 0.5)

print("\nPASS — division record settles the division, league record settles the wildcard."
      if not fails else f"\n{len(fails)} FAILED")
sys.exit(1 if fails else 0)

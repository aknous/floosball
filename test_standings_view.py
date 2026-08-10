"""The standings board seeds the way the playoffs actually seed.

Four divisions of four per league, eight qualifiers: the four division winners take seeds
1-4 and the best four of everyone else take 5-8. The board therefore cannot just sort by
record — a division winner with a losing record still holds a top seed, and sorting by
record would put the cutline on the wrong row and make the seed column read 1,2,3,5,6,4.

Also covers the two derived columns that carry the most room to be quietly wrong: games
back (signed FROM the club on the cut, so a qualifier reads negative) and the movement
arrow (compared against rank BY RECORD, not display row — otherwise a rival winning its
division invents movement the club never earned).

Run: .venv/bin/python test_standings_view.py   (exits non-zero on any failure)
"""
import sys
sys.path.insert(0, '/Users/andrew/Projects/floosball')
import logging; logging.disable(logging.CRITICAL)
from standings_view import seedLeague, gamesBackFrom, playoffSpots, divisionsOf

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)


class T:
    _n = 0
    def __init__(self, name, wins, losses, division, divW=0, divL=0, lgW=0, lgL=0,
                 scoreDiff=0, pts=0):
        T._n += 1
        self.id = T._n
        self.name = name
        self.division = division
        played = wins + losses
        self.seasonTeamStats = {
            'wins': wins, 'losses': losses,
            'winPerc': round(wins / played, 4) if played else 0.0,
            'scoreDiff': scoreDiff,
            'divWins': divW, 'divLosses': divL, 'divTies': 0,
            'lgWins': lgW, 'lgLosses': lgL, 'lgTies': 0,
            'Offense': {'pts': pts},
        }
    def __repr__(self): return self.name


def league16():
    """A 16-club league where the North winner is a LOSING team.

    That is the case the whole seeding rule exists for: North is weak, so its best club
    goes 6-8, and a 10-4 club in a strong division has to sit behind it at seed 5.
    """
    teams = []
    # East — strong
    teams += [T('E1', 12, 2, 'East', 5, 1, 9, 3, scoreDiff=120),
              T('E2', 10, 4, 'East', 4, 2, 8, 4, scoreDiff=70),
              T('E3', 8, 6, 'East', 3, 3, 6, 6, scoreDiff=10),
              T('E4', 7, 7, 'East', 0, 6, 5, 7, scoreDiff=-20)]
    # West
    teams += [T('W1', 11, 3, 'West', 5, 1, 9, 3, scoreDiff=100),
              T('W2', 10, 4, 'West', 4, 2, 8, 4, scoreDiff=60),
              T('W3', 9, 5, 'West', 3, 3, 7, 5, scoreDiff=30),
              T('W4', 5, 9, 'West', 0, 6, 3, 9, scoreDiff=-60)]
    # South
    teams += [T('S1', 9, 5, 'South', 5, 1, 7, 5, scoreDiff=40),
              T('S2', 8, 6, 'South', 4, 2, 6, 6, scoreDiff=15),
              T('S3', 6, 8, 'South', 2, 4, 4, 8, scoreDiff=-30),
              T('S4', 4, 10, 'South', 1, 5, 2, 10, scoreDiff=-80)]
    # North — weak; its winner has a losing record
    teams += [T('N1', 6, 8, 'North', 5, 1, 4, 8, scoreDiff=-25),
              T('N2', 5, 9, 'North', 4, 2, 3, 9, scoreDiff=-50),
              T('N3', 4, 10, 'North', 2, 4, 2, 10, scoreDiff=-90),
              T('N4', 3, 11, 'North', 1, 5, 1, 11, scoreDiff=-110)]
    return teams


print("\nSeeding a 16-club, 4-division league")
teams = league16()
result = seedLeague(teams)
seeds = result['seeds']
byName = {t.name: t for t in teams}

expect("half the league qualifies", playoffSpots(16) == 8)
expect("eight clubs are seeded", len(seeds) == 8)

kinds = [seeds[t.id][1] for t in teams if t.id in seeds]
expect("exactly four division seeds", kinds.count('division') == 4)
expect("exactly four wildcard seeds", kinds.count('wildcard') == 4)

winners = {name for name in ('E1', 'W1', 'S1', 'N1')}
seededDivision = {t.name for t in teams if seeds.get(t.id, (None, None))[1] == 'division'}
expect("the four division winners hold the division seeds", seededDivision == winners)

expect("a losing division winner still gets a top-four seed",
       seeds[byName['N1'].id][0] <= 4 and byName['N1'].seasonTeamStats['wins'] == 6)

expect("division seeds are numbered 1-4", sorted(seeds[byName[n].id][0] for n in winners) == [1, 2, 3, 4])
expect("the best division winner is the top seed", seeds[byName['E1'].id][0] == 1)

e2 = seeds[byName['E2'].id]
expect("a 10-4 non-winner is a WILDCARD, not a division seed", e2[1] == 'wildcard')
expect("...and sits behind every division winner", e2[0] >= 5)

expect("a division runner-up with a better record than a winner is still outside the top four",
       seeds[byName['W2'].id][0] >= 5)

print("\nDisplay order")
order = [t.name for t in result['ordered']]
seedNumbers = [seeds[t.id][0] for t in result['ordered'] if t.id in seeds]
expect("the qualifiers lead the list in seed order 1..8", seedNumbers == [1, 2, 3, 4, 5, 6, 7, 8])
expect("all 16 clubs are present exactly once", sorted(order) == sorted(t.name for t in teams))
expect("no seeded club appears after an unseeded one",
       all(result['ordered'][i].id in seeds for i in range(8))
       and all(result['ordered'][i].id not in seeds for i in range(8, 16)))

print("\nDivisions")
divs = result['divisions']
expect("four divisions come back", len(divs) == 4)
expect("each holds exactly four clubs", all(len(ids) == 4 for ids in divs.values()))
expect("a division is listed in its own standings order, leader first",
       divs['North'][0] == byName['N1'].id)
expect("divisionsOf ignores unstamped clubs",
       len(divisionsOf([T('X', 1, 1, None)])) == 0)

print("\nGames back")
cut = next(t for t in result['ordered'] if seeds.get(t.id, (None,))[0] == 8)
expect("the club on the cut is exactly zero back", gamesBackFrom(cut, cut) == 0.0)
expect("a club above the cut reads NEGATIVE (ahead)", gamesBackFrom(cut, byName['E1']) < 0)
expect("a club below the cut reads POSITIVE (chasing)", gamesBackFrom(cut, byName['N4']) > 0)
# 8-6 vs 6-8 is two games of wins and two of losses -> two games back, not four.
a = T('A', 8, 6, 'East'); b = T('B', 6, 8, 'East')
expect("games back halves the combined win+loss gap", gamesBackFrom(a, b) == 2.0)
c = T('C', 8, 5, 'East')
expect("an unplayed game shows up as a half game", gamesBackFrom(c, a) == 0.5)
expect("no cut club yields zero rather than an error", gamesBackFrom(None, a) == 0.0)

print("\nRecord ranks (what the movement arrow compares)")
ranks = result['recordRanks']
expect("record rank is separate from display order", ranks[byName['E2'].id] < ranks[byName['N1'].id])
expect("the best record is rank 1", ranks[byName['E1'].id] == 1)
expect("every club is ranked", len(ranks) == 16)
expect("N1 seeds top-four but ranks low on record",
       seeds[byName['N1'].id][0] <= 4 and ranks[byName['N1'].id] > 8)

print("\nNo divisions stamped")
flat = [T(f'F{i}', 14 - i, i, None) for i in range(8)]
flatResult = seedLeague(flat)
expect("falls back to plain record order", [t.name for t in flatResult['ordered']] == [f'F{i}' for i in range(8)])
expect("four seeds for an eight-club league", len(flatResult['seeds']) == 4)
expect("every seed is a wildcard when there is nothing to win",
       all(kind == 'wildcard' for _, kind in flatResult['seeds'].values()))

print()
if fails:
    print(f"FAIL — {len(fails)} check(s) failed:")
    for f in fails:
        print(f"  - {f}")
else:
    print("PASS — the board seeds the way the playoffs seed.")
sys.exit(1 if fails else 0)

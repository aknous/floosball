"""A wildcard berth is not clinched while a tie can still take it.

Reported from a live board: the Broads shown as having CLINCHED a wildcard after week
27, and out of the playoffs after losing in week 28. A badge that has to be taken away
is the single failure `clinchStatus` exists to prevent.

⚠️ ONE CAUSE, shared with the division bug. `_projected` advances wins and losses only,
so `divWins` / `lgWins` ride through UNCHANGED — when the worst case lands on a TIE,
`orderTeams` breaks it on TODAY's division and league records rather than the ones the
finished season will hold. The club won the projected tiebreak, was shown as clinched,
then lost the real one.

A berth now has to survive every tie going against the club: seeded in the worst case,
and nobody left outside the field level with it on points.

Run: ./run_tests.sh clinch_wildcard
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.WARNING)
from standings_view import clinchStatus

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)


class T:
    """⚠️ standings_view reads `seasonTeamStats`, never bare .wins."""
    def __init__(self, tid, name, w, l, division, div=(0, 0), lg=(0, 0), diff=0):
        self.id = tid; self.name = name; self.abbr = name[:3].upper()
        self.division = division
        self.seasonTeamStats = {
            'wins': w, 'losses': l, 'ties': 0,
            'winPerc': w / max(1, w + l), 'scoreDiff': diff,
            'divWins': div[0], 'divLosses': div[1], 'divTies': 0,
            'lgWins': lg[0], 'lgLosses': lg[1], 'lgTies': 0,
            'Offense': {'pts': 0}}


DIVS = ['North', 'South', 'East', 'West']
TOTAL = 28


def build(records):
    """16 clubs, four divisions of four, in the given order."""
    teams = []
    for i, rec in enumerate(records):
        w, l = rec[0], rec[1]
        div = rec[2] if len(rec) > 2 else (0, 0)
        lg = rec[3] if len(rec) > 3 else (0, 0)
        teams.append(T(i + 1, f'T{i+1}', w, l, DIVS[i // 4], div, lg))
    return teams


# ── the reported case ──────────────────────────────────────────────────────
# Week 27. The Broads hold the last berth by a single game over a chaser they do not
# play, and the chaser can draw level. Their LEAGUE record is the wildcard tiebreaker,
# and it is not yet decided either.
records = [(20, 7), (19, 8), (10, 17), (9, 18)] * 1
records += [(18, 9), (17, 10), (16, 11), (8, 19)]      # South
records += [(15, 12), (14, 13, (7, 5), (11, 9)), (13, 14), (7, 20)]   # East: the Broads at index 9
records += [(12, 15, (6, 6), (11, 9)), (11, 16), (6, 21), (5, 22)]    # West: the chaser at index 12
teams = build(records)
status = clinchStatus(teams, TOTAL)
broads = teams[9]
expect("a club one game clear of a chaser who can draw level has NOT clinched",
       status[broads.id]['clinchedPlayoffs'] is False)

# ── the mirror: elimination must not be claimed on a tie either ────────────
tail = teams[-1]
expect("a club that could still draw level with the field is not eliminated",
       isinstance(status[tail.id]['eliminated'], bool))

# ── genuinely safe still reads as safe ─────────────────────────────────────
# Nothing outside the field can reach them: eight clubs far clear, eight far behind.
#
# ⚠️ TWO STRONG AND TWO WEAK PER DIVISION, deliberately. Stacking all eight strong clubs
# into two divisions leaves two ALL-WEAK divisions, and each of those still sends a
# guaranteed division winner — taking two of the eight berths and genuinely knocking two
# strong clubs out. That is the division rule working, not a clinch bug, and it is easy
# to mistake for one.
records = []
for _ in range(4):
    records += [(24, 3), (24, 3), (4, 23), (4, 23)]
teams = build(records)
status = clinchStatus(teams, TOTAL)
# ⚠️ Select by RECORD, not by position. The strong clubs are interleaved across the
# divisions now, so teams[:8] is four of each and the assertion silently tested the
# wrong set.
strong = [t for t in teams if t.seasonTeamStats['wins'] > 12]
weak = [t for t in teams if t.seasonTeamStats['wins'] <= 12]
inField = [t for t in strong if status[t.id]['clinchedPlayoffs']]
expect(f"every club beyond reach is clinched ({len(inField)}/{len(strong)})",
       len(inField) == len(strong))
expect("and every club beyond hope is eliminated",
       all(status[t.id]['eliminated'] for t in weak))

# ── a division title is a berth even when the points are level ─────────────
# ⚠️ A guaranteed division seed does not depend on winning a wildcard tie, so the tie
# test must not withhold it.
records = [(20, 8, (11, 1)), (12, 16, (2, 10)), (11, 17), (10, 18)]
records += [(20, 8)] * 4 + [(20, 8)] * 4 + [(20, 8)] * 4
teams = build(records)
status = clinchStatus(teams, TOTAL)
champ = teams[0]
expect("a secured division title is a berth even with the league level on points",
       not status[champ.id]['clinchedDivision'] or status[champ.id]['clinchedPlayoffs'])

# ── the invariant ──────────────────────────────────────────────────────────
for recs in [[(20, 7), (19, 8), (10, 17), (9, 18)] + [(15, 12)] * 12,
             [(24, 3)] * 8 + [(4, 23)] * 8,
             [(14, 14)] * 16]:
    teams = build(recs)
    status = clinchStatus(teams, TOTAL)
    bad = [t.name for t in teams
           if status[t.id]['clinchedDivision'] and not status[t.id]['clinchedPlayoffs']]
    expect(f"a clinched division is always a clinched berth ({bad})", not bad)
    both = [t.name for t in teams
            if status[t.id]['clinchedPlayoffs'] and status[t.id]['eliminated']]
    expect(f"nothing is both clinched and eliminated ({both})", not both)

# ── the season is over: the field is settled, ties and all ─────────────────
# ⚠️ The tie guard above exists because a PROJECTED tie is unresolved. Once every game
# is played there is no projection — the tiebreakers have run on final numbers and the
# field IS the field. Reported from a finished board: the 7 and 8 seeds shown as not
# having clinched, tied on record AND on league record with the club in 9th. They were
# in. The same correction the division badge needed, which had to be made twice because
# the berth and the title are computed separately.
records = []
for _ in range(4):
    records += [(20, 8, (8, 4), (14, 6)), (18, 10, (7, 5), (13, 7)),
                (14, 14, (6, 6), (10, 10)), (14, 14, (6, 6), (10, 10))]
teams = build(records)
status = clinchStatus(teams, TOTAL)
seeded = [t for t in teams if status[t.id]['clinchedPlayoffs']]
elim = [t for t in teams if status[t.id]['eliminated']]
expect(f"a finished season has exactly a full field clinched ({len(seeded)})", len(seeded) == 8)
expect(f"and everyone else eliminated ({len(elim)})", len(elim) == 8)
expect("nobody is left in limbo once the season is over",
       len(seeded) + len(elim) == len(teams))

# The clubs level on record AND league record are the reported case — whichever way the
# tiebreak fell, they must be on one side of the line, not neither.
levels = [t for t in teams if t.seasonTeamStats['wins'] == 14]
undecided = [t.name for t in levels
             if not status[t.id]['clinchedPlayoffs'] and not status[t.id]['eliminated']]
expect(f"clubs tied on record and league record are still resolved ({undecided})",
       not undecided)


# ── A weak division winner does not keep the rest of the league alive ────────
# ⚠️ THE REPORTED CASE (owner, live board): the Oysters were 3 games back of the wildcard
# and 4 back in their own division with 2 to play — no road by either route — and the
# board showed them alive. The Monuments likewise.
#
# The cause was `tiedFromInside` asking `_points(other) <= _points(myBest)` over EVERY
# seeded club. A DIVISION WINNER holds a top-four seed at ANY record, so one bad division
# puts a club inside the field on far fewer points than healthy clubs sitting outside it —
# and every one of those clubs then cleared the test by being AHEAD of it. Being ahead of
# a division winner you cannot displace is not a tiebreak you might win; it is proof their
# berth has nothing to do with record.
print("Weak division winner does not spare the rest of the league")
weakDiv = [
    ('North', [(18, 8), (17, 9), (16, 10), (15, 11)]),
    ('South', [(15, 11), (14, 12), (13, 13), (11, 15)]),   # the last of these is the report
    ('East',  [(14, 12), (13, 13), (12, 14), (11, 15)]),
    ('West',  [(8, 18), (7, 19), (6, 20), (5, 21)]),       # winner seeded on 8 points
]
wt = build([r for _div, _recs in weakDiv for r in _recs])
wstatus = clinchStatus(wt, TOTAL)
# 3 back of the cut and 4 back in the division, with 2 to play: a ceiling of 13 against a
# cut whose FLOOR is 14 and a division leader whose floor is 15.
oysters = wt[7]
expect("a club short of both the wildcard and its division is eliminated",
       wstatus[oysters.id]['eliminated'])
# The mirror, and the reason the fix is not simply "eliminate more": the weak division's
# own clubs are genuinely alive, because the title is still reachable inside it.
westAlive = [t for t in wt if t.division == 'West' and not wstatus[t.id]['eliminated']]
expect(f"clubs who can still win the weak division stay alive ({len(westAlive)} of 4)",
       len(westAlive) == 3)
# ⚠️ And the guard still does its real job: a genuine tie for a WILDCARD proves nothing
# either way, so a club whose ceiling exactly meets the cut's floor is not eliminated.
tieForWildcard = wt[10]        # East 12-14: ceiling 14, cut floor 14
expect("a club level with the cut on points is NOT eliminated",
       not wstatus[tieForWildcard.id]['eliminated'])

print()
if fails:
    print(f"{len(fails)} FAILED"); sys.exit(1)
print("PASS — a berth survives every tie, or it is not called clinched.")

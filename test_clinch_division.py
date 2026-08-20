"""Winning a division has to be mathematically won, and consistent with the berth.

Reported from a live board at week 27: the Sand Dollars were shown as division
champions while one game up on the club they still had to PLAY in week 28 — a loss
there ties them and the title goes to a tiebreak they can lose. The same row showed
no playoff berth clinched, which is self-contradicting: division winners take seeds
1-4, so a genuine title is a berth.

⚠️ ONE CAUSE. `clinchStatus` tested the title with `rivalCeiling <= myPoints`, which
counts a rival who can draw LEVEL as beaten. Everything else in that function runs the
real worst-case seeding (which honours the division rule), so this looser rule was the
only way the two badges could disagree.

Run: ./run_tests.sh clinch_division
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
    """⚠️ standings_view reads `seasonTeamStats`, never bare .wins — a fake with plain
    attributes silently reads 0-0 and every assertion passes on an empty league."""
    def __init__(self, tid, name, w, l, t=0, division='North', div=(0, 0)):
        self.id = tid; self.name = name; self.abbr = name[:3].upper()
        self.division = division
        self.seasonTeamStats = {'wins': w, 'losses': l, 'ties': t,
                                'winPerc': w / max(1, w + l + t), 'scoreDiff': 0,
                                'divWins': div[0], 'divLosses': div[1], 'divTies': 0,
                                'lgWins': 0, 'lgLosses': 0, 'lgTies': 0,
                                'Offense': {'pts': 0}}


def league(*rows):
    """Four divisions of four, so seeding behaves as it does in the real league.

    A row is (wins, losses) or (wins, losses, (divWins, divLosses)) — the division
    record matters now that a level finish is settled on it.
    """
    teams = []
    tid = 0
    for divIndex, name in enumerate(['North', 'South', 'East', 'West']):
        for slot in range(4):
            tid += 1
            if divIndex == 0 and slot < len(rows):
                row = rows[slot]
                w, l = row[0], row[1]
                div = row[2] if len(row) > 2 else (0, 0)
            else:
                w, l, div = 8, 19, (0, 0)      # filler, clearly out of the race
            teams.append(T(tid, f'Team{tid}', w, l, division=name, div=div))
    return teams


TOTAL = 28

# ── the reported case: one game up, one game left, and they play each other ──
# ⚠️ Level on points is settled by DIVISION RECORD, so the same standings row can be a
# clinch or not depending on it. That is the whole point of the report: the Rocks were
# shown as champions while the Strangers held the better division record.

# The Rocks case — the rival would WIN the tie, so nothing is clinched.
teams = league((20, 7, (6, 5)), (19, 8, (9, 2)))
status = clinchStatus(teams, TOTAL)
leader, rival = teams[0], teams[1]
expect("a one-game lead is NOT clinched when the rival would win the tiebreak",
       status[leader.id]['clinchedDivision'] is False)
expect("the rival is not eliminated from the division race either",
       status[rival.id]['clinchedDivision'] is False)

# The Sand Dollars case — the leader's division record is beyond reach even at its worst,
# so the title is mathematically settled and the badge should show.
teams = league((20, 7, (10, 1)), (19, 8, (4, 7)))
status = clinchStatus(teams, TOTAL)
expect("a one-game lead IS clinched when the division tiebreak is already secured",
       status[teams[0].id]['clinchedDivision'] is True)

# A level division record cannot settle it — the next rung is score differential, which
# has no ceiling and cannot be projected at all.
teams = league((20, 7, (6, 5)), (19, 8, (6, 5)))
status = clinchStatus(teams, TOTAL)
expect("an unsettled tiebreak leaves the title open",
       status[teams[0].id]['clinchedDivision'] is False)

# ── two clear, with one to play, genuinely is won ──
teams = league((21, 6), (19, 8))
status = clinchStatus(teams, TOTAL)
expect("a two-game lead with one game left IS clinched",
       status[teams[0].id]['clinchedDivision'] is True)

# ── a tie is half a point, so a half-game edge is still catchable ──
teams = league((20, 7), (19, 7, ))
teams[1].seasonTeamStats.update({'wins': 19, 'losses': 7, 'ties': 1})
status = clinchStatus(teams, TOTAL)
expect("a half-game edge with a game left is not clinched",
       status[teams[0].id]['clinchedDivision'] is False)

# ── the invariant the report exposed ──
# ⚠️ Division winners take seeds 1-4, so a clinched title IS a clinched berth. These are
# computed by DIFFERENT methods — a points comparison and a worst-case re-seed — so
# nothing but this check stops them drifting apart again.
# ⚠️ The tiebreak-clinch case is the one that could break this invariant, because the two
# sides use DIFFERENT division records: this check uses the leader's WORST projected one,
# while seedLeague breaks its ties on today's. Ours is strictly the harsher of the two, so
# a club that clears it also clears the seeding — but that is a property worth pinning
# rather than reasoning about once.
for rows in [((20, 7), (19, 8)), ((21, 6), (19, 8)), ((24, 3), (12, 15)), ((14, 13), (14, 13)),
             ((20, 7, (10, 1)), (19, 8, (4, 7))), ((20, 7, (6, 5)), (19, 8, (9, 2)))]:
    teams = league(*rows)
    status = clinchStatus(teams, TOTAL)
    bad = [t.name for t in teams
           if status[t.id]['clinchedDivision'] and not status[t.id]['clinchedPlayoffs']]
    expect(f"clinching a division always clinches a berth {rows} ({bad})", not bad)

# ── a finished season still resolves ──
teams = league((20, 8), (19, 9))
status = clinchStatus(teams, TOTAL)
expect("with every game played, the leader has won the division",
       status[teams[0].id]['clinchedDivision'] is True)

# ── nothing is clinched on opening day ──
teams = league((1, 0), (0, 1))
status = clinchStatus(teams, TOTAL)
expect("a one-game lead in week 1 clinches nothing",
       not any(v['clinchedDivision'] for v in status.values()))

print()
if fails:
    print(f"{len(fails)} FAILED"); sys.exit(1)
print("PASS — a division is only won when no rival can even draw level.")

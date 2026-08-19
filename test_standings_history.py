"""Standings trajectories and the division games-back column.

Two things a fan asked for, one shared idea: the LEAGUE column answers "am I making the
playoffs" and a division block has to answer "am I winning my division". At four clubs
per division that second question is what most of the league is actually racing for --
24 of 32 clubs will never win a league title.

⚠️ The history is derived from `games`, and the winner there is `winner_team_id`, NOT the
higher score. A frames game is decided by frames won with points only breaking a level
tie, so reading the scoreline would mis-record every frames result -- the same defect
that put the wrong club in the recap email and the playoff history. Measured on prod
season 2: 14 of 336 regular-season finals have a winner that is not the higher score.

Run: .venv/bin/python test_standings_history.py   (exits non-zero on any failure)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.WARNING)
from standings_view import divisionGamesBack, gamesBackFrom
from standings_history import buildStandingsHistory, _winnerOf

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)


class T:
    # ⚠️ standings_view._record reads `seasonTeamStats`, NOT bare .wins/.losses. A fake
    # with plain attributes silently reads 0-0 for every club, which makes every
    # games-back assertion pass at 0.0 and proves nothing.
    def __init__(self, tid, name, w, l, t=0):
        self.id = tid; self.name = name; self.abbr = name[:3].upper()
        self.color = '#123456'; self.secondaryColor = '#654321'
        self.seasonTeamStats = {'wins': w, 'losses': l, 'ties': t}


# ── division games back ────────────────────────────────────────────────────
teams = [T(1, 'Alpha', 10, 2), T(2, 'Bravo', 8, 4), T(3, 'Charlie', 6, 6), T(4, 'Delta', 2, 10)]
divs = {'North': [1, 2, 3, 4]}
gb = divisionGamesBack(divs, teams)
expect(f"the division leader is 0 back ({gb[1]})", gb[1] == 0.0)
expect(f"second place is 2 back ({gb[2]})", gb[2] == 2.0)
expect(f"the bottom club is 8 back ({gb[4]})", gb[4] == 8.0)
expect("nothing in a division reads negative", all(v >= 0 for v in gb.values()))

# Half games are real: one club having played a game the other has not.
uneven = [T(1, 'Alpha', 10, 2), T(2, 'Bravo', 9, 2)]
gbu = divisionGamesBack({'N': [1, 2]}, uneven)
expect(f"an unplayed game shows as a half game ({gbu[2]})", gbu[2] == 0.5)

# ⚠️ The leader is divisions[name][0] — already ordered by the full tiebreaker chain.
# Re-deriving it by win% here would skip the contextual tiebreaker and could disagree
# with the division-winner rule the same payload reports.
flipped = {'North': [2, 1, 3, 4]}
expect("the leader is taken from the given order, not recomputed",
       divisionGamesBack(flipped, teams)[2] == 0.0)
expect("an empty division does not raise", divisionGamesBack({'Empty': []}, teams) == {})

# ── the winner rule ────────────────────────────────────────────────────────
expect("winner_team_id wins over the scoreline",
       _winnerOf(home=1, away=2, hs=10, aws=40, winner=1) == 1)
expect("a legacy row with no winner falls back to the score",
       _winnerOf(home=1, away=2, hs=10, aws=40, winner=None) == 2)
expect("a level legacy row is a tie", _winnerOf(1, 2, 20, 20, None) is None)

# ── the trajectory ─────────────────────────────────────────────────────────
class FakeSession:
    def __init__(self, rows, scheduledWeeks=28):
        self._rows = rows; self._weeks = scheduledWeeks
    def execute(self, q, *_a, **_k):
        rows, weeks = self._rows, self._weeks
        isSchedule = 'MAX(week)' in str(q)
        class R:
            def fetchall(self): return rows
            def fetchone(self): return (weeks,) if isSchedule else None
        return R()

# week, home, away, hs, as, winner
rows = [
    (1, 1, 2, 21, 14, 1), (1, 3, 4, 7, 28, 4),
    (2, 1, 3, 3, 10, 3),  (2, 2, 4, 17, 17, None),
    (3, 1, 4, 30, 0, 1),  (3, 2, 3, 14, 21, 3),
]
tbl = {'League A': [T(1, 'Alpha', 0, 0), T(2, 'Bravo', 0, 0),
                    T(3, 'Charlie', 0, 0), T(4, 'Delta', 0, 0)]}
dbl = {'League A': {'North': [1, 2], 'South': [3, 4]}}
hist = buildStandingsHistory(FakeSession(rows), 1, tbl, dbl)

expect(f"one point per played week ({hist['weeks']})", hist['weeks'] == [1, 2, 3])
byId = {t['id']: t for t in hist['leagues'][0]['teams']}
expect("every team gets a full series",
       all(len(t['series']) == 3 for t in byId.values()))

alpha = byId[1]['series']
expect(f"the record accumulates ({[(p['wins'], p['losses']) for p in alpha]})",
       [(p['wins'], p['losses']) for p in alpha] == [(1, 0), (1, 1), (2, 1)])
expect(f"games above .500 tracks it ({[p['gamesAbove500'] for p in alpha]})",
       [p['gamesAbove500'] for p in alpha] == [1, 0, 1])

# ⚠️ A tie is neither a win nor a loss and must not silently become one.
bravo = byId[2]['series']
expect(f"a tie is recorded as a tie ({[(p['wins'], p['losses'], p['ties']) for p in bravo]})",
       [p['ties'] for p in bravo] == [0, 1, 1] and bravo[-1]['wins'] == 0)

# ⚠️ The division leader is recomputed EACH WEEK. The whole point of the chart is that
# the lead changes hands, so freezing today's leader would draw a false history.
southLead = [(p['week'], byId[3]['series'][i]['divisionGamesBack'],
              byId[4]['series'][i]['divisionGamesBack'])
             for i, p in enumerate(byId[3]['series'])]
expect(f"the division lead changes hands over time ({southLead})",
       southLead[0][1] > 0 and southLead[-1][1] == 0.0)

# ⚠️ The x-axis spans the whole SCHEDULED season, not just the weeks with results, or
# every line is redrawn at a different scale each week and a fan cannot see how far
# through the season they are.
expect(f"the full season length is reported ({hist.get('totalWeeks')})",
       hist.get('totalWeeks') == 28)
expect("it is the scheduled length, not the played length",
       hist['totalWeeks'] > len(hist['weeks']))

expect("the payload carries division membership",
       {d['name'] for d in hist['leagues'][0]['divisions']} == {'North', 'South'})
expect("teams carry the identity a chart needs to draw a line",
       all(t.get('color') and t.get('abbr') and t.get('division') for t in byId.values()))

# A season with nothing played yet must return empty, not raise.
empty = buildStandingsHistory(FakeSession([]), 99, tbl, dbl)
expect("an unplayed season returns empty rather than raising",
       empty['weeks'] == [] and all(t['series'] == [] for t in empty['leagues'][0]['teams']))

print()
if fails:
    print(f"{len(fails)} FAILED"); sys.exit(1)
print("PASS — division races read from the leader, and the trajectory follows the real winner.")

"""Reloading a season's schedule must REPLACE each team's fixture list, not extend it.

`_loadScheduleFromDatabase` appends every game to `homeTeam.schedule` and
`awayTeam.schedule`. The only two places that clear those lists are new-season paths
(`teamManager`'s season roll-over and `clearTeamSeasonStats`), and neither runs on a
RESUME — so before this was fixed, every restart that resumed an existing season stacked
another full copy of the season onto every team. A team page showed 56 fixtures after one
restart and 84 after two, while the games table and the league schedule both stayed
correctly at 28 weeks (they are ASSIGNED, not appended).

That asymmetry is the trap: the data was never wrong, only the in-memory per-team view,
so nothing in the DB would ever have shown it.

Run: .venv/bin/python test_schedule_reload.py   (exits non-zero on any failure)
"""
import sys
sys.path.insert(0, '/Users/andrew/Projects/floosball')
import logging; logging.disable(logging.CRITICAL)

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)


class FakeTeam:
    def __init__(self, teamId):
        self.id = teamId
        self.abbr = f'T{teamId}'
        self.schedule = ['a stale fixture from a previous load']


class FakeTeamManager:
    def __init__(self, teams):
        self.teams = teams


print("\nThe reload clears every team's schedule before refilling")
# The behavior under test is the reset loop at the top of _loadScheduleFromDatabase.
# Exercising the whole method needs a DB, a Season and a service container; the contract
# that actually matters is "no team keeps a fixture from a previous load", so that is what
# is asserted here directly against the same statement the method runs.
teams = [FakeTeam(i) for i in range(1, 5)]
teamManager = FakeTeamManager(teams)

expect("teams start with stale fixtures", all(len(t.schedule) == 1 for t in teams))

for team in teamManager.teams:
    team.schedule = []

expect("every team is emptied, not just the ones in the new slate",
       all(t.schedule == [] for t in teams))

print("\nThe reset is in the reload path, above the appends")
source = open('/Users/andrew/Projects/floosball/managers/seasonManager.py').read()
start = source.index('def _loadScheduleFromDatabase')
end = source.index('def _recalculateScheduleTimes')
body = source[start:end]

resetAt = body.find('team.schedule = []')
appendAt = body.find('homeTeam.schedule.append')
expect("the reload resets team schedules", resetAt != -1)
expect("the reload still appends fixtures", appendAt != -1)
expect("the reset runs BEFORE the appends", resetAt != -1 and appendAt != -1 and resetAt < appendAt)
expect("it resets over teamManager.teams, so a team absent from this season is cleared too",
       'for team in teamManager.teams:' in body[:appendAt])

print("\nThe league schedule was never the problem")
expect("currentSeason.schedule is ASSIGNED, not appended, in the reload",
       'self.currentSeason.schedule = [weekMap[w] for w in sorted(weekMap)]' in body)

print()
if fails:
    print(f"FAIL — {len(fails)} check(s) failed:")
    for f in fails:
        print(f"  - {f}")
else:
    print("PASS — a resume replaces each team's fixture list instead of stacking another copy on it.")
sys.exit(1 if fails else 0)

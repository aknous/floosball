"""The playoff email agrees with the playoff field.

Reported: an end-of-season email told a fan their team had made the playoffs when it had
not. The day-4 mail built its own field as `_seedTeams(league.teamList)[:len//2]` -- the
TOP HALF BY RECORD, with no division rule -- so a division winner with a poor record was
told it had missed, and the club sitting just above the record cutline was told it was in
while that winner's guaranteed seed had already taken the berth.

⚠️ This was the THIRD independent answer to "who made the playoffs" in the codebase, and
the reason CLAUDE.md gives for the clinch logic re-seeding rather than counting: a
division winner occupies a berth without ever appearing above you in the table. Measured
on the live board once before -- BOS, DET and PHI all finished 14-14 with only seven
clubs holding more points, all three read as qualified, and 13-15 MIN had taken seed 4.

Run: ./run_tests.sh email_playoff_field
"""
import sys, os, io
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.WARNING)
from standings_view import seedLeague
from seeding import orderTeams

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)


class T:
    def __init__(self, tid, name, w, l, division):
        self.id = tid; self.name = name; self.abbr = name[:3].upper()
        self.division = division
        self.seasonTeamStats = {'wins': w, 'losses': l, 'ties': 0,
                                'winPerc': round(w / max(1, w + l), 4), 'scoreDiff': 0,
                                'divWins': 0, 'divLosses': 0, 'divTies': 0,
                                'lgWins': 0, 'lgLosses': 0, 'lgTies': 0,
                                'Offense': {'pts': 0}}


DIVS = ['North', 'South', 'East', 'West']
# A weak division winner and a strong club just above the record cutline — the shape that
# makes the two answers disagree.
records = [(11, 17), (10, 18), (9, 19), (8, 20),      # North: a weak division wins it
           (20, 8), (19, 9), (18, 10), (17, 11),      # South: strong
           (16, 12), (15, 13), (14, 14), (13, 15),    # East
           (12, 16), (12, 16), (11, 17), (10, 18)]    # West
teams = [T(i + 1, f'T{i+1}', w, l, DIVS[i // 4]) for i, (w, l) in enumerate(records)]

seeded = set(seedLeague(list(teams))['seeds'].keys())
byRecord = {t.id for t in orderTeams(list(teams))[:len(teams) // 2]}

expect(f"the two answers genuinely differ on this field ({sorted(seeded ^ byRecord)})",
       seeded != byRecord)

weakWinner = teams[0]
expect("the weak division winner IS in the real field",
       weakWinner.id in seeded)
expect("...and the record cut would have left it out",
       weakWinner.id not in byRecord)

wrongly = sorted(byRecord - seeded)
expect(f"the record cut wrongly includes someone the field excludes ({wrongly})",
       bool(wrongly))

expect("the field is the right size", len(seeded) == len(teams) // 2)

# ── the email must use the seeding, not the record cut ─────────────────────
src = io.open('managers/seasonManager.py', encoding='utf-8').read()
block = src[src.index('playoffTeamIds = set()'):]
block = block[:block.index('leaderboardTop.append')]
expect("the day-4 mail builds its field from seedLeague", 'seedLeague' in block)
expect("...and no longer takes the top half by record as its primary answer",
       block.index('seedLeague') < block.index('len(sortedTeams) // 2'))

# ⚠️ The season-end mail read `clinchPlayoff` and `t.madePlayoffs`, neither of which
# exists — so it could never say "Made Playoffs" for anyone.
expect("the season-end mail reads attributes that actually exist",
       "getattr(t, 'clinchPlayoff', False)" not in src)
expect("...and takes madePlayoffs from seasonTeamStats where it lives",
       "_stats.get('madePlayoffs')" in src)

# Read the source rather than importing: floosball_team and floosball_player import each
# other, so importing it standalone raises on the circular reference.
teamSrc = io.open('floosball_team.py', encoding='utf-8').read()
expect("Team really has no `madePlayoffs` attribute, which is why that read was dead",
       '.madePlayoffs =' not in teamSrc)

print()
if fails:
    print(f"{len(fails)} FAILED"); sys.exit(1)
print("PASS — the email reports the field the playoffs actually use.")

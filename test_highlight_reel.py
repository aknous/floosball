"""Highlight Reel counts the week's big plays, and it was reading a field already cleared.

Reported by a user: their favorite team had at least ten big plays in the week and the card
paid nothing.

⚠️ IT HAS NEVER PAID A SINGLE FLOOBIT, FOR ANYBODY. The week loop nulls
`currentSeason.activeGames` ("so roster swaps are unlocked between weeks") and keeps the
reference in `completedWeekGames`. Card scoring runs far downstream of that -- the null at
~:989, then `_onWeekComplete` at ~:1091, then `_processWeekCardEffects` at ~:1531, then the
big-play count. So the guard `if self.currentSeason.activeGames:` was always False,
`bigPlaysByTeam` was always empty, `ctx.favoriteTeamBigPlays` was always 0, and
`_computeHighlightReel` returned its "waiting for big plays" branch every week of every season.

⚠️ THE PROJECTION DISAGREED, WHICH IS WHY IT READ AS BROKEN RATHER THAN UNTRIGGERED.
`cardProjection` reads `seasonTeamStats['bigPlays']`, which IS populated, so the shop and the
lineup showed a plausible number beside a payout that could not happen. A card that pays zero
while advertising a number is reported; one that quietly pays zero is not.

⚠️ CREDITING BOTH TEAMS IS DELIBERATE and is NOT the bug. `recordManager` says so where it
accumulates the same figure: the card counts big plays in games the favorite team PLAYED IN,
whichever side executed them. Case 4 pins that, so a future "fix" to attribute by WPA has to
argue with the projection it would then contradict.

Run: .venv/bin/python test_highlight_reel.py
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.WARNING)

fails = []
def expect(label, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {label}")
    if not cond:
        fails.append(label)

HERE = os.path.dirname(os.path.abspath(__file__))
season = open(os.path.join(HERE, 'managers', 'seasonManager.py')).read()

print("\n1. The count reads the field that still holds the week's games")
block = season.split('bigPlaysByTeam = {}')[1].split('# ─── Get weekly modifier')[0]
expect('it reads completedWeekGames', 'completedWeekGames' in block)
expect('with activeGames only as a fallback',
       block.index('completedWeekGames') < block.index('activeGames'))

print("\n2. ...and the clear really does happen first")
clearAt = season.index('self.currentSeason.activeGames = None', season.index('completedWeekGames = self.currentSeason.activeGames'))
countAt = season.index('bigPlaysByTeam = {}')
expect('activeGames is nulled before the card scoring reads anything', clearAt < countAt)

print("\n3. The card pays on a real count and says so when there is none")
from managers.cardEffects import _computeHighlightReel
from managers.cardEffectCalculator import CardCalcContext
import dataclasses
fields = {f.name: f.default for f in dataclasses.fields(CardCalcContext)
          if f.default is not dataclasses.MISSING}
expect('favoriteTeamBigPlays defaults to 0', fields.get('favoriteTeamBigPlays') == 0)

class Ctx:
    favoriteTeamBigPlays = 0
r = _computeHighlightReel({'rewardValue': 6}, Ctx(), None, None)
expect('no big plays pays nothing and says it is waiting',
       r.floobits in (0, None) and 'waiting' in (r.equation or ''))
Ctx.favoriteTeamBigPlays = 10
r = _computeHighlightReel({'rewardValue': 6}, Ctx(), None, None)
expect(f'ten big plays at 6F each pays 60 (got {r.floobits})', r.floobits == 60)
expect('and the equation shows the count', '10 big plays' in (r.equation or ''))

print("\n4. Both teams are credited ON PURPOSE -- do not 'fix' this without the projection")
rec = open(os.path.join(HERE, 'managers', 'recordManager.py')).read()
expect('recordManager records the intent in a comment',
       'regardless of which side executed them' in rec)
expect('and credits both sides of the game',
       "homeTeam.seasonTeamStats['bigPlays']" in rec and "awayTeam.seasonTeamStats['bigPlays']" in rec)
proj = open(os.path.join(HERE, 'managers', 'cardProjection.py')).read()
expect('the projection reads that same both-teams figure',
       "favStats.get('bigPlays'" in proj)

print(f"\n{len(fails)} failed" if fails else "\nall good")
sys.exit(1 if fails else 0)

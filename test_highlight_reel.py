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
block = season.split('def _bigPlaysByTeam')[1].split('    def ', 1)[0]
expect('it reads completedWeekGames', 'completedWeekGames' in block)
expect('with activeGames only as a fallback',
       block.index('completedWeekGames') < block.index('activeGames'))

print("\n2. ...and the clear really does happen before scoring reads anything")
clearAt = season.index('self.currentSeason.activeGames = None',
                       season.index('completedWeekGames = self.currentSeason.activeGames'))
useAt = season.index('bigPlaysByTeam = self._bigPlaysByTeam()')
expect('activeGames is nulled first', clearAt < useAt)

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

print("\n5. END TO END -- a really simulated game, through the real counting code")
# ⚠️ CASES 1-4 ONLY ASSERT THE SHAPE. They read the source and call the compute function with
# a number I typed in, so they would ALL still pass if `isBigPlay` were never set on a play,
# or if the count never reached the payout. This case plays a real game and carries its feed
# through `_bigPlaysByTeam` into `_computeHighlightReel`.
import asyncio, random
import numpy as np
from scenario import _makeTeam
from game_rules import GameRules
import floosball_game as FG
from managers.seasonManager import SeasonManager


async def _play(gid):
    random.seed(gid); np.random.seed(gid % (2 ** 31))
    h, a = _makeTeam('H', 'HOM', 100 + gid * 10), _makeTeam('A', 'AWY', 500 + gid * 10)
    h.id, a.id = 101, 202
    g = FG.Game(h, a, gameRules=GameRules()); g.id = gid
    g._anomalyAttentionLoaded = True; g._anomalyEnabled = False
    g._anomalyAttention = {}; g._anomalyState = {}
    g._criticalityMultiplier = 1.0; g._criticalityActive = False; g._anomalyIntensity = 1.0
    g.previousHomeWinProbability = g.previousAwayWinProbability = 50.0
    await g.playGame()
    return g


# a seed whose game actually contains big plays, so the assertion is about the wiring
played = None
for seed in range(12):
    g = asyncio.run(_play(seed))
    if sum(1 for e in g.gameFeed
           if getattr(e.get('play') if isinstance(e, dict) else None, 'isBigPlay', False)):
        played = g
        break
expect('a simulated game contains big plays at all', played is not None)

truth = sum(1 for e in played.gameFeed
            if getattr(e.get('play') if isinstance(e, dict) else None, 'isBigPlay', False))

class _Season:
    """The season as it looks when card scoring runs: activeGames already cleared."""
    completedWeekGames = [played]
    activeGames = None

sm = SeasonManager.__new__(SeasonManager)       # no boot; the method reads only currentSeason
sm.currentSeason = _Season()
counted = sm._bigPlaysByTeam()
expect(f'the count reaches both teams in the game ({counted})',
       counted.get(101) == truth and counted.get(202) == truth)

# ⚠️ AND THE SAME OBJECT WITH ONLY `activeGames` SET IS THE BUG, REPRODUCED.
class _Cleared:
    completedWeekGames = None
    activeGames = None
sm.currentSeason = _Cleared()
expect('with nothing to read it pays nothing rather than raising', sm._bigPlaysByTeam() == {})

payout = _computeHighlightReel({'rewardValue': 6}, type('C', (), {
    'favoriteTeamBigPlays': counted.get(101, 0)})(), None, None)
expect(f'and a fan of the home team is paid for them ({payout.floobits}F on {truth} plays)',
       payout.floobits == 6 * truth and truth > 0)

print(f"\n{len(fails)} failed" if fails else "\nall good")
sys.exit(1 if fails else 0)

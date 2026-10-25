"""A tackled carrier credits exactly ONE tackle, to the defender who made it; a carrier who
scores credits none.

Reported alongside season 11's MVP ballot (Straycat Doughty, a safety with 568 tackles, 21
a game). The sim was handing out tackles by what the defense GAVE UP:

  * the safety got a tackle on every run of 5+ yards and every completion of 15+, ON TOP
    of the real tackler,
  * the covering defender got one on every completion, touchdowns included, and on a 15+
    yard catch the safety got one as well (the play text named only the safety),
  * every run tackle went to the LB (inside) or DE (edge): `runPlay` reassigned them
    AFTER `_resolveRunGates` had named who actually stopped the carrier.

Measured over 150 seeded games: 70.9 tackles a team-game against 51.3 tackled plays
(1.38 a play); after, 52.6 (the difference is sacks). Game results are unchanged within
noise (points 46.20 / 46.20 and 45.51 / 45.58 over two seeds of 400 games); the real
tackler now gets the confidence swing and returns the fumble he forces.

Run: python test_tackle_credit.py
"""
import asyncio, logging, os, random, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
logging.disable(logging.CRITICAL)
os.environ.setdefault('TIMING_MODE', 'fast')
import numpy as np

import playcall_nfl_check as H
import floosball_game as FG
from game_rules import GameRules
from managers.timingManager import TimingManager, TimingMode

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)


rng = random.Random(424242); random.seed(5); np.random.seed(5)
teams = []
for t in range(8):
    team = H._makeTeam(f'T{t}', f'T{t:02d}', 10000 + t * 100, phys=rng.randint(74, 92),
                       ment=rng.randint(74, 92), defRun=rng.randint(70, 88), defPass=rng.randint(70, 88))
    team.id = t
    np.random.seed(900 + t); team.coach.generateAttributes()
    teams.append(team)

SLOTS = ('qb', 'rb', 'wr1', 'wr2', 'te')


def tackles(team):
    return {slot: ((team.rosterDict[slot].gameStatsDict.get('defense') or {}).get('tackles', 0))
            for slot in SLOTS if team.rosterDict.get(slot) is not None}


records = []
original = FG.Game.playCaller


def hooked(game):
    defense = game.awayTeam if game.offensiveTeam is game.homeTeam else game.homeTeam
    before = tackles(defense)
    original(game)
    after = tackles(defense)
    credited = [defense.rosterDict[s] for s in after if after[s] > before.get(s, 0)]
    total = sum(after[s] - before.get(s, 0) for s in after)
    records.append((game.play, total, credited))


FG.Game.playCaller = hooked
try:
    for g in range(30):
        home, away = rng.sample(teams, 2)
        game = FG.Game(home, away, gameRules=GameRules(), timingManager=TimingManager(TimingMode.FAST))
        game.id = g
        asyncio.run(asyncio.wait_for(game.playGame(), timeout=120))
finally:
    FG.Game.playCaller = original

runs = [r for r in records if getattr(r[0], 'playType', None) is FG.PlayType.Run]
catches = [r for r in records if getattr(r[0], 'isPassCompletion', False)
           and not getattr(r[0], 'isInterception', False)]
# The OFFENSE scoring: a fumble returned for a touchdown still had a real tackle in it.
tds = [r for r in runs + catches if r[0].playResult is FG.PlayResult.Touchdown
       and not getattr(r[0], 'isFumbleLost', False)]

print(f"{len(records)} plays: {len(runs)} runs, {len(catches)} completions, {len(tds)} touchdowns")
expect("no play credits more than one tackle", max(r[1] for r in records) <= 1)
expect("a touchdown credits no tackle", all(r[1] == 0 for r in tds))
tackledRuns = [r for r in runs if r[1] == 1]
expect("a tackled run credits the defender the play names as the tackler",
       tackledRuns and all(r[2] == [r[0].tackledBy] for r in tackledRuns))
tackledCatches = [r for r in catches if r[1] == 1]
expect("a tackled completion credits the defender the play names as the tackler",
       tackledCatches and all(r[2] == [r[0].tackledBy] for r in tackledCatches))
safetyRunTackles = [r for r in tackledRuns if r[0].tackledBy is not None
                    and r[0].tackledBy.position.name == 'QB']
expect("safeties still make run tackles (the secondary level, or chasing a long run down)",
       len(safetyRunTackles) > 0)

if os.environ.get('DEBUG_TACKLES'):
    for r in [r for r in tds if r[1]][:4] + [r for r in tackledCatches if r[2] != [r[0].tackledBy]][:4]:
        p = r[0]
        print(p.playType, p.playResult, 'yds', p.yardage, 'yte', p.yardsToEndzone, 'tackledBy',
              getattr(p.tackledBy, 'name', None), 'credited', [c.name for c in r[2]],
              'sacked', getattr(p.sackedBy, 'name', None), 'scramble', getattr(p, 'isScramble', None),
              'checkdown', getattr(p, 'isCheckdown', None), 'text', (getattr(p, 'playText', '') or '')[:110])

print()
if fails:
    print(f"{len(fails)} FAILED"); sys.exit(1)
print("PASS — one tackle per tackled carrier, to the defender who made it.")

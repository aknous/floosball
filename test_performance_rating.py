"""Performance ratings are RATES, and LB / CB / S tackles do not count.

Reported: season 11's MVP ballot put Straycat Doughty, a 1-star QB with 47 TDs and 35 INTs,
3rd. Two separate faults, both in the rating MVP reads:

  1. The QB, RB, receiver and kicker formulas ranked season TOTALS (yards, TDs, INTs,
     receptions, made FGs), so volume set by the play-caller read as quality. (Doughty
     himself survives this fix: by rate he is 2nd in TD rate and yards per attempt in a
     league whose TD:INT is 1.07. High-volume receivers and kickers moved most.)
  2. The defensive score credited tackles the sim hands out by what the defense GAVE UP
     (a safety tackle on every 5+ yard run and 15+ yard completion, a corner tackle on
     every completion against him). Safety tackles correlated +0.81 to +0.89 with team
     yards allowed, so a worse defense read as a better safety. Doughty: defensive 100,
     ballot 3rd; without them, 11th.

Run: python test_performance_rating.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.WARNING)
from types import SimpleNamespace

from performance_rating import PerfInput, ratePosition, receiverShares, _shrunkRates
from constants import DEF_BOX_WEIGHTS

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)


def qb(pid, att, comp, yards, tds, ints, games=28, team=None):
    return PerfInput(pid, {'passing': {'att': att, 'comp': comp, 'yards': yards,
                                       'tds': tds, 'ints': ints}}, games, team)


def receiver(pid, targets, rec, drops, yards, yac, tds, team, games=28):
    return PerfInput(pid, {'receiving': {'targets': targets, 'receptions': rec, 'drops': drops,
                                         'yards': yards, 'yac': yac, 'tds': tds}}, games, team)


def field(n=6):
    """A pool of ordinary starters, 1,250 attempts each, with small spreads."""
    return [qb(100 + i, 1250, 800 + 5 * i, 8100 + 40 * i, 25 + i, 24 - i) for i in range(n)]


print("QB: volume is not quality")
# Identical rates, twice the attempts: the same rating (no shrinkage, so they tie exactly).
pool = field() + [qb(1, 1200, 780, 8000, 26, 22), qb(2, 2400, 1560, 16000, 52, 44)]
r = ratePosition('QB', pool, priorGames=0)
expect("double the attempts at the same rates rates the same", r[1] == r[2])

# The reported shape: the most attempts, most yards and TDs, but a worse INT rate than a
# lower-volume passer who matches him on every other rate.
heavy = qb(1, 1605, 1059, 11849, 47, 35)          # Doughty's line: 2.2% INT
clean = qb(2, 1290, 851, 9520, 37, 17)            # a hair lower comp/ypa/td rates, 1.3% INT
r = ratePosition('QB', field() + [heavy, clean], priorGames=0)
expect("a worse INT rate rates lower, however many more TDs the volume buys", r[2] > r[1])

print("Small samples")
starters = field()
oneGame = qb(9, 40, 30, 400, 3, 0, games=1)
rates = _shrunkRates(starters + [oneGame], lambda p: p.get('passing', 'comp'),
                     lambda p: p.get('passing', 'att'), priorGames=1.0)
poolRate = sum(p.get('passing', 'comp') for p in starters + [oneGame]) / \
    sum(p.get('passing', 'att') for p in starters + [oneGame])
own = 30 / 40
# Median per-game volume is ~44.6 attempts, so one 40-attempt game is pulled a bit more
# than halfway to the pool...
expect("a one-game rate is pulled about halfway to the position's rate",
       0.4 < (rates[-1] - poolRate) / (own - poolRate) < 0.55)
# ...while a 28-game starter's rate barely moves.
starterOwn = starters[0].get('passing', 'comp') / starters[0].get('passing', 'att')
expect("a full season's rate barely moves", abs(rates[0] - starterOwn) < 0.003)

print("Receivers: share of the team's targets")
# Same line, but team B throws twice as often, so the same targets are half the share.
lineA = receiver(1, 300, 200, 10, 2600, 1000, 10, team='A')
lineB = receiver(2, 300, 200, 10, 2600, 1000, 10, team='B')
mates = [receiver(10, 300, 200, 10, 2400, 900, 8, team='A'),
         receiver(11, 900, 600, 30, 7200, 2700, 24, team='B'),
         receiver(12, 250, 170, 12, 2000, 800, 7, team='C'),
         receiver(13, 260, 175, 11, 2100, 820, 6, team='C')]
everyone = [lineA, lineB] + mates
r = ratePosition('WR', everyone, shares=receiverShares(everyone), priorGames=0)
expect("the same targets on a pass-heavier team rate lower", r[1] > r[2])
shares = receiverShares(everyone)
expect("target share is per game against his own team", abs(shares[1][0] - 0.5) < 1e-9)

print("Kicker: made-FG volume is gone")
kicks = [PerfInput(i, {'kicking': {'fgs': f, 'fgAtt': a, 'fgYards': f * 38}}, 28)
         for i, (f, a) in enumerate([(97, 117), (60, 69), (80, 95), (70, 82), (50, 60)])]
r = ratePosition('K', kicks, priorGames=0)
expect("a more accurate kicker with fewer tries outrates a busier, less accurate one",
       r[1] > r[0])

print("Defense: no tackles where the sim credits them by yards allowed")
for grp in ('S', 'LB', 'CB'):
    expect(f"{grp} score has no tackle term", 'tackles' not in DEF_BOX_WEIGHTS[grp])
expect("tackles for loss still count for LB", DEF_BOX_WEIGHTS['LB'].get('tfl', 0) > 0)

print("Both rating paths use the shared formulas")
import managers.playerManager as pmMod
from floosball_player import Position, DefensivePosition


def player(pid, position, stats, team):
    return SimpleNamespace(id=pid, position=position, seasonStatsDict=stats, gamesPlayed=28,
                           team=team, defensivePosition=None, seasonPerformanceRating=0)


teamA, teamB = SimpleNamespace(id=1), SimpleNamespace(id=2)
qbs = [player(p.playerId, Position.QB, p.stats, teamA if p.playerId % 2 else teamB)
       for p in field() + [heavy, clean]]
fake = SimpleNamespace(activeQbs=qbs, activeRbs=[], activeWrs=[], activeTes=[], activeKs=[],
                       activePlayers=qbs)
pmMod.PlayerManager.calculatePerformanceRatings(fake, currentWeek=28)
direct = ratePosition('QB', [PerfInput(p.id, p.seasonStatsDict, 28, p.team.id) for p in qbs])
expect("the season rating is the shared formula",
       all(p.seasonPerformanceRating == direct[p.id] for p in qbs))

rows = [SimpleNamespace(player_id=p.id, team_id=p.team.id, passing_stats=p.seasonStatsDict['passing'],
                        rushing_stats={}, receiving_stats={}, kicking_stats={}) for p in qbs]
game = pmMod.PlayerManager.calculateGamePerformanceRatings(fake, rows)
directGame = ratePosition('QB', [PerfInput(p.id, p.seasonStatsDict, 1, p.team.id) for p in qbs])
expect("the single-game rating is the same formula", game == directGame)

print()
if fails:
    print(f"{len(fails)} FAILED"); sys.exit(1)
print("PASS — ratings are rates, and tackles the sim gives for yards allowed do not count.")

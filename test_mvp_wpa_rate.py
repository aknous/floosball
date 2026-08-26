"""MVP's WPA term is per GAME, not per snap.

Reported: quarterbacks are never in the MVP race. Measured over 20 simulated seasons
under the old rule, a QB won **1 MVP in 20** while receivers took 11.

⚠️ THE CAUSE IS THE DENOMINATOR. A WPA snap is logged only when a player is involved,
and the counts are wildly different -- measured on production, a QB logs ~1,233 a season
against a kicker's ~105 and a receiver's ~290. So the QB carries the league's
SECOND-HIGHEST RAW WPA and its LOWEST per-snap rate (0.119 vs the kicker's 2.67) purely
by being involved in everything.

⚠️ THE TWO HALVES ONLY WORK TOGETHER. Per game rewards volume, which is the opposite
failure: at the old weight of 0.30 it hands QBs 14 of 20 and all but erases receivers.
Paired with MVP_WPA_WEIGHT 0.20 it splits QB 8 / WR 8 / RB 3 / TE 1.

Four other explanations were tested against real data and ruled out, and are recorded so
they are not re-litigated: QBs logging snaps on run plays (they do not -- snaps ≈
attempts + sacks + carries), a lower QB rating ceiling (one season's noise: 95 in S1, 98
in S2), interception count vs rate (ceiling moves one point, no ordering change), and
star receivers inflating their QB (correlation with best-receiver RATING is -0.08).

Run: ./run_tests.sh mvp_wpa_rate
"""
import sys, os, io
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.WARNING)

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)

src = io.open('managers/playerManager.py', encoding='utf-8').read()
block = src[src.index('def wpaRate('):]
block = block[:block.index('positionGroups')]

expect("the rate is per GAME", 'gamesPlayed' in block)
expect("...and no longer divides by snaps", 'seasonWpaSnaps' not in block)

# ⚠️ The attributes it reads must actually exist, or every player scores 0 and the
# term silently disappears from the ballot.
player = io.open('floosball_player.py', encoding='utf-8').read()
expect("Player.gamesPlayed exists and is incremented per game",
       'self.gamesPlayed = 0' in player and 'self.gamesPlayed += 1' in player)
expect("the seasonStatsDict fallback key exists", "seasonStatsDict['gp']" in player)

from constants import MVP_WPA_WEIGHT, MVP_PERF_WEIGHT, MVP_DEF_WPA_WEIGHT
expect(f"the weight is reduced to pair with per-game ({MVP_WPA_WEIGHT})",
       abs(MVP_WPA_WEIGHT - 0.20) < 1e-9)
expect("performance still dominates the score",
       MVP_PERF_WEIGHT > MVP_WPA_WEIGHT)

# ── the helper behaves ─────────────────────────────────────────────────────
class P:
    def __init__(self, wpa, games, snaps=0, gp=None):
        self.seasonWpa = wpa; self.gamesPlayed = games
        self.seasonWpaSnaps = snaps
        self.seasonStatsDict = {'gp': gp} if gp is not None else {}

import textwrap, inspect
import managers.playerManager as pm
srcFn = inspect.getsource(pm.PlayerManager._computeMvpCandidates)
fnSrc = textwrap.dedent(
    srcFn[srcFn.index('        def wpaRate('):srcFn.index('        positionGroups')])
ns = {}
exec(compile(fnSrc, '<wpaRate>', 'exec'), ns)
wpaRate = ns['wpaRate']

expect("a 280-WPA season over 28 games rates 10.0", abs(wpaRate(P(280.0, 28)) - 10.0) < 1e-9)
expect("snaps no longer affect it", wpaRate(P(280.0, 28, snaps=9999)) == wpaRate(P(280.0, 28)))
expect("a player with no games scores 0 rather than raising", wpaRate(P(50.0, 0)) == 0.0)
expect("the seasonStatsDict fallback is used when the counter is unstamped",
       abs(wpaRate(P(56.0, 0, gp=28)) - 2.0) < 1e-9)

# ⚠️ The whole point: high volume must no longer be a penalty.
qb = P(151.7, 28, snaps=1233)      # production QB averages
wr = P(39.9, 28, snaps=290)
expect("a QB's larger involvement is no longer a handicap", wpaRate(qb) > wpaRate(wr))

print()
if fails:
    print(f"{len(fails)} FAILED"); sys.exit(1)
print("PASS — WPA is per game, and volume is no longer punished.")

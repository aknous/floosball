"""Performance ratings: how well a player produced, as a 60-100 percentile of his position.

ONE definition, shared by the season rating (`PlayerManager.calculatePerformanceRatings`,
which feeds MVP, All-Pro, the stats leaderboard and card edition eligibility) and the
single-game rating (`calculateGamePerformanceRatings`). They were two hand-copied sets of
formulas, which is how a change to one silently leaves the other behind.

⚠️ EVERY TERM IS A RATE, NOT A SEASON TOTAL (2026-10-22). The old formulas ranked
quarterbacks on total yards, total TDs and total interceptions, so the passer who threw the
most rated highest: season 11's Straycat Doughty threw 1,605 times (most in the league by
150+), led in yards, was 2nd in TDs, and rated 88 with a nearly 1:1 TD:INT ratio. His TD
rate (2.9%) matched Marberry's and Wispy July's (2.8%) while his INT rate was 2.2% to
their 1.3%, and the formula saw none of it. How often a QB throws, or a back carries, is
the play-caller's choice, so it is not credited at all. A receiver's TARGETS are different:
the quarterback throws to whoever is open, so getting the ball is part of the job, and it
is credited as his share of his TEAM's targets, which removes the team's pass volume.

⚠️ A RATE OVER A FEW PLAYS IS SHRUNK TOWARD THE POSITION'S RATE, by
`PERF_RATE_PRIOR_GAMES` games of typical volume, so a backup's two-game sample cannot top
a starter's season. Over a full season it moves a starter's rate by about a 28th.

The weights are the old ones on each replaced term (a total became the rate in its slot),
with one change: an interception counts as much as a touchdown (QB, 0.8 -> 1.0), since a
pick costs at least as much as a touchdown gains.
"""

from statistics import median
from typing import Any, Callable, Dict, List, Optional, Tuple

from scipy import stats as scipyStats

import floosball_methods as FloosMethods
from constants import PERF_RATE_PRIOR_GAMES


class PerfInput:
    """One player's line for a rating pool.

    stats: {'passing': {...}, 'rushing': {...}, 'receiving': {...}, 'kicking': {...}},
    the same stat dicts a season line or a game row carries. games: games the line covers
    (1 for a single game). teamKey: anything identifying his team, for target share.
    """
    __slots__ = ('playerId', 'stats', 'games', 'teamKey')

    def __init__(self, playerId, stats: Dict[str, Any], games: int = 1, teamKey=None):
        self.playerId = playerId
        self.stats = stats or {}
        self.games = max(1, int(games or 1))
        self.teamKey = teamKey

    def get(self, category: str, key: str) -> float:
        return float((self.stats.get(category) or {}).get(key, 0) or 0)


# A rate term: (name, weight, higherIsBetter, numerator, denominator).
_Rate = Tuple[str, float, bool, Callable[[PerfInput], float], Callable[[PerfInput], float]]


def _touches(p: PerfInput) -> float:
    return p.get('rushing', 'carries') + p.get('receiving', 'receptions')


QB_TERMS: List[_Rate] = [
    ('compPct', 1.2, True,  lambda p: p.get('passing', 'comp'),  lambda p: p.get('passing', 'att')),
    ('ypa',     1.0, True,  lambda p: p.get('passing', 'yards'), lambda p: p.get('passing', 'att')),
    ('tdRate',  1.0, True,  lambda p: p.get('passing', 'tds'),   lambda p: p.get('passing', 'att')),
    ('intRate', 1.0, False, lambda p: p.get('passing', 'ints'),  lambda p: p.get('passing', 'att')),
]

# Scrimmage yards per touch takes the old total-yards slot, so a back who catches the ball
# is credited for it (receiving was not in the RB rating at all).
RB_TERMS: List[_Rate] = [
    ('ypc',     1.2, True,  lambda p: p.get('rushing', 'yards'), lambda p: p.get('rushing', 'carries')),
    ('ypTouch', 1.2, True,  lambda p: p.get('rushing', 'yards') + p.get('receiving', 'yards'), _touches),
    ('tdRate',  1.0, True,  lambda p: p.get('rushing', 'tds') + p.get('receiving', 'tds'), _touches),
    ('fumRate', 0.6, False, lambda p: p.get('rushing', 'fumblesLost'), lambda p: p.get('rushing', 'carries')),
]

RECEIVER_TERMS: List[_Rate] = [
    ('catchRate', 1.4, True,  lambda p: p.get('receiving', 'receptions'), lambda p: p.get('receiving', 'targets')),
    ('dropRate',  1.2, False, lambda p: p.get('receiving', 'drops'),      lambda p: p.get('receiving', 'targets')),
    ('ypr',       1.0, True,  lambda p: p.get('receiving', 'yards'),      lambda p: p.get('receiving', 'receptions')),
    ('yacPerRec', 1.0, True,  lambda p: p.get('receiving', 'yac'),        lambda p: p.get('receiving', 'receptions')),
    ('tdRate',    0.6, True,  lambda p: p.get('receiving', 'tds'),        lambda p: p.get('receiving', 'targets')),
]
# Volume a receiver EARNS, measured against his own team's passing: target share takes the
# old receptions slot (0.8), receiving yards per team target the old total-yards slot (1.0).
RECEIVER_SHARE_WEIGHTS = {'targetShare': 0.8, 'yardsPerTeamTarget': 1.0}

# The made-FG total (0.7) is dropped: it counts how often the offense stalled in range.
K_TERMS: List[_Rate] = [
    ('fgPct', 1.3, True, lambda p: p.get('kicking', 'fgs'),     lambda p: p.get('kicking', 'fgAtt')),
    ('fgAvg', 1.0, True, lambda p: p.get('kicking', 'fgYards'), lambda p: p.get('kicking', 'fgs')),
]

POSITION_TERMS = {'QB': QB_TERMS, 'RB': RB_TERMS, 'WR': RECEIVER_TERMS,
                  'TE': RECEIVER_TERMS, 'K': K_TERMS}


def isRated(position: str, p: PerfInput) -> bool:
    """Who enters a position's pool (the gates the old formulas used)."""
    if position == 'QB':
        return p.get('passing', 'yards') > 0 and p.get('passing', 'att') > 0
    if position == 'RB':
        return p.get('rushing', 'yards') > 0 and p.get('rushing', 'carries') > 0
    if position in ('WR', 'TE'):
        return p.get('receiving', 'yards') > 0 and p.get('receiving', 'targets') > 0
    if position == 'K':
        return p.get('kicking', 'fgs') > 0 and p.get('kicking', 'fgAtt') > 0
    return False


def _shrunkRates(pool: List[PerfInput], num, den, priorGames: float) -> List[float]:
    """Each player's num/den, shrunk toward the pool's rate by `priorGames` games of the
    pool's median per-game volume."""
    nums = [num(p) for p in pool]
    dens = [den(p) for p in pool]
    totalDen = sum(dens)
    poolRate = (sum(nums) / totalDen) if totalDen > 0 else 0.0
    perGame = [d / p.games for d, p in zip(dens, pool)]
    prior = priorGames * (median(perGame) if perGame else 0.0)
    out = []
    for n, d in zip(nums, dens):
        denom = d + prior
        out.append((n + prior * poolRate) / denom if denom > 0 else poolRate)
    return out


def receiverShares(players: List[PerfInput]) -> Dict[Any, Tuple[float, float]]:
    """{playerId: (targetShare, yardsPerTeamTarget)}, both per game against his team's
    targets per game. `players` should be every pass catcher (RB, WR, TE) so the team
    total is complete; a player with no team is measured against the league's average."""
    teamTargets: Dict[Any, float] = {}
    teamGames: Dict[Any, int] = {}
    for p in players:
        if p.teamKey is None:
            continue
        teamTargets[p.teamKey] = teamTargets.get(p.teamKey, 0.0) + p.get('receiving', 'targets')
        teamGames[p.teamKey] = max(teamGames.get(p.teamKey, 1), p.games)
    perGameTeam = {k: teamTargets[k] / teamGames[k] for k in teamTargets}
    leagueTeam = (sum(perGameTeam.values()) / len(perGameTeam)) if perGameTeam else 0.0
    out = {}
    for p in players:
        teamPerGame = perGameTeam.get(p.teamKey, leagueTeam) or leagueTeam
        if teamPerGame <= 0:
            out[p.playerId] = (0.0, 0.0)
            continue
        out[p.playerId] = (p.get('receiving', 'targets') / p.games / teamPerGame,
                           p.get('receiving', 'yards') / p.games / teamPerGame)
    return out


def _percentiles(values: List[float], higherIsBetter: bool) -> List[float]:
    pct = [scipyStats.percentileofscore(values, v, 'rank') for v in values]
    return pct if higherIsBetter else [100.0 - x for x in pct]


def ratePosition(position: str, players: List[PerfInput],
                 shares: Optional[Dict[Any, Tuple[float, float]]] = None,
                 priorGames: float = PERF_RATE_PRIOR_GAMES) -> Dict[Any, int]:
    """{playerId: 60-100 rating} for every rated player at `position`. Receivers need
    `shares` from `receiverShares` over all pass catchers."""
    terms = POSITION_TERMS.get(position)
    if not terms:
        return {}
    pool = [p for p in players if isRated(position, p)]
    if not pool:
        return {}
    weighted = [0.0] * len(pool)
    totalWeight = 0.0
    for _name, weight, higher, num, den in terms:
        pct = _percentiles(_shrunkRates(pool, num, den, priorGames), higher)
        weighted = [w + weight * x for w, x in zip(weighted, pct)]
        totalWeight += weight
    if position in ('WR', 'TE'):
        shares = shares if shares is not None else receiverShares(pool)
        for idx, key in enumerate(('targetShare', 'yardsPerTeamTarget')):
            weight = RECEIVER_SHARE_WEIGHTS[key]
            vals = [shares.get(p.playerId, (0.0, 0.0))[idx] for p in pool]
            pct = _percentiles(vals, True)
            weighted = [w + weight * x for w, x in zip(weighted, pct)]
            totalWeight += weight
    return {p.playerId: FloosMethods.scaleValue(w / totalWeight, 60, 100, 0, 100)
            for p, w in zip(pool, weighted)}

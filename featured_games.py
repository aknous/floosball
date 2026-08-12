"""Which games are FEATURED — the ones worth clearing an evening for.

Two ways in:

  * an ELITE MATCHUP, both clubs at or above `ELITE_ELO`
  * a BUBBLE BATTLE, both clubs clustered around the playoff cutline late in the season,
    in the same league (so the result actually moves them past each other) and both still
    alive

Extracted from the `/api/currentGames` handler, where it was computed inline, so the rule
has one home.

⚠️ The reason this moved: the cutline is now derived from league size, not the hardcoded
`PLAYOFF_SPOTS = 6` it used to be. At 32 clubs the field is EIGHT per league, so a bubble
measured against a 6-spot cutline centered the window two places above the clubs actually
fighting for the last seat — the redesigned game board's FEATURED chip was landing on the
wrong games.
"""

from typing import Any, Dict, List, Optional

ELITE_ELO = 1570
# A bubble battle only means anything once the table has settled; before this the standings
# move too much for "near the cutline" to describe anybody.
BUBBLE_WEEK_MIN = 18
# How far either side of the cutline still counts as the bubble.
BUBBLE_ABOVE = 2
BUBBLE_BELOW = 3


def _leaguePositions(app) -> tuple:
    """`({teamId: 1-indexed position}, {teamId: leagueName})`, ordered by record."""
    positions: Dict[int, int] = {}
    leagueOf: Dict[int, str] = {}
    spots: Dict[int, int] = {}
    for league in getattr(getattr(app, 'leagueManager', None), 'leagues', []) or []:
        ordered = sorted(
            league.teamList,
            key=lambda t: (-(t.seasonTeamStats.get('wins', 0) or 0),
                           t.seasonTeamStats.get('losses', 0) or 0),
        )
        cut = max(1, len(ordered) // 2)
        for position, team in enumerate(ordered, 1):
            positions[team.id] = position
            leagueOf[team.id] = league.name
            spots[team.id] = cut
    return positions, leagueOf, spots


def markFeatured(app, games: List[Any], currentWeek: Optional[int] = None) -> None:
    """Stamp `isFeatured` on each game in place.

    Playoff games are deliberately NOT featured: every one of them is, so the designation
    would stop carrying information exactly when it matters most.
    """
    if currentWeek is None:
        currentSeason = getattr(getattr(app, 'seasonManager', None), 'currentSeason', None)
        currentWeek = getattr(currentSeason, 'currentWeek', 0) or 0

    isRegularSeason = isinstance(currentWeek, int) and 1 <= currentWeek <= 28
    lateRegularSeason = isRegularSeason and currentWeek >= BUBBLE_WEEK_MIN
    positions, leagueOf, spots = _leaguePositions(app)

    for game in games:
        try:
            if getattr(game, 'gameType', '') == 'playoff' or getattr(game, 'isPlayoff', False):
                game.isFeatured = False
                continue
            homeElo = getattr(game, 'homeTeamElo', getattr(game.homeTeam, 'elo', 1500)) or 1500
            awayElo = getattr(game, 'awayTeamElo', getattr(game.awayTeam, 'elo', 1500)) or 1500
            eliteMatchup = isRegularSeason and homeElo >= ELITE_ELO and awayElo >= ELITE_ELO

            homePos = positions.get(game.homeTeam.id, 99)
            awayPos = positions.get(game.awayTeam.id, 99)
            cut = spots.get(game.homeTeam.id, 8)
            sameLeague = (leagueOf.get(game.homeTeam.id) is not None
                          and leagueOf.get(game.homeTeam.id) == leagueOf.get(game.awayTeam.id))
            bothAlive = (not getattr(game.homeTeam, 'eliminated', False)
                         and not getattr(game.awayTeam, 'eliminated', False))
            inBubble = lambda p: (cut - BUBBLE_ABOVE) <= p <= (cut + BUBBLE_BELOW)
            bubbleBattle = (lateRegularSeason and sameLeague and bothAlive
                            and inBubble(homePos) and inBubble(awayPos))

            game.isFeatured = bool(eliteMatchup or bubbleBattle)
        except Exception:
            game.isFeatured = False

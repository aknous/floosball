"""Shared playoff-seeding / standings ordering.

A single source of truth so the standings board can never diverge from how the
playoffs actually seed. Tiebreaker chain, best team first:

  1. win percentage
  2. score differential (full season)
  3. head-to-head point differential among the EXACT set of tied teams
     (a mini round-robin — sums each tied team's point diff in regular-season
     games vs the OTHER tied teams; works for 2 or 3+ tied teams)
  4. points for (total points scored)
  5. points against (fewer is better)

Ties that survive all of these keep their prior (stable) order.

Operates on team objects exposing `.id` and `.seasonTeamStats` (a dict with
`winPerc`, `scoreDiff`, and `Offense.pts`). Head-to-head needs the season's
regular-season game results, passed as `h2hGames`:
a list of (home_team_id, away_team_id, home_score, away_score).
"""

REGULAR_SEASON_WEEKS = 28  # playoffs are weeks 29+; H2H excludes them


def _baseKey(team):
    s = getattr(team, 'seasonTeamStats', {}) or {}
    return (s.get('winPerc', 0) or 0, s.get('scoreDiff', 0) or 0)


def _pointsFor(team):
    s = getattr(team, 'seasonTeamStats', {}) or {}
    return (s.get('Offense', {}) or {}).get('pts', 0) or 0


def _pointsAgainst(team):
    # pointsAgainst = pointsFor - scoreDiff
    s = getattr(team, 'seasonTeamStats', {}) or {}
    return _pointsFor(team) - (s.get('scoreDiff', 0) or 0)


def _headToHeadDiff(group, h2hGames):
    """Per-team point differential in games played ONLY among `group`."""
    ids = {t.id for t in group}
    diff = {t.id: 0 for t in group}
    for home, away, homeScore, awayScore in h2hGames:
        if home in ids and away in ids:
            diff[home] += (homeScore - awayScore)
            diff[away] += (awayScore - homeScore)
    return diff


def orderTeams(teams, h2hGames=None):
    """Teams ordered best-first by the full tiebreaker chain."""
    h2hGames = h2hGames or []
    ordered = sorted(teams, key=_baseKey, reverse=True)
    result = []
    i, n = 0, len(ordered)
    while i < n:
        j = i + 1
        while j < n and _baseKey(ordered[j]) == _baseKey(ordered[i]):
            j += 1
        group = ordered[i:j]
        if len(group) > 1:
            diff = _headToHeadDiff(group, h2hGames)
            # H2H point diff, then points-for, then fewest points-against.
            group = sorted(
                group,
                key=lambda t: (diff[t.id], _pointsFor(t), -_pointsAgainst(t)),
                reverse=True,
            )
        result.extend(group)
        i = j
    return result


def buildH2HGames(session, season):
    """Final regular-season head-to-head games for `season`, as
    (home_team_id, away_team_id, home_score, away_score) tuples. Playoff weeks
    (29+) are excluded so postseason results don't skew the tiebreaker."""
    from database.models import Game
    rows = (
        session.query(
            Game.home_team_id, Game.away_team_id, Game.home_score, Game.away_score,
        )
        .filter(
            Game.season == season,
            Game.status == 'final',
            Game.week <= REGULAR_SEASON_WEEKS,
        )
        .all()
    )
    return [(r[0], r[1], r[2] or 0, r[3] or 0) for r in rows]

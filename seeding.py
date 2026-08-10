"""Shared playoff-seeding / standings ordering.

A single source of truth so the standings board can never diverge from how the
playoffs actually seed. Tiebreaker chain, best team first:

  1. win percentage
  2. CONTEXTUAL (owner, 2026-08-07):
       - all tied clubs in the SAME division -> DIVISION win%   (the division-title tiebreak)
       - otherwise                           -> LEAGUE win%     (the wildcard tiebreak)
  3. score differential (full season)
  4. head-to-head point differential among the EXACT set of tied teams
     (a mini round-robin — sums each tied team's point diff in regular-season
     games vs the OTHER tied teams; works for 2 or 3+ tied teams)
  5. points for (total points scored)
  6. points against (fewer is better)

⚠️ WHY STEP 2 SWITCHES. Division record is only comparable between clubs that played the
same division slate — 12 of 28 games against the identical three opponents. Comparing an
8-4 division record in one division against an 8-4 in another compares different opponents
and means very little. So a division title is settled on division record, and a wildcard
race — where the tied clubs come from different divisions — falls to LEAGUE record, which
they DO share a basis for (24 of 28 games are intra-league).

A tie group is treated as same-division only when EVERY club in it shares a division. Two
clubs from one division tied with a third from another is a wildcard comparison, and uses
league record.

Ties that survive all of these keep their prior (stable) order.

Operates on team objects exposing `.id` and `.seasonTeamStats` (a dict with
`winPerc`, `scoreDiff`, and `Offense.pts`). Head-to-head needs the season's
regular-season game results, passed as `h2hGames`:
a list of (home_team_id, away_team_id, home_score, away_score).
"""

REGULAR_SEASON_WEEKS = 28  # playoffs are weeks 29+; H2H excludes them


def _divisionWinPerc(team):
    """Win rate inside the club's own division, 0.0 when it has played none.

    A RATE rather than raw wins: clubs can reach the tiebreaker having played a different
    number of division games (a mid-season standings read, or an abandoned fixture), and
    raw wins would quietly reward whoever had played more of them.
    """
    s = getattr(team, 'seasonTeamStats', {}) or {}
    w = s.get('divWins', 0) or 0
    l = s.get('divLosses', 0) or 0
    t = s.get('divTies', 0) or 0
    played = w + l + t
    if not played:
        return 0.0
    return round((w + 0.5 * t) / played, 4)


def _leagueWinPerc(team):
    """Win rate against clubs in the club's own league, 0.0 when it has played none.

    The wildcard counterpart to `_divisionWinPerc`. 24 of the 28 games are intra-league, so
    two clubs from different divisions still share enough of a basis for this to mean
    something — which division record does not.
    """
    s = getattr(team, 'seasonTeamStats', {}) or {}
    w = s.get('lgWins', 0) or 0
    l = s.get('lgLosses', 0) or 0
    t = s.get('lgTies', 0) or 0
    played = w + l + t
    if not played:
        return 0.0
    return round((w + 0.5 * t) / played, 4)


def _sharedDivision(group):
    """The division every club in `group` belongs to, or None if they differ.

    None also when any club is unstamped: an unstamped club has no division record worth
    comparing, so the group falls to the league tiebreak.
    """
    divs = {getattr(t, 'division', None) for t in group}
    if len(divs) != 1:
        return None
    only = divs.pop()
    return only or None


def _baseKey(team):
    s = getattr(team, 'seasonTeamStats', {}) or {}
    return s.get('winPerc', 0) or 0


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


def orderTeams(teams, h2hGames=None):
    """Teams ordered best-first by the full tiebreaker chain (see module docstring)."""
    h2hGames = h2hGames or []
    # Grouped on win% ALONE, because step 2 is contextual — it depends on who else is in
    # the tie, so it cannot be folded into a flat sort key the way score differential was.
    ordered = sorted(teams, key=_baseKey, reverse=True)
    result = []
    i, n = 0, len(ordered)
    while i < n:
        j = i + 1
        while j < n and _baseKey(ordered[j]) == _baseKey(ordered[i]):
            j += 1
        group = ordered[i:j]
        if len(group) > 1:
            # Division title vs wildcard: same division -> division record, else league.
            rate = _divisionWinPerc if _sharedDivision(group) else _leagueWinPerc
            diff = _headToHeadDiff(group, h2hGames)
            group = sorted(
                group,
                key=lambda t: (
                    rate(t),
                    (getattr(t, 'seasonTeamStats', {}) or {}).get('scoreDiff', 0) or 0,
                    diff[t.id],
                    _pointsFor(t),
                    -_pointsAgainst(t),
                ),
                reverse=True,
            )
        result.extend(group)
        i = j
    return result

"""Week-by-week standings trajectories — the data behind a graphical standings chart.

One line per team across the season, the shape MLB graphical standings use. Derived from
the `games` table rather than stored, so it works for any completed week of any season
including ones that predate this module.

⚠️ THE WINNER IS NOT ALWAYS THE HIGHER SCORE. A frames game is decided by frames won and
points only break a level tie, so `winner_team_id` is authoritative and the scoreline is
only a fallback for rows written before that column existed. Reading the scores directly
would mis-record every frames game — the same defect that put the wrong club in the recap
email and the playoff history.

⚠️ Measured on production season 2: **14 of 336 regular-season finals (4%) have a winner
that is not the higher score**, including a 17-17 that someone won and a 20-23 won by the
club that scored 20. A scoreline reading would draw those 14 lines wrong and turn several
decided games into ties.
"""
from typing import Any, Dict, List, Optional

from sqlalchemy import text


def _resultsByWeek(session, season: int) -> Dict[int, List[tuple]]:
    """{week: [(homeId, awayId, homeScore, awayScore, winnerId), ...]} for finals only."""
    rows = session.execute(text("""
        SELECT week, home_team_id, away_team_id, home_score, away_score, winner_team_id
        FROM games
        WHERE season = :s AND LOWER(status) = 'final'
          AND (is_playoff IS NULL OR is_playoff = 0)
        ORDER BY week
    """), {'s': season}).fetchall()
    out: Dict[int, List[tuple]] = {}
    for week, home, away, hs, aws, winner in rows:
        out.setdefault(int(week or 0), []).append((home, away, hs or 0, aws or 0, winner))
    return out


def _winnerOf(home, away, hs, aws, winner) -> Optional[int]:
    """Authoritative winner, or None for a tie.

    ⚠️ `winner_team_id` first. Only fall back to the scoreline when it is absent, which
    means a legacy row — and note a legacy frames row is simply unrecoverable, since the
    frames tally was never stored on the game.
    """
    if winner:
        return winner
    if hs > aws:
        return home
    if aws > hs:
        return away
    return None


def buildStandingsHistory(session, season: int, teamsByLeague: Dict[str, List[Any]],
                          divisionsByLeague: Dict[str, Dict[str, List[int]]]) -> Dict[str, Any]:
    """Per-team cumulative trajectory, grouped by league.

    Each point carries the raw record plus the two y-axes a graphical standings chart
    wants: `gamesAbove500` (wins - losses, the classic form, which spreads the lines
    around a zero line instead of bunching them in a monotonic climb) and
    `divisionGamesBack` (behind that club's own division leader AS OF THAT WEEK, which is
    the race most of the league is actually in).
    """
    byWeek = _resultsByWeek(session, season)
    weeks = sorted(byWeek)

    allTeams = {t.id: t for members in teamsByLeague.values() for t in members}
    wins: Dict[int, int] = {tid: 0 for tid in allTeams}
    losses: Dict[int, int] = {tid: 0 for tid in allTeams}
    ties: Dict[int, int] = {tid: 0 for tid in allTeams}

    # teamId -> [point, ...]
    series: Dict[int, List[Dict[str, Any]]] = {tid: [] for tid in allTeams}
    # Division membership, flattened, so a week's leader can be found per division.
    divisionOf: Dict[int, str] = {}
    for _league, divs in (divisionsByLeague or {}).items():
        for name, ids in (divs or {}).items():
            for tid in ids:
                divisionOf[tid] = name

    for week in weeks:
        for home, away, hs, aws, winner in byWeek[week]:
            w = _winnerOf(home, away, hs, aws, winner)
            if w is None:
                for tid in (home, away):
                    if tid in ties:
                        ties[tid] += 1
                continue
            loser = away if w == home else home
            if w in wins:
                wins[w] += 1
            if loser in losses:
                losses[loser] += 1

        # A division's leader is recomputed EACH WEEK — the point of the chart is that the
        # lead changes hands, so freezing today's leader would draw a false history.
        leaderByDivision: Dict[str, tuple] = {}
        for tid in allTeams:
            div = divisionOf.get(tid)
            if div is None:
                continue
            key = (wins[tid] - losses[tid], wins[tid])
            if div not in leaderByDivision or key > leaderByDivision[div][0]:
                leaderByDivision[div] = (key, tid)

        for tid in allTeams:
            div = divisionOf.get(tid)
            gb = 0.0
            if div in leaderByDivision:
                lid = leaderByDivision[div][1]
                gb = ((wins[lid] - wins[tid]) + (losses[tid] - losses[lid])) / 2.0
            series[tid].append({
                'week': week,
                'wins': wins[tid], 'losses': losses[tid], 'ties': ties[tid],
                'gamesAbove500': wins[tid] - losses[tid],
                'divisionGamesBack': gb,
            })

    leagues = []
    for leagueName, members in teamsByLeague.items():
        divs = (divisionsByLeague or {}).get(leagueName) or {}
        leagues.append({
            'name': leagueName,
            'divisions': [{'name': n, 'teamIds': list(ids)} for n, ids in divs.items()],
            'teams': [{
                'id': t.id,
                'name': t.name,
                'abbr': getattr(t, 'abbr', None) or t.name[:3].upper(),
                'color': getattr(t, 'color', None),
                'secondaryColor': getattr(t, 'secondaryColor', None),
                'division': divisionOf.get(t.id),
                'series': series.get(t.id, []),
            } for t in members],
        })

    return {'season': season, 'weeks': weeks, 'leagues': leagues}

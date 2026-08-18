"""The box score for a finished game, rebuilt from what was persisted.

⚠️ THIS EXISTS BECAUSE A FINISHED GAME HAD NO SOURCE FOR ITS OWN STATS. The per-player
line reaches the live modal over the `game_state` WebSocket, riding on the in-memory
roster objects; `GET /api/games/{id}` only ever returned a summary. So the moment a game
left the live stream its box score was unreachable — not purged, just unserved. Measured
on a week-1 game twenty-four weeks later: the API answered 200 with the right score, and
twelve `GamePlayerStats` rows sat in the database untouched.

What IS genuinely gone is the play-by-play. Plays live only on the in-memory game object
and are never written down, which is the intended trade (owner: "only the heavy data like
all the play data needs to get purged"). A finished game therefore reads as a box score
and a final line, not as a replay.

Everything here is read-only and defensive: a missing stat group, a deleted player or a
game with no rows at all comes back as an empty section rather than an error, because a
box score is something a page displays and must never be something a page dies on.
"""
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

# The groups a line is built from, in the order a reader scans them. `returning` is last
# because it is the newest and the least often non-zero.
STAT_GROUPS = ('passing', 'rushing', 'receiving', 'kicking', 'defense', 'returning')

# What makes a player worth a row in their group. A player who took the field but did
# nothing in a category should not pad that category — the QB belongs under passing, not
# under receiving as well because the field exists on their record.
GROUP_KEY_STAT = {
    'passing':   ('att', 'comp', 'yards', 'tds'),
    'rushing':   ('carries', 'yards', 'tds'),
    'receiving': ('targets', 'receptions', 'yards', 'tds'),
    'kicking':   ('fgs', 'fgAtt', 'xp', 'punts', 'pts'),
    'defense':   ('tackles', 'sacks', 'ints', 'tfl'),
    'returning': ('puntReturns', 'puntReturnYards', 'fairCatches', 'muffs'),
}


def _hasProduction(group: str, stats: Dict[str, Any]) -> bool:
    """Did this player actually do anything in this group?"""
    if not stats:
        return False
    for key in GROUP_KEY_STAT.get(group, ()):
        try:
            if float(stats.get(key) or 0) != 0:
                return True
        except (TypeError, ValueError):
            continue
    return False


def buildBoxScore(session, gameId: int) -> Optional[Dict[str, Any]]:
    """Per-team, per-group player lines for one game, or None if nothing was stored.

    Returns `{'home': {group: [line, …]}, 'away': {…}, 'teamIds': {...}}`. Grouping is by
    the team id ON THE STAT ROW rather than by the player's CURRENT team — a player traded
    or released since is still credited to the club they played that game for, which is
    the whole point of a historical box score.
    """
    try:
        from database.models import GamePlayerStats, Game, Player
    except Exception as e:
        logger.debug(f"Box score unavailable (models): {e}")
        return None

    try:
        game = session.query(Game).filter(Game.id == gameId).first()
        if game is None:
            return None
        rows = session.query(GamePlayerStats).filter(
            GamePlayerStats.game_id == gameId).all()
        if not rows:
            return None

        names: Dict[int, Dict[str, Any]] = {}
        ids = {r.player_id for r in rows}
        if ids:
            for p in session.query(Player).filter(Player.id.in_(ids)).all():
                names[p.id] = {'name': p.name, 'position': getattr(p, 'position', None)}

        out: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
            'home': {g: [] for g in STAT_GROUPS},
            'away': {g: [] for g in STAT_GROUPS},
        }
        for r in rows:
            side = 'home' if r.team_id == game.home_team_id else 'away'
            who = names.get(r.player_id, {})
            for group in STAT_GROUPS:
                stats = getattr(r, f'{group}_stats', None) or {}
                if not _hasProduction(group, stats):
                    continue
                out[side][group].append({
                    'playerId': r.player_id,
                    'name': who.get('name') or f'Player {r.player_id}',
                    'position': who.get('position'),
                    'teamId': r.team_id,
                    'stats': stats,
                    'fantasyPoints': r.fantasy_points or 0,
                })

        # Biggest contributor first within a group, so the line a reader wants is the one
        # they see. Yards is the common currency; kicking and defense fall back to points
        # and tackles respectively.
        def sortKey(group: str):
            def key(line):
                s = line['stats'] or {}
                for k in ('yards', 'pts', 'tackles', 'puntReturnYards'):
                    if k in s:
                        try:
                            return -float(s.get(k) or 0)
                        except (TypeError, ValueError):
                            return 0.0
                return 0.0
            return key

        for side in ('home', 'away'):
            for group in STAT_GROUPS:
                out[side][group].sort(key=sortKey(group))
            # Drop empty groups so a client can render whatever it is handed without
            # having to know which sections happen to be empty this week.
            out[side] = {g: v for g, v in out[side].items() if v}

        out['teamIds'] = {'home': game.home_team_id, 'away': game.away_team_id}
        return out
    except Exception as e:
        logger.debug(f"Box score build failed for game {gameId}: {e}")
        return None


def postgamePlaysFor(session, gameId):
    """The stored postgame lines for one game, in the cutaway shape the live feed used.

    ⚠️ Needed because a FINISHED game can be served from either path. The archive rebuild
    below uses `_postgamePlays` on the row it already loaded; the LIVE path serves a game
    still held in memory — and after a restart that object can be a shell with an empty
    feed, which is exactly what happened: game 607 came back `status: Final`, six quotes
    sitting in its row, and `plays: []`, because it was found in memory and so never
    reached the archive rebuild at all. Whichever path serves the game, the lines have to
    be reachable.
    """
    try:
        from database.models import Game
        row = session.query(Game).filter(Game.id == gameId).first()
        return _postgamePlays(row) if row is not None else []
    except Exception:
        return []


def _postgamePlays(gameRow):
    """The persisted postgame lines, shaped as the cutaway-carrying plays the live feed
    produced, so every existing reader works unchanged. Empty for games that finished
    before the column existed — there is nothing to recover, since these only ever lived
    in memory."""
    raw = getattr(gameRow, 'postgame_quotes', None)
    if not raw:
        return []
    try:
        import json
        quotes = json.loads(raw) or []
    except Exception:
        return []
    return [{
        'isSidelineCutaway': True,
        'sidelineCutaway': q,
        # These all happened at the whistle; the rail sorts on the stamped time inside
        # the cutaway, so the ordering here is only a stable tiebreak.
        'playNumber': 0.9,
        'quarter': None,
        'timeRemaining': '0:00',
    } for q in quotes if isinstance(q, dict)]


def buildFinishedGame(session, gameId: int) -> Optional[Dict[str, Any]]:
    """A finished game rebuilt entirely from the database.

    The game endpoint searches memory first and 404s when a game is not there. That is
    fine while a season is live, but it means a restart — or any game the schedule no
    longer holds — is simply gone. This is the fallback: enough to render a result and a
    box score, with `plays` deliberately empty.
    """
    try:
        from database.models import Game, Team
    except Exception:
        return None
    try:
        g = session.query(Game).filter(Game.id == gameId).first()
        if g is None:
            return None
        teams = {t.id: t for t in session.query(Team).filter(
            Team.id.in_([g.home_team_id, g.away_team_id])).all()}

        def side(teamId, score, quarters):
            t = teams.get(teamId)
            return {
                'id': str(teamId),
                'name': getattr(t, 'name', 'Unknown'),
                'city': getattr(t, 'city', ''),
                'abbr': getattr(t, 'abbr', None) or (getattr(t, 'name', '???')[:3].upper()),
                'color': getattr(t, 'color', '#888888'),
                'secondaryColor': getattr(t, 'secondary_color', None) or getattr(t, 'color', '#888888'),
                'score': score,
                'quarters': quarters,
            }

        return {
            'id': g.id,
            'season': g.season,
            'week': g.week,
            'status': 'Final' if g.status == 'final' else g.status,
            'isOvertime': bool(g.is_overtime),
            'isPlayoff': bool(g.is_playoff),
            'playoffRound': g.playoff_round,
            'homeScore': g.home_score,
            'awayScore': g.away_score,
            'homeTeam': side(g.home_team_id, g.home_score,
                             [g.home_score_q1, g.home_score_q2, g.home_score_q3,
                              g.home_score_q4, g.home_score_ot]),
            'awayTeam': side(g.away_team_id, g.away_score,
                             [g.away_score_q1, g.away_score_q2, g.away_score_q3,
                              g.away_score_q4, g.away_score_ot]),
            # ⚠️ NOT ENTIRELY EMPTY ANY MORE. Plays are still never persisted — the feed
            # is large and that is a deliberate trade — but the POSTGAME LINES are, and
            # they are handed back in the cutaway shape the live feed used. That is what
            # lets the Bleachers rail render them with no client change at all: it reads
            # cutaways out of `plays`, and cannot tell these came from a column.
            'plays': _postgamePlays(g),
            'fromArchive': True,
        }
    except Exception as e:
        logger.debug(f"Archived game rebuild failed for {gameId}: {e}")
        return None

"""How far a club got in the playoffs, season by season.

⚠️ DERIVED, NOT STORED. `games` already carries `is_playoff` and `playoff_round` for every
postseason game ever played, so a club's run is recoverable by reading the deepest round
it appears in. That matters more than it sounds: a stored field would only start working
the season it shipped, while this answers for every season already in the database.

The gap it fills (user report): "My pathetic team only made the playoffs 4 out of 17
times, but I can't tell how far they went on any of those other than the Floosbowl
(because of the League Champions badge). I want to be able to see R1, R2, CR."

Round numbers map to the four-round bracket described in CLAUDE.md:
    1 -> Playoffs Round 1     2 -> Playoffs Round 2
    3 -> League Championship  4 -> Floos Bowl
"""
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

# label, and the short form a badge uses
ROUND_LABEL = {
    1: ('Round 1', 'R1'),
    2: ('Round 2', 'R2'),
    3: ('League Championship', 'CR'),
    4: ('Floos Bowl', 'FB'),
}
FINAL_ROUND = 4


def _roundNumber(raw: Any) -> Optional[int]:
    """`playoff_round` is stored as a string. Tolerate the round NAME too.

    The column has held plain numbers ('1'..'4') in every season checked, but the season
    manager also knows these rounds by name, so a future writer using the name should not
    silently produce a club with no playoff history.
    """
    if raw is None:
        return None
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        pass
    text = str(raw).strip().lower()
    if 'floos' in text:
        return 4
    if 'championship' in text:
        return 3
    if '2' in text:
        return 2
    if '1' in text:
        return 1
    return None


def buildPlayoffHistory(session, teamId: int) -> List[Dict[str, Any]]:
    """One entry per season this club reached the postseason, newest first.

    Each entry says the deepest round they played, whether they won it, and how their run
    ended — which is the actual question ("how far did we get"), not simply which games
    they were in.
    """
    try:
        from database.models import Game
    except Exception as e:
        logger.debug(f"Playoff history unavailable: {e}")
        return []

    try:
        rows = (
            session.query(Game)
            .filter(Game.is_playoff == True,  # noqa: E712 — SQLAlchemy needs the comparison
                    Game.status == 'final',
                    (Game.home_team_id == teamId) | (Game.away_team_id == teamId))
            .all()
        )
    except Exception as e:
        logger.debug(f"Playoff history query failed for team {teamId}: {e}")
        return []

    bySeason: Dict[int, Dict[int, Any]] = {}
    for g in rows:
        rnd = _roundNumber(g.playoff_round)
        if rnd is None:
            continue
        isHome = g.home_team_id == teamId
        ours = g.home_score if isHome else g.away_score
        theirs = g.away_score if isHome else g.home_score
        # ⚠️ The stored winner decides, not the points. A frames playoff game is won on
        # frames, so `ours > theirs` would report the wrong side — and a wrong playoff run
        # is worse than a wrong regular-season row, since this drives how deep a club is
        # shown to have gone. Falls back to points for rows predating the column.
        winnerId = getattr(g, 'winner_team_id', None)
        won = (winnerId == teamId) if winnerId is not None else (ours > theirs)
        bySeason.setdefault(g.season, {})[rnd] = {
            'won': won,
            'for': ours, 'against': theirs,
            'opponentId': g.away_team_id if isHome else g.home_team_id,
            'gameId': g.id,
        }

    out: List[Dict[str, Any]] = []
    for season in sorted(bySeason, reverse=True):
        games = bySeason[season]
        deepest = max(games)
        last = games[deepest]
        label, short = ROUND_LABEL.get(deepest, (f'Round {deepest}', f'R{deepest}'))

        if deepest == FINAL_ROUND and last['won']:
            outcome, badge = 'Champions', 'CHAMPIONS'
        elif deepest == FINAL_ROUND:
            outcome, badge = 'Lost the Floos Bowl', 'FB'
        elif last['won']:
            # Won their last recorded game without a further round — the bracket did not
            # continue for them, which should not happen, so say so rather than invent it.
            outcome, badge = f'Won {label}', short
        else:
            outcome, badge = f'Lost in {label}', short

        out.append({
            'season': season,
            'roundsPlayed': sorted(games),
            'deepestRound': deepest,
            'deepestRoundLabel': label,
            'badge': badge,
            'outcome': outcome,
            'wins': sum(1 for r in games.values() if r['won']),
            'losses': sum(1 for r in games.values() if not r['won']),
            'games': [
                {'round': r, 'roundLabel': ROUND_LABEL.get(r, (f'Round {r}', ''))[0], **games[r]}
                for r in sorted(games)
            ],
        })
    return out


def summarize(history: List[Dict[str, Any]], seasonsPlayed: Optional[int] = None) -> Dict[str, Any]:
    """The one-line version: appearances, titles, and how deep they usually get."""
    if not history:
        return {'appearances': 0, 'titles': 0, 'bestRound': None,
                'bestRoundLabel': None, 'seasonsPlayed': seasonsPlayed}
    best = max(h['deepestRound'] for h in history)
    return {
        'appearances': len(history),
        'titles': sum(1 for h in history if h['badge'] == 'CHAMPIONS'),
        'bestRound': best,
        'bestRoundLabel': ROUND_LABEL.get(best, (f'Round {best}', ''))[0],
        'seasonsPlayed': seasonsPlayed,
    }

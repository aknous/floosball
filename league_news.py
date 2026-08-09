"""One publisher for the league-news feed.

The feed is PERSISTED and cumulative. That is the whole point: it must not clear when the
week rolls over, and stories fall off the bottom because the reader asks for a fixed
number of them, not because the sim stopped considering them true. An earlier version
generated the feed from current state on every request, which meant a clinch stopped being
news the moment the standings moved on and nothing that happened in week 9 was ever
visible in week 10.

So a news item is published AT THE MOMENT IT HAPPENS, by whichever system it happened in,
through `publish()` below. Three rules that come with that:

  * Every headline is ONE templated clause. No analysis, no second sentence. An earlier
    design draft gave the lead authored editorial prose and it was rejected — nothing here
    publishes copy at that level and an automated version never would.
  * A LEAD item carries exactly four numbers. Carrying `stats` is what makes an item
    eligible to lead; everything else is a row.
  * Publishing is best-effort. A news write must never be the thing that takes down a game
    end, a rule vote or a criticality — every call site swallows its own failure.
"""

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger('floosball.leagueNews')

# Categories the front page knows how to colour. Anything else still stores and renders,
# just in the muted fallback.
CLINCHED = 'clinched'
ELIMINATED = 'eliminated'
UPSET = 'upset'
RECORD = 'record'
BIG_GAME = 'big_game'
STREAK = 'streak'
CRITICALITY = 'criticality'
RULES = 'rules'
ANOMALY = 'anomaly_transition'
CORES = 'cores'
SIGNING = 'signing'
# An item written by a person, from the admin portal. Everything else in this file is
# published BY a system AT the moment its event happened; this is the one category with a
# human author, which is why it is never subject to the per-category caps downstream.
ANNOUNCEMENT = 'announcement'


def stat(label: str, value: Any, positive: Optional[bool] = None) -> Dict[str, Any]:
    """One cell of a lead item's four-number strip."""
    entry: Dict[str, Any] = {'label': label, 'value': str(value)}
    if positive is not None:
        entry['positive'] = positive
    return entry


def publish(
    session,
    *,
    season: int,
    week: int,
    category: str,
    text: str,
    eventType: Optional[str] = None,
    teamId: Optional[int] = None,
    playerId: Optional[int] = None,
    playerName: Optional[str] = None,
    stats: Optional[List[Dict[str, Any]]] = None,
    leadWeight: Optional[float] = None,
    core: Optional[str] = None,
    coreDisplayName: Optional[str] = None,
    anomalyState: Optional[str] = None,
    exchangeId: Optional[str] = None,
    turnIndex: Optional[int] = None,
    turnCount: Optional[int] = None,
    commit: bool = True,
    broadcast: bool = True,
) -> None:
    """Persist a news item and push it to anyone currently connected.

    Persist FIRST. If the broadcast fails the row still survives and the item shows up on
    the reader's next load, which is the failure mode that matters — the reverse loses it
    entirely.

    `commit=False` when the caller owns a transaction it is about to commit anyway (the
    game-end path does), so a news write does not force an early flush of half-applied
    game state.
    """
    try:
        from database.models import LeagueNewsItem
        session.add(LeagueNewsItem(
            season=season,
            week=week,
            category=category,
            event_type=eventType,
            text=text,
            team_id=teamId,
            player_id=playerId,
            player_name=playerName,
            stats_json=json.dumps(stats) if stats else None,
            lead_weight=leadWeight,
            core=core,
            core_display_name=coreDisplayName,
            anomaly_state=anomalyState,
            exchange_id=exchangeId,
            turn_index=turnIndex,
            turn_count=turnCount,
        ))
        if commit:
            session.commit()
    except Exception as e:
        if commit:
            try:
                session.rollback()
            except Exception:
                pass
        logger.debug(f"League news persist skipped ({category}): {e}")

    if not broadcast:
        return
    try:
        from api.game_broadcaster import broadcaster
        from api.event_models import LeagueNewsEvent
        if broadcaster is None or LeagueNewsEvent is None or not broadcaster.is_enabled():
            return
        event = LeagueNewsEvent.leagueNews(text=text)
        event['category'] = category
        if eventType:
            event['eventType'] = eventType
        # `broadcast_sync('season', ...)` is the sim-thread-safe path — the async
        # `broadcast_season_event` needs a running loop, which the game engine does not
        # have. This mirrors what the Cores news path already does.
        broadcaster.broadcast_sync('season', event)
    except Exception as e:
        logger.debug(f"League news broadcast skipped ({category}): {e}")


def publishSafe(sessionFactory, **kwargs) -> None:
    """`publish` for callers that hold no session — opens and closes its own.

    Used from the game engine, which runs on the sim thread and has no session of its own
    to borrow.
    """
    try:
        session = sessionFactory()
    except Exception as e:
        logger.debug(f"League news session unavailable: {e}")
        return
    try:
        publish(session, **kwargs)
    finally:
        try:
            session.close()
        except Exception:
            pass

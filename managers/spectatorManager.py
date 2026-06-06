"""Spectator income — the cheer bar (feature/fan-income).

The ACTIVE non-fantasy path: watching live games fills a segmented bar, each
completed segment pays Floobits. **Server-validated:** fill is credited only for
plays that ACTUALLY happened in a game the user is heartbeating (the endpoint
reads the live game's play count from the in-memory season state and passes it
in), so you can't earn faster than the game plays, a blurred/closed tab sends no
heartbeats, and per-game/weekly caps bound idling or botting.

Per-game witnessed-play tracking is in-memory (ephemeral session state); only the
durable bar + weekly cap live in SpectatorProgress.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Dict, Optional

from sqlalchemy.orm import Session

from database.models import SpectatorProgress
from constants import (
    SPECTATOR_FILL_PER_PLAY,
    SPECTATOR_FILL_PER_POINT,
    SPECTATOR_SEGMENT_SIZE,
    SPECTATOR_SEGMENT_PAYOUT,
    SPECTATOR_RALLY_FILL,
    SPECTATOR_REACTION_FILL,
    SPECTATOR_REACTION_CAP_PER_GAME,
    SPECTATOR_SUPPORTED_TEAM_MULT,
    SPECTATOR_HEARTBEAT_WINDOW_SEC,
    SPECTATOR_MAX_PLAYS_PER_HEARTBEAT,
    SPECTATOR_WEEKLY_PAYOUT_CAP,
)
from logger_config import get_logger

logger = get_logger("floosball.spectator")

# Per-user live watch state (ephemeral): userId -> {gameId, lastPlayCount,
# lastBeat (epoch s), reactionCount}. Resets when the heartbeat window lapses.
_watch: Dict[int, dict] = {}


def _weekMarker(season: Optional[int], week: Optional[int]) -> int:
    return (season or 0) * 100 + (week or 0)


def _present(userId: int) -> bool:
    """True if the user has a non-stale watch session (recently heartbeated)."""
    st = _watch.get(userId)
    return bool(st and (time.time() - st.get('lastBeat', 0)) <= SPECTATOR_HEARTBEAT_WINDOW_SEC)


def _loadProgress(session: Session, userId: int, season: int, week: int) -> SpectatorProgress:
    p = session.query(SpectatorProgress).filter_by(user_id=userId).first()
    if p is None:
        p = SpectatorProgress(user_id=userId, bar_fill=0.0, week_marker=_weekMarker(season, week))
        session.add(p)
    wm = _weekMarker(season, week)
    if p.week_marker != wm:  # week rolled — reset the weekly cap counters
        p.week_marker = wm
        p.weekly_floobits = 0
        p.weekly_segments = 0
    return p


def _addFill(session: Session, userId: int, fill: float, season: int, week: int) -> None:
    """Add fill to the bar and pay out completed segments up to the weekly cap.
    Caller commits."""
    p = _loadProgress(session, userId, season, week)
    if fill > 0:
        p.bar_fill = (p.bar_fill or 0.0) + fill
    from database.repositories.card_repositories import CurrencyRepository
    repo = CurrencyRepository(session)
    while p.bar_fill >= SPECTATOR_SEGMENT_SIZE and (p.weekly_floobits or 0) < SPECTATOR_WEEKLY_PAYOUT_CAP:
        p.bar_fill -= SPECTATOR_SEGMENT_SIZE
        payout = min(SPECTATOR_SEGMENT_PAYOUT, SPECTATOR_WEEKLY_PAYOUT_CAP - (p.weekly_floobits or 0))
        repo.addFunds(userId, payout, 'spectator_cheer',
                      description='Cheer bar segment', season=season, week=week)
        p.weekly_floobits = (p.weekly_floobits or 0) + payout
        p.weekly_segments = (p.weekly_segments or 0) + 1
    # Once capped out for the week, don't let the bar balloon.
    if (p.weekly_floobits or 0) >= SPECTATOR_WEEKLY_PAYOUT_CAP:
        p.bar_fill = min(p.bar_fill, SPECTATOR_SEGMENT_SIZE * 0.99)
    p.updated_at = datetime.utcnow()


def _status(session: Session, userId: int, season: int, week: int) -> dict:
    p = _loadProgress(session, userId, season, week)
    fill = p.bar_fill or 0.0
    return {
        'barFill': round(fill, 1),
        'segmentSize': SPECTATOR_SEGMENT_SIZE,
        'segmentProgress': round(min(1.0, fill / SPECTATOR_SEGMENT_SIZE), 3),
        'segmentPayout': SPECTATOR_SEGMENT_PAYOUT,
        'weeklyFloobits': p.weekly_floobits or 0,
        'weeklyCap': SPECTATOR_WEEKLY_PAYOUT_CAP,
        'weeklySegments': p.weekly_segments or 0,
        'cappedOut': (p.weekly_floobits or 0) >= SPECTATOR_WEEKLY_PAYOUT_CAP,
        'present': _present(userId),
    }


def heartbeat(session: Session, userId: int, gameId: int, currentPlayCount: int,
              supportedTeam: bool, season: int, week: int, currentScore: int = 0) -> dict:
    """A presence heartbeat for a live game. Credits fill for the plays that have
    actually happened since the last heartbeat (capped per beat) PLUS a bonus for
    points scored in that window (TDs/FGs fill faster), scaled up for your
    supported team. The first beat (or after the window lapses) just sets a
    baseline — no retroactive credit. Caller need not commit (we do)."""
    now = time.time()
    st = _watch.get(userId)
    fresh = (not st or st.get('gameId') != gameId
             or (now - st.get('lastBeat', 0)) > SPECTATOR_HEARTBEAT_WINDOW_SEC)
    if fresh:
        _watch[userId] = {'gameId': gameId, 'lastPlayCount': currentPlayCount,
                          'lastScore': currentScore, 'lastBeat': now, 'reactionCount': 0}
        _loadProgress(session, userId, season, week)
        session.commit()
        return _status(session, userId, season, week)

    newPlays = max(0, min(currentPlayCount - st['lastPlayCount'], SPECTATOR_MAX_PLAYS_PER_HEARTBEAT))
    newPoints = max(0, currentScore - st.get('lastScore', currentScore))  # score only climbs
    st['lastPlayCount'] = currentPlayCount
    st['lastScore'] = currentScore
    st['lastBeat'] = now
    mult = SPECTATOR_SUPPORTED_TEAM_MULT if supportedTeam else 1.0
    fill = (newPlays * SPECTATOR_FILL_PER_PLAY + newPoints * SPECTATOR_FILL_PER_POINT) * mult
    _addFill(session, userId, fill, season, week)
    session.commit()
    return _status(session, userId, season, week)


def addRallyFill(session: Session, userId: int, season: int, week: int) -> None:
    """A (free) rally adds fill — only while the user is actively present."""
    if not _present(userId):
        return
    _addFill(session, userId, SPECTATOR_RALLY_FILL, season, week)
    session.commit()


def addReactionFill(session: Session, userId: int, gameId: int, season: int, week: int) -> None:
    """A reaction adds a little fill, diminishing (capped per game), present-only."""
    st = _watch.get(userId)
    if not _present(userId) or not st or st.get('gameId') != gameId:
        return
    if st.get('reactionCount', 0) >= SPECTATOR_REACTION_CAP_PER_GAME:
        return
    st['reactionCount'] = st.get('reactionCount', 0) + 1
    _addFill(session, userId, SPECTATOR_REACTION_FILL, season, week)
    session.commit()


def getStatus(session: Session, userId: int, season: int, week: int) -> dict:
    s = _status(session, userId, season, week)
    session.commit()
    return s

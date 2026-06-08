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
    SPECTATOR_BIG_PLAY_FILL,
    SPECTATOR_OWN_BIG_PLAY_MULT,
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


def claim(session: Session, userId: int, gameId: int, witnessedPlays: int,
          witnessedPoints: int, supportedTeam: bool, season: int, week: int,
          realPlayCount: int, realScore: int, witnessedBigPlays: int = 0,
          realBigMine: int = 0, realBigOther: int = 0) -> dict:
    """WS-driven bank. The client watches the season WebSocket and counts the
    plays/points (and big plays) it actually WITNESSED (modal open + tab visible)
    since its last bank; it posts those here. We credit the MINIMUM of what the
    client claims and the game's REAL progress since the last claim (the endpoint
    reads the live game's true play count/score/big-plays from in-memory state):

      * fill can't outrun the game        (witnessed capped to real → anti-cheat)
      * plays that streamed by while the   (the client never witnessed them →
        modal was closed aren't credited    witnessed stays low → that's the cap)

    Big plays (WPA-swing highlights) pay a bonus on top of the per-play fill,
    worth more when YOUR supported team made it (`realBigMine` vs `realBigOther`
    are the season-state big-play counts attributed to your team / the other).

    The witnessed count IS the presence signal, so there's no fixed polling
    cadence: the client banks on segment completion, a slow keepalive, and on
    close. A claim that credits nothing (a keepalive during a lull, or the first
    sync after reopening) does no DB write. Caller need not commit."""
    now = time.time()
    st = _watch.get(userId)
    if not st or st.get('gameId') != gameId:
        # New watch session (first claim, or switched games) — baseline at the
        # current real progress, credit nothing retroactively.
        _watch[userId] = {'gameId': gameId, 'lastPlayCount': realPlayCount,
                          'lastScore': realScore, 'lastBeat': now, 'reactionCount': 0,
                          'lastBigMine': realBigMine, 'lastBigOther': realBigOther}
        _loadProgress(session, userId, season, week)
        session.commit()  # persist the row (and any week-rollover reset)
        return _status(session, userId, season, week)

    realPlays = max(0, realPlayCount - st['lastPlayCount'])
    realPoints = max(0, realScore - st.get('lastScore', realScore))
    creditPlays = max(0, min(int(witnessedPlays or 0), realPlays))
    creditPoints = max(0, min(int(witnessedPoints or 0), realPoints))
    st['lastPlayCount'] = realPlayCount
    st['lastScore'] = realScore
    st['lastBeat'] = now

    # Big plays: credit what the client witnessed, capped by what really
    # happened this window; attribute to your team (own-mult) vs the other.
    realMineDelta = max(0, realBigMine - st.get('lastBigMine', realBigMine))
    realOtherDelta = max(0, realBigOther - st.get('lastBigOther', realBigOther))
    st['lastBigMine'] = realBigMine
    st['lastBigOther'] = realBigOther
    creditBig = max(0, min(int(witnessedBigPlays or 0), realMineDelta + realOtherDelta))
    mineCredit = min(creditBig, realMineDelta)
    otherCredit = creditBig - mineCredit
    bigFill = (mineCredit * SPECTATOR_BIG_PLAY_FILL * SPECTATOR_OWN_BIG_PLAY_MULT
               + otherCredit * SPECTATOR_BIG_PLAY_FILL)

    if creditPlays or creditPoints or bigFill:
        mult = SPECTATOR_SUPPORTED_TEAM_MULT if supportedTeam else 1.0
        fill = (creditPlays * SPECTATOR_FILL_PER_PLAY + creditPoints * SPECTATOR_FILL_PER_POINT) * mult
        fill += bigFill
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

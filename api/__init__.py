"""
Floosball API Package
Modern API layer with REST endpoints and WebSocket support
"""

from .websocket_manager import manager as websocket_manager
from .game_broadcaster import broadcaster
from .event_models import (
    EventType,
    GameEvent,
    SeasonEvent,
    StandingsEvent,
    PlayerEvent,
    SystemEvent
)

__all__ = [
    'websocket_manager',
    'broadcaster',
    'EventType',
    'GameEvent',
    'SeasonEvent',
    'StandingsEvent',
    'PlayerEvent',
    'SystemEvent'
]

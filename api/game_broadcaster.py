"""
Game Broadcasting Module
Provides hooks for broadcasting game events via WebSocket during simulation
"""

import asyncio
from typing import Optional, Dict, Any
from logger_config import get_logger

logger = get_logger("floosball.game_broadcaster")

class GameBroadcaster:
    """
    Singleton class that handles broadcasting game events to WebSocket clients
    Can be enabled/disabled to avoid overhead when not needed
    """

    _instance = None
    _enabled = False
    _ws_manager = None
    _main_loop = None  # Main asyncio event loop — required for dispatching from threadpool (sync REST endpoints)

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GameBroadcaster, cls).__new__(cls)
        return cls._instance

    @classmethod
    def enable(cls, ws_manager):
        """Enable broadcasting with a WebSocket manager"""
        cls._enabled = True
        cls._ws_manager = ws_manager
        logger.info("Game broadcasting ENABLED")

    @classmethod
    def set_main_loop(cls, loop):
        """Store the main event loop reference so sync code (REST threadpool) can dispatch broadcasts."""
        cls._main_loop = loop
        logger.info("Main event loop registered for cross-thread broadcasts")
    
    @classmethod
    def disable(cls):
        """Disable broadcasting to reduce overhead"""
        cls._enabled = False
        cls._ws_manager = None
        logger.info("Game broadcasting DISABLED")
    
    @classmethod
    def is_enabled(cls) -> bool:
        """Check if broadcasting is enabled"""
        return cls._enabled and cls._ws_manager is not None
    
    @classmethod
    async def broadcast_game_event(cls, game_id: int, event: Dict[str, Any]):
        """
        Broadcast an event to game-specific channel
        
        Args:
            game_id: The game ID
            event: Event dictionary to broadcast
        """
        if not cls.is_enabled():
            return
        
        try:
            channel = f"game_{game_id}"
            await cls._ws_manager.broadcast(event, channel)
            
            # Also broadcast to season channel for global listeners
            await cls._ws_manager.broadcast(event, "season")
            
        except Exception as e:
            logger.error(f"Error broadcasting game event: {e}")
    
    @classmethod
    async def broadcast_season_event(cls, event: Dict[str, Any]):
        """
        Broadcast an event to season channel
        
        Args:
            event: Event dictionary to broadcast
        """
        if not cls.is_enabled():
            return
        
        try:
            await cls._ws_manager.broadcast(event, "season")
        except Exception as e:
            logger.error(f"Error broadcasting season event: {e}")
    
    @classmethod
    async def broadcast_standings_update(cls, standings: Dict[str, Any]):
        """
        Broadcast standings update to standings channel
        
        Args:
            standings: Standings data to broadcast
        """
        if not cls.is_enabled():
            return
        
        try:
            await cls._ws_manager.broadcast(standings, "standings")
            await cls._ws_manager.broadcast(standings, "season")
        except Exception as e:
            logger.error(f"Error broadcasting standings update: {e}")
    
    @classmethod
    async def broadcast_to_user(cls, userId: int, event: Dict[str, Any]) -> int:
        """Send an event to every WebSocket identified as this user. Returns count."""
        if not cls.is_enabled():
            return 0
        try:
            return await cls._ws_manager.send_to_user(userId, event)
        except Exception as e:
            logger.error(f"Error broadcasting to user {userId}: {e}")
            return 0

    @classmethod
    def broadcast_to_user_sync(cls, userId: int, event: Dict[str, Any]) -> None:
        """Fire-and-forget user broadcast from sync code. Works from both async
        context (running loop) and sync threadpool (FastAPI sync endpoints)."""
        if not cls.is_enabled():
            return
        try:
            # Prefer an already-running loop in the current thread
            try:
                loop = asyncio.get_running_loop()
                asyncio.create_task(cls.broadcast_to_user(userId, event))
                return
            except RuntimeError:
                pass
            # Fallback: dispatch onto the main loop from a worker thread
            if cls._main_loop is not None and cls._main_loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    cls.broadcast_to_user(userId, event), cls._main_loop,
                )
            else:
                logger.warning("broadcast_to_user_sync: no running loop available")
        except Exception as e:
            logger.error(f"Error in sync user broadcast: {e}")

    @classmethod
    def broadcast_sync(cls, game_id: int, event: Dict[str, Any]):
        """
        Synchronous wrapper for broadcasting (creates async task).
        Works from both async context and sync threadpool.

        Args:
            game_id: The game ID
            event: Event dictionary to broadcast
        """
        if not cls.is_enabled():
            return

        try:
            try:
                loop = asyncio.get_running_loop()
                asyncio.create_task(cls.broadcast_game_event(game_id, event))
                return
            except RuntimeError:
                pass
            if cls._main_loop is not None and cls._main_loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    cls.broadcast_game_event(game_id, event), cls._main_loop,
                )
            else:
                logger.warning("broadcast_sync: no running loop available")
        except Exception as e:
            logger.error(f"Error in sync broadcast: {e}")


# Global singleton instance
broadcaster = GameBroadcaster()

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
    def broadcast_sync(cls, game_id: int, event: Dict[str, Any]):
        """
        Synchronous wrapper for broadcasting (creates async task)
        Use this from synchronous game code
        
        Args:
            game_id: The game ID
            event: Event dictionary to broadcast
        """
        if not cls.is_enabled():
            return
        
        try:
            # Get or create event loop
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                # No running loop, create a task in the default loop
                loop = asyncio.get_event_loop()
            
            # Schedule the broadcast as a task
            if loop.is_running():
                asyncio.create_task(cls.broadcast_game_event(game_id, event))
            else:
                loop.create_task(cls.broadcast_game_event(game_id, event))
                
        except Exception as e:
            logger.error(f"Error in sync broadcast: {e}")


# Global singleton instance
broadcaster = GameBroadcaster()

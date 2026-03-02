"""
WebSocket Connection Manager for Floosball
Manages WebSocket connections for real-time game updates and broadcasting
"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set, List, Any, Optional
import asyncio
import json
from datetime import datetime
from logger_config import get_logger

logger = get_logger("floosball.websocket")

class ConnectionManager:
    """Manages WebSocket connections and message broadcasting"""
    
    def __init__(self):
        # Dictionary mapping channel names to sets of websocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        
        # Track connection metadata
        self.connection_metadata: Dict[WebSocket, Dict[str, Any]] = {}
        
        logger.info("WebSocket ConnectionManager initialized")
    
    async def connect(self, websocket: WebSocket, channel: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Accept a new WebSocket connection and add it to a channel
        
        Args:
            websocket: The WebSocket connection
            channel: Channel name (e.g., "game_123", "season", "standings")
            metadata: Optional metadata about the connection (user_id, etc.)
        """
        await websocket.accept()
        
        # Add to channel
        if channel not in self.active_connections:
            self.active_connections[channel] = set()
        self.active_connections[channel].add(websocket)
        
        # Store metadata
        if metadata:
            self.connection_metadata[websocket] = {
                **metadata,
                'channel': channel,
                'connected_at': datetime.now().isoformat()
            }
        
        logger.info(f"WebSocket connected to channel '{channel}' (total: {len(self.active_connections[channel])})")
    
    def disconnect(self, websocket: WebSocket, channel: str):
        """
        Remove a WebSocket connection from a channel
        
        Args:
            websocket: The WebSocket connection
            channel: Channel name
        """
        if channel in self.active_connections:
            self.active_connections[channel].discard(websocket)
            
            # Clean up empty channels
            if len(self.active_connections[channel]) == 0:
                del self.active_connections[channel]
        
        # Remove metadata
        if websocket in self.connection_metadata:
            del self.connection_metadata[websocket]
        
        logger.info(f"WebSocket disconnected from channel '{channel}'")
    
    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        """
        Send a message to a specific WebSocket connection
        
        Args:
            message: Message dictionary to send
            websocket: Target WebSocket connection
        """
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
    
    async def broadcast(self, message: Dict[str, Any], channel: str):
        """
        Broadcast a message to all connections in a channel
        
        Args:
            message: Message dictionary to broadcast
            channel: Channel name
        """
        if channel not in self.active_connections:
            logger.debug(f"No active connections for channel '{channel}'")
            return
        
        # Add timestamp to message
        message['timestamp'] = datetime.now().isoformat()
        
        # Send to all connections in channel
        disconnected = []
        for connection in self.active_connections[channel]:
            try:
                await connection.send_json(message)
            except WebSocketDisconnect:
                disconnected.append(connection)
            except Exception as e:
                logger.error(f"Error broadcasting to connection: {e}")
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for connection in disconnected:
            self.disconnect(connection, channel)
        
        if len(disconnected) > 0:
            logger.info(f"Cleaned up {len(disconnected)} disconnected clients from '{channel}'")
    
    async def broadcast_to_multiple_channels(self, message: Dict[str, Any], channels: List[str]):
        """
        Broadcast a message to multiple channels simultaneously
        
        Args:
            message: Message dictionary to broadcast
            channels: List of channel names
        """
        tasks = [self.broadcast(message, channel) for channel in channels]
        await asyncio.gather(*tasks)
    
    def get_channel_count(self, channel: str) -> int:
        """Get the number of active connections for a channel"""
        return len(self.active_connections.get(channel, set()))
    
    def get_all_channels(self) -> List[str]:
        """Get list of all active channels"""
        return list(self.active_connections.keys())
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about active connections"""
        total_connections = sum(len(conns) for conns in self.active_connections.values())
        
        return {
            'total_connections': total_connections,
            'active_channels': len(self.active_connections),
            'channels': {
                channel: len(connections) 
                for channel, connections in self.active_connections.items()
            }
        }

# Global singleton instance
manager = ConnectionManager()

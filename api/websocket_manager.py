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

        # Track user IDs per connection for unique user count
        self.connection_user_ids: Dict[WebSocket, int] = {}

        # Which game each connection currently has open (viewer counts). Set by the
        # client's `watch` message when a game modal opens, cleared on `unwatch` or
        # disconnect. Counted by DISTINCT USER, so one person with several tabs is
        # one viewer.
        self.connection_watching: Dict[WebSocket, str] = {}

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

        # Remove user ID tracking
        if websocket in self.connection_user_ids:
            del self.connection_user_ids[websocket]

        # Stop counting this connection as a viewer
        self.connection_watching.pop(websocket, None)

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
        for connection in list(self.active_connections.get(channel, set())):
            try:
                # Skip connections that are already closed
                if connection.client_state.name != 'CONNECTED':
                    disconnected.append(connection)
                    continue
                await connection.send_json(message)
            except WebSocketDisconnect:
                disconnected.append(connection)
            except Exception as e:
                logger.debug(f"Broadcast to closing connection: {e}")
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
    
    def watch(self, websocket: WebSocket, gameId: Optional[str]) -> List[str]:
        """Mark this connection as watching `gameId` (None / '' = watching nothing).

        Returns the game ids whose viewer count may have changed — the one being
        left and the one being joined — so the caller can broadcast just those."""
        previous = self.connection_watching.get(websocket)
        if gameId:
            self.connection_watching[websocket] = str(gameId)
        else:
            self.connection_watching.pop(websocket, None)
        changed = []
        if previous:
            changed.append(previous)
        if gameId and str(gameId) != previous:
            changed.append(str(gameId))
        return changed

    def get_viewer_count(self, gameId: str) -> int:
        """How many DISTINCT USERS have this game open.

        Counted by user id so a person with several tabs is one viewer. A socket
        that never identified (logged out) has no user id and isn't counted."""
        target = str(gameId)
        users = {
            self.connection_user_ids[ws]
            for ws, gid in self.connection_watching.items()
            if gid == target and ws in self.connection_user_ids
        }
        return len(users)

    def identify(self, websocket: WebSocket, userId: int):
        """Associate a user ID with a WebSocket connection."""
        self.connection_user_ids[websocket] = userId

    async def send_to_user(self, userId: int, message: Dict[str, Any]) -> int:
        """Send a message to every connection that has identified as this user.
        Returns the number of sockets the message was sent to."""
        targets = [ws for ws, uid in self.connection_user_ids.items() if uid == userId]
        if not targets:
            logger.info(f"send_to_user({userId}): no identified connections (event={message.get('event')})")
            return 0
        message.setdefault('timestamp', datetime.now().isoformat())
        disconnected = []
        sent = 0
        for connection in targets:
            try:
                if connection.client_state.name != 'CONNECTED':
                    disconnected.append(connection)
                    continue
                await connection.send_json(message)
                sent += 1
            except WebSocketDisconnect:
                disconnected.append(connection)
            except Exception as e:
                logger.debug(f"send_to_user failed on one socket: {e}")
                disconnected.append(connection)
        # Best-effort cleanup — find the channel for each dead socket
        for connection in disconnected:
            meta = self.connection_metadata.get(connection, {})
            ch = meta.get('channel') or next(
                (c for c, conns in self.active_connections.items() if connection in conns),
                None,
            )
            if ch:
                self.disconnect(connection, ch)
        return sent

    def get_channel_count(self, channel: str) -> int:
        """Get the number of active connections for a channel"""
        return len(self.active_connections.get(channel, set()))
    
    def get_all_channels(self) -> List[str]:
        """Get list of all active channels"""
        return list(self.active_connections.keys())
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about active connections"""
        total_connections = sum(len(conns) for conns in self.active_connections.values())
        
        uniqueUsers = len(set(self.connection_user_ids.values()))

        return {
            'total_connections': total_connections,
            'unique_users': uniqueUsers,
            'channels': {
                channel: len(connections)
                for channel, connections in self.active_connections.items()
            }
        }

# Global singleton instance
manager = ConnectionManager()

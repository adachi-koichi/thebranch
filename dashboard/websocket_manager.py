import json
import logging
from typing import Dict, Set
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket 接続管理"""

    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        """クライアント接続"""
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)
        logger.info(f"WebSocket connected: user_id={user_id}")

    def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        """クライアント切断"""
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        logger.info(f"WebSocket disconnected: user_id={user_id}")

    async def broadcast(self, event: dict) -> None:
        """全ユーザーに ブロードキャスト"""
        payload = json.dumps(event)
        disconnected = []

        for user_id, connections in self.active_connections.items():
            for connection in list(connections):
                try:
                    await connection.send_text(payload)
                except Exception as e:
                    logger.warning(f"Failed to send message to {user_id}: {e}")
                    disconnected.append((user_id, connection))

        # 切断済み接続を削除
        for user_id, connection in disconnected:
            self.disconnect(connection, user_id)

    async def broadcast_to_user(self, user_id: str, event: dict) -> None:
        """特定ユーザーに ブロードキャスト"""
        if user_id not in self.active_connections:
            return

        payload = json.dumps(event)
        connections = self.active_connections[user_id]

        for connection in list(connections):
            try:
                await connection.send_text(payload)
            except Exception as e:
                logger.warning(f"Failed to send message to {user_id}: {e}")
                self.disconnect(connection, user_id)

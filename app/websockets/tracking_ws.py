import json
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect
from redis.asyncio import Redis

from app.core.redis import get_redis_client


class ConnectionManager:
    """Gerencia conexões WebSocket ativas por delivery_id."""

    def __init__(self) -> None:
        # delivery_id -> lista de WebSockets conectados
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, delivery_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        if delivery_id not in self._connections:
            self._connections[delivery_id] = []
        self._connections[delivery_id].append(websocket)

    def disconnect(self, delivery_id: str, websocket: WebSocket) -> None:
        if delivery_id in self._connections:
            self._connections[delivery_id].discard(websocket) if hasattr(
                self._connections[delivery_id], "discard"
            ) else None
            try:
                self._connections[delivery_id].remove(websocket)
            except ValueError:
                pass
            if not self._connections[delivery_id]:
                del self._connections[delivery_id]

    async def broadcast(self, delivery_id: str, data: dict) -> None:
        if delivery_id not in self._connections:
            return
        dead: list[WebSocket] = []
        for ws in self._connections[delivery_id]:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(delivery_id, ws)


manager = ConnectionManager()


async def tracking_websocket_endpoint(websocket: WebSocket, delivery_id: UUID) -> None:
    """
    Endpoint WebSocket para rastreamento ao vivo.
    Clientes se conectam em ws://.../ws/tracking/{delivery_id}
    e recebem atualizações em tempo real.
    """
    delivery_str = str(delivery_id)
    await manager.connect(delivery_str, websocket)

    # Envia posição atual ao conectar
    redis: Redis = await get_redis_client()
    live_data = await redis.get(f"tracking:{delivery_str}")
    if live_data:
        await websocket.send_json(json.loads(live_data))

    try:
        while True:
            # Mantém conexão aberta; atualizações chegam via broadcast
            data = await websocket.receive_text()
            # Pode receber ping/pong ou comandos do cliente no futuro
    except WebSocketDisconnect:
        manager.disconnect(delivery_str, websocket)

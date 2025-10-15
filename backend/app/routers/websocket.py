import json
import asyncio
from typing import Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import AsyncSessionLocal
from ..services.auth import AuthService
from ..middleware.tenant import TenantMiddleware
from ..redis_client import redis_client

router = APIRouter(tags=["websocket"])

# Store active connections by org_id
active_connections: Dict[int, Set[WebSocket]] = {}


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, org_id: int):
        await websocket.accept()
        if org_id not in self.active_connections:
            self.active_connections[org_id] = set()
        self.active_connections[org_id].add(websocket)

    def disconnect(self, websocket: WebSocket, org_id: int):
        if org_id in self.active_connections:
            self.active_connections[org_id].discard(websocket)
            if not self.active_connections[org_id]:
                del self.active_connections[org_id]

    async def send_to_org(self, org_id: int, message: str):
        if org_id in self.active_connections:
            disconnected = set()
            for connection in self.active_connections[org_id].copy():
                try:
                    await connection.send_text(message)
                except Exception:
                    disconnected.add(connection)
            
            # Remove disconnected connections
            for connection in disconnected:
                self.active_connections[org_id].discard(connection)


manager = ConnectionManager()


async def authenticate_websocket(websocket: WebSocket) -> tuple[int, int]:
    """Authenticate WebSocket connection and return user_id, org_id."""
    # Get token from query params or headers
    token = None
    
    # Try query params first
    if "token" in websocket.query_params:
        token = websocket.query_params["token"]
    
    # Try Authorization header
    if not token and "authorization" in websocket.headers:
        auth_header = websocket.headers["authorization"]
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        raise HTTPException(status_code=401, detail="Authentication required")

    # Verify token
    payload = AuthService.verify_token(token)
    if not payload or "user_id" not in payload or "org_id" not in payload:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        raise HTTPException(status_code=401, detail="Invalid token")

    return payload["user_id"], payload["org_id"]


@router.websocket("/ws/{org_id}")
async def websocket_endpoint(websocket: WebSocket, org_id: int):
    try:
        # Authenticate
        user_id, token_org_id = await authenticate_websocket(websocket)
        
        # Verify org access
        if token_org_id != org_id:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # Connect to manager
        await manager.connect(websocket, org_id)
        
        # Send initial connection message
        await websocket.send_text(json.dumps({
            "type": "connected",
            "org_id": org_id,
            "user_id": user_id
        }))

        # Keep connection alive and handle messages
        try:
            while True:
                # Wait for messages from client (ping/pong)
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                    message = json.loads(data)
                    
                    if message.get("type") == "ping":
                        await websocket.send_text(json.dumps({"type": "pong"}))
                        
                except asyncio.TimeoutError:
                    # Send heartbeat
                    await websocket.send_text(json.dumps({"type": "heartbeat"}))
                    
        except WebSocketDisconnect:
            pass
            
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        manager.disconnect(websocket, org_id)


async def redis_listener():
    """Listen for Redis pub/sub messages and broadcast to WebSocket clients."""
    pubsub = redis_client.pubsub()
    await pubsub.psubscribe("org:*:tasks")
    
    try:
        async for message in pubsub.listen():
            if message["type"] == "pmessage":
                channel = message["channel"]
                data = message["data"]
                
                # Extract org_id from channel name
                try:
                    org_id = int(channel.split(":")[1])
                    await manager.send_to_org(org_id, data)
                except (ValueError, IndexError):
                    continue
                    
    except Exception as e:
        print(f"Redis listener error: {e}")
    finally:
        await pubsub.unsubscribe()


# Start Redis listener when module is imported
import asyncio
asyncio.create_task(redis_listener())
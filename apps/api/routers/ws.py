"""
WebSocket endpoint for real-time capture events → frontend.
Each connected client gets a copy of events broadcast from the capture scheduler.
"""
import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from apps.api.engines.vision import scheduler

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])

_connections: list[WebSocket] = []


async def _broadcast_loop():
    """Read from scheduler's event queue and push to all connected clients."""
    while True:
        try:
            event = await scheduler.get_event()
            dead: list[WebSocket] = []
            for ws in _connections:
                try:
                    await ws.send_text(json.dumps(event))
                except Exception:
                    dead.append(ws)
            for ws in dead:
                _connections.remove(ws)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.debug("Broadcast error: %s", e)


@router.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    await websocket.accept()
    _connections.append(websocket)
    logger.info("WebSocket client connected. Total: %d", len(_connections))
    try:
        while True:
            # Keep connection alive; events pushed via broadcast_loop
            await asyncio.sleep(10)
            await websocket.send_text('{"type":"ping"}')
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in _connections:
            _connections.remove(websocket)
        logger.info("WebSocket client disconnected. Total: %d", len(_connections))

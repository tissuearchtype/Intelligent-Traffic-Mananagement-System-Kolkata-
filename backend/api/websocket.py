"""
=============================================================
  WebSocket Handler — Live Camera Stream
  File: backend/api/websocket.py
=============================================================
"""

import cv2, json, time, asyncio, numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool

router = APIRouter()
connected_clients: list[WebSocket] = []


@router.websocket("/stream")
async def stream_frames(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    detector = websocket.app.state.detector
    print(f"[WS] Client connected. Total: {len(connected_clients)}")

    try:
        while True:
            frame_bytes = await websocket.receive_bytes()
            np_arr = np.frombuffer(frame_bytes, np.uint8)
            frame  = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if frame is None:
                await websocket.send_json({"error": "Could not decode frame"})
                continue

            try:
                # Run the heavy AI prediction in a separate thread so it doesn't freeze the server
                result = await run_in_threadpool(detector.predict_frame, frame)
                await websocket.send_json(result.to_dict())
            except Exception as e:
                print(f"[WS Model Error] {e}")
                await websocket.send_json({"error": "Inference failed"})

            # Yield control back to the event loop so the connection doesn't timeout
            await asyncio.sleep(0.01)

    except WebSocketDisconnect:
        print("[WS] Client disconnected.")
    except Exception as e:
        print(f"[WS] Connection dropped: {e}")
    finally:
        if websocket in connected_clients:
            connected_clients.remove(websocket)


@router.websocket("/alerts")
async def alert_feed(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        while True:
            await asyncio.sleep(30)
            await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in connected_clients:
            connected_clients.remove(websocket)


async def broadcast_alert(alert: dict):
    dead = []
    for ws in connected_clients:
        try:
            await ws.send_json({"type": "alert", **alert})
        except Exception:
            dead.append(ws)
    for ws in dead:
        connected_clients.remove(ws)
import asyncio
import logging
import time
import uuid
import os
from datetime import datetime

import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.session_manager import session_manager

logger = logging.getLogger("realtime_v2")
router = APIRouter()

AI_SERVER_URL = os.getenv("AI_SERVER_URL", "http://localhost:8001/api/analyze-frame")
AI_SESSION_URL = AI_SERVER_URL.removesuffix("/api/analyze-frame")

class SessionContext:
    def __init__(self):
        self.session_id: str = str(uuid.uuid4())
        self.frame_queue: asyncio.Queue = asyncio.Queue(maxsize=5)
        self.result_queue: asyncio.Queue = asyncio.Queue(maxsize=5)
        
        self.created_at: datetime = datetime.now()
        self.last_access: datetime = datetime.now()
        
        self.frames_received: int = 0
        self.frames_processed: int = 0
        self.frames_dropped: int = 0
        self.avg_latency_ms: float = 0.0
        self.last_frame_time: float = time.time()

    def update_latency(self, latency_ms: float):
        total_latency = self.avg_latency_ms * self.frames_processed
        self.frames_processed += 1
        self.avg_latency_ms = (total_latency + latency_ms) / self.frames_processed

    def update_access(self):
        """Cập nhật thời gian truy cập cuối (cho cả receive và process)"""
        self.last_access = datetime.now()
        self.last_frame_time = time.time()


@router.get("/ws/realtime-v2/metrics")
async def get_active_sessions():
    metrics = await session_manager.get_all_metrics()
    return {
        "active_connections": len(metrics),
        "sessions": metrics
    }


@router.websocket("/ws/realtime-v2")
async def realtime_video_endpoint(websocket: WebSocket):
    await websocket.accept()
    ctx = SessionContext()
    await session_manager.add_session(ctx)
    logger.info(f"[{ctx.session_id}] Connected. Session registered.")

    # === TASK 1: HEALTH CHECK (inactive timeout) ===
    async def session_health_check():
        try:
            while True:
                await asyncio.sleep(30)
                if time.time() - ctx.last_frame_time > 60:
                    logger.warning(f"[{ctx.session_id}] Inactive >60s, force closing.")
                    await websocket.close(code=1000, reason="Inactive")
                    break
        except asyncio.CancelledError:
            pass

    # === TASK 2: RECEIVE FRAMES ===
    async def receive_frames():
        try:
            while True:
                data = await websocket.receive_json()
                ctx.update_access()
                ctx.frames_received += 1

                if "image" not in data:
                    continue

                # Drop oldest if queue full
                if ctx.frame_queue.full():
                    try:
                        ctx.frame_queue.get_nowait()
                        ctx.frame_queue.task_done()
                        ctx.frames_dropped += 1
                        logger.warning(f"[{ctx.session_id}] Frame queue full, dropped oldest.")
                    except asyncio.QueueEmpty:
                        pass

                await ctx.frame_queue.put(data)
        except WebSocketDisconnect:
            raise
        except Exception as e:
            logger.error(f"[{ctx.session_id}] Receive error: {e}")

    # === TASK 3: PROCESS FRAMES (call AI) ===
    async def process_frames():
        async with httpx.AsyncClient() as client:
            try:
                while True:
                    frame_data = await ctx.frame_queue.get()
                    start_time = time.time()
                    try:
                        payload = {
                            "session_id": ctx.session_id,
                            "image": frame_data.get("image"),
                            "timestamp": frame_data.get("timestamp")
                        }
                        response = await client.post(AI_SERVER_URL, json=payload, timeout=7.0)
                        response.raise_for_status()
                        result = response.json()
                        latency_ms = (time.time() - start_time) * 1000
                        ctx.update_latency(latency_ms)

                        # Result queue backpressure: drop oldest if full
                        if ctx.result_queue.full():
                            try:
                                ctx.result_queue.get_nowait()
                                ctx.result_queue.task_done()
                                logger.warning(f"[{ctx.session_id}] Result queue full, dropped oldest result.")
                            except asyncio.QueueEmpty:
                                pass
                        await ctx.result_queue.put(result)
                    except Exception as e:
                        logger.error(f"[{ctx.session_id}] AI call error: {e}")
                    finally:
                        ctx.frame_queue.task_done()
            except asyncio.CancelledError:
                pass

    # === TASK 4: SEND RESULTS ===
    async def send_results():
        try:
            while True:
                result = await ctx.result_queue.get()
                await websocket.send_json(result)
                ctx.result_queue.task_done()
        except asyncio.CancelledError:
            pass

    # Start all tasks
    tasks = [
        asyncio.create_task(session_health_check()),
        asyncio.create_task(receive_frames()),
        asyncio.create_task(process_frames()),
        asyncio.create_task(send_results())
    ]

    try:
        await tasks[1]  # wait for receiver task (it will raise on disconnect)
    except WebSocketDisconnect:
        logger.info(f"[{ctx.session_id}] Client disconnected.")
    finally:
        # Cancel all tasks
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

        # Clear queues
        for q in [ctx.frame_queue, ctx.result_queue]:
            while not q.empty():
                try:
                    q.get_nowait()
                    q.task_done()
                except asyncio.QueueEmpty:
                    break

        try:
            async with httpx.AsyncClient() as client:
                await client.delete(
                    f"{AI_SESSION_URL}/api/realtime-session/{ctx.session_id}",
                    timeout=3.0,
                )
        except Exception as e:
            logger.warning(f"[{ctx.session_id}] AI session cleanup failed: {e}")

        await session_manager.remove_session(ctx.session_id)
        logger.info(
            f"[{ctx.session_id}] Closed. Received={ctx.frames_received}, "
            f"Processed={ctx.frames_processed}, Dropped={ctx.frames_dropped}, "
            f"AvgLat={ctx.avg_latency_ms:.2f}ms"
        )

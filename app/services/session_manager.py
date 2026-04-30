import asyncio
from typing import Dict, List, Any

# Tránh circular import bằng cách import type muộn hoặc dùng type hints string
# Giả sử SessionContext nằm trong realtime_v2.py (sẽ inject vào)

class RealtimeSessionManager:
    def __init__(self):
        self.sessions: Dict[str, Any] = {}
        self._lock = asyncio.Lock()

    async def add_session(self, ctx: Any):
        async with self._lock:
            self.sessions[ctx.session_id] = ctx

    async def remove_session(self, session_id: str):
        async with self._lock:
            if session_id in self.sessions:
                del self.sessions[session_id]

    async def get_all_metrics(self) -> List[Dict[str, Any]]:
        async with self._lock:
            metrics = []
            for session_id, ctx in self.sessions.items():
                metrics.append({
                    "session_id": session_id,
                    "created_at": ctx.created_at.isoformat(),
                    "frames_received": ctx.frames_received,
                    "frames_processed": ctx.frames_processed,
                    "frames_dropped": ctx.frames_dropped,
                    "avg_latency_ms": round(ctx.avg_latency_ms, 2),
                    "queue_depth": ctx.frame_queue.qsize()
                })
            return metrics

# Singleton instance để dùng chung trên toàn app
session_manager = RealtimeSessionManager()
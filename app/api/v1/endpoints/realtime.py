import time
from typing import Any

import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import settings

router = APIRouter()

def _safe_number(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        if number != number or number in (float("inf"), float("-inf")):
            return default
        return number
    except (TypeError, ValueError):
        return default

def _normalize_people(raw_people: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_people, list):
        return []

    normalized_people: list[dict[str, Any]] = []
    for person in raw_people:
        if not isinstance(person, dict):
            continue

        bbox = person.get("bbox")
        keypoints = person.get("keypoints")

        normalized_people.append(
            {
                "bbox": bbox if isinstance(bbox, list) else None,
                "keypoints": keypoints if isinstance(keypoints, list) else [],
            }
        )

    return normalized_people

def _normalize_alerts(raw_alerts: Any, fallback_timestamp: int) -> list[dict[str, Any]]:
    if not isinstance(raw_alerts, list):
        return []

    normalized_alerts: list[dict[str, Any]] = []
    for index, alert in enumerate(raw_alerts):
        if not isinstance(alert, dict):
            continue

        event_type = str(
            alert.get("event_type")
            or alert.get("label")
            or alert.get("type")
            or "warning"
        )
        timestamp = int(_safe_number(alert.get("timestamp"), fallback_timestamp))

        normalized_alerts.append(
            {
                "id": str(alert.get("id") or f"{event_type}-{timestamp}-{index}"),
                "event_type": event_type,
                "score": _safe_number(alert.get("score") or alert.get("confidence"), 0.0),
                "timestamp": timestamp,
                "message": alert.get("message"),
            }
        )

    return normalized_alerts

def _empty_realtime_payload(latency_ms: int = 0) -> dict[str, Any]:
    return {
        "people": [],
        "alerts": [],
        "latency_ms": max(0, int(latency_ms)),
    }

def _normalize_realtime_payload(
    payload: Any,
    fallback_latency_ms: int,
    fallback_timestamp: int,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return _empty_realtime_payload(fallback_latency_ms)

    normalized_latency = max(
        fallback_latency_ms,
        int(_safe_number(payload.get("latency_ms"), fallback_latency_ms)),
    )

    return {
        "people": _normalize_people(payload.get("people")),
        "alerts": _normalize_alerts(payload.get("alerts") or payload.get("events"), fallback_timestamp),
        "latency_ms": normalized_latency,
    }


# ✅ FIX: Use environment variable for AI server URL
import os
AI_URL = os.getenv("AI_SERVER_URL", "http://localhost:8001").strip().rstrip("/")

@router.websocket("/ws/realtime")
async def realtime_ws_v2(ws: WebSocket):
    print("🔗 [WS V2] WS ROUTE HIT")
    print("🔗 [WS V2] Connection request received")
    # 🔥 CÁCH 1: KHÔNG Depends, KHÔNG Auth, KHÔNG Token
    # Bắt tay ngay lập tức để thông luồng
    await ws.accept()
    print("✅ [WS V2] WS ACCEPT")
    print("✅ [WS V2] Frontend Connected! (Auth Disabled for Debugging)")

    # Lấy URL và khử trùng
    ai_url = settings.AI_SERVER_URL.strip().rstrip("/")

    async with httpx.AsyncClient() as client:
        try:
            while True:
                try:
                    data = await ws.receive_json()
                    print("📥 [WS V2] WS RECEIVE")
                    print("📥 [WS V2] Received frame data")
                    fallback_timestamp = int(_safe_number(data.get("timestamp"), time.time() * 1000))
                    frame_base64 = data.get("image") or data.get("frame_base64")

                    if not isinstance(frame_base64, str) or not frame_base64.strip():
                        await ws.send_json(_empty_realtime_payload())
                        continue

                    started_at = time.perf_counter()
                    try:
                        res = await client.post(
                            f"{ai_url}/api/analyze-frame",
                            json={
                                "image": frame_base64,
                                "frame_id": data.get("frame_id"),
                                "timestamp": fallback_timestamp,
                            },
                            timeout=10.0,
                        )
                        res.raise_for_status()
                        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                        
                        await ws.send_json(
                            _normalize_realtime_payload(
                                res.json(),
                                fallback_latency_ms=elapsed_ms,
                                fallback_timestamp=fallback_timestamp,
                            )
                        )
                    except Exception as e:
                        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                        print(f"⚠️ [AI Call Error - V2]: {e}")
                        await ws.send_json(_empty_realtime_payload(elapsed_ms))
                except Exception as e:
                    print(f"❌ [WS V2] WS ERROR in loop: {e}")
                    break
        except WebSocketDisconnect:
            print("🔴 [WS V2] Frontend Disconnected!")
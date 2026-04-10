from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import httpx

router = APIRouter()
AI_URL = " https://controls-widespread-robinson-participate.trycloudflare.com" # URL Cloudflare hoặc Runpod

@router.websocket("/ws/realtime")
async def realtime_ws(ws: WebSocket):
    await ws.accept()
    
    # Dùng 1 client duy nhất cho toàn bộ session để tối ưu tốc độ
    async with httpx.AsyncClient() as client:
        try:
            while True:
                # Nhận frame từ FE
                data = await ws.receive_json()
                
                # Gửi sang AI soi
                try:
                    res = await client.post(
                        f"{AI_URL}/api/analyze-frame",
                        json={"image": data["image"]},
                        timeout=1.0
                    )
                    # Trả kết quả (Keypoints) về FE
                    await ws.send_json(res.json())
                except:
                    await ws.send_json({"people": []})
        except WebSocketDisconnect:
            pass
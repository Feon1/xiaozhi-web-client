import asyncio
import os
import json
import uuid
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import websockets
from dotenv import load_dotenv
import uvicorn

load_dotenv()

# --- АДРЕС ВАШЕГО MCPHub (НЕ api.xiaozhi.me!) ---
WS_URL = os.getenv("WS_URL", "wss://xiaozhi-mcphub-deploy-server.onrender.com/mcp")
TOKEN = os.getenv("DEVICE_TOKEN", "")
if not TOKEN:
    print("⚠️  DEVICE_TOKEN не задан!")

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

def get_mac_address():
    mac = uuid.getnode()
    return ':'.join(['{:02x}'.format((mac >> elements) & 0xff) for elements in range(0, 8*6, 8)][::-1])

def get_client_id():
    client_id = os.getenv("CLIENT_ID")
    if not client_id:
        new_id = str(uuid.uuid4())
        with open(".env", "a") as f:
            f.write(f"CLIENT_ID={new_id}\n")
        os.environ["CLIENT_ID"] = new_id
        return new_id
    return client_id

DEVICE_ID = get_mac_address()
CLIENT_ID = get_client_id()

@app.websocket("/")
async def websocket_proxy(websocket: WebSocket):
    await websocket.accept()
    print(f"📡 Клиент подключился: {websocket.client}")

    ws_url_with_token = f"{WS_URL}?token={TOKEN}" if TOKEN else WS_URL
    headers = {
        "Device-Id": DEVICE_ID,
        "Client-Id": CLIENT_ID,
        "Protocol-Version": "1",
    }

    print(f"🌐 Подключение к MCPHub по адресу: {ws_url_with_token}")
    print(f"📋 Заголовки: {headers}")

    try:
        async with websockets.connect(ws_url_with_token, extra_headers=headers, timeout=10) as server_ws:
            print("✅ Подключено к MCPHub")
            async def forward_to_server():
                try:
                    while True:
                        msg = await websocket.receive_text()
                        await server_ws.send(msg)
                except WebSocketDisconnect:
                    pass
                except Exception as e:
                    print(f"Ошибка клиент→сервер: {e}")

            async def forward_to_client():
                try:
                    async for msg in server_ws:
                        if isinstance(msg, str):
                            await websocket.send_text(msg)
                        else:
                            pass
                except Exception as e:
                    print(f"Ошибка сервер→клиент: {e}")

            await asyncio.gather(forward_to_server(), forward_to_client())
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"❌ Неверный статус-код: {e.status_code}")
        await websocket.close()
    except Exception as e:
        print(f"❌ Ошибка прокси: {e}")
        await websocket.close()
    finally:
        print("🔌 Клиент отключён")

@app.get("/", response_class=HTMLResponse)
async def get_index():
    try:
        with open("templates/index.html", "r", encoding="utf-8") as f:
            html = f.read()
        html = html.replace("{{ device_id }}", DEVICE_ID)
        html = html.replace("{{ ws_url }}", WS_URL)
        html = html.replace("{{ local_proxy_url }}", "")
        html = html.replace("{{ token_status }}", "Включено" if TOKEN else "Отключено")
        html = html.replace("{{ enable_checked }}", "checked" if TOKEN else "")
        html = html.replace("{{ token }}", TOKEN)
        return HTMLResponse(content=html)
    except Exception as e:
        print(f"Ошибка загрузки шаблона: {e}")
        return HTMLResponse(content=f"Ошибка сервера: {e}", status_code=500)

@app.post("/save_config")
async def save_config(request: Request):
    return {"success": True, "message": "Заглушка"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

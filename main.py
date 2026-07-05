import asyncio
import os
import json
import uuid
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import websockets
from dotenv import load_dotenv
import uvicorn

load_dotenv()

# ----- Конфигурация -----
WS_URL = os.getenv("WS_URL", "wss://api.xiaozhi.me/ws")
TOKEN = os.getenv("DEVICE_TOKEN", "123")
ENABLE_TOKEN = os.getenv("ENABLE_TOKEN", "true").lower() == "true"

app = FastAPI()

# Статика и шаблоны
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Генерация ID устройства
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

# ----- WebSocket прокси -----
@app.websocket("/")
async def websocket_proxy(websocket: WebSocket):
    await websocket.accept()
    print(f"📡 Клиент подключился: {websocket.client}")
    
    headers = {
        "Device-Id": DEVICE_ID,
        "Client-Id": CLIENT_ID,
        "Protocol-Version": "1",
    }
    if ENABLE_TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    
    try:
        async with websockets.connect(WS_URL, extra_headers=headers) as server_ws:
            print("✅ Подключено к серверу Xiaozhi")
            
            async def forward_to_server():
                try:
                    while True:
                        msg = await websocket.receive_text()
                        await server_ws.send(msg)
                except WebSocketDisconnect:
                    pass
                except Exception as e:
                    print(f"Ошибка пересылки клиент→сервер: {e}")
            
            async def forward_to_client():
                try:
                    async for msg in server_ws:
                        if isinstance(msg, str):
                            await websocket.send_text(msg)
                        else:
                            # бинарные данные игнорируем (аудио)
                            pass
                except Exception as e:
                    print(f"Ошибка пересылки сервер→клиент: {e}")
            
            await asyncio.gather(
                forward_to_server(),
                forward_to_client()
            )
    except Exception as e:
        print(f"❌ Ошибка прокси: {e}")
        await websocket.close()
    finally:
        print("🔌 Клиент отключён")

# ----- Главная страница -----
@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "device_id": DEVICE_ID,
        "ws_url": WS_URL,
        "local_proxy_url": "",  # теперь не используется
        "enable_token": ENABLE_TOKEN,
        "token": TOKEN
    })

# ----- Сохранение настроек (для совместимости) -----
@app.post("/save_config")
async def save_config(request: Request):
    data = await request.json()
    # Можно сохранять в .env, но для простоты просто возвращаем успех
    return {"success": True, "message": "Настройки сохранены (только для интерфейса)"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

import asyncio
import os
import uuid
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import websockets
from dotenv import load_dotenv
import uvicorn

load_dotenv()

# --- КОНФИГУРАЦИЯ ---
WS_URL = os.getenv("WS_URL", "wss://api.xiaozhi.me/v1/ws")  # пробуем /v1/ws
TOKEN = os.getenv("DEVICE_TOKEN", "")
if not TOKEN:
    print("⚠️  DEVICE_TOKEN не задан! Чат не будет работать.")

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

def get_mac_address():
    mac = uuid.getnode()
    return ':'.join(['{:02x}'.format((mac >> elements) & 0xff) for elements in range(0, 8*6, 8)][::-1])

DEVICE_ID = get_mac_address()
CLIENT_ID = str(uuid.uuid4())  # генерируем случайный Client-Id

@app.websocket("/")
async def websocket_proxy(websocket: WebSocket):
    await websocket.accept()
    print(f"📡 Клиент подключился: {websocket.client}")

    headers = {
        "Device-Id": DEVICE_ID,
        "Client-Id": CLIENT_ID,
        "Protocol-Version": "1",
        "Authorization": f"Bearer {TOKEN}"
    }

    print(f"🌐 Подключение к Xiaozhi: {WS_URL}")
    print(f"📋 Заголовки: {headers}")

    try:
        async with websockets.connect(WS_URL, extra_headers=headers, timeout=10) as server_ws:
            print("✅ Подключено к Xiaozhi")
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
                            # бинарные данные (аудио) игнорируем для простоты
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
    with open("templates/index.html", "r", encoding="utf-8") as f:
        html = f.read()
    html = html.replace("{{ device_id }}", DEVICE_ID)
    return HTMLResponse(content=html)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

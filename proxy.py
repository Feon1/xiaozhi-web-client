import asyncio
import websockets
import os
import json
from dotenv import load_dotenv
import uuid
from urllib.parse import urlparse

load_dotenv()

# ----- Конфигурация -----
WS_URL = os.getenv("WS_URL")
if not WS_URL:
    print("⚠️  WS_URL не задан, использую значение по умолчанию")
    WS_URL = "ws://localhost:9005"

TOKEN = os.getenv("DEVICE_TOKEN")
if not TOKEN:
    print("⚠️  DEVICE_TOKEN не задан, использую '123'")
    TOKEN = "123"

LOCAL_PROXY_URL = os.getenv("LOCAL_PROXY_URL", "ws://localhost:5002")
try:
    parsed = urlparse(LOCAL_PROXY_URL)
    PROXY_HOST = '0.0.0.0'
    PROXY_PORT = parsed.port or 5002
except Exception:
    PROXY_HOST = '0.0.0.0'
    PROXY_PORT = 5002

# ----- Вспомогательные функции -----
def get_mac_address():
    mac = uuid.getnode()
    return ':'.join(['{:02x}'.format((mac >> elements) & 0xff) for elements in range(0, 8*6, 8)][::-1])

def get_client_id():
    client_id = os.getenv("CLIENT_ID")
    if not client_id:
        new_id = str(uuid.uuid4())
        with open(".env", "a") as env_file:
            env_file.write(f"CLIENT_ID={new_id}\n")
        os.environ["CLIENT_ID"] = new_id
        return new_id
    return client_id

# ----- Основной прокси-класс (только текст) -----
class WebSocketProxy:
    def __init__(self):
        self.device_id = get_mac_address()
        self.client_id = get_client_id()
        self.enable_token = os.getenv("ENABLE_TOKEN", "true").lower() == "true"
        self.token = os.getenv("DEVICE_TOKEN", "123")
        
        self.headers = {
            "Device-Id": self.device_id,
            "Client-Id": self.client_id,
            "Protocol-Version": "1",
        }
        if self.enable_token:
            self.headers["Authorization"] = f"Bearer {self.token}"

    async def proxy_handler(self, websocket):
        """Обработка подключения от браузера"""
        try:
            print(f"📡 Новый клиент: {websocket.remote_address}")
            async with websockets.connect(WS_URL, extra_headers=self.headers) as server_ws:
                print("✅ Подключено к серверу Xiaozhi")
                
                # Запускаем два направления
                client_to_server = asyncio.create_task(self.forward_text(websocket, server_ws))
                server_to_client = asyncio.create_task(self.forward_text(server_ws, websocket))
                
                done, pending = await asyncio.wait(
                    [client_to_server, server_to_client],
                    return_when=asyncio.FIRST_COMPLETED
                )
                for task in pending:
                    task.cancel()
        except Exception as e:
            print(f"❌ Ошибка прокси: {e}")
        finally:
            print("🔌 Клиент отключён")

    async def forward_text(self, source, destination):
        """Пересылка только текстовых (JSON) сообщений"""
        try:
            async for message in source:
                if isinstance(message, str):
                    # Текстовое сообщение – передаём как есть
                    await destination.send(message)
                else:
                    # Бинарные данные (аудио) – игнорируем
                    print("⏩ Пропущен бинарный пакет (аудио)")
        except Exception as e:
            print(f"⚠️ Ошибка пересылки: {e}")

    async def main(self):
        """Запуск прокси-сервера"""
        print(f"🚀 Прокси-сервер запущен на {PROXY_HOST}:{PROXY_PORT}")
        print(f"📱 Device ID: {self.device_id}")
        print(f"🔑 Token: {TOKEN}")
        print(f"🌐 Целевой WS: {WS_URL}")
        
        async with websockets.serve(self.proxy_handler, PROXY_HOST, PROXY_PORT):
            await asyncio.Future()  # Бесконечное ожидание

if __name__ == "__main__":
    proxy = WebSocketProxy()
    asyncio.run(proxy.main())

import asyncio
import json
import logging
import time
from uuid import uuid4
from datetime import datetime
from typing import Optional, Dict, Any

import websockets
from django.conf import settings

from .models import MaxSession, MessageLog, DailyStatistics

logger = logging.getLogger(__name__)


class MaxClientService:
    def __init__(self, session: MaxSession):
        self.session = session
        self.auth_token = session.auth_token
        self.user_agent_data = session.user_agent_data
        self.device_id = session.device_id
        self.websocket = None
        self.seq_counter = 100
        self.connection_active = False
    
    def _generate_user_agent(self, device_id: Optional[str] = None) -> dict:
        if device_id is None:
            device_id = str(uuid4())
        
        return {
            "ver": 13,
            "cmd": 0,
            "seq": 0,
            "opcode": 6,
            "payload": {
                "userAgent": {
                    "deviceType": "WEB",
                    "locale": "ru",
                    "deviceLocale": "en",
                    "osVersion": "Linux",
                    "deviceName": "Chrome",
                    "headerUserAgent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
                    "appVersion": "26.1.4",
                    "screen": "1080x1920 1.0x",
                    "timezone": "Europe/Moscow"
                },
                "deviceId": device_id
            }
        }
    
    def _get_next_seq(self) -> int:
        self.seq_counter += 1
        return self.seq_counter
    
    def _generate_cid(self) -> int:
        return int(time.time() * 1000)
    
    async def _connect(self):
        """
        Асинхронное подключение к WebSocket API Max.
        Переписанная async версия из main.py.
        """
        if not self.user_agent_data:
            self.user_agent_data = self._generate_user_agent(self.device_id)
            self.session.user_agent_data = self.user_agent_data
            self.session.save()
        
        try:
            logger.info(f"[{self.device_id}] Connecting to WebSocket...")
            
            headers = {
                "User-Agent": self.user_agent_data['payload']['userAgent']['headerUserAgent'],
                "Origin": "https://web.max.ru",
                "Host": "ws-api.oneme.ru",
                "Pragma": "no-cache",
                "Cache-Control": "no-cache",
                "Sec-WebSocket-Extensions": "permessage-deflate; client_max_window_bits",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"
            }
            
            self.websocket = await websockets.connect(
                "wss://ws-api.oneme.ru/websocket",
                extra_headers=headers
            )
            self.connection_active = True
            
            logger.info(f"[{self.device_id}] Sending user agent...")
            await self.websocket.send(json.dumps(self.user_agent_data))
            
            response = await self.websocket.recv()
            logger.info(f"[{self.device_id}] User agent response: {response}")
            
        except Exception as e:
            logger.error(f"[{self.device_id}] Connection error: {e}")
            self.connection_active = False
            raise
    
    async def _disconnect(self):
        """Закрытие WebSocket соединения"""
        if self.websocket:
            try:
                logger.info(f"[{self.device_id}] Closing WebSocket connection...")
                await self.websocket.close()
            except Exception as e:
                if "no close frame received or sent" not in str(e):
                    logger.warning(f"[{self.device_id}] Warning during disconnect: {e}")
            finally:
                self.websocket = None
                self.connection_active = False
    
    async def start_qr_auth(self) -> Dict[str, Any]:
        """
        Инициализация входа по QR коду.
        Возвращает qrLink, trackId и expiresAt.
        """
        await self._connect()
        
        # Opcode 288: Запрос QR кода
        qr_request_payload = {
            "ver": 11,
            "cmd": 0,
            "seq": self._get_next_seq(),
            "opcode": 288,
            "payload": {}
        }
        
        logger.info(f"[{self.device_id}] Requesting QR code...")
        await self.websocket.send(json.dumps(qr_request_payload))
        
        response = await self.websocket.recv()
        response_data = json.loads(response)
        logger.info(f"[{self.device_id}] QR response: {response}")
        
        if response_data.get('payload', {}).get('error'):
             raise ValueError(f"QR Error: {response_data['payload']['error']}")
             
        payload = response_data['payload']
        # Пример ответа: {"pollingInterval": 5000, "qrLink": "...", "trackId": "...", ...}
        
        await self._disconnect()
        return payload

    async def check_qr_auth_status(self, track_id: str) -> Dict[str, Any]:
        """
        Проверка статуса авторизации по QR.
        Если авторизация успешна (loginAvailable: true), завершает вход (Opcode 291).
        """
        await self._connect()
        
        # Opcode 289: Проверка статуса
        check_payload = {
            "ver": 11,
            "cmd": 0,
            "seq": self._get_next_seq(),
            "opcode": 289,
            "payload": {
                "trackId": track_id
            }
        }
        
        logger.info(f"[{self.device_id}] Checking QR status for {track_id}...")
        await self.websocket.send(json.dumps(check_payload))
        
        response = await self.websocket.recv()
        response_data = json.loads(response)
        logger.info(f"[{self.device_id}] Status response: {response}")
        
        status_payload = response_data.get('payload', {}).get('status', {})
        
        if status_payload.get('loginAvailable'):
            # Opcode 291: Завершение входа (Login)
            logger.info(f"[{self.device_id}] Login available! Finalizing auth...")
            
            login_payload = {
                "ver": 11,
                "cmd": 0,
                "seq": self._get_next_seq(),
                "opcode": 291,
                "payload": {
                    "trackId": track_id
                }
            }
            
            await self.websocket.send(json.dumps(login_payload))
            
            login_response = await self.websocket.recv()
            login_data = json.loads(login_response)
            logger.info(f"[{self.device_id}] Login response: {login_data}")
            
            # Извлекаем токен
            # {"payload":{"tokenAttrs":{"LOGIN":{"token":"..."}}}}
            try:
                token = login_data['payload']['tokenAttrs']['LOGIN']['token']
                self.auth_token = token
                self.session.auth_token = token
                self.session.save()
                
                await self._disconnect()
                return {"status": "success", "token": token}
                
            except KeyError:
                await self._disconnect()
                return {"status": "error", "message": "Token not found in login response", "details": login_data}
        
        # Если еще не залогинились
        await self._disconnect()
        return {"status": "waiting", "details": status_payload}
    
    async def establish_online_session(self):
        """Установка онлайн сессии (sync chats)"""
        if not self.auth_token:
            raise ValueError("No auth token provided. Please authenticate first.")
        
        if not self.connection_active:
            await self._connect()
        
        sync_payload = {
            "ver": 11,
            "cmd": 0,
            "seq": self._get_next_seq(),
            "opcode": 19,
            "payload": {
                "interactive": True,
                "token": self.auth_token,
                "chatsCount": 40,
                "chatsSync": 0,
                "contactsSync": 0,
                "presenceSync": 0,
                "draftsSync": 0
            }
        }
        
        logger.info(f"[{self.device_id}] Establishing online session...")
        await self.websocket.send(json.dumps(sync_payload))
        
        response = await self.websocket.recv()
        logger.info(f"[{self.device_id}] Online session established")
        
        return response
    
    async def send_message(self, chat_id: str, message_text: str, chat_config=None, retries: int = 2) -> Dict[str, Any]:
        """
        Отправка сообщения в чат с логированием в БД.
        
        Args:
            chat_id: ID чата
            message_text: Текст сообщения
            chat_config: Объект ChatConfig (опционально, для логирования)
            retries: Количество попыток при ошибке
            
        Returns:
            dict: Ответ от сервера
        """
        for attempt in range(retries):
            try:
                if not self.connection_active:
                    await self.establish_online_session()
                
                message_payload = {
                    "cmd": 0,
                    "opcode": 64,
                    "payload": {
                        "chatId": int(chat_id),
                        "message": {
                            "attaches": [],
                            "cid": self._generate_cid(),
                            "elements": [],
                            "text": message_text
                        },
                        "notify": True,
                        "token": self.auth_token
                    },
                    "seq": self._get_next_seq(),
                    "ver": 11
                }
                
                logger.info(f"[{self.device_id}] Sending message to chat {chat_id}")
                await self.websocket.send(json.dumps(message_payload))
                
                response = await self.websocket.recv()
                response_data = json.loads(response)
                
                logger.info(f"[{self.device_id}] Message response: {response}")
                
                if response_data.get('payload', {}).get('error'):
                    error_msg = response_data['payload']['error']
                    
                    # Логирование ошибки в БД
                    if chat_config:
                        MessageLog.objects.create(
                            session=self.session,
                            chat_config=chat_config,
                            message_text=message_text,
                            status='failed',
                            error_message=error_msg,
                            response_data=response_data
                        )
                    
                    raise ValueError(f"Server error: {error_msg}")
                
                # Логирование успеха в БД
                if chat_config:
                    MessageLog.objects.create(
                        session=self.session,
                        chat_config=chat_config,
                        message_text=message_text,
                        status='success',
                        response_data=response_data
                    )
                
                return response_data
                
            except Exception as e:
                logger.error(f"[{self.device_id}] Error in send_message (attempt {attempt + 1}): {e}")
                self.connection_active = False
                
                if attempt == retries - 1:
                    # Последняя попытка - логируем ошибку
                    if chat_config:
                        MessageLog.objects.create(
                            session=self.session,
                            chat_config=chat_config,
                            message_text=message_text,
                            status='failed',
                            error_message=str(e)
                        )
                    raise e
                
                await asyncio.sleep(1)  # Ждем перед повтором
    
    async def close(self):
        """Закрытие соединения"""
        await self._disconnect()




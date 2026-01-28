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
        self.phone_number = session.phone_number
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
                    "osVersion": "Windows 10",
                    "deviceName": "Chrome Browser",
                    "headerUserAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
                    "deviceLocale": "ru",
                    "appVersion": "27.5.10",
                    "screen": "1920x1080 1.0x",
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
            logger.info(f"[{self.phone_number}] Connecting to WebSocket...")
            
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
            
            logger.info(f"[{self.phone_number}] Sending user agent...")
            await self.websocket.send(json.dumps(self.user_agent_data))
            
            response = await self.websocket.recv()
            logger.info(f"[{self.phone_number}] User agent response: {response}")
            
        except Exception as e:
            logger.error(f"[{self.phone_number}] Connection error: {e}")
            self.connection_active = False
            raise
    
    async def _disconnect(self):
        """Закрытие WebSocket соединения"""
        if self.websocket:
            try:
                logger.info(f"[{self.phone_number}] Closing WebSocket connection...")
                await self.websocket.close()
            except Exception as e:
                if "no close frame received or sent" not in str(e):
                    logger.warning(f"[{self.phone_number}] Warning during disconnect: {e}")
            finally:
                self.websocket = None
                self.connection_active = False
    
    async def authenticate(self, phone_number: str) -> str:
        """
        Аутентификация пользователя по номеру телефона.
        Возвращает auth_token и сохраняет в БД.
        
        Args:
            phone_number: Номер телефона в формате +7XXXXXXXXXX
            
        Returns:
            str: Auth token
        """
        self.phone_number = phone_number
        await self._connect()
        
        auth_payload = {
            "ver": 11,
            "cmd": 0,
            "seq": 7,
            "opcode": 17,
            "payload": {
                "phone": self.phone_number,
                "type": "START_AUTH",
                "language": "ru"
            }
        }
        
        logger.info(f"[{self.phone_number}] Sending auth request...")
        await self.websocket.send(json.dumps(auth_payload))
        
        code_resp = json.loads(await self.websocket.recv())
        logger.info(f"[{self.phone_number}] Auth response: {code_resp}")
        
        if code_resp.get('payload', {}).get('error'):
            error_msg = code_resp['payload']['error'] + ": " + code_resp['payload']['localizedMessage']
            await self._disconnect()
            raise ValueError(error_msg)
        
        token = code_resp['payload']['token']
        logger.info(f"[{self.phone_number}] Auth token received. Waiting for verification code...")
        
        # В Django это должно быть через веб-интерфейс или API
        # Здесь возвращаем token для последующей верификации
        return token
    
    async def verify_code(self, token: str, code: str) -> str:
        """
        Верификация кода из SMS.
        
        Args:
            token: Токен из authenticate()
            code: Код из SMS
            
        Returns:
            str: Auth token для последующих запросов
        """
        verify_payload = {
            "ver": 11,
            "cmd": 0,
            "seq": 9,
            "opcode": 18,
            "payload": {
                "token": token,
                "verifyCode": code,
                "authTokenType": "CHECK_CODE"
            }
        }
        
        logger.info(f"[{self.phone_number}] Sending verification...")
        await self.websocket.send(json.dumps(verify_payload))
        
        token_resp = json.loads(await self.websocket.recv())
        logger.info(f"[{self.phone_number}] Token response: {token_resp}")
        
        self.auth_token = token_resp['payload']['tokenAttrs']['LOGIN']['token']
        
        # Сохраняем в базу данных
        self.session.auth_token = self.auth_token
        self.session.save()
        
        await self._disconnect()
        return self.auth_token
    
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
        
        logger.info(f"[{self.phone_number}] Establishing online session...")
        await self.websocket.send(json.dumps(sync_payload))
        
        response = await self.websocket.recv()
        logger.info(f"[{self.phone_number}] Online session established")
        
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
                
                logger.info(f"[{self.phone_number}] Sending message to chat {chat_id}")
                await self.websocket.send(json.dumps(message_payload))
                
                response = await self.websocket.recv()
                response_data = json.loads(response)
                
                logger.info(f"[{self.phone_number}] Message response: {response}")
                
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
                logger.error(f"[{self.phone_number}] Error in send_message (attempt {attempt + 1}): {e}")
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


# Вспомогательные функции для синхронного использования в Django views
def run_async(coro):
    """
    Запуск асинхронной функции в синхронном контексте Django.
    Используется в views, где async/await не поддерживается.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

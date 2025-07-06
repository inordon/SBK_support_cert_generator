"""
Middleware для Telegram бота
"""
import logging
import time
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User


class LoggingMiddleware(BaseMiddleware):
    """Middleware для логирования действий пользователей"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        user: User = data.get('event_from_user')

        if user:
            start_time = time.time()

            # Логирование входящего события
            if hasattr(event, 'text'):
                self.logger.info(f"User {user.id} (@{user.username}): {event.text}")
            elif hasattr(event, 'data'):
                self.logger.info(f"User {user.id} (@{user.username}) callback: {event.data}")

            try:
                result = await handler(event, data)

                # Логирование времени обработки
                processing_time = time.time() - start_time
                self.logger.debug(f"Request processed in {processing_time:.3f}s")

                return result

            except Exception as e:
                self.logger.error(f"Error processing request from {user.id}: {e}")
                raise

        return await handler(event, data)


class AuthMiddleware(BaseMiddleware):
    """Middleware для проверки авторизации"""

    def __init__(self, allowed_users: set, verify_users: set):
        self.allowed_users = allowed_users
        self.verify_users = verify_users
        self.logger = logging.getLogger(__name__)

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        user: User = data.get('event_from_user')

        if user:
            # Проверка доступа к боту
            if user.id not in self.allowed_users and user.id not in self.verify_users:
                self.logger.warning(f"Unauthorized access attempt from {user.id} (@{user.username})")

                if hasattr(event, 'answer'):
                    await event.answer("❌ У вас нет доступа к этому боту.")
                elif hasattr(event, 'message') and hasattr(event.message, 'answer'):
                    await event.message.answer("❌ У вас нет доступа к этому боту.")

                return

            # Добавление информации о правах в data
            data['user_permissions'] = {
                'can_generate': user.id in self.allowed_users,
                'can_verify': user.id in self.allowed_users or user.id in self.verify_users
            }

        return await handler(event, data)


class RateLimitMiddleware(BaseMiddleware):
    """Middleware для ограничения частоты запросов"""

    def __init__(self, rate_limit: int = 10):
        self.rate_limit = rate_limit  # запросов в минуту
        self.requests = {}  # user_id -> [timestamps]
        self.logger = logging.getLogger(__name__)

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        user: User = data.get('event_from_user')

        if user:
            now = time.time()
            user_requests = self.requests.get(user.id, [])

            # Удаление старых запросов (старше 1 минуты)
            user_requests = [req_time for req_time in user_requests if now - req_time < 60]

            # Проверка лимита
            if len(user_requests) >= self.rate_limit:
                self.logger.warning(f"Rate limit exceeded for user {user.id}")

                if hasattr(event, 'answer'):
                    await event.answer("⏳ Слишком много запросов. Попробуйте позже.")
                elif hasattr(event, 'message') and hasattr(event.message, 'answer'):
                    await event.message.answer("⏳ Слишком много запросов. Попробуйте позже.")

                return

            # Добавление текущего запроса
            user_requests.append(now)
            self.requests[user.id] = user_requests

        return await handler(event, data)
"""
Middleware для проверки прав доступа пользователей - исправленная версия.
"""

import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from config.settings import get_settings

logger = logging.getLogger(__name__)


class AccessMiddleware(BaseMiddleware):
    """Middleware для проверки прав доступа к боту."""

    def __init__(self):
        """Инициализация middleware."""
        self.settings = get_settings()
        super().__init__()

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        """
        Основной метод middleware для проверки доступа.

        Args:
            handler: Обработчик события
            event: Событие Telegram
            data: Данные события

        Returns:
            Any: Результат выполнения обработчика или None при отказе в доступе
        """
        user_id = None
        chat_type = None

        # Получаем user_id и тип чата из разных типов событий
        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
            chat_type = event.chat.type if event.chat else None
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None
            chat_type = event.message.chat.type if event.message and event.message.chat else None

        # Если не удалось получить user_id, разрешаем доступ
        # (возможно, это служебное сообщение)
        if user_id is None:
            return await handler(event, data)

        # Проверяем тип чата - в группах бот не отвечает на команды
        if chat_type in ['group', 'supergroup']:
            # В группах бот молчит, только слушает для уведомлений
            logger.debug(f"Сообщение в группе {chat_type} от пользователя {user_id} - игнорируем")
            return None

        # Только в личных сообщениях проверяем права доступа
        is_allowed = self.settings.is_allowed_user(user_id)
        is_admin = self.settings.is_admin(user_id)
        is_verify = self.settings.is_verify_user(user_id)

        # Детальная отладка
        admin_users = self.settings.admin_users_set
        verify_users = self.settings.verify_users_set
        all_users = self.settings.all_allowed_users

        logger.info(f"Пользователь {user_id}: allowed={is_allowed}, admin={is_admin}, verify={is_verify}")
        logger.info(f"Админы: {admin_users}")
        logger.info(f"Проверяющие: {verify_users}")
        logger.info(f"Все разрешенные: {all_users}")

        if not is_allowed:
            logger.warning(f"ОТКАЗ В ДОСТУПЕ для пользователя {user_id}")
            logger.warning(f"Пользователь НЕ найден в списках: админы={admin_users}, проверяющие={verify_users}")

            # Отправляем сообщение о запрете доступа только в личных сообщениях
            if isinstance(event, Message) and chat_type == 'private':
                await event.answer(
                    "❌ У вас нет доступа к этому боту.\n\n"
                    "Обратитесь к администратору для получения прав доступа."
                )
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    "❌ У вас нет доступа к этому боту.",
                    show_alert=True
                )

            return None  # Не выполняем обработчик

        # Добавляем информацию о правах пользователя в данные
        data['user_permissions'] = {
            'is_admin': is_admin,
            'can_verify': is_verify,
            'user_id': user_id,
            'chat_type': chat_type
        }

        logger.debug(f"Пользователь {user_id} получил доступ в {chat_type}. Права: {data['user_permissions']}")

        # Выполняем основной обработчик
        return await handler(event, data)


class AdminRequiredMiddleware(BaseMiddleware):
    """Middleware для проверки прав администратора."""

    def __init__(self):
        """Инициализация middleware."""
        self.settings = get_settings()
        super().__init__()

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        """
        Проверка прав администратора.

        Args:
            handler: Обработчик события
            event: Событие Telegram
            data: Данные события

        Returns:
            Any: Результат выполнения обработчика или None при отказе в доступе
        """
        user_id = None
        chat_type = None

        # Получаем user_id и тип чата из разных типов событий
        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
            chat_type = event.chat.type if event.chat else None
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None
            chat_type = event.message.chat.type if event.message and event.message.chat else None

        if user_id is None:
            return None

        # В группах не обрабатываем админские команды
        if chat_type in ['group', 'supergroup']:
            return None

        # Проверяем права администратора
        if not self.settings.is_admin(user_id):
            logger.warning(f"Пользователь {user_id} попытался выполнить действие администратора")

            # Отправляем сообщение об отсутствии прав только в личных сообщениях
            if isinstance(event, Message) and chat_type == 'private':
                await event.answer(
                    "❌ Это действие доступно только администраторам.\n\n"
                    "У вас есть права только на проверку сертификатов."
                )
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    "❌ Действие доступно только администраторам.",
                    show_alert=True
                )

            return None

        # Выполняем основной обработчик
        return await handler(event, data)


class VerifyRequiredMiddleware(BaseMiddleware):
    """Middleware для проверки прав на проверку сертификатов."""

    def __init__(self):
        """Инициализация middleware."""
        self.settings = get_settings()
        super().__init__()

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        """
        Проверка прав на проверку сертификатов.

        Args:
            handler: Обработчик события
            event: Событие Telegram
            data: Данные события

        Returns:
            Any: Результат выполнения обработчика или None при отказе в доступе
        """
        user_id = None
        chat_type = None

        # Получаем user_id и тип чата из разных типов событий
        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
            chat_type = event.chat.type if event.chat else None
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None
            chat_type = event.message.chat.type if event.message and event.message.chat else None

        if user_id is None:
            return None

        # В группах не обрабатываем команды проверки
        if chat_type in ['group', 'supergroup']:
            return None

        # Проверяем права на проверку (администраторы тоже могут проверять)
        if not self.settings.is_verify_user(user_id):
            logger.warning(f"Пользователь {user_id} попытался проверить сертификат без прав")

            # Отправляем сообщение об отсутствии прав только в личных сообщениях
            if isinstance(event, Message) and chat_type == 'private':
                await event.answer(
                    "❌ У вас нет прав на проверку сертификатов.\n\n"
                    "Обратитесь к администратору для получения необходимых прав."
                )
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    "❌ Нет прав на проверку сертификатов.",
                    show_alert=True
                )

            return None

        # Выполняем основной обработчик
        return await handler(event, data)


def setup_middlewares(dp):
    """
    Настройка middleware для диспетчера.

    Args:
        dp: Диспетчер aiogram
    """
    # Общий middleware для проверки доступа ко всем сообщениям
    dp.message.middleware(AccessMiddleware())
    dp.callback_query.middleware(AccessMiddleware())

    logger.info("Middleware настроены успешно")


def admin_required():
    """
    Декоратор для методов, требующих права администратора.

    Returns:
        AdminRequiredMiddleware: Middleware для проверки прав администратора
    """
    return AdminRequiredMiddleware()


def verify_required():
    """
    Декоратор для методов, требующих права проверки.

    Returns:
        VerifyRequiredMiddleware: Middleware для проверки прав
    """
    return VerifyRequiredMiddleware()
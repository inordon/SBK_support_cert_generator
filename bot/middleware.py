"""
Middleware для проверки прав доступа пользователей - исправленная версия с отладкой.
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
        user_info = ""

        # Получаем user_id и тип чата из разных типов событий
        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
            chat_type = event.chat.type if event.chat else None
            if event.from_user:
                user_info = f"@{event.from_user.username or 'no_username'} ({event.from_user.full_name or 'no_name'})"
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None
            chat_type = event.message.chat.type if event.message and event.message.chat else None
            if event.from_user:
                user_info = f"@{event.from_user.username or 'no_username'} ({event.from_user.full_name or 'no_name'})"

        # Если не удалось получить user_id, разрешаем доступ
        # (возможно, это служебное сообщение)
        if user_id is None:
            logger.debug("Пропускаем событие без user_id")
            return await handler(event, data)

        is_group = chat_type in ['group', 'supergroup']

        # В группах обрабатываем только команды (начинаются с /) и callback-запросы
        if is_group:
            if isinstance(event, Message):
                if not (event.text and event.text.startswith('/')):
                    logger.debug(f"Не-командное сообщение в группе от {user_id} - игнорируем")
                    return None
            # CallbackQuery в группах пропускаем (для inline-кнопок)

        # Проверяем права доступа
        is_admin = self.settings.is_admin(user_id)
        is_verify = self.settings.is_verify_user(user_id)
        is_allowed = self.settings.is_allowed_user(user_id)

        logger.debug(f"🔍 Проверка доступа: user={user_id}, admin={is_admin}, verify={is_verify}, allowed={is_allowed}, group={is_group}")

        # Если пользователь не найден в списках
        if not is_allowed:
            logger.warning(f"❌ Отказ в доступе для {user_id} {user_info}")

            # В группах молча игнорируем неавторизованных пользователей
            if is_group:
                return None

            # Отправляем сообщение о запрете доступа только в личных сообщениях
            if isinstance(event, Message) and chat_type == 'private':
                debug_info = (
                    f"❌ У вас нет доступа к этому боту.\n\n"
                    f"🆔 Ваш Telegram ID: `{user_id}`\n"
                    f"👤 Информация: {user_info}\n\n"
                    f"📝 Обратитесь к администратору для получения прав доступа.\n"
                    f"Администратор должен добавить ваш ID в переменную VERIFY_USERS или ADMIN_USERS в файле .env"
                )
                await event.answer(debug_info, parse_mode="Markdown")
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    f"❌ У вас нет доступа к этому боту. ID: {user_id}",
                    show_alert=True
                )

            return None  # Не выполняем обработчик

        # Добавляем информацию о правах пользователя в данные
        data['user_permissions'] = {
            'is_admin': is_admin,
            'can_verify': is_verify,
            'user_id': user_id,
            'chat_type': chat_type,
            'is_group': is_group
        }

        logger.debug(f"✅ Доступ разрешен: {user_id} {user_info} в {chat_type}")

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
        is_admin = self.settings.is_admin(user_id)

        logger.debug(f"🔐 Проверка админских прав: user={user_id}, is_admin={is_admin}")

        if not is_admin:
            logger.warning(f"❌ Пользователь {user_id} попытался выполнить действие администратора")

            # Отправляем сообщение об отсутствии прав только в личных сообщениях
            if isinstance(event, Message) and chat_type == 'private':
                await event.answer(
                    f"❌ Это действие доступно только администраторам.\n\n"
                    f"🆔 Ваш ID: `{user_id}`\n"
                    f"У вас есть права только на проверку сертификатов.\n\n"
                    f"Для получения прав администратора обратитесь к владельцу бота.",
                    parse_mode="Markdown"
                )
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    f"❌ Действие доступно только администраторам. ID: {user_id}",
                    show_alert=True
                )

            return None

        logger.debug(f"✅ Админские права подтверждены: user={user_id}")

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

        # Проверяем права на проверку (администраторы тоже могут проверять)
        can_verify = self.settings.is_verify_user(user_id)

        logger.debug(f"🔍 Проверка прав верификации: user={user_id}, can_verify={can_verify}")

        if not can_verify:
            logger.warning(f"❌ Пользователь {user_id} попытался проверить сертификат без прав")

            is_group = chat_type in ['group', 'supergroup']
            if is_group:
                return None

            # Отправляем сообщение об отсутствии прав только в личных сообщениях
            if isinstance(event, Message) and chat_type == 'private':
                await event.answer(
                    f"❌ У вас нет прав на проверку сертификатов.\n\n"
                    f"🆔 Ваш ID: `{user_id}`\n"
                    f"Обратитесь к администратору для получения необходимых прав.",
                    parse_mode="Markdown"
                )
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    f"❌ Нет прав на проверку сертификатов. ID: {user_id}",
                    show_alert=True
                )

            return None

        logger.debug(f"✅ Права верификации подтверждены: user={user_id}")

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

    logger.info("✅ Middleware настроены успешно")

    # Выводим информацию о настройках доступа
    settings = get_settings()
    logger.info(f"📊 Настройки доступа:")
    logger.info(f"   Администраторы ({len(settings.admin_users_set)}): {settings.admin_users_set}")
    logger.info(f"   Пользователи для проверки ({len(settings.verify_users_set)}): {settings.verify_users_set}")
    logger.info(f"   Всего разрешенных пользователей: {len(settings.all_allowed_users)}")


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


# Функция для тестирования прав доступа
def test_access_permissions():
    """Тестирует права доступа для диагностики."""
    settings = get_settings()

    print("🔍 ДИАГНОСТИКА ПРАВ ДОСТУПА:")
    print("=" * 50)
    print(f"Admin users: {settings.admin_users}")
    print(f"Verify users: {settings.verify_users}")
    print(f"Admin users set: {settings.admin_users_set}")
    print(f"Verify users set: {settings.verify_users_set}")
    print(f"All allowed users: {settings.all_allowed_users}")
    print("=" * 50)

    # Тестируем конкретного пользователя
    test_user_id = input("Введите Telegram ID для тестирования: ")
    try:
        user_id = int(test_user_id)
        print(f"\n🧪 ТЕСТ ДЛЯ ПОЛЬЗОВАТЕЛЯ {user_id}:")
        print(f"   is_admin: {settings.is_admin(user_id)}")
        print(f"   is_verify_user: {settings.is_verify_user(user_id)}")
        print(f"   is_allowed_user: {settings.is_allowed_user(user_id)}")
        print(f"   in admin_users_set: {user_id in settings.admin_users_set}")
        print(f"   in verify_users_set: {user_id in settings.verify_users_set}")
        print(f"   in all_allowed_users: {user_id in settings.all_allowed_users}")
    except ValueError:
        print("❌ Некорректный ID пользователя")


if __name__ == "__main__":
    # Запуск диагностики
    test_access_permissions()
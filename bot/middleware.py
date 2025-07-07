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

        # Проверяем тип чата - в группах бот не отвечает на команды
        if chat_type in ['group', 'supergroup']:
            # В группах бот молчит, только слушает для уведомлений
            logger.debug(f"Сообщение в группе {chat_type} от пользователя {user_id} - игнорируем")
            return None

        # ОТЛАДОЧНОЕ ЛОГИРОВАНИЕ
        logger.info(f"🔍 ПРОВЕРКА ДОСТУПА:")
        logger.info(f"   User ID: {user_id} (тип: {type(user_id)})")
        logger.info(f"   User Info: {user_info}")
        logger.info(f"   Chat Type: {chat_type}")

        # Получаем множества пользователей
        admin_users = self.settings.admin_users_set
        verify_users = self.settings.verify_users_set
        all_users = self.settings.all_allowed_users

        logger.info(f"   Admin Users: {admin_users}")
        logger.info(f"   Verify Users: {verify_users}")
        logger.info(f"   All Allowed: {all_users}")

        # Проверяем права доступа
        is_admin = self.settings.is_admin(user_id)
        is_verify = self.settings.is_verify_user(user_id)
        is_allowed = self.settings.is_allowed_user(user_id)

        logger.info(f"   Is Admin: {is_admin}")
        logger.info(f"   Is Verify: {is_verify}")
        logger.info(f"   Is Allowed: {is_allowed}")

        # Дополнительная проверка через прямое сравнение
        direct_admin_check = user_id in admin_users
        direct_verify_check = user_id in verify_users
        direct_all_check = user_id in all_users

        logger.info(f"   Direct Admin Check: {direct_admin_check}")
        logger.info(f"   Direct Verify Check: {direct_verify_check}")
        logger.info(f"   Direct All Check: {direct_all_check}")

        # Если пользователь не найден в списках
        if not is_allowed:
            logger.warning(f"❌ ОТКАЗ В ДОСТУПЕ для пользователя {user_id} {user_info}")
            logger.warning(f"   Пользователь НЕ найден в списках доступа")
            logger.warning(f"   Проверьте .env файл и убедитесь, что ID {user_id} добавлен в VERIFY_USERS или ADMIN_USERS")

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
            'chat_type': chat_type
        }

        logger.info(f"✅ Пользователь {user_id} {user_info} получил доступ в {chat_type}")
        logger.info(f"   Права: admin={is_admin}, verify={is_verify}")

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

        logger.info(f"🔐 ПРОВЕРКА АДМИНСКИХ ПРАВ:")
        logger.info(f"   User ID: {user_id}")
        logger.info(f"   Is Admin: {is_admin}")
        logger.info(f"   Admin Users: {self.settings.admin_users_set}")

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

        logger.info(f"✅ Админские права подтверждены для пользователя {user_id}")

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
        can_verify = self.settings.is_verify_user(user_id)

        logger.info(f"🔍 ПРОВЕРКА ПРАВ НА ВЕРИФИКАЦИЮ:")
        logger.info(f"   User ID: {user_id}")
        logger.info(f"   Can Verify: {can_verify}")
        logger.info(f"   Admin Users: {self.settings.admin_users_set}")
        logger.info(f"   Verify Users: {self.settings.verify_users_set}")

        if not can_verify:
            logger.warning(f"❌ Пользователь {user_id} попытался проверить сертификат без прав")

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

        logger.info(f"✅ Права на верификацию подтверждены для пользователя {user_id}")

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
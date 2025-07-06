"""
Главный модуль Telegram бота
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage

# Добавляем путь к модулям
sys.path.append(str(Path(__file__).parent.parent))

from core.storage import DatabaseStorage, FileStorage
from bot.handlers import CertificateHandlers


class CertificateBot:
    """Главный класс Telegram бота"""

    def __init__(self):
        self.setup_logging()
        self.load_config()
        self.setup_storage()
        self.setup_bot()

    def setup_logging(self):
        """Настройка логирования"""
        log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('bot.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def load_config(self):
        """Загрузка конфигурации"""
        # Обязательные параметры
        self.bot_token = os.getenv('BOT_TOKEN')
        if not self.bot_token:
            raise ValueError("BOT_TOKEN не найден в переменных окружения")

        # Права пользователей
        allowed_users_str = os.getenv('ALLOWED_USERS', '')
        self.allowed_users = set(
            int(user_id.strip())
            for user_id in allowed_users_str.split(',')
            if user_id.strip().isdigit()
        )

        verify_users_str = os.getenv('VERIFY_USERS', '')
        self.verify_users = set(
            int(user_id.strip())
            for user_id in verify_users_str.split(',')
            if user_id.strip().isdigit()
        )

        # Чат для уведомлений
        notification_chat_str = os.getenv('NOTIFICATION_CHAT')
        self.notification_chat = int(notification_chat_str) if notification_chat_str else None

        # База данных
        self.database_url = os.getenv('DATABASE_URL')
        if not self.database_url:
            raise ValueError("DATABASE_URL не найден в переменных окружения")

        # Файловое хранилище
        self.certificates_dir = os.getenv('CERTIFICATES_DIR', 'certificates')

        # Redis для FSM (опционально)
        self.redis_url = os.getenv('REDIS_URL')

        self.logger.info(f"Загружена конфигурация: {len(self.allowed_users)} генераторов, "
                         f"{len(self.verify_users)} проверяющих")

    def setup_storage(self):
        """Настройка хранилищ"""
        # База данных
        self.db_storage = DatabaseStorage(self.database_url)

        # Файловое хранилище
        self.file_storage = FileStorage(self.certificates_dir)

        self.logger.info("Хранилища настроены")

    def setup_bot(self):
        """Настройка бота"""
        # Создание бота
        self.bot = Bot(
            token=self.bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )

        # Настройка хранилища состояний
        if self.redis_url:
            storage = RedisStorage.from_url(self.redis_url)
            self.logger.info("Используется Redis для хранения состояний")
        else:
            storage = MemoryStorage()
            self.logger.info("Используется Memory storage для хранения состояний")

        # Создание диспетчера
        self.dp = Dispatcher(storage=storage)

        # Создание обработчиков
        self.handlers = CertificateHandlers(
            db_storage=self.db_storage,
            file_storage=self.file_storage,
            allowed_users=self.allowed_users,
            verify_users=self.verify_users,
            notification_chat=self.notification_chat
        )

        # Регистрация роутера
        self.dp.include_router(self.handlers.router)

        # Middleware для логирования
        @self.dp.message.middleware()
        async def logging_middleware(handler, event, data):
            user = event.from_user
            self.logger.info(f"Сообщение от {user.id} (@{user.username}): {event.text}")
            return await handler(event, data)

        # Обработчик ошибок
        @self.dp.error()
        async def error_handler(event, exception):
            self.logger.error(f"Ошибка в боте: {exception}", exc_info=True)

    async def start(self):
        """Запуск бота"""
        try:
            # Подключение к БД
            await self.db_storage.connect()
            self.logger.info("Подключение к БД установлено")

            # Получение информации о боте
            bot_info = await self.bot.get_me()
            self.logger.info(f"Бот запущен: @{bot_info.username}")

            # Запуск поллинга
            await self.dp.start_polling(self.bot)

        except Exception as e:
            self.logger.error(f"Ошибка запуска бота: {e}")
            raise
        finally:
            # Закрытие соединений
            await self.db_storage.disconnect()
            await self.bot.session.close()

    async def stop(self):
        """Остановка бота"""
        self.logger.info("Остановка бота...")
        await self.db_storage.disconnect()
        await self.bot.session.close()


async def main():
    """Главная функция"""
    bot = CertificateBot()

    try:
        await bot.start()
    except KeyboardInterrupt:
        print("\nОстановка бота...")
    except Exception as e:
        logging.error(f"Критическая ошибка: {e}")
        sys.exit(1)
    finally:
        await bot.stop()


if __name__ == '__main__':
    asyncio.run(main())
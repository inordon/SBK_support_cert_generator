"""
Основной файл для запуска Telegram бота.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Добавляем корневую директорию в путь для импортов
sys.path.append(str(Path(__file__).parent.parent))

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config.settings import get_settings, validate_settings
from core.database import get_db_manager
from .middleware import setup_middlewares
from .handlers import common, admin, verify

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/bot.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


async def create_bot_and_dispatcher() -> tuple[Bot, Dispatcher]:
    """
    Создает экземпляры бота и диспетчера.

    Returns:
        tuple[Bot, Dispatcher]: Кортеж с ботом и диспетчером
    """
    settings = get_settings()

    # Создаем бота с настройками по умолчанию
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    # Создаем диспетчер с хранилищем состояний в памяти
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    return bot, dp


def setup_handlers(dp: Dispatcher):
    """
    Настройка обработчиков команд.

    Args:
        dp: Диспетчер aiogram
    """
    # Порядок важен! Сначала специфичные обработчики, потом общие

    # Обработчики для администраторов (создание сертификатов)
    dp.include_router(admin.router)

    # Обработчики для проверки сертификатов
    dp.include_router(verify.router)

    # Общие обработчики (должны быть последними)
    dp.include_router(common.router)

    logger.info("Обработчики команд настроены")


async def setup_bot_commands(bot: Bot):
    """
    Настройка команд бота в меню.

    Args:
        bot: Экземпляр бота
    """
    from aiogram.types import BotCommand

    commands = [
        BotCommand(command="start", description="🚀 Запустить бота"),
        BotCommand(command="help", description="❓ Справка по командам"),
        BotCommand(command="cancel", description="❌ Отменить текущую операцию"),
        BotCommand(command="status", description="📊 Статистика (только админы)"),
    ]

    await bot.set_my_commands(commands)
    logger.info("Команды бота настроены")


async def check_bot_permissions(bot: Bot):
    """
    Проверяет права бота и его настройки.

    Args:
        bot: Экземпляр бота
    """
    try:
        bot_info = await bot.get_me()
        logger.info(f"Бот запущен: @{bot_info.username} ({bot_info.full_name})")

        # Проверяем возможность отправки сообщений в группу уведомлений
        settings = get_settings()
        try:
            await bot.send_message(
                chat_id=settings.notification_group,
                text="🤖 Бот запущен и готов к работе!"
            )
            logger.info("Уведомление о запуске отправлено в группу")
        except Exception as e:
            logger.warning(f"Не удалось отправить уведомление в группу: {e}")

    except Exception as e:
        logger.error(f"Ошибка проверки прав бота: {e}")
        raise


async def on_startup():
    """Действия при запуске бота."""
    logger.info("Запуск бота...")

    # Проверяем настройки
    if not validate_settings():
        logger.error("Некорректные настройки. Запуск невозможен.")
        sys.exit(1)

    # Проверяем подключение к БД
    db_manager = get_db_manager()
    if not db_manager.health_check():
        logger.error("Не удалось подключиться к базе данных. Запуск невозможен.")
        sys.exit(1)

    # Создаем таблицы если их нет
    try:
        db_manager.create_tables()
        logger.info("Таблицы базы данных проверены/созданы")
    except Exception as e:
        logger.error(f"Ошибка создания таблиц БД: {e}")
        sys.exit(1)

    logger.info("Инициализация завершена успешно")


async def on_shutdown(bot: Bot = None):
    """Действия при завершении работы бота."""
    logger.info("Завершение работы бота...")

    # Отправляем уведомление о завершении работы
    if bot:
        try:
            settings = get_settings()
            await bot.send_message(
                chat_id=settings.notification_group,
                text="🔴 Бот остановлен"
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить уведомление об остановке: {e}")

    logger.info("Бот завершил работу")


async def main():
    """Основная функция запуска бота."""
    try:
        # Выполняем действия при запуске
        await on_startup()

        # Создаем бота и диспетчер
        bot, dp = await create_bot_and_dispatcher()

        # Настраиваем middleware
        setup_middlewares(dp)

        # Настраиваем обработчики
        setup_handlers(dp)

        # Настраиваем команды бота
        await setup_bot_commands(bot)

        # Проверяем права бота
        await check_bot_permissions(bot)

        # Регистрируем функции lifecycle
        dp.startup.register(on_startup)
        dp.shutdown.register(lambda: on_shutdown(bot))

        logger.info("Бот готов к работе. Начинаем polling...")

        # Запускаем polling
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)
    finally:
        await on_shutdown()


def run_bot():
    """Запускает бота в синхронном режиме."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_bot()
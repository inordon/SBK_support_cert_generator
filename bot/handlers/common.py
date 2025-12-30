"""
Общие обработчики команд (/start, /help и т.д.).
"""

import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from core.service import get_certificate_service
from ..keyboards import get_main_menu_admin, get_main_menu_verify, ButtonTexts
from config.settings import get_settings

logger = logging.getLogger(__name__)
router = Router()

# Получаем сервисы
certificate_service = get_certificate_service()
settings = get_settings()


@router.message(CommandStart())
async def start_command(message: Message, state: FSMContext, user_permissions: dict):
    """Обработчик команды /start."""
    await state.clear()  # Очищаем любые активные состояния

    user_name = message.from_user.full_name or f"Пользователь {message.from_user.id}"

    if user_permissions['is_admin']:
        welcome_text = (
            f"👋 Добро пожаловать, {user_name}!\n\n"
            "🔑 Вы вошли как администратор\n\n"
            "Доступные функции:\n"
            "• 📝 Создание сертификатов\n"
            "• 📋 Просмотр своих сертификатов\n"
            "• 🔍 Проверка сертификатов\n"
            "• 🔎 Поиск по домену и ИНН\n\n"
            "Выберите действие:"
        )
        keyboard = get_main_menu_admin()

    else:
        welcome_text = (
            f"👋 Добро пожаловать, {user_name}!\n\n"
            "🔍 Вы можете проверять сертификаты\n\n"
            "Доступные функции:\n"
            "• 🔍 Проверка сертификатов по ID\n"
            "• 🔎 Поиск по домену и ИНН\n\n"
            "Выберите действие:"
        )
        keyboard = get_main_menu_verify()

    await message.answer(welcome_text, reply_markup=keyboard)


@router.message(Command("help"))
@router.message(F.text == ButtonTexts.HELP)
async def help_command(message: Message, user_permissions: dict):
    """Обработчик команды /help и кнопки справки."""

    if user_permissions['is_admin']:
        help_text = (
            "📖 Справка по боту (Администратор)\n\n"

            "🔧 Доступные команды:\n"
            "• /start - Перезапуск бота\n"
            "• /help - Эта справка\n\n"

            "📝 Создание сертификатов:\n"
            "1. Нажмите 'Создать сертификат'\n"
            "2. Введите домен (поддерживаются wildcard: *.example.com)\n"
#            "3. Введите ИНН (10 или 12 цифр)\n"
            "3. Введите ИНН/БИН организации:\n"
                "ИНН РФ: 10 или 12 цифр\n"
                "БИН Казахстана: 12 цифр"
            "4. Выберите период действия\n"
            "5. Укажите количество пользователей\n"
            "6. Подтвердите создание\n\n"

            "🔍 Проверка сертификатов:\n"
            "• Введите ID сертификата в формате XXXXX-XXXXX-XXXXX-XXXXX\n"
            "• Получите полную информацию о сертификате\n\n"

            "🔎 Поиск сертификатов:\n"
            "• По домену: найти все сертификаты для домена\n"
            "• По ИНН: найти все сертификаты организации\n\n"

            "📋 Мои сертификаты:\n"
            "• Просмотр всех созданных вами сертификатов\n"
            "• Разделение на активные, просроченные и деактивированные\n\n"

            "📅 Поддерживаемые форматы доменов:\n"
            "• example.com\n"
            "• sub.example.com\n"
            "• my-site.com\n"
            "• *.example.com\n"
            "• *.sub.example.com\n\n"

            "ℹ️ Дополнительная информация:\n"
            "• Сертификаты автоматически сохраняются в БД и файлы\n"
            "• При создании отправляется уведомление в группу\n"
            "• ID сертификата содержит дату окончания в последних 4 символах\n"
            "• Все действия логируются"
        )
        keyboard = get_main_menu_admin()

    else:
        help_text = (
            "📖 Справка по боту (Проверка)\n\n"

            "🔧 Доступные команды:\n"
            "• /start - Перезапуск бота\n"
            "• /help - Эта справка\n\n"

            "🔍 Проверка сертификатов:\n"
            "1. Нажмите 'Проверить сертификат'\n"
            "2. Введите ID сертификата в формате XXXXX-XXXXX-XXXXX-XXXXX\n"
            "3. Получите информацию о статусе сертификата\n\n"

            "🔎 Поиск сертификатов:\n"
            "• По домену: найти все сертификаты для домена\n"
            "• По ИНН: найти все сертификаты организации\n\n"

            "📊 Информация о сертификате:\n"
            "• ID сертификата\n"
            "• Доменное имя\n"
            "• ИНН организации\n"
            "• Период действия\n"
            "• Количество пользователей\n"
            "• Статус (активен/просрочен/деактивирован)\n"
            "• Дата создания\n\n"

            "🎯 Статусы сертификатов:\n"
            "• ✅ Активен - сертификат действителен\n"
            "• ⚠️ Истекает - осталось менее 30 дней\n"
            "• ⚠️ Просрочен - срок действия истек\n"
            "• ❌ Деактивирован - сертификат отключен\n\n"

            "💡 Полезные советы:\n"
            "• ID сертификата можно скопировать из уведомлений\n"
            "• При поиске по домену можно использовать частичное совпадение\n"
            "• Все проверки сертификатов записываются в историю"
        )
        keyboard = get_main_menu_verify()

    await message.answer(help_text, reply_markup=keyboard)


@router.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext, user_permissions: dict):
    """Обработчик команды /cancel для отмены текущих операций."""
    await state.clear()

    keyboard = get_main_menu_admin() if user_permissions['is_admin'] else get_main_menu_verify()

    await message.answer(
        "❌ Текущая операция отменена. Возвращаемся в главное меню.",
        reply_markup=keyboard
    )


@router.message(Command("status"))
async def status_command(message: Message, user_permissions: dict):
    """Обработчик команды /status для получения статистики."""

    if not user_permissions['is_admin']:
        await message.answer(
            "❌ Команда доступна только администраторам.",
            reply_markup=get_main_menu_verify()
        )
        return

    try:
        # Получаем статистику
        stats = certificate_service.get_statistics()

        db_stats = stats['database']
        file_stats = stats['file_storage']

        status_text = (
            "📊 Статистика системы\n\n"

            "🗄️ База данных:\n"
            f"• Всего сертификатов: {db_stats['total_certificates']}\n"
            f"• Активных: {db_stats['active_certificates']}\n"
            f"• Просроченных: {db_stats['expired_certificates']}\n"
            f"• Деактивированных: {db_stats['inactive_certificates']}\n\n"

            "📁 Файловое хранилище:\n"
            f"• Файлов: {file_stats['total_files']}\n"
            f"• Размер: {file_stats['total_size_mb']} МБ\n"
            f"• Годы: {', '.join(file_stats['years_covered']) if file_stats['years_covered'] else 'нет данных'}\n"
            f"• Путь: {file_stats['base_path']}\n\n"

            f"🕒 Обновлено: {stats['last_updated'][:19]}"
        )

        await message.answer(status_text, reply_markup=get_main_menu_admin())

    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        await message.answer(
            "❌ Не удалось получить статистику системы.",
            reply_markup=get_main_menu_admin()
        )

@router.message()
async def unknown_message(message: Message, user_permissions: dict):
    """Обработчик неизвестных сообщений."""

    # Проверяем, не является ли это системным сообщением
    if message.content_type != 'text':
        return

    keyboard = get_main_menu_admin() if user_permissions['is_admin'] else get_main_menu_verify()

    await message.answer(
        "❓ Неизвестная команда. Воспользуйтесь меню или командой /help для получения справки.",
        reply_markup=keyboard
    )

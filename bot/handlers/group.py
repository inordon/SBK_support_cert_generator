"""
Обработчики slash-команд для работы в групповых чатах.

Команды работают как в группах, так и в личных сообщениях.
В группах не используются reply-клавиатуры, ответы идут через reply.
"""

import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command, CommandObject
from core.service import get_certificate_service
from core.models import SearchRequest
from core.exceptions import ValidationError
from ..keyboards import get_main_menu_admin, get_main_menu_verify
from config.settings import get_settings

logger = logging.getLogger(__name__)
router = Router()

# Получаем сервисы
certificate_service = get_certificate_service()
settings = get_settings()


def _get_keyboard(user_permissions: dict):
    """Возвращает клавиатуру или None для групповых чатов."""
    if user_permissions.get('is_group'):
        return None
    if user_permissions.get('is_admin'):
        return get_main_menu_admin()
    return get_main_menu_verify()


@router.message(Command("verify"))
async def cmd_verify(message: Message, command: CommandObject, user_permissions: dict):
    """
    Проверка сертификата по ID.
    Использование: /verify XXXXX-XXXXX-XXXXX-XXXXX
    """
    if not command.args:
        help_text = (
            "🔍 Проверка сертификата\n\n"
            "Использование: /verify XXXXX-XXXXX-XXXXX-XXXXX\n\n"
            "Введите ID сертификата после команды."
        )
        await message.reply(help_text)
        return

    certificate_id = command.args.strip().upper()

    try:
        certificate = certificate_service.verify_certificate(certificate_id, message.from_user.id)

        if certificate is None:
            await message.reply(f"❌ Сертификат с ID {certificate_id} не найден.")
            return

        cert_info = certificate_service.format_certificate_info(certificate, detailed=True)

        # Краткий итог по статусу
        if not certificate.is_active:
            status_line = "⚠️ Сертификат деактивирован"
        elif certificate.is_expired:
            status_line = "⚠️ Срок действия сертификата истек"
        elif certificate.days_left <= 7:
            status_line = f"⚠️ Сертификат истекает через {certificate.days_left} дней!"
        elif certificate.days_left <= 30:
            status_line = f"⚠️ Сертификат истекает через {certificate.days_left} дней"
        else:
            status_line = "✅ Сертификат действителен"

        response = f"🔍 Результат проверки:\n\n{cert_info}\n\n{status_line}"
        keyboard = _get_keyboard(user_permissions)
        await message.reply(response, reply_markup=keyboard)

    except ValidationError as e:
        await message.reply(f"❌ Ошибка валидации: {e}")
    except Exception as e:
        logger.error(f"Ошибка проверки сертификата {certificate_id}: {e}")
        await message.reply("❌ Ошибка при проверке сертификата. Попробуйте позже.")


@router.message(Command("search"))
async def cmd_search(message: Message, command: CommandObject, user_permissions: dict):
    """
    Поиск сертификатов по домену или ИНН.
    Использование: /search <домен или ИНН>
    """
    if not command.args:
        help_text = (
            "🔎 Поиск сертификатов\n\n"
            "Использование:\n"
            "• /search example.com - поиск по домену\n"
            "• /search 1234567890 - поиск по ИНН\n"
        )
        await message.reply(help_text)
        return

    query = command.args.strip()

    # Автоопределение: если все цифры и 10/12 символов → ИНН, иначе → домен
    if query.isdigit() and len(query) in [10, 12]:
        search_request = SearchRequest(inn=query, active_only=True)
        search_type = "ИНН"
        search_value = query
    else:
        search_request = SearchRequest(domain=query.lower(), active_only=True)
        search_type = "домену"
        search_value = query.lower()

    try:
        certificates = certificate_service.search_certificates(search_request)

        if not certificates:
            await message.reply(f"📝 Сертификаты по {search_type} '{search_value}' не найдены.")
            return

        result_text = f"🔎 Найдено по {search_type} '{search_value}': {len(certificates)}\n\n"

        for i, cert in enumerate(certificates[:5], 1):
            cert_info = certificate_service.format_certificate_info(cert)
            result_text += f"{i}. {cert_info}\n\n"

        if len(certificates) > 5:
            result_text += f"... и ещё {len(certificates) - 5} сертификатов"

        keyboard = _get_keyboard(user_permissions)
        await message.reply(result_text, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Ошибка поиска '{query}': {e}")
        await message.reply("❌ Ошибка при поиске. Попробуйте позже.")


@router.message(Command("list"))
async def cmd_list(message: Message, user_permissions: dict):
    """Список всех активных сертификатов."""
    try:
        search_request = SearchRequest(active_only=True)
        certificates = certificate_service.search_certificates(search_request)

        if not certificates:
            await message.reply("📝 Активные сертификаты не найдены.")
            return

        result_text = f"📋 Активные сертификаты ({len(certificates)}):\n\n"
        result_text += certificate_service.format_certificates_list(certificates, max_items=15)

        keyboard = _get_keyboard(user_permissions)
        await message.reply(result_text, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Ошибка получения списка сертификатов: {e}")
        await message.reply("❌ Ошибка при получении списка. Попробуйте позже.")


@router.message(Command("stats"))
async def cmd_stats(message: Message, user_permissions: dict):
    """Статистика по сертификатам (доступна всем авторизованным пользователям)."""
    try:
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
        )

        keyboard = _get_keyboard(user_permissions)
        await message.reply(status_text, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        await message.reply("❌ Не удалось получить статистику.")

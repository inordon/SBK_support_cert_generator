"""
Обработчики команд для администраторов - исправленная версия.
"""

import logging
import re
from datetime import datetime, date, timedelta
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from core.service import get_certificate_service
from core.models import CertificateRequest
from core.exceptions import *
from ..states import CreateCertificateStates
from ..keyboards import (
    get_main_menu_admin, get_confirmation_keyboard, get_cancel_keyboard,
    ButtonTexts, remove_keyboard
)
from ..middleware import admin_required
from config.settings import get_settings

logger = logging.getLogger(__name__)
router = Router()
router.message.middleware(admin_required())

# Получаем сервисы
certificate_service = get_certificate_service()
settings = get_settings()


@router.message(F.text == ButtonTexts.CREATE_CERTIFICATE)
async def start_create_certificate(message: Message, state: FSMContext):
    """Начинает процесс создания сертификата."""
    await state.clear()  # Очищаем предыдущие состояния

    instruction_text = """📝 Создание нового сертификата

Отправьте информацию в следующем формате:

```
Срок действия: ДД.ММ.ГГГГ-ДД.ММ.ГГГГ
ИНН: 1234567890
Домен: example.com
Количество пользователей: 100
```

📋 Примеры:
```
Срок действия: 01.01.2025-31.12.2025
ИНН: 7707083893
Домен: my-site.com
Количество пользователей: 500
```

```
Срок действия: 01.07.2025-30.06.2026
ИНН: 1234567890
Домен: *.example.com
Количество пользователей: 1
```

ℹ️ Поддерживаемые форматы доменов:
• example.com
• sub.example.com
• my-site.com
• *.example.com (wildcard)
• *.sub.example.com

Отправьте данные или нажмите "Отменить":"""

    await message.answer(
        instruction_text,
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )

    await state.set_state(CreateCertificateStates.waiting_for_certificate_data)


@router.message(CreateCertificateStates.waiting_for_certificate_data)
async def process_certificate_data(message: Message, state: FSMContext):
    """Обрабатывает данные сертификата, переданные одним сообщением."""
    if message.text == ButtonTexts.CANCEL:
        await cancel_creation(message, state)
        return

    try:
        # Парсим данные из сообщения
        certificate_data = parse_certificate_message(message.text)

        # Валидируем данные
        errors = certificate_service.validate_certificate_data(
            certificate_data['domain'],
            certificate_data['inn'],
            certificate_data['valid_from'],
            certificate_data['valid_to'],
            certificate_data['users_count']
        )

        if errors:
            error_text = "❌ Ошибки валидации:\n\n" + "\n".join(f"• {error}" for error in errors)
            error_text += "\n\nПопробуйте еще раз или нажмите 'Отменить':"

            await message.answer(
                error_text,
                reply_markup=get_cancel_keyboard()
            )
            return

        # Проверяем существующие сертификаты для домена
        try:
            from core.models import SearchRequest
            search_request = SearchRequest(domain=certificate_data['domain'], active_only=True)
            existing_certificates = certificate_service.search_certificates(search_request)

            # Сохраняем данные в состоянии
            await state.update_data(**certificate_data, has_existing=len(existing_certificates) > 0)

            if existing_certificates:
                certificates_list = certificate_service.format_certificates_list(existing_certificates)
                await message.answer(
                    f"⚠️ Для домена {certificate_data['domain']} уже существуют активные сертификаты:\n\n"
                    f"{certificates_list}\n\n"
                    "Продолжить создание нового сертификата?"
                )

            # Форматируем информацию для подтверждения
            period_str = f"{certificate_data['valid_from'].strftime('%d.%m.%Y')}-{certificate_data['valid_to'].strftime('%d.%m.%Y')}"

            confirmation_text = (
                "✅ Подтвердите создание сертификата:\n\n"
                f"🌐 Домен: {certificate_data['domain']}\n"
                f"🏢 ИНН: {certificate_data['inn']}\n"
                f"📅 Период: {period_str}\n"
                f"👥 Пользователей: {certificate_data['users_count']}\n"
            )

            if len(existing_certificates) > 0:
                confirmation_text += "\n⚠️ Для этого домена уже есть активные сертификаты!"

            await message.answer(
                confirmation_text,
                reply_markup=get_confirmation_keyboard()
            )

            await state.set_state(CreateCertificateStates.waiting_for_confirmation)

        except Exception as e:
            logger.error(f"Ошибка при проверке существующих сертификатов: {e}")
            await message.answer(
                "❌ Произошла ошибка при проверке существующих сертификатов. "
                "Попробуйте еще раз.",
                reply_markup=get_cancel_keyboard()
            )

    except ValueError as e:
        await message.answer(
            f"❌ Ошибка формата данных: {e}\n\n"
            "Проверьте формат и попробуйте еще раз:",
            reply_markup=get_cancel_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка обработки данных сертификата: {e}")
        await message.answer(
            "❌ Произошла неожиданная ошибка при обработке данных.\n\n"
            "Попробуйте еще раз или нажмите 'Отменить':",
            reply_markup=get_cancel_keyboard()
        )


def parse_certificate_message(text: str) -> dict:
    """
    Парсит сообщение с данными сертификата.

    Args:
        text: Текст сообщения

    Returns:
        dict: Словарь с данными сертификата

    Raises:
        ValueError: При ошибке парсинга
    """
    # Удаляем лишние пробелы и переводы строк
    text = text.strip()

    # Инициализируем результат
    result = {}

    # Паттерны для поиска данных
    patterns = {
        'period': r'срок\s+действия\s*:\s*(\d{1,2}\.\d{1,2}\.\d{4})\s*-\s*(\d{1,2}\.\d{1,2}\.\d{4})',
        'inn': r'инн\s*:\s*(\d{10,12})',
        'domain': r'домен\s*:\s*([a-zA-Z0-9.*-]+\.[a-zA-Z]{2,})',
        'users': r'количество\s+пользователей\s*:\s*(\d+)'
    }

    # Ищем период действия
    period_match = re.search(patterns['period'], text, re.IGNORECASE | re.UNICODE)
    if not period_match:
        raise ValueError("Не найден срок действия. Используйте формат: Срок действия: ДД.ММ.ГГГГ-ДД.ММ.ГГГГ")

    try:
        valid_from = datetime.strptime(period_match.group(1), "%d.%m.%Y").date()
        valid_to = datetime.strptime(period_match.group(2), "%d.%m.%Y").date()
        result['valid_from'] = valid_from
        result['valid_to'] = valid_to
    except ValueError as e:
        raise ValueError(f"Неверный формат даты: {e}")

    # Ищем ИНН
    inn_match = re.search(patterns['inn'], text, re.IGNORECASE)
    if not inn_match:
        raise ValueError("Не найден ИНН. Используйте формат: ИНН: 1234567890")
    result['inn'] = inn_match.group(1)

    # Ищем домен
    domain_match = re.search(patterns['domain'], text, re.IGNORECASE)
    if not domain_match:
        raise ValueError("Не найден домен. Используйте формат: Домен: example.com")
    result['domain'] = domain_match.group(1).lower()

    # Ищем количество пользователей
    users_match = re.search(patterns['users'], text, re.IGNORECASE | re.UNICODE)
    if not users_match:
        raise ValueError("Не найдено количество пользователей. Используйте формат: Количество пользователей: 100")

    try:
        users_count = int(users_match.group(1))
        if users_count < 1:
            raise ValueError("Количество пользователей должно быть больше 0")
        result['users_count'] = users_count
    except ValueError as e:
        raise ValueError(f"Неверное количество пользователей: {e}")

    return result


@router.message(CreateCertificateStates.waiting_for_confirmation)
async def process_confirmation(message: Message, state: FSMContext):
    """Обрабатывает подтверждение создания сертификата."""
    if message.text == ButtonTexts.CANCEL:
        await cancel_creation(message, state)
        return

    if message.text != ButtonTexts.CONFIRM:
        await message.answer(
            "Выберите действие:",
            reply_markup=get_confirmation_keyboard()
        )
        return

    # Получаем данные из состояния
    data = await state.get_data()

    try:
        # Создаем запрос на сертификат
        certificate_request = CertificateRequest(
            domain=data['domain'],
            inn=data['inn'],
            valid_from=data['valid_from'],
            valid_to=data['valid_to'],
            users_count=data['users_count'],
            created_by=message.from_user.id
        )

        # Создаем сертификат
        certificate, has_existing = certificate_service.create_certificate(certificate_request)

        # Форматируем информацию о созданном сертификате
        cert_info = certificate_service.format_certificate_info(certificate, detailed=True)

        await message.answer(
            f"✅ Сертификат успешно создан!\n\n{cert_info}",
            reply_markup=get_main_menu_admin(),
            parse_mode="Markdown"
        )

        # Отправляем уведомление в группу
        try:
            notification_text = (
                f"🆕 Создан новый сертификат\n\n"
                f"🆔 ID: `{certificate.certificate_id}`\n"
                f"🌐 Домен: {certificate.domain}\n"
                f"🏢 ИНН: {certificate.inn}\n"
                f"📅 Период: {certificate.validity_period}\n"
                f"👥 Пользователей: {certificate.users_count}\n"
                f"👤 Создатель: {message.from_user.full_name} ({message.from_user.id})"
            )

            # Получаем бота из контекста
            bot = message.bot
            await bot.send_message(
                chat_id=settings.notification_group,
                text=notification_text,
                parse_mode="Markdown"
            )

        except Exception as e:
            logger.error(f"Ошибка отправки уведомления в группу: {e}")

        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка создания сертификата: {e}")

        if isinstance(e, ValidationError):
            error_text = f"❌ Ошибка валидации: {e}"
        elif isinstance(e, GenerationError):
            error_text = f"❌ Ошибка генерации ID: {e}"
        else:
            error_text = "❌ Произошла неожиданная ошибка при создании сертификата."

        await message.answer(
            error_text + "\n\nПопробуйте еще раз.",
            reply_markup=get_main_menu_admin()
        )
        await state.clear()


@router.message(F.text == ButtonTexts.MY_CERTIFICATES)
async def show_user_certificates(message: Message):
    """Показывает сертификаты, созданные пользователем."""
    try:
        certificates = certificate_service.get_user_certificates(
            message.from_user.id, active_only=False
        )

        if not certificates:
            await message.answer(
                "📝 Вы еще не создали ни одного сертификата.",
                reply_markup=get_main_menu_admin()
            )
            return

        # Разделяем на активные и неактивные
        active_certificates = [cert for cert in certificates if cert.is_active and not cert.is_expired]
        expired_certificates = [cert for cert in certificates if cert.is_active and cert.is_expired]
        inactive_certificates = [cert for cert in certificates if not cert.is_active]

        response_parts = []

        if active_certificates:
            active_list = certificate_service.format_certificates_list(active_certificates)
            response_parts.append(f"✅ Активные сертификаты ({len(active_certificates)}):\n{active_list}")

        if expired_certificates:
            expired_list = certificate_service.format_certificates_list(expired_certificates)
            response_parts.append(f"⚠️ Просроченные сертификаты ({len(expired_certificates)}):\n{expired_list}")

        if inactive_certificates:
            inactive_list = certificate_service.format_certificates_list(inactive_certificates)
            response_parts.append(f"❌ Деактивированные сертификаты ({len(inactive_certificates)}):\n{inactive_list}")

        response_text = f"📋 Ваши сертификаты (всего: {len(certificates)}):\n\n" + \
                        "\n\n".join(response_parts)

        await message.answer(response_text, reply_markup=get_main_menu_admin())

    except Exception as e:
        logger.error(f"Ошибка получения сертификатов пользователя {message.from_user.id}: {e}")
        await message.answer(
            "❌ Произошла ошибка при получении списка сертификатов.",
            reply_markup=get_main_menu_admin()
        )


async def cancel_creation(message: Message, state: FSMContext):
    """Отменяет процесс создания сертификата."""
    await state.clear()
    await message.answer(
        "❌ Создание сертификата отменено.",
        reply_markup=get_main_menu_admin()
    )
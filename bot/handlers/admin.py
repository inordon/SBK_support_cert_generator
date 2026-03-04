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

Отправьте данные построчно в формате:

```
01.12.2024-01.12.2025
1234567890
example.com
100
```

Дополнительно можно указать email и контактных лиц:

```
01.01.2025-31.12.2025
7707083893
my-site.com
500
support@company.com
Иванов И.И. ivanov@company.com
Петров П.П. petrov@company.com
```

Строки 5+ необязательны:
• Строка 5: email для отправки запросов
• Строки 6+: ФИО и email контактных лиц

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

            if certificate_data.get('request_email'):
                confirmation_text += f"📧 Email для запросов: {certificate_data['request_email']}\n"

            if certificate_data.get('contacts'):
                contacts_str = "\n".join(f"  • {c['name']} ({c['email']})" for c in certificate_data['contacts'])
                confirmation_text += f"👤 Контактные лица:\n{contacts_str}\n"

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
    Поддерживает два формата:
    1. Построчно: период / ИНН / домен / пользователи
    2. С подписями: "Срок действия: ...", "ИНН: ..." и т.д.

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

    # Проверяем, есть ли в тексте подписи (старый формат)
    if any(keyword in text.lower() for keyword in ['срок действия:', 'инн:', 'домен:', 'количество']):
        return parse_certificate_with_labels(text)

    # Парсим построчный формат
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    if len(lines) < 4:
        raise ValueError(
            f"Неверное количество строк: {len(lines)}. Ожидается минимум 4 строки:\n"
            "1. Срок действия (ДД.ММ.ГГГГ-ДД.ММ.ГГГГ)\n"
            "2. ИНН (10 или 12 цифр)\n"
            "3. Домен\n"
            "4. Количество пользователей\n"
            "5. Email для запросов (необязательно)\n"
            "6+. ФИО email контактных лиц (необязательно)"
        )

    try:
        # Строка 1: Период действия
        period_line = lines[0]
        if '-' not in period_line:
            raise ValueError("В первой строке должен быть период в формате ДД.ММ.ГГГГ-ДД.ММ.ГГГГ")

        date_parts = period_line.split('-')
        if len(date_parts) != 2:
            raise ValueError("Период должен содержать дату начала и окончания через дефис")

        valid_from = datetime.strptime(date_parts[0].strip(), "%d.%m.%Y").date()
        valid_to = datetime.strptime(date_parts[1].strip(), "%d.%m.%Y").date()
        result['valid_from'] = valid_from
        result['valid_to'] = valid_to

    except ValueError as e:
        if "time data" in str(e):
            raise ValueError("Неверный формат даты в первой строке. Используйте ДД.ММ.ГГГГ-ДД.ММ.ГГГГ")
        raise ValueError(f"Ошибка в дате: {e}")

    # Строка 2: ИНН
    inn_line = lines[1]
    if not inn_line.isdigit():
        raise ValueError("Вторая строка должна содержать только цифры ИНН")
    if len(inn_line) not in [10, 12]:
        raise ValueError("ИНН должен содержать 10 или 12 цифр")
    result['inn'] = inn_line

    # Строка 3: Домен
    domain_line = lines[2].lower()
    if not domain_line or '.' not in domain_line:
        raise ValueError("Третья строка должна содержать доменное имя")
    result['domain'] = domain_line

    # Строка 4: Количество пользователей
    users_line = lines[3]
    if not users_line.isdigit():
        raise ValueError("Четвертая строка должна содержать только цифры (количество пользователей)")

    users_count = int(users_line)
    if users_count < 1:
        raise ValueError("Количество пользователей должно быть больше 0")
    result['users_count'] = users_count

    # Строка 5 (необязательная): Email для запросов
    if len(lines) > 4:
        email_line = lines[4].strip()
        if '@' in email_line and ' ' not in email_line:
            result['request_email'] = email_line
            contact_start = 5
        else:
            # Если строка 5 не похожа на email, это может быть контакт
            result['request_email'] = None
            contact_start = 4

        # Строки 6+ (необязательные): Контактные лица (ФИО email)
        contacts = []
        for i in range(contact_start, len(lines)):
            contact_line = lines[i].strip()
            if not contact_line:
                continue
            # Ищем email в строке (последнее слово с @)
            parts = contact_line.rsplit(maxsplit=1)
            if len(parts) == 2 and '@' in parts[1]:
                contacts.append({"name": parts[0].strip(), "email": parts[1].strip()})
            elif '@' in contact_line:
                # Пробуем разделить по пробелу перед email
                import re as _re
                match = _re.match(r'^(.+?)\s+([\w.+-]+@[\w.-]+)$', contact_line)
                if match:
                    contacts.append({"name": match.group(1).strip(), "email": match.group(2).strip()})

        if contacts:
            result['contacts'] = contacts

    return result


def parse_certificate_with_labels(text: str) -> dict:
    """
    Парсит сообщение с подписями (старый формат).

    Args:
        text: Текст сообщения с подписями

    Returns:
        dict: Словарь с данными сертификата

    Raises:
        ValueError: При ошибке парсинга
    """
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
        logger.info(f"Создание запроса сертификата для пользователя {message.from_user.id}")

        certificate_request = CertificateRequest(
            domain=data['domain'],
            inn=data['inn'],
            valid_from=data['valid_from'],
            valid_to=data['valid_to'],
            users_count=data['users_count'],
            created_by=message.from_user.id,
            created_by_username=message.from_user.username,
            created_by_full_name=message.from_user.full_name,
            request_email=data.get('request_email'),
            contacts=data.get('contacts')
        )

        logger.info(f"Запрос создан: {certificate_request}")

        # Создаем сертификат
        logger.info("Вызываем сервис создания сертификата")
        certificate, has_existing = certificate_service.create_certificate(certificate_request)
        logger.info(f"Сертификат создан успешно: {certificate.certificate_id}")

        # Форматируем информацию о созданном сертификате
        cert_info = certificate_service.format_certificate_info(certificate, detailed=True)
        logger.info(f"Форматированная информация: {cert_info}")

        success_message = f"✅ Сертификат успешно создан!\n\n{cert_info}"
        logger.info(f"Итоговое сообщение: {success_message}")

        await message.answer(
            success_message,
            reply_markup=get_main_menu_admin()
        )

        # Отправляем уведомление в группу
        try:
            # Проверяем, настроена ли группа для уведомлений
            if settings.notification_group and settings.notification_group != 0:
                # Получаем статус для красивого отображения
                status = certificate.status_info

                notification_text = (
                    f"🆕 Создан новый сертификат\n\n"
                    f"🆔 ID: {certificate.certificate_id}\n"
                    f"🌐 Домен: {certificate.domain}\n"
                    f"🏢 ИНН: {certificate.inn}\n"
                    f"📅 Период: {certificate.validity_period}\n"
                    f"👥 Пользователей: {certificate.users_count}\n"
                    f"{status['emoji']} Статус: {status['text']}\n"
                )

                if certificate.request_email:
                    notification_text += f"📧 Email для запросов: {certificate.request_email}\n"

                if certificate.contacts:
                    contacts_str = "\n".join(f"  • {c.get('name', '')} ({c.get('email', '')})" for c in certificate.contacts)
                    notification_text += f"👤 Контактные лица:\n{contacts_str}\n"

                notification_text += f"🔧 Создатель: {certificate.creator_display_name}"

                # Получаем бота из контекста
                bot = message.bot
                await bot.send_message(
                    chat_id=settings.notification_group,
                    text=notification_text
                )
                logger.info("Уведомление отправлено в группу")
            else:
                logger.info("Группа для уведомлений не настроена, пропускаем отправку")

        except Exception as e:
            logger.warning(f"Не удалось отправить уведомление в группу: {e}")

        # Отправляем email-уведомление (если настроено)
        try:
            from core.email_service import get_email_service
            email_service = get_email_service()
            if email_service.is_configured:
                email_service.send_certificate_notification(certificate.to_dict())
        except Exception as e:
            logger.warning(f"Не удалось отправить email-уведомление: {e}")

        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка создания сертификата: {e}", exc_info=True)

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
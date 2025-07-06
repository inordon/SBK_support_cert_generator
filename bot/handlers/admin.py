"""
Обработчики команд для администраторов.
"""

import logging
from datetime import datetime, date, timedelta
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from core.service import get_certificate_service
from core.models import CertificateRequest
from core.exceptions import *
from core.validators import PeriodValidator
from ..states import CreateCertificateStates
from ..keyboards import (
    get_main_menu_admin, get_period_presets_keyboard, get_users_count_presets_keyboard,
    get_confirmation_keyboard, get_duplicate_confirmation_keyboard, get_cancel_keyboard,
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

    await message.answer(
        "📝 Создание нового сертификата\n\n"
        "Введите доменное имя для сертификата.\n\n"
        "Поддерживаемые форматы:\n"
        "• example.com\n"
        "• sub.example.com\n"
        "• *.example.com\n"
        "• *.sub.example.com\n\n"
        "Домены могут содержать дефисы: my-site.com",
        reply_markup=get_cancel_keyboard()
    )

    await state.set_state(CreateCertificateStates.waiting_for_domain)


@router.message(CreateCertificateStates.waiting_for_domain)
async def process_domain_input(message: Message, state: FSMContext):
    """Обрабатывает ввод домена."""
    if message.text == ButtonTexts.CANCEL:
        await cancel_creation(message, state)
        return

    domain = message.text.strip().lower()

    # Валидируем домен
    errors = certificate_service.validate_certificate_data(
        domain=domain,
        inn="1234567890",  # Временные значения для валидации только домена
        valid_from=date.today(),
        valid_to=date.today() + timedelta(days=365),
        users_count=1
    )

    domain_errors = [error for error in errors if "домен" in error.lower()]

    if domain_errors:
        await message.answer(
            f"❌ Ошибка валидации домена:\n\n{domain_errors[0]}\n\n"
            "Попробуйте еще раз или нажмите 'Отменить':",
            reply_markup=get_cancel_keyboard()
        )
        return

    # Проверяем существующие сертификаты для домена
    try:
        from core.models import SearchRequest
        search_request = SearchRequest(domain=domain, active_only=True)
        existing_certificates = certificate_service.search_certificates(search_request)

        # Сохраняем данные в состоянии
        await state.update_data(domain=domain, has_existing=len(existing_certificates) > 0)

        if existing_certificates:
            certificates_list = certificate_service.format_certificates_list(existing_certificates)
            await message.answer(
                f"⚠️ Для домена {domain} уже существуют активные сертификаты:\n\n"
                f"{certificates_list}\n\n"
                "Продолжить создание нового сертификата?"
            )

        await message.answer(
            "Введите ИНН организации (10 или 12 цифр):",
            reply_markup=get_cancel_keyboard()
        )

        await state.set_state(CreateCertificateStates.waiting_for_inn)

    except Exception as e:
        logger.error(f"Ошибка при проверке существующих сертификатов: {e}")
        await message.answer(
            "❌ Произошла ошибка при проверке существующих сертификатов. "
            "Попробуйте еще раз.",
            reply_markup=get_cancel_keyboard()
        )


@router.message(CreateCertificateStates.waiting_for_inn)
async def process_inn_input(message: Message, state: FSMContext):
    """Обрабатывает ввод ИНН."""
    if message.text == ButtonTexts.CANCEL:
        await cancel_creation(message, state)
        return

    inn = message.text.strip()

    # Валидируем ИНН
    errors = certificate_service.validate_certificate_data(
        domain="example.com",  # Временное значение
        inn=inn,
        valid_from=date.today(),
        valid_to=date.today() + timedelta(days=365),
        users_count=1
    )

    inn_errors = [error for error in errors if "инн" in error.lower()]

    if inn_errors:
        await message.answer(
            f"❌ Ошибка валидации ИНН:\n\n{inn_errors[0]}\n\n"
            "Попробуйте еще раз или нажмите 'Отменить':",
            reply_markup=get_cancel_keyboard()
        )
        return

    # Сохраняем ИНН в состоянии
    await state.update_data(inn=inn)

    await message.answer(
        "📅 Выберите период действия сертификата:",
        reply_markup=get_period_presets_keyboard()
    )

    await state.set_state(CreateCertificateStates.waiting_for_period)


@router.message(CreateCertificateStates.waiting_for_period)
async def process_period_input(message: Message, state: FSMContext):
    """Обрабатывает ввод периода действия."""
    if message.text == ButtonTexts.CANCEL:
        await cancel_creation(message, state)
        return

    if message.text == ButtonTexts.BACK:
        await message.answer(
            "Введите ИНН организации (10 или 12 цифр):",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(CreateCertificateStates.waiting_for_inn)
        return

    # Проверяем, выбран ли предустановленный период
    months = ButtonTexts.get_period_months(message.text)

    if months > 0:
        # Рассчитываем даты
        valid_from = date.today()
        valid_to = valid_from + timedelta(days=months * 30)  # Приблизительно

        # Корректируем конечную дату на последний день месяца
        if valid_to.day != valid_from.day:
            next_month = valid_to.replace(day=1) + timedelta(days=32)
            valid_to = next_month.replace(day=1) - timedelta(days=1)

    elif message.text == ButtonTexts.PERIOD_MANUAL:
        await message.answer(
            "Введите период действия в формате: ДД.ММ.ГГГГ-ДД.ММ.ГГГГ\n\n"
            "Например: 01.01.2024-31.12.2024",
            reply_markup=get_cancel_keyboard()
        )
        return

    else:
        # Попытка парсинга ручного ввода
        try:
            period_validator = PeriodValidator()
            valid_from, valid_to = period_validator.parse_period_string(message.text)
        except Exception as e:
            await message.answer(
                f"❌ Неверный формат периода: {e}\n\n"
                "Используйте формат: ДД.ММ.ГГГГ-ДД.ММ.ГГГГ\n"
                "Или выберите готовый вариант:",
                reply_markup=get_period_presets_keyboard()
            )
            return

    # Валидируем период
    errors = certificate_service.validate_certificate_data(
        domain="example.com",  # Временные значения
        inn="1234567890",
        valid_from=valid_from,
        valid_to=valid_to,
        users_count=1
    )

    period_errors = [error for error in errors if any(word in error.lower()
                                                      for word in ["дата", "период", "год"])]

    if period_errors:
        await message.answer(
            f"❌ Ошибка валидации периода:\n\n{period_errors[0]}\n\n"
            "Выберите другой период:",
            reply_markup=get_period_presets_keyboard()
        )
        return

    # Сохраняем период в состоянии
    await state.update_data(valid_from=valid_from, valid_to=valid_to)

    await message.answer(
        "👥 Выберите количество пользователей:",
        reply_markup=get_users_count_presets_keyboard()
    )

    await state.set_state(CreateCertificateStates.waiting_for_users_count)


@router.message(CreateCertificateStates.waiting_for_users_count)
async def process_users_count_input(message: Message, state: FSMContext):
    """Обрабатывает ввод количества пользователей."""
    if message.text == ButtonTexts.CANCEL:
        await cancel_creation(message, state)
        return

    if message.text == ButtonTexts.BACK:
        await message.answer(
            "📅 Выберите период действия сертификата:",
            reply_markup=get_period_presets_keyboard()
        )
        await state.set_state(CreateCertificateStates.waiting_for_period)
        return

    # Проверяем, выбрано ли предустановленное значение
    users_count = ButtonTexts.extract_users_count(message.text)

    if users_count > 0:
        # Значение выбрано из предустановленных
        pass
    elif message.text == ButtonTexts.USERS_MANUAL:
        await message.answer(
            "Введите количество пользователей (от 1 до 1000):",
            reply_markup=get_cancel_keyboard()
        )
        return
    else:
        # Попытка парсинга ручного ввода
        try:
            users_count = int(message.text.strip())
        except ValueError:
            await message.answer(
                "❌ Неверный формат числа. Введите целое число от 1 до 1000:",
                reply_markup=get_users_count_presets_keyboard()
            )
            return

    # Валидируем количество пользователей
    if not (1 <= users_count <= 1000):
        await message.answer(
            "❌ Количество пользователей должно быть от 1 до 1000:",
            reply_markup=get_users_count_presets_keyboard()
        )
        return

    # Сохраняем количество пользователей
    await state.update_data(users_count=users_count)

    # Получаем все данные для подтверждения
    data = await state.get_data()

    # Форматируем информацию для подтверждения
    period_str = f"{data['valid_from'].strftime('%d.%m.%Y')}-{data['valid_to'].strftime('%d.%m.%Y')}"

    confirmation_text = (
        "✅ Подтвердите создание сертификата:\n\n"
        f"🌐 Домен: {data['domain']}\n"
        f"🏢 ИНН: {data['inn']}\n"
        f"📅 Период: {period_str}\n"
        f"👥 Пользователей: {users_count}\n"
    )

    if data.get('has_existing', False):
        confirmation_text += "\n⚠️ Для этого домена уже есть активные сертификаты!"

    await message.answer(
        confirmation_text,
        reply_markup=get_confirmation_keyboard()
    )

    await state.set_state(CreateCertificateStates.waiting_for_confirmation)


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
            reply_markup=get_main_menu_admin()
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
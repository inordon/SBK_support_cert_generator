"""
Обработчики команд для редактирования сертификатов - исправленная версия.
"""

import logging
import re
from datetime import datetime, date
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from core.service import get_certificate_service
from core.models import EditCertificateDatesRequest
from core.exceptions import *
from ..states import EditCertificateStates
from ..keyboards import (
    get_main_menu_admin, get_edit_confirmation_keyboard, get_cancel_keyboard,
    ButtonTexts
)
from ..middleware import admin_required

logger = logging.getLogger(__name__)
router = Router()
router.message.middleware(admin_required())

# Получаем сервисы
certificate_service = get_certificate_service()


@router.message(F.text == ButtonTexts.EDIT_CERTIFICATE)
async def start_edit_certificate(message: Message, state: FSMContext):
    """Начинает процесс редактирования сертификата."""
    await state.clear()

    instruction_text = """✏️ Редактирование сертификата

Введите ID сертификата, который хотите отредактировать.

Формат ID: XXXXX-XXXXX-XXXXX-XXXXX
Например: A7K9M-X3P2R-Q8W1E-RT0524

После ввода ID вы сможете изменить даты действия сертификата."""

    await message.answer(
        instruction_text,
        reply_markup=get_cancel_keyboard()
    )

    await state.set_state(EditCertificateStates.waiting_for_certificate_id)


@router.message(EditCertificateStates.waiting_for_certificate_id)
async def process_certificate_id_for_edit(message: Message, state: FSMContext):
    """Обрабатывает ввод ID сертификата для редактирования."""
    if message.text == ButtonTexts.CANCEL:
        await cancel_edit(message, state)
        return

    certificate_id = message.text.strip().upper()

    try:
        # Проверяем существование сертификата
        certificate = certificate_service.verify_certificate(certificate_id, message.from_user.id)

        if certificate is None:
            await message.answer(
                f"❌ Сертификат с ID {certificate_id} не найден.\n\n"
                "Проверьте правильность ввода ID и повторите попытку:",
                reply_markup=get_cancel_keyboard()
            )
            return

        # Сохраняем данные сертификата в состоянии
        await state.update_data(
            certificate_id=certificate_id,
            original_certificate=certificate
        )

        # Показываем текущую информацию о сертификате
        cert_info = certificate_service.format_certificate_info(certificate, detailed=True)

        dates_instruction = """
📅 Введите новые даты действия сертификата в формате:

ДД.ММ.ГГГГ-ДД.ММ.ГГГГ

Примеры:
• 01.01.2025-31.12.2025
• 15.06.2024-14.06.2026

Или введите "отменить" для возврата в главное меню."""

        # Отправляем БЕЗ parse_mode, чтобы избежать проблем с Markdown
        await message.answer(
            f"📋 Найден сертификат:\n\n{cert_info}\n\n{dates_instruction}",
            reply_markup=get_cancel_keyboard()
        )

        await state.set_state(EditCertificateStates.waiting_for_new_dates)

    except ValidationError as e:
        await message.answer(
            f"❌ Ошибка валидации: {e}\n\n"
            "Проверьте формат ID и повторите попытку:",
            reply_markup=get_cancel_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка поиска сертификата {certificate_id}: {e}")
        await message.answer(
            "❌ Произошла ошибка при поиске сертификата. Попробуйте позже.",
            reply_markup=get_cancel_keyboard()
        )


@router.message(EditCertificateStates.waiting_for_new_dates)
async def process_new_dates(message: Message, state: FSMContext):
    """Обрабатывает ввод новых дат действия сертификата."""
    if message.text == ButtonTexts.CANCEL:
        await cancel_edit(message, state)
        return

    try:
        # Парсим новые даты
        new_valid_from, new_valid_to = parse_dates_string(message.text.strip())

        # Получаем данные из состояния
        state_data = await state.get_data()
        certificate_id = state_data['certificate_id']
        original_certificate = state_data['original_certificate']

        # Валидируем новые даты
        errors = validate_new_dates(new_valid_from, new_valid_to)
        if errors:
            error_text = "❌ Ошибки валидации:\n\n" + "\n".join(f"• {error}" for error in errors)
            error_text += "\n\nПопробуйте еще раз или нажмите 'Отменить':"

            await message.answer(
                error_text,
                reply_markup=get_cancel_keyboard()
            )
            return

        # Сохраняем новые даты в состоянии
        await state.update_data(
            new_valid_from=new_valid_from,
            new_valid_to=new_valid_to
        )

        # Показываем сравнение для подтверждения
        comparison_text = format_dates_comparison(
            original_certificate.valid_from,
            original_certificate.valid_to,
            new_valid_from,
            new_valid_to
        )

        confirmation_text = f"""📝 Подтвердите изменение дат сертификата:

🆔 ID: {certificate_id}
🌐 Домен: {original_certificate.domain}

{comparison_text}

⚠️ Внимание: После подтверждения изменения нельзя будет отменить!"""

        # Отправляем БЕЗ parse_mode
        await message.answer(
            confirmation_text,
            reply_markup=get_edit_confirmation_keyboard()
        )

        await state.set_state(EditCertificateStates.waiting_for_edit_confirmation)

    except ValueError as e:
        await message.answer(
            f"❌ Ошибка формата дат: {e}\n\n"
            "Используйте формат: ДД.ММ.ГГГГ-ДД.ММ.ГГГГ\n"
            "Например: 01.01.2025-31.12.2025",
            reply_markup=get_cancel_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка обработки новых дат: {e}")
        await message.answer(
            "❌ Произошла неожиданная ошибка при обработке дат.\n\n"
            "Попробуйте еще раз или нажмите 'Отменить':",
            reply_markup=get_cancel_keyboard()
        )


@router.message(EditCertificateStates.waiting_for_edit_confirmation)
async def process_edit_confirmation(message: Message, state: FSMContext):
    """Обрабатывает подтверждение редактирования сертификата."""
    if message.text == ButtonTexts.CANCEL_EDIT:
        await cancel_edit(message, state)
        return

    if message.text != ButtonTexts.CONFIRM_EDIT:
        await message.answer(
            "Выберите действие:",
            reply_markup=get_edit_confirmation_keyboard()
        )
        return

    # Получаем данные из состояния
    state_data = await state.get_data()

    try:
        # Создаем запрос на редактирование
        edit_request = EditCertificateDatesRequest(
            certificate_id=state_data['certificate_id'],
            new_valid_from=state_data['new_valid_from'],
            new_valid_to=state_data['new_valid_to'],
            edited_by=message.from_user.id,
            edit_reason=f"Отредактировано через бота пользователем {message.from_user.full_name or message.from_user.username or message.from_user.id}"
        )

        # Выполняем редактирование
        updated_certificate = certificate_service.edit_certificate_dates(edit_request)

        # Форматируем информацию об обновленном сертификате
        cert_info = certificate_service.format_certificate_info(updated_certificate, detailed=True)

        success_message = f"✅ Даты сертификата успешно изменены!\n\n{cert_info}"

        await message.answer(
            success_message,
            reply_markup=get_main_menu_admin()
        )

        # Отправляем уведомление в группу
        try:
            from config.settings import get_settings
            settings = get_settings()

            if settings.notification_group and settings.notification_group != 0:
                notification_text = (
                    f"📝 Изменены даты сертификата\n\n"
                    f"🆔 ID: {updated_certificate.certificate_id}\n"
                    f"🌐 Домен: {updated_certificate.domain}\n"
                    f"📅 Новый период: {updated_certificate.validity_period}\n"
                    f"👤 Изменено: {updated_certificate.creator_display_name}"
                )

                bot = message.bot
                await bot.send_message(
                    chat_id=settings.notification_group,
                    text=notification_text
                )
                logger.info("Уведомление об изменении отправлено в группу")
        except Exception as e:
            logger.warning(f"Не удалось отправить уведомление в группу: {e}")

        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка редактирования сертификата: {e}", exc_info=True)

        if isinstance(e, CertificateNotFoundError):
            error_text = f"❌ Сертификат не найден: {e}"
        elif isinstance(e, ValidationError):
            error_text = f"❌ Ошибка валидации: {e}"
        else:
            error_text = "❌ Произошла неожиданная ошибка при редактировании сертификата."

        await message.answer(
            error_text + "\n\nПопробуйте еще раз.",
            reply_markup=get_main_menu_admin()
        )
        await state.clear()


async def cancel_edit(message: Message, state: FSMContext):
    """Отменяет процесс редактирования сертификата."""
    await state.clear()
    await message.answer(
        "❌ Редактирование сертификата отменено.",
        reply_markup=get_main_menu_admin()
    )


def parse_dates_string(dates_string: str) -> tuple[date, date]:
    """
    Парсит строку с датами в формате DD.MM.YYYY-DD.MM.YYYY.

    Args:
        dates_string: Строка с датами

    Returns:
        tuple[date, date]: Кортеж дат начала и окончания

    Raises:
        ValueError: При некорректном формате
    """
    if '-' not in dates_string:
        raise ValueError("Неверный формат. Используйте: ДД.ММ.ГГГГ-ДД.ММ.ГГГГ")

    date_parts = dates_string.split('-')
    if len(date_parts) != 2:
        raise ValueError("Неверный формат. Используйте: ДД.ММ.ГГГГ-ДД.ММ.ГГГГ")

    try:
        valid_from = datetime.strptime(date_parts[0].strip(), "%d.%m.%Y").date()
        valid_to = datetime.strptime(date_parts[1].strip(), "%d.%m.%Y").date()
        return valid_from, valid_to
    except ValueError as e:
        raise ValueError(f"Неверный формат даты: {e}")


def validate_new_dates(valid_from: date, valid_to: date) -> list[str]:
    """
    Валидирует новые даты действия сертификата.

    Args:
        valid_from: Дата начала действия
        valid_to: Дата окончания действия

    Returns:
        list[str]: Список ошибок валидации
    """
    errors = []

    # Проверяем, что дата окончания позже даты начала
    if valid_to <= valid_from:
        errors.append("Дата окончания должна быть позже даты начала")

    # Проверяем, что период не превышает 5 лет
    years_diff = (valid_to - valid_from).days / 365.25
    if years_diff > 5:
        errors.append("Период действия не может превышать 5 лет")

    return errors


def format_dates_comparison(old_from: date, old_to: date, new_from: date, new_to: date) -> str:
    """
    Форматирует сравнение старых и новых дат БЕЗ Markdown разметки.

    Args:
        old_from: Старая дата начала
        old_to: Старая дата окончания
        new_from: Новая дата начала
        new_to: Новая дата окончания

    Returns:
        str: Отформатированное сравнение
    """
    old_period = f"{old_from.strftime('%d.%m.%Y')}-{old_to.strftime('%d.%m.%Y')}"
    new_period = f"{new_from.strftime('%d.%m.%Y')}-{new_to.strftime('%d.%m.%Y')}"

    return f"""📅 Изменение периода действия:

❌ Было: {old_period}
✅ Будет: {new_period}

📊 Детали изменений:
• Начало: {old_from.strftime('%d.%m.%Y')} → {new_from.strftime('%d.%m.%Y')}
• Окончание: {old_to.strftime('%d.%m.%Y')} → {new_to.strftime('%d.%m.%Y')}"""
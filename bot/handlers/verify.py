"""
Обработчики команд для проверки и поиска сертификатов - исправленная версия.
"""

import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from core.service import get_certificate_service
from core.models import SearchRequest
from core.exceptions import *
from ..states import VerifyCertificateStates, SearchStates
from ..keyboards import (
    get_main_menu_admin, get_main_menu_verify, get_search_type_keyboard,
    get_cancel_keyboard, get_back_keyboard, ButtonTexts
)
from ..middleware import verify_required
from config.settings import get_settings

logger = logging.getLogger(__name__)
router = Router()
router.message.middleware(verify_required())

# Получаем сервисы
certificate_service = get_certificate_service()
settings = get_settings()


@router.message(F.text == ButtonTexts.VERIFY_CERTIFICATE)
async def start_verify_certificate(message: Message, state: FSMContext, user_permissions: dict):
    """Начинает процесс проверки сертификата."""
    await state.clear()

    await message.answer(
        "🔍 Проверка сертификата\n\n"
        "Введите ID сертификата для проверки.\n\n"
        "Формат ID: XXXXX-XXXXX-XXXXX-XXXXX\n"
        "Например: A7K9M-X3P2R-Q8W1E-RT0524",
        reply_markup=get_cancel_keyboard()
    )

    await state.set_state(VerifyCertificateStates.waiting_for_certificate_id)


@router.message(VerifyCertificateStates.waiting_for_certificate_id)
async def process_certificate_verification(message: Message, state: FSMContext, user_permissions: dict):
    """Обрабатывает проверку сертификата по ID."""
    if message.text == ButtonTexts.CANCEL:
        await cancel_verification(message, state, user_permissions)
        return

    certificate_id = message.text.strip().upper()

    try:
        # Проверяем сертификат
        certificate = certificate_service.verify_certificate(certificate_id, message.from_user.id)

        if certificate is None:
            await message.answer(
                f"❌ Сертификат с ID {certificate_id} не найден.\n\n"
                "Проверьте правильность ввода ID и повторите попытку:",
                reply_markup=get_cancel_keyboard()
            )
            return

        # Форматируем подробную информацию о сертификате
        cert_info = certificate_service.format_certificate_info(certificate, detailed=True)

        # Добавляем дополнительную информацию о статусе
        status_info = []

        if not certificate.is_active:
            status_info.append("⚠️ Сертификат был деактивирован")
        elif certificate.is_expired:
            status_info.append("⚠️ Срок действия сертификата истек")
        elif certificate.days_left <= 7:
            status_info.append(f"⚠️ Сертификат истекает в ближайшие {certificate.days_left} дней")
        elif certificate.days_left <= 30:
            status_info.append(f"⚠️ Сертификат истекает через {certificate.days_left} дней")
        else:
            status_info.append("✅ Сертификат действителен")

        response_text = f"🔍 Результат проверки:\n\n{cert_info}"

        if status_info:
            response_text += f"\n\n{' '.join(status_info)}"

        # Выбираем подходящую клавиатуру
        keyboard = get_main_menu_admin() if user_permissions['is_admin'] else get_main_menu_verify()

        await message.answer(
            response_text,
            reply_markup=keyboard
        )

        await state.clear()

    except ValidationError as e:
        await message.answer(
            f"❌ Ошибка валидации: {e}\n\n"
            "Проверьте формат ID и повторите попытку:",
            reply_markup=get_cancel_keyboard()
        )

    except Exception as e:
        logger.error(f"Ошибка проверки сертификата {certificate_id}: {e}")
        await message.answer(
            "❌ Произошла ошибка при проверке сертификата. Попробуйте позже.",
            reply_markup=get_cancel_keyboard()
        )


@router.message(F.text == ButtonTexts.SEARCH)
async def start_search(message: Message, state: FSMContext):
    """Начинает процесс поиска сертификатов."""
    await state.clear()

    await message.answer(
        "🔎 Поиск сертификатов\n\n"
        "Выберите тип поиска:",
        reply_markup=get_search_type_keyboard()
    )

    await state.set_state(SearchStates.waiting_for_search_type)


@router.message(SearchStates.waiting_for_search_type)
async def process_search_type(message: Message, state: FSMContext):
    """Обрабатывает выбор типа поиска."""
    if message.text == ButtonTexts.BACK:
        await cancel_search(message, state)
        return

    if message.text == ButtonTexts.SEARCH_BY_DOMAIN:
        await message.answer(
            "🌐 Поиск по домену\n\n"
            "Введите доменное имя для поиска.\n"
            "Можно ввести как полный домен (example.com), "
            "так и его часть (example) для поиска всех подходящих доменов:",
            reply_markup=get_back_keyboard()
        )
        await state.set_state(SearchStates.waiting_for_domain_search)

    elif message.text == ButtonTexts.SEARCH_BY_INN:
        await message.answer(
            "🏢 Поиск по ИНН\n\n"
            "Введите ИНН организации (10 или 12 цифр):",
            reply_markup=get_back_keyboard()
        )
        await state.set_state(SearchStates.waiting_for_inn_search)

    else:
        await message.answer(
            "Выберите тип поиска:",
            reply_markup=get_search_type_keyboard()
        )


@router.message(SearchStates.waiting_for_domain_search)
async def process_domain_search(message: Message, state: FSMContext, user_permissions: dict):
    """Обрабатывает поиск по домену."""
    if message.text == ButtonTexts.BACK:
        await message.answer(
            "🔎 Поиск сертификатов\n\n"
            "Выберите тип поиска:",
            reply_markup=get_search_type_keyboard()
        )
        await state.set_state(SearchStates.waiting_for_search_type)
        return

    domain_query = message.text.strip().lower()

    try:
        # Создаем запрос поиска
        search_request = SearchRequest(domain=domain_query, active_only=True)
        certificates = certificate_service.search_certificates(search_request)

        if not certificates:
            await message.answer(
                f"📝 Сертификаты для домена '{domain_query}' не найдены.",
                reply_markup=get_main_menu_admin() if user_permissions['is_admin'] else get_main_menu_verify()
            )
        else:
            # Форматируем результаты поиска
            result_text = f"🔎 Найдено сертификатов для '{domain_query}': {len(certificates)}\n\n"

            # Показываем детальную информацию для первых 3 сертификатов
            for i, certificate in enumerate(certificates[:3], 1):
                cert_info = certificate_service.format_certificate_info(certificate)
                result_text += f"{i}. {cert_info}\n\n"

            # Если сертификатов больше 3, показываем краткий список остальных
            if len(certificates) > 3:
                remaining_list = certificate_service.format_certificates_list(certificates[3:])
                result_text += f"Остальные сертификаты:\n{remaining_list}"

            keyboard = get_main_menu_admin() if user_permissions['is_admin'] else get_main_menu_verify()
            await message.answer(result_text, reply_markup=keyboard)

        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка поиска по домену {domain_query}: {e}")
        await message.answer(
            "❌ Произошла ошибка при поиске. Попробуйте позже.",
            reply_markup=get_back_keyboard()
        )


@router.message(SearchStates.waiting_for_inn_search)
async def process_inn_search(message: Message, state: FSMContext, user_permissions: dict):
    """Обрабатывает поиск по ИНН."""
    if message.text == ButtonTexts.BACK:
        await message.answer(
            "🔎 Поиск сертификатов\n\n"
            "Выберите тип поиска:",
            reply_markup=get_search_type_keyboard()
        )
        await state.set_state(SearchStates.waiting_for_search_type)
        return

    inn_query = message.text.strip()

    # Базовая валидация ИНН (только цифры)
    if not inn_query.isdigit() or len(inn_query) not in [10, 12]:
        await message.answer(
            "❌ Неверный формат ИНН. Введите 10 или 12 цифр:",
            reply_markup=get_back_keyboard()
        )
        return

    try:
        # Создаем запрос поиска
        search_request = SearchRequest(inn=inn_query, active_only=True)
        certificates = certificate_service.search_certificates(search_request)

        if not certificates:
            await message.answer(
                f"📝 Сертификаты для ИНН '{inn_query}' не найдены.",
                reply_markup=get_main_menu_admin() if user_permissions['is_admin'] else get_main_menu_verify()
            )
        else:
            # Форматируем результаты поиска
            result_text = f"🔎 Найдено сертификатов для ИНН '{inn_query}': {len(certificates)}\n\n"

            # Показываем детальную информацию для первых 3 сертификатов
            for i, certificate in enumerate(certificates[:3], 1):
                cert_info = certificate_service.format_certificate_info(certificate)
                result_text += f"{i}. {cert_info}\n\n"

            # Если сертификатов больше 3, показываем краткий список остальных
            if len(certificates) > 3:
                remaining_list = certificate_service.format_certificates_list(certificates[3:])
                result_text += f"Остальные сертификаты:\n{remaining_list}"

            keyboard = get_main_menu_admin() if user_permissions['is_admin'] else get_main_menu_verify()
            await message.answer(result_text, reply_markup=keyboard)

        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка поиска по ИНН {inn_query}: {e}")
        await message.answer(
            "❌ Произошла ошибка при поиске. Попробуйте позже.",
            reply_markup=get_back_keyboard()
        )


async def cancel_verification(message: Message, state: FSMContext, user_permissions: dict):
    """Отменяет процесс проверки сертификата."""
    await state.clear()
    keyboard = get_main_menu_admin() if user_permissions['is_admin'] else get_main_menu_verify()
    await message.answer(
        "❌ Проверка сертификата отменена.",
        reply_markup=keyboard
    )


async def cancel_search(message: Message, state: FSMContext):
    """Отменяет процесс поиска сертификатов."""
    await state.clear()

    # Определяем права пользователя для выбора клавиатуры
    is_admin = settings.is_admin(message.from_user.id)
    keyboard = get_main_menu_admin() if is_admin else get_main_menu_verify()

    await message.answer(
        "❌ Поиск отменен.",
        reply_markup=keyboard
    )
"""
Обработчики команд Telegram бота
"""
import logging
from typing import Dict, Any, Optional

from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core.generator import CertificateGenerator
from core.storage import DatabaseStorage, FileStorage, StorageError
from core.validators import ValidationError


# Состояния для генерации сертификата
class GenerateStates(StatesGroup):
    waiting_for_domain = State()
    waiting_for_inn = State()
    waiting_for_period = State()
    waiting_for_users = State()
    confirmation = State()


class CertificateHandlers:
    """Класс обработчиков команд бота"""

    def __init__(
            self,
            db_storage: DatabaseStorage,
            file_storage: FileStorage,
            allowed_users: set,
            verify_users: set,
            notification_chat: Optional[int] = None
    ):
        self.db_storage = db_storage
        self.file_storage = file_storage
        self.generator = CertificateGenerator()
        self.allowed_users = allowed_users
        self.verify_users = verify_users
        self.notification_chat = notification_chat
        self.logger = logging.getLogger(__name__)

        # Создание роутера
        self.router = Router()
        self._setup_handlers()

    def _check_permissions(self, user_id: int, action: str = "generate") -> bool:
        """Проверка прав пользователя"""
        if action == "generate":
            return user_id in self.allowed_users
        elif action == "verify":
            return user_id in self.verify_users or user_id in self.allowed_users
        return False

    def _setup_handlers(self):
        """Настройка обработчиков"""

        @self.router.message(Command("start"))
        async def cmd_start(message: Message):
            """Обработчик команды /start"""
            welcome_text = (
                "🔐 Добро пожаловать в систему управления сертификатами!\n\n"
                "Доступные команды:\n"
                "• /generate - Генерация нового сертификата\n"
                "• /verify - Проверка существующего сертификата\n"
                "• /help - Справка по командам\n"
                "• /cancel - Отмена текущей операции\n\n"
                "Для начала работы выберите нужную команду."
            )

            keyboard = InlineKeyboardBuilder()

            if self._check_permissions(message.from_user.id, "generate"):
                keyboard.add(InlineKeyboardButton(
                    text="🆕 Создать сертификат",
                    callback_data="generate"
                ))

            if self._check_permissions(message.from_user.id, "verify"):
                keyboard.add(InlineKeyboardButton(
                    text="🔍 Проверить сертификат",
                    callback_data="verify"
                ))

            keyboard.adjust(1)

            await message.answer(welcome_text, reply_markup=keyboard.as_markup())

        @self.router.message(Command("help"))
        async def cmd_help(message: Message):
            """Обработчик команды /help"""
            help_text = (
                "📖 Справка по командам:\n\n"
                "🆕 /generate - Генерация нового сертификата\n"
                "   Запускает пошаговый процесс создания сертификата\n\n"
                "🔍 /verify - Проверка сертификата\n"
                "   Введите ID сертификата для проверки его статуса\n\n"
                "❌ /cancel - Отмена операции\n"
                "   Прерывает текущий процесс генерации\n\n"
                "📋 Формат данных:\n"
                "• Домен: example.com или *.example.com\n"
                "• ИНН: 10 или 12 цифр\n"
                "• Период: ДД.ММ.ГГГГ-ДД.ММ.ГГГГ\n"
                "• Пользователи: число от 1 до 1000\n\n"
                "Пример ID сертификата: ABCD1-XYZ12-QWRT5-WX0124"
            )
            await message.answer(help_text)

        @self.router.message(Command("cancel"))
        async def cmd_cancel(message: Message, state: FSMContext):
            """Обработчик команды /cancel"""
            await state.clear()
            await message.answer(
                "❌ Операция отменена.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="🏠 В главное меню", callback_data="start")
                ]])
            )

        @self.router.message(Command("generate"))
        async def cmd_generate(message: Message, state: FSMContext):
            """Обработчик команды /generate"""
            if not self._check_permissions(message.from_user.id, "generate"):
                await message.answer("❌ У вас нет прав для генерации сертификатов.")
                return

            await message.answer(
                "🆕 Начинаем процесс создания сертификата.\n\n"
                "1️⃣ Введите доменное имя:\n"
                "Например: example.com или *.example.com"
            )
            await state.set_state(GenerateStates.waiting_for_domain)

        @self.router.message(Command("verify"))
        async def cmd_verify(message: Message):
            """Обработчик команды /verify"""
            if not self._check_permissions(message.from_user.id, "verify"):
                await message.answer("❌ У вас нет прав для проверки сертификатов.")
                return

            await message.answer(
                "🔍 Введите ID сертификата для проверки:\n"
                "Формат: XXXXX-XXXXX-XXXXX-XXXXX\n"
                "Например: ABCD1-XYZ12-QWRT5-WX0124"
            )

        # Обработчики callback кнопок
        @self.router.callback_query(F.data == "generate")
        async def callback_generate(callback, state: FSMContext):
            """Callback обработчик кнопки генерации"""
            await callback.message.delete()
            await cmd_generate(callback.message, state)
            await callback.answer()

        @self.router.callback_query(F.data == "verify")
        async def callback_verify(callback):
            """Callback обработчик кнопки проверки"""
            await callback.message.delete()
            await cmd_verify(callback.message)
            await callback.answer()

        @self.router.callback_query(F.data == "start")
        async def callback_start(callback):
            """Callback обработчик кнопки главного меню"""
            await callback.message.delete()
            await cmd_start(callback.message)
            await callback.answer()

        # Обработчики состояний генерации
        @self.router.message(StateFilter(GenerateStates.waiting_for_domain))
        async def process_domain(message: Message, state: FSMContext):
            """Обработка ввода домена"""
            domain = message.text.strip()

            try:
                self.generator.validators.validate_domain(domain)
                await state.update_data(domain=domain)

                await message.answer(
                    f"✅ Домен: {domain}\n\n"
                    "2️⃣ Введите ИНН организации:\n"
                    "10 или 12 цифр"
                )
                await state.set_state(GenerateStates.waiting_for_inn)

            except ValidationError as e:
                await message.answer(f"❌ Ошибка: {e}\n\nПопробуйте еще раз:")

        @self.router.message(StateFilter(GenerateStates.waiting_for_inn))
        async def process_inn(message: Message, state: FSMContext):
            """Обработка ввода ИНН"""
            inn = message.text.strip()

            try:
                self.generator.validators.validate_inn(inn)
                await state.update_data(inn=inn)

                await message.answer(
                    f"✅ ИНН: {inn}\n\n"
                    "3️⃣ Введите период действия:\n"
                    "Формат: ДД.ММ.ГГГГ-ДД.ММ.ГГГГ\n"
                    "Например: 01.01.2024-31.12.2024"
                )
                await state.set_state(GenerateStates.waiting_for_period)

            except ValidationError as e:
                await message.answer(f"❌ Ошибка: {e}\n\nПопробуйте еще раз:")

        @self.router.message(StateFilter(GenerateStates.waiting_for_period))
        async def process_period(message: Message, state: FSMContext):
            """Обработка ввода периода"""
            period = message.text.strip()

            try:
                valid_from, valid_to = self.generator.validators.validate_period(period)
                await state.update_data(period=period, valid_from=valid_from, valid_to=valid_to)

                await message.answer(
                    f"✅ Период: {period}\n\n"
                    "4️⃣ Введите количество пользователей:\n"
                    "Число от 1 до 1000"
                )
                await state.set_state(GenerateStates.waiting_for_users)

            except ValidationError as e:
                await message.answer(f"❌ Ошибка: {e}\n\nПопробуйте еще раз:")

        @self.router.message(StateFilter(GenerateStates.waiting_for_users))
        async def process_users(message: Message, state: FSMContext):
            """Обработка ввода количества пользователей"""
            try:
                users_count = int(message.text.strip())
                self.generator.validators.validate_users_count(users_count)
                await state.update_data(users_count=users_count)

                # Получение всех данных для подтверждения
                data = await state.get_data()

                confirmation_text = (
                    "📋 Проверьте данные для создания сертификата:\n\n"
                    f"🌐 Домен: {data['domain']}\n"
                    f"🏢 ИНН: {data['inn']}\n"
                    f"📅 Период: {data['period']}\n"
                    f"👥 Пользователи: {users_count}\n\n"
                    "Все данные корректны?"
                )

                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="✅ Создать", callback_data="confirm_generate"),
                        InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_generate")
                    ]
                ])

                await message.answer(confirmation_text, reply_markup=keyboard)
                await state.set_state(GenerateStates.confirmation)

            except (ValueError, ValidationError) as e:
                await message.answer(f"❌ Ошибка: {e}\n\nПопробуйте еще раз:")

        @self.router.callback_query(F.data == "confirm_generate", StateFilter(GenerateStates.confirmation))
        async def confirm_generate(callback, state: FSMContext):
            """Подтверждение создания сертификата"""
            data = await state.get_data()

            try:
                # Проверка дубликатов
                existing = await self.db_storage.find_certificates_by_domain(data['domain'])
                active_certs = [cert for cert in existing if cert.is_active]

                if active_certs:
                    await callback.message.edit_text(
                        f"❌ Активный сертификат для домена {data['domain']} уже существует:\n"
                        f"ID: {active_certs[0].certificate_id}\n\n"
                        "Деактивируйте существующий сертификат перед созданием нового.",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                            InlineKeyboardButton(text="🏠 В главное меню", callback_data="start")
                        ]])
                    )
                    await state.clear()
                    await callback.answer()
                    return

                # Генерация сертификата
                certificate = self.generator.generate_certificate(
                    domain=data['domain'],
                    inn=data['inn'],
                    period=data['period'],
                    users_count=data['users_count'],
                    created_by=callback.from_user.id
                )

                # Сохранение в БД
                cert_uuid = await self.db_storage.save_certificate(certificate)
                certificate.id = cert_uuid

                # Сохранение в файл
                file_path = self.file_storage.save_certificate(certificate)

                # Успешное создание
                success_text = (
                    "✅ Сертификат успешно создан!\n\n"
                    f"🆔 ID: `{certificate.certificate_id}`\n"
                    f"🌐 Домен: {certificate.domain}\n"
                    f"🏢 ИНН: {certificate.inn}\n"
                    f"📅 Период: {data['period']}\n"
                    f"👥 Пользователи: {certificate.users_count}\n"
                    f"📅 Создан: {certificate.created_at.strftime('%d.%m.%Y %H:%M')}"
                )

                await callback.message.edit_text(
                    success_text,
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="🏠 В главное меню", callback_data="start")
                    ]])
                )

                # Уведомление в группу
                if self.notification_chat:
                    notification_text = (
                        "🆕 Создан новый сертификат\n\n"
                        f"ID: {certificate.certificate_id}\n"
                        f"Домен: {certificate.domain}\n"
                        f"Создатель: {callback.from_user.full_name} (@{callback.from_user.username})"
                    )
                    try:
                        await callback.bot.send_message(self.notification_chat, notification_text)
                    except Exception as e:
                        self.logger.error(f"Ошибка отправки уведомления: {e}")

                # Логирование
                self.logger.info(
                    f"Создан сертификат {certificate.certificate_id} "
                    f"пользователем {callback.from_user.id} ({callback.from_user.username})"
                )

                await state.clear()
                await callback.answer("Сертификат создан!")

            except (ValidationError, StorageError) as e:
                await callback.message.edit_text(
                    f"❌ Ошибка создания сертификата: {e}",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="🏠 В главное меню", callback_data="start")
                    ]])
                )
                await state.clear()
                await callback.answer()

            except Exception as e:
                self.logger.error(f"Неожиданная ошибка при создании сертификата: {e}")
                await callback.message.edit_text(
                    "❌ Произошла внутренняя ошибка. Попробуйте позже.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="🏠 В главное меню", callback_data="start")
                    ]])
                )
                await state.clear()
                await callback.answer()

        @self.router.callback_query(F.data == "cancel_generate")
        async def cancel_generate(callback, state: FSMContext):
            """Отмена создания сертификата"""
            await state.clear()
            await callback.message.edit_text(
                "❌ Создание сертификата отменено.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="🏠 В главное меню", callback_data="start")
                ]])
            )
            await callback.answer()

        # Обработчик проверки сертификата (только для пользователей с правами проверки)
        @self.router.message(F.text.regexp(r'^[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}$'))
                                           async def verify_certificate_handler(message: Message):
            """Обработчик проверки сертификата по ID"""
            if not self._check_permissions(message.from_user.id, "verify"):
                await message.answer("❌ У вас нет прав для проверки сертификатов.")
                return

            certificate_id = message.text.strip().upper()

            try:
                # Проверка формата
                if not self.generator.verify_certificate_id_format(certificate_id):
                    await message.answer(
                        f"❌ Неверный формат ID сертификата: {certificate_id}\n"
                        "Формат должен быть: XXXXX-XXXXX-XXXXX-XXXXX"
                    )
                    return

                # Поиск сертификата в БД
                certificate = await self.db_storage.get_certificate(certificate_id)

                if not certificate:
                    # Поиск в файлах (резервный способ)
                    certificate = self.file_storage.load_certificate(certificate_id)

                if not certificate:
                    await message.answer(
                        f"❌ Сертификат {certificate_id} не найден в системе.",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                            InlineKeyboardButton(text="🏠 В главное меню", callback_data="start")
                        ]])
                    )
                    return

                # Проверка статуса сертификата
                from datetime import datetime
                now = datetime.now()

                status_icon = "✅"
                status_text = "ДЕЙСТВИТЕЛЕН"

                if not getattr(certificate, 'is_active', True):
                    status_icon = "❌"
                    status_text = "ДЕАКТИВИРОВАН"
                elif now < certificate.valid_from:
                    status_icon = "⏳"
                    status_text = "ЕЩЕ НЕ ДЕЙСТВУЕТ"
                elif now > certificate.valid_to:
                    status_icon = "❌"
                    status_text = "ИСТЕК"

                # Формирование ответа
                verify_text = (
                    f"🔍 Результат проверки сертификата:\n\n"
                    f"🆔 ID: `{certificate.certificate_id}`\n"
                    f"🌐 Домен: {certificate.domain}\n"
                    f"🏢 ИНН: {certificate.inn}\n"
                    f"📅 Период: {certificate.valid_from.strftime('%d.%m.%Y')}-{certificate.valid_to.strftime('%d.%m.%Y')}\n"
                    f"👥 Пользователи: {certificate.users_count}\n"
                    f"📅 Создан: {certificate.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                    f"📊 Статус: {status_icon} {status_text}"
                )

                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="🔍 Проверить другой", callback_data="verify"),
                        InlineKeyboardButton(text="🏠 В главное меню", callback_data="start")
                    ]
                ])

                await message.answer(verify_text, parse_mode="Markdown", reply_markup=keyboard)

                # Логирование
                self.logger.info(
                    f"Проверен сертификат {certificate_id} "
                    f"пользователем {message.from_user.id} ({message.from_user.username})"
                )

            except Exception as e:
                self.logger.error(f"Ошибка проверки сертификата {certificate_id}: {e}")
                await message.answer(
                    "❌ Произошла ошибка при проверке сертификата. Попробуйте позже.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="🏠 В главное меню", callback_data="start")
                    ]])
                )

        # Обработчик неизвестных сообщений
        @self.router.message()
        async def unknown_message(message: Message):
            """Обработчик неизвестных сообщений"""
            help_text = (
                "❓ Неизвестная команда.\n\n"
                "Доступные команды:\n"
                "• /start - Главное меню\n"
                "• /generate - Создать сертификат\n"
                "• /verify - Проверить сертификат\n"
                "• /help - Справка\n\n"
                "Или отправьте ID сертификата для проверки."
            )

            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🏠 В главное меню", callback_data="start")
            ]])

            await message.answer(help_text, reply_markup=keyboard)
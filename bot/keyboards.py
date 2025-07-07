"""
Reply клавиатуры для Telegram бота.
"""

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.utils.keyboard import ReplyKeyboardBuilder


def get_main_menu_admin() -> ReplyKeyboardMarkup:
    """
    Главное меню для администраторов с кнопкой редактирования.

    Returns:
        ReplyKeyboardMarkup: Клавиатура главного меню
    """
    builder = ReplyKeyboardBuilder()

    # Первый ряд - основные действия
    builder.row(
        KeyboardButton(text="📝 Создать сертификат"),
        KeyboardButton(text="📋 Мои сертификаты")
    )

    # Второй ряд - проверка и поиск
    builder.row(
        KeyboardButton(text="🔍 Проверить сертификат"),
        KeyboardButton(text="🔎 Поиск")
    )

    # Третий ряд - редактирование и справка
    builder.row(
        KeyboardButton(text="✏️ Редактировать сертификат"),
        KeyboardButton(text="❓ Справка")
    )

    return builder.as_markup(resize_keyboard=True, one_time_keyboard=False)


def get_main_menu_verify() -> ReplyKeyboardMarkup:
    """
    Главное меню для пользователей с правами проверки.

    Returns:
        ReplyKeyboardMarkup: Клавиатура главного меню
    """
    builder = ReplyKeyboardBuilder()

    # Первый ряд - проверка и поиск
    builder.row(
        KeyboardButton(text="🔍 Проверить сертификат"),
        KeyboardButton(text="🔎 Поиск")
    )

    # Второй ряд - справка
    builder.row(
        KeyboardButton(text="❓ Справка")
    )

    return builder.as_markup(resize_keyboard=True, one_time_keyboard=False)


def get_search_type_keyboard() -> ReplyKeyboardMarkup:
    """
    Клавиатура выбора типа поиска.

    Returns:
        ReplyKeyboardMarkup: Клавиатура типов поиска
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="🌐 По домену"),
        KeyboardButton(text="🏢 По ИНН")
    )

    builder.row(
        KeyboardButton(text="🔙 Назад")
    )

    return builder.as_markup(resize_keyboard=True, one_time_keyboard=False)


def get_period_presets_keyboard() -> ReplyKeyboardMarkup:
    """
    Клавиатура с предустановленными периодами действия.

    Returns:
        ReplyKeyboardMarkup: Клавиатура периодов
    """
    builder = ReplyKeyboardBuilder()

    # Первый ряд - короткие периоды
    builder.row(
        KeyboardButton(text="📅 1 месяц"),
        KeyboardButton(text="📅 3 месяца")
    )

    # Второй ряд - стандартные периоды
    builder.row(
        KeyboardButton(text="📅 6 месяцев"),
        KeyboardButton(text="📅 1 год")
    )

    # Третий ряд - длинные периоды
    builder.row(
        KeyboardButton(text="📅 2 года"),
        KeyboardButton(text="📅 3 года")
    )

    # Четвертый ряд - ручной ввод и отмена
    builder.row(
        KeyboardButton(text="✏️ Ввести вручную")
    )

    builder.row(
        KeyboardButton(text="🔙 Назад")
    )

    return builder.as_markup(resize_keyboard=True, one_time_keyboard=False)


def get_users_count_presets_keyboard() -> ReplyKeyboardMarkup:
    """
    Клавиатура с предустановленными значениями количества пользователей.

    Returns:
        ReplyKeyboardMarkup: Клавиатура количества пользователей
    """
    builder = ReplyKeyboardBuilder()

    # Первый ряд - малые значения
    builder.row(
        KeyboardButton(text="👥 1"),
        KeyboardButton(text="👥 5"),
        KeyboardButton(text="👥 10")
    )

    # Второй ряд - средние значения
    builder.row(
        KeyboardButton(text="👥 25"),
        KeyboardButton(text="👥 50"),
        KeyboardButton(text="👥 100")
    )

    # Третий ряд - большие значения
    builder.row(
        KeyboardButton(text="👥 250"),
        KeyboardButton(text="👥 500"),
        KeyboardButton(text="👥 1000")
    )

    # Четвертый ряд - ручной ввод и отмена
    builder.row(
        KeyboardButton(text="✏️ Ввести вручную")
    )

    builder.row(
        KeyboardButton(text="🔙 Назад")
    )

    return builder.as_markup(resize_keyboard=True, one_time_keyboard=False)


def get_confirmation_keyboard() -> ReplyKeyboardMarkup:
    """
    Клавиатура подтверждения действия.

    Returns:
        ReplyKeyboardMarkup: Клавиатура подтверждения
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="✅ Подтвердить"),
        KeyboardButton(text="❌ Отменить")
    )

    return builder.as_markup(resize_keyboard=True, one_time_keyboard=False)


def get_edit_confirmation_keyboard() -> ReplyKeyboardMarkup:
    """
    Клавиатура подтверждения редактирования.

    Returns:
        ReplyKeyboardMarkup: Клавиатура подтверждения редактирования
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="✅ Подтвердить изменения"),
        KeyboardButton(text="❌ Отменить изменения")
    )

    return builder.as_markup(resize_keyboard=True, one_time_keyboard=False)


def get_duplicate_confirmation_keyboard() -> ReplyKeyboardMarkup:
    """
    Клавиатура подтверждения при наличии дубликатов.

    Returns:
        ReplyKeyboardMarkup: Клавиатура подтверждения дубликата
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="✅ Да, создать"),
        KeyboardButton(text="❌ Нет, отменить")
    )

    return builder.as_markup(resize_keyboard=True, one_time_keyboard=False)


def get_back_keyboard() -> ReplyKeyboardMarkup:
    """
    Простая клавиатура с кнопкой "Назад".

    Returns:
        ReplyKeyboardMarkup: Клавиатура с кнопкой назад
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="🔙 Назад")
    )

    return builder.as_markup(resize_keyboard=True, one_time_keyboard=False)


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """
    Простая клавиатура с кнопкой "Отменить".

    Returns:
        ReplyKeyboardMarkup: Клавиатура с кнопкой отмены
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="❌ Отменить")
    )

    return builder.as_markup(resize_keyboard=True, one_time_keyboard=False)


def remove_keyboard() -> ReplyKeyboardRemove:
    """
    Удаляет клавиатуру.

    Returns:
        ReplyKeyboardRemove: Объект для удаления клавиатуры
    """
    return ReplyKeyboardRemove()


# Константы для текстов кнопок
class ButtonTexts:
    """Константы для текстов кнопок."""

    # Главное меню
    CREATE_CERTIFICATE = "📝 Создать сертификат"
    MY_CERTIFICATES = "📋 Мои сертификаты"
    VERIFY_CERTIFICATE = "🔍 Проверить сертификат"
    SEARCH = "🔎 Поиск"
    HELP = "❓ Справка"

    # Редактирование
    EDIT_CERTIFICATE = "✏️ Редактировать сертификат"
    EDIT_DATES = "📅 Изменить даты"

    # Поиск
    SEARCH_BY_DOMAIN = "🌐 По домену"
    SEARCH_BY_INN = "🏢 По ИНН"

    # Периоды
    PERIOD_1_MONTH = "📅 1 месяц"
    PERIOD_3_MONTHS = "📅 3 месяца"
    PERIOD_6_MONTHS = "📅 6 месяцев"
    PERIOD_1_YEAR = "📅 1 год"
    PERIOD_2_YEARS = "📅 2 года"
    PERIOD_3_YEARS = "📅 3 года"
    PERIOD_MANUAL = "✏️ Ввести вручную"

    # Количество пользователей
    USERS_1 = "👥 1"
    USERS_5 = "👥 5"
    USERS_10 = "👥 10"
    USERS_25 = "👥 25"
    USERS_50 = "👥 50"
    USERS_100 = "👥 100"
    USERS_250 = "👥 250"
    USERS_500 = "👥 500"
    USERS_1000 = "👥 1000"
    USERS_MANUAL = "✏️ Ввести вручную"

    # Подтверждение
    CONFIRM = "✅ Подтвердить"
    CANCEL = "❌ Отменить"
    YES_CREATE = "✅ Да, создать"
    NO_CANCEL = "❌ Нет, отменить"

    # Подтверждение редактирования
    CONFIRM_EDIT = "✅ Подтвердить изменения"
    CANCEL_EDIT = "❌ Отменить изменения"

    # Навигация
    BACK = "🔙 Назад"

    @classmethod
    def extract_users_count(cls, text: str) -> int:
        """
        Извлекает количество пользователей из текста кнопки.

        Args:
            text: Текст кнопки

        Returns:
            int: Количество пользователей или 0 если не найдено
        """
        users_mapping = {
            cls.USERS_1: 1,
            cls.USERS_5: 5,
            cls.USERS_10: 10,
            cls.USERS_25: 25,
            cls.USERS_50: 50,
            cls.USERS_100: 100,
            cls.USERS_250: 250,
            cls.USERS_500: 500,
            cls.USERS_1000: 1000
        }

        return users_mapping.get(text, 0)

    @classmethod
    def get_period_months(cls, text: str) -> int:
        """
        Получает количество месяцев из текста кнопки периода.

        Args:
            text: Текст кнопки

        Returns:
            int: Количество месяцев или 0 если не найдено
        """
        period_mapping = {
            cls.PERIOD_1_MONTH: 1,
            cls.PERIOD_3_MONTHS: 3,
            cls.PERIOD_6_MONTHS: 6,
            cls.PERIOD_1_YEAR: 12,
            cls.PERIOD_2_YEARS: 24,
            cls.PERIOD_3_YEARS: 36
        }

        return period_mapping.get(text, 0)
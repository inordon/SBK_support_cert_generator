"""
Состояния FSM (Finite State Machine) для диалогов Telegram бота.
"""

from aiogram.fsm.state import State, StatesGroup


class CreateCertificateStates(StatesGroup):
    """Состояния процесса создания сертификата."""

    waiting_for_domain = State()           # Ожидание ввода домена
    waiting_for_inn = State()              # Ожидание ввода ИНН
    waiting_for_period = State()           # Ожидание ввода периода действия
    waiting_for_users_count = State()      # Ожидание ввода количества пользователей
    waiting_for_confirmation = State()     # Ожидание подтверждения создания
    waiting_for_duplicate_confirmation = State()  # Подтверждение при дубликатах


class VerifyCertificateStates(StatesGroup):
    """Состояния процесса проверки сертификата."""

    waiting_for_certificate_id = State()   # Ожидание ввода ID сертификата


class SearchStates(StatesGroup):
    """Состояния процесса поиска сертификатов."""

    waiting_for_search_type = State()      # Выбор типа поиска
    waiting_for_domain_search = State()    # Ожидание ввода домена для поиска
    waiting_for_inn_search = State()       # Ожидание ввода ИНН для поиска
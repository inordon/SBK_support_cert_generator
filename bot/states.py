# bot/states.py - обновленная версия

"""
Состояния FSM (Finite State Machine) для диалогов Telegram бота.
"""

from aiogram.fsm.state import State, StatesGroup


class CreateCertificateStates(StatesGroup):
    """Состояния процесса создания сертификата."""

    waiting_for_certificate_data = State()    # Ожидание всех данных одним сообщением
    waiting_for_confirmation = State()        # Ожидание подтверждения создания


class VerifyCertificateStates(StatesGroup):
    """Состояния процесса проверки сертификата."""

    waiting_for_certificate_id = State()   # Ожидание ввода ID сертификата


class SearchStates(StatesGroup):
    """Состояния процесса поиска сертификатов."""

    waiting_for_search_type = State()      # Выбор типа поиска
    waiting_for_domain_search = State()    # Ожидание ввода домена для поиска
    waiting_for_inn_search = State()       # Ожидание ввода ИНН для поиска
"""
Certificate Management Bot - Система управления сертификатами через Telegram.

Основные компоненты:
- core: Бизнес-логика для работы с сертификатами
- bot: Telegram бот для взаимодействия с пользователями
- config: Настройки и конфигурация
"""

__version__ = "1.0.0"
__author__ = "Certificate Bot Team"
__description__ = "Telegram бот для генерации, проверки и управления сертификатами"
__license__ = "MIT"

# Основные компоненты для импорта
from core import get_certificate_service
from config import get_settings

__all__ = [
    'get_certificate_service',
    'get_settings'
]
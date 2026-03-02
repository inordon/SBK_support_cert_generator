"""
Пакет обработчиков команд Telegram бота.
"""

from . import admin
from . import verify
from . import common
from . import edit
from . import group

__all__ = ['admin', 'verify', 'common', 'edit', 'group']
"""
Генератор уникальных номеров сертификатов.
Портировано из core/generator.py для Django.
"""

import random
import string
from datetime import date


class CertificateIDGenerator:
    """Генератор уникальных ID сертификатов формата XXXXX-XXXXX-XXXXX-XXXXX."""

    CHARACTERS = string.ascii_uppercase + string.digits
    MAX_ATTEMPTS = 1000

    def generate(self, valid_to: date) -> str:
        """
        Генерирует ID сертификата.
        Последние 4 символа последнего блока = MMYY (месяц/год окончания).
        Уникальность обеспечивается DB unique constraint в views.
        """
        suffix = f'{valid_to.month:02d}{valid_to.year % 100:02d}'
        return self._build_id(suffix)

    def _build_id(self, suffix: str) -> str:
        block = lambda: ''.join(random.choices(self.CHARACTERS, k=5))
        last_prefix = random.choice(self.CHARACTERS)
        return f'{block()}-{block()}-{block()}-{last_prefix}{suffix}'

    @staticmethod
    def validate_format(certificate_id: str) -> bool:
        if not certificate_id or len(certificate_id) != 23:
            return False
        parts = certificate_id.split('-')
        if len(parts) != 4:
            return False
        allowed = set(string.ascii_uppercase + string.digits)
        return all(len(p) == 5 and all(c in allowed for c in p) for p in parts)

    @staticmethod
    def extract_expiry(certificate_id: str):
        """Возвращает (month, year) из ID сертификата."""
        last_block = certificate_id.split('-')[-1]
        month = int(last_block[1:3])
        year_short = int(last_block[3:5])
        current_century = date.today().year // 100
        year = current_century * 100 + year_short
        return month, year

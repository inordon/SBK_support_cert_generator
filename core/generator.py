"""
Генератор сертификатов
"""
import random
import string
from datetime import datetime
from typing import Optional

from .models import Certificate
from .validators import Validators


class CertificateGenerator:
    """Генератор сертификатов"""

    # Символы для генерации
    CHARS = string.ascii_uppercase + string.digits

    def __init__(self):
        self.validators = Validators()

    def generate_certificate(
            self,
            domain: str,
            inn: str,
            period: str,
            users_count: int,
            created_by: Optional[int] = None
    ) -> Certificate:
        """
        Генерация нового сертификата

        Args:
            domain: Доменное имя
            inn: ИНН организации
            period: Период действия в формате DD.MM.YYYY-DD.MM.YYYY
            users_count: Количество пользователей
            created_by: ID создателя

        Returns:
            Объект сертификата

        Raises:
            ValidationError: При невалидных входных данных
        """
        # Валидация входных данных
        self.validators.validate_domain(domain)
        self.validators.validate_inn(inn)
        valid_from, valid_to = self.validators.validate_period(period)
        self.validators.validate_users_count(users_count)

        # Генерация ID сертификата
        certificate_id = self._generate_certificate_id(valid_to)

        # Создание объекта сертификата
        certificate = Certificate(
            certificate_id=certificate_id,
            domain=domain,
            inn=inn,
            valid_from=valid_from,
            valid_to=valid_to,
            users_count=users_count,
            created_at=datetime.now(),
            created_by=created_by
        )

        return certificate

    def _generate_certificate_id(self, valid_to: datetime) -> str:
        """
        Генерация уникального ID сертификата

        Args:
            valid_to: Дата окончания действия сертификата

        Returns:
            ID сертификата в формате XXXXX-XXXXX-XXXXX-XXXXX
        """
        # Генерируем первые 3 блока (15 символов)
        blocks = []
        for _ in range(3):
            block = ''.join(random.choices(self.CHARS, k=5))
            blocks.append(block)

        # Последний блок: первый символ случайный + MMYY
        month_year = valid_to.strftime("%m%y")
        first_char = random.choice(self.CHARS)
        last_block = first_char + month_year
        blocks.append(last_block)

        return '-'.join(blocks)

    def verify_certificate_id_format(self, certificate_id: str) -> bool:
        """
        Проверка формата ID сертификата

        Args:
            certificate_id: ID сертификата для проверки

        Returns:
            True если формат корректен
        """
        if not certificate_id or len(certificate_id) != 23:
            return False

        # Проверка формата XXXXX-XXXXX-XXXXX-XXXXX
        parts = certificate_id.split('-')
        if len(parts) != 4:
            return False

        # Проверка длины каждой части
        for part in parts:
            if len(part) != 5:
                return False
            # Проверка символов
            for char in part:
                if char not in self.CHARS:
                    return False

        # Проверка последних 4 символов (MMYY)
        last_part = parts[-1]
        month_year = last_part[1:]  # Пропускаем первый символ

        try:
            month = int(month_year[:2])
            year = int(month_year[2:])

            # Проверка корректности месяца
            if month < 1 or month > 12:
                return False

            # Проверка корректности года (от 00 до 99)
            if year < 0 or year > 99:
                return False

        except ValueError:
            return False

        return True
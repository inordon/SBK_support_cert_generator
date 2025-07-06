"""
Модуль валидации входных данных для сертификатов.
"""

import re
from datetime import date, datetime
from typing import List, Tuple
from .exceptions import *


class DomainValidator:
    """Валидатор доменных имен с поддержкой wildcard."""

    def __init__(self):
        # Паттерн для валидации части домена (может содержать дефисы, но не в начале/конце)
        self.domain_part_pattern = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?$')
        # Паттерн для полного домена
        self.domain_pattern = re.compile(r'^(\*\.)?[a-zA-Z0-9]([a-zA-Z0-9.-]*[a-zA-Z0-9])?$')

    def validate(self, domain: str) -> bool:
        """
        Валидация доменного имени.

        Args:
            domain: Доменное имя для валидации

        Returns:
            bool: True если домен валиден, False иначе
        """
        if not domain or len(domain) > 255:
            return False

        # Проверяем общий формат
        if not self.domain_pattern.match(domain):
            return False

        # Обрабатываем wildcard
        if domain.startswith('*.'):
            domain = domain[2:]  # Убираем '*.'

        # Разделяем на части
        parts = domain.split('.')

        # Должно быть минимум 2 части (например, site.com)
        if len(parts) < 2:
            return False

        # Валидируем каждую часть
        for part in parts:
            if not self._validate_domain_part(part):
                return False

        return True

    def _validate_domain_part(self, part: str) -> bool:
        """
        Валидация отдельной части домена.

        Args:
            part: Часть домена для валидации

        Returns:
            bool: True если часть валидна, False иначе
        """
        if not part or len(part) > 63:
            return False

        # Не может начинаться или заканчиваться дефисом
        if part.startswith('-') or part.endswith('-'):
            return False

        # Проверяем паттерн
        return bool(self.domain_part_pattern.match(part))

    def get_domain_examples(self) -> List[str]:
        """Возвращает примеры валидных доменов."""
        return [
            "example.com",
            "my-site.com",
            "sub.example.com",
            "sub-domain.my-site.com",
            "*.example.com",
            "*.sub.example.com",
            "*.sub-domain.my-site.com"
        ]


class INNValidator:
    """Валидатор ИНН с проверкой контрольной суммы."""

    def validate(self, inn: str) -> bool:
        """
        Валидация ИНН с проверкой контрольной суммы.

        Args:
            inn: ИНН для валидации

        Returns:
            bool: True если ИНН валиден, False иначе
        """
        if not inn or not inn.isdigit():
            return False

        if len(inn) == 10:
            return self._validate_inn_10(inn)
        elif len(inn) == 12:
            return self._validate_inn_12(inn)

        return False

    def _validate_inn_10(self, inn: str) -> bool:
        """Валидация 10-значного ИНН."""
        coefficients = [2, 4, 10, 3, 5, 9, 4, 6, 8]

        checksum = sum(int(inn[i]) * coefficients[i] for i in range(9))
        control_digit = (checksum % 11) % 10

        return int(inn[9]) == control_digit

    def _validate_inn_12(self, inn: str) -> bool:
        """Валидация 12-значного ИНН."""
        # Проверяем первую контрольную цифру
        coefficients_1 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
        checksum_1 = sum(int(inn[i]) * coefficients_1[i] for i in range(10))
        control_digit_1 = (checksum_1 % 11) % 10

        if int(inn[10]) != control_digit_1:
            return False

        # Проверяем вторую контрольную цифру
        coefficients_2 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
        checksum_2 = sum(int(inn[i]) * coefficients_2[i] for i in range(11))
        control_digit_2 = (checksum_2 % 11) % 10

        return int(inn[11]) == control_digit_2


class PeriodValidator:
    """Валидатор периода действия сертификата."""

    def validate(self, valid_from: date, valid_to: date) -> Tuple[bool, str]:
        """
        Валидация периода действия.

        Args:
            valid_from: Дата начала действия
            valid_to: Дата окончания действия

        Returns:
            Tuple[bool, str]: (валиден ли период, сообщение об ошибке)
        """
        today = date.today()

        # Проверяем, что даты не в прошлом
        if valid_from < today:
            return False, "Дата начала не может быть в прошлом"

        # Проверяем, что дата окончания позже даты начала
        if valid_to <= valid_from:
            return False, "Дата окончания должна быть позже даты начала"

        # Проверяем, что период не превышает 5 лет
        years_diff = (valid_to - valid_from).days / 365.25
        if years_diff > 5:
            return False, "Период действия не может превышать 5 лет"

        return True, ""

    def parse_period_string(self, period: str) -> Tuple[date, date]:
        """
        Парсинг строки периода в формате DD.MM.YYYY-DD.MM.YYYY.

        Args:
            period: Строка периода

        Returns:
            Tuple[date, date]: Кортеж дат начала и окончания

        Raises:
            PeriodValidationError: При некорректном формате
        """
        try:
            date_parts = period.split('-')
            if len(date_parts) != 2:
                raise PeriodValidationError("Неверный формат периода. Используйте DD.MM.YYYY-DD.MM.YYYY")

            valid_from = datetime.strptime(date_parts[0].strip(), "%d.%m.%Y").date()
            valid_to = datetime.strptime(date_parts[1].strip(), "%d.%m.%Y").date()

            return valid_from, valid_to

        except ValueError as e:
            raise PeriodValidationError(f"Неверный формат даты: {e}")


class UsersCountValidator:
    """Валидатор количества пользователей."""

    def validate(self, users_count: int) -> bool:
        """
        Валидация количества пользователей.

        Args:
            users_count: Количество пользователей

        Returns:
            bool: True если количество валидно, False иначе
        """
        return isinstance(users_count, int) and 1 <= users_count <= 1000


class CertificateIDValidator:
    """Валидатор ID сертификата."""

    def __init__(self):
        # Паттерн для валидации ID сертификата: XXXXX-XXXXX-XXXXX-XXXXX
        self.pattern = re.compile(r'^[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}$')

    def validate(self, certificate_id: str) -> bool:
        """
        Валидация ID сертификата.

        Args:
            certificate_id: ID сертификата для валидации

        Returns:
            bool: True если ID валиден, False иначе
        """
        if not certificate_id or len(certificate_id) != 23:
            return False

        return bool(self.pattern.match(certificate_id))

    def validate_ending(self, certificate_id: str, expected_month: int, expected_year: int) -> bool:
        """
        Валидация окончания ID сертификата (месяц и год).

        Args:
            certificate_id: ID сертификата
            expected_month: Ожидаемый месяц
            expected_year: Ожидаемый год

        Returns:
            bool: True если окончание соответствует, False иначе
        """
        if not self.validate(certificate_id):
            return False

        # Извлекаем последние 4 символа
        ending = certificate_id[-4:]

        # Последние 2 цифры - месяц и год
        try:
            month_str = ending[2:4]  # Месяц
            year_str = ending[4:6]   # Год (последние 2 цифры)

            # Конвертируем в числа
            month = int(month_str)
            year = int(year_str)

            # Проверяем соответствие
            return month == expected_month and year == (expected_year % 100)

        except (ValueError, IndexError):
            return False


class DataValidator:
    """Общий валидатор для всех типов данных."""

    def __init__(self):
        self.domain_validator = DomainValidator()
        self.inn_validator = INNValidator()
        self.period_validator = PeriodValidator()
        self.users_count_validator = UsersCountValidator()
        self.certificate_id_validator = CertificateIDValidator()

    def validate_all(self, domain: str, inn: str, valid_from: date,
                     valid_to: date, users_count: int) -> List[str]:
        """
        Валидация всех данных сертификата.

        Args:
            domain: Доменное имя
            inn: ИНН
            valid_from: Дата начала действия
            valid_to: Дата окончания действия
            users_count: Количество пользователей

        Returns:
            List[str]: Список ошибок валидации (пустой если все в порядке)
        """
        errors = []

        # Валидация домена
        if not self.domain_validator.validate(domain):
            errors.append(f"Некорректный домен: {domain}")

        # Валидация ИНН
        if not self.inn_validator.validate(inn):
            errors.append(f"Некорректный ИНН: {inn}")

        # Валидация периода
        period_valid, period_error = self.period_validator.validate(valid_from, valid_to)
        if not period_valid:
            errors.append(period_error)

        # Валидация количества пользователей
        if not self.users_count_validator.validate(users_count):
            errors.append(f"Некорректное количество пользователей: {users_count}")

        return errors
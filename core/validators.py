"""
Валидаторы для входных данных
"""
import re
from datetime import datetime, timedelta
from typing import Tuple


class ValidationError(Exception):
    """Исключение для ошибок валидации"""
    pass


class Validators:
    """Класс для валидации входных данных"""

    @staticmethod
    def validate_domain(domain: str) -> bool:
        """
        Валидация домена с поддержкой wildcard

        Args:
            domain: Доменное имя для проверки

        Returns:
            True если домен валиден

        Raises:
            ValidationError: При невалидном домене
        """
        if not domain or len(domain) > 255:
            raise ValidationError("Домен не может быть пустым или длиннее 255 символов")

        # Разрешаем wildcard в начале
        if domain.startswith("*."):
            domain = domain[2:]

        # Проверка общего формата
        domain_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)*$'
        if not re.match(domain_pattern, domain):
            raise ValidationError("Некорректный формат домена")

        # Проверка длины частей
        parts = domain.split('.')
        for part in parts:
            if len(part) > 63:
                raise ValidationError("Часть домена не может быть длиннее 63 символов")

        return True

    @staticmethod
    def validate_inn(inn: str) -> bool:
        """
        Валидация ИНН с проверкой контрольной суммы

        Args:
            inn: ИНН для проверки

        Returns:
            True если ИНН валиден

        Raises:
            ValidationError: При невалидном ИНН
        """
        if not inn or not inn.isdigit():
            raise ValidationError("ИНН должен содержать только цифры")

        if len(inn) not in [10, 12]:
            raise ValidationError("ИНН должен содержать 10 или 12 цифр")

        # Проверка контрольной суммы для 10-значного ИНН
        if len(inn) == 10:
            check_digit = Validators._calculate_inn_10_check_digit(inn[:9])
            if check_digit != int(inn[9]):
                raise ValidationError("Неверная контрольная сумма ИНН")

        # Проверка контрольной суммы для 12-значного ИНН
        elif len(inn) == 12:
            check_digit_11 = Validators._calculate_inn_12_check_digit_11(inn[:10])
            check_digit_12 = Validators._calculate_inn_12_check_digit_12(inn[:11])

            if check_digit_11 != int(inn[10]) or check_digit_12 != int(inn[11]):
                raise ValidationError("Неверная контрольная сумма ИНН")

        return True

    @staticmethod
    def _calculate_inn_10_check_digit(inn_9: str) -> int:
        """Расчет контрольной суммы для 10-значного ИНН"""
        coefficients = [2, 4, 10, 3, 5, 9, 4, 6, 8]
        sum_val = sum(int(inn_9[i]) * coefficients[i] for i in range(9))
        return sum_val % 11 % 10

    @staticmethod
    def _calculate_inn_12_check_digit_11(inn_10: str) -> int:
        """Расчет 11-й контрольной цифры для 12-значного ИНН"""
        coefficients = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
        sum_val = sum(int(inn_10[i]) * coefficients[i] for i in range(10))
        return sum_val % 11 % 10

    @staticmethod
    def _calculate_inn_12_check_digit_12(inn_11: str) -> int:
        """Расчет 12-й контрольной цифры для 12-значного ИНН"""
        coefficients = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
        sum_val = sum(int(inn_11[i]) * coefficients[i] for i in range(11))
        return sum_val % 11 % 10

    @staticmethod
    def validate_period(period: str) -> Tuple[datetime, datetime]:
        """
        Валидация периода действия сертификата

        Args:
            period: Период в формате DD.MM.YYYY-DD.MM.YYYY

        Returns:
            Кортеж (начальная_дата, конечная_дата)

        Raises:
            ValidationError: При невалидном периоде
        """
        try:
            start_str, end_str = period.split('-')
            start_date = datetime.strptime(start_str.strip(), '%d.%m.%Y')
            end_date = datetime.strptime(end_str.strip(), '%d.%m.%Y')
        except ValueError:
            raise ValidationError("Неверный формат периода. Используйте DD.MM.YYYY-DD.MM.YYYY")

        # Проверка логичности дат
        if start_date >= end_date:
            raise ValidationError("Начальная дата должна быть раньше конечной")

        # Проверка, что даты не в прошлом
        now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        if start_date < now:
            raise ValidationError("Начальная дата не может быть в прошлом")

        # Проверка максимального периода (5 лет)
        max_period = timedelta(days=5*365)
        if end_date - start_date > max_period:
            raise ValidationError("Период действия не может превышать 5 лет")

        return start_date, end_date

    @staticmethod
    def validate_users_count(users_count: int) -> bool:
        """
        Валидация количества пользователей

        Args:
            users_count: Количество пользователей

        Returns:
            True если значение валидно

        Raises:
            ValidationError: При невалидном значении
        """
        if not isinstance(users_count, int) or users_count < 1 or users_count > 1000:
            raise ValidationError("Количество пользователей должно быть от 1 до 1000")

        return True
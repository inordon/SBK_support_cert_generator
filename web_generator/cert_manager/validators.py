"""
Валидаторы для сертификатов. Портировано из core/validators.py.
"""

import re
from django.core.exceptions import ValidationError


def validate_domain(value):
    """Валидация доменного имени с поддержкой wildcard."""
    if not value or len(value) > 255:
        raise ValidationError('Некорректная длина домена.')

    pattern = re.compile(r'^(\*\.)?[a-zA-Z0-9]([a-zA-Z0-9.\-]*[a-zA-Z0-9])?$')
    if not pattern.match(value):
        raise ValidationError(f'Некорректный формат домена: {value}')

    test_domain = value[2:] if value.startswith('*.') else value
    parts = test_domain.split('.')
    if len(parts) < 2:
        raise ValidationError('Домен должен содержать минимум 2 части.')

    part_re = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?$')
    for part in parts:
        if not part or len(part) > 63:
            raise ValidationError(f'Некорректная часть домена: {part}')
        if not part_re.match(part):
            raise ValidationError(f'Недопустимые символы в части домена: {part}')


def validate_inn(value):
    """Валидация ИНН (РФ) / БИН (Казахстан)."""
    if not value or not value.isdigit():
        raise ValidationError('ИНН/БИН должен содержать только цифры.')

    if len(value) == 10:
        coefficients = [2, 4, 10, 3, 5, 9, 4, 6, 8]
        checksum = sum(int(value[i]) * coefficients[i] for i in range(9))
        if int(value[9]) != (checksum % 11) % 10:
            raise ValidationError('Некорректная контрольная сумма ИНН.')
    elif len(value) == 12:
        # Try as Russian INN first
        c1 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
        c2 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
        s1 = sum(int(value[i]) * c1[i] for i in range(10))
        s2 = sum(int(value[i]) * c2[i] for i in range(11))
        d1 = (s1 % 11) % 10
        d2 = (s2 % 11) % 10
        if int(value[10]) == d1 and int(value[11]) == d2:
            return  # Valid Russian 12-digit INN

        # Try as Kazakhstan BIN
        month = int(value[2:4])
        if month < 1 or month > 12:
            raise ValidationError('Некорректный ИНН/БИН.')

        # Контрольная цифра БИН (12-й разряд)
        weights_1 = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
        s = sum(int(value[i]) * weights_1[i] for i in range(11))
        remainder = s % 11
        if remainder == 10:
            weights_2 = [3, 4, 5, 6, 7, 8, 9, 10, 11, 1, 2]
            s = sum(int(value[i]) * weights_2[i] for i in range(11))
            remainder = s % 11
            if remainder == 10:
                raise ValidationError('Некорректная контрольная сумма БИН.')
        if int(value[11]) != remainder:
            raise ValidationError('Некорректная контрольная сумма БИН.')
    else:
        raise ValidationError('ИНН/БИН должен содержать 10 или 12 цифр.')

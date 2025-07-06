"""
Базовые тесты для проверки функциональности системы.
"""

import pytest
from datetime import date, timedelta
from core.generator import CertificateIDGenerator
from core.validator import DomainValidator, INNValidator, DataValidator
from core.models import CertificateRequest


class TestCertificateIDGenerator:
    """Тесты генератора ID сертификатов."""

    def test_generate_valid_id(self):
        """Тест генерации валидного ID."""
        generator = CertificateIDGenerator()
        valid_to = date(2024, 5, 31)

        cert_id = generator.generate(valid_to)

        assert len(cert_id) == 23
        assert cert_id.count('-') == 3
        assert cert_id.endswith('0524')  # Май 2024

    def test_validate_id_format(self):
        """Тест валидации формата ID."""
        generator = CertificateIDGenerator()

        # Валидные ID
        assert generator.validate_id_format('A1B2C-D3E4F-G5H6I-J7K80')
        assert generator.validate_id_format('AAAAA-BBBBB-CCCCC-DDDDD')

        # Невалидные ID
        assert not generator.validate_id_format('SHORT')
        assert not generator.validate_id_format('TOOLONGIDENTIFIER')
        assert not generator.validate_id_format('A1B2C-D3E4F-G5H6I')  # Неполный
        assert not generator.validate_id_format('A1B2C_D3E4F_G5H6I_J7K80')  # Неверные разделители

    def test_extract_expiry_date(self):
        """Тест извлечения даты окончания."""
        generator = CertificateIDGenerator()

        month, year = generator.extract_expiry_date('A1B2C-D3E4F-G5H6I-J7K0524')
        assert month == 5
        assert year == 2024

        month, year = generator.extract_expiry_date('A1B2C-D3E4F-G5H6I-J7K1225')
        assert month == 12
        assert year == 2025


class TestDomainValidator:
    """Тесты валидатора доменов."""

    def test_valid_domains(self):
        """Тест валидных доменов."""
        validator = DomainValidator()

        valid_domains = [
            'example.com',
            'sub.example.com',
            'my-site.com',
            'test-domain.org',
            '*.example.com',
            '*.sub.example.com',
            'site123.ru',
            'a.b'
        ]

        for domain in valid_domains:
            assert validator.validate(domain), f"Домен {domain} должен быть валидным"

    def test_invalid_domains(self):
        """Тест невалидных доменов."""
        validator = DomainValidator()

        invalid_domains = [
            '-example.com',  # Начинается с дефиса
            'example-.com',  # Заканчивается дефисом
            'example..com',  # Двойная точка
            '*.*.example.com',  # Несколько wildcards
            'example.*',  # Wildcard не в начале
            'a',  # Слишком короткий
            '',  # Пустой
            'example.com' + 'a' * 250  # Слишком длинный
        ]

        for domain in invalid_domains:
            assert not validator.validate(domain), f"Домен {domain} должен быть невалидным"


class TestINNValidator:
    """Тесты валидатора ИНН."""

    def test_valid_inn_10(self):
        """Тест валидного 10-значного ИНН."""
        validator = INNValidator()

        # Примеры валидных 10-значных ИНН
        valid_inns = [
            '7707083893',  # Сбербанк
            '5077746887',  # Альфа-банк
        ]

        for inn in valid_inns:
            assert validator.validate(inn), f"ИНН {inn} должен быть валидным"

    def test_invalid_inn(self):
        """Тест невалидных ИНН."""
        validator = INNValidator()

        invalid_inns = [
            '123456789',    # 9 цифр
            '12345678901',  # 11 цифр
            '1234567890123',  # 13 цифр
            'abcdefghij',   # Буквы
            '1234567890',   # Неверная контрольная сумма
            '',  # Пустой
        ]

        for inn in invalid_inns:
            assert not validator.validate(inn), f"ИНН {inn} должен быть невалидным"


class TestDataValidator:
    """Тесты общего валидатора данных."""

    def test_validate_all_valid_data(self):
        """Тест валидации корректных данных."""
        validator = DataValidator()

        errors = validator.validate_all(
            domain='example.com',
            inn='7707083893',
            valid_from=date.today(),
            valid_to=date.today() + timedelta(days=365),
            users_count=100
        )

        assert len(errors) == 0, f"Не должно быть ошибок валидации: {errors}"

    def test_validate_all_invalid_data(self):
        """Тест валидации некорректных данных."""
        validator = DataValidator()

        errors = validator.validate_all(
            domain='-invalid.com',
            inn='123',
            valid_from=date.today() + timedelta(days=365),  # Начало после окончания
            valid_to=date.today(),
            users_count=2000  # Слишком много
        )

        assert len(errors) > 0, "Должны быть ошибки валидации"
        assert any('домен' in error.lower() for error in errors)
        assert any('инн' in error.lower() for error in errors)


class TestCertificateRequest:
    """Тесты модели запроса сертификата."""

    def test_create_valid_request(self):
        """Тест создания валидного запроса."""
        request = CertificateRequest(
            domain='example.com',
            inn='7707083893',
            valid_from=date.today(),
            valid_to=date.today() + timedelta(days=365),
            users_count=100,
            created_by=123456789
        )

        assert request.domain == 'example.com'
        assert request.inn == '7707083893'
        assert request.users_count == 100

    def test_domain_normalization(self):
        """Тест нормализации домена."""
        request = CertificateRequest(
            domain='EXAMPLE.COM',
            inn='7707083893',
            valid_from=date.today(),
            valid_to=date.today() + timedelta(days=365),
            users_count=100,
            created_by=123456789
        )

        assert request.domain == 'example.com'


if __name__ == '__main__':
    pytest.main(['-v', __file__])
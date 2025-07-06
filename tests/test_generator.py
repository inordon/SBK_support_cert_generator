"""
Тесты для генератора сертификатов
"""
import pytest
from datetime import datetime, timedelta

from core.generator import CertificateGenerator
from core.validators import ValidationError


class TestCertificateGenerator:
    """Тесты для класса CertificateGenerator"""

    @pytest.fixture
    def generator(self):
        """Фикстура для генератора"""
        return CertificateGenerator()

    def test_generate_certificate_valid(self, generator):
        """Тест генерации корректного сертификата"""
        tomorrow = datetime.now() + timedelta(days=1)
        next_month = tomorrow + timedelta(days=30)
        period = f"{tomorrow.strftime('%d.%m.%Y')}-{next_month.strftime('%d.%m.%Y')}"

        certificate = generator.generate_certificate(
            domain="example.com",
            inn="7707083893",
            period=period,
            users_count=100,
            created_by=123456789
        )

        assert certificate.domain == "example.com"
        assert certificate.inn == "7707083893"
        assert certificate.users_count == 100
        assert certificate.created_by == 123456789
        assert len(certificate.certificate_id) == 23
        assert certificate.certificate_id.count('-') == 3

    def test_generate_certificate_id_format(self, generator):
        """Тест формата ID сертификата"""
        valid_to = datetime.now() + timedelta(days=30)

        cert_id = generator._generate_certificate_id(valid_to)

        # Проверка общего формата
        assert len(cert_id) == 23
        assert cert_id.count('-') == 3

        # Проверка последних 4 символов (MMYY)
        last_part = cert_id.split('-')[-1]
        month_year = last_part[1:]  # Пропускаем первый символ

        expected_month_year = valid_to.strftime("%m%y")
        assert month_year == expected_month_year

    def test_verify_certificate_id_format_valid(self, generator):
        """Тест проверки корректного формата ID"""
        valid_ids = [
            "ABCD1-XYZ12-QWRT5-WX0124",
            "12345-ABCDE-67890-F0124",
            "AAAAA-BBBBB-CCCCC-D1224"
        ]

        for cert_id in valid_ids:
            assert generator.verify_certificate_id_format(cert_id) is True

    def test_verify_certificate_id_format_invalid(self, generator):
        """Тест проверки некорректного формата ID"""
        invalid_ids = [
            "",
            "ABCD1-XYZ12-QWRT5",  # Короткий
            "ABCD1-XYZ12-QWRT5-WX0124-EXTRA",  # Длинный
            "ABCD1_XYZ12_QWRT5_WX0124",  # Неверные разделители
            "abcd1-xyz12-qwrt5-wx0124",  # Строчные буквы
            "ABCD1-XYZ12-QWRT5-WX1324",  # Неверный месяц (13)
            "ABCD1-XYZ12-QWRT5-WX0024"   # Неверный месяц (00)
        ]

        for cert_id in invalid_ids:
            assert generator.verify_certificate_id_format(cert_id) is False

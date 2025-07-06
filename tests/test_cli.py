"""
Тесты для CLI
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import sys
from io import StringIO

from cli import CertificateCLI
from core.models import Certificate


class TestCertificateCLI:
    """Тесты для CLI интерфейса"""

    @pytest.fixture
    def mock_db_storage(self):
        """Мок для БД"""
        mock = AsyncMock()
        mock.connect = AsyncMock()
        mock.disconnect = AsyncMock()
        mock.save_certificate = AsyncMock(return_value="test-uuid")
        mock.get_certificate = AsyncMock(return_value=None)
        return mock

    @pytest.fixture
    def mock_file_storage(self):
        """Мок для файлового хранилища"""
        mock = MagicMock()
        mock.save_certificate = MagicMock(return_value="/path/to/file")
        mock.load_certificate = MagicMock(return_value=None)
        return mock

    @pytest.fixture
    def cli(self, mock_db_storage, mock_file_storage):
        """Фикстура для CLI"""
        cli = CertificateCLI()
        cli.db_storage = mock_db_storage
        cli.file_storage = mock_file_storage
        return cli

    @pytest.mark.asyncio
    async def test_generate_certificate_success(self, cli, capsys):
        """Тест успешной генерации сертификата через CLI"""
        tomorrow = datetime.now() + timedelta(days=1)
        next_month = tomorrow + timedelta(days=30)

        # Мок аргументов
        args = MagicMock()
        args.domain = "example.com"
        args.inn = "7707083893"
        args.period = f"{tomorrow.strftime('%d.%m.%Y')}-{next_month.strftime('%d.%m.%Y')}"
        args.users = 100

        await cli.generate_certificate(args)

        captured = capsys.readouterr()
        assert "✓ Сертификат успешно создан:" in captured.out
        assert "example.com" in captured.out

    @pytest.mark.asyncio
    async def test_verify_certificate_not_found(self, cli, capsys):
        """Тест проверки несуществующего сертификата"""
        args = MagicMock()
        args.certificate_id = "ABCD1-XYZ12-QWRT5-WX0124"

        await cli.verify_certificate(args)

        captured = capsys.readouterr()
        assert "✗ Сертификат ABCD1-XYZ12-QWRT5-WX0124 не найден" in captured.out

    @pytest.mark.asyncio
    async def test_verify_certificate_found(self, cli, capsys):
        """Тест проверки существующего сертификата"""
        # Создаем тестовый сертификат
        certificate = Certificate(
            certificate_id="ABCD1-XYZ12-QWRT5-WX0124",
            domain="example.com",
            inn="7707083893",
            valid_from=datetime.now(),
            valid_to=datetime.now() + timedelta(days=30),
            users_count=100,
            created_at=datetime.now()
        )

        cli.db_storage.get_certificate.return_value = certificate

        args = MagicMock()
        args.certificate_id = "ABCD1-XYZ12-QWRT5-WX0124"

        await cli.verify_certificate(args)

        captured = capsys.readouterr()
        assert "✓ Сертификат найден:" in captured.out
        assert "example.com" in captured.out
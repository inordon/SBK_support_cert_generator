"""
Тесты для API
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import httpx
from fastapi.testclient import TestClient

from core.api import CertificateAPI
from core.models import Certificate


class TestCertificateAPI:
    """Тесты для API сертификатов"""

    @pytest.fixture
    def mock_db_storage(self):
        """Мок для БД"""
        mock = AsyncMock()
        mock.connect = AsyncMock()
        mock.disconnect = AsyncMock()
        mock.save_certificate = AsyncMock(return_value="test-uuid")
        mock.get_certificate = AsyncMock(return_value=None)
        mock.find_certificates_by_domain = AsyncMock(return_value=[])
        return mock

    @pytest.fixture
    def mock_file_storage(self):
        """Мок для файлового хранилища"""
        mock = MagicMock()
        mock.save_certificate = MagicMock(return_value="/path/to/file")
        return mock

    @pytest.fixture
    def api(self, mock_db_storage, mock_file_storage):
        """Фикстура для API"""
        return CertificateAPI(mock_db_storage, mock_file_storage, "test-api-key")

    @pytest.fixture
    def client(self, api):
        """Тестовый клиент"""
        return TestClient(api.app)

    def test_create_certificate_success(self, client, mock_db_storage, mock_file_storage):
        """Тест успешного создания сертификата"""
        tomorrow = datetime.now() + timedelta(days=1)
        next_month = tomorrow + timedelta(days=30)
        period = f"{tomorrow.strftime('%d.%m.%Y')}-{next_month.strftime('%d.%m.%Y')}"

        request_data = {
            "domain": "example.com",
            "inn": "7707083893",
            "period": period,
            "users_count": 100
        }

        response = client.post(
            "/certificates",
            json=request_data,
            headers={"Authorization": "Bearer test-api-key"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["domain"] == "example.com"
        assert data["inn"] == "7707083893"
        assert data["users_count"] == 100
        assert "certificate_id" in data

    def test_create_certificate_invalid_data(self, client):
        """Тест создания сертификата с невалидными данными"""
        request_data = {
            "domain": "invalid..domain",
            "inn": "invalid",
            "period": "invalid-period",
            "users_count": 0
        }

        response = client.post(
            "/certificates",
            json=request_data,
            headers={"Authorization": "Bearer test-api-key"}
        )

        assert response.status_code == 400

    def test_verify_certificate_not_found(self, client, mock_db_storage):
        """Тест проверки несуществующего сертификата"""
        mock_db_storage.get_certificate.return_value = None

        response = client.get(
            "/certificates/ABCD1-XYZ12-QWRT5-WX0124/verify",
            headers={"Authorization": "Bearer test-api-key"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["exists"] is False
        assert data["valid"] is False

    def test_verify_certificate_invalid_format(self, client):
        """Тест проверки сертификата с неверным форматом ID"""
        response = client.get(
            "/certificates/invalid-format/verify",
            headers={"Authorization": "Bearer test-api-key"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["exists"] is False
        assert data["valid"] is False
        assert "Неверный формат" in data["message"]

    def test_unauthorized_request(self, client):
        """Тест неавторизованного запроса"""
        response = client.post(
            "/certificates",
            json={"domain": "example.com"}
        )

        assert response.status_code == 401

    def test_health_check(self, client):
        """Тест проверки здоровья API"""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
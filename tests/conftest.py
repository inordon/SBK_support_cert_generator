"""
Общие фикстуры для тестов
"""
import pytest
import asyncio
from datetime import datetime, timedelta
import tempfile
import os

from core.models import Certificate


@pytest.fixture
def sample_certificate():
    """Образец сертификата для тестов"""
    return Certificate(
        certificate_id="ABCD1-XYZ12-QWRT5-WX0124",
        domain="example.com",
        inn="7707083893",
        valid_from=datetime.now(),
        valid_to=datetime.now() + timedelta(days=30),
        users_count=100,
        created_at=datetime.now(),
        created_by=123456789
    )


@pytest.fixture
def temp_certificates_dir():
    """Временная директория для сертификатов"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def event_loop():
    """Фикстура для asyncio event loop"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
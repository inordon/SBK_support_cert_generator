"""
Основной модуль бизнес-логики системы сертификатов.
"""

from .service import get_certificate_service
from .models import Certificate, CertificateRequest, SearchRequest
from .generator import CertificateIDGenerator
from .validator import DataValidator
from .database import get_db_manager, get_certificate_repo
from .storage import get_file_storage, get_storage_manager

__version__ = "1.0.0"

__all__ = [
    'get_certificate_service',
    'Certificate',
    'CertificateRequest',
    'SearchRequest',
    'CertificateIDGenerator',
    'DataValidator',
    'get_db_manager',
    'get_certificate_repo',
    'get_file_storage',
    'get_storage_manager'
]
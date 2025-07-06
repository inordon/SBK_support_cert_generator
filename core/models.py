"""
Модели данных для системы сертификатов
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import uuid


@dataclass
class Certificate:
    """Модель сертификата"""
    certificate_id: str
    domain: str
    inn: str
    valid_from: datetime
    valid_to: datetime
    users_count: int
    created_at: datetime
    created_by: Optional[int] = None
    id: Optional[uuid.UUID] = None
    is_active: bool = True

    def to_dict(self) -> dict:
        """Преобразование в словарь для JSON"""
        return {
            "certificate_id": self.certificate_id,
            "domain": self.domain,
            "inn": self.inn,
            "validity_period": f"{self.valid_from.strftime('%d.%m.%Y')}-{self.valid_to.strftime('%d.%m.%Y')}",
            "users_count": self.users_count,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by
        }


@dataclass
class CertificateHistory:
    """Модель истории действий с сертификатом"""
    certificate_id: str
    action: str
    performed_at: datetime
    performed_by: Optional[int]
    details: dict
    id: Optional[uuid.UUID] = None
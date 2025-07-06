"""
Pydantic модели для валидации и сериализации данных сертификатов.
"""

from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, Field, validator
from .exceptions import *


class CertificateRequest(BaseModel):
    """Модель запроса на создание сертификата."""
    domain: str = Field(..., min_length=3, max_length=255, description="Доменное имя")
    inn: str = Field(..., min_length=10, max_length=12, description="ИНН организации")
    valid_from: date = Field(..., description="Дата начала действия")
    valid_to: date = Field(..., description="Дата окончания действия")
    users_count: int = Field(..., ge=1, le=1000, description="Количество пользователей")
    created_by: int = Field(..., description="Telegram ID создателя")

    @validator('domain')
    def validate_domain(cls, v):
        """Валидация доменного имени."""
        from .validator import DomainValidator
        validator = DomainValidator()
        if not validator.validate(v):
            raise DomainValidationError(f"Некорректный домен: {v}")
        return v.lower()

    @validator('inn')
    def validate_inn(cls, v):
        """Валидация ИНН."""
        from .validator import INNValidator
        validator = INNValidator()
        if not validator.validate(v):
            raise INNValidationError(f"Некорректный ИНН: {v}")
        return v

    @validator('valid_to')
    def validate_period(cls, v, values):
        """Валидация периода действия."""
        if 'valid_from' in values:
            valid_from = values['valid_from']
            if v <= valid_from:
                raise PeriodValidationError("Дата окончания должна быть позже даты начала")

            # Проверяем, что период не превышает 5 лет
            years_diff = (v - valid_from).days / 365.25
            if years_diff > 5:
                raise PeriodValidationError("Период действия не может превышать 5 лет")

            # Проверяем, что даты не в прошлом
            today = date.today()
            if valid_from < today:
                raise PeriodValidationError("Дата начала не может быть в прошлом")

        return v

    class Config:
        """Конфигурация модели."""
        schema_extra = {
            "example": {
                "domain": "example.com",
                "inn": "1234567890",
                "valid_from": "2024-01-01",
                "valid_to": "2024-12-31",
                "users_count": 100,
                "created_by": 123456789
            }
        }


class Certificate(BaseModel):
    """Модель сертификата."""
    id: Optional[str] = None
    certificate_id: str = Field(..., min_length=23, max_length=23, description="ID сертификата")
    domain: str = Field(..., description="Доменное имя")
    inn: str = Field(..., description="ИНН организации")
    valid_from: date = Field(..., description="Дата начала действия")
    valid_to: date = Field(..., description="Дата окончания действия")
    users_count: int = Field(..., description="Количество пользователей")
    created_at: datetime = Field(default_factory=datetime.now, description="Дата создания")
    created_by: int = Field(..., description="Telegram ID создателя")
    is_active: bool = Field(default=True, description="Активен ли сертификат")

    @property
    def validity_period(self) -> str:
        """Возвращает период действия в формате DD.MM.YYYY-DD.MM.YYYY."""
        return f"{self.valid_from.strftime('%d.%m.%Y')}-{self.valid_to.strftime('%d.%m.%Y')}"

    @property
    def is_expired(self) -> bool:
        """Проверяет, истек ли срок действия сертификата."""
        return date.today() > self.valid_to

    @property
    def days_left(self) -> int:
        """Возвращает количество дней до истечения срока действия."""
        return (self.valid_to - date.today()).days

    def to_dict(self) -> dict:
        """Конвертирует объект в словарь для JSON сериализации."""
        return {
            "certificate_id": self.certificate_id,
            "domain": self.domain,
            "inn": self.inn,
            "validity_period": self.validity_period,
            "users_count": self.users_count,
            "created_at": self.created_at.isoformat(),
            "created_by": str(self.created_by),
            "is_active": self.is_active,
            "is_expired": self.is_expired,
            "days_left": self.days_left
        }

    class Config:
        """Конфигурация модели."""
        orm_mode = True
        schema_extra = {
            "example": {
                "certificate_id": "A7K9M-X3P2R-Q8W1E-RT0524",
                "domain": "example.com",
                "inn": "1234567890",
                "valid_from": "2024-01-01",
                "valid_to": "2024-05-31",
                "users_count": 100,
                "created_at": "2024-01-01T10:00:00",
                "created_by": 123456789,
                "is_active": True
            }
        }


class CertificateHistory(BaseModel):
    """Модель записи истории изменений сертификата."""
    id: Optional[str] = None
    certificate_id: str = Field(..., description="ID сертификата")
    action: str = Field(..., description="Выполненное действие")
    performed_at: datetime = Field(default_factory=datetime.now, description="Время выполнения")
    performed_by: int = Field(..., description="Telegram ID пользователя")
    details: Optional[dict] = Field(default=None, description="Дополнительные детали")

    class Config:
        """Конфигурация модели."""
        orm_mode = True


class SearchRequest(BaseModel):
    """Модель запроса поиска сертификатов."""
    domain: Optional[str] = Field(None, description="Поиск по домену")
    inn: Optional[str] = Field(None, description="Поиск по ИНН")
    certificate_id: Optional[str] = Field(None, description="Поиск по ID сертификата")
    active_only: bool = Field(default=True, description="Только активные сертификаты")

    @validator('certificate_id')
    def validate_certificate_id_format(cls, v):
        """Валидация формата ID сертификата."""
        if v and len(v) != 23:
            raise ValidationError("Некорректный формат ID сертификата")
        return v

    class Config:
        """Конфигурация модели."""
        schema_extra = {
            "example": {
                "domain": "example.com",
                "inn": "1234567890",
                "certificate_id": "A7K9M-X3P2R-Q8W1E-RT0524",
                "active_only": True
            }
        }
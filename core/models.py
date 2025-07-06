# core/models.py - исправленная версия

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
    users_count: int = Field(..., ge=1, description="Количество пользователей")
    created_by: int = Field(..., description="Telegram ID создателя")

    @validator('domain')
    def validate_domain(cls, v):
        """Валидация доменного имени."""
        # Перенесем логику валидации сюда, избегая circular import
        domain = v.lower().strip()

        # Базовая валидация длины
        if not domain or len(domain) > 255:
            raise DomainValidationError(f"Некорректная длина домена: {domain}")

        # Проверка паттерна
        import re
        domain_pattern = re.compile(r'^(\*\.)?[a-zA-Z0-9]([a-zA-Z0-9.-]*[a-zA-Z0-9])?$')
        if not domain_pattern.match(domain):
            raise DomainValidationError(f"Некорректный формат домена: {domain}")

        # Обрабатываем wildcard
        test_domain = domain[2:] if domain.startswith('*.') else domain

        # Разделяем на части
        parts = test_domain.split('.')
        if len(parts) < 2:
            raise DomainValidationError(f"Домен должен содержать минимум 2 части: {domain}")

        # Валидируем каждую часть
        domain_part_pattern = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?$')
        for part in parts:
            if not part or len(part) > 63:
                raise DomainValidationError(f"Некорректная часть домена: {part}")
            if part.startswith('-') or part.endswith('-'):
                raise DomainValidationError(f"Часть домена не может начинаться или заканчиваться дефисом: {part}")
            if not domain_part_pattern.match(part):
                raise DomainValidationError(f"Некорректные символы в части домена: {part}")

        return domain

    @validator('inn')
    def validate_inn(cls, v):
        """Валидация ИНН."""
        inn = v.strip()

        if not inn or not inn.isdigit():
            raise INNValidationError(f"ИНН должен содержать только цифры: {inn}")

        if len(inn) == 10:
            # Валидация 10-значного ИНН
            coefficients = [2, 4, 10, 3, 5, 9, 4, 6, 8]
            checksum = sum(int(inn[i]) * coefficients[i] for i in range(9))
            control_digit = (checksum % 11) % 10
            if int(inn[9]) != control_digit:
                raise INNValidationError(f"Некорректная контрольная сумма ИНН: {inn}")
        elif len(inn) == 12:
            # Валидация 12-значного ИНН
            # Первая контрольная цифра
            coefficients_1 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
            checksum_1 = sum(int(inn[i]) * coefficients_1[i] for i in range(10))
            control_digit_1 = (checksum_1 % 11) % 10
            if int(inn[10]) != control_digit_1:
                raise INNValidationError(f"Некорректная первая контрольная сумма ИНН: {inn}")

            # Вторая контрольная цифра
            coefficients_2 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
            checksum_2 = sum(int(inn[i]) * coefficients_2[i] for i in range(11))
            control_digit_2 = (checksum_2 % 11) % 10
            if int(inn[11]) != control_digit_2:
                raise INNValidationError(f"Некорректная вторая контрольная сумма ИНН: {inn}")
        else:
            raise INNValidationError(f"ИНН должен содержать 10 или 12 цифр: {inn}")

        return inn

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
        json_schema_extra = {
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
        from_attributes = True
        json_schema_extra = {
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
        from_attributes = True


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
        json_schema_extra = {
            "example": {
                "domain": "example.com",
                "inn": "1234567890",
                "certificate_id": "A7K9M-X3P2R-Q8W1E-RT0524",
                "active_only": True
            }
        }
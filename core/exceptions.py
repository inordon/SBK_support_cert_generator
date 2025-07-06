"""
Кастомные исключения для системы сертификатов.
"""


class CertificateError(Exception):
    """Базовое исключение для всех ошибок сертификатов."""
    pass


class ValidationError(CertificateError):
    """Ошибка валидации входных данных."""
    pass


class DomainValidationError(ValidationError):
    """Ошибка валидации домена."""
    pass


class INNValidationError(ValidationError):
    """Ошибка валидации ИНН."""
    pass


class PeriodValidationError(ValidationError):
    """Ошибка валидации периода действия."""
    pass


class UsersCountValidationError(ValidationError):
    """Ошибка валидации количества пользователей."""
    pass


class CertificateNotFoundError(CertificateError):
    """Сертификат не найден."""
    pass


class CertificateExistsError(CertificateError):
    """Сертификат уже существует."""
    pass


class DatabaseError(CertificateError):
    """Ошибка работы с базой данных."""
    pass


class StorageError(CertificateError):
    """Ошибка работы с файловым хранилищем."""
    pass


class GenerationError(CertificateError):
    """Ошибка генерации сертификата."""
    pass
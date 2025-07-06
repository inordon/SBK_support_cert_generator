"""
API для работы с сертификатами
"""
import logging
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer
from pydantic import BaseModel

from .generator import CertificateGenerator
from .storage import DatabaseStorage, FileStorage, StorageError
from .validators import ValidationError


# Модели для API
class CertificateRequest(BaseModel):
    """Модель запроса на создание сертификата"""
    domain: str
    inn: str
    period: str  # DD.MM.YYYY-DD.MM.YYYY
    users_count: int
    created_by: Optional[int] = None


class CertificateResponse(BaseModel):
    """Модель ответа с сертификатом"""
    certificate_id: str
    domain: str
    inn: str
    validity_period: str
    users_count: int
    created_at: str
    created_by: Optional[int]
    status: str = "active"


class VerifyResponse(BaseModel):
    """Модель ответа проверки сертификата"""
    certificate_id: str
    exists: bool
    valid: bool
    details: Optional[CertificateResponse] = None
    message: str


class CertificateAPI:
    """API для работы с сертификатами"""

    def __init__(
            self,
            db_storage: DatabaseStorage,
            file_storage: FileStorage,
            api_key: Optional[str] = None
    ):
        self.db_storage = db_storage
        self.file_storage = file_storage
        self.generator = CertificateGenerator()
        self.api_key = api_key
        self.logger = logging.getLogger(__name__)

        # Создание FastAPI приложения
        self.app = FastAPI(
            title="Certificate Management API",
            description="API для управления сертификатами",
            version="1.0.0"
        )

        # Настройка безопасности
        if api_key:
            self.security = HTTPBearer()

        self._setup_routes()

    def _verify_api_key(self, token: str = Depends(HTTPBearer())) -> bool:
        """Проверка API ключа"""
        if self.api_key and token.credentials != self.api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return True

    def _setup_routes(self):
        """Настройка маршрутов API"""

        @self.app.post("/certificates", response_model=CertificateResponse)
        async def create_certificate(
                request: CertificateRequest,
                authorized: bool = Depends(self._verify_api_key) if self.api_key else True
        ):
            """Создание нового сертификата"""
            try:
                # Генерация сертификата
                certificate = self.generator.generate_certificate(
                    domain=request.domain,
                    inn=request.inn,
                    period=request.period,
                    users_count=request.users_count,
                    created_by=request.created_by
                )

                # Проверка на дубликаты по домену
                existing = await self.db_storage.find_certificates_by_domain(request.domain)
                if existing:
                    active_certs = [cert for cert in existing if cert.is_active]
                    if active_certs:
                        raise HTTPException(
                            status_code=409,
                            detail=f"Активный сертификат для домена {request.domain} уже существует"
                        )

                # Сохранение в БД
                cert_uuid = await self.db_storage.save_certificate(certificate)
                certificate.id = cert_uuid

                # Сохранение в файл
                file_path = self.file_storage.save_certificate(certificate)

                self.logger.info(
                    f"Создан сертификат {certificate.certificate_id} "
                    f"для домена {certificate.domain}, файл: {file_path}"
                )

                return CertificateResponse(
                    certificate_id=certificate.certificate_id,
                    domain=certificate.domain,
                    inn=certificate.inn,
                    validity_period=f"{certificate.valid_from.strftime('%d.%m.%Y')}-{certificate.valid_to.strftime('%d.%m.%Y')}",
                    users_count=certificate.users_count,
                    created_at=certificate.created_at.isoformat(),
                    created_by=certificate.created_by
                )

            except ValidationError as e:
                self.logger.warning(f"Ошибка валидации: {e}")
                raise HTTPException(status_code=400, detail=str(e))
            except StorageError as e:
                self.logger.error(f"Ошибка сохранения: {e}")
                raise HTTPException(status_code=500, detail="Ошибка сохранения сертификата")
            except Exception as e:
                self.logger.error(f"Неожиданная ошибка: {e}")
                raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

        @self.app.get("/certificates/{certificate_id}/verify", response_model=VerifyResponse)
        async def verify_certificate(
                certificate_id: str,
                authorized: bool = Depends(self._verify_api_key) if self.api_key else True
        ):
            """Проверка сертификата"""
            try:
                # Проверка формата ID
                if not self.generator.verify_certificate_id_format(certificate_id):
                    return VerifyResponse(
                        certificate_id=certificate_id,
                        exists=False,
                        valid=False,
                        message="Неверный формат ID сертификата"
                    )

                # Поиск в БД
                certificate = await self.db_storage.get_certificate(certificate_id)

                if not certificate:
                    return VerifyResponse(
                        certificate_id=certificate_id,
                        exists=False,
                        valid=False,
                        message="Сертификат не найден"
                    )

                # Проверка активности
                if not certificate.is_active:
                    return VerifyResponse(
                        certificate_id=certificate_id,
                        exists=True,
                        valid=False,
                        message="Сертификат деактивирован"
                    )

                # Проверка срока действия
                from datetime import datetime
                now = datetime.now()
                if now < certificate.valid_from or now > certificate.valid_to:
                    return VerifyResponse(
                        certificate_id=certificate_id,
                        exists=True,
                        valid=False,
                        details=CertificateResponse(
                            certificate_id=certificate.certificate_id,
                            domain=certificate.domain,
                            inn=certificate.inn,
                            validity_period=f"{certificate.valid_from.strftime('%d.%m.%Y')}-{certificate.valid_to.strftime('%d.%m.%Y')}",
                            users_count=certificate.users_count,
                            created_at=certificate.created_at.isoformat(),
                            created_by=certificate.created_by,
                            status="expired" if now > certificate.valid_to else "not_yet_valid"
                        ),
                        message="Сертификат не действителен по времени"
                    )

                # Сертификат валиден
                return VerifyResponse(
                    certificate_id=certificate_id,
                    exists=True,
                    valid=True,
                    details=CertificateResponse(
                        certificate_id=certificate.certificate_id,
                        domain=certificate.domain,
                        inn=certificate.inn,
                        validity_period=f"{certificate.valid_from.strftime('%d.%m.%Y')}-{certificate.valid_to.strftime('%d.%m.%Y')}",
                        users_count=certificate.users_count,
                        created_at=certificate.created_at.isoformat(),
                        created_by=certificate.created_by
                    ),
                    message="Сертификат действителен"
                )

            except Exception as e:
                self.logger.error(f"Ошибка проверки сертификата: {e}")
                raise HTTPException(status_code=500, detail="Ошибка проверки сертификата")

        @self.app.get("/certificates/domain/{domain}", response_model=List[CertificateResponse])
        async def get_certificates_by_domain(
                domain: str,
                authorized: bool = Depends(self._verify_api_key) if self.api_key else True
        ):
            """Получение сертификатов по домену"""
            try:
                certificates = await self.db_storage.find_certificates_by_domain(domain)

                return [
                    CertificateResponse(
                        certificate_id=cert.certificate_id,
                        domain=cert.domain,
                        inn=cert.inn,
                        validity_period=f"{cert.valid_from.strftime('%d.%m.%Y')}-{cert.valid_to.strftime('%d.%m.%Y')}",
                        users_count=cert.users_count,
                        created_at=cert.created_at.isoformat(),
                        created_by=cert.created_by,
                        status="active" if cert.is_active else "inactive"
                    )
                    for cert in certificates
                ]

            except Exception as e:
                self.logger.error(f"Ошибка получения сертификатов: {e}")
                raise HTTPException(status_code=500, detail="Ошибка получения сертификатов")

        @self.app.get("/health")
        async def health_check():
            """Проверка здоровья API"""
            return {"status": "healthy", "timestamp": "2024-07-06T12:00:00Z"}
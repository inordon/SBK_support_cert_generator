"""
Основная бизнес-логика для работы с сертификатами - обновленная версия.
"""

import logging
from datetime import datetime, date
from typing import List, Optional, Dict, Tuple
from .models import Certificate, CertificateRequest, SearchRequest, EditCertificateDatesRequest
from .database import get_certificate_repo, Certificate as DBCertificate
from .storage import get_storage_manager
from .generator import CertificateIDGenerator
from .validators import DataValidator
from .exceptions import *

# Настройка логирования
logger = logging.getLogger(__name__)


class CertificateService:
    """Сервис для работы с сертификатами."""

    def __init__(self):
        """Инициализация сервиса."""
        self.certificate_repo = get_certificate_repo()
        self.storage_manager = get_storage_manager()
        self.id_generator = CertificateIDGenerator()
        self.validator = DataValidator()

    def create_certificate(self, request: CertificateRequest) -> Tuple[Certificate, bool]:
        """
        Создает новый сертификат.

        Args:
            request: Запрос на создание сертификата

        Returns:
            Tuple[Certificate, bool]: Созданный сертификат и флаг о наличии существующих

        Raises:
            ValidationError: При ошибке валидации
            GenerationError: При ошибке генерации ID
            DatabaseError: При ошибке БД
        """
        logger.info(f"Создание сертификата для домена {request.domain} пользователем {request.created_by}")

        try:
            # Проверяем существующие сертификаты для домена
            existing_certificates = self.certificate_repo.get_certificates_by_domain(
                request.domain, active_only=True
            )
            has_existing = len(existing_certificates) > 0

            # Получаем все существующие ID для проверки уникальности
            existing_ids = self.certificate_repo.get_existing_certificate_ids()

            # Генерируем уникальный ID
            certificate_id = self.id_generator.generate(request.valid_to, existing_ids)

            # Создаем объект сертификата для БД
            db_certificate_data = {
                "certificate_id": certificate_id,
                "domain": request.domain,
                "inn": request.inn,
                "valid_from": request.valid_from,
                "valid_to": request.valid_to,
                "users_count": request.users_count,
                "created_by": str(request.created_by),
                "created_by_username": request.created_by_username,
                "created_by_full_name": request.created_by_full_name,
                "is_active": True,
                "request_email": request.request_email,
                "contacts": request.contacts
            }

            # Сохраняем в БД
            db_certificate = self.certificate_repo.create_certificate(db_certificate_data)

            # Создаем Pydantic модель для возврата из данных БД
            certificate = self._convert_db_to_pydantic(db_certificate)

            # Сохраняем в файловое хранилище
            try:
                self.storage_manager.save_certificate_complete(certificate)
                logger.info(f"Сертификат {certificate_id} сохранен в файловое хранилище")
            except Exception as e:
                logger.warning(f"Ошибка сохранения сертификата в файл: {e}")

            logger.info(f"Сертификат {certificate_id} успешно создан")
            return certificate, has_existing

        except Exception as e:
            logger.error(f"Ошибка создания сертификата: {e}")
            if isinstance(e, (ValidationError, GenerationError, DatabaseError)):
                raise
            raise DatabaseError(f"Неожиданная ошибка при создании сертификата: {e}")

    def edit_certificate_dates(self, edit_request: EditCertificateDatesRequest) -> Certificate:
        """
        Редактирует даты действия сертификата.

        Args:
            edit_request: Запрос на редактирование дат

        Returns:
            Certificate: Обновленный сертификат

        Raises:
            CertificateNotFoundError: Если сертификат не найден
            ValidationError: При ошибке валидации
        """
        logger.info(f"Редактирование дат сертификата {edit_request.certificate_id} пользователем {edit_request.edited_by}")

        try:
            # Находим сертификат в БД
            db_certificate = self.certificate_repo.get_certificate_by_id(edit_request.certificate_id)
            if not db_certificate:
                raise CertificateNotFoundError(f"Сертификат {edit_request.certificate_id} не найден")

            # Обновляем даты
            success = self.certificate_repo.update_certificate_dates(
                edit_request.certificate_id,
                edit_request.new_valid_from,
                edit_request.new_valid_to,
                str(edit_request.edited_by),
                edit_request.edit_reason
            )

            if not success:
                raise DatabaseError("Не удалось обновить даты сертификата")

            # Получаем обновленный сертификат
            updated_db_certificate = self.certificate_repo.get_certificate_by_id(edit_request.certificate_id)
            updated_certificate = self._convert_db_to_pydantic(updated_db_certificate)

            # Обновляем файл сертификата
            try:
                self.storage_manager.save_certificate_complete(updated_certificate)
                logger.info(f"Файл сертификата {edit_request.certificate_id} обновлен")
            except Exception as e:
                logger.warning(f"Ошибка обновления файла сертификата: {e}")

            logger.info(f"Даты сертификата {edit_request.certificate_id} успешно обновлены")
            return updated_certificate

        except Exception as e:
            logger.error(f"Ошибка редактирования дат сертификата {edit_request.certificate_id}: {e}")
            if isinstance(e, (CertificateNotFoundError, ValidationError, DatabaseError)):
                raise
            raise DatabaseError(f"Неожиданная ошибка при редактировании дат: {e}")

    def verify_certificate(self, certificate_id: str, user_id: int) -> Optional[Certificate]:
        """
        Проверяет сертификат по ID.

        Args:
            certificate_id: ID сертификата
            user_id: ID пользователя, выполняющего проверку

        Returns:
            Optional[Certificate]: Сертификат или None если не найден
        """
        logger.info(f"Проверка сертификата {certificate_id} пользователем {user_id}")

        try:
            # Валидируем формат ID
            if not self.id_generator.validate_id_format(certificate_id):
                logger.warning(f"Некорректный формат ID сертификата: {certificate_id}")
                raise ValidationError("Некорректный формат ID сертификата")

            # Ищем сертификат в БД
            db_certificate = self.certificate_repo.get_certificate_by_id(certificate_id)

            if not db_certificate:
                logger.info(f"Сертификат {certificate_id} не найден")
                return None

            # Записываем факт проверки
            self.certificate_repo.add_verification_record(
                certificate_id,
                str(user_id),
                {"verified_at": datetime.now().isoformat()}
            )

            # Создаем Pydantic модель
            certificate = self._convert_db_to_pydantic(db_certificate)

            logger.info(f"Сертификат {certificate_id} успешно проверен")
            return certificate

        except Exception as e:
            logger.error(f"Ошибка проверки сертификата {certificate_id}: {e}")
            if isinstance(e, ValidationError):
                raise
            raise DatabaseError(f"Ошибка при проверке сертификата: {e}")

    def search_certificates(self, search_request: SearchRequest) -> List[Certificate]:
        """
        Поиск сертификатов по критериям.

        Args:
            search_request: Параметры поиска

        Returns:
            List[Certificate]: Список найденных сертификатов
        """
        logger.info(f"Поиск сертификатов: домен={search_request.domain}, ИНН={search_request.inn}")

        try:
            db_certificates = self.certificate_repo.search_certificates(
                domain=search_request.domain,
                inn=search_request.inn,
                active_only=search_request.active_only
            )

            # Конвертируем в Pydantic модели
            certificates = [self._convert_db_to_pydantic(db_cert) for db_cert in db_certificates]

            logger.info(f"Найдено сертификатов: {len(certificates)}")
            return certificates

        except Exception as e:
            logger.error(f"Ошибка поиска сертификатов: {e}")
            raise DatabaseError(f"Ошибка при поиске сертификатов: {e}")

    def get_user_certificates(self, user_id: int, active_only: bool = True) -> List[Certificate]:
        """
        Получает сертификаты, созданные пользователем.

        Args:
            user_id: ID пользователя
            active_only: Только активные сертификаты

        Returns:
            List[Certificate]: Список сертификатов пользователя
        """
        logger.info(f"Получение сертификатов пользователя {user_id}")

        try:
            db_certificates = self.certificate_repo.get_certificates_by_user(
                str(user_id), active_only
            )

            certificates = [self._convert_db_to_pydantic(db_cert) for db_cert in db_certificates]
            return certificates

        except Exception as e:
            logger.error(f"Ошибка получения сертификатов пользователя {user_id}: {e}")
            raise DatabaseError(f"Ошибка при получении сертификатов пользователя: {e}")

    def deactivate_certificate(self, certificate_id: str, user_id: int) -> bool:
        """
        Деактивирует сертификат.

        Args:
            certificate_id: ID сертификата
            user_id: ID пользователя

        Returns:
            bool: True если сертификат деактивирован
        """
        logger.info(f"Деактивация сертификата {certificate_id} пользователем {user_id}")

        try:
            result = self.certificate_repo.deactivate_certificate(certificate_id, str(user_id))

            if result:
                logger.info(f"Сертификат {certificate_id} успешно деактивирован")
            else:
                logger.warning(f"Сертификат {certificate_id} не найден для деактивации")

            return result

        except Exception as e:
            logger.error(f"Ошибка деактивации сертификата {certificate_id}: {e}")
            raise DatabaseError(f"Ошибка при деактивации сертификата: {e}")

    def get_statistics(self) -> Dict:
        """
        Получает статистику по сертификатам.

        Returns:
            Dict: Статистика
        """
        logger.info("Получение статистики сертификатов")

        try:
            db_stats = self.certificate_repo.get_statistics()
            file_stats = self.storage_manager.file_storage.get_storage_stats()

            return {
                "database": db_stats,
                "file_storage": file_stats,
                "last_updated": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            raise DatabaseError(f"Ошибка при получении статистики: {e}")

    def validate_certificate_data(self, domain: str, inn: str, valid_from: date,
                                  valid_to: date, users_count: int) -> List[str]:
        """
        Валидирует данные сертификата.

        Args:
            domain: Доменное имя
            inn: ИНН
            valid_from: Дата начала действия
            valid_to: Дата окончания действия
            users_count: Количество пользователей

        Returns:
            List[str]: Список ошибок валидации
        """
        return self.validator.validate_all(domain, inn, valid_from, valid_to, users_count)

    def format_certificate_info(self, certificate: Certificate, detailed: bool = False) -> str:
        """
        Форматирует информацию о сертификате для отображения с правильным статусом.

        Args:
            certificate: Сертификат
            detailed: Подробная информация

        Returns:
            str: Отформатированная информация
        """
        status = certificate.status_info

        info = [
            f"🆔 ID: {certificate.certificate_id}",
            f"🌐 Домен: {certificate.domain}",
            f"🏢 ИНН: {certificate.inn}",
            f"📅 Период: {certificate.validity_period}",
            f"👥 Пользователей: {certificate.users_count}",
            f"{status['emoji']} Статус: {status['text']}"
        ]

        if certificate.request_email:
            info.append(f"📧 Email для запросов: {certificate.request_email}")

        if certificate.contacts:
            contacts_lines = []
            for c in certificate.contacts:
                contacts_lines.append(f"  • {c.get('name', '')} ({c.get('email', '')})")
            info.append("👤 Контактные лица:\n" + "\n".join(contacts_lines))

        if detailed:
            # Безопасно обрабатываем имя создателя
            creator_name = certificate.creator_display_name or f"ID: {certificate.created_by}"
            info.extend([
                f"📝 Создан: {certificate.created_at.strftime('%d.%m.%Y %H:%M')}",
                f"🔧 Создатель: {creator_name}"
            ])

        return "\n".join(info)

    def format_certificates_list(self, certificates: List[Certificate],
                                 max_items: int = 10) -> str:
        """
        Форматирует список сертификатов для отображения с правильными статусами.

        Args:
            certificates: Список сертификатов
            max_items: Максимальное количество элементов для отображения

        Returns:
            str: Отформатированный список
        """
        if not certificates:
            return "📝 Сертификаты не найдены"

        items = []
        for i, cert in enumerate(certificates[:max_items], 1):
            status = cert.status_info
            emoji = status['emoji']

            # Краткая информация о статусе
            if status['status'] == 'not_started':
                status_text = f"начнется {cert.valid_from.strftime('%d.%m')}"
            elif status['status'] in ['expired']:
                status_text = f"истек {cert.valid_to.strftime('%d.%m')}"
            elif status['status'] in ['expiring_very_soon', 'expiring_soon']:
                status_text = f"{status['days_left']}д"
            elif status['status'] == 'active':
                status_text = f"{status['days_left']}д"
            else:
                status_text = "неактивен"

            items.append(f"{i}. {emoji} {cert.domain} ({cert.certificate_id[:11]}...) - {status_text}")

        result = "\n".join(items)

        if len(certificates) > max_items:
            result += f"\n\n... и еще {len(certificates) - max_items} сертификатов"

        return result

    def _convert_db_to_pydantic(self, db_certificate: DBCertificate) -> Certificate:
        """
        Конвертирует объект БД в Pydantic модель.

        Args:
            db_certificate: Объект сертификата из БД

        Returns:
            Certificate: Pydantic модель сертификата
        """
        # Получаем значения с проверкой на None
        is_active = getattr(db_certificate, 'is_active', True)
        if is_active is None:
            is_active = True

        created_by = getattr(db_certificate, 'created_by', '0')
        try:
            created_by_int = int(created_by) if created_by else 0
        except (ValueError, TypeError):
            created_by_int = 0

        return Certificate(
            id=str(db_certificate.id),
            certificate_id=db_certificate.certificate_id,
            domain=db_certificate.domain,
            inn=db_certificate.inn,
            valid_from=db_certificate.valid_from,
            valid_to=db_certificate.valid_to,
            users_count=db_certificate.users_count,
            created_at=db_certificate.created_at,
            created_by=created_by_int,
            created_by_username=getattr(db_certificate, 'created_by_username', None),
            created_by_full_name=getattr(db_certificate, 'created_by_full_name', None),
            is_active=is_active,
            request_email=getattr(db_certificate, 'request_email', None),
            contacts=getattr(db_certificate, 'contacts', None)
        )


# Глобальный экземпляр сервиса
certificate_service = CertificateService()


def get_certificate_service() -> CertificateService:
    """Возвращает экземпляр сервиса сертификатов."""
    return certificate_service
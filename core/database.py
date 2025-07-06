# core/database.py - критические исправления

"""
Модели SQLAlchemy для работы с базой данных.
"""

import uuid
from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import (
    create_engine, Column, String, Integer, DateTime, Date,
    Boolean, Text, Index, UniqueConstraint, text
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from config.settings import get_settings

# Базовый класс для моделей
Base = declarative_base()


class Certificate(Base):
    """Модель сертификата."""

    __tablename__ = "certificates"

    # Основные поля
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    certificate_id = Column(String(23), unique=True, nullable=False, index=True)
    domain = Column(String(255), nullable=False, index=True)
    inn = Column(String(12), nullable=False, index=True)
    valid_from = Column(Date, nullable=False, index=True)
    valid_to = Column(Date, nullable=False, index=True)
    users_count = Column(Integer, nullable=False)

    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by = Column(String(20), nullable=False)  # Telegram user ID как строка
    is_active = Column(Boolean, default=True, server_default=text('true'), nullable=False, index=True)

    # Индексы для оптимизации поиска
    __table_args__ = (
        Index('idx_certificate_active_domain', 'domain', 'is_active'),
        Index('idx_certificate_active_inn', 'inn', 'is_active'),
        Index('idx_certificate_validity', 'valid_from', 'valid_to'),
        Index('idx_certificate_created_by', 'created_by'),
    )

    def __repr__(self):
        return f"<Certificate(id={self.certificate_id}, domain={self.domain})>"

    @property
    def is_expired(self) -> bool:
        """Проверяет, истек ли срок действия сертификата."""
        return date.today() > self.valid_to

    @property
    def days_left(self) -> int:
        """Возвращает количество дней до истечения срока действия."""
        return (self.valid_to - date.today()).days

    @property
    def validity_period(self) -> str:
        """Возвращает период действия в формате DD.MM.YYYY-DD.MM.YYYY."""
        return f"{self.valid_from.strftime('%d.%m.%Y')}-{self.valid_to.strftime('%d.%m.%Y')}"

    def to_dict(self) -> dict:
        """Конвертирует объект в словарь."""
        return {
            "id": str(self.id),
            "certificate_id": self.certificate_id,
            "domain": self.domain,
            "inn": self.inn,
            "valid_from": self.valid_from.isoformat(),
            "valid_to": self.valid_to.isoformat(),
            "validity_period": self.validity_period,
            "users_count": self.users_count,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "is_active": self.is_active,
            "is_expired": self.is_expired,
            "days_left": self.days_left
        }


class CertificateHistory(Base):
    """Модель истории изменений сертификатов."""

    __tablename__ = "certificate_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    certificate_id = Column(String(23), nullable=False, index=True)
    action = Column(String(50), nullable=False)  # 'created', 'verified', 'deactivated', etc.
    performed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    performed_by = Column(String(20), nullable=False)  # Telegram user ID
    details = Column(JSONB, nullable=True)  # Дополнительная информация в JSON

    # Индексы
    __table_args__ = (
        Index('idx_history_certificate_id', 'certificate_id'),
        Index('idx_history_performed_at', 'performed_at'),
        Index('idx_history_action', 'action'),
    )

    def __repr__(self):
        return f"<CertificateHistory(certificate_id={self.certificate_id}, action={self.action})>"


class DatabaseManager:
    """Менеджер для работы с базой данных."""

    def __init__(self, database_url: str = None):
        """
        Инициализация менеджера БД.

        Args:
            database_url: URL подключения к БД
        """
        if database_url is None:
            settings = get_settings()
            database_url = settings.database_url

        self.engine = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False  # Установить True для отладки SQL запросов
        )

        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

        # Добавляем ссылку на модели для использования в репозитории
        self.Certificate = Certificate
        self.CertificateHistory = CertificateHistory

    def create_tables(self):
        """Создает все таблицы в базе данных."""
        Base.metadata.create_all(bind=self.engine)
        print("Таблицы базы данных созданы успешно")

    def drop_tables(self):
        """Удаляет все таблицы из базы данных."""
        Base.metadata.drop_all(bind=self.engine)
        print("Таблицы базы данных удалены")

    def get_session(self) -> Session:
        """Возвращает новую сессию для работы с БД."""
        return self.SessionLocal()

    def health_check(self) -> bool:
        """Проверяет подключение к базе данных."""
        try:
            with self.get_session() as session:
                session.execute(text("SELECT 1"))
                return True
        except Exception as e:
            print(f"Ошибка подключения к БД: {e}")
            return False


class CertificateRepository:
    """Репозиторий для работы с сертификатами."""

    def __init__(self, db_manager: DatabaseManager):
        """
        Инициализация репозитория.

        Args:
            db_manager: Менеджер базы данных
        """
        self.db_manager = db_manager

    def create_certificate(self, certificate_data: dict) -> Certificate:
        """
        Создает новый сертификат.

        Args:
            certificate_data: Данные сертификата

        Returns:
            Certificate: Созданный сертификат
        """
        with self.db_manager.get_session() as session:
            certificate = Certificate(**certificate_data)
            session.add(certificate)
            session.commit()

            # Сохраняем все данные в переменные ДО закрытия сессии
            cert_id = certificate.id
            cert_certificate_id = certificate.certificate_id
            cert_domain = certificate.domain
            cert_inn = certificate.inn
            cert_valid_from = certificate.valid_from
            cert_valid_to = certificate.valid_to
            cert_users_count = certificate.users_count
            cert_created_at = certificate.created_at
            cert_created_by = certificate.created_by
            cert_is_active = certificate.is_active

            # Добавляем запись в историю
            self._add_history_record(
                session,
                cert_certificate_id,
                "created",
                cert_created_by,
                {"domain": cert_domain, "inn": cert_inn}
            )
            session.commit()

        # Создаем новый объект Certificate ВНЕ контекста сессии
        new_certificate = Certificate()
        new_certificate.id = cert_id
        new_certificate.certificate_id = cert_certificate_id
        new_certificate.domain = cert_domain
        new_certificate.inn = cert_inn
        new_certificate.valid_from = cert_valid_from
        new_certificate.valid_to = cert_valid_to
        new_certificate.users_count = cert_users_count
        new_certificate.created_at = cert_created_at
        new_certificate.created_by = cert_created_by
        new_certificate.is_active = cert_is_active

        return new_certificate

    def get_certificate_by_id(self, certificate_id: str) -> Optional[Certificate]:
        """
        Получает сертификат по ID.

        Args:
            certificate_id: ID сертификата

        Returns:
            Optional[Certificate]: Сертификат или None
        """
        with self.db_manager.get_session() as session:
            return session.query(Certificate).filter(
                Certificate.certificate_id == certificate_id
            ).first()

    def get_certificates_by_domain(self, domain: str, active_only: bool = True) -> List[Certificate]:
        """
        Получает сертификаты по домену.

        Args:
            domain: Доменное имя
            active_only: Только активные сертификаты

        Returns:
            List[Certificate]: Список сертификатов
        """
        with self.db_manager.get_session() as session:
            query = session.query(Certificate).filter(Certificate.domain == domain)

            if active_only:
                query = query.filter(Certificate.is_active == True)

            return query.order_by(Certificate.created_at.desc()).all()

    def get_certificates_by_inn(self, inn: str, active_only: bool = True) -> List[Certificate]:
        """
        Получает сертификаты по ИНН.

        Args:
            inn: ИНН организации
            active_only: Только активные сертификаты

        Returns:
            List[Certificate]: Список сертификатов
        """
        with self.db_manager.get_session() as session:
            query = session.query(Certificate).filter(Certificate.inn == inn)

            if active_only:
                query = query.filter(Certificate.is_active == True)

            return query.order_by(Certificate.created_at.desc()).all()

    def get_certificates_by_user(self, user_id: str, active_only: bool = True) -> List[Certificate]:
        """
        Получает сертификаты, созданные пользователем.

        Args:
            user_id: ID пользователя
            active_only: Только активные сертификаты

        Returns:
            List[Certificate]: Список сертификатов
        """
        with self.db_manager.get_session() as session:
            query = session.query(Certificate).filter(Certificate.created_by == str(user_id))

            if active_only:
                query = query.filter(Certificate.is_active == True)

            return query.order_by(Certificate.created_at.desc()).all()

    def search_certificates(self, domain: str = None, inn: str = None,
                            active_only: bool = True) -> List[Certificate]:
        """
        Поиск сертификатов по домену и/или ИНН.

        Args:
            domain: Доменное имя для поиска
            inn: ИНН для поиска
            active_only: Только активные сертификаты

        Returns:
            List[Certificate]: Список найденных сертификатов
        """
        with self.db_manager.get_session() as session:
            query = session.query(Certificate)

            if domain:
                query = query.filter(Certificate.domain.ilike(f"%{domain}%"))

            if inn:
                query = query.filter(Certificate.inn == inn)

            if active_only:
                query = query.filter(Certificate.is_active == True)

            return query.order_by(Certificate.created_at.desc()).all()

    def get_existing_certificate_ids(self) -> set[str]:
        """
        Получает множество всех существующих ID сертификатов.

        Returns:
            set[str]: Множество ID сертификатов
        """
        with self.db_manager.get_session() as session:
            result = session.query(Certificate.certificate_id).all()
            return {row.certificate_id for row in result}

    def deactivate_certificate(self, certificate_id: str, user_id: str) -> bool:
        """
        Деактивирует сертификат.

        Args:
            certificate_id: ID сертификата
            user_id: ID пользователя, выполняющего действие

        Returns:
            bool: True если сертификат деактивирован, False если не найден
        """
        with self.db_manager.get_session() as session:
            certificate = session.query(Certificate).filter(
                Certificate.certificate_id == certificate_id
            ).first()

            if certificate:
                certificate.is_active = False

                # Добавляем запись в историю
                self._add_history_record(
                    session,
                    certificate_id,
                    "deactivated",
                    user_id
                )

                session.commit()
                return True

            return False

    def add_verification_record(self, certificate_id: str, user_id: str, details: dict = None):
        """
        Добавляет запись о проверке сертификата.

        Args:
            certificate_id: ID сертификата
            user_id: ID пользователя
            details: Дополнительные детали
        """
        with self.db_manager.get_session() as session:
            self._add_history_record(session, certificate_id, "verified", user_id, details)
            session.commit()

    def _add_history_record(self, session: Session, certificate_id: str,
                            action: str, user_id: str, details: dict = None):
        """
        Добавляет запись в историю изменений.

        Args:
            session: Сессия БД
            certificate_id: ID сертификата
            action: Выполненное действие
            user_id: ID пользователя
            details: Дополнительные детали
        """
        history_record = CertificateHistory(
            certificate_id=certificate_id,
            action=action,
            performed_by=str(user_id),
            details=details
        )
        session.add(history_record)

    def get_certificate_history(self, certificate_id: str) -> List[CertificateHistory]:
        """
        Получает историю изменений сертификата.

        Args:
            certificate_id: ID сертификата

        Returns:
            List[CertificateHistory]: Список записей истории
        """
        with self.db_manager.get_session() as session:
            return session.query(CertificateHistory).filter(
                CertificateHistory.certificate_id == certificate_id
            ).order_by(CertificateHistory.performed_at.desc()).all()

    def get_statistics(self) -> dict:
        """
        Получает статистику по сертификатам.

        Returns:
            dict: Статистика
        """
        with self.db_manager.get_session() as session:
            total_certificates = session.query(Certificate).count()
            active_certificates = session.query(Certificate).filter(Certificate.is_active == True).count()
            expired_certificates = session.query(Certificate).filter(
                Certificate.valid_to < date.today(),
                Certificate.is_active == True
            ).count()

            return {
                "total_certificates": total_certificates,
                "active_certificates": active_certificates,
                "expired_certificates": expired_certificates,
                "inactive_certificates": total_certificates - active_certificates
            }


# Глобальный менеджер БД
db_manager = DatabaseManager()
certificate_repo = CertificateRepository(db_manager)


def get_db_manager() -> DatabaseManager:
    """Возвращает менеджер БД."""
    return db_manager


def get_certificate_repo() -> CertificateRepository:
    """Возвращает репозиторий сертификатов."""
    return certificate_repo


if __name__ == "__main__":
    # Тестирование подключения к БД
    if db_manager.health_check():
        print("✓ Подключение к базе данных успешно")
        db_manager.create_tables()
    else:
        print("✗ Не удалось подключиться к базе данных")
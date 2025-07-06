"""
Модуль для работы с хранилищем сертификатов
"""
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import asyncpg
from asyncpg import Pool

from .models import Certificate, CertificateHistory


class StorageError(Exception):
    """Исключение для ошибок хранилища"""
    pass


class DatabaseStorage:
    """Класс для работы с PostgreSQL"""

    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.pool: Optional[Pool] = None

    async def connect(self) -> None:
        """Подключение к базе данных"""
        try:
            self.pool = await asyncpg.create_pool(
                self.connection_string,
                min_size=5,
                max_size=20,
                command_timeout=60
            )
        except Exception as e:
            raise StorageError(f"Ошибка подключения к БД: {e}")

    async def disconnect(self) -> None:
        """Отключение от базы данных"""
        if self.pool:
            await self.pool.close()

    async def save_certificate(self, certificate: Certificate) -> uuid.UUID:
        """
        Сохранение сертификата в БД

        Args:
            certificate: Объект сертификата для сохранения

        Returns:
            UUID сохраненного сертификата

        Raises:
            StorageError: При ошибке сохранения
        """
        if not self.pool:
            raise StorageError("Нет подключения к БД")

        cert_uuid = uuid.uuid4()

        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO certificates 
                    (id, certificate_id, domain, inn, valid_from, valid_to, 
                     users_count, created_at, created_by, is_active)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    """,
                    cert_uuid,
                    certificate.certificate_id,
                    certificate.domain,
                    certificate.inn,
                    certificate.valid_from,
                    certificate.valid_to,
                    certificate.users_count,
                    certificate.created_at,
                    certificate.created_by,
                    certificate.is_active
                )

                # Запись в историю
                await self._log_history(
                    conn,
                    certificate.certificate_id,
                    "CREATE",
                    certificate.created_by,
                    {"domain": certificate.domain, "inn": certificate.inn}
                )

        except asyncpg.UniqueViolationError:
            raise StorageError("Сертификат с таким ID уже существует")
        except Exception as e:
            raise StorageError(f"Ошибка сохранения сертификата: {e}")

        return cert_uuid

    async def get_certificate(self, certificate_id: str) -> Optional[Certificate]:
        """
        Получение сертификата по ID

        Args:
            certificate_id: ID сертификата

        Returns:
            Объект сертификата или None если не найден
        """
        if not self.pool:
            raise StorageError("Нет подключения к БД")

        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, certificate_id, domain, inn, valid_from, valid_to,
                           users_count, created_at, created_by, is_active
                    FROM certificates 
                    WHERE certificate_id = $1
                    """,
                    certificate_id
                )

                if row:
                    return Certificate(
                        id=row['id'],
                        certificate_id=row['certificate_id'],
                        domain=row['domain'],
                        inn=row['inn'],
                        valid_from=row['valid_from'],
                        valid_to=row['valid_to'],
                        users_count=row['users_count'],
                        created_at=row['created_at'],
                        created_by=row['created_by'],
                        is_active=row['is_active']
                    )
                return None

        except Exception as e:
            raise StorageError(f"Ошибка получения сертификата: {e}")

    async def find_certificates_by_domain(self, domain: str) -> List[Certificate]:
        """
        Поиск сертификатов по домену

        Args:
            domain: Доменное имя

        Returns:
            Список сертификатов
        """
        if not self.pool:
            raise StorageError("Нет подключения к БД")

        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT id, certificate_id, domain, inn, valid_from, valid_to,
                           users_count, created_at, created_by, is_active
                    FROM certificates 
                    WHERE domain = $1 AND is_active = true
                    ORDER BY created_at DESC
                    """,
                    domain
                )

                certificates = []
                for row in rows:
                    certificates.append(Certificate(
                        id=row['id'],
                        certificate_id=row['certificate_id'],
                        domain=row['domain'],
                        inn=row['inn'],
                        valid_from=row['valid_from'],
                        valid_to=row['valid_to'],
                        users_count=row['users_count'],
                        created_at=row['created_at'],
                        created_by=row['created_by'],
                        is_active=row['is_active']
                    ))

                return certificates

        except Exception as e:
            raise StorageError(f"Ошибка поиска сертификатов: {e}")

    async def _log_history(
            self,
            conn,
            certificate_id: str,
            action: str,
            performed_by: Optional[int],
            details: dict
    ) -> None:
        """Запись действия в историю"""
        await conn.execute(
            """
            INSERT INTO certificate_history 
            (id, certificate_id, action, performed_at, performed_by, details)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            uuid.uuid4(),
            certificate_id,
            action,
            datetime.now(),
            performed_by,
            json.dumps(details)
        )


class FileStorage:
    """Класс для работы с файловым хранилищем"""

    def __init__(self, base_path: str = "certificates"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(exist_ok=True)

    def save_certificate(self, certificate: Certificate) -> Path:
        """
        Сохранение сертификата в файл

        Args:
            certificate: Объект сертификата

        Returns:
            Путь к сохраненному файлу
        """
        # Создание структуры папок: YYYY/MM/
        year = certificate.created_at.year
        month = certificate.created_at.month

        dir_path = self.base_path / str(year) / f"{month:02d}"
        dir_path.mkdir(parents=True, exist_ok=True)

        # Имя файла: domain_certificateID.json
        filename = f"{certificate.domain}_{certificate.certificate_id}.json"
        file_path = dir_path / filename

        # Сохранение JSON
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(certificate.to_dict(), f, ensure_ascii=False, indent=2)

            # Установка прав доступа
            os.chmod(file_path, 0o644)

            return file_path

        except Exception as e:
            raise StorageError(f"Ошибка сохранения файла: {e}")

    def load_certificate(self, certificate_id: str) -> Optional[Certificate]:
        """
        Загрузка сертификата из файла

        Args:
            certificate_id: ID сертификата

        Returns:
            Объект сертификата или None если не найден
        """
        # Поиск файла по всей структуре
        for year_dir in self.base_path.iterdir():
            if not year_dir.is_dir():
                continue

            for month_dir in year_dir.iterdir():
                if not month_dir.is_dir():
                    continue

                for file_path in month_dir.glob(f"*_{certificate_id}.json"):
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)

                        # Парсинг периода действия
                        period_parts = data['validity_period'].split('-')
                        valid_from = datetime.strptime(period_parts[0], '%d.%m.%Y')
                        valid_to = datetime.strptime(period_parts[1], '%d.%m.%Y')

                        return Certificate(
                            certificate_id=data['certificate_id'],
                            domain=data['domain'],
                            inn=data['inn'],
                            valid_from=valid_from,
                            valid_to=valid_to,
                            users_count=data['users_count'],
                            created_at=datetime.fromisoformat(data['created_at']),
                            created_by=data.get('created_by')
                        )

                    except Exception:
                        continue

        return None
"""
Модуль для работы с файловым хранилищем сертификатов.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict
from .models import Certificate
from .exceptions import StorageError
from config.settings import get_settings


class FileStorage:
    """Менеджер файлового хранилища сертификатов."""

    def __init__(self, base_path: Path = None):
        """
        Инициализация файлового хранилища.

        Args:
            base_path: Базовый путь к директории сертификатов
        """
        if base_path is None:
            settings = get_settings()
            base_path = settings.certificates_path

        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def save_certificate(self, certificate: Certificate) -> Path:
        """
        Сохраняет сертификат в JSON файл.

        Структура: certificates/YYYY/domain_certificateID.json

        Args:
            certificate: Объект сертификата для сохранения

        Returns:
            Path: Путь к сохраненному файлу

        Raises:
            StorageError: При ошибке сохранения файла
        """
        try:
            # Определяем год создания
            year = certificate.created_at.year

            # Создаем директорию для года
            year_dir = self.base_path / str(year)
            year_dir.mkdir(parents=True, exist_ok=True)

            # Формируем имя файла: domain_certificateID.json
            filename = f"{certificate.domain}_{certificate.certificate_id}.json"
            file_path = year_dir / filename

            # Подготавливаем данные для сохранения
            certificate_data = certificate.to_dict()

            # Сохраняем в JSON файл
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(certificate_data, f, ensure_ascii=False, indent=2)

            return file_path

        except Exception as e:
            raise StorageError(f"Ошибка сохранения сертификата в файл: {e}")

    def load_certificate(self, certificate_id: str) -> Optional[Dict]:
        """
        Загружает сертификат из JSON файла по ID.

        Args:
            certificate_id: ID сертификата

        Returns:
            Optional[Dict]: Данные сертификата или None если не найден
        """
        try:
            # Ищем файл во всех годовых директориях
            for year_dir in self.base_path.iterdir():
                if year_dir.is_dir() and year_dir.name.isdigit():
                    # Ищем файлы с нужным certificate_id
                    for file_path in year_dir.glob(f"*_{certificate_id}.json"):
                        with open(file_path, 'r', encoding='utf-8') as f:
                            return json.load(f)

            return None

        except Exception as e:
            raise StorageError(f"Ошибка загрузки сертификата из файла: {e}")

    def find_certificates_by_domain(self, domain: str) -> List[Dict]:
        """
        Находит все сертификаты для указанного домена.

        Args:
            domain: Доменное имя

        Returns:
            List[Dict]: Список найденных сертификатов
        """
        certificates = []

        try:
            # Ищем во всех годовых директориях
            for year_dir in self.base_path.iterdir():
                if year_dir.is_dir() and year_dir.name.isdigit():
                    # Ищем файлы с нужным доменом
                    for file_path in year_dir.glob(f"{domain}_*.json"):
                        with open(file_path, 'r', encoding='utf-8') as f:
                            certificate_data = json.load(f)
                            certificates.append(certificate_data)

            return certificates

        except Exception as e:
            raise StorageError(f"Ошибка поиска сертификатов по домену: {e}")

    def get_all_certificates(self) -> List[Dict]:
        """
        Получает все сертификаты из файлового хранилища.

        Returns:
            List[Dict]: Список всех сертификатов
        """
        certificates = []

        try:
            # Проходим по всем годовым директориям
            for year_dir in self.base_path.iterdir():
                if year_dir.is_dir() and year_dir.name.isdigit():
                    # Читаем все JSON файлы
                    for file_path in year_dir.glob("*.json"):
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                certificate_data = json.load(f)
                                certificates.append(certificate_data)
                        except Exception as e:
                            print(f"Ошибка чтения файла {file_path}: {e}")
                            continue

            return certificates

        except Exception as e:
            raise StorageError(f"Ошибка получения всех сертификатов: {e}")

    def delete_certificate(self, certificate_id: str, domain: str = None) -> bool:
        """
        Удаляет файл сертификата.

        Args:
            certificate_id: ID сертификата
            domain: Доменное имя (для ускорения поиска)

        Returns:
            bool: True если файл удален, False если не найден
        """
        try:
            # Если известен домен, ищем более эффективно
            if domain:
                for year_dir in self.base_path.iterdir():
                    if year_dir.is_dir() and year_dir.name.isdigit():
                        file_path = year_dir / f"{domain}_{certificate_id}.json"
                        if file_path.exists():
                            file_path.unlink()
                            return True
            else:
                # Ищем во всех директориях
                for year_dir in self.base_path.iterdir():
                    if year_dir.is_dir() and year_dir.name.isdigit():
                        for file_path in year_dir.glob(f"*_{certificate_id}.json"):
                            file_path.unlink()
                            return True

            return False

        except Exception as e:
            raise StorageError(f"Ошибка удаления сертификата: {e}")

    def backup_certificates(self, backup_path: Path = None) -> Path:
        """
        Создает резервную копию всех сертификатов.

        Args:
            backup_path: Путь для сохранения бэкапа

        Returns:
            Path: Путь к файлу резервной копии
        """
        if backup_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.base_path.parent / f"certificates_backup_{timestamp}.json"

        try:
            all_certificates = self.get_all_certificates()

            backup_data = {
                "created_at": datetime.now().isoformat(),
                "total_certificates": len(all_certificates),
                "certificates": all_certificates
            }

            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)

            return backup_path

        except Exception as e:
            raise StorageError(f"Ошибка создания резервной копии: {e}")

    def restore_from_backup(self, backup_path: Path) -> int:
        """
        Восстанавливает сертификаты из резервной копии.

        Args:
            backup_path: Путь к файлу резервной копии

        Returns:
            int: Количество восстановленных сертификатов
        """
        try:
            with open(backup_path, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)

            certificates = backup_data.get('certificates', [])
            restored_count = 0

            for cert_data in certificates:
                try:
                    # Создаем объект Certificate для сохранения
                    # Преобразуем строковые даты обратно в объекты datetime/date
                    cert_data_copy = cert_data.copy()

                    # Определяем год из created_at
                    created_at = datetime.fromisoformat(cert_data['created_at'])
                    year = created_at.year

                    # Создаем директорию для года
                    year_dir = self.base_path / str(year)
                    year_dir.mkdir(parents=True, exist_ok=True)

                    # Формируем путь к файлу
                    filename = f"{cert_data['domain']}_{cert_data['certificate_id']}.json"
                    file_path = year_dir / filename

                    # Сохраняем файл
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(cert_data, f, ensure_ascii=False, indent=2)

                    restored_count += 1

                except Exception as e:
                    print(f"Ошибка восстановления сертификата {cert_data.get('certificate_id', 'unknown')}: {e}")
                    continue

            return restored_count

        except Exception as e:
            raise StorageError(f"Ошибка восстановления из резервной копии: {e}")

    def cleanup_old_files(self, days_old: int = 365) -> int:
        """
        Удаляет старые файлы сертификатов.

        Args:
            days_old: Возраст файлов в днях для удаления

        Returns:
            int: Количество удаленных файлов
        """
        try:
            from datetime import timedelta

            cutoff_date = datetime.now() - timedelta(days=days_old)
            deleted_count = 0

            for year_dir in self.base_path.iterdir():
                if year_dir.is_dir() and year_dir.name.isdigit():
                    for file_path in year_dir.glob("*.json"):
                        # Проверяем время модификации файла
                        file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)

                        if file_mtime < cutoff_date:
                            try:
                                file_path.unlink()
                                deleted_count += 1
                            except Exception as e:
                                print(f"Ошибка удаления файла {file_path}: {e}")

            return deleted_count

        except Exception as e:
            raise StorageError(f"Ошибка очистки старых файлов: {e}")

    def get_storage_stats(self) -> Dict:
        """
        Получает статистику файлового хранилища.

        Returns:
            Dict: Статистика хранилища
        """
        try:
            total_files = 0
            total_size = 0
            years = []

            for year_dir in self.base_path.iterdir():
                if year_dir.is_dir() and year_dir.name.isdigit():
                    years.append(year_dir.name)
                    year_files = 0

                    for file_path in year_dir.glob("*.json"):
                        total_files += 1
                        year_files += 1
                        total_size += file_path.stat().st_size

            return {
                "total_files": total_files,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / 1024 / 1024, 2),
                "years_covered": sorted(years),
                "base_path": str(self.base_path)
            }

        except Exception as e:
            raise StorageError(f"Ошибка получения статистики хранилища: {e}")


class CertificateStorageManager:
    """Менеджер для координации работы с БД и файловым хранилищем."""

    def __init__(self, file_storage: FileStorage = None):
        """
        Инициализация менеджера хранилища.

        Args:
            file_storage: Экземпляр файлового хранилища
        """
        if file_storage is None:
            file_storage = FileStorage()

        self.file_storage = file_storage

    def save_certificate_complete(self, certificate: Certificate) -> Dict:
        """
        Полное сохранение сертификата (БД + файл).

        Args:
            certificate: Объект сертификата

        Returns:
            Dict: Результат операции
        """
        result = {
            "database_saved": False,
            "file_saved": False,
            "file_path": None,
            "errors": []
        }

        try:
            # Сохраняем в файловое хранилище
            file_path = self.file_storage.save_certificate(certificate)
            result["file_saved"] = True
            result["file_path"] = str(file_path)

        except Exception as e:
            result["errors"].append(f"Ошибка сохранения в файл: {e}")

        return result

    def load_certificate_complete(self, certificate_id: str) -> Optional[Dict]:
        """
        Загружает сертификат из файлового хранилища.

        Args:
            certificate_id: ID сертификата

        Returns:
            Optional[Dict]: Данные сертификата или None
        """
        try:
            return self.file_storage.load_certificate(certificate_id)
        except Exception as e:
            print(f"Ошибка загрузки сертификата {certificate_id}: {e}")
            return None

    def sync_database_to_files(self) -> Dict:
        """
        Синхронизирует данные из БД в файловое хранилище.

        Returns:
            Dict: Результат синхронизации
        """
        from .database import get_certificate_repo

        repo = get_certificate_repo()
        result = {
            "synced_count": 0,
            "errors": [],
            "total_certificates": 0
        }

        try:
            # Получаем все сертификаты из БД
            with repo.db_manager.get_session() as session:
                certificates = session.query(repo.db_manager.Certificate).all()
                result["total_certificates"] = len(certificates)

                for certificate in certificates:
                    try:
                        self.file_storage.save_certificate(certificate)
                        result["synced_count"] += 1
                    except Exception as e:
                        result["errors"].append(f"Ошибка синхронизации {certificate.certificate_id}: {e}")

        except Exception as e:
            result["errors"].append(f"Ошибка получения данных из БД: {e}")

        return result


# Глобальный экземпляр файлового хранилища
file_storage = FileStorage()
storage_manager = CertificateStorageManager(file_storage)


def get_file_storage() -> FileStorage:
    """Возвращает экземпляр файлового хранилища."""
    return file_storage


def get_storage_manager() -> CertificateStorageManager:
    """Возвращает менеджер хранилища."""
    return storage_manager


if __name__ == "__main__":
    # Тестирование файлового хранилища
    storage = FileStorage()

    # Получаем статистику
    stats = storage.get_storage_stats()
    print("Статистика файлового хранилища:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # Создаем резервную копию
    try:
        backup_path = storage.backup_certificates()
        print(f"\nРезервная копия создана: {backup_path}")
    except StorageError as e:
        print(f"Ошибка создания резервной копии: {e}")
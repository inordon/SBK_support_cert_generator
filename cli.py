"""
CLI интерфейс для генератора сертификатов
"""
import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# Добавляем путь к модулям
sys.path.append(str(Path(__file__).parent))

from core.generator import CertificateGenerator
from core.storage import DatabaseStorage, FileStorage
from core.validators import ValidationError


class CertificateCLI:
    """CLI интерфейс для работы с сертификатами"""

    def __init__(self):
        self.generator = CertificateGenerator()
        self.setup_logging()
        self.setup_storage()

    def setup_logging(self):
        """Настройка логирования"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('certificates.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def setup_storage(self):
        """Настройка хранилищ"""
        # Файловое хранилище
        certificates_dir = os.getenv('CERTIFICATES_DIR', 'certificates')
        self.file_storage = FileStorage(certificates_dir)

        # БД (если настроена)
        db_url = os.getenv('DATABASE_URL')
        if db_url:
            self.db_storage = DatabaseStorage(db_url)
        else:
            self.db_storage = None
            self.logger.warning("База данных не настроена, используется только файловое хранилище")

    async def generate_certificate(self, args):
        """Генерация сертификата через CLI"""
        try:
            # Генерация сертификата
            certificate = self.generator.generate_certificate(
                domain=args.domain,
                inn=args.inn,
                period=args.period,
                users_count=args.users
            )

            # Сохранение в файл
            file_path = self.file_storage.save_certificate(certificate)

            # Сохранение в БД (если доступна)
            if self.db_storage:
                try:
                    await self.db_storage.connect()
                    cert_uuid = await self.db_storage.save_certificate(certificate)
                    await self.db_storage.disconnect()
                    self.logger.info(f"Сертификат сохранен в БД с UUID: {cert_uuid}")
                except Exception as e:
                    self.logger.error(f"Ошибка сохранения в БД: {e}")

            print(f"✓ Сертификат успешно создан:")
            print(f"  ID: {certificate.certificate_id}")
            print(f"  Домен: {certificate.domain}")
            print(f"  ИНН: {certificate.inn}")
            print(f"  Период: {certificate.valid_from.strftime('%d.%m.%Y')}-{certificate.valid_to.strftime('%d.%m.%Y')}")
            print(f"  Пользователи: {certificate.users_count}")
            print(f"  Файл: {file_path}")

            self.logger.info(f"Создан сертификат {certificate.certificate_id}")

        except ValidationError as e:
            print(f"✗ Ошибка валидации: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"✗ Ошибка: {e}")
            self.logger.error(f"Ошибка генерации сертификата: {e}")
            sys.exit(1)

    async def verify_certificate(self, args):
        """Проверка сертификата через CLI"""
        certificate_id = args.certificate_id

        try:
            # Проверка формата
            if not self.generator.verify_certificate_id_format(certificate_id):
                print(f"✗ Неверный формат ID сертификата: {certificate_id}")
                return

            # Поиск в БД
            certificate = None
            if self.db_storage:
                try:
                    await self.db_storage.connect()
                    certificate = await self.db_storage.get_certificate(certificate_id)
                    await self.db_storage.disconnect()
                except Exception as e:
                    self.logger.warning(f"Ошибка поиска в БД: {e}")

            # Поиск в файлах (если не найден в БД)
            if not certificate:
                certificate = self.file_storage.load_certificate(certificate_id)

            if not certificate:
                print(f"✗ Сертификат {certificate_id} не найден")
                return

            # Проверка активности и срока действия
            from datetime import datetime
            now = datetime.now()

            print(f"✓ Сертификат найден:")
            print(f"  ID: {certificate.certificate_id}")
            print(f"  Домен: {certificate.domain}")
            print(f"  ИНН: {certificate.inn}")
            print(f"  Период: {certificate.valid_from.strftime('%d.%m.%Y')}-{certificate.valid_to.strftime('%d.%m.%Y')}")
            print(f"  Пользователи: {certificate.users_count}")
            print(f"  Создан: {certificate.created_at.strftime('%d.%m.%Y %H:%M')}")

            # Статус
            if not getattr(certificate, 'is_active', True):
                print("  Статус: ✗ ДЕАКТИВИРОВАН")
            elif now < certificate.valid_from:
                print("  Статус: ⏳ ЕЩЕ НЕ ДЕЙСТВУЕТ")
            elif now > certificate.valid_to:
                print("  Статус: ✗ ИСТЕК")
            else:
                print("  Статус: ✓ ДЕЙСТВИТЕЛЕН")

            self.logger.info(f"Проверен сертификат {certificate_id}")

        except Exception as e:
            print(f"✗ Ошибка проверки: {e}")
            self.logger.error(f"Ошибка проверки сертификата: {e}")
            sys.exit(1)

    def list_certificates(self, args):
        """Список сертификатов"""
        try:
            print("Список сертификатов в файловой системе:")

            certs_found = False
            for year_dir in self.file_storage.base_path.iterdir():
                if not year_dir.is_dir():
                    continue

                for month_dir in year_dir.iterdir():
                    if not month_dir.is_dir():
                        continue

                    for cert_file in month_dir.glob("*.json"):
                        certs_found = True
                        print(f"  {cert_file.name}")

            if not certs_found:
                print("  Сертификаты не найдены")

        except Exception as e:
            print(f"✗ Ошибка получения списка: {e}")
            self.logger.error(f"Ошибка получения списка сертификатов: {e}")

    def main(self):
        """Главная функция CLI"""
        parser = argparse.ArgumentParser(
            description="Генератор и проверка сертификатов",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Примеры использования:
  %(prog)s generate --domain example.com --inn 1234567890 --period "01.01.2024-31.12.2024" --users 100
  %(prog)s verify ABCD1-XYZ12-QWRT5-WX0124
  %(prog)s list
            """
        )

        subparsers = parser.add_subparsers(dest='command', help='Доступные команды')

        # Команда генерации
        gen_parser = subparsers.add_parser('generate', help='Генерация нового сертификата')
        gen_parser.add_argument('--domain', required=True, help='Доменное имя')
        gen_parser.add_argument('--inn', required=True, help='ИНН организации')
        gen_parser.add_argument('--period', required=True, help='Период действия (DD.MM.YYYY-DD.MM.YYYY)')
        gen_parser.add_argument('--users', type=int, required=True, help='Количество пользователей')

        # Команда проверки
        verify_parser = subparsers.add_parser('verify', help='Проверка сертификата')
        verify_parser.add_argument('certificate_id', help='ID сертификата для проверки')

        # Команда списка
        list_parser = subparsers.add_parser('list', help='Список сертификатов')

        args = parser.parse_args()

        if not args.command:
            parser.print_help()
            return

        if args.command == 'generate':
            asyncio.run(self.generate_certificate(args))
        elif args.command == 'verify':
            asyncio.run(self.verify_certificate(args))
        elif args.command == 'list':
            self.list_certificates(args)


if __name__ == '__main__':
    cli = CertificateCLI()
    cli.main()
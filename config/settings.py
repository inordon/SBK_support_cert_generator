# config/settings.py - добавим автосоздание директорий

"""
Настройки приложения, загружаемые из переменных окружения.
"""

import os
import json
from pathlib import Path
from typing import List, Set, Optional, Dict
from pydantic import Field, validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки приложения."""

    # Настройки бота
    bot_token: str = Field(..., env="BOT_TOKEN", description="Токен Telegram бота")
    admin_users: str = Field(..., env="ADMIN_USERS", description="ID администраторов через запятую")
    verify_users: str = Field(..., env="VERIFY_USERS", description="ID пользователей для проверки через запятую")
    notification_group: int = Field(..., env="NOTIFICATION_GROUP", description="ID группы для уведомлений")

    # Настройки базы данных
    db_host: str = Field(default="localhost", env="DB_HOST", description="Хост базы данных")
    db_port: int = Field(default=5432, env="DB_PORT", description="Порт базы данных")
    db_name: str = Field(..., env="DB_NAME", description="Имя базы данных")
    db_user: str = Field(..., env="DB_USER", description="Пользователь базы данных")
    db_password: str = Field(..., env="DB_PASSWORD", description="Пароль базы данных")

    # Настройки хранилища
    certificates_path: Path = Field(
        default=Path("./certificates"),
        env="CERTIFICATES_PATH",
        description="Путь к директории сертификатов"
    )

    # Настройки логирования
    log_level: str = Field(default="INFO", env="LOG_LEVEL", description="Уровень логирования")
    log_file: Path = Field(
        default=Path("./logs/bot.log"),
        env="LOG_FILE",
        description="Путь к файлу логов"
    )

    # Настройки приложения
    debug: bool = Field(default=False, env="DEBUG", description="Режим отладки")
    timezone: str = Field(default="Europe/Moscow", env="TIMEZONE", description="Часовой пояс")

    # Настройки резервного копирования (опционально)
    backup_enabled: bool = Field(default=False, env="BACKUP_ENABLED", description="Включить резервное копирование")
    backup_schedule: str = Field(default="0 2 * * *", env="BACKUP_SCHEDULE", description="Расписание резервного копирования")
    max_backup_files: int = Field(default=30, env="MAX_BACKUP_FILES", description="Максимальное количество файлов бэкапа")

    # Настройки email (опционально)
    email_enabled: bool = Field(default=False, env="EMAIL_ENABLED", description="Включить отправку email")
    email_smtp_host: str = Field(default="smtp.gmail.com", env="EMAIL_SMTP_HOST", description="SMTP сервер")
    email_smtp_port: int = Field(default=587, env="EMAIL_SMTP_PORT", description="SMTP порт")
    email_smtp_user: str = Field(default="", env="EMAIL_SMTP_USER", description="SMTP логин")
    email_smtp_password: str = Field(default="", env="EMAIL_SMTP_PASSWORD", description="SMTP пароль")
    email_from: str = Field(default="", env="EMAIL_FROM", description="Адрес отправителя")
    email_request_to: str = Field(default="", env="EMAIL_REQUEST_TO", description="Адрес для запросов на сертификаты")
    email_allowed_senders: str = Field(default="", env="EMAIL_ALLOWED_SENDERS", description="JSON-список разрешенных отправителей [{name, email}]")

    # Настройки веб-сервиса (опционально)
    web_enabled: bool = Field(default=False, env="WEB_ENABLED", description="Включить веб-сервис")
    web_host: str = Field(default="0.0.0.0", env="WEB_HOST", description="Хост веб-сервиса")
    web_port: int = Field(default=8443, env="WEB_PORT", description="Порт веб-сервиса")
    web_secret_key: str = Field(default="change-me-in-production", env="WEB_SECRET_KEY", description="Секретный ключ для сессий")
    web_users: str = Field(default="", env="WEB_USERS", description="JSON-список веб-пользователей [{username, password, role}]")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Создаем директории сразу при инициализации
        self.create_directories()

    @property
    def database_url(self) -> str:
        """Возвращает URL подключения к базе данных."""
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def admin_users_set(self) -> Set[int]:
        """Возвращает множество ID администраторов."""
        return {int(user_id.strip()) for user_id in self.admin_users.split(",") if user_id.strip()}

    @property
    def verify_users_set(self) -> Set[int]:
        """Возвращает множество ID пользователей для проверки."""
        return {int(user_id.strip()) for user_id in self.verify_users.split(",") if user_id.strip()}

    @property
    def all_allowed_users(self) -> Set[int]:
        """Возвращает множество всех разрешенных пользователей."""
        return self.admin_users_set.union(self.verify_users_set)

    def is_admin(self, user_id: int) -> bool:
        """Проверяет, является ли пользователь администратором."""
        return user_id in self.admin_users_set

    def is_verify_user(self, user_id: int) -> bool:
        """Проверяет, может ли пользователь проверять сертификаты."""
        return user_id in self.verify_users_set or user_id in self.admin_users_set

    def is_allowed_user(self, user_id: int) -> bool:
        """Проверяет, является ли пользователь разрешенным."""
        return user_id in self.all_allowed_users

    @property
    def email_allowed_senders_list(self) -> List[Dict[str, str]]:
        """Возвращает список разрешенных отправителей email."""
        if not self.email_allowed_senders:
            return []
        try:
            return json.loads(self.email_allowed_senders)
        except (json.JSONDecodeError, TypeError):
            return []

    @property
    def web_users_list(self) -> List[Dict[str, str]]:
        """Возвращает список веб-пользователей."""
        if not self.web_users:
            return []
        try:
            return json.loads(self.web_users)
        except (json.JSONDecodeError, TypeError):
            return []

    def get_web_user(self, username: str, password: str) -> Optional[Dict[str, str]]:
        """Проверяет учетные данные веб-пользователя."""
        for user in self.web_users_list:
            if user.get('username') == username and user.get('password') == password:
                return user
        return None

    def is_email_sender_allowed(self, email: str) -> bool:
        """Проверяет, разрешен ли отправитель email."""
        allowed = self.email_allowed_senders_list
        if not allowed:
            return True  # Если список не задан, разрешаем всех
        return any(s.get('email', '').lower() == email.lower() for s in allowed)

    @validator('admin_users', 'verify_users')
    def validate_user_ids(cls, v):
        """Валидация списков пользователей."""
        if not v:
            raise ValueError("Список пользователей не может быть пустым")

        try:
            user_ids = []
            for user_id_str in v.split(","):
                user_id_str = user_id_str.strip()
                if user_id_str:
                    user_id = int(user_id_str)
                    # Проверяем, что ID достаточно длинный для Telegram
                    if user_id < 100000:  # Минимальный валидный Telegram ID
                        print(f"⚠️  Подозрительно короткий Telegram ID: {user_id}")
                    user_ids.append(user_id)

            if not user_ids:
                raise ValueError("Не найдено корректных ID пользователей")

            print(f"✅ Распознано пользователей: {len(user_ids)}")
            for uid in user_ids:
                print(f"  - {uid}")

            return v
        except ValueError as e:
            raise ValueError(f"Некорректные ID пользователей: {e}")

    @validator('certificates_path', 'log_file')
    def validate_paths(cls, v):
        """Валидация путей к файлам и директориям."""
        if isinstance(v, str):
            v = Path(v)

        # Создаем родительские директории если они не существуют
        v.parent.mkdir(parents=True, exist_ok=True)

        return v

    @validator('notification_group')
    def validate_notification_group(cls, v):
        """Валидация ID группы для уведомлений."""
        if v > 0:
            raise ValueError("ID группы должен быть отрицательным числом")
        return v

    def create_directories(self):
        """Создает необходимые директории."""
        try:
            # Создаем директорию для сертификатов
            self.certificates_path.mkdir(parents=True, exist_ok=True)
            print(f"✅ Создана директория для сертификатов: {self.certificates_path}")

            # Создаем директорию для логов
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            print(f"✅ Создана директория для логов: {self.log_file.parent}")

            # Проверяем права доступа
            if not os.access(self.certificates_path, os.W_OK):
                print(f"⚠️  Нет прав записи в {self.certificates_path}")
                # Пробуем изменить права
                try:
                    os.chmod(self.certificates_path, 0o755)
                    print(f"✅ Права на {self.certificates_path} исправлены")
                except Exception as e:
                    print(f"❌ Не удалось исправить права: {e}")

            if not os.access(self.log_file.parent, os.W_OK):
                print(f"⚠️  Нет прав записи в {self.log_file.parent}")
                # Пробуем изменить права
                try:
                    os.chmod(self.log_file.parent, 0o755)
                    print(f"✅ Права на {self.log_file.parent} исправлены")
                except Exception as e:
                    print(f"❌ Не удалось исправить права: {e}")

        except Exception as e:
            print(f"❌ Ошибка создания директорий: {e}")

    class Config:
        """Конфигурация настроек."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Игнорировать дополнительные поля из .env


# Глобальная переменная с настройками
settings = Settings()


def get_settings() -> Settings:
    """Возвращает объект настроек."""
    return settings


def load_settings_from_file(env_file: str = ".env") -> Settings:
    """
    Загружает настройки из указанного файла.

    Args:
        env_file: Путь к файлу с переменными окружения

    Returns:
        Settings: Объект настроек
    """
    return Settings(_env_file=env_file)


def create_env_example():
    """Создает пример файла .env."""
    env_example_content = """# Настройки Telegram бота
BOT_TOKEN=your_bot_token_here
ADMIN_USERS=123456789,987654321
VERIFY_USERS=111111111,222222222,333333333
NOTIFICATION_GROUP=-1001234567890

# Настройки базы данных PostgreSQL
DB_HOST=localhost
DB_PORT=5432
DB_NAME=certificates_db
DB_USER=certificates_user
DB_PASSWORD=your_password_here

# Настройки хранилища файлов
CERTIFICATES_PATH=./certificates

# Настройки логирования
LOG_LEVEL=INFO
LOG_FILE=./logs/bot.log

# Общие настройки
DEBUG=false
TIMEZONE=Europe/Moscow

# Настройки email (опционально)
EMAIL_ENABLED=false
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_SMTP_USER=your_email@gmail.com
EMAIL_SMTP_PASSWORD=your_app_password
EMAIL_FROM=your_email@gmail.com
EMAIL_REQUEST_TO=certificates@yourcompany.com
# JSON-список разрешенных отправителей: [{"name": "Иванов И.И.", "email": "ivanov@company.com"}]
EMAIL_ALLOWED_SENDERS=[]

# Настройки веб-сервиса (опционально)
WEB_ENABLED=false
WEB_HOST=0.0.0.0
WEB_PORT=8443
WEB_SECRET_KEY=change-me-in-production
# JSON-список пользователей: [{"username": "admin", "password": "secret", "role": "admin"}]
WEB_USERS=[]
"""

    with open(".env.example", "w", encoding="utf-8") as f:
        f.write(env_example_content)

    print("Создан файл .env.example с примером конфигурации")


def validate_settings():
    """Проверяет корректность настроек."""
    try:
        settings = get_settings()

        print("Проверка настроек:")
        print(f"  ✓ Токен бота: {'*' * 10}{settings.bot_token[-10:]}")
        print(f"  ✓ Администраторы: {len(settings.admin_users_set)} пользователей")
        print(f"  ✓ Пользователи для проверки: {len(settings.verify_users_set)} пользователей")
        print(f"  ✓ Группа уведомлений: {settings.notification_group}")
        print(f"  ✓ База данных: {settings.db_host}:{settings.db_port}/{settings.db_name}")
        print(f"  ✓ Директория сертификатов: {settings.certificates_path}")

        # Создаем необходимые директории
        settings.create_directories()

        return True

    except Exception as e:
        print(f"Ошибка в настройках: {e}")
        return False


if __name__ == "__main__":
    # Создаем пример конфигурации
    create_env_example()

    # Проверяем настройки
    if not validate_settings():
        print("\nСоздайте файл .env на основе .env.example и укажите корректные значения")
    else:
        print("\nНастройки корректны!")
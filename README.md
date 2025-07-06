# Certificate Management Telegram Bot

Система управления сертификатами через Telegram бота с поддержкой генерации, проверки и поиска сертификатов.

## Возможности

### Для администраторов:
- 📝 Создание новых сертификатов
- 📋 Просмотр созданных сертификатов
- 🔍 Проверка сертификатов по ID
- 🔎 Поиск по домену и ИНН
- 📊 Статистика системы

### Для пользователей с правами проверки:
- 🔍 Проверка сертификатов по ID
- 🔎 Поиск по домену и ИНН

## Архитектура

```
certificate_bot/
├── core/                 # Бизнес-логика
│   ├── models.py        # Pydantic модели
│   ├── database.py      # SQLAlchemy модели и БД
│   ├── generator.py     # Генератор ID сертификатов
│   ├── validator.py     # Валидация данных
│   ├── storage.py       # Файловое хранилище
│   ├── service.py       # Основная бизнес-логика
│   └── exceptions.py    # Кастомные исключения
├── bot/                 # Telegram бот
│   ├── handlers/        # Обработчики команд
│   ├── keyboards.py     # Reply клавиатуры
│   ├── states.py        # FSM состояния
│   ├── middleware.py    # Middleware для прав доступа
│   └── main.py          # Запуск бота
├── config/              # Конфигурация
└── migrations/          # Миграции БД
```

## Установка и запуск

### 1. Клонирование репозитория

```bash
git clone <repository-url>
cd certificate_bot
```

### 2. Настройка окружения

```bash
# Создание виртуального окружения
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows

# Установка зависимостей
pip install -r requirements.txt
```

### 3. Настройка конфигурации

```bash
# Копируем пример конфигурации
cp .env.example .env

# Редактируем .env файл с реальными значениями
nano .env
```

### 4. Настройка базы данных

```bash
# Создание БД (PostgreSQL)
createdb certificates_db

# Запуск миграций
alembic upgrade head
```

### 5. Запуск бота

```bash
python -m bot.main
```

## Docker запуск

### 1. Подготовка

```bash
# Создаем директории для данных
mkdir -p data/{postgres,certificates,logs,backups}

# Копируем конфигурацию
cp .env.example .env
# Редактируем .env
```

### 2. Запуск

```bash
# Запуск основных сервисов
docker-compose up -d

# Запуск с админ-панелью
docker-compose --profile admin up -d

# Создание резервной копии
docker-compose --profile backup run --rm backup

# Просмотр логов
docker-compose logs -f certificate_bot
```

### 3. Остановка

```bash
docker-compose down
```

## Конфигурация

### Обязательные параметры

| Параметр | Описание | Пример |
|----------|----------|---------|
| `BOT_TOKEN` | Токен Telegram бота | `1234567890:AAABBB...` |
| `ADMIN_USERS` | ID администраторов через запятую | `123456789,987654321` |
| `VERIFY_USERS` | ID пользователей для проверки | `111111111,222222222` |
| `NOTIFICATION_GROUP` | ID группы для уведомлений | `-1001234567890` |
| `DB_PASSWORD` | Пароль базы данных | `your_strong_password` |

### Дополнительные параметры

| Параметр | Значение по умолчанию | Описание |
|----------|----------------------|----------|
| `DB_HOST` | `localhost` | Хост БД |
| `DB_PORT` | `5432` | Порт БД |
| `DB_NAME` | `certificates_db` | Имя БД |
| `DB_USER` | `certificates_user` | Пользователь БД |
| `CERTIFICATES_PATH` | `./certificates` | Путь к файлам сертификатов |
| `LOG_LEVEL` | `INFO` | Уровень логирования |
| `DEBUG` | `false` | Режим отладки |

## Формат сертификатов

### ID сертификата
- **Формат:** `XXXXX-XXXXX-XXXXX-XXXXX` (23 символа)
- **Символы:** A-Z, 0-9
- **Последние 4 символа:** месяц и год окончания (MMYY)
- **Пример:** `A7K9M-X3P2R-Q8W1E-RT0524` (истекает в мае 2024)

### Поддерживаемые домены
- `example.com`
- `sub.example.com`
- `my-site.com`
- `*.example.com` (wildcard)
- `*.sub.example.com`
- `*.my-site.com`

### Валидация ИНН
- 10-значный ИНН для юридических лиц
- 12-значный ИНН для физических лиц
- Проверка контрольной суммы

## Использование

### Команды бота

| Команда | Описание | Доступ |
|---------|----------|---------|
| `/start` | Запуск бота | Все |
| `/help` | Справка | Все |
| `/cancel` | Отмена операции | Все |
| `/status` | Статистика системы | Админы |

### Процесс создания сертификата

1. Нажмите "📝 Создать сертификат"
2. Введите доменное имя
3. Введите ИНН организации
4. Выберите период действия
5. Укажите количество пользователей
6. Подтвердите создание

### Проверка сертификата

1. Нажмите "🔍 Проверить сертификат"
2. Введите ID сертификата
3. Получите информацию о статусе

### Поиск сертификатов

1. Нажмите "🔎 Поиск"
2. Выберите тип поиска (по домену или ИНН)
3. Введите критерий поиска
4. Просмотрите результаты

## API документация

### Основные классы

#### CertificateService
Основной сервис для работы с сертификатами.

```python
from core.service import get_certificate_service

service = get_certificate_service()

# Создание сертификата
certificate, has_existing = service.create_certificate(request)

# Проверка сертификата
certificate = service.verify_certificate(certificate_id, user_id)

# Поиск сертификатов
certificates = service.search_certificates(search_request)
```

#### CertificateIDGenerator
Генератор уникальных ID сертификатов.

```python
from core.generator import CertificateIDGenerator

generator = CertificateIDGenerator()

# Генерация ID
certificate_id = generator.generate(valid_to_date, existing_ids)

# Валидация формата
is_valid = generator.validate_id_format(certificate_id)

# Извлечение даты окончания
month, year = generator.extract_expiry_date(certificate_id)
```

#### DataValidator
Валидатор всех типов данных.

```python
from core.validator import DataValidator

validator = DataValidator()

# Валидация всех данных
errors = validator.validate_all(domain, inn, valid_from, valid_to, users_count)
```

## Структура базы данных

### Таблица certificates

```sql
CREATE TABLE certificates (
                              id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                              certificate_id VARCHAR(23) UNIQUE NOT NULL,
                              domain VARCHAR(255) NOT NULL,
                              inn VARCHAR(12) NOT NULL,
                              valid_from DATE NOT NULL,
                              valid_to DATE NOT NULL,
                              users_count INTEGER NOT NULL,
                              created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                              created_by VARCHAR(20) NOT NULL,
                              is_active BOOLEAN DEFAULT TRUE
);
```

### Таблица certificate_history

```sql
CREATE TABLE certificate_history (
                                     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                                     certificate_id VARCHAR(23) NOT NULL,
                                     action VARCHAR(50) NOT NULL,
                                     performed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                                     performed_by VARCHAR(20) NOT NULL,
                                     details JSONB
);
```

### Индексы

```sql
CREATE INDEX idx_certificate_active_domain ON certificates(domain, is_active);
CREATE INDEX idx_certificate_active_inn ON certificates(inn, is_active);
CREATE INDEX idx_certificate_validity ON certificates(valid_from, valid_to);
CREATE INDEX idx_history_certificate_id ON certificate_history(certificate_id);
```

## Файловая структура

### Сертификаты сохраняются в формате:
```
certificates/
└── YYYY/
    └── domain_certificateID.json
```

### Пример файла сертификата:
```json
{
  "certificate_id": "A7K9M-X3P2R-Q8W1E-RT0524",
  "domain": "example.com",
  "inn": "1234567890",
  "validity_period": "01.01.2024-31.05.2024",
  "users_count": 100,
  "created_at": "2024-01-01T10:00:00",
  "created_by": "123456789",
  "is_active": true,
  "is_expired": false,
  "days_left": 120
}
```

## Мониторинг и логирование

### Логи
- Все действия записываются в `/app/logs/bot.log`
- Уровни: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Ротация логов по размеру и времени

### Метрики
- Количество созданных сертификатов
- Количество проверок
- Ошибки валидации
- Производительность БД

### Healthcheck
```bash
# Проверка работоспособности бота
docker-compose ps

# Проверка логов
docker-compose logs certificate_bot

# Проверка БД
docker-compose exec postgres pg_isready
```

## Масштабирование

### Горизонтальное масштабирование
1. Запуск нескольких экземпляров бота (webhook mode)
2. Использование Redis для хранения состояний FSM
3. Load balancer для распределения нагрузки

### Вертикальное масштабирование
1. Увеличение ресурсов контейнера
2. Оптимизация SQL запросов
3. Кэширование частых запросов

### Конфигурация для продакшена

```yaml
# docker-compose.prod.yml
services:
  certificate_bot:
    deploy:
      replicas: 3
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
    environment:
      BOT_WEBHOOK_URL: https://your-domain.com/webhook
      REDIS_URL: redis://redis:6379/0

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes

  postgres:
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
```

## Резервное копирование

### Автоматическое резервное копирование

```bash
# Создание cron задачи
0 2 * * * docker-compose --profile backup run --rm backup

# Ручное создание бэкапа
docker-compose --profile backup run --rm backup
```

### Восстановление из резервной копии

```bash
# Восстановление БД
docker-compose exec postgres psql -U certificates_user -d certificates_db < backup_20240101_020000.sql

# Синхронизация файлов
python -c "
from core.storage import get_storage_manager
manager = get_storage_manager()
result = manager.sync_database_to_files()
print(f'Синхронизировано: {result[\"synced_count\"]} файлов')
"
```

## Безопасность

### Рекомендации
1. Используйте сильные пароли для БД
2. Ограничьте доступ к серверу
3. Регулярно обновляйте зависимости
4. Настройте файрвол
5. Используйте HTTPS для webhook

### Защита данных
1. Шифрование чувствительных данных
2. Аудит доступа к сертификатам
3. Регулярное резервное копирование
4. Мониторинг подозрительной активности

## Troubleshooting

### Частые проблемы

#### Бот не отвечает
```bash
# Проверить статус контейнера
docker-compose ps

# Проверить логи
docker-compose logs certificate_bot

# Перезапустить бота
docker-compose restart certificate_bot
```

#### Ошибки БД
```bash
# Проверить подключение к БД
docker-compose exec postgres pg_isready

# Проверить логи БД
docker-compose logs postgres

# Перезапустить БД
docker-compose restart postgres
```

#### Проблемы с правами
1. Проверить настройки ADMIN_USERS и VERIFY_USERS в .env
2. Убедиться, что ID пользователей указаны корректно
3. Перезапустить бота после изменения конфигурации

## Разработка

### Настройка среды разработки

```bash
# Клонирование и настройка
git clone <repo>
cd certificate_bot
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Запуск тестов
pytest

# Линтинг кода
flake8 .
black .

# Создание миграции
alembic revision --autogenerate -m "Description"
```

### Структура тестов

```python
# tests/test_generator.py
def test_certificate_id_generation():
    generator = CertificateIDGenerator()
    cert_id = generator.generate(date(2024, 5, 31))
    assert len(cert_id) == 23
    assert cert_id.endswith('0524')

# tests/test_validator.py
def test_domain_validation():
    validator = DomainValidator()
    assert validator.validate('example.com')
    assert validator.validate('*.example.com')
    assert not validator.validate('-example.com')
```

## Лицензия

MIT License

## Поддержка

Для получения поддержки:
1. Создайте issue в GitHub
2. Обратитесь к администратору системы
3. Проверьте документацию и FAQ
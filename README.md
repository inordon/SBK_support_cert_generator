# Система управления сертификатами

Комплексная система для генерации и проверки сертификатов с Telegram ботом и REST API.

## Компоненты системы

### 1. Core модуль (Генератор сертификатов)
- Генерация уникальных ID сертификатов в формате XXXXX-XXXXX-XXXXX-XXXXX
- Валидация входных данных (домены, ИНН, периоды, количество пользователей)
- Сохранение в PostgreSQL и файловую систему
- CLI интерфейс для работы из командной строки

### 2. REST API
- FastAPI сервер для интеграции с внешними системами
- Endpoints для создания и проверки сертификатов
- Аутентификация по API ключу
- Автоматическая документация OpenAPI

### 3. Telegram бот
- Пошаговый процесс создания сертификатов
- Проверка существующих сертификатов
- Контроль доступа через списки пользователей
- Уведомления в группы

### 4. База данных PostgreSQL
- Хранение сертификатов и истории действий
- Индексы для быстрого поиска
- Ограничения и триггеры для целостности данных
- Функции для статистики и очистки

## Установка и запуск

### Требования
- Python 3.11+
- Docker и Docker Compose
- PostgreSQL 15+
- Redis (опционально, для FSM состояний)

### Быстрый старт

1. Клонирование и настройка:
```bash
git clone <repository>
cd certificate-management-system
cp .env.example .env
# Отредактируйте .env файл с вашими настройками
```

2. Запуск через Docker Compose:
```bash
# Сборка и запуск всех сервисов
docker-compose up -d

# Или только основные сервисы (без nginx)
docker-compose up -d postgres redis api bot

# Проверка статуса
docker-compose ps
```

3. Инициализация базы данных:
```bash
# База данных автоматически инициализируется при первом запуске
# Схема создается из файла database/init.sql
```

### Ручная установка

1. Установка зависимостей:
```bash
pip install -r requirements.txt
```

2. Настройка переменных окружения:
```bash
export BOT_TOKEN="your_bot_token"
export DATABASE_URL="postgresql://user:pass@localhost/db"
export API_KEY="your_api_key"
export ALLOWED_USERS="123456789,987654321"
export VERIFY_USERS="111111111,222222222"
```

3. Запуск компонентов:
```bash
# API сервер
python api_server.py

# Telegram бот
python bot/main.py

# CLI использование
python cli.py generate --domain example.com --inn 1234567890 --period "01.01.2024-31.12.2024" --users 100
```

## Использование

### CLI интерфейс

```bash
# Генерация сертификата
python cli.py generate \
  --domain example.com \
  --inn 7707083893 \
  --period "01.01.2024-31.12.2024" \
  --users 100

# Проверка сертификата
python cli.py verify ABCD1-XYZ12-QWRT5-WX0124

# Список сертификатов
python cli.py list
```

### REST API

```bash
# Создание сертификата
curl -X POST "http://localhost:8000/certificates" \
  -H "Authorization: Bearer your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "example.com",
    "inn": "7707083893",
    "period": "01.01.2024-31.12.2024",
    "users_count": 100
  }'

# Проверка сертификата
curl "http://localhost:8000/certificates/ABCD1-XYZ12-QWRT5-WX0124/verify" \
  -H "Authorization: Bearer your_api_key"

# Поиск по домену
curl "http://localhost:8000/certificates/domain/example.com" \
  -H "Authorization: Bearer your_api_key"
```

### Telegram бот

1. Добавьте бота в контакты
2. Используйте команды:
    - `/start` - Начало работы
    - `/generate` - Создание сертификата
    - `/verify` - Проверка сертификата
    - `/help` - Справка

## Конфигурация

### Переменные окружения

```env
# Telegram бот
BOT_TOKEN=your_telegram_bot_token
ALLOWED_USERS=123456789,987654321  # ID пользователей для генерации
VERIFY_USERS=111111111,222222222   # ID пользователей для проверки
NOTIFICATION_CHAT=-1001234567890   # Чат для уведомлений

# База данных
DATABASE_URL=postgresql://user:pass@host:port/db
POSTGRES_PASSWORD=strong_password
CERT_APP_PASSWORD=app_password

# Redis (опционально)
REDIS_URL=redis://:password@host:port/db
REDIS_PASSWORD=redis_password

# API
API_KEY=your_secret_api_key

# Файловая система
CERTIFICATES_DIR=./certificates

# Логирование
LOG_LEVEL=INFO
```

### Структура сертификатов

```
certificates/
├── 2024/
│   ├── 01/
│   │   ├── example.com_ABCD1-XYZ12-QWRT5-WX0124.json
│   │   └── test.org_EFGH5-IJKL6-MNOP7-QR0124.json
│   └── 02/
│       └── another.domain_STUV8-WXYZ9-ABCD0-EF0224.json
└── 2025/
    └── ...
```

### Формат ID сертификата

- Общая длина: 23 символа (20 символов + 3 дефиса)
- Формат: `XXXXX-XXXXX-XXXXX-XXXXX`
- Символы: A-Z, 0-9
- Последние 4 символа: первый символ + MMYY (месяц и год окончания)
- Пример: `ABCD1-XYZ12-QWRT5-WX0124` (окончание в январе 2024)

## Безопасность

- Аутентификация API через Bearer токены
- Контроль доступа в Telegram боте по ID пользователей
- Валидация всех входных данных
- Непривилегированные пользователи в Docker контейнерах
- Правильные права доступа к файлам (644 для файлов, 755 для директорий)

## Мониторинг и логирование

- Структурированные логи в формате JSON
- Логирование всех операций с сертификатами
- Health check endpoints для мониторинга
- Метрики производительности
- Ротация логов

## Масштабирование

### Горизонтальное масштабирование

1. **API сервер**: Несколько инстансов за load balancer
2. **Telegram бот**: Один инстанс (ограничение Telegram)
3. **База данных**: Master-slave репликация
4. **Redis**: Redis Cluster для FSM состояний

### Оптимизация производительности

1. **Индексы БД**: Добавлены для всех часто используемых запросов
2. **Пулы соединений**: Настроены для PostgreSQL
3. **Кэширование**: Redis для временных данных
4. **Батчинг**: Групповые операции для массовых действий

### Мониторинг ресурсов

```bash
# Мониторинг Docker контейнеров
docker-compose top
docker-compose logs -f

# Проверка состояния сервисов
curl http://localhost:8000/health
```

## Разработка

### Запуск в режиме разработки

```bash
# API с автоперезагрузкой
uvicorn api_server:app --reload --host 0.0.0.0 --port 8000

# Бот с отладкой
LOG_LEVEL=DEBUG python bot/main.py
```

### Тестирование

```bash
# Установка зависимостей для тестов
pip install pytest pytest-asyncio pytest-mock httpx

# Запуск всех тестов
pytest

# Запуск с покрытием
pytest --cov=core --cov-report=html

# Тесты конкретного модуля
pytest tests/test_validators.py -v
```

### Форматирование кода

```bash
# Установка инструментов
pip install black isort flake8

# Форматирование
black .
isort .

# Проверка стиля
flake8 .
```

## Устранение неполадок

### Частые проблемы

1. **Ошибка подключения к БД**
   ```bash
   # Проверьте статус PostgreSQL
   docker-compose logs postgres
   
   # Проверьте строку подключения
   echo $DATABASE_URL
   ```

2. **Бот не отвечает**
   ```bash
   # Проверьте токен
   curl https://api.telegram.org/bot$BOT_TOKEN/getMe
   
   # Проверьте логи
   docker-compose logs bot
   ```

3. **API недоступен**
   ```bash
   # Проверьте health endpoint
   curl http://localhost:8000/health
   
   # Проверьте логи
   docker-compose logs api
   ```

### Логи и отладка

```bash
# Просмотр логов всех сервисов
docker-compose logs -f

# Логи конкретного сервиса
docker-compose logs -f bot

# Вход в контейнер для отладки
docker-compose exec api bash
```

## Лицензия

MIT License - см. файл LICENSE

## Поддержка

Для получения поддержки:
1. Создайте issue в репозитории
2. Опишите проблему с приложением логов
3. Укажите версию системы и конфигурацию

---

## Схема взаимодействия компонентов

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Telegram Bot  │    │    REST API     │    │   CLI Interface │
│                 │    │                 │    │                 │
│ - Пошаговая     │    │ - CRUD операции │    │ - Генерация     │
│   генерация     │    │ - Валидация     │    │ - Проверка      │
│ - Проверка      │    │ - Аутентификация│    │ - Список        │
│ - Контроль      │    │ - Документация  │    │                 │
│   доступа       │    │                 │    │                 │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │     Core Generator      │
                    │                         │
                    │ - Генерация ID          │
                    │ - Валидация данных      │
                    │ - Бизнес-логика         │
                    │                         │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │    Storage Layer        │
                    │                         │
                    │ ┌─────────┐ ┌─────────┐ │
                    │ │PostgreSQL │ │  Files  │ │
                    │ │         │ │         │ │
                    │ │- Основные│ │- JSON   │ │
                    │ │  данные │ │- Резерв │ │
                    │ │- История│ │- Архив  │ │
                    │ └─────────┘ └─────────┘ │
                    └─────────────────────────┘
```
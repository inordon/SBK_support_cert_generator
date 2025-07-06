# Quick Start Guide - Certificate Bot

## 🚀 Быстрый запуск (без Makefile)

### 1. Настройка конфигурации
```bash
# Копируем пример настроек
cp .env.example .env

# Редактируем настройки (обязательно!)
nano .env
```

### 2. Запуск системы
```bash
# Сборка и запуск всех сервисов
docker-compose up -d --build
```

### 3. Миграция базы данных (для обновления)
```bash
# Если обновляете существующую систему, выполните миграцию
python migrate.py

# Или через Docker
docker-compose exec certificate_bot python migrate.py

# Или используя Makefile
make migrate
```

### 4. Проверка работы
```bash
# Просмотр логов бота
docker-compose logs -f certificate_bot

# Проверка статуса всех сервисов
docker-compose ps

# Проверка БД
docker-compose exec postgres pg_isready -U certificates_user -d certificates_db
```

## 📋 Основные команды

### Управление сервисами
```bash
# Запуск
docker-compose up -d

# Остановка
docker-compose down

# Перезапуск
docker-compose restart certificate_bot

# Просмотр логов
docker-compose logs certificate_bot
docker-compose logs postgres
```

### Работа с базой данных
```bash
# Подключение к БД
docker-compose exec postgres psql -U certificates_user -d certificates_db

# Бэкап БД
docker-compose exec postgres pg_dump -U certificates_user certificates_db > backup.sql

# Восстановление БД
docker-compose exec -T postgres psql -U certificates_user -d certificates_db < backup.sql

# Миграция (убрать ограничение на пользователей)
python migrate.py
```

### Отладка
```bash
# Подключение к контейнеру бота
docker-compose exec certificate_bot /bin/bash

# Просмотр файлов сертификатов
docker-compose exec certificate_bot ls -la /app/certificates/

# Проверка переменных окружения
docker-compose exec certificate_bot env | grep BOT
```

## 🛠️ Разработка

### Локальный запуск (без Docker)
```bash
# Установка зависимостей
pip install -r requirements.txt

# Настройка БД (PostgreSQL должен быть установлен)
createdb certificates_db
alembic upgrade head

# Запуск бота
python run.py
```

### Тестирование
```bash
# Установка тестовых зависимостей
pip install pytest pytest-cov

# Запуск тестов
python -m pytest tests/ -v

# Тесты с покрытием
python -m pytest tests/ --cov=core --cov=bot
```

## 🔧 Настройка продакшена

### 1. Создайте production .env
```bash
cp .env.example .env.prod
# Настройте продакшен параметры
```

### 2. Используйте production compose файл
```bash
# Создайте docker-compose.prod.yml с production настройками
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

### 3. Настройте мониторинг
```bash
# Запуск с Adminer для мониторинга БД
docker-compose --profile admin up -d
# Adminer доступен на http://localhost:8080
```

## 🆕 Новые возможности v2.0

### Создание сертификата одним сообщением
Теперь админы могут создать сертификат, отправив все данные одним сообщением:

```
Срок действия: 01.01.2025-31.12.2025
ИНН: 7707083893
Домен: example.com
Количество пользователей: 10000
```

### Без ограничений на пользователей
Убрано ограничение на 1000 пользователей. Теперь можно указать любое количество ≥ 1.

### Миграция для существующих систем
Если у вас уже развернута система, выполните миграцию:
```bash
# Локально
python migrate.py

# В Docker
make migrate-docker

# Или через Makefile
make migrate
```

## 📊 Мониторинг

### Логи
```bash
# Все логи
docker-compose logs

# Только ошибки
docker-compose logs | grep ERROR

# Следить за логами в реальном времени
docker-compose logs -f certificate_bot
```

### Статистика
```bash
# Использование ресурсов
docker stats

# Размер данных
du -sh data/

# Статус контейнеров
docker-compose ps
```

## 🆘 Решение проблем

### Бот не отвечает
```bash
# Проверить логи
docker-compose logs certificate_bot

# Перезапустить бота
docker-compose restart certificate_bot

# Проверить токен
docker-compose exec certificate_bot env | grep BOT_TOKEN
```

### Проблемы с БД
```bash
# Проверить статус БД
docker-compose exec postgres pg_isready

# Перезапустить БД
docker-compose restart postgres

# Проверить подключение
docker-compose exec postgres psql -U certificates_user -d certificates_db -c "SELECT 1;"
```

### Ошибки создания сертификатов
```bash
# Проверить ограничения БД
docker-compose exec postgres psql -U certificates_user -d certificates_db -c "
SELECT conname, pg_get_constraintdef(oid) 
FROM pg_constraint 
WHERE conrelid = 'certificates'::regclass;"

# Выполнить миграцию если нужно
python migrate.py
```

### Очистка системы
```bash
# Остановка и удаление контейнеров
docker-compose down -v

# Удаление образов
docker-compose down --rmi local

# Полная очистка Docker
docker system prune -a
```

## ✅ Готово!

После выполнения этих шагов ваш бот должен работать. Проверьте:

1. **Telegram бот отвечает на команду /start**
2. **Администраторы могут создавать сертификаты новым способом**
3. **Можно указать любое количество пользователей ≥ 1**
4. **Пользователи могут проверять сертификаты**
5. **Уведомления приходят в группу**

## 🔄 Обновление с предыдущей версии

Если у вас уже была развернута предыдущая версия:

```bash
# 1. Остановить сервисы
docker-compose down

# 2. Обновить код
git pull  # или скопировать новые файлы

# 3. Пересобрать образы
docker-compose build

# 4. Запустить сервисы
docker-compose up -d

# 5. Выполнить миграцию
make migrate

# 6. Проверить работу
make status
```

---

*Makefile и скрипты миграции облегчают управление системой и обновления.*
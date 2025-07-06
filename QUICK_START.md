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

### 3. Проверка работы
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
2. **Администраторы могут создавать сертификаты**
3. **Пользователи могут проверять сертификаты**
4. **Уведомления приходят в группу**

---

*Makefile добавляет удобство, но не является обязательным для работы системы.*
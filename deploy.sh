#!/bin/bash
# deploy.sh - Скрипт развертывания на сервере

set -e

echo "🚀 Развертывание Certificate Management System..."

# Проверка наличия .env файла
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo "📋 Создание .env из .env.example..."
        cp .env.example .env
        echo "⚠️  ВАЖНО: Отредактируйте .env файл перед запуском!"
        echo "   Необходимо установить:"
        echo "   - BOT_TOKEN"
        echo "   - POSTGRES_PASSWORD"
        echo "   - CERT_APP_PASSWORD"
        echo "   - REDIS_PASSWORD"
        echo "   - API_KEY"
        echo "   - ALLOWED_USERS"
        exit 1
    else
        echo "❌ Файл .env не найден!"
        exit 1
    fi
fi

# Создание необходимых директорий
echo "📁 Создание директорий..."
mkdir -p certificates logs database

# Установка прав
chmod 755 certificates logs database
chmod +x database/02-create-user.sh

# Проверка Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен!"
    exit 1
fi

if ! docker compose version &> /dev/null 2>&1; then
    if ! command -v docker-compose &> /dev/null; then
        echo "❌ Docker Compose не установлен!"
        exit 1
    fi
    COMPOSE_CMD="docker-compose"
else
    COMPOSE_CMD="docker compose"
fi

# Остановка старых контейнеров
echo "⏹️  Остановка старых контейнеров..."
$COMPOSE_CMD down

# Сборка и запуск
echo "🔨 Сборка образов..."
$COMPOSE_CMD build

echo "🚀 Запуск сервисов..."
$COMPOSE_CMD up -d

# Ожидание запуска
echo "⏳ Ожидание запуска сервисов..."
sleep 10

# Проверка статуса
echo "📊 Проверка статуса..."
$COMPOSE_CMD ps

# Проверка здоровья API
echo "🔍 Проверка API..."
if curl -f http://localhost:8000/health &> /dev/null; then
    echo "✅ API работает!"
else
    echo "⚠️  API еще запускается..."
fi

echo ""
echo "✅ Развертывание завершено!"
echo ""
echo "📋 Полезные команды:"
echo "   $COMPOSE_CMD logs -f          # Просмотр логов"
echo "   $COMPOSE_CMD ps               # Статус сервисов"
echo "   $COMPOSE_CMD restart bot      # Перезапуск бота"
echo "   $COMPOSE_CMD exec postgres psql -U cert_app -d certificates_db"
echo ""
echo "🔗 Доступ к сервисам:"
echo "   API: http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo "   PostgreSQL: localhost:5432"
echo "   Redis: localhost:6379"
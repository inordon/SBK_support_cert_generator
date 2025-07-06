#!/bin/bash
# complete_restart.sh
# Полная очистка и перезапуск системы сертификатов

set -e

echo "🔄 Полная очистка и перезапуск системы сертификатов..."

# Определение команды Docker Compose
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    echo "❌ Docker Compose не найден! Установите Docker Compose."
    exit 1
fi

echo "✅ Используется: $DOCKER_COMPOSE"

# Остановка всех сервисов
echo "⏹️ Остановка сервисов..."
$DOCKER_COMPOSE down

# Удаление volumes
echo "🗑️ Удаление volumes..."
$DOCKER_COMPOSE down -v

# Принудительное удаление volumes
echo "🗑️ Принудительное удаление volumes..."
docker volume ls -q | grep -E "(postgres|redis|certificates|logs)" | xargs -r docker volume rm || true

# Очистка системы
echo "🧹 Очистка Docker системы..."
docker system prune -f

# Создание необходимых директорий
echo "📁 Создание директорий..."
mkdir -p certificates logs database
chmod 755 certificates logs database

# Удаление ненужных файлов (если существуют)
echo "🗑️ Удаление неиспользуемых файлов..."
rm -f database/create_user.sh database/set_password.sql || true

# Проверка .env файла
if [ ! -f .env ]; then
    echo "❌ Файл .env не найден! Скопируйте .env.example в .env и настройте."
    exit 1
fi

# Проверка обязательных переменных
echo "🔍 Проверка переменных окружения..."
source .env

if [ -z "$BOT_TOKEN" ] || [ "$BOT_TOKEN" = "your_bot_token_here" ]; then
    echo "❌ BOT_TOKEN не настроен в .env файле!"
    echo "   Получите токен у @BotFather в Telegram"
    exit 1
fi

if [ -z "$CERT_APP_PASSWORD" ] || [ "$CERT_APP_PASSWORD" = "strong_app_password" ]; then
    echo "❌ CERT_APP_PASSWORD не настроен в .env файле!"
    echo "   Установите сильный пароль для пользователя БД"
    exit 1
fi

if [ -z "$POSTGRES_PASSWORD" ] || [ "$POSTGRES_PASSWORD" = "strong_postgres_password" ]; then
    echo "❌ POSTGRES_PASSWORD не настроен в .env файле!"
    echo "   Установите сильный пароль для PostgreSQL"
    exit 1
fi

if [ -z "$ALLOWED_USERS" ] || [ "$ALLOWED_USERS" = "123456789,987654321" ]; then
    echo "❌ ALLOWED_USERS не настроен в .env файле!"
    echo "   Укажите ваш Telegram User ID (получить у @userinfobot)"
    exit 1
fi

echo "✅ Переменные окружения настроены корректно"

# Пересборка образов
echo "🔨 Пересборка образов..."
$DOCKER_COMPOSE build --no-cache --pull

# Запуск сервисов
echo "🚀 Запуск сервисов..."
$DOCKER_COMPOSE up -d

# Ожидание запуска PostgreSQL
echo "⏳ Ожидание запуска PostgreSQL..."
for i in {1..30}; do
    if $DOCKER_COMPOSE exec -T postgres pg_isready -U postgres >/dev/null 2>&1; then
        echo "✅ PostgreSQL запущен"
        break
    fi
    echo "   Попытка $i/30..."
    sleep 2
done

# Дополнительное ожидание для инициализации
echo "⏳ Ожидание инициализации БД..."
sleep 10

# Проверка создания схемы
echo "🔍 Проверка схемы certificates..."
if $DOCKER_COMPOSE exec -T postgres psql -U postgres -d certificates_db -c "\dn certificates" | grep -q certificates; then
    echo "✅ Схема certificates создана"
else
    echo "❌ Схема certificates не создана"
    echo "📋 Логи PostgreSQL:"
    $DOCKER_COMPOSE logs postgres --tail=20
    exit 1
fi

# Проверка создания пользователя
echo "🔍 Проверка пользователя cert_app..."
if $DOCKER_COMPOSE exec -T postgres psql -U postgres -d certificates_db -c "SELECT usename FROM pg_user WHERE usename = 'cert_app';" | grep -q cert_app; then
    echo "✅ Пользователь cert_app создан успешно"
else
    echo "❌ Пользователь cert_app не создан"
    exit 1
fi

# Проверка таблиц
echo "🔍 Проверка таблиц..."
if $DOCKER_COMPOSE exec -T postgres psql -U postgres -d certificates_db -c "\dt certificates.*" | grep -q certificates; then
    echo "✅ Таблицы созданы"
else
    echo "❌ Таблицы не созданы"
    exit 1
fi

# Проверка прав пользователя
echo "🔍 Проверка прав cert_app..."
if $DOCKER_COMPOSE exec -T postgres psql -U cert_app -d certificates_db -c "SELECT 1 FROM certificates.certificates LIMIT 0;" >/dev/null 2>&1; then
    echo "✅ Пользователь cert_app имеет доступ к таблицам"
else
    echo "❌ Пользователь cert_app не имеет доступа к таблицам"
    exit 1
fi

# Проверка статуса сервисов
echo "📊 Проверка статуса сервисов..."
$DOCKER_COMPOSE ps

# Проверка API
echo "🔍 Проверка API..."
sleep 5
if curl -f http://localhost:8000/health >/dev/null 2>&1; then
    echo "✅ API работает"
    echo "📋 Статус компонентов:"
    curl -s http://localhost:8000/health | python3 -m json.tool || true
else
    echo "⚠️ API еще запускается или есть проблемы"
    echo "📋 Логи API:"
    $DOCKER_COMPOSE logs api --tail=10
fi

echo ""
echo "🎉 Система успешно запущена!"
echo ""
echo "🔗 Полезные команды:"
echo "  $DOCKER_COMPOSE logs -f              # Просмотр логов всех сервисов"
echo "  $DOCKER_COMPOSE logs -f bot          # Логи только бота"
echo "  $DOCKER_COMPOSE ps                   # Статус сервисов"
echo "  curl http://localhost:8000/health    # Проверка API"
echo "  curl http://localhost:8000/docs      # Документация API"
echo ""
echo "🤖 Telegram бот готов к работе!"
echo "   Найдите вашего бота и отправьте /start"
echo ""
echo "📋 Для отладки проблем:"
echo "  $DOCKER_COMPOSE logs postgres        # Логи БД"
echo "  $DOCKER_COMPOSE exec postgres psql -U cert_app -d certificates_db"
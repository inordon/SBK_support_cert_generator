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

# Создание скрипта создания пользователя, если его нет
if [ ! -f database/create_user.sh ]; then
    echo "📝 Создание скрипта database/create_user.sh..."
    cat > database/create_user.sh << 'EOF'
#!/bin/bash
# database/create_user.sh
# Скрипт для создания пользователя cert_app после создания схемы

set -e

echo "Creating application user cert_app..."

# Проверяем, что переменная CERT_APP_PASSWORD задана
if [ -z "$CERT_APP_PASSWORD" ]; then
    echo "ERROR: CERT_APP_PASSWORD environment variable is not set"
    exit 1
fi

# Создаем пользователя cert_app с паролем и правами
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Проверяем, существует ли пользователь
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'cert_app') THEN
            -- Создание пользователя cert_app
            CREATE USER cert_app WITH PASSWORD '$CERT_APP_PASSWORD';
            RAISE NOTICE 'User cert_app created';
        ELSE
            RAISE NOTICE 'User cert_app already exists';
        END IF;
    END
    \$\$;

    -- Предоставление прав на схему certificates
    GRANT USAGE ON SCHEMA certificates TO cert_app;

    -- Предоставление прав на таблицы
    GRANT SELECT, INSERT, UPDATE, DELETE ON certificates TO cert_app;
    GRANT SELECT, INSERT ON certificate_history TO cert_app;

    -- Предоставление прав на представления
    GRANT SELECT ON active_certificates TO cert_app;
    GRANT SELECT ON certificates_with_history TO cert_app;

    -- Предоставление прав на последовательности
    GRANT USAGE ON ALL SEQUENCES IN SCHEMA certificates TO cert_app;

    -- Проверка создания пользователя
    SELECT 'User cert_app configured successfully' as result;
EOSQL

echo "User cert_app created successfully with all necessary permissions."
EOF
fi

# Установка прав на скрипт
chmod +x database/create_user.sh

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

# Проверка создания пользователя
echo "🔍 Проверка пользователя cert_app..."
if $DOCKER_COMPOSE exec -T postgres psql -U postgres -d certificates_db -c "SELECT usename FROM pg_user WHERE usename = 'cert_app';" | grep -q cert_app; then
    echo "✅ Пользователь cert_app создан успешно"
else
    echo "❌ Пользователь cert_app не создан"
    echo "📋 Логи PostgreSQL:"
    $DOCKER_COMPOSE logs postgres --tail=20
    exit 1
fi

# Проверка подключения пользователя
echo "🔍 Проверка подключения пользователя..."
if $DOCKER_COMPOSE exec -T postgres psql -U cert_app -d certificates_db -c "SELECT current_user;" >/dev/null 2>&1; then
    echo "✅ Пользователь cert_app может подключаться к БД"
else
    echo "❌ Пользователь cert_app не может подключиться к БД"
    exit 1
fi

# Проверка таблиц
echo "🔍 Проверка таблиц..."
if $DOCKER_COMPOSE exec -T postgres psql -U cert_app -d certificates_db -c "\dt certificates.*" | grep -q certificates; then
    echo "✅ Таблицы созданы и доступны"
else
    echo "❌ Таблицы не созданы или недоступны"
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
else
    echo "⚠️ API еще запускается или есть проблемы"
    echo "📋 Логи API:"
    $DOCKER_COMPOSE logs api --tail=10
fi

echo ""
echo "🎉 Система успешно запущена!"
echo ""
echo "🔗 Полезные команды:"
echo "  $DOCKER_COMPOSE logs -f              # Просмотр логов"
echo "  $DOCKER_COMPOSE ps                   # Статус сервисов"
echo "  curl http://localhost:8000/health   # Проверка API"
echo ""
echo "🤖 Telegram бот готов к работе!"
echo "   Найдите вашего бота и отправьте /start"
echo ""
echo "📋 Для отладки:"
echo "  $DOCKER_COMPOSE logs bot     # Логи бота"
echo "  $DOCKER_COMPOSE logs api     # Логи API"
echo "  $DOCKER_COMPOSE logs postgres # Логи БД"
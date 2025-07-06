#!/bin/bash
# create_user.sh
# Скрипт для создания пользователя cert_app с паролем из переменной окружения

set -e

echo "Creating user cert_app..."

# Проверяем, что переменная CERT_APP_PASSWORD задана
if [ -z "$CERT_APP_PASSWORD" ]; then
    echo "ERROR: CERT_APP_PASSWORD environment variable is not set"
    exit 1
fi

# Создаем пользователя cert_app с паролем и правами
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Создание пользователя cert_app
    CREATE USER cert_app WITH PASSWORD '$CERT_APP_PASSWORD';

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
    SELECT 'User cert_app created successfully' as result;
EOSQL

echo "User cert_app created successfully with all necessary permissions."
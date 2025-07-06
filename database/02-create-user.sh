#!/bin/bash
# database/02-create-user.sh
set -e

echo "Creating database user cert_app..."

# Используем переменную окружения, переданную из docker-compose
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Создаем роль только если её нет
    DO
    \$do\$
    BEGIN
        IF NOT EXISTS (
            SELECT FROM pg_catalog.pg_roles
            WHERE rolname = 'cert_app'
        ) THEN
            CREATE ROLE cert_app LOGIN PASSWORD '${CERT_APP_PASSWORD}';
            RAISE NOTICE 'User cert_app created';
        ELSE
            ALTER ROLE cert_app WITH PASSWORD '${CERT_APP_PASSWORD}';
            RAISE NOTICE 'User cert_app password updated';
        END IF;
    END
    \$do\$;

    -- Предоставляем права на схему
    GRANT USAGE ON SCHEMA certificates TO cert_app;

    -- Права на таблицы
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA certificates TO cert_app;
    GRANT SELECT, INSERT, UPDATE, DELETE ON certificates.certificates TO cert_app;
    GRANT SELECT, INSERT ON certificates.certificate_history TO cert_app;

    -- Права на последовательности
    GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA certificates TO cert_app;

    -- Права на функции
    GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA certificates TO cert_app;

    -- Права по умолчанию для будущих объектов
    ALTER DEFAULT PRIVILEGES IN SCHEMA certificates
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO cert_app;

    ALTER DEFAULT PRIVILEGES IN SCHEMA certificates
        GRANT USAGE, SELECT ON SEQUENCES TO cert_app;

    ALTER DEFAULT PRIVILEGES IN SCHEMA certificates
        GRANT EXECUTE ON FUNCTIONS TO cert_app;

    -- Проверка
    SELECT 'User cert_app configured successfully' as status;
EOSQL

echo "Database user created successfully!"
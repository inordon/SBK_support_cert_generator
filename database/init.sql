-- database/init.sql
-- Схема базы данных для системы управления сертификатами

-- Создание расширений
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Создание схемы
CREATE SCHEMA IF NOT EXISTS certificates;
SET search_path TO certificates, public;

-- Таблица сертификатов
CREATE TABLE certificates (
                              id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                              certificate_id VARCHAR(23) NOT NULL UNIQUE,
                              domain VARCHAR(255) NOT NULL,
                              inn VARCHAR(12) NOT NULL,
                              valid_from DATE NOT NULL,
                              valid_to DATE NOT NULL,
                              users_count INTEGER NOT NULL CHECK (users_count > 0 AND users_count <= 1000),
                              created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                              created_by BIGINT,
                              is_active BOOLEAN DEFAULT TRUE,

    -- Ограничения
                              CONSTRAINT chk_certificate_id_format
                                  CHECK (certificate_id ~ '^[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}

-- Таблица истории действий с сертификатами
CREATE TABLE certificate_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    certificate_id VARCHAR(23) NOT NULL,
    action VARCHAR(50) NOT NULL,
    performed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    performed_by BIGINT,
    details JSONB,

    -- Внешний ключ
    CONSTRAINT fk_certificate_history_cert
        FOREIGN KEY (certificate_id) REFERENCES certificates(certificate_id)
);

-- Индексы для оптимизации запросов
-- Основные индексы
CREATE INDEX idx_certificates_certificate_id ON certificates(certificate_id);
CREATE INDEX idx_certificates_domain ON certificates(domain);
CREATE INDEX idx_certificates_inn ON certificates(inn);
CREATE INDEX idx_certificates_created_at ON certificates(created_at);
CREATE INDEX idx_certificates_valid_from ON certificates(valid_from);
CREATE INDEX idx_certificates_valid_to ON certificates(valid_to);
CREATE INDEX idx_certificates_is_active ON certificates(is_active);

-- Составные индексы
CREATE INDEX idx_certificates_domain_active ON certificates(domain, is_active);
CREATE INDEX idx_certificates_active_valid ON certificates(is_active, valid_from, valid_to);
CREATE INDEX idx_certificates_created_by_date ON certificates(created_by, created_at);

-- Индексы для истории
CREATE INDEX idx_certificate_history_cert_id ON certificate_history(certificate_id);
CREATE INDEX idx_certificate_history_action ON certificate_history(action);
CREATE INDEX idx_certificate_history_performed_at ON certificate_history(performed_at);
CREATE INDEX idx_certificate_history_performed_by ON certificate_history(performed_by);

-- GIN индекс для JSONB поля details
CREATE INDEX idx_certificate_history_details ON certificate_history USING gin(details);

-- Индекс для полнотекстового поиска по домену
CREATE INDEX idx_certificates_domain_trgm ON certificates USING gin(domain gin_trgm_ops);

-- Функция для автоматического логирования изменений
CREATE OR REPLACE FUNCTION log_certificate_changes()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO certificate_history (certificate_id, action, details)
        VALUES (NEW.certificate_id, 'CREATE', row_to_json(NEW));
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO certificate_history (certificate_id, action, details)
        VALUES (NEW.certificate_id, 'UPDATE',
                jsonb_build_object(
                    'old', row_to_json(OLD),
                    'new', row_to_json(NEW)
                ));
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO certificate_history (certificate_id, action, details)
        VALUES (OLD.certificate_id, 'DELETE', row_to_json(OLD));
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Триггер для автоматического логирования
CREATE TRIGGER trigger_certificate_changes
    AFTER INSERT OR UPDATE OR DELETE ON certificates
    FOR EACH ROW EXECUTE FUNCTION log_certificate_changes();

-- Функция для проверки уникальности активных сертификатов по домену
CREATE OR REPLACE FUNCTION check_unique_active_domain()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.is_active = TRUE THEN
        IF EXISTS (
            SELECT 1 FROM certificates
            WHERE domain = NEW.domain
            AND is_active = TRUE
            AND certificate_id != NEW.certificate_id
        ) THEN
            RAISE EXCEPTION 'Активный сертификат для домена % уже существует', NEW.domain;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Триггер для проверки уникальности активных доменов
CREATE TRIGGER trigger_unique_active_domain
    BEFORE INSERT OR UPDATE ON certificates
    FOR EACH ROW EXECUTE FUNCTION check_unique_active_domain();

-- Функция для очистки истории старше определенного периода
CREATE OR REPLACE FUNCTION cleanup_old_history(retention_days INTEGER DEFAULT 365)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM certificate_history
    WHERE performed_at < NOW() - INTERVAL '1 day' * retention_days;

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Функция для получения статистики по сертификатам
CREATE OR REPLACE FUNCTION get_certificate_stats()
RETURNS TABLE (
    total_certificates BIGINT,
    active_certificates BIGINT,
    expired_certificates BIGINT,
    domains_count BIGINT,
    avg_users_per_cert NUMERIC,
    certificates_by_month JSON
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*) as total_certificates,
        COUNT(*) FILTER (WHERE is_active = TRUE AND valid_to >= CURRENT_DATE) as active_certificates,
        COUNT(*) FILTER (WHERE valid_to < CURRENT_DATE) as expired_certificates,
        COUNT(DISTINCT domain) as domains_count,
        AVG(users_count) as avg_users_per_cert,
        (
            SELECT json_agg(monthly_stats)
            FROM (
                SELECT
                    TO_CHAR(created_at, 'YYYY-MM') as month,
                    COUNT(*) as count
                FROM certificates
                WHERE created_at >= CURRENT_DATE - INTERVAL '12 months'
                GROUP BY TO_CHAR(created_at, 'YYYY-MM')
                ORDER BY month
            ) monthly_stats
        ) as certificates_by_month
    FROM certificates;
END;
$$ LANGUAGE plpgsql;

-- Представление для активных сертификатов
CREATE VIEW active_certificates AS
SELECT
    c.*,
    CASE
        WHEN CURRENT_DATE < c.valid_from THEN 'not_yet_valid'
        WHEN CURRENT_DATE > c.valid_to THEN 'expired'
        ELSE 'valid'
    END as status,
    (c.valid_to - CURRENT_DATE) as days_until_expiry
FROM certificates c
WHERE c.is_active = TRUE;

-- Представление для сертификатов с историей
CREATE VIEW certificates_with_history AS
SELECT
    c.*,
    (
        SELECT json_agg(
            json_build_object(
                'action', h.action,
                'performed_at', h.performed_at,
                'performed_by', h.performed_by,
                'details', h.details
            ) ORDER BY h.performed_at DESC
        )
        FROM certificate_history h
        WHERE h.certificate_id = c.certificate_id
    ) as history
FROM certificates c;

-- Создание пользователя для приложения
CREATE USER cert_app WITH PASSWORD 'change_this_password';

-- Предоставление прав
GRANT USAGE ON SCHEMA certificates TO cert_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON certificates TO cert_app;
GRANT SELECT, INSERT ON certificate_history TO cert_app;
GRANT SELECT ON active_certificates TO cert_app;
GRANT SELECT ON certificates_with_history TO cert_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA certificates TO cert_app;

-- Комментарии к таблицам и столбцам
COMMENT ON TABLE certificates IS 'Основная таблица сертификатов';
COMMENT ON COLUMN certificates.certificate_id IS 'Уникальный ID сертификата в формате XXXXX-XXXXX-XXXXX-XXXXX';
COMMENT ON COLUMN certificates.domain IS 'Доменное имя, поддерживает wildcard (*.example.com)';
COMMENT ON COLUMN certificates.inn IS 'ИНН организации (10 или 12 цифр)';
COMMENT ON COLUMN certificates.valid_from IS 'Дата начала действия сертификата';
COMMENT ON COLUMN certificates.valid_to IS 'Дата окончания действия сертификата';
COMMENT ON COLUMN certificates.users_count IS 'Количество пользователей (1-1000)';
COMMENT ON COLUMN certificates.created_by IS 'ID пользователя Telegram, создавшего сертификат';
COMMENT ON COLUMN certificates.is_active IS 'Флаг активности сертификата';

COMMENT ON TABLE certificate_history IS 'История действий с сертификатами';
COMMENT ON COLUMN certificate_history.action IS 'Тип действия (CREATE, UPDATE, DELETE, VERIFY)';
COMMENT ON COLUMN certificate_history.performed_by IS 'ID пользователя, выполнившего действие';
COMMENT ON COLUMN certificate_history.details IS 'Дополнительные детали действия в формате JSON';

-- Примеры запросов для работы с данными
/*
-- Получение активных сертификатов для домена
SELECT * FROM active_certificates WHERE domain = 'example.com';

-- Получение истории действий с сертификатом
SELECT * FROM certificate_history
WHERE certificate_id = 'ABCD1-XYZ12-QWRT5-WX0124'
ORDER BY performed_at DESC;

-- Поиск сертификатов по части домена
SELECT * FROM certificates
WHERE domain % 'example'
ORDER BY similarity(domain, 'example') DESC;

-- Статистика по сертификатам
SELECT * FROM get_certificate_stats();

-- Сертификаты, истекающие в ближайшие 30 дней
SELECT certificate_id, domain, valid_to, days_until_expiry
FROM active_certificates
WHERE days_until_expiry <= 30 AND days_until_expiry > 0
ORDER BY days_until_expiry;

-- Очистка старой истории (старше года)
SELECT cleanup_old_history(365);
*/),
    CONSTRAINT chk_domain_format
        CHECK (domain ~ '^(\*\.)?[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)*

-- Таблица истории действий с сертификатами
CREATE TABLE certificate_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    certificate_id VARCHAR(23) NOT NULL,
    action VARCHAR(50) NOT NULL,
    performed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    performed_by BIGINT,
    details JSONB,

    -- Внешний ключ
    CONSTRAINT fk_certificate_history_cert
        FOREIGN KEY (certificate_id) REFERENCES certificates(certificate_id)
);

-- Индексы для оптимизации запросов
-- Основные индексы
CREATE INDEX idx_certificates_certificate_id ON certificates(certificate_id);
CREATE INDEX idx_certificates_domain ON certificates(domain);
CREATE INDEX idx_certificates_inn ON certificates(inn);
CREATE INDEX idx_certificates_created_at ON certificates(created_at);
CREATE INDEX idx_certificates_valid_from ON certificates(valid_from);
CREATE INDEX idx_certificates_valid_to ON certificates(valid_to);
CREATE INDEX idx_certificates_is_active ON certificates(is_active);

-- Составные индексы
CREATE INDEX idx_certificates_domain_active ON certificates(domain, is_active);
CREATE INDEX idx_certificates_active_valid ON certificates(is_active, valid_from, valid_to);
CREATE INDEX idx_certificates_created_by_date ON certificates(created_by, created_at);

-- Индексы для истории
CREATE INDEX idx_certificate_history_cert_id ON certificate_history(certificate_id);
CREATE INDEX idx_certificate_history_action ON certificate_history(action);
CREATE INDEX idx_certificate_history_performed_at ON certificate_history(performed_at);
CREATE INDEX idx_certificate_history_performed_by ON certificate_history(performed_by);

-- GIN индекс для JSONB поля details
CREATE INDEX idx_certificate_history_details ON certificate_history USING gin(details);

-- Индекс для полнотекстового поиска по домену
CREATE INDEX idx_certificates_domain_trgm ON certificates USING gin(domain gin_trgm_ops);

-- Функция для автоматического логирования изменений
CREATE OR REPLACE FUNCTION log_certificate_changes()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO certificate_history (certificate_id, action, details)
        VALUES (NEW.certificate_id, 'CREATE', row_to_json(NEW));
RETURN NEW;
ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO certificate_history (certificate_id, action, details)
        VALUES (NEW.certificate_id, 'UPDATE',
                jsonb_build_object(
                    'old', row_to_json(OLD),
                    'new', row_to_json(NEW)
                ));
RETURN NEW;
ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO certificate_history (certificate_id, action, details)
        VALUES (OLD.certificate_id, 'DELETE', row_to_json(OLD));
RETURN OLD;
END IF;
RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Триггер для автоматического логирования
CREATE TRIGGER trigger_certificate_changes
    AFTER INSERT OR UPDATE OR DELETE ON certificates
    FOR EACH ROW EXECUTE FUNCTION log_certificate_changes();

-- Функция для проверки уникальности активных сертификатов по домену
CREATE OR REPLACE FUNCTION check_unique_active_domain()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.is_active = TRUE THEN
        IF EXISTS (
            SELECT 1 FROM certificates
            WHERE domain = NEW.domain
            AND is_active = TRUE
            AND certificate_id != NEW.certificate_id
        ) THEN
            RAISE EXCEPTION 'Активный сертификат для домена % уже существует', NEW.domain;
END IF;
END IF;
RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Триггер для проверки уникальности активных доменов
CREATE TRIGGER trigger_unique_active_domain
    BEFORE INSERT OR UPDATE ON certificates
                         FOR EACH ROW EXECUTE FUNCTION check_unique_active_domain();

-- Функция для очистки истории старше определенного периода
CREATE OR REPLACE FUNCTION cleanup_old_history(retention_days INTEGER DEFAULT 365)
RETURNS INTEGER AS $$
DECLARE
deleted_count INTEGER;
BEGIN
DELETE FROM certificate_history
WHERE performed_at < NOW() - INTERVAL '1 day' * retention_days;

GET DIAGNOSTICS deleted_count = ROW_COUNT;
RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Функция для получения статистики по сертификатам
CREATE OR REPLACE FUNCTION get_certificate_stats()
RETURNS TABLE (
    total_certificates BIGINT,
    active_certificates BIGINT,
    expired_certificates BIGINT,
    domains_count BIGINT,
    avg_users_per_cert NUMERIC,
    certificates_by_month JSON
) AS $$
BEGIN
RETURN QUERY
SELECT
    COUNT(*) as total_certificates,
    COUNT(*) FILTER (WHERE is_active = TRUE AND valid_to >= CURRENT_DATE) as active_certificates,
        COUNT(*) FILTER (WHERE valid_to < CURRENT_DATE) as expired_certificates,
        COUNT(DISTINCT domain) as domains_count,
    AVG(users_count) as avg_users_per_cert,
    (
        SELECT json_agg(monthly_stats)
        FROM (
                 SELECT
                     TO_CHAR(created_at, 'YYYY-MM') as month,
                    COUNT(*) as count
                 FROM certificates
                 WHERE created_at >= CURRENT_DATE - INTERVAL '12 months'
                 GROUP BY TO_CHAR(created_at, 'YYYY-MM')
                 ORDER BY month
             ) monthly_stats
    ) as certificates_by_month
FROM certificates;
END;
$$ LANGUAGE plpgsql;

-- Представление для активных сертификатов
CREATE VIEW active_certificates AS
SELECT
    c.*,
    CASE
        WHEN CURRENT_DATE < c.valid_from THEN 'not_yet_valid'
        WHEN CURRENT_DATE > c.valid_to THEN 'expired'
        ELSE 'valid'
        END as status,
    (c.valid_to - CURRENT_DATE) as days_until_expiry
FROM certificates c
WHERE c.is_active = TRUE;

-- Представление для сертификатов с историей
CREATE VIEW certificates_with_history AS
SELECT
    c.*,
    (
        SELECT json_agg(
                       json_build_object(
                               'action', h.action,
                               'performed_at', h.performed_at,
                               'performed_by', h.performed_by,
                               'details', h.details
                       ) ORDER BY h.performed_at DESC
               )
        FROM certificate_history h
        WHERE h.certificate_id = c.certificate_id
    ) as history
FROM certificates c;

-- Создание пользователя для приложения
CREATE USER cert_app WITH PASSWORD 'change_this_password';

-- Предоставление прав
GRANT USAGE ON SCHEMA certificates TO cert_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON certificates TO cert_app;
GRANT SELECT, INSERT ON certificate_history TO cert_app;
GRANT SELECT ON active_certificates TO cert_app;
GRANT SELECT ON certificates_with_history TO cert_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA certificates TO cert_app;

-- Комментарии к таблицам и столбцам
COMMENT ON TABLE certificates IS 'Основная таблица сертификатов';
COMMENT ON COLUMN certificates.certificate_id IS 'Уникальный ID сертификата в формате XXXXX-XXXXX-XXXXX-XXXXX';
COMMENT ON COLUMN certificates.domain IS 'Доменное имя, поддерживает wildcard (*.example.com)';
COMMENT ON COLUMN certificates.inn IS 'ИНН организации (10 или 12 цифр)';
COMMENT ON COLUMN certificates.valid_from IS 'Дата начала действия сертификата';
COMMENT ON COLUMN certificates.valid_to IS 'Дата окончания действия сертификата';
COMMENT ON COLUMN certificates.users_count IS 'Количество пользователей (1-1000)';
COMMENT ON COLUMN certificates.created_by IS 'ID пользователя Telegram, создавшего сертификат';
COMMENT ON COLUMN certificates.is_active IS 'Флаг активности сертификата';

COMMENT ON TABLE certificate_history IS 'История действий с сертификатами';
COMMENT ON COLUMN certificate_history.action IS 'Тип действия (CREATE, UPDATE, DELETE, VERIFY)';
COMMENT ON COLUMN certificate_history.performed_by IS 'ID пользователя, выполнившего действие';
COMMENT ON COLUMN certificate_history.details IS 'Дополнительные детали действия в формате JSON';

-- Примеры запросов для работы с данными
/*
-- Получение активных сертификатов для домена
SELECT * FROM active_certificates WHERE domain = 'example.com';

-- Получение истории действий с сертификатом
SELECT * FROM certificate_history
WHERE certificate_id = 'ABCD1-XYZ12-QWRT5-WX0124'
ORDER BY performed_at DESC;

-- Поиск сертификатов по части домена
SELECT * FROM certificates
WHERE domain % 'example'
ORDER BY similarity(domain, 'example') DESC;

-- Статистика по сертификатам
SELECT * FROM get_certificate_stats();

-- Сертификаты, истекающие в ближайшие 30 дней
SELECT certificate_id, domain, valid_to, days_until_expiry
FROM active_certificates
WHERE days_until_expiry <= 30 AND days_until_expiry > 0
ORDER BY days_until_expiry;

-- Очистка старой истории (старше года)
SELECT cleanup_old_history(365);
*/),
    CONSTRAINT chk_inn_format
        CHECK (inn ~ '^\d{10}$|^\d{12}

-- Таблица истории действий с сертификатами
CREATE TABLE certificate_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    certificate_id VARCHAR(23) NOT NULL,
    action VARCHAR(50) NOT NULL,
    performed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    performed_by BIGINT,
    details JSONB,

    -- Внешний ключ
    CONSTRAINT fk_certificate_history_cert
        FOREIGN KEY (certificate_id) REFERENCES certificates(certificate_id)
);

-- Индексы для оптимизации запросов
-- Основные индексы
CREATE INDEX idx_certificates_certificate_id ON certificates(certificate_id);
CREATE INDEX idx_certificates_domain ON certificates(domain);
CREATE INDEX idx_certificates_inn ON certificates(inn);
CREATE INDEX idx_certificates_created_at ON certificates(created_at);
CREATE INDEX idx_certificates_valid_from ON certificates(valid_from);
CREATE INDEX idx_certificates_valid_to ON certificates(valid_to);
CREATE INDEX idx_certificates_is_active ON certificates(is_active);

-- Составные индексы
CREATE INDEX idx_certificates_domain_active ON certificates(domain, is_active);
CREATE INDEX idx_certificates_active_valid ON certificates(is_active, valid_from, valid_to);
CREATE INDEX idx_certificates_created_by_date ON certificates(created_by, created_at);

-- Индексы для истории
CREATE INDEX idx_certificate_history_cert_id ON certificate_history(certificate_id);
CREATE INDEX idx_certificate_history_action ON certificate_history(action);
CREATE INDEX idx_certificate_history_performed_at ON certificate_history(performed_at);
CREATE INDEX idx_certificate_history_performed_by ON certificate_history(performed_by);

-- GIN индекс для JSONB поля details
CREATE INDEX idx_certificate_history_details ON certificate_history USING gin(details);

-- Индекс для полнотекстового поиска по домену
CREATE INDEX idx_certificates_domain_trgm ON certificates USING gin(domain gin_trgm_ops);

-- Функция для автоматического логирования изменений
CREATE OR REPLACE FUNCTION log_certificate_changes()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO certificate_history (certificate_id, action, details)
        VALUES (NEW.certificate_id, 'CREATE', row_to_json(NEW));
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO certificate_history (certificate_id, action, details)
        VALUES (NEW.certificate_id, 'UPDATE',
                jsonb_build_object(
                    'old', row_to_json(OLD),
                    'new', row_to_json(NEW)
                ));
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO certificate_history (certificate_id, action, details)
        VALUES (OLD.certificate_id, 'DELETE', row_to_json(OLD));
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Триггер для автоматического логирования
CREATE TRIGGER trigger_certificate_changes
    AFTER INSERT OR UPDATE OR DELETE ON certificates
    FOR EACH ROW EXECUTE FUNCTION log_certificate_changes();

-- Функция для проверки уникальности активных сертификатов по домену
CREATE OR REPLACE FUNCTION check_unique_active_domain()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.is_active = TRUE THEN
        IF EXISTS (
            SELECT 1 FROM certificates
            WHERE domain = NEW.domain
            AND is_active = TRUE
            AND certificate_id != NEW.certificate_id
        ) THEN
            RAISE EXCEPTION 'Активный сертификат для домена % уже существует', NEW.domain;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Триггер для проверки уникальности активных доменов
CREATE TRIGGER trigger_unique_active_domain
    BEFORE INSERT OR UPDATE ON certificates
    FOR EACH ROW EXECUTE FUNCTION check_unique_active_domain();

-- Функция для очистки истории старше определенного периода
CREATE OR REPLACE FUNCTION cleanup_old_history(retention_days INTEGER DEFAULT 365)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM certificate_history
    WHERE performed_at < NOW() - INTERVAL '1 day' * retention_days;

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Функция для получения статистики по сертификатам
CREATE OR REPLACE FUNCTION get_certificate_stats()
RETURNS TABLE (
    total_certificates BIGINT,
    active_certificates BIGINT,
    expired_certificates BIGINT,
    domains_count BIGINT,
    avg_users_per_cert NUMERIC,
    certificates_by_month JSON
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*) as total_certificates,
        COUNT(*) FILTER (WHERE is_active = TRUE AND valid_to >= CURRENT_DATE) as active_certificates,
        COUNT(*) FILTER (WHERE valid_to < CURRENT_DATE) as expired_certificates,
        COUNT(DISTINCT domain) as domains_count,
        AVG(users_count) as avg_users_per_cert,
        (
            SELECT json_agg(monthly_stats)
            FROM (
                SELECT
                    TO_CHAR(created_at, 'YYYY-MM') as month,
                    COUNT(*) as count
                FROM certificates
                WHERE created_at >= CURRENT_DATE - INTERVAL '12 months'
                GROUP BY TO_CHAR(created_at, 'YYYY-MM')
                ORDER BY month
            ) monthly_stats
        ) as certificates_by_month
    FROM certificates;
END;
$$ LANGUAGE plpgsql;

-- Представление для активных сертификатов
CREATE VIEW active_certificates AS
SELECT
    c.*,
    CASE
        WHEN CURRENT_DATE < c.valid_from THEN 'not_yet_valid'
        WHEN CURRENT_DATE > c.valid_to THEN 'expired'
        ELSE 'valid'
    END as status,
    (c.valid_to - CURRENT_DATE) as days_until_expiry
FROM certificates c
WHERE c.is_active = TRUE;

-- Представление для сертификатов с историей
CREATE VIEW certificates_with_history AS
SELECT
    c.*,
    (
        SELECT json_agg(
            json_build_object(
                'action', h.action,
                'performed_at', h.performed_at,
                'performed_by', h.performed_by,
                'details', h.details
            ) ORDER BY h.performed_at DESC
        )
        FROM certificate_history h
        WHERE h.certificate_id = c.certificate_id
    ) as history
FROM certificates c;

-- Создание пользователя для приложения
CREATE USER cert_app WITH PASSWORD 'change_this_password';

-- Предоставление прав
GRANT USAGE ON SCHEMA certificates TO cert_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON certificates TO cert_app;
GRANT SELECT, INSERT ON certificate_history TO cert_app;
GRANT SELECT ON active_certificates TO cert_app;
GRANT SELECT ON certificates_with_history TO cert_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA certificates TO cert_app;

-- Комментарии к таблицам и столбцам
COMMENT ON TABLE certificates IS 'Основная таблица сертификатов';
COMMENT ON COLUMN certificates.certificate_id IS 'Уникальный ID сертификата в формате XXXXX-XXXXX-XXXXX-XXXXX';
COMMENT ON COLUMN certificates.domain IS 'Доменное имя, поддерживает wildcard (*.example.com)';
COMMENT ON COLUMN certificates.inn IS 'ИНН организации (10 или 12 цифр)';
COMMENT ON COLUMN certificates.valid_from IS 'Дата начала действия сертификата';
COMMENT ON COLUMN certificates.valid_to IS 'Дата окончания действия сертификата';
COMMENT ON COLUMN certificates.users_count IS 'Количество пользователей (1-1000)';
COMMENT ON COLUMN certificates.created_by IS 'ID пользователя Telegram, создавшего сертификат';
COMMENT ON COLUMN certificates.is_active IS 'Флаг активности сертификата';

COMMENT ON TABLE certificate_history IS 'История действий с сертификатами';
COMMENT ON COLUMN certificate_history.action IS 'Тип действия (CREATE, UPDATE, DELETE, VERIFY)';
COMMENT ON COLUMN certificate_history.performed_by IS 'ID пользователя, выполнившего действие';
COMMENT ON COLUMN certificate_history.details IS 'Дополнительные детали действия в формате JSON';

-- Примеры запросов для работы с данными
/*
-- Получение активных сертификатов для домена
SELECT * FROM active_certificates WHERE domain = 'example.com';

-- Получение истории действий с сертификатом
SELECT * FROM certificate_history
WHERE certificate_id = 'ABCD1-XYZ12-QWRT5-WX0124'
ORDER BY performed_at DESC;

-- Поиск сертификатов по части домена
SELECT * FROM certificates
WHERE domain % 'example'
ORDER BY similarity(domain, 'example') DESC;

-- Статистика по сертификатам
SELECT * FROM get_certificate_stats();

-- Сертификаты, истекающие в ближайшие 30 дней
SELECT certificate_id, domain, valid_to, days_until_expiry
FROM active_certificates
WHERE days_until_expiry <= 30 AND days_until_expiry > 0
ORDER BY days_until_expiry;

-- Очистка старой истории (старше года)
SELECT cleanup_old_history(365);
*/),
    CONSTRAINT chk_valid_period
        CHECK (valid_from < valid_to),
    CONSTRAINT chk_max_period
        CHECK ((valid_to - valid_from) <= INTERVAL '5 years')
);

-- Таблица истории действий с сертификатами
CREATE TABLE certificate_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    certificate_id VARCHAR(23) NOT NULL,
    action VARCHAR(50) NOT NULL,
    performed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    performed_by BIGINT,
    details JSONB,

    -- Внешний ключ
    CONSTRAINT fk_certificate_history_cert
        FOREIGN KEY (certificate_id) REFERENCES certificates(certificate_id)
);

-- Индексы для оптимизации запросов
-- Основные индексы
CREATE INDEX idx_certificates_certificate_id ON certificates(certificate_id);
CREATE INDEX idx_certificates_domain ON certificates(domain);
CREATE INDEX idx_certificates_inn ON certificates(inn);
CREATE INDEX idx_certificates_created_at ON certificates(created_at);
CREATE INDEX idx_certificates_valid_from ON certificates(valid_from);
CREATE INDEX idx_certificates_valid_to ON certificates(valid_to);
CREATE INDEX idx_certificates_is_active ON certificates(is_active);

-- Составные индексы
CREATE INDEX idx_certificates_domain_active ON certificates(domain, is_active);
CREATE INDEX idx_certificates_active_valid ON certificates(is_active, valid_from, valid_to);
CREATE INDEX idx_certificates_created_by_date ON certificates(created_by, created_at);

-- Индексы для истории
CREATE INDEX idx_certificate_history_cert_id ON certificate_history(certificate_id);
CREATE INDEX idx_certificate_history_action ON certificate_history(action);
CREATE INDEX idx_certificate_history_performed_at ON certificate_history(performed_at);
CREATE INDEX idx_certificate_history_performed_by ON certificate_history(performed_by);

-- GIN индекс для JSONB поля details
CREATE INDEX idx_certificate_history_details ON certificate_history USING gin(details);

-- Индекс для полнотекстового поиска по домену
CREATE INDEX idx_certificates_domain_trgm ON certificates USING gin(domain gin_trgm_ops);

-- Функция для автоматического логирования изменений
CREATE OR REPLACE FUNCTION log_certificate_changes()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO certificate_history (certificate_id, action, details)
        VALUES (NEW.certificate_id, 'CREATE', row_to_json(NEW));
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO certificate_history (certificate_id, action, details)
        VALUES (NEW.certificate_id, 'UPDATE',
                jsonb_build_object(
                    'old', row_to_json(OLD),
                    'new', row_to_json(NEW)
                ));
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO certificate_history (certificate_id, action, details)
        VALUES (OLD.certificate_id, 'DELETE', row_to_json(OLD));
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Триггер для автоматического логирования
CREATE TRIGGER trigger_certificate_changes
    AFTER INSERT OR UPDATE OR DELETE ON certificates
    FOR EACH ROW EXECUTE FUNCTION log_certificate_changes();

-- Функция для проверки уникальности активных сертификатов по домену
CREATE OR REPLACE FUNCTION check_unique_active_domain()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.is_active = TRUE THEN
        IF EXISTS (
            SELECT 1 FROM certificates
            WHERE domain = NEW.domain
            AND is_active = TRUE
            AND certificate_id != NEW.certificate_id
        ) THEN
            RAISE EXCEPTION 'Активный сертификат для домена % уже существует', NEW.domain;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Триггер для проверки уникальности активных доменов
CREATE TRIGGER trigger_unique_active_domain
    BEFORE INSERT OR UPDATE ON certificates
    FOR EACH ROW EXECUTE FUNCTION check_unique_active_domain();

-- Функция для очистки истории старше определенного периода
CREATE OR REPLACE FUNCTION cleanup_old_history(retention_days INTEGER DEFAULT 365)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM certificate_history
    WHERE performed_at < NOW() - INTERVAL '1 day' * retention_days;

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Функция для получения статистики по сертификатам
CREATE OR REPLACE FUNCTION get_certificate_stats()
RETURNS TABLE (
    total_certificates BIGINT,
    active_certificates BIGINT,
    expired_certificates BIGINT,
    domains_count BIGINT,
    avg_users_per_cert NUMERIC,
    certificates_by_month JSON
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*) as total_certificates,
        COUNT(*) FILTER (WHERE is_active = TRUE AND valid_to >= CURRENT_DATE) as active_certificates,
        COUNT(*) FILTER (WHERE valid_to < CURRENT_DATE) as expired_certificates,
        COUNT(DISTINCT domain) as domains_count,
        AVG(users_count) as avg_users_per_cert,
        (
            SELECT json_agg(monthly_stats)
            FROM (
                SELECT
                    TO_CHAR(created_at, 'YYYY-MM') as month,
                    COUNT(*) as count
                FROM certificates
                WHERE created_at >= CURRENT_DATE - INTERVAL '12 months'
                GROUP BY TO_CHAR(created_at, 'YYYY-MM')
                ORDER BY month
            ) monthly_stats
        ) as certificates_by_month
    FROM certificates;
END;
$$ LANGUAGE plpgsql;

-- Представление для активных сертификатов
CREATE VIEW active_certificates AS
SELECT
    c.*,
    CASE
        WHEN CURRENT_DATE < c.valid_from THEN 'not_yet_valid'
        WHEN CURRENT_DATE > c.valid_to THEN 'expired'
        ELSE 'valid'
    END as status,
    (c.valid_to - CURRENT_DATE) as days_until_expiry
FROM certificates c
WHERE c.is_active = TRUE;

-- Представление для сертификатов с историей
CREATE VIEW certificates_with_history AS
SELECT
    c.*,
    (
        SELECT json_agg(
            json_build_object(
                'action', h.action,
                'performed_at', h.performed_at,
                'performed_by', h.performed_by,
                'details', h.details
            ) ORDER BY h.performed_at DESC
        )
        FROM certificate_history h
        WHERE h.certificate_id = c.certificate_id
    ) as history
FROM certificates c;

-- Создание пользователя для приложения
CREATE USER cert_app WITH PASSWORD 'change_this_password';

-- Предоставление прав
GRANT USAGE ON SCHEMA certificates TO cert_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON certificates TO cert_app;
GRANT SELECT, INSERT ON certificate_history TO cert_app;
GRANT SELECT ON active_certificates TO cert_app;
GRANT SELECT ON certificates_with_history TO cert_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA certificates TO cert_app;

-- Комментарии к таблицам и столбцам
COMMENT ON TABLE certificates IS 'Основная таблица сертификатов';
COMMENT ON COLUMN certificates.certificate_id IS 'Уникальный ID сертификата в формате XXXXX-XXXXX-XXXXX-XXXXX';
COMMENT ON COLUMN certificates.domain IS 'Доменное имя, поддерживает wildcard (*.example.com)';
COMMENT ON COLUMN certificates.inn IS 'ИНН организации (10 или 12 цифр)';
COMMENT ON COLUMN certificates.valid_from IS 'Дата начала действия сертификата';
COMMENT ON COLUMN certificates.valid_to IS 'Дата окончания действия сертификата';
COMMENT ON COLUMN certificates.users_count IS 'Количество пользователей (1-1000)';
COMMENT ON COLUMN certificates.created_by IS 'ID пользователя Telegram, создавшего сертификат';
COMMENT ON COLUMN certificates.is_active IS 'Флаг активности сертификата';

COMMENT ON TABLE certificate_history IS 'История действий с сертификатами';
COMMENT ON COLUMN certificate_history.action IS 'Тип действия (CREATE, UPDATE, DELETE, VERIFY)';
COMMENT ON COLUMN certificate_history.performed_by IS 'ID пользователя, выполнившего действие';
COMMENT ON COLUMN certificate_history.details IS 'Дополнительные детали действия в формате JSON';

-- Примеры запросов для работы с данными
/*
-- Получение активных сертификатов для домена
SELECT * FROM active_certificates WHERE domain = 'example.com';

-- Получение истории действий с сертификатом
SELECT * FROM certificate_history
WHERE certificate_id = 'ABCD1-XYZ12-QWRT5-WX0124'
ORDER BY performed_at DESC;

-- Поиск сертификатов по части домена
SELECT * FROM certificates
WHERE domain % 'example'
ORDER BY similarity(domain, 'example') DESC;

-- Статистика по сертификатам
SELECT * FROM get_certificate_stats();

-- Сертификаты, истекающие в ближайшие 30 дней
SELECT certificate_id, domain, valid_to, days_until_expiry
FROM active_certificates
WHERE days_until_expiry <= 30 AND days_until_expiry > 0
ORDER BY days_until_expiry;

-- Очистка старой истории (старше года)
SELECT cleanup_old_history(365);
*/
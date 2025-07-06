-- Инициализация базы данных для системы сертификатов
-- Этот скрипт выполняется при первом запуске PostgreSQL контейнера

-- Создание расширений
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Функция для обновления timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
RETURN NEW;
END;
$$ language 'plpgsql';

-- Таблица сертификатов
CREATE TABLE IF NOT EXISTS certificates (
                                            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    certificate_id VARCHAR(23) UNIQUE NOT NULL,
    domain VARCHAR(255) NOT NULL,
    inn VARCHAR(12) NOT NULL,
    valid_from DATE NOT NULL,
    valid_to DATE NOT NULL,
    users_count INTEGER NOT NULL CHECK (users_count > 0 AND users_count <= 1000),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
                             created_by VARCHAR(20) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                             );

-- Комментарии к таблице сертификатов
COMMENT ON TABLE certificates IS 'Основная таблица сертификатов';
COMMENT ON COLUMN certificates.id IS 'Уникальный идентификатор записи';
COMMENT ON COLUMN certificates.certificate_id IS 'ID сертификата в формате XXXXX-XXXXX-XXXXX-XXXXX';
COMMENT ON COLUMN certificates.domain IS 'Доменное имя (поддерживает wildcard)';
COMMENT ON COLUMN certificates.inn IS 'ИНН организации (10 или 12 цифр)';
COMMENT ON COLUMN certificates.valid_from IS 'Дата начала действия сертификата';
COMMENT ON COLUMN certificates.valid_to IS 'Дата окончания действия сертификата';
COMMENT ON COLUMN certificates.users_count IS 'Количество пользователей (от 1 до 1000)';
COMMENT ON COLUMN certificates.created_at IS 'Дата и время создания записи';
COMMENT ON COLUMN certificates.created_by IS 'Telegram ID пользователя, создавшего сертификат';
COMMENT ON COLUMN certificates.is_active IS 'Флаг активности сертификата';

-- Таблица истории изменений
CREATE TABLE IF NOT EXISTS certificate_history (
                                                   id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    certificate_id VARCHAR(23) NOT NULL,
    action VARCHAR(50) NOT NULL,
    performed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
                               performed_by VARCHAR(20) NOT NULL,
    details JSONB,
    CONSTRAINT fk_certificate_history_cert_id
    FOREIGN KEY (certificate_id)
    REFERENCES certificates(certificate_id)
                           ON DELETE CASCADE
    );

-- Комментарии к таблице истории
COMMENT ON TABLE certificate_history IS 'История изменений и действий с сертификатами';
COMMENT ON COLUMN certificate_history.certificate_id IS 'ID сертификата';
COMMENT ON COLUMN certificate_history.action IS 'Тип действия (created, verified, deactivated, etc.)';
COMMENT ON COLUMN certificate_history.performed_at IS 'Дата и время выполнения действия';
COMMENT ON COLUMN certificate_history.performed_by IS 'Telegram ID пользователя';
COMMENT ON COLUMN certificate_history.details IS 'Дополнительная информация в JSON формате';

-- Создание индексов для оптимизации производительности

-- Индексы для таблицы certificates
CREATE INDEX IF NOT EXISTS idx_certificates_certificate_id ON certificates(certificate_id);
CREATE INDEX IF NOT EXISTS idx_certificates_domain ON certificates(domain);
CREATE INDEX IF NOT EXISTS idx_certificates_inn ON certificates(inn);
CREATE INDEX IF NOT EXISTS idx_certificates_active_domain ON certificates(domain, is_active);
CREATE INDEX IF NOT EXISTS idx_certificates_active_inn ON certificates(inn, is_active);
CREATE INDEX IF NOT EXISTS idx_certificates_validity ON certificates(valid_from, valid_to);
CREATE INDEX IF NOT EXISTS idx_certificates_created_by ON certificates(created_by);
CREATE INDEX IF NOT EXISTS idx_certificates_created_at ON certificates(created_at);
CREATE INDEX IF NOT EXISTS idx_certificates_is_active ON certificates(is_active);

-- Составные индексы для часто используемых запросов
CREATE INDEX IF NOT EXISTS idx_certificates_active_valid ON certificates(is_active, valid_to)
    WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_certificates_domain_active_valid ON certificates(domain, is_active, valid_to);

-- Индексы для таблицы certificate_history
CREATE INDEX IF NOT EXISTS idx_history_certificate_id ON certificate_history(certificate_id);
CREATE INDEX IF NOT EXISTS idx_history_performed_at ON certificate_history(performed_at);
CREATE INDEX IF NOT EXISTS idx_history_action ON certificate_history(action);
CREATE INDEX IF NOT EXISTS idx_history_performed_by ON certificate_history(performed_by);

-- Составные индексы для истории
CREATE INDEX IF NOT EXISTS idx_history_cert_action ON certificate_history(certificate_id, action);
CREATE INDEX IF NOT EXISTS idx_history_cert_date ON certificate_history(certificate_id, performed_at);

-- Триггер для автоматического обновления updated_at
CREATE TRIGGER update_certificates_updated_at
    BEFORE UPDATE ON certificates
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Создание представлений для удобства работы

-- Представление активных сертификатов
CREATE OR REPLACE VIEW active_certificates AS
SELECT
    c.*,
    CASE
        WHEN c.valid_to < CURRENT_DATE THEN 'expired'
        WHEN c.valid_to - CURRENT_DATE <= 30 THEN 'expiring_soon'
        ELSE 'active'
        END AS status,
    (c.valid_to - CURRENT_DATE) AS days_left
FROM certificates c
WHERE c.is_active = TRUE;

COMMENT ON VIEW active_certificates IS 'Представление активных сертификатов с вычисляемым статусом';

-- Представление статистики сертификатов
CREATE OR REPLACE VIEW certificate_stats AS
SELECT
    COUNT(*) AS total_certificates,
    COUNT(*) FILTER (WHERE is_active = TRUE) AS active_certificates,
        COUNT(*) FILTER (WHERE is_active = TRUE AND valid_to < CURRENT_DATE) AS expired_certificates,
        COUNT(*) FILTER (WHERE is_active = FALSE) AS inactive_certificates,
        COUNT(*) FILTER (WHERE is_active = TRUE AND valid_to - CURRENT_DATE <= 30) AS expiring_soon,
        AVG(users_count) AS avg_users_count,
    MIN(valid_from) AS earliest_cert_date,
    MAX(valid_to) AS latest_expiry_date
FROM certificates;

COMMENT ON VIEW certificate_stats IS 'Представление общей статистики по сертификатам';

-- Информация о завершении инициализации
DO $$
BEGIN
    RAISE NOTICE 'База данных сертификатов успешно инициализирована!';
    RAISE NOTICE 'Создано таблиц: %', (SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_name IN ('certificates', 'certificate_history'));
    RAISE NOTICE 'Создано индексов: %', (SELECT COUNT(*) FROM pg_indexes WHERE schemaname = 'public' AND tablename IN ('certificates', 'certificate_history'));
    RAISE NOTICE 'Создано представлений: %', (SELECT COUNT(*) FROM information_schema.views WHERE table_schema = 'public');
END $$;
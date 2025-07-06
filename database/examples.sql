-- database/examples.sql
-- Примеры SQL запросов для работы с системой сертификатов

-- Получение активных сертификатов для домена
SELECT * FROM active_certificates WHERE domain = 'example.com';

-- Получение истории действий с сертификатом
SELECT * FROM certificate_history
WHERE certificate_id = 'ABCD1-XYZ12-QWRT5-WX0124'
ORDER BY performed_at DESC;

-- Поиск сертификатов по части домена
SELECT * FROM certificates
WHERE domain LIKE '%example%'
ORDER BY created_at DESC;

-- Получение всех сертификатов с историей
SELECT * FROM certificates_with_history
WHERE domain = 'example.com';

-- Сертификаты, истекающие в ближайшие 30 дней
SELECT certificate_id, domain, valid_to, days_until_expiry
FROM active_certificates
WHERE days_until_expiry <= 30 AND days_until_expiry > 0
ORDER BY days_until_expiry;

-- Статистика по сертификатам
SELECT
    COUNT(*) as total_certificates,
    COUNT(*) FILTER (WHERE is_active = TRUE) as active_certificates,
        COUNT(*) FILTER (WHERE valid_to < CURRENT_DATE) as expired_certificates,
        COUNT(DISTINCT domain) as unique_domains,
    AVG(users_count) as avg_users_per_cert
FROM certificates;

-- Топ доменов по количеству сертификатов
SELECT domain, COUNT(*) as cert_count
FROM certificates
GROUP BY domain
ORDER BY cert_count DESC
    LIMIT 10;

-- Сертификаты созданные за последний месяц
SELECT certificate_id, domain, created_at
FROM certificates
WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY created_at DESC;

-- Очистка старой истории (старше года)
SELECT cleanup_old_history(365);

-- Поиск сертификатов по создателю
SELECT certificate_id, domain, created_at
FROM certificates
WHERE created_by = 123456789
ORDER BY created_at DESC;

-- Проверка дубликатов по домену
SELECT domain, COUNT(*) as count
FROM certificates
WHERE is_active = TRUE
GROUP BY domain
HAVING COUNT(*) > 1;
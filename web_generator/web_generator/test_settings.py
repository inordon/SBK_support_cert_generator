"""
Настройки для тестов. Используют SQLite вместо PostgreSQL.
"""

from .settings import *  # noqa: F401,F403

# SQLite для тестов — не требует PostgreSQL
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Ускоряем хеширование паролей в тестах
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Отключаем Celery — задачи выполняются синхронно
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Email — сохраняем в памяти
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# Тестовые получатели уведомлений
CERT_NOTIFICATION_RECIPIENTS = ['test@example.com']

# Статика — без сжатия для тестов
STORAGES = {
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}

"""
Django settings for web_generator project.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ['DJANGO_SECRET_KEY']  # обязательная переменная, без fallback

DEBUG = os.getenv('DJANGO_DEBUG', 'True').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',')
    if origin.strip()
]

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third party
    'crispy_forms',
    'crispy_bootstrap5',
    'django_filters',
    'django_celery_beat',
    'axes',
    # Local
    'cert_manager',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'axes.middleware.AxesMiddleware',
]

ROOT_URLCONF = 'web_generator.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'web_generator.wsgi.application'

# Database — external PostgreSQL server

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'cert_generator'),
        'USER': os.getenv('DB_USER', 'cert_user'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', '192.168.1.100'),
        'PORT': os.getenv('DB_PORT', '5432'),
        'OPTIONS': {
            'connect_timeout': 5,
        },
    }
}

# Password validation

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# LDAP Authentication

AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# django-axes: защита от brute-force
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # часы
AXES_LOCKOUT_PARAMETERS = ['username']

LDAP_ENABLED = os.getenv('LDAP_ENABLED', 'False').lower() in ('true', '1', 'yes')

if LDAP_ENABLED:
    import ldap
    from django_auth_ldap.config import LDAPSearch, GroupOfNamesType

    AUTHENTICATION_BACKENDS.insert(0, 'django_auth_ldap.backend.LDAPBackend')

    AUTH_LDAP_SERVER_URI = os.getenv('LDAP_SERVER_URI', 'ldap://ldap.example.com')
    AUTH_LDAP_BIND_DN = os.getenv('LDAP_BIND_DN', '')
    AUTH_LDAP_BIND_PASSWORD = os.getenv('LDAP_BIND_PASSWORD', '')

    AUTH_LDAP_USER_SEARCH = LDAPSearch(
        os.getenv('LDAP_USER_SEARCH_BASE', 'ou=users,dc=example,dc=com'),
        ldap.SCOPE_SUBTREE,
        os.getenv('LDAP_USER_SEARCH_FILTER', '(sAMAccountName=%(user)s)'),
    )

    AUTH_LDAP_USER_ATTR_MAP = {
        'first_name': os.getenv('LDAP_ATTR_FIRST_NAME', 'givenName'),
        'last_name': os.getenv('LDAP_ATTR_LAST_NAME', 'sn'),
        'email': os.getenv('LDAP_ATTR_EMAIL', 'mail'),
    }

    # LDAP Group settings
    LDAP_GROUP_SEARCH_BASE = os.getenv('LDAP_GROUP_SEARCH_BASE', '')
    if LDAP_GROUP_SEARCH_BASE:
        AUTH_LDAP_GROUP_SEARCH = LDAPSearch(
            LDAP_GROUP_SEARCH_BASE,
            ldap.SCOPE_SUBTREE,
            '(objectClass=groupOfNames)',
        )
        AUTH_LDAP_GROUP_TYPE = GroupOfNamesType()

    # Map LDAP groups to Django flags
    LDAP_STAFF_GROUP = os.getenv('LDAP_STAFF_GROUP', '')
    LDAP_SUPERUSER_GROUP = os.getenv('LDAP_SUPERUSER_GROUP', '')
    if LDAP_STAFF_GROUP or LDAP_SUPERUSER_GROUP:
        AUTH_LDAP_USER_FLAGS_BY_GROUP = {}
        if LDAP_STAFF_GROUP:
            AUTH_LDAP_USER_FLAGS_BY_GROUP['is_staff'] = LDAP_STAFF_GROUP
        if LDAP_SUPERUSER_GROUP:
            AUTH_LDAP_USER_FLAGS_BY_GROUP['is_superuser'] = LDAP_SUPERUSER_GROUP

    AUTH_LDAP_ALWAYS_UPDATE_USER = True

    # TLS settings
    if os.getenv('LDAP_START_TLS', 'False').lower() in ('true', '1', 'yes'):
        AUTH_LDAP_START_TLS = True

# Internationalization

LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = os.getenv('TZ', 'Europe/Moscow')
USE_I18N = True
USE_TZ = True

# Static files

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

# Default primary key field type

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Crispy Forms

CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'

# Login/Logout redirects

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

# Email settings

EMAIL_BACKEND = os.getenv(
    'EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend'
)
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.example.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() in ('true', '1', 'yes')
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'certs@example.com')

# Certificate notification recipients (comma-separated)
CERT_NOTIFICATION_RECIPIENTS = os.getenv('CERT_NOTIFICATION_RECIPIENTS', '').split(',')

# Celery settings

CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# Logging

LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FORMAT = os.getenv('LOG_FORMAT', 'text')  # 'text' или 'json'

_formatter = 'json' if LOG_FORMAT == 'json' else 'verbose'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{asctime} [{levelname}] {name}: {message}',
            'style': '{',
        },
        'json': {
            '()': 'web_generator.logging_json.JsonFormatter',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': _formatter,
        },
    },
    'root': {
        'handlers': ['console'],
        'level': LOG_LEVEL,
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
        'cert_manager': {
            'handlers': ['console'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
        'celery': {
            'handlers': ['console'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
    },
}

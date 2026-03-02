#!/usr/bin/env python3
"""
Точка входа для запуска веб-сервиса управления сертификатами.

Использование:
    python run_web.py

Или через uvicorn:
    uvicorn web.app:app --host 0.0.0.0 --port 8443
"""

import sys
import uvicorn
from config.settings import get_settings


def main():
    settings = get_settings()

    if not settings.web_enabled:
        print("Веб-сервис отключен. Установите WEB_ENABLED=true в .env")
        print("Также настройте WEB_SECRET_KEY и WEB_USERS")
        sys.exit(1)

    if not settings.web_users_list:
        print("Не настроены веб-пользователи. Установите WEB_USERS в .env")
        print('Пример: WEB_USERS=[{"username":"admin","password":"secret","role":"admin","name":"Администратор"}]')
        sys.exit(1)

    print(f"Запуск веб-сервиса на {settings.web_host}:{settings.web_port}")
    print(f"Настроено пользователей: {len(settings.web_users_list)}")

    uvicorn.run(
        "web.app:app",
        host=settings.web_host,
        port=settings.web_port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    main()

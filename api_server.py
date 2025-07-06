"""
FastAPI сервер для API сертификатов
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.api import CertificateAPI
from core.storage import DatabaseStorage, FileStorage


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    # Запуск
    logging.info("Запуск API сервера...")

    # Подключение к БД
    await app.state.certificate_api.db_storage.connect()
    logging.info("Подключение к БД установлено")

    yield

    # Завершение
    logging.info("Остановка API сервера...")
    await app.state.certificate_api.db_storage.disconnect()


def create_app() -> FastAPI:
    """Создание FastAPI приложения"""
    # Настройка логирования
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/api.log'),
            logging.StreamHandler()
        ]
    )

    # Создание приложения
    app = FastAPI(
        title="Certificate Management API",
        description="API для управления сертификатами",
        version="1.0.0",
        lifespan=lifespan
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # В продакшене указать конкретные домены
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Настройка хранилищ
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL не найден в переменных окружения")

    certificates_dir = os.getenv('CERTIFICATES_DIR', 'certificates')
    api_key = os.getenv('API_KEY')

    db_storage = DatabaseStorage(database_url)
    file_storage = FileStorage(certificates_dir)

    # Создание API
    certificate_api = CertificateAPI(db_storage, file_storage, api_key)
    app.state.certificate_api = certificate_api

    # Подключение роутов
    app.mount("/", certificate_api.app)

    return app


# Создание приложения
app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True if os.getenv('ENVIRONMENT') == 'development' else False,
        workers=1 if os.getenv('ENVIRONMENT') == 'development' else 4
    )
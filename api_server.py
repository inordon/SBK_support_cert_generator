"""
FastAPI сервер для API сертификатов
"""
import logging
import os
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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
    # Создаем директорию для логов если её нет
    os.makedirs('logs', exist_ok=True)

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

    # Подключение роутов от CertificateAPI
    app.mount("/", certificate_api.app)

    # Добавляем собственный health check с проверкой БД
    @app.get("/health", tags=["monitoring"])
    async def health_check():
        """Проверка здоровья API и БД"""
        health_status = {
            "status": "checking",
            "timestamp": datetime.now().isoformat(),
            "components": {}
        }

        # Проверка API
        health_status["components"]["api"] = {
            "status": "healthy",
            "message": "API is running"
        }

        # Проверка БД
        try:
            if app.state.certificate_api.db_storage.pool:
                async with app.state.certificate_api.db_storage.pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
                health_status["components"]["database"] = {
                    "status": "healthy",
                    "message": "Database connection is active"
                }
            else:
                health_status["components"]["database"] = {
                    "status": "unhealthy",
                    "message": "Database pool not initialized"
                }
        except Exception as e:
            health_status["components"]["database"] = {
                "status": "unhealthy",
                "message": f"Database error: {str(e)}"
            }

        # Проверка файлового хранилища
        try:
            certificates_path = app.state.certificate_api.file_storage.base_path
            if certificates_path.exists() and certificates_path.is_dir():
                health_status["components"]["file_storage"] = {
                    "status": "healthy",
                    "message": f"Certificates directory exists: {certificates_path}"
                }
            else:
                health_status["components"]["file_storage"] = {
                    "status": "unhealthy",
                    "message": "Certificates directory not found"
                }
        except Exception as e:
            health_status["components"]["file_storage"] = {
                "status": "unhealthy",
                "message": f"File storage error: {str(e)}"
            }

        # Общий статус
        all_healthy = all(
            comp.get("status") == "healthy"
            for comp in health_status["components"].values()
        )

        health_status["status"] = "healthy" if all_healthy else "unhealthy"

        # Возвращаем с соответствующим HTTP кодом
        if all_healthy:
            return JSONResponse(content=health_status, status_code=200)
        else:
            return JSONResponse(content=health_status, status_code=503)

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
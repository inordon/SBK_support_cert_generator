"""
FastAPI веб-приложение для управления сертификатами технической поддержки.

Предоставляет веб-интерфейс с ролевой моделью (admin/verify),
аналогичный Telegram-боту.
"""

import logging
import sys
from pathlib import Path
from datetime import date, datetime
from typing import Optional

from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import get_settings
from core.service import get_certificate_service
from core.models import CertificateRequest, SearchRequest, EditCertificateDatesRequest
from core.email_service import get_email_service

logger = logging.getLogger(__name__)

settings = get_settings()
certificate_service = get_certificate_service()
email_service = get_email_service()

app = FastAPI(title="SBK Certificate Manager", docs_url=None, redoc_url=None)

# Настройка сессий
app.add_middleware(SessionMiddleware, secret_key=settings.web_secret_key)

# Статические файлы и шаблоны
web_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=str(web_dir / "static")), name="static")
templates = Jinja2Templates(directory=str(web_dir / "templates"))


# --- Зависимости ---

def get_current_user(request: Request) -> Optional[dict]:
    """Получает текущего пользователя из сессии."""
    return request.session.get("user")


def require_auth(request: Request) -> dict:
    """Требует аутентификацию."""
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return user


def require_admin(request: Request) -> dict:
    """Требует права администратора."""
    user = require_auth(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Доступ запрещен")
    return user


# --- Маршруты ---

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Главная страница."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    return RedirectResponse(url="/dashboard", status_code=303)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Страница входа."""
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": None
    })


@app.post("/login")
async def login_action(request: Request, username: str = Form(...), password: str = Form(...)):
    """Обработка входа."""
    user = settings.get_web_user(username, password)
    if not user:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Неверное имя пользователя или пароль"
        })

    request.session["user"] = {
        "username": user["username"],
        "role": user.get("role", "verify"),
        "name": user.get("name", user["username"])
    }
    return RedirectResponse(url="/dashboard", status_code=303)


@app.get("/logout")
async def logout(request: Request):
    """Выход из системы."""
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Панель управления."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    try:
        stats = certificate_service.get_statistics()
    except Exception:
        stats = {"database": {}, "file_storage": {}}

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "stats": stats,
    })


@app.get("/certificates", response_class=HTMLResponse)
async def certificates_list(request: Request):
    """Список сертификатов."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    search_domain = request.query_params.get("domain", "")
    search_inn = request.query_params.get("inn", "")

    try:
        if search_domain or search_inn:
            sr = SearchRequest(
                domain=search_domain or None,
                inn=search_inn or None,
                active_only=False
            )
            certificates = certificate_service.search_certificates(sr)
        else:
            sr = SearchRequest(active_only=False)
            certificates = certificate_service.search_certificates(sr)
    except Exception as e:
        logger.error(f"Ошибка получения сертификатов: {e}")
        certificates = []

    return templates.TemplateResponse("certificates.html", {
        "request": request,
        "user": user,
        "certificates": certificates,
        "search_domain": search_domain,
        "search_inn": search_inn,
    })


@app.get("/certificates/create", response_class=HTMLResponse)
async def create_certificate_page(request: Request):
    """Страница создания сертификата."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if user.get("role") != "admin":
        return RedirectResponse(url="/dashboard", status_code=303)

    return templates.TemplateResponse("create_certificate.html", {
        "request": request,
        "user": user,
        "error": None,
        "success": None,
    })


@app.post("/certificates/create")
async def create_certificate_action(request: Request):
    """Обработка создания сертификата."""
    user = get_current_user(request)
    if not user or user.get("role") != "admin":
        return RedirectResponse(url="/login", status_code=303)

    try:
        form_data = await request.form()
        domain = form_data.get("domain", "")
        inn = form_data.get("inn", "")
        valid_from = form_data.get("valid_from", "")
        valid_to = form_data.get("valid_to", "")
        users_count = int(form_data.get("users_count", 1))
        request_email = form_data.get("request_email", "").strip() or None

        # Собираем контактные лица из множественных полей
        contact_names = form_data.getlist("contact_name")
        contact_emails = form_data.getlist("contact_email")
        contacts = []
        for name, email in zip(contact_names, contact_emails):
            name = name.strip()
            email = email.strip()
            if name and email:
                contacts.append({"name": name, "email": email})

        vf = datetime.strptime(valid_from, "%Y-%m-%d").date()
        vt = datetime.strptime(valid_to, "%Y-%m-%d").date()

        # Валидация
        errors = certificate_service.validate_certificate_data(domain, inn, vf, vt, users_count)
        if errors:
            return templates.TemplateResponse("create_certificate.html", {
                "request": request,
                "user": user,
                "error": "\n".join(errors),
                "success": None,
            })

        cert_request = CertificateRequest(
            domain=domain.strip().lower(),
            inn=inn.strip(),
            valid_from=vf,
            valid_to=vt,
            users_count=users_count,
            created_by=0,  # Веб-пользователь (не Telegram)
            created_by_username=None,
            created_by_full_name=f"web:{user['username']}",
            request_email=request_email,
            contacts=contacts or None
        )

        certificate, has_existing = certificate_service.create_certificate(cert_request)

        # Email-уведомление
        if email_service.is_configured:
            try:
                email_service.send_certificate_notification(certificate.to_dict())
            except Exception as e:
                logger.warning(f"Не удалось отправить email: {e}")

        return templates.TemplateResponse("create_certificate.html", {
            "request": request,
            "user": user,
            "error": None,
            "success": f"Сертификат создан: {certificate.certificate_id}",
            "certificate": certificate,
        })

    except Exception as e:
        logger.error(f"Ошибка создания сертификата через веб: {e}")
        return templates.TemplateResponse("create_certificate.html", {
            "request": request,
            "user": user,
            "error": f"Ошибка: {e}",
            "success": None,
        })


@app.get("/certificates/verify", response_class=HTMLResponse)
async def verify_certificate_page(request: Request):
    """Страница проверки сертификата."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    cert_id = request.query_params.get("id", "")
    certificate = None
    error = None

    if cert_id:
        try:
            certificate = certificate_service.verify_certificate(cert_id.strip().upper(), 0)
            if certificate is None:
                error = f"Сертификат с ID {cert_id} не найден"
        except Exception as e:
            error = str(e)

    return templates.TemplateResponse("verify_certificate.html", {
        "request": request,
        "user": user,
        "certificate": certificate,
        "cert_id": cert_id,
        "error": error,
    })


@app.get("/request", response_class=HTMLResponse)
async def request_certificate_page(request: Request):
    """Страница запроса сертификата (для внешних пользователей по email)."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    allowed_senders = email_service.get_allowed_senders()

    return templates.TemplateResponse("request_certificate.html", {
        "request": request,
        "user": user,
        "allowed_senders": allowed_senders,
        "email_configured": email_service.is_configured,
        "error": None,
        "success": None,
    })


@app.post("/request")
async def request_certificate_action(
    request: Request,
    domain: str = Form(...),
    inn: str = Form(...),
    valid_from: str = Form(...),
    valid_to: str = Form(...),
    users_count: int = Form(...),
    sender_name: str = Form(...),
    sender_email: str = Form(...)
):
    """Обработка запроса на сертификат через email."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    allowed_senders = email_service.get_allowed_senders()

    if not email_service.is_configured:
        return templates.TemplateResponse("request_certificate.html", {
            "request": request,
            "user": user,
            "allowed_senders": allowed_senders,
            "email_configured": False,
            "error": "Email не настроен",
            "success": None,
        })

    request_data = {
        "domain": domain,
        "inn": inn,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "users_count": users_count,
    }

    success = email_service.send_certificate_request(request_data, sender_name, sender_email)

    return templates.TemplateResponse("request_certificate.html", {
        "request": request,
        "user": user,
        "allowed_senders": allowed_senders,
        "email_configured": True,
        "error": None if success else "Не удалось отправить запрос. Проверьте email отправителя.",
        "success": "Запрос отправлен на рассмотрение" if success else None,
    })

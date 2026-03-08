import logging

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Q, Count, Case, When, Value, BooleanField
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .decorators import admin_required
from .forms import CertificateCreateForm, CertificateEditDatesForm, CertificateSearchForm
from .generator import CertificateIDGenerator
from .models import Certificate, CertificateHistory, NotificationLog
from .tasks import send_certificate_notification_task

logger = logging.getLogger(__name__)

CERTS_PER_PAGE = 25
LOGS_PER_PAGE = 50


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            logger.info('Пользователь %s вошёл в систему', user.username)
            next_url = request.GET.get('next', 'dashboard')
            return redirect(next_url)
        else:
            logger.warning('Неудачная попытка входа: %s', request.POST.get('username', ''))
    else:
        form = AuthenticationForm()

    return render(request, 'registration/login.html', {'form': form})


def logout_view(request):
    logger.info('Пользователь %s вышел из системы', request.user.username)
    logout(request)
    return redirect('login')


@login_required
def dashboard(request):
    """Главная страница — дашборд со статистикой (один агрегирующий запрос)."""
    today = timezone.now().date()
    expiry_threshold = today + timezone.timedelta(days=60)

    stats = Certificate.objects.aggregate(
        total=Count('id'),
        active=Count('id', filter=Q(
            is_active=True, valid_from__lte=today, valid_to__gte=today
        )),
        expiring=Count('id', filter=Q(
            is_active=True, valid_to__gte=today, valid_to__lte=expiry_threshold
        )),
        expired=Count('id', filter=Q(is_active=True, valid_to__lt=today)),
        inactive=Count('id', filter=Q(is_active=False)),
    )

    recent_certs = Certificate.objects.order_by('-created_at')[:5]
    recent_history = CertificateHistory.objects.select_related('performed_by')[:10]

    logger.debug('Dashboard загружен пользователем %s', request.user.username)

    context = {
        **stats,
        'recent_certs': recent_certs,
        'recent_history': recent_history,
    }
    return render(request, 'certificates/dashboard.html', context)


@login_required
def certificate_list(request):
    """Список сертификатов с поиском, фильтрацией и пагинацией."""
    form = CertificateSearchForm(request.GET)
    certs = Certificate.objects.select_related('created_by').all()

    today = timezone.now().date()

    if form.is_valid():
        q = form.cleaned_data.get('q', '').strip()
        status = form.cleaned_data.get('status', '')

        if q:
            certs = certs.filter(
                Q(domain__icontains=q) |
                Q(inn__icontains=q) |
                Q(certificate_id__icontains=q)
            )

        if status == 'active':
            certs = certs.filter(is_active=True, valid_from__lte=today, valid_to__gte=today)
        elif status == 'expiring':
            certs = certs.filter(
                is_active=True,
                valid_to__gte=today,
                valid_to__lte=today + timezone.timedelta(days=60)
            )
        elif status == 'expired':
            certs = certs.filter(is_active=True, valid_to__lt=today)
        elif status == 'inactive':
            certs = certs.filter(is_active=False)

    paginator = Paginator(certs, CERTS_PER_PAGE)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'certificates/list.html', {
        'page_obj': page,
        'form': form,
    })


@admin_required
def certificate_create(request):
    """Создание нового сертификата."""
    if request.method == 'POST':
        form = CertificateCreateForm(request.POST)
        if form.is_valid():
            cert = form.save(commit=False)
            cert.created_by = request.user

            # Генерируем уникальный ID с retry через DB unique constraint
            generator = CertificateIDGenerator()
            for attempt in range(10):
                cert.certificate_id = generator.generate(cert.valid_to)
                try:
                    cert.save()
                    break
                except IntegrityError:
                    if attempt == 9:
                        logger.error('Не удалось сохранить сертификат: исчерпаны попытки генерации ID')
                        messages.error(request, 'Ошибка генерации уникального ID. Попробуйте ещё раз.')
                        return render(request, 'certificates/create.html', {'form': form})
                    continue

            CertificateHistory.objects.create(
                certificate=cert,
                action='created',
                performed_by=request.user,
                details={
                    'domain': cert.domain,
                    'inn': cert.inn,
                    'valid_from': str(cert.valid_from),
                    'valid_to': str(cert.valid_to),
                    'users_count': cert.users_count,
                }
            )

            # Email-уведомление через Celery
            send_certificate_notification_task.delay(
                str(cert.pk), 'created', request.user.pk
            )

            logger.info(
                'Сертификат %s создан пользователем %s',
                cert.certificate_id, request.user.username
            )
            messages.success(
                request,
                f'Сертификат {cert.certificate_id} успешно создан.'
            )
            return redirect('certificate_detail', cert_id=cert.certificate_id)
    else:
        form = CertificateCreateForm()

    return render(request, 'certificates/create.html', {'form': form})


@login_required
def certificate_detail(request, cert_id):
    """Детальная информация о сертификате."""
    cert = get_object_or_404(Certificate, certificate_id=cert_id)
    history = cert.history.select_related('performed_by').all()

    return render(request, 'certificates/detail.html', {
        'certificate': cert,
        'history': history,
    })


@admin_required
def certificate_edit_dates(request, cert_id):
    """Редактирование дат сертификата."""
    cert = get_object_or_404(Certificate, certificate_id=cert_id)

    if request.method == 'POST':
        form = CertificateEditDatesForm(request.POST)
        if form.is_valid():
            old_from = cert.valid_from
            old_to = cert.valid_to

            cert.valid_from = form.cleaned_data['new_valid_from']
            cert.valid_to = form.cleaned_data['new_valid_to']
            cert.save(update_fields=['valid_from', 'valid_to', 'updated_at'])

            CertificateHistory.objects.create(
                certificate=cert,
                action='dates_updated',
                performed_by=request.user,
                details={
                    'old_valid_from': str(old_from),
                    'old_valid_to': str(old_to),
                    'new_valid_from': str(cert.valid_from),
                    'new_valid_to': str(cert.valid_to),
                    'reason': form.cleaned_data.get('edit_reason', ''),
                }
            )

            # Email-уведомление через Celery
            send_certificate_notification_task.delay(
                str(cert.pk), 'updated', request.user.pk
            )

            logger.info(
                'Даты сертификата %s изменены пользователем %s',
                cert.certificate_id, request.user.username
            )
            messages.success(request, 'Даты сертификата обновлены.')
            return redirect('certificate_detail', cert_id=cert.certificate_id)
    else:
        form = CertificateEditDatesForm(initial={
            'new_valid_from': cert.valid_from,
            'new_valid_to': cert.valid_to,
        })

    return render(request, 'certificates/edit_dates.html', {
        'certificate': cert,
        'form': form,
    })


@admin_required
def certificate_deactivate(request, cert_id):
    """Деактивация сертификата."""
    cert = get_object_or_404(Certificate, certificate_id=cert_id)

    if request.method == 'POST':
        cert.is_active = False
        cert.save(update_fields=['is_active', 'updated_at'])

        CertificateHistory.objects.create(
            certificate=cert,
            action='deactivated',
            performed_by=request.user,
        )

        logger.info(
            'Сертификат %s деактивирован пользователем %s',
            cert.certificate_id, request.user.username
        )
        messages.success(request, f'Сертификат {cert.certificate_id} деактивирован.')
        return redirect('certificate_detail', cert_id=cert.certificate_id)

    return render(request, 'certificates/deactivate_confirm.html', {
        'certificate': cert,
    })


@admin_required
def certificate_activate(request, cert_id):
    """Активация сертификата (с подтверждающей страницей)."""
    cert = get_object_or_404(Certificate, certificate_id=cert_id)

    if request.method == 'POST':
        cert.is_active = True
        cert.save(update_fields=['is_active', 'updated_at'])

        CertificateHistory.objects.create(
            certificate=cert,
            action='activated',
            performed_by=request.user,
        )

        logger.info(
            'Сертификат %s активирован пользователем %s',
            cert.certificate_id, request.user.username
        )
        messages.success(request, f'Сертификат {cert.certificate_id} активирован.')
        return redirect('certificate_detail', cert_id=cert.certificate_id)

    return render(request, 'certificates/activate_confirm.html', {
        'certificate': cert,
    })


@login_required
def notification_log(request):
    """Журнал отправленных уведомлений с пагинацией."""
    logs = NotificationLog.objects.select_related('certificate').all()
    paginator = Paginator(logs, LOGS_PER_PAGE)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'certificates/notifications.html', {'page_obj': page})

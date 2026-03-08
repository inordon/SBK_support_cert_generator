import json
import logging
from collections import defaultdict
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.core.paginator import Paginator
from django.db import IntegrityError, connection
from django.db.models import Q, Count, Sum, DecimalField
from django.db.models.functions import TruncMonth
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from .decorators import admin_required
from .forms import (
    CertificateCreateForm, CertificateEditDatesForm,
    CertificatePaymentForm, CertificateSearchForm,
)
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


@require_POST
def logout_view(request):
    logger.info('Пользователь %s вышел из системы', request.user.username)
    logout(request)
    return redirect('login')


def healthz(request):
    """Health-check endpoint для Docker и внешних мониторингов."""
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'detail': str(e)}, status=503)


@login_required
def dashboard(request):
    """Главная страница — дашборд со статистикой и аналитикой."""
    today = timezone.now().date()
    expiry_threshold = today + timedelta(days=60)

    # Основная статистика (один агрегирующий запрос)
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
        total_revenue=Sum('price', filter=Q(payment_status='paid')),
        pending_revenue=Sum('price', filter=Q(payment_status='pending')),
    )

    # Создание сертификатов по месяцам (последние 12 мес)
    twelve_months_ago = today - timedelta(days=365)
    created_by_month = list(
        Certificate.objects
        .filter(created_at__date__gte=twelve_months_ago)
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(count=Count('id'), revenue=Sum('price'))
        .order_by('month')
    )

    # Истечения на ближайшие 6 месяцев
    six_months_ahead = today + timedelta(days=180)
    expiry_by_month = list(
        Certificate.objects
        .filter(is_active=True, valid_to__gte=today, valid_to__lte=six_months_ahead)
        .annotate(month=TruncMonth('valid_to'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )

    # Топ-5 доменов по кол-ву сертификатов
    top_domains = list(
        Certificate.objects.values('domain')
        .annotate(count=Count('id'))
        .order_by('-count')[:5]
    )

    # Топ-5 ИНН по кол-ву сертификатов
    top_inns = list(
        Certificate.objects.values('inn')
        .annotate(count=Count('id'))
        .order_by('-count')[:5]
    )

    # Статистика уведомлений
    notify_stats = NotificationLog.objects.aggregate(
        total_sent=Count('id'),
        success=Count('id', filter=Q(success=True)),
        failed=Count('id', filter=Q(success=False)),
    )

    # Распределение по статусам оплаты
    payment_stats = list(
        Certificate.objects.values('payment_status')
        .annotate(count=Count('id'))
        .order_by('payment_status')
    )

    recent_certs = Certificate.objects.order_by('-created_at')[:5]
    recent_history = CertificateHistory.objects.select_related('performed_by')[:10]

    # Подготовка данных для Chart.js
    chart_created_labels = [
        entry['month'].strftime('%m.%Y') for entry in created_by_month
    ]
    chart_created_data = [entry['count'] for entry in created_by_month]
    chart_created_revenue = [
        float(entry['revenue'] or 0) for entry in created_by_month
    ]

    chart_expiry_labels = [
        entry['month'].strftime('%m.%Y') for entry in expiry_by_month
    ]
    chart_expiry_data = [entry['count'] for entry in expiry_by_month]

    # Donut: статусы сертификатов
    chart_status_data = [
        stats['active'] or 0,
        stats['expiring'] or 0,
        stats['expired'] or 0,
        stats['inactive'] or 0,
    ]

    # Donut: оплата
    payment_map = {ps['payment_status']: ps['count'] for ps in payment_stats}
    chart_payment_data = [
        payment_map.get('paid', 0),
        payment_map.get('pending', 0),
        payment_map.get('free', 0),
    ]

    context = {
        **stats,
        'recent_certs': recent_certs,
        'recent_history': recent_history,
        'notify_stats': notify_stats,
        'top_domains': top_domains,
        'top_inns': top_inns,
        # JSON for Chart.js
        'chart_created_labels': json.dumps(chart_created_labels),
        'chart_created_data': json.dumps(chart_created_data),
        'chart_created_revenue': json.dumps(chart_created_revenue),
        'chart_expiry_labels': json.dumps(chart_expiry_labels),
        'chart_expiry_data': json.dumps(chart_expiry_data),
        'chart_status_data': json.dumps(chart_status_data),
        'chart_payment_data': json.dumps(chart_payment_data),
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
                valid_to__lte=today + timedelta(days=60)
            )
        elif status == 'expired':
            certs = certs.filter(is_active=True, valid_to__lt=today)
        elif status == 'inactive':
            certs = certs.filter(is_active=False)

        payment = form.cleaned_data.get('payment', '')
        if payment:
            certs = certs.filter(payment_status=payment)

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
                    'price': str(cert.price) if cert.price else None,
                    'payment_status': cert.payment_status,
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


@admin_required
def certificate_update_payment(request, cert_id):
    """Изменение стоимости и статуса оплаты."""
    cert = get_object_or_404(Certificate, certificate_id=cert_id)

    if request.method == 'POST':
        form = CertificatePaymentForm(request.POST)
        if form.is_valid():
            old_price = cert.price
            old_status = cert.payment_status

            cert.price = form.cleaned_data['price']
            cert.payment_status = form.cleaned_data['payment_status']
            cert.save(update_fields=['price', 'payment_status', 'updated_at'])

            CertificateHistory.objects.create(
                certificate=cert,
                action='payment_updated',
                performed_by=request.user,
                details={
                    'old_price': str(old_price) if old_price else None,
                    'new_price': str(cert.price) if cert.price else None,
                    'old_payment_status': old_status,
                    'new_payment_status': cert.payment_status,
                }
            )

            logger.info(
                'Оплата сертификата %s изменена пользователем %s',
                cert.certificate_id, request.user.username
            )
            messages.success(request, 'Данные оплаты обновлены.')
            return redirect('certificate_detail', cert_id=cert.certificate_id)
    else:
        form = CertificatePaymentForm(initial={
            'price': cert.price,
            'payment_status': cert.payment_status,
        })

    return render(request, 'certificates/update_payment.html', {
        'certificate': cert,
        'form': form,
    })


@login_required
def notification_log(request):
    """Журнал отправленных уведомлений с пагинацией."""
    logs = NotificationLog.objects.select_related('certificate').all()
    paginator = Paginator(logs, LOGS_PER_PAGE)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'certificates/notifications.html', {'page_obj': page})

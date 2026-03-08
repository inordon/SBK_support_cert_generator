from django.contrib import messages
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.db.models import Q, Count
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .forms import CertificateCreateForm, CertificateEditDatesForm, CertificateSearchForm
from .generator import CertificateIDGenerator
from .models import Certificate, CertificateHistory, NotificationLog
from .services import send_certificate_notification


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            next_url = request.GET.get('next', 'dashboard')
            return redirect(next_url)
    else:
        form = AuthenticationForm()

    return render(request, 'registration/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def dashboard(request):
    """Главная страница — дашборд со статистикой."""
    today = timezone.now().date()
    certs = Certificate.objects.all()

    total = certs.count()
    active = certs.filter(is_active=True, valid_from__lte=today, valid_to__gte=today).count()
    expiring = certs.filter(
        is_active=True,
        valid_to__gte=today,
        valid_to__lte=today + timezone.timedelta(days=60)
    ).count()
    expired = certs.filter(is_active=True, valid_to__lt=today).count()
    inactive = certs.filter(is_active=False).count()

    recent_certs = certs[:5]
    recent_history = CertificateHistory.objects.select_related('performed_by')[:10]

    context = {
        'total': total,
        'active': active,
        'expiring': expiring,
        'expired': expired,
        'inactive': inactive,
        'recent_certs': recent_certs,
        'recent_history': recent_history,
    }
    return render(request, 'certificates/dashboard.html', context)


@login_required
def certificate_list(request):
    """Список сертификатов с поиском и фильтрацией."""
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

    return render(request, 'certificates/list.html', {
        'certificates': certs,
        'form': form,
    })


@login_required
def certificate_create(request):
    """Создание нового сертификата."""
    if request.method == 'POST':
        form = CertificateCreateForm(request.POST)
        if form.is_valid():
            cert = form.save(commit=False)

            # Генерируем уникальный ID
            generator = CertificateIDGenerator()
            existing_ids = set(
                Certificate.objects.values_list('certificate_id', flat=True)
            )
            cert.certificate_id = generator.generate(cert.valid_to, existing_ids)
            cert.created_by = request.user
            cert.save()

            # История
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

            # Email-уведомление
            send_certificate_notification(cert, action='created', user=request.user)

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


@login_required
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

            send_certificate_notification(cert, action='updated', user=request.user)

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


@login_required
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

        messages.success(request, f'Сертификат {cert.certificate_id} деактивирован.')
        return redirect('certificate_detail', cert_id=cert.certificate_id)

    return render(request, 'certificates/deactivate_confirm.html', {
        'certificate': cert,
    })


@login_required
def certificate_activate(request, cert_id):
    """Активация сертификата."""
    cert = get_object_or_404(Certificate, certificate_id=cert_id)

    if request.method == 'POST':
        cert.is_active = True
        cert.save(update_fields=['is_active', 'updated_at'])

        CertificateHistory.objects.create(
            certificate=cert,
            action='activated',
            performed_by=request.user,
        )

        messages.success(request, f'Сертификат {cert.certificate_id} активирован.')
        return redirect('certificate_detail', cert_id=cert.certificate_id)

    return redirect('certificate_detail', cert_id=cert.certificate_id)


@login_required
def notification_log(request):
    """Журнал отправленных уведомлений."""
    logs = NotificationLog.objects.select_related('certificate').all()
    return render(request, 'certificates/notifications.html', {'logs': logs})

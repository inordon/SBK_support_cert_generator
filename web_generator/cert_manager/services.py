"""
Сервис для email-уведомлений о сертификатах.
"""

import logging
from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from .models import Certificate, NotificationLog

logger = logging.getLogger(__name__)


def _log_notification(certificate, notification_type, valid_to_date, recipients, success, error_message=''):
    """Создаёт запись в логе уведомлений, обновляя при конфликте уникальности."""
    try:
        NotificationLog.objects.create(
            certificate=certificate,
            notification_type=notification_type,
            valid_to_date=valid_to_date,
            recipients=recipients,
            success=success,
            error_message=error_message,
        )
    except IntegrityError:
        # Запись с таким (certificate, type, valid_to_date) уже есть — обновляем
        NotificationLog.objects.filter(
            certificate=certificate,
            notification_type=notification_type,
            valid_to_date=valid_to_date,
        ).update(
            recipients=recipients,
            success=success,
            error_message=error_message,
        )


def send_certificate_notification(certificate: Certificate, action: str, user=None):
    """
    Отправляет email-уведомление о действии с сертификатом.
    Вызывается из Celery-задачи, а не из view напрямую.

    Args:
        certificate: объект сертификата
        action: 'created' или 'updated'
        user: пользователь, выполнивший действие
    """
    recipients = [r.strip() for r in settings.CERT_NOTIFICATION_RECIPIENTS if r.strip()]
    if certificate.request_email:
        recipients.append(certificate.request_email)

    if not recipients:
        logger.info('Нет получателей для уведомления о сертификате %s', certificate.certificate_id)
        return

    subjects = {
        'created': f'Создан новый сертификат: {certificate.certificate_id}',
        'updated': f'Изменён сертификат: {certificate.certificate_id}',
    }

    context = {
        'certificate': certificate,
        'action': action,
        'user': user,
    }

    html_message = render_to_string(f'email/certificate_{action}.html', context)
    plain_message = strip_tags(html_message)

    recipients_str = ', '.join(recipients)

    try:
        send_mail(
            subject=subjects.get(action, f'Уведомление: {certificate.certificate_id}'),
            message=plain_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=False,
        )
        _log_notification(certificate, action, certificate.valid_to, recipients_str, True)
        logger.info('Уведомление "%s" отправлено для %s', action, certificate.certificate_id)
    except Exception as e:
        logger.error('Ошибка отправки уведомления: %s', e)
        _log_notification(certificate, action, certificate.valid_to, recipients_str, False, str(e))


def send_expiry_notification(certificate: Certificate, months_left: int):
    """
    Отправляет уведомление об истечении срока сертификата.

    Уникальность определяется по (certificate, notification_type, valid_to_date).
    Если сертификат продлили (valid_to изменился), уведомление отправится снова.
    """
    notify_type = f'expiry_{months_left}m'

    # Проверяем, не отправляли ли уже для этого конкретного valid_to
    if NotificationLog.objects.filter(
        certificate=certificate,
        notification_type=notify_type,
        valid_to_date=certificate.valid_to,
        success=True,
    ).exists():
        return

    recipients = [r.strip() for r in settings.CERT_NOTIFICATION_RECIPIENTS if r.strip()]
    if certificate.request_email:
        recipients.append(certificate.request_email)

    if not recipients:
        return

    subject = (
        f'Сертификат {certificate.certificate_id} истекает '
        f'через {"2 месяца" if months_left == 2 else "1 месяц"}'
    )

    context = {
        'certificate': certificate,
        'months_left': months_left,
    }

    html_message = render_to_string('email/certificate_expiry.html', context)
    plain_message = strip_tags(html_message)

    recipients_str = ', '.join(recipients)

    try:
        send_mail(
            subject=subject,
            message=plain_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=False,
        )
        _log_notification(certificate, notify_type, certificate.valid_to, recipients_str, True)
        logger.info('Уведомление об истечении (%d мес) отправлено для %s',
                     months_left, certificate.certificate_id)
    except Exception as e:
        logger.error('Ошибка отправки уведомления об истечении: %s', e)
        _log_notification(certificate, notify_type, certificate.valid_to, recipients_str, False, str(e))

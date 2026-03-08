"""
Celery задачи для уведомлений и периодической проверки сертификатов.
"""

import logging
from datetime import timedelta
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=60,
    retry_backoff_max=600,
    max_retries=3,
)
def send_certificate_notification_task(certificate_pk: str, action: str, user_pk=None):
    """
    Асинхронная отправка email-уведомления о создании/изменении сертификата.
    Вызывается из views вместо синхронного send_certificate_notification.
    """
    from django.contrib.auth import get_user_model
    from .models import Certificate
    from .services import send_certificate_notification

    User = get_user_model()

    try:
        certificate = Certificate.objects.get(pk=certificate_pk)
    except Certificate.DoesNotExist:
        logger.error('Сертификат %s не найден для отправки уведомления', certificate_pk)
        return

    user = None
    if user_pk:
        try:
            user = User.objects.get(pk=user_pk)
        except User.DoesNotExist:
            pass

    send_certificate_notification(certificate, action, user)


@shared_task
def check_expiring_certificates():
    """
    Проверяет сертификаты, истекающие через 2 месяца и через 1 месяц,
    и отправляет email-уведомления.
    Запускается ежедневно через Celery Beat.
    """
    from .models import Certificate
    from .services import send_expiry_notification

    today = timezone.now().date()
    logger.info('Запуск проверки истекающих сертификатов на %s', today)

    # За 2 месяца (примерно 60 дней)
    target_2m = today + timedelta(days=60)
    window_2m_start = target_2m - timedelta(days=3)
    window_2m_end = target_2m + timedelta(days=3)

    certs_2m = Certificate.objects.filter(
        is_active=True,
        valid_to__gte=window_2m_start,
        valid_to__lte=window_2m_end,
    )

    sent_2m = 0
    for cert in certs_2m:
        if send_expiry_notification(cert, months_left=2):
            sent_2m += 1

    # За 1 месяц (примерно 30 дней)
    target_1m = today + timedelta(days=30)
    window_1m_start = target_1m - timedelta(days=3)
    window_1m_end = target_1m + timedelta(days=3)

    certs_1m = Certificate.objects.filter(
        is_active=True,
        valid_to__gte=window_1m_start,
        valid_to__lte=window_1m_end,
    )

    sent_1m = 0
    for cert in certs_1m:
        if send_expiry_notification(cert, months_left=1):
            sent_1m += 1

    logger.info(
        'Проверка завершена: %d уведомлений за 2 мес, %d за 1 мес',
        sent_2m, sent_1m
    )
    return {'2_months': sent_2m, '1_month': sent_1m}

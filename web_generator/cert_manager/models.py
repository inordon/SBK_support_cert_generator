import uuid
from django.core.exceptions import ValidationError
from django.db import models
from django.conf import settings
from django.utils import timezone


class Certificate(models.Model):
    """Модель сертификата."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    certificate_id = models.CharField(
        'ID сертификата', max_length=23, unique=True,
        help_text='Формат: XXXXX-XXXXX-XXXXX-XXXXX'
    )
    domain = models.CharField('Домен', max_length=255, db_index=True)
    inn = models.CharField('ИНН/БИН', max_length=12, db_index=True)
    valid_from = models.DateField('Действует с')
    valid_to = models.DateField('Действует до', db_index=True)
    users_count = models.PositiveIntegerField('Кол-во пользователей')
    created_at = models.DateTimeField('Создан', default=timezone.now)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name='Создал',
        related_name='certificates'
    )
    is_active = models.BooleanField('Активен', default=True, db_index=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)
    request_email = models.EmailField(
        'Email для запросов', blank=True, default=''
    )
    contacts = models.JSONField(
        'Контакты', default=list, blank=True,
        help_text='Список контактов: [{name, email}]'
    )

    class Meta:
        db_table = 'web_certificates'
        ordering = ['-created_at']
        verbose_name = 'Сертификат'
        verbose_name_plural = 'Сертификаты'
        indexes = [
            models.Index(fields=['domain', 'is_active']),
            models.Index(fields=['inn', 'is_active']),
            models.Index(fields=['is_active', 'valid_to']),
        ]

    def clean(self):
        super().clean()
        if self.contacts:
            if not isinstance(self.contacts, list):
                raise ValidationError({'contacts': 'Контакты должны быть списком.'})
            for i, item in enumerate(self.contacts):
                if not isinstance(item, dict):
                    raise ValidationError({'contacts': f'Элемент {i} должен быть объектом.'})
                if 'name' not in item or 'email' not in item:
                    raise ValidationError(
                        {'contacts': f'Элемент {i}: обязательные поля — name, email.'}
                    )

    def __str__(self):
        return f'{self.certificate_id} — {self.domain}'

    @property
    def validity_period(self):
        return f"{self.valid_from.strftime('%d.%m.%Y')} — {self.valid_to.strftime('%d.%m.%Y')}"

    @property
    def days_left(self):
        today = timezone.now().date()
        if today > self.valid_to:
            return 0
        if today < self.valid_from:
            return 0
        return (self.valid_to - today).days

    @property
    def status(self):
        """Возвращает текущий статус сертификата."""
        today = timezone.now().date()
        if not self.is_active:
            return 'inactive'
        if today < self.valid_from:
            return 'not_started'
        if today > self.valid_to:
            return 'expired'
        days = (self.valid_to - today).days
        if days <= 7:
            return 'expiring_critical'
        if days <= 30:
            return 'expiring_soon'
        if days <= 60:
            return 'expiring_warning'
        return 'active'

    @property
    def status_display(self):
        today = timezone.now().date()
        labels = {
            'inactive': ('Деактивирован', 'danger'),
            'not_started': (f'Начнётся через {(self.valid_from - today).days} дн', 'secondary'),
            'expired': (f'Просрочен ({(today - self.valid_to).days} дн)', 'danger'),
            'expiring_critical': (f'Истекает через {self.days_left} дн', 'danger'),
            'expiring_soon': (f'Истекает через {self.days_left} дн', 'warning'),
            'expiring_warning': (f'Истекает через {self.days_left} дн', 'warning'),
            'active': (f'Активен ({self.days_left} дн)', 'success'),
        }
        text, badge = labels.get(self.status, ('Неизвестно', 'secondary'))
        return text, badge


class CertificateHistory(models.Model):
    """Журнал действий с сертификатами."""

    ACTION_CHOICES = [
        ('created', 'Создан'),
        ('updated', 'Изменён'),
        ('dates_updated', 'Даты изменены'),
        ('deactivated', 'Деактивирован'),
        ('activated', 'Активирован'),
        ('verified', 'Проверен'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    certificate = models.ForeignKey(
        Certificate, on_delete=models.CASCADE,
        related_name='history', to_field='certificate_id',
        db_column='certificate_id', verbose_name='Сертификат'
    )
    action = models.CharField('Действие', max_length=50, choices=ACTION_CHOICES)
    performed_at = models.DateTimeField('Дата', default=timezone.now)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name='Пользователь'
    )
    details = models.JSONField('Детали', default=dict, blank=True)

    class Meta:
        db_table = 'web_certificate_history'
        ordering = ['-performed_at']
        verbose_name = 'Запись истории'
        verbose_name_plural = 'История сертификатов'

    def __str__(self):
        return f'{self.certificate_id} — {self.get_action_display()}'


class NotificationLog(models.Model):
    """Лог отправленных уведомлений об истечении сертификатов."""

    NOTIFY_TYPE_CHOICES = [
        ('expiry_2m', 'За 2 месяца до истечения'),
        ('expiry_1m', 'За 1 месяц до истечения'),
        ('created', 'Создание сертификата'),
        ('updated', 'Изменение сертификата'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    certificate = models.ForeignKey(
        Certificate, on_delete=models.CASCADE,
        related_name='notifications', verbose_name='Сертификат'
    )
    notification_type = models.CharField(
        'Тип уведомления', max_length=20, choices=NOTIFY_TYPE_CHOICES
    )
    valid_to_date = models.DateField(
        'Дата истечения на момент уведомления', null=True, blank=True,
        help_text='Для expiry-уведомлений: к какому valid_to относится'
    )
    sent_at = models.DateTimeField('Отправлено', default=timezone.now)
    recipients = models.TextField('Получатели', help_text='Через запятую')
    success = models.BooleanField('Успешно', default=True)
    error_message = models.TextField('Ошибка', blank=True, default='')

    class Meta:
        db_table = 'web_notification_log'
        ordering = ['-sent_at']
        verbose_name = 'Уведомление'
        verbose_name_plural = 'Уведомления'
        constraints = [
            models.UniqueConstraint(
                fields=['certificate', 'notification_type', 'valid_to_date'],
                name='unique_notification_per_period',
            ),
        ]

    def __str__(self):
        return f'{self.certificate} — {self.get_notification_type_display()}'

"""
Management command для настройки расписания Celery Beat.
"""

from django.core.management.base import BaseCommand
from django_celery_beat.models import PeriodicTask, CrontabSchedule


class Command(BaseCommand):
    help = 'Создаёт расписание Celery Beat для проверки истекающих сертификатов'

    def handle(self, *args, **options):
        # Ежедневно в 09:00
        schedule, _ = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='9',
            day_of_week='*',
            day_of_month='*',
            month_of_year='*',
        )

        task, created = PeriodicTask.objects.get_or_create(
            name='Проверка истекающих сертификатов',
            defaults={
                'task': 'cert_manager.tasks.check_expiring_certificates',
                'crontab': schedule,
                'enabled': True,
            }
        )

        if created:
            self.stdout.write(self.style.SUCCESS(
                'Задача "Проверка истекающих сертификатов" создана (ежедневно в 09:00)'
            ))
        else:
            self.stdout.write(self.style.WARNING(
                'Задача уже существует'
            ))

import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_generator.settings')

app = Celery('web_generator')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

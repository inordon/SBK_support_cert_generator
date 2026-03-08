from django.contrib import admin
from .models import Certificate, CertificateHistory, NotificationLog


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ['certificate_id', 'domain', 'inn', 'valid_from',
                    'valid_to', 'users_count', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['certificate_id', 'domain', 'inn']
    readonly_fields = ['certificate_id', 'created_at', 'updated_at']


@admin.register(CertificateHistory)
class CertificateHistoryAdmin(admin.ModelAdmin):
    list_display = ['certificate', 'action', 'performed_by', 'performed_at']
    list_filter = ['action', 'performed_at']
    readonly_fields = ['certificate', 'action', 'performed_by', 'performed_at', 'details']


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ['certificate', 'notification_type', 'sent_at', 'success']
    list_filter = ['notification_type', 'success', 'sent_at']
    readonly_fields = ['certificate', 'notification_type', 'sent_at',
                       'recipients', 'success', 'error_message']

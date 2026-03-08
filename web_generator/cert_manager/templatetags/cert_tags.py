from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def status_badge(certificate):
    """Возвращает HTML-бейдж статуса сертификата."""
    text, badge_class = certificate.status_display
    return mark_safe(f'<span class="badge bg-{escape(badge_class)}">{escape(text)}</span>')

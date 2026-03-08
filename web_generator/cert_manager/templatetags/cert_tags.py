from django import template

register = template.Library()


@register.filter
def status_badge(certificate):
    """Возвращает HTML-бейдж статуса сертификата."""
    text, badge_class = certificate.status_display
    return f'<span class="badge bg-{badge_class}">{text}</span>'

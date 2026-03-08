"""
Декораторы для разграничения прав доступа.

Роли:
- Любой аутентифицированный пользователь (is_authenticated) — просмотр.
- Администратор (is_staff) — создание, редактирование, деактивация/активация.
"""

from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def admin_required(view_func):
    """
    Декоратор: требует аутентификации + is_staff.
    Обычные пользователи (операторы) получают 403.
    """
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied(
                'У вас нет прав для выполнения этого действия. '
                'Обратитесь к администратору.'
            )
        return view_func(request, *args, **kwargs)
    return wrapper

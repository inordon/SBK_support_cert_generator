from django.urls import path
from . import views

urlpatterns = [
    path('healthz/', views.healthz, name='healthz'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('', views.dashboard, name='dashboard'),
    path('certificates/', views.certificate_list, name='certificate_list'),
    path('certificates/create/', views.certificate_create, name='certificate_create'),
    path('certificates/<str:cert_id>/', views.certificate_detail, name='certificate_detail'),
    path('certificates/<str:cert_id>/edit-dates/', views.certificate_edit_dates, name='certificate_edit_dates'),
    path('certificates/<str:cert_id>/deactivate/', views.certificate_deactivate, name='certificate_deactivate'),
    path('certificates/<str:cert_id>/activate/', views.certificate_activate, name='certificate_activate'),
    path('certificates/<str:cert_id>/payment/', views.certificate_update_payment, name='certificate_update_payment'),
    path('notifications/', views.notification_log, name='notification_log'),
]

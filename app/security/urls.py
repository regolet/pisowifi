"""
Security module URL configuration
"""

from django.urls import path
from . import views
from . import api_views

app_name = 'security'

urlpatterns = [
    path('dashboard/', views.SecurityDashboardView.as_view(), name='dashboard'),
    path('dashboard/api/', views.security_dashboard_api, name='dashboard_api'),
    path('report/', views.security_report_view, name='report'),
    path('alerts/', views.security_alerts_view, name='alerts'),
    path('block-ip/', views.block_ip_view, name='block_ip'),
    path('unblock-ip/', views.unblock_ip_view, name='unblock_ip'),
    path('fail2ban-unban/', views.fail2ban_unban_view, name='fail2ban_unban'),
    
    # API Key Management
    path('api-keys/', api_views.APIKeyManagementView.as_view(), name='api_keys'),
    path('api-keys/create/', api_views.create_api_key_view, name='create_api_key'),
    path('api-keys/revoke/', api_views.revoke_api_key_view, name='revoke_api_key'),
    path('api-keys/test/', api_views.test_api_key_view, name='test_api_key'),
]
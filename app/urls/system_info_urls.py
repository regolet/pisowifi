"""
System Information URLs
"""
from django.urls import path
from app.views.system_info_views import (
    system_info_dashboard, 
    system_info_api, 
    system_info_detailed_api
)

app_name = 'system_info'

urlpatterns = [
    path('dashboard/', system_info_dashboard, name='dashboard'),
    path('api/', system_info_api, name='api'),
    path('api/detailed/', system_info_detailed_api, name='detailed_api'),
]
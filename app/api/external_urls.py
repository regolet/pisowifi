"""
External API URLs for PISOWifi integrations
"""

from django.urls import path
from app.security.api_views import (
    api_clients_list,
    api_sales_summary, 
    api_system_status
)

urlpatterns = [
    path('clients/', api_clients_list, name='api_clients'),
    path('sales/summary/', api_sales_summary, name='api_sales_summary'),
    path('system/status/', api_system_status, name='api_system_status'),
]
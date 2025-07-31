from django.urls import path, include
from app.api.views import DashboardDetails 

urlpatterns = [
	path('dashboard_data/', DashboardDetails.as_view()),
	path('external/', include('app.api.external_urls')),
]
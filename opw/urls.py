from django.contrib import admin
from django.urls import path, include
from django.views.generic.base import RedirectView
from django.http import FileResponse
from django.conf.urls.static import static
from django.conf import settings
import os

from .views import *
from app.login import admin_login_view

def favicon_view(request):
    favicon_path = os.path.join(settings.BASE_DIR, 'favicon.ico')
    return FileResponse(open(favicon_path, 'rb'), content_type='image/x-icon') 

urlpatterns = [
    path('app/', include('app.urls')),
    path('admin/login/', admin_login_view, name='admin_login'),  # Custom login with rate limiting
    path('admin/', admin.site.urls),
    path('app/api/', include('app.api.urls')),
    path('admin/security/', include('app.security.urls')),
    path('favicon.ico', favicon_view, name='favicon'),
    path('', RedirectView.as_view(url='/app/portal')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Serve static files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0] if settings.STATICFILES_DIRS else settings.STATIC_ROOT)

"""
Admin Authentication Override
Ensures admin users get permanent tokens on login
"""
from django.contrib.auth import login as django_login
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponseRedirect
from django.urls import reverse
from app.services.admin_token_service import get_or_create_admin_token
import logging

logger = logging.getLogger(__name__)

# Store original login function
_original_django_login = django_login

def admin_login_with_token(request, user, backend=None):
    """
    Override Django login to set admin token for staff users
    """
    # Call original login
    _original_django_login(request, user, backend)
    
    # If user is staff, ensure they have an admin token
    if user.is_staff:
        token = get_or_create_admin_token(request)
        if token:
            # Store token in session as backup
            request.session['admin_token'] = token
            request.session['admin_token_user_id'] = user.id
            request.session.set_expiry(365 * 24 * 60 * 60)  # 1 year
            logger.info(f"Set admin token for user {user.username} on login")

# Monkey patch Django login for admin
django_login = admin_login_with_token

def ensure_admin_token(view_func):
    """
    Decorator to ensure admin users have tokens
    """
    def wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_staff:
            # Check if user has token
            if 'admin_token' not in request.COOKIES:
                token = get_or_create_admin_token(request)
                if token:
                    response = view_func(request, *args, **kwargs)
                    response.set_cookie(
                        'admin_token',
                        token,
                        max_age=365 * 24 * 60 * 60,  # 1 year
                        httponly=True,
                        secure=False,
                        samesite='Lax'
                    )
                    return response
        
        return view_func(request, *args, **kwargs)
    
    return wrapped_view
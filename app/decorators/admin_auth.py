"""
Admin Authentication Decorators
Custom decorators that work with token authentication
"""
from functools import wraps
from django.http import JsonResponse
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
import logging

logger = logging.getLogger(__name__)

def admin_required_json(view_func):
    """
    Decorator for admin views that return JSON responses
    Works with both session and token authentication
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Check if user is authenticated and is staff
        if not request.user.is_authenticated:
            logger.warning(f"Unauthenticated request to {request.path}")
            return JsonResponse({
                'status': 'error',
                'message': 'Authentication required',
                'code': 'AUTH_REQUIRED'
            }, status=401)
        
        if not request.user.is_staff:
            logger.warning(f"Non-staff user {request.user.username} tried to access {request.path}")
            return JsonResponse({
                'status': 'error',
                'message': 'Admin privileges required',
                'code': 'ADMIN_REQUIRED'
            }, status=403)
        
        # User is authenticated and is staff, proceed with view
        logger.debug(f"Admin user {request.user.username} accessing {request.path}")
        return view_func(request, *args, **kwargs)
    
    return wrapper

def is_admin_user(user):
    """Check if user is authenticated admin"""
    return user.is_authenticated and user.is_staff

def admin_required_simple(view_func):
    """
    Simple admin required decorator using user_passes_test
    """
    return user_passes_test(
        is_admin_user,
        login_url='/admin/login/'
    )(view_func)
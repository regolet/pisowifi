"""
Admin Token Authentication Middleware
Provides session-independent authentication for admin users
"""
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth import login
from django.contrib.auth.models import AnonymousUser
from app.services.admin_token_service import admin_token_service, get_or_create_admin_token
import logging

logger = logging.getLogger(__name__)

class AdminTokenAuthMiddleware(MiddlewareMixin):
    """
    Middleware that authenticates admin users via tokens instead of sessions
    This prevents session expiration issues during long operations
    """
    
    def process_request(self, request):
        # Only process admin requests
        if not request.path.startswith('/admin/'):
            return None
        
        # Check for admin token in cookies or headers
        token = (
            request.COOKIES.get('admin_token') or 
            request.META.get('HTTP_X_ADMIN_TOKEN') or
            request.GET.get('admin_token')
        )
        
        if token:
            # Validate token and get user
            user = admin_token_service.get_user_from_token(token)
            if user and user.is_staff:
                # Set user without using session
                request.user = user
                request._cached_user = user
                request.admin_token_auth = True
                logger.debug(f"Authenticated admin user {user.username} via token")
                return None
        
        # Fall back to normal session auth
        return None
    
    def process_response(self, request, response):
        # Set admin token cookie if user is authenticated admin
        if (hasattr(request, 'user') and 
            request.user.is_authenticated and 
            request.user.is_staff and
            request.path.startswith('/admin/')):
            
            # Get or create admin token
            token = get_or_create_admin_token(request)
            if token and 'admin_token' not in request.COOKIES:
                # Set cookie with very long expiration
                response.set_cookie(
                    'admin_token',
                    token,
                    max_age=365 * 24 * 60 * 60,  # 1 year
                    httponly=True,
                    secure=False,  # Set to True in production with HTTPS
                    samesite='Lax'
                )
                logger.info(f"Set admin token cookie for user {request.user.username}")
        
        return response

class AdminUpdateAuthMiddleware(MiddlewareMixin):
    """
    Special middleware for update operations that completely bypasses session checks
    """
    
    def process_request(self, request):
        # Only process update-related admin requests
        if '/systemupdate/' not in request.path:
            return None
        
        # If already authenticated via token, skip
        if getattr(request, 'admin_token_auth', False):
            return None
        
        # For update operations, try to authenticate via token even if session expired
        token = (
            request.COOKIES.get('admin_token') or 
            request.META.get('HTTP_X_ADMIN_TOKEN')
        )
        
        if token:
            user = admin_token_service.get_user_from_token(token)
            if user and user.is_staff:
                # Force authentication without session
                request.user = user
                request._cached_user = user
                request.admin_token_auth = True
                
                # Bypass session framework entirely
                if hasattr(request, 'session'):
                    # Make session think it's authenticated
                    request.session['_auth_user_id'] = str(user.id)
                    request.session['_auth_user_backend'] = 'django.contrib.auth.backends.ModelBackend'
                    request.session['_auth_user_hash'] = user.get_session_auth_hash()
                    request.session.modified = True
                
                logger.info(f"Force authenticated admin user {user.username} for update operation")
                
        return None
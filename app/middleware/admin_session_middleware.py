"""
Admin Session Persistence Middleware
Prevents session expiration for admin users during critical operations
"""
from django.utils import timezone
from django.contrib.sessions.models import Session
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

class AdminSessionPersistenceMiddleware:
    """
    Middleware that ensures admin sessions never expire unexpectedly
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Process the request
        response = self.get_response(request)
        
        # Only process for authenticated admin users
        if (request.user.is_authenticated and 
            request.user.is_staff and 
            request.session.session_key):
            
            self.extend_admin_session(request)
        
        return response
    
    def extend_admin_session(self, request):
        """
        Extend session for admin users to prevent expiration
        """
        try:
            session_key = request.session.session_key
            if not session_key:
                return
            
            # Check if this is an admin request
            if '/admin/' in request.path:
                # Get the current session
                try:
                    session = Session.objects.get(session_key=session_key)
                    current_time = timezone.now()
                    
                    # If session expires within the next hour, extend it
                    if session.expire_date <= current_time + timedelta(hours=1):
                        # Extend session by 24 hours
                        session.expire_date = current_time + timedelta(hours=24)
                        session.save()
                        logger.debug(f"Extended admin session {session_key} until {session.expire_date}")
                    
                    # Special handling for update operations
                    if '/systemupdate/' in request.path:
                        # Always extend for update operations
                        session.expire_date = current_time + timedelta(hours=24)
                        session.save()
                        logger.debug(f"Extended update operation session {session_key}")
                        
                except Session.DoesNotExist:
                    # Session doesn't exist, create a new one
                    request.session.create()
                    logger.info(f"Created new session for admin user: {request.user.username}")
                    
        except Exception as e:
            logger.error(f"Error in admin session middleware: {e}")

class NoSessionExpirationMiddleware:
    """
    Middleware that completely disables session expiration for admin operations
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Check if this is an admin user on admin pages
        if (hasattr(request, 'user') and 
            request.user.is_authenticated and 
            request.user.is_staff and 
            '/admin/' in request.path):
            
            # Temporarily disable session expiration
            original_session_age = request.session.get_expiry_age()
            
            # Set a very long expiration (30 days)
            request.session.set_expiry(86400 * 30)
            
            # Store original expiry for restoration if needed
            request.session['_original_expiry'] = original_session_age
        
        response = self.get_response(request)
        return response
"""
Session utilities for admin operations
"""
from django.contrib.sessions.models import Session
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

def disable_session_expiration(request):
    """
    Completely disable session expiration for the current request
    """
    if request.session.session_key:
        try:
            session = Session.objects.get(session_key=request.session.session_key)
            # Set expiration to very far in the future (1 year)
            session.expire_date = timezone.now() + timedelta(days=365)
            session.save()
            logger.info(f"Disabled session expiration for session {request.session.session_key}")
            return True
        except Session.DoesNotExist:
            # Create new session with long expiration
            request.session.create()
            request.session.set_expiry(365 * 24 * 60 * 60)  # 1 year in seconds
            logger.info(f"Created new non-expiring session")
            return True
    else:
        # Create new session
        request.session.create()
        request.session.set_expiry(365 * 24 * 60 * 60)  # 1 year in seconds
        logger.info(f"Created new session with long expiration")
        return True

def make_session_permanent(request):
    """
    Make the current session permanent (never expires)
    """
    # Set session to never expire
    request.session.set_expiry(None)
    
    # Also update the database record
    if request.session.session_key:
        try:
            session = Session.objects.get(session_key=request.session.session_key)
            # Set to expire in 10 years
            session.expire_date = timezone.now() + timedelta(days=3650)
            session.save()
            logger.info(f"Made session permanent: {request.session.session_key}")
        except Session.DoesNotExist:
            pass

def extend_session_for_admin(request, hours=24):
    """
    Extend session for admin operations
    """
    if request.user.is_authenticated and request.user.is_staff:
        request.session.set_expiry(hours * 60 * 60)
        
        if request.session.session_key:
            try:
                session = Session.objects.get(session_key=request.session.session_key)
                session.expire_date = timezone.now() + timedelta(hours=hours)
                session.save()
                logger.info(f"Extended admin session by {hours} hours")
            except Session.DoesNotExist:
                pass
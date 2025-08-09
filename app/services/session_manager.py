"""
Session Management Service for Long-Running Operations
Handles session extension and management during system updates
"""
import time
import threading
from django.contrib.sessions.models import Session
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

class SessionKeepAlive:
    """
    Manages session keep-alive for long-running operations like system updates
    """
    
    def __init__(self, request, operation_name="operation"):
        self.session_key = request.session.session_key
        self.operation_name = operation_name
        self.keep_alive_thread = None
        self.stop_event = threading.Event()
        self.extend_interval = 300  # Extend session every 5 minutes
        self.session_extension = 3600  # Extend by 1 hour each time
        
    def start_keep_alive(self):
        """Start the session keep-alive thread"""
        if self.session_key:
            self.keep_alive_thread = threading.Thread(
                target=self._keep_alive_worker,
                daemon=True,
                name=f"SessionKeepAlive-{self.operation_name}"
            )
            self.keep_alive_thread.start()
            logger.info(f"Started session keep-alive for {self.operation_name} (session: {self.session_key})")
    
    def stop_keep_alive(self):
        """Stop the session keep-alive thread"""
        if self.keep_alive_thread and self.keep_alive_thread.is_alive():
            self.stop_event.set()
            self.keep_alive_thread.join(timeout=5)
            logger.info(f"Stopped session keep-alive for {self.operation_name}")
    
    def _keep_alive_worker(self):
        """Worker function that extends session periodically"""
        while not self.stop_event.wait(self.extend_interval):
            try:
                self._extend_session()
            except Exception as e:
                logger.warning(f"Failed to extend session for {self.operation_name}: {e}")
                break
    
    def _extend_session(self):
        """Extend the current session"""
        try:
            if self.session_key:
                session = Session.objects.get(session_key=self.session_key)
                # Extend session by the specified time
                new_expiry = timezone.now() + timedelta(seconds=self.session_extension)
                session.expire_date = new_expiry
                session.save()
                logger.debug(f"Extended session {self.session_key} until {new_expiry}")
        except Session.DoesNotExist:
            logger.warning(f"Session {self.session_key} no longer exists")
            self.stop_event.set()
        except Exception as e:
            logger.error(f"Error extending session: {e}")

class UpdateSessionManager:
    """
    Specialized session manager for system update operations
    """
    
    def __init__(self, request, update_object):
        self.request = request
        self.update = update_object
        self.session_keeper = None
        
    def __enter__(self):
        """Context manager entry - start session management"""
        self.start_session_management()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - stop session management"""
        self.stop_session_management()
    
    def start_session_management(self):
        """Start managing the session for update operations"""
        try:
            # Force session creation if it doesn't exist
            if not self.request.session.session_key:
                self.request.session.create()
            
            # Start keep-alive mechanism
            self.session_keeper = SessionKeepAlive(
                self.request, 
                f"Update-{self.update.Version_Number}"
            )
            self.session_keeper.start_keep_alive()
            
            # Store update operation in session for tracking
            self.request.session['active_update'] = {
                'update_id': self.update.pk,
                'version': self.update.Version_Number,
                'started_at': timezone.now().isoformat()
            }
            self.request.session.save()
            
            logger.info(f"Started session management for update {self.update.Version_Number}")
            
        except Exception as e:
            logger.error(f"Failed to start session management: {e}")
    
    def stop_session_management(self):
        """Stop session management"""
        try:
            if self.session_keeper:
                self.session_keeper.stop_keep_alive()
            
            # Clean up session data
            if 'active_update' in self.request.session:
                del self.request.session['active_update']
                self.request.session.save()
            
            logger.info(f"Stopped session management for update {self.update.Version_Number}")
            
        except Exception as e:
            logger.error(f"Failed to stop session management: {e}")
    
    def extend_session_for_update(self, extra_time=7200):
        """Extend session specifically for update operations (default 2 hours)"""
        try:
            if self.request.session.session_key:
                session = Session.objects.get(session_key=self.request.session.session_key)
                session.expire_date = timezone.now() + timedelta(seconds=extra_time)
                session.save()
                logger.info(f"Extended session for update by {extra_time} seconds")
        except Exception as e:
            logger.error(f"Failed to extend session for update: {e}")

def create_update_session_context(request, update_object):
    """
    Factory function to create session management context for updates
    Usage:
        with create_update_session_context(request, update) as session_mgr:
            # Perform long-running update operations
            pass
    """
    return UpdateSessionManager(request, update_object)

def is_session_active(session_key):
    """Check if a session is still active"""
    try:
        session = Session.objects.get(session_key=session_key)
        return session.expire_date > timezone.now()
    except Session.DoesNotExist:
        return False

def cleanup_expired_update_sessions():
    """Clean up expired sessions that were tracking updates"""
    try:
        # This could be called periodically to clean up
        expired_sessions = Session.objects.filter(expire_date__lt=timezone.now())
        count = expired_sessions.count()
        expired_sessions.delete()
        logger.info(f"Cleaned up {count} expired sessions")
    except Exception as e:
        logger.error(f"Failed to cleanup expired sessions: {e}")
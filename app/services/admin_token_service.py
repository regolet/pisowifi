"""
Admin Token Service - Bypass session expiration entirely
Uses secure tokens for admin operations that don't expire
"""
import secrets
import hashlib
import json
from datetime import datetime, timedelta
from django.conf import settings
from django.core.cache import cache
from django.contrib.auth.models import User
import logging

logger = logging.getLogger(__name__)

class AdminTokenService:
    """
    Provides session-independent authentication tokens for admin operations
    """
    
    def __init__(self):
        self.token_prefix = 'admin_token_'
        self.token_lifetime = timedelta(days=365)  # 1 year tokens
        
    def generate_admin_token(self, user):
        """
        Generate a secure token for admin user that bypasses session expiration
        """
        if not user.is_staff:
            return None
            
        # Generate secure random token
        token = secrets.token_urlsafe(64)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        # Store token data
        token_data = {
            'user_id': user.id,
            'username': user.username,
            'created_at': datetime.now().isoformat(),
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
            'email': user.email,
            'token_hash': token_hash
        }
        
        # Store in cache with very long expiration
        cache_key = f"{self.token_prefix}{token_hash}"
        cache.set(cache_key, token_data, timeout=int(self.token_lifetime.total_seconds()))
        
        # Also store in a file as backup (in case cache is cleared)
        self._store_token_backup(token_hash, token_data)
        
        logger.info(f"Generated admin token for user {user.username}")
        
        return token
    
    def validate_token(self, token):
        """
        Validate admin token and return user data
        """
        try:
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            cache_key = f"{self.token_prefix}{token_hash}"
            
            # Try cache first
            token_data = cache.get(cache_key)
            
            if not token_data:
                # Try backup file
                token_data = self._load_token_backup(token_hash)
                if token_data:
                    # Restore to cache
                    cache.set(cache_key, token_data, timeout=int(self.token_lifetime.total_seconds()))
            
            if token_data:
                # Verify token is still valid
                created_at = datetime.fromisoformat(token_data['created_at'])
                if datetime.now() - created_at < self.token_lifetime:
                    return token_data
                else:
                    logger.warning(f"Token expired for user {token_data.get('username')}")
                    
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            
        return None
    
    def get_user_from_token(self, token):
        """
        Get Django user object from token
        """
        token_data = self.validate_token(token)
        if token_data:
            try:
                return User.objects.get(id=token_data['user_id'])
            except User.DoesNotExist:
                logger.error(f"User {token_data['user_id']} not found for valid token")
        return None
    
    def invalidate_token(self, token):
        """
        Invalidate a token
        """
        try:
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            cache_key = f"{self.token_prefix}{token_hash}"
            cache.delete(cache_key)
            self._remove_token_backup(token_hash)
            logger.info(f"Invalidated token {token_hash[:8]}...")
            return True
        except Exception as e:
            logger.error(f"Failed to invalidate token: {e}")
            return False
    
    def _get_backup_path(self, token_hash):
        """Get backup file path for token"""
        import os
        backup_dir = os.path.join(settings.BASE_DIR, '.admin_tokens')
        os.makedirs(backup_dir, exist_ok=True)
        return os.path.join(backup_dir, f"{token_hash}.json")
    
    def _store_token_backup(self, token_hash, token_data):
        """Store token data to file as backup"""
        try:
            backup_path = self._get_backup_path(token_hash)
            with open(backup_path, 'w') as f:
                json.dump(token_data, f)
        except Exception as e:
            logger.warning(f"Failed to store token backup: {e}")
    
    def _load_token_backup(self, token_hash):
        """Load token data from backup file"""
        try:
            backup_path = self._get_backup_path(token_hash)
            if os.path.exists(backup_path):
                with open(backup_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load token backup: {e}")
        return None
    
    def _remove_token_backup(self, token_hash):
        """Remove token backup file"""
        try:
            backup_path = self._get_backup_path(token_hash)
            if os.path.exists(backup_path):
                os.remove(backup_path)
        except Exception as e:
            logger.warning(f"Failed to remove token backup: {e}")

# Global instance
admin_token_service = AdminTokenService()

def generate_permanent_admin_token(user):
    """
    Generate a permanent token for admin operations
    """
    return admin_token_service.generate_admin_token(user)

def validate_admin_token(token):
    """
    Validate an admin token
    """
    return admin_token_service.validate_token(token)

def get_or_create_admin_token(request):
    """
    Get existing admin token from cookies or create new one
    """
    # Check if user has existing token in cookie
    existing_token = request.COOKIES.get('admin_token')
    
    if existing_token and admin_token_service.validate_token(existing_token):
        return existing_token
    
    # Generate new token if user is staff
    if request.user.is_authenticated and request.user.is_staff:
        return admin_token_service.generate_admin_token(request.user)
    
    return None
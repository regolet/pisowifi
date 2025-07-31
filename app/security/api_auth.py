"""
API Key Authentication for PISOWifi External Integrations
"""

import secrets
import hashlib
import hmac
from datetime import datetime, timedelta
from django.contrib.auth.models import User
from django.core.cache import cache
from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from functools import wraps
import logging

from .monitoring import security_monitor

logger = logging.getLogger('security')


class APIKey:
    """
    API Key management for external integrations
    """
    
    def __init__(self, key_id, key_secret, user, name, permissions=None, expires_at=None):
        self.key_id = key_id
        self.key_secret = key_secret
        self.user = user
        self.name = name
        self.permissions = permissions or []
        self.expires_at = expires_at
        self.created_at = timezone.now()
        self.last_used = None
        self.usage_count = 0
    
    def is_valid(self):
        """Check if API key is still valid"""
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True
    
    def has_permission(self, permission):
        """Check if API key has specific permission"""
        return permission in self.permissions
    
    def to_dict(self):
        """Convert to dictionary for storage"""
        return {
            'key_id': self.key_id,
            'key_secret': self.key_secret,
            'user_id': self.user.id if self.user else None,
            'name': self.name,
            'permissions': self.permissions,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'created_at': self.created_at.isoformat(),
            'last_used': self.last_used.isoformat() if self.last_used else None,
            'usage_count': self.usage_count
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create APIKey from dictionary"""
        user = None
        if data.get('user_id'):
            try:
                user = User.objects.get(id=data['user_id'])
            except User.DoesNotExist:
                pass
        
        api_key = cls(
            key_id=data['key_id'],
            key_secret=data['key_secret'],
            user=user,
            name=data['name'],
            permissions=data.get('permissions', []),
            expires_at=datetime.fromisoformat(data['expires_at']) if data.get('expires_at') else None
        )
        
        if data.get('created_at'):
            api_key.created_at = datetime.fromisoformat(data['created_at'])
        if data.get('last_used'):
            api_key.last_used = datetime.fromisoformat(data['last_used'])
        
        api_key.usage_count = data.get('usage_count', 0)
        
        return api_key


class APIKeyManager:
    """
    Manages API keys for external integrations
    """
    
    CACHE_PREFIX = 'pisowifi_api_key'
    CACHE_TIMEOUT = 3600  # 1 hour
    
    # Available permissions
    PERMISSIONS = {
        'read_clients': 'Read client information',
        'manage_clients': 'Manage client connections',
        'read_vouchers': 'Read voucher information',
        'manage_vouchers': 'Create and manage vouchers',
        'read_reports': 'Access sales and usage reports',
        'read_network': 'Read network configuration',
        'manage_network': 'Modify network settings',
        'read_system': 'Read system status',
        'manage_system': 'Modify system settings',
        'security_read': 'Read security information',
        'security_manage': 'Manage security settings',
    }
    
    def generate_api_key(self, user, name, permissions=None, expires_days=None):
        """
        Generate a new API key
        """
        # Generate unique key ID and secret
        key_id = 'pk_' + secrets.token_urlsafe(16)  # pk_ prefix for PISOWifi Key
        key_secret = secrets.token_urlsafe(32)
        
        # Calculate expiration date
        expires_at = None
        if expires_days:
            expires_at = timezone.now() + timedelta(days=expires_days)
        
        # Create API key object
        api_key = APIKey(
            key_id=key_id,
            key_secret=key_secret,
            user=user,
            name=name,
            permissions=permissions or [],
            expires_at=expires_at
        )
        
        # Store in cache
        self._store_api_key(api_key)
        
        # Log creation
        security_monitor.log_security_event(
            'api_key_created',
            self._get_client_ip(),
            {
                'key_id': key_id,
                'name': name,
                'permissions': permissions,
                'created_by': user.username if user else 'system',
                'expires_at': expires_at.isoformat() if expires_at else None
            }
        )
        
        logger.info(f"API key created: {key_id} for {name}")
        
        return api_key
    
    def authenticate_request(self, request):
        """
        Authenticate API request using API key
        """
        # Get API key from headers
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if not auth_header.startswith('Bearer '):
            return None, 'Missing or invalid Authorization header'
        
        key_id = auth_header[7:]  # Remove 'Bearer ' prefix
        
        # Get API key from cache
        api_key = self._get_api_key(key_id)
        
        if not api_key:
            # Log failed authentication
            security_monitor.log_security_event(
                'api_auth_failure',
                self._get_client_ip(request),
                {
                    'key_id': key_id,
                    'reason': 'invalid_key'
                }
            )
            return None, 'Invalid API key'
        
        if not api_key.is_valid():
            # Log expired key usage
            security_monitor.log_security_event(
                'api_auth_failure',
                self._get_client_ip(request),
                {
                    'key_id': key_id,
                    'reason': 'expired_key'
                }
            )
            return None, 'API key has expired'
        
        # Update last used timestamp and usage count
        api_key.last_used = timezone.now()
        api_key.usage_count += 1
        self._store_api_key(api_key)
        
        # Log successful authentication
        security_monitor.log_security_event(
            'api_auth_success',
            self._get_client_ip(request),
            {
                'key_id': key_id,
                'name': api_key.name,
                'user': api_key.user.username if api_key.user else None
            }
        )
        
        return api_key, None
    
    def revoke_api_key(self, key_id, revoked_by=None):
        """
        Revoke an API key
        """
        api_key = self._get_api_key(key_id)
        
        if api_key:
            # Remove from cache
            cache_key = f"{self.CACHE_PREFIX}:{key_id}"
            cache.delete(cache_key)
            
            # Log revocation
            security_monitor.log_security_event(
                'api_key_revoked',
                self._get_client_ip(),
                {
                    'key_id': key_id,
                    'name': api_key.name,
                    'revoked_by': revoked_by
                }
            )
            
            logger.info(f"API key revoked: {key_id} by {revoked_by}")
            return True
        
        return False
    
    def list_api_keys(self):
        """
        List all active API keys (for admin interface)
        """
        # In a production system, you'd store these in a database
        # For now, we'll return a placeholder
        return []
    
    def _store_api_key(self, api_key):
        """
        Store API key in cache
        """
        cache_key = f"{self.CACHE_PREFIX}:{api_key.key_id}"
        cache.set(cache_key, api_key.to_dict(), self.CACHE_TIMEOUT)
    
    def _get_api_key(self, key_id):
        """
        Retrieve API key from cache
        """
        cache_key = f"{self.CACHE_PREFIX}:{key_id}"
        data = cache.get(cache_key)
        
        if data:
            return APIKey.from_dict(data)
        
        return None
    
    def _get_client_ip(self, request=None):
        """
        Get client IP address from request
        """
        if not request:
            return '127.0.0.1'
        
        # Check for real IP in headers (for reverse proxy setups)
        ip = request.META.get('HTTP_X_REAL_IP')
        if ip:
            return ip
        
        ip = request.META.get('HTTP_X_FORWARDED_FOR')
        if ip:
            return ip.split(',')[0].strip()
        
        return request.META.get('REMOTE_ADDR', '127.0.0.1')


# Global API key manager instance
api_key_manager = APIKeyManager()


def require_api_key(permissions=None):
    """
    Decorator to require API key authentication
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Skip API key check for admin users with session authentication
            if request.user.is_authenticated and request.user.is_staff:
                return view_func(request, *args, **kwargs)
            
            # Authenticate API key
            api_key, error = api_key_manager.authenticate_request(request)
            
            if error:
                return JsonResponse({
                    'error': error,
                    'code': 'authentication_failed'
                }, status=401)
            
            # Check permissions
            if permissions:
                missing_permissions = []
                for permission in permissions:
                    if not api_key.has_permission(permission):
                        missing_permissions.append(permission)
                
                if missing_permissions:
                    security_monitor.log_security_event(
                        'api_permission_denied',
                        api_key_manager._get_client_ip(request),
                        {
                            'key_id': api_key.key_id,
                            'required_permissions': permissions,
                            'missing_permissions': missing_permissions
                        }
                    )
                    
                    return JsonResponse({
                        'error': 'Insufficient permissions',
                        'code': 'permission_denied',
                        'required_permissions': permissions,
                        'missing_permissions': missing_permissions
                    }, status=403)
            
            # Add API key to request for use in view
            request.api_key = api_key
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def require_api_permission(permission):
    """
    Decorator to require specific API permission
    """
    return require_api_key([permission])


# Rate limiting for API endpoints
def api_rate_limit(max_requests=100, window_minutes=60):
    """
    Rate limiting decorator for API endpoints
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Get rate limit key (IP or API key)
            if hasattr(request, 'api_key'):
                rate_key = f"api_rate_limit:{request.api_key.key_id}"
            else:
                client_ip = api_key_manager._get_client_ip(request)
                rate_key = f"api_rate_limit:ip:{client_ip}"
            
            # Check current request count
            current_count = cache.get(rate_key, 0)
            
            if current_count >= max_requests:
                # Log rate limit exceeded
                security_monitor.log_security_event(
                    'api_rate_limit_exceeded',
                    api_key_manager._get_client_ip(request),
                    {
                        'rate_key': rate_key,
                        'max_requests': max_requests,
                        'window_minutes': window_minutes,
                        'current_count': current_count
                    }
                )
                
                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'code': 'rate_limit_exceeded',
                    'max_requests': max_requests,
                    'window_minutes': window_minutes,
                    'retry_after': window_minutes * 60
                }, status=429)
            
            # Increment counter
            cache.set(rate_key, current_count + 1, window_minutes * 60)
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator
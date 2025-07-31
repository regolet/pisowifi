"""
Security decorators for PISOWifi views
Provides rate limiting and security checks for specific endpoints
"""

import functools
import logging
from django.core.cache import cache
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django_ratelimit.decorators import ratelimit
from django_ratelimit.exceptions import Ratelimited

logger = logging.getLogger('security')


def get_client_ip(request):
    """Get real client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
    return ip


def security_rate_limit(rate='5/5m', methods=['POST'], key=None):
    """
    Custom rate limiting decorator with security logging
    
    Args:
        rate: Rate limit (e.g., '5/5m' = 5 requests per 5 minutes)
        methods: HTTP methods to apply rate limiting to
        key: Custom key function (defaults to IP-based)
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Apply rate limiting
            rate_limited_view = ratelimit(
                key=key or 'ip',
                rate=rate,
                method=methods,
                block=True
            )(view_func)
            
            try:
                return rate_limited_view(request, *args, **kwargs)
            except Ratelimited:
                client_ip = get_client_ip(request)
                logger.warning(f"Rate limit exceeded for {client_ip} on {request.path}")
                
                # Log security event
                security_logger = logging.getLogger('security')
                security_logger.warning(f"RATE_LIMIT: {client_ip} exceeded {rate} on {request.path}")
                
                # Return appropriate response
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'error': 'Rate limit exceeded',
                        'message': 'Too many requests. Please try again later.',
                        'code': 429
                    }, status=429)
                else:
                    response = HttpResponse("Rate limit exceeded", status=429)
                    response['Retry-After'] = '300'  # 5 minutes
                    return response
        
        return wrapper
    return decorator


def admin_rate_limit(rate='3/5m'):
    """Rate limiting specifically for admin endpoints"""
    return security_rate_limit(rate=rate, key='ip')


def voucher_rate_limit(rate='10/5m'):
    """Rate limiting specifically for voucher operations"""
    return security_rate_limit(rate=rate, key='ip')


def payment_rate_limit(rate='20/5m'):
    """Rate limiting specifically for payment operations"""
    return security_rate_limit(rate=rate, key='ip')


def portal_rate_limit(rate='30/1m'):
    """Rate limiting for portal access"""
    return security_rate_limit(rate=rate, key='ip', methods=['GET', 'POST'])


def require_local_ip(view_func):
    """
    Decorator to require local IP addresses for sensitive operations
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        client_ip = get_client_ip(request)
        local_ips = ['127.0.0.1', '::1', '10.0.0.1', 'localhost']
        
        if client_ip not in local_ips:
            logger.warning(f"Non-local IP attempted sensitive operation: {client_ip}")
            return JsonResponse({
                'error': 'Access denied',
                'message': 'This operation is only allowed from local network'
            }, status=403)
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def log_security_event(event_type):
    """
    Decorator to log security events
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            client_ip = get_client_ip(request)
            
            # Log the security event
            security_logger = logging.getLogger('security')
            security_logger.info(f"SECURITY_EVENT: {event_type} from {client_ip} to {request.path}")
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def validate_request_size(max_size=1024*1024):  # 1MB default
    """
    Decorator to validate request body size
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            content_length = request.META.get('CONTENT_LENGTH')
            if content_length and int(content_length) > max_size:
                client_ip = get_client_ip(request)
                logger.warning(f"Oversized request from {client_ip}: {content_length} bytes")
                
                return JsonResponse({
                    'error': 'Request too large',
                    'message': f'Request size exceeds {max_size} bytes limit',
                    'max_size': max_size
                }, status=413)
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def suspicious_activity_check(view_func):
    """
    Decorator to check for suspicious activity patterns
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        client_ip = get_client_ip(request)
        
        # Check for rapid requests from same IP
        activity_key = f"activity:{client_ip}"
        recent_requests = cache.get(activity_key, [])
        now = timezone.now()
        
        # Remove requests older than 1 minute
        recent_requests = [
            req_time for req_time in recent_requests 
            if (now - req_time).total_seconds() < 60
        ]
        
        # Add current request
        recent_requests.append(now)
        cache.set(activity_key, recent_requests, 300)  # 5 minutes
        
        # Check for suspicious activity (more than 60 requests per minute)
        if len(recent_requests) > 60:
            logger.warning(f"Suspicious activity detected from {client_ip}: {len(recent_requests)} requests/minute")
            
            # Block IP temporarily
            block_key = f"blocked:{client_ip}"
            cache.set(block_key, True, 900)  # Block for 15 minutes
            
            return JsonResponse({
                'error': 'Suspicious activity detected',
                'message': 'Your IP has been temporarily blocked due to unusual activity'
            }, status=429)
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def check_blocked_ip(view_func):
    """
    Decorator to check if IP is blocked
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        client_ip = get_client_ip(request)
        block_key = f"blocked:{client_ip}"
        
        if cache.get(block_key):
            logger.warning(f"Blocked IP attempted access: {client_ip}")
            return JsonResponse({
                'error': 'Access denied',
                'message': 'Your IP address has been blocked due to security violations'
            }, status=403)
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


# Combined security decorator for high-risk endpoints
def high_security(rate='5/5m', max_size=512*1024):
    """
    Combined security decorator for high-risk endpoints
    Includes rate limiting, size validation, and activity monitoring
    """
    def decorator(view_func):
        @check_blocked_ip
        @suspicious_activity_check
        @validate_request_size(max_size)
        @security_rate_limit(rate=rate)
        @never_cache
        def wrapper(request, *args, **kwargs):
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator
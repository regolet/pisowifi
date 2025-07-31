"""
Security event handlers for PISOWifi system
"""

import logging
from django.http import JsonResponse
from django.shortcuts import render
from django.contrib import messages
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger('security')


def lockout_response(request, credentials, *args, **kwargs):
    """
    Custom lockout response for django-axes with countdown timer
    """
    from django.conf import settings
    import datetime
    
    client_ip = get_client_ip(request)
    
    # Calculate remaining lockout time
    cooloff_time = getattr(settings, 'AXES_COOLOFF_TIME', 1)  # in hours
    lockout_seconds = int(cooloff_time * 3600)  # convert to seconds
    
    # Try to get exact lockout time from axes
    try:
        from axes.models import AccessAttempt
        # Get the most recent failed attempt for this IP
        attempt = AccessAttempt.objects.filter(ip_address=client_ip).order_by('-attempt_time').first()
        if attempt:
            lockout_until = attempt.attempt_time + datetime.timedelta(seconds=lockout_seconds)
            remaining_seconds = (lockout_until - timezone.now()).total_seconds()
            remaining_seconds = max(0, int(remaining_seconds))
        else:
            remaining_seconds = lockout_seconds
    except Exception as e:
        logger.warning(f"Could not calculate exact lockout time: {e}")
        remaining_seconds = lockout_seconds
    
    # Format remaining time
    if remaining_seconds > 0:
        if remaining_seconds < 60:
            time_remaining = f"{remaining_seconds} seconds"
        elif remaining_seconds < 3600:
            time_remaining = f"{remaining_seconds // 60} minutes and {remaining_seconds % 60} seconds"
        else:
            hours = remaining_seconds // 3600
            minutes = (remaining_seconds % 3600) // 60
            time_remaining = f"{hours} hours and {minutes} minutes"
    else:
        time_remaining = "Account should be unlocked now"
    
    # Log the lockout event
    logger.warning(f"Account lockout triggered for IP {client_ip}, remaining time: {time_remaining}")
    
    # Check if this is an AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'error': 'Account temporarily locked',
            'message': f'Too many failed login attempts. Try again in {time_remaining}.',
            'remaining_seconds': remaining_seconds,
            'locked_until': time_remaining,
            'code': 423
        }, status=423)
    
    # For regular requests, render a lockout page
    context = {
        'lockout_message': f'Your account has been temporarily locked due to too many failed login attempts.',
        'time_remaining': time_remaining,
        'remaining_seconds': remaining_seconds,
        'contact_admin': True
    }
    
    return render(request, 'security/lockout.html', context)


def get_client_ip(request):
    """Get real client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
    return ip


def log_security_event(event_type, request, details=None):
    """
    Log security events with consistent formatting
    """
    client_ip = get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
    
    log_message = f"SECURITY_EVENT: {event_type} from {client_ip}"
    if details:
        log_message += f" - {details}"
    
    # Log to security logger
    security_logger = logging.getLogger('security')
    security_logger.warning(log_message)
    
    # Store in cache for monitoring
    event_key = f"security_events:{timezone.now().strftime('%Y-%m-%d')}"
    events = cache.get(event_key, [])
    
    event_data = {
        'timestamp': timezone.now().isoformat(),
        'type': event_type,
        'ip': client_ip,
        'user_agent': user_agent,
        'details': details,
        'path': request.path
    }
    
    events.append(event_data)
    # Keep only last 1000 events per day
    events = events[-1000:]
    
    cache.set(event_key, events, 86400)  # 24 hours


def handle_suspicious_activity(request, activity_type, details=None):
    """
    Handle suspicious activity detection
    """
    client_ip = get_client_ip(request)
    
    # Log the event
    log_security_event(f'suspicious_{activity_type}', request, details)
    
    # Increment suspicion score
    suspicion_key = f"suspicion:{client_ip}"
    current_score = cache.get(suspicion_key, 0)
    
    # Different activity types have different severity scores
    score_increment = {
        'injection_attempt': 10,
        'scanner_detected': 8,
        'rate_limit_exceeded': 5,
        'invalid_request': 3,
        'unusual_pattern': 2
    }.get(activity_type, 1)
    
    new_score = current_score + score_increment
    cache.set(suspicion_key, new_score, 3600)  # 1 hour
    
    # Auto-block if score exceeds threshold
    if new_score >= 20:
        block_ip_temporarily(client_ip, duration=1800)  # 30 minutes
        log_security_event('auto_ip_block', request, f'Suspicion score: {new_score}')


def block_ip_temporarily(ip, duration=3600):
    """
    Temporarily block an IP address
    """
    block_key = f"blocked_ip:{ip}"
    cache.set(block_key, {
        'blocked_at': timezone.now().isoformat(),
        'duration': duration,
        'reason': 'Suspicious activity detected'
    }, duration)
    
    logger.error(f"IP {ip} temporarily blocked for {duration} seconds")


def is_ip_blocked(ip):
    """
    Check if an IP address is currently blocked
    """
    block_key = f"blocked_ip:{ip}"
    return cache.get(block_key) is not None


def get_security_stats():
    """
    Get security statistics for monitoring
    """
    today = timezone.now().strftime('%Y-%m-%d')
    event_key = f"security_events:{today}"
    events = cache.get(event_key, [])
    
    # Count events by type
    event_counts = {}
    for event in events:
        event_type = event['type']
        event_counts[event_type] = event_counts.get(event_type, 0) + 1
    
    # Get blocked IPs count
    blocked_ips = []
    # This is a simplified check - in production, you might want to store blocked IPs separately
    
    return {
        'total_events': len(events),
        'event_types': event_counts,
        'blocked_ips_count': len(blocked_ips),
        'last_updated': timezone.now().isoformat()
    }


def clear_ip_block(ip):
    """
    Manually clear an IP block (for admin use)
    """
    block_key = f"blocked_ip:{ip}"
    cache.delete(block_key)
    
    suspicion_key = f"suspicion:{ip}"
    cache.delete(suspicion_key)
    
    logger.info(f"IP block cleared for {ip}")


def whitelist_ip(ip, duration=86400):
    """
    Temporarily whitelist an IP address
    """
    whitelist_key = f"whitelisted_ip:{ip}"
    cache.set(whitelist_key, {
        'whitelisted_at': timezone.now().isoformat(),
        'duration': duration
    }, duration)
    
    # Also clear any existing blocks
    clear_ip_block(ip)
    
    logger.info(f"IP {ip} whitelisted for {duration} seconds")
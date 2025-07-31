"""
Advanced Security Middleware for PISOWifi System
Provides comprehensive protection against various attack vectors
"""

import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import SuspiciousOperation
import re

logger = logging.getLogger('security')


class SecurityConfig:
    """Configuration for security middleware"""
    
    # Rate limiting settings (more reasonable limits)
    RATE_LIMITS = {
        'admin_login': {'requests': 10, 'window': 300},  # 10 attempts per 5 minutes
        'api_general': {'requests': 200, 'window': 60},  # 200 requests per minute
        'portal_access': {'requests': 60, 'window': 60},  # 60 requests per minute
        'voucher_redeem': {'requests': 20, 'window': 300},  # 20 attempts per 5 minutes
        'payment': {'requests': 30, 'window': 300},  # 30 payment attempts per 5 minutes
    }
    
    # Suspicious patterns
    SUSPICIOUS_PATTERNS = [
        r'[\'"<>]',  # Potential XSS/SQL injection
        r'(union|select|drop|insert|update|delete)\s',  # SQL injection keywords
        r'<script|javascript:|vbscript:',  # XSS patterns
        r'\.\.\/|\.\.\\',  # Path traversal
        r'(cmd|exec|system|eval)\s*\(',  # Code injection
    ]
    
    # Blocked user agents (bots, scanners)
    BLOCKED_USER_AGENTS = [
        r'sqlmap', r'nikto', r'nessus', r'openvas',
        r'w3af', r'skipfish', r'gobuster', r'dirb',
        r'masscan', r'nmap', r'zmap'
    ]
    
    # Maximum request size (10MB)
    MAX_REQUEST_SIZE = 10 * 1024 * 1024


class AdvancedSecurityMiddleware:
    """
    Advanced security middleware providing:
    - Rate limiting
    - Suspicious activity detection
    - Request filtering
    - Attack pattern recognition
    - Automatic IP blocking
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.config = SecurityConfig()
        
    def __call__(self, request):
        # Pre-request security checks
        security_response = self.process_request(request)
        if security_response:
            return security_response
            
        response = self.get_response(request)
        
        # Post-request security processing
        self.process_response(request, response)
        
        return response
    
    def process_request(self, request):
        """Process incoming request for security threats"""
        client_ip = self.get_client_ip(request)
        
        # Check if IP is temporarily blocked
        if self.is_ip_blocked(client_ip):
            block_info = cache.get(f"blocked_ip:{client_ip}", {})
            if isinstance(block_info, dict) and 'until' in block_info:
                blocked_until = datetime.fromisoformat(block_info['until'])
                remaining_seconds = (blocked_until - timezone.now()).total_seconds()
                if remaining_seconds > 0:
                    if remaining_seconds < 60:
                        remaining_str = f"{int(remaining_seconds)} seconds"
                    elif remaining_seconds < 3600:
                        remaining_str = f"{int(remaining_seconds // 60)} minutes"
                    else:
                        remaining_str = f"{int(remaining_seconds // 3600)} hours"
                    message = f"IP temporarily blocked. Try again in {remaining_str}."
                else:
                    message = "IP blocked due to security violations"
            else:
                message = "IP blocked due to security violations"
            
            logger.warning(f"Blocked IP attempted access: {client_ip}")
            return self.security_response(message, 429)  # Use 429 (Too Many Requests) instead of 403
        
        # Check request size
        if self.is_request_too_large(request):
            logger.warning(f"Oversized request from {client_ip}")
            return self.security_response("Request too large", 413)
        
        # Check for malicious user agents
        if self.is_malicious_user_agent(request):
            logger.warning(f"Malicious user agent from {client_ip}: {request.META.get('HTTP_USER_AGENT', '')}")
            self.record_violation(client_ip, 'malicious_user_agent')
            return self.security_response("Access denied", 403)
        
        # Check for suspicious patterns in request
        if self.has_suspicious_patterns(request):
            logger.warning(f"Suspicious request patterns from {client_ip}")
            self.record_violation(client_ip, 'suspicious_patterns')
            return self.security_response("Malicious request detected", 400)
        
        # Apply rate limiting
        rate_limit_response = self.apply_rate_limiting(request, client_ip)
        if rate_limit_response:
            return rate_limit_response
        
        return None
    
    def process_response(self, request, response):
        """Process response for additional security measures"""
        client_ip = self.get_client_ip(request)
        
        # Log failed authentication attempts
        if (response.status_code in [401, 403] and 
            '/admin/' in request.path):
            self.record_violation(client_ip, 'auth_failure')
            logger.warning(f"Authentication failure from {client_ip} to {request.path}")
    
    def get_client_ip(self, request):
        """Get real client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
        return ip
    
    def is_ip_blocked(self, ip):
        """Check if IP is in blocked list"""
        blocked_key = f"blocked_ip:{ip}"
        block_info = cache.get(blocked_key, None)
        
        if block_info and isinstance(block_info, dict):
            # Check if still blocked
            blocked_until = datetime.fromisoformat(block_info['until'])
            if timezone.now() < blocked_until:
                return True
            else:
                # Block expired, clear it
                cache.delete(blocked_key)
                return False
        elif block_info:  # Old format, treat as boolean
            return bool(block_info)
        
        return False
    
    def is_request_too_large(self, request):
        """Check if request exceeds size limits"""
        content_length = request.META.get('CONTENT_LENGTH')
        if content_length:
            try:
                return int(content_length) > self.config.MAX_REQUEST_SIZE
            except ValueError:
                return False
        return False
    
    def is_malicious_user_agent(self, request):
        """Check for known malicious user agents"""
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        if not user_agent:
            return True  # Block requests without user agent
        
        for pattern in self.config.BLOCKED_USER_AGENTS:
            if re.search(pattern, user_agent, re.IGNORECASE):
                return True
        return False
    
    def has_suspicious_patterns(self, request):
        """Check for suspicious patterns in request"""
        # Check URL path
        path = request.path.lower()
        
        # Check query parameters
        query_string = request.META.get('QUERY_STRING', '').lower()
        
        # Check POST data (if available)
        post_data = ''
        if hasattr(request, 'body'):
            try:
                post_data = request.body.decode('utf-8', errors='ignore').lower()
            except:
                pass
        
        # Combine all request data
        request_data = f"{path} {query_string} {post_data}"
        
        # Check against suspicious patterns
        for pattern in self.config.SUSPICIOUS_PATTERNS:
            if re.search(pattern, request_data, re.IGNORECASE):
                return True
        
        return False
    
    def apply_rate_limiting(self, request, client_ip):
        """Apply rate limiting based on request type"""
        # Determine rate limit type
        limit_type = self.get_rate_limit_type(request)
        if not limit_type:
            return None
        
        config = self.config.RATE_LIMITS.get(limit_type)
        if not config:
            return None
        
        # Check rate limit
        key = f"rate_limit:{limit_type}:{client_ip}"
        current_requests = cache.get(key, 0)
        
        if current_requests >= config['requests']:
            logger.warning(f"Rate limit exceeded for {client_ip} on {limit_type}")
            self.record_violation(client_ip, 'rate_limit')
            return self.rate_limit_response(config['window'])
        
        # Increment counter
        cache.set(key, current_requests + 1, config['window'])
        return None
    
    def get_rate_limit_type(self, request):
        """Determine the type of rate limiting to apply"""
        path = request.path.lower()
        
        if '/admin/login' in path:
            return 'admin_login'
        elif '/admin/' in path:
            return 'api_general'
        elif '/app/portal' in path:
            return 'portal_access'
        elif '/app/redeem' in path:
            return 'voucher_redeem'
        elif '/app/pay' in path or '/app/browse' in path:
            return 'payment'
        elif '/app/' in path:
            return 'api_general'
        
        return None
    
    def get_progressive_block_duration(self, ip):
        """Calculate progressive block duration based on violation history"""
        block_history_key = f"block_history:{ip}"
        block_count = cache.get(block_history_key, 0)
        
        # Progressive durations: 1min, 3min, 5min, 10min, 30min, 1hr, 2hr, 24hr
        durations = [60, 180, 300, 600, 1800, 3600, 7200, 86400]
        
        # Get the appropriate duration based on block count
        duration_index = min(block_count, len(durations) - 1)
        duration = durations[duration_index]
        
        # Increment block count for next time
        cache.set(block_history_key, block_count + 1, 86400 * 7)  # Remember for 7 days
        
        return duration
    
    def record_violation(self, ip, violation_type):
        """Record security violation for IP"""
        violation_key = f"violations:{ip}"
        violations = cache.get(violation_key, [])
        
        violations.append({
            'type': violation_type,
            'timestamp': timezone.now().isoformat()
        })
        
        # Keep only last 100 violations
        violations = violations[-100:]
        cache.set(violation_key, violations, 86400)  # 24 hours
        
        # Check violations in last 10 minutes (more reasonable than 1 hour)
        recent_violations = [
            v for v in violations 
            if (timezone.now() - datetime.fromisoformat(v['timestamp'])).seconds < 600
        ]
        
        # Block after 5 violations in 10 minutes (more reasonable than 10 in 1 hour)
        if len(recent_violations) >= 5:
            duration = self.get_progressive_block_duration(ip)
            self.block_ip(ip, duration=duration)
    
    def block_ip(self, ip, duration=60):
        """Block an IP address with progressive duration"""
        blocked_key = f"blocked_ip:{ip}"
        blocked_until = timezone.now() + timedelta(seconds=duration)
        
        cache.set(blocked_key, {
            'blocked': True,
            'until': blocked_until.isoformat(),
            'duration': duration
        }, duration)
        
        # Human-readable duration
        if duration < 60:
            duration_str = f"{duration} seconds"
        elif duration < 3600:
            duration_str = f"{duration // 60} minutes"
        else:
            duration_str = f"{duration // 3600} hours"
            
        logger.warning(f"IP {ip} blocked for {duration_str} due to security violations")
        
        # Also log to security logger
        security_logger = logging.getLogger('security')
        security_logger.warning(f"SECURITY_BLOCK: IP {ip} blocked for {duration}s")
    
    def security_response(self, message, status_code):
        """Return a security response"""
        return JsonResponse({
            'error': 'Security violation detected',
            'message': message,
            'code': status_code
        }, status=status_code)
    
    def rate_limit_response(self, retry_after):
        """Return rate limit exceeded response"""
        response = HttpResponse(
            "Rate limit exceeded. Please try again later.",
            status=429
        )
        response['Retry-After'] = str(retry_after)
        return response


class RequestSizeMiddleware:
    """Middleware to limit request body size"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.max_size = getattr(settings, 'MAX_REQUEST_SIZE', 10 * 1024 * 1024)  # 10MB
    
    def __call__(self, request):
        content_length = request.META.get('CONTENT_LENGTH')
        if content_length and int(content_length) > self.max_size:
            logger.warning(f"Request size limit exceeded: {content_length} bytes")
            return JsonResponse({
                'error': 'Request too large',
                'max_size': self.max_size
            }, status=413)
        
        return self.get_response(request)


class LoginRateLimitMiddleware:
    """Simple progressive rate limiting for login attempts"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Only apply to admin login attempts
        if (request.path == '/admin/login/' and request.method == 'POST'):
            client_ip = self.get_client_ip(request)
            
            # Check if IP is currently locked out
            lockout_info = self.get_lockout_info(client_ip)
            if lockout_info:
                return self.lockout_response(request, lockout_info)
        
        response = self.get_response(request)
        
        # Check for failed login after response
        if (request.path == '/admin/login/' and request.method == 'POST' and 
            response.status_code == 200 and b'errorlist' in response.content):
            # This is a failed login attempt
            self.record_failed_attempt(self.get_client_ip(request))
        elif (request.path == '/admin/login/' and request.method == 'POST' and 
              response.status_code == 302):
            # Successful login, clear attempts
            self.clear_failed_attempts(self.get_client_ip(request))
        
        return response
    
    def get_client_ip(self, request):
        """Get real client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
        return ip
    
    def get_lockout_info(self, ip):
        """Check if IP is currently locked out"""
        lockout_key = f"login_lockout:{ip}"
        lockout_data = cache.get(lockout_key)
        
        if lockout_data:
            locked_until = datetime.fromisoformat(lockout_data['until'])
            if timezone.now() < locked_until:
                remaining_seconds = (locked_until - timezone.now()).total_seconds()
                lockout_data['remaining_seconds'] = max(0, int(remaining_seconds))
                return lockout_data
            else:
                # Lockout expired, clear it
                cache.delete(lockout_key)
        
        return None
    
    def record_failed_attempt(self, ip):
        """Record a failed login attempt and apply progressive lockout"""
        attempts_key = f"login_attempts:{ip}"
        attempts = cache.get(attempts_key, 0)
        attempts += 1
        
        logger.warning(f"Failed login attempt #{attempts} from IP {ip}")
        
        if attempts >= 5:  # After 5 failed attempts, start locking
            lockout_count = attempts - 4  # 1st lockout = 1, 2nd = 2, etc.
            lockout_minutes = lockout_count  # Progressive: 1min, 2min, 3min, etc.
            lockout_seconds = lockout_minutes * 60
            
            locked_until = timezone.now() + timedelta(seconds=lockout_seconds)
            
            lockout_data = {
                'until': locked_until.isoformat(),
                'duration_minutes': lockout_minutes,
                'attempt_count': attempts,
                'remaining_seconds': lockout_seconds
            }
            
            # Store lockout info
            lockout_key = f"login_lockout:{ip}"
            cache.set(lockout_key, lockout_data, lockout_seconds)
            
            logger.error(f"IP {ip} locked out for {lockout_minutes} minutes after {attempts} failed attempts")
        
        # Store attempt count for 30 minutes
        cache.set(attempts_key, attempts, 1800)
    
    def clear_failed_attempts(self, ip):
        """Clear failed attempts after successful login"""
        attempts_key = f"login_attempts:{ip}"
        lockout_key = f"login_lockout:{ip}"
        cache.delete(attempts_key)
        cache.delete(lockout_key)
        logger.info(f"Cleared failed attempts for IP {ip} after successful login")
    
    def lockout_response(self, request, lockout_info):
        """Return lockout response with countdown"""
        remaining_seconds = lockout_info['remaining_seconds']
        
        if remaining_seconds < 60:
            time_str = f"{remaining_seconds} seconds"
        else:
            minutes = remaining_seconds // 60
            seconds = remaining_seconds % 60
            time_str = f"{minutes} minutes and {seconds} seconds"
        
        # For AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'error': 'Login temporarily locked',
                'message': f'Too many failed attempts. Try again in {time_str}.',
                'remaining_seconds': remaining_seconds,
                'attempt_count': lockout_info['attempt_count']
            }, status=429)
        
        # For regular requests, render lockout page
        from django.shortcuts import render
        context = {
            'lockout_message': 'Your login has been temporarily locked due to too many failed attempts.',
            'time_remaining': time_str,
            'remaining_seconds': remaining_seconds,
            'attempt_count': lockout_info['attempt_count']
        }
        
        from django.template.response import TemplateResponse
        return TemplateResponse(request, 'security/lockout.html', context)


class IPWhitelistMiddleware:
    """Middleware to allow only whitelisted IPs for admin access"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.admin_whitelist = getattr(settings, 'ADMIN_IP_WHITELIST', [])
    
    def __call__(self, request):
        if request.path.startswith('/admin/') and self.admin_whitelist:
            client_ip = self.get_client_ip(request)
            if client_ip not in self.admin_whitelist:
                logger.warning(f"Unauthorized admin access attempt from {client_ip}")
                return JsonResponse({
                    'error': 'Access denied',
                    'message': 'Admin access not allowed from this IP'
                }, status=403)
        
        return self.get_response(request)
    
    def get_client_ip(self, request):
        """Get real client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
        return ip
"""
Custom login views with progressive rate limiting
"""

import logging
from datetime import datetime, timedelta
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import authenticate, login
from django.contrib.auth.views import LoginView
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.contrib import messages

logger = logging.getLogger('security')


class CustomAdminLoginView(LoginView):
    """Custom admin login view with progressive rate limiting"""
    
    template_name = 'admin/login.html'
    
    def get_client_ip(self):
        """Get real client IP address"""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = self.request.META.get('REMOTE_ADDR', '0.0.0.0')
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
                # Reset attempts after lockout expires
                attempts_key = f"login_attempts:{ip}"
                cache.delete(attempts_key)
        
        return None
    
    def get_attempt_info(self, ip):
        """Get current attempt information"""
        attempts_key = f"login_attempts:{ip}"
        attempts = cache.get(attempts_key, 0)
        return {
            'attempts': attempts,
            'remaining': max(0, 5 - attempts)
        }
    
    def record_failed_attempt(self, ip):
        """Record a failed login attempt and apply progressive lockout"""
        attempts_key = f"login_attempts:{ip}"
        attempts = cache.get(attempts_key, 0)
        attempts += 1
        
        logger.warning(f"Failed login attempt #{attempts} from IP {ip}")
        
        if attempts >= 5:  # After 5 failed attempts, start locking
            lockout_count_key = f"lockout_count:{ip}"
            lockout_count = cache.get(lockout_count_key, 0) + 1
            
            # Progressive lockout times: 1min, 2min, 3min, 4min, 5min, 10min, 15min, 30min, 1hr
            lockout_minutes = [1, 2, 3, 4, 5, 10, 15, 30, 60]
            lockout_index = min(lockout_count - 1, len(lockout_minutes) - 1)
            lockout_duration_minutes = lockout_minutes[lockout_index]
            lockout_seconds = lockout_duration_minutes * 60
            
            locked_until = timezone.now() + timedelta(seconds=lockout_seconds)
            
            lockout_data = {
                'until': locked_until.isoformat(),
                'duration_minutes': lockout_duration_minutes,
                'attempt_count': attempts,
                'lockout_number': lockout_count,
                'remaining_seconds': lockout_seconds
            }
            
            # Store lockout info
            lockout_key = f"login_lockout:{ip}"
            cache.set(lockout_key, lockout_data, lockout_seconds)
            cache.set(lockout_count_key, lockout_count, 86400)  # Remember lockout count for 24 hours
            
            # Clear attempts (they'll reset after lockout)
            cache.delete(attempts_key)
            
            logger.error(f"IP {ip} locked out for {lockout_duration_minutes} minutes after {attempts} failed attempts (lockout #{lockout_count})")
            return lockout_data
        else:
            # Store attempt count for 30 minutes
            cache.set(attempts_key, attempts, 1800)
            return None
    
    def clear_failed_attempts(self, ip):
        """Clear failed attempts after successful login"""
        attempts_key = f"login_attempts:{ip}"
        lockout_key = f"login_lockout:{ip}"
        cache.delete(attempts_key)
        cache.delete(lockout_key)
        logger.info(f"Cleared failed attempts for IP {ip} after successful login")
    
    def get(self, request, *args, **kwargs):
        """Handle GET requests - show login form with current status"""
        client_ip = self.get_client_ip()
        
        # Check if locked out
        lockout_info = self.get_lockout_info(client_ip)
        if lockout_info:
            return self.render_lockout_page(lockout_info)
        
        # Get attempt information
        attempt_info = self.get_attempt_info(client_ip)
        
        # Add attempt info to context
        context = self.get_context_data()
        context.update({
            'attempts_made': attempt_info['attempts'],
            'attempts_remaining': attempt_info['remaining'],
            'show_attempt_warning': attempt_info['attempts'] > 0,
        })
        
        return self.render_to_response(context)
    
    def post(self, request, *args, **kwargs):
        """Handle POST requests - process login attempt"""
        client_ip = self.get_client_ip()
        
        # Check if locked out
        lockout_info = self.get_lockout_info(client_ip)
        if lockout_info:
            return self.render_lockout_page(lockout_info)
        
        # Get credentials
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        
        if username and password:
            user = authenticate(request, username=username, password=password)
            if user is not None and user.is_active and user.is_staff:
                # Successful login
                login(request, user)
                self.clear_failed_attempts(client_ip)
                logger.info(f"Successful admin login for user {username} from IP {client_ip}")
                return redirect(self.get_success_url())
            else:
                # Failed login
                lockout_data = self.record_failed_attempt(client_ip)
                if lockout_data:
                    # Locked out after this attempt
                    return self.render_lockout_page(lockout_data)
                else:
                    # Still have attempts left
                    attempt_info = self.get_attempt_info(client_ip)
                    context = self.get_context_data()
                    context.update({
                        'error_message': 'Password incorrect',
                        'attempts_made': attempt_info['attempts'],
                        'attempts_remaining': attempt_info['remaining'],
                        'show_attempt_warning': True,
                        'form_errors': True
                    })
                    return self.render_to_response(context)
        
        # Invalid form data
        context = self.get_context_data()
        context['error_message'] = 'Please enter both username and password'
        return self.render_to_response(context)
    
    def render_lockout_page(self, lockout_info):
        """Render the lockout page with countdown"""
        remaining_seconds = lockout_info['remaining_seconds']
        
        if remaining_seconds < 60:
            time_str = f"{remaining_seconds} seconds"
        else:
            minutes = remaining_seconds // 60
            seconds = remaining_seconds % 60
            if seconds > 0:
                time_str = f"{minutes} minutes and {seconds} seconds"
            else:
                time_str = f"{minutes} minutes"
        
        context = {
            'lockout_message': 'Login temporarily disabled due to too many failed attempts.',
            'time_remaining': time_str,
            'remaining_seconds': remaining_seconds,
            'attempt_count': lockout_info['attempt_count'],
            'lockout_number': lockout_info['lockout_number'],
            'duration_minutes': lockout_info['duration_minutes']
        }
        
        return render(self.request, 'admin/login_lockout.html', context)


@never_cache
@csrf_protect
def admin_login_view(request):
    """Function-based view wrapper for the custom login"""
    view = CustomAdminLoginView.as_view()
    return view(request)
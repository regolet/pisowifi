"""
Enhanced admin interface with 2FA and security features
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.contrib import messages
from django_otp.admin import OTPAdminSite
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
import qrcode
import io
import base64
from django.conf import settings


class OTPRequiredAdminSite(OTPAdminSite):
    """
    Admin site that requires 2FA for access
    """
    site_header = 'PISOWifi Secure Admin'
    site_title = 'PISOWifi Admin'
    index_title = 'Secure Administration Dashboard'


class UserSecurityAdmin(BaseUserAdmin):
    """
    Enhanced User admin with 2FA management
    """
    list_display = BaseUserAdmin.list_display + ('totp_enabled', 'backup_tokens', 'last_login_ip', 'security_actions')
    list_filter = BaseUserAdmin.list_filter + ('last_login',)
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Security', {
            'fields': ('last_login_ip', 'failed_login_attempts', 'account_locked_until'),
            'classes': ('collapse',)
        }),
    )
    
    def totp_enabled(self, obj):
        """Check if user has TOTP enabled"""
        devices = TOTPDevice.objects.filter(user=obj, confirmed=True)
        if devices.exists():
            return format_html('<span style="color: green;">✓ Enabled</span>')
        return format_html('<span style="color: red;">✗ Disabled</span>')
    
    totp_enabled.short_description = '2FA Status'
    
    def backup_tokens(self, obj):
        """Show backup token count"""
        static_device = StaticDevice.objects.filter(user=obj).first()
        if static_device:
            token_count = StaticToken.objects.filter(device=static_device).count()
            return f"{token_count} tokens"
        return "No backup tokens"
    
    backup_tokens.short_description = 'Backup Tokens'
    
    def last_login_ip(self, obj):
        """Show last login IP (would need to be stored in user profile)"""
        # This would require extending the User model or using a profile
        return "N/A"
    
    last_login_ip.short_description = 'Last Login IP'
    
    def security_actions(self, obj):
        """Security management actions"""
        actions = []
        
        # 2FA Setup link
        setup_url = reverse('admin:setup_2fa', args=[obj.pk])
        actions.append(f'<a href="{setup_url}" class="button">Setup 2FA</a>')
        
        # Reset 2FA link
        reset_url = reverse('admin:reset_2fa', args=[obj.pk])
        actions.append(f'<a href="{reset_url}" class="button">Reset 2FA</a>')
        
        # Generate backup tokens
        backup_url = reverse('admin:generate_backup_tokens', args=[obj.pk])
        actions.append(f'<a href="{backup_url}" class="button">Backup Tokens</a>')
        
        return format_html(' | '.join(actions))
    
    security_actions.short_description = 'Security Actions'
    security_actions.allow_tags = True


# Custom admin site with 2FA
admin_site = OTPRequiredAdminSite()

# Register models with the secure admin site
admin_site.register(User, UserSecurityAdmin)


def setup_2fa_view(request, user_id):
    """
    View to help users set up 2FA
    """
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        messages.error(request, "User not found.")
        return HttpResponseRedirect(reverse('admin:auth_user_changelist'))
    
    # Create or get TOTP device
    device, created = TOTPDevice.objects.get_or_create(
        user=user,
        name='default',
        defaults={'confirmed': False}
    )
    
    if created or not device.confirmed:
        # Generate QR code for setup
        qr_url = device.config_url
        
        # Create QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_url)
        qr.make(fit=True)
        
        # Convert to base64 image
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        qr_code_data = base64.b64encode(buffer.getvalue()).decode()
        
        context = {
            'user': user,
            'qr_code_data': qr_code_data,
            'secret_key': device.bin_key.hex(),
            'qr_url': qr_url,
            'issuer': getattr(settings, 'OTP_TOTP_ISSUER', 'PISOWifi'),
        }
        
        # This would render a template for 2FA setup
        messages.info(request, f"2FA setup initiated for {user.username}. Please scan the QR code with your authenticator app.")
    else:
        messages.info(request, f"2FA is already enabled for {user.username}.")
    
    return HttpResponseRedirect(reverse('admin:auth_user_change', args=[user_id]))


def reset_2fa_view(request, user_id):
    """
    View to reset user's 2FA
    """
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        messages.error(request, "User not found.")
        return HttpResponseRedirect(reverse('admin:auth_user_changelist'))
    
    # Delete all TOTP devices
    TOTPDevice.objects.filter(user=user).delete()
    
    # Delete all static devices and tokens
    StaticDevice.objects.filter(user=user).delete()
    
    messages.success(request, f"2FA has been reset for {user.username}. They will need to set it up again.")
    
    return HttpResponseRedirect(reverse('admin:auth_user_change', args=[user_id]))


def generate_backup_tokens_view(request, user_id):
    """
    Generate backup tokens for user
    """
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        messages.error(request, "User not found.")
        return HttpResponseRedirect(reverse('admin:auth_user_changelist'))
    
    # Get or create static device
    device, created = StaticDevice.objects.get_or_create(
        user=user,
        name='backup'
    )
    
    # Clear existing tokens
    StaticToken.objects.filter(device=device).delete()
    
    # Generate 10 new backup tokens
    tokens = []
    for i in range(10):
        token = StaticToken.random_token()
        StaticToken.objects.create(device=device, token=token)
        tokens.append(token)
    
    # In a real implementation, you'd want to show these in a secure way
    messages.success(request, f"Generated {len(tokens)} backup tokens for {user.username}.")
    
    return HttpResponseRedirect(reverse('admin:auth_user_change', args=[user_id]))
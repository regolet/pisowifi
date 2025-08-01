"""
Security module admin interface
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html


class UserSecurityAdmin(BaseUserAdmin):
    """
    Enhanced User admin with security management
    """
    list_display = BaseUserAdmin.list_display + ('last_login_ip', 'account_status')
    list_filter = BaseUserAdmin.list_filter + ('last_login',)
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Security', {
            'fields': ('last_login_ip', 'failed_login_attempts', 'account_locked_until'),
            'classes': ('collapse',)
        }),
    )
    
    def last_login_ip(self, obj):
        """Show last login IP (would need to be stored in user profile)"""
        # This would require extending the User model or using a profile
        return "N/A"
    
    last_login_ip.short_description = 'Last Login IP'
    
    def account_status(self, obj):
        """Show account status"""
        if obj.is_active:
            return format_html('<span style="color: green;">✓ Active</span>')
        return format_html('<span style="color: red;">✗ Inactive</span>')
    
    account_status.short_description = 'Status'


# Register with default admin site
admin.site.unregister(User)
admin.site.register(User, UserSecurityAdmin)
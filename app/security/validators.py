"""
Custom password validators for enhanced security
"""

import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class ComplexPasswordValidator:
    """
    Validate that the password contains a mix of character types
    """
    
    def validate(self, password, user=None):
        """
        Validate that the password meets complexity requirements
        """
        errors = []
        
        # Check for at least one uppercase letter
        if not re.search(r'[A-Z]', password):
            errors.append(_('Password must contain at least one uppercase letter.'))
        
        # Check for at least one lowercase letter
        if not re.search(r'[a-z]', password):
            errors.append(_('Password must contain at least one lowercase letter.'))
        
        # Check for at least one digit
        if not re.search(r'\d', password):
            errors.append(_('Password must contain at least one digit.'))
        
        # Check for at least one special character
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append(_('Password must contain at least one special character (!@#$%^&*(),.?":{}|<>).'))
        
        # Check for common patterns
        if re.search(r'(.)\1{2,}', password):
            errors.append(_('Password cannot contain three or more consecutive identical characters.'))
        
        # Check for sequential characters
        if self.has_sequential_chars(password):
            errors.append(_('Password cannot contain sequential characters (abc, 123, etc.).'))
        
        if errors:
            raise ValidationError(errors)
    
    def has_sequential_chars(self, password):
        """
        Check for sequential characters in password
        """
        password = password.lower()
        
        # Check for sequential letters
        for i in range(len(password) - 2):
            if (ord(password[i+1]) == ord(password[i]) + 1 and 
                ord(password[i+2]) == ord(password[i]) + 2):
                return True
        
        # Check for sequential numbers
        for i in range(len(password) - 2):
            try:
                if (int(password[i+1]) == int(password[i]) + 1 and 
                    int(password[i+2]) == int(password[i]) + 2):
                    return True
            except ValueError:
                continue
        
        return False
    
    def get_help_text(self):
        return _(
            "Your password must contain at least one uppercase letter, "
            "one lowercase letter, one digit, and one special character. "
            "It cannot contain three consecutive identical characters or "
            "sequential characters."
        )


class NoPersonalInfoValidator:
    """
    Validate that the password doesn't contain personal information
    """
    
    def validate(self, password, user=None):
        if user is None:
            return
        
        password_lower = password.lower()
        
        # Check username
        if user.username and user.username.lower() in password_lower:
            raise ValidationError(
                _('Password cannot contain your username.'),
                code='password_contains_username',
            )
        
        # Check email parts
        if user.email:
            email_parts = user.email.lower().split('@')
            for part in email_parts:
                if len(part) > 3 and part in password_lower:
                    raise ValidationError(
                        _('Password cannot contain parts of your email address.'),
                        code='password_contains_email',
                    )
        
        # Check first/last name if available
        if hasattr(user, 'first_name') and user.first_name:
            if user.first_name.lower() in password_lower:
                raise ValidationError(
                    _('Password cannot contain your first name.'),
                    code='password_contains_first_name',
                )
        
        if hasattr(user, 'last_name') and user.last_name:
            if user.last_name.lower() in password_lower:
                raise ValidationError(
                    _('Password cannot contain your last name.'),
                    code='password_contains_last_name',
                )
    
    def get_help_text(self):
        return _(
            "Your password cannot contain your personal information "
            "(username, email, name)."
        )


class PasswordHistoryValidator:
    """
    Validate that the password hasn't been used recently
    (This would require storing password history - simplified version)
    """
    
    def __init__(self, history_count=5):
        self.history_count = history_count
    
    def validate(self, password, user=None):
        # In a full implementation, you would check against stored password hashes
        # For now, we'll just implement a basic check
        pass
    
    def get_help_text(self):
        return _(
            f"Your password cannot be one of your last {self.history_count} passwords."
        )


class NoCompromisedPasswordValidator:
    """
    Validate that the password is not in a known compromised password list
    (This is a simplified version - in production, you'd check against actual breach databases)
    """
    
    COMMON_COMPROMISED = [
        'password', '123456', '123456789', 'qwerty', 'abc123',
        'password123', 'admin', 'letmein', 'welcome', 'monkey',
        'dragon', 'master', 'shadow', 'passw0rd', 'football'
    ]
    
    def validate(self, password, user=None):
        if password.lower() in [pwd.lower() for pwd in self.COMMON_COMPROMISED]:
            raise ValidationError(
                _('This password has been found in data breaches and is not secure.'),
                code='password_compromised',
            )
    
    def get_help_text(self):
        return _(
            "Your password cannot be a commonly compromised password."
        )
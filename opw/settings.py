import os
from django.core.management.utils import get_random_secret_key

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
def get_env_variable(var_name, default=None):
    """Get environment variable or return default/raise exception"""
    try:
        return os.environ[var_name]
    except KeyError:
        if default is not None:
            return default
        error_msg = f"Set the {var_name} environment variable"
        raise Exception(error_msg)

# SECURITY WARNING: keep the secret key used in production secret!
# Generate new secret key if not provided
SECRET_KEY = get_env_variable('SECRET_KEY', get_random_secret_key())

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True  # Enabled for development to serve static files

# SECURITY: Only allow specific hosts
ALLOWED_HOSTS_STR = get_env_variable('ALLOWED_HOSTS', 'localhost,127.0.0.1,*')
ALLOWED_HOSTS = [host.strip() for host in ALLOWED_HOSTS_STR.split(',') if host.strip()]

# Development mode check
DEV_MODE = get_env_variable('DEV_MODE', 'False').lower() == 'true'


# Application definition

INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'app',
    'rest_framework',
]

# Authentication Backends
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',  # Default auth backend
]

MIDDLEWARE = [
    # 'django.middleware.security.SecurityMiddleware',  # Disabled to prevent HTTPS issues
    # 'app.security.middleware.AdvancedSecurityMiddleware',  # Our advanced security - DISABLED
    # 'app.security.middleware.RequestSizeMiddleware',  # Request size limiting - DISABLED
    # 'app.security.middleware.LoginRateLimitMiddleware',  # Simple login rate limiting - DISABLED
    'django.contrib.sessions.middleware.SessionMiddleware',
    'app.middleware.admin_session_middleware.AdminSessionPersistenceMiddleware',  # Prevent admin session expiration
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Security Headers
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# HTTPS/SSL Settings - DISABLED
# HTTP-only configuration to prevent HTTPS redirect issues
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Session Security
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 86400 * 30  # 30 days - extremely long timeout for admin operations
SESSION_SAVE_EVERY_REQUEST = True  # Save session on every request to prevent expiration during updates
SESSION_EXPIRE_AT_BROWSER_CLOSE = False  # Don't expire when browser closes to prevent interruptions
# Additional session settings for admin persistence
SESSION_ENGINE = 'django.contrib.sessions.backends.db'  # Use database backend for reliability
CSRF_COOKIE_HTTPONLY = True

ROOT_URLCONF = 'opw.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'app', 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'opw.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

JAZZMIN_SETTINGS = {
    # Site branding
    'site_title': 'OJO PISOWifi Admin',
    'site_header': 'OJO PISOWifi',
    'site_brand': 'OJO PISOWifi',
    'site_logo': None,
    'site_logo_classes': "img-circle elevation-3",
    'site_icon': 'fas fa-wifi',
    'welcome_sign': "Welcome to the Ultimate PISOWifi Management Dashboard",
    'copyright': 'OJO PISOWifi Management System',
    
    # Search model - disabled
    'search_model': [],
    
    # Top Menu
    'topmenu_links': [
        # Top menu items removed as requested
    ],
    
    # User menu on the top right
    'usermenu_links': [
        {'name': 'View Site', 'url': '/', 'new_window': True, 'icon': 'fas fa-external-link-alt'}
    ],
    
    # Side Menu
    'show_sidebar': True,
    'navigation_expanded': True,
    'hide_apps': [],
    'hide_models': ['app.UpdateSettings', 'app.PortalText', 'app.CoinSlot', 'app.CoinQueue', 'app.TrafficMonitor', 'app.ConnectionTracker', 'app.TTLFirewallRule', 'app.TrafficAnalysis', 'app.DeviceBehaviorProfile', 'app.NetworkIntelligence', 'app.Ledger'],
    
    # Custom menu grouping
    'custom_links': {
        'app': []
    },
    
    # Dashboard icon consistency
    'default_icon_parents': 'fas fa-chevron-circle-right',
    'default_icon_children': 'fas fa-circle',
    
    # User display settings
    'user_avatar': None,
    'show_ui_builder': False,
    'show_user_name': True,  # Show full name beside profile
    'show_user_info': True,  # Show user information in header
    'user_name_format': 'full',  # Show full name instead of username
    
    'order_with_respect_to': [
        'app', 
        'app.Clients',
        'app.SalesReport',
        'app.Rates',
        'app.Vouchers',
        'app.Settings',
        'app.Network',
        'app.Whitelist',
        'app.BlockedDevices',
        'app.PortalSettings',
        'app.Device',
        'app.CoinSlot',
        'app.CoinQueue',
        'app.Ledger',
        'app.SecuritySettings',
        'app.TrafficMonitor',
        'app.ConnectionTracker',
        'app.TTLFirewallRule',
        'app.DeviceFingerprint',
        'app.TrafficAnalysis',
        'app.DeviceBehaviorProfile',
        'app.AdaptiveQoSRule',
        'app.NetworkIntelligence',
        'app.SystemUpdate',
        'app.UpdateSettings'
    ],
    
    # Icons
    'icons': {
        # Authentication
        'auth': 'fas fa-users-cog',
        'auth.user': 'far fa-user',
        'auth.Group': 'fas fa-users',
        
        # Core PISOWifi Models
        'app': 'fas fa-wifi',  # Keep wifi solid for branding
        'app.Clients': 'fas fa-users',
        'app.Settings': 'fas fa-cog',
        'app.Device': 'fas fa-laptop',
        'app.Network': 'fas fa-network-wired',
        'app.Whitelist': 'far fa-check-circle',
        'app.Rates': 'fas fa-dollar-sign',
        'app.Vouchers': 'fas fa-ticket-alt',
        
        # Financial Models
        'app.CoinSlot': 'fas fa-coins',
        'app.CoinQueue': 'fas fa-list-ol',
        'app.Ledger': 'fas fa-book',
        'app.SalesReport': 'fas fa-chart-bar',
        
        # Security & Monitoring Models
        'app.SecuritySettings': 'fas fa-shield-alt',
        'app.TrafficMonitor': 'fas fa-eye',
        'app.BlockedDevices': 'fas fa-ban',
        'app.ConnectionTracker': 'fas fa-route',
        'app.TTLFirewallRule': 'fas fa-fire',
        'app.DeviceFingerprint': 'fas fa-fingerprint',
        'app.TrafficAnalysis': 'fas fa-chart-area',
        'app.DeviceBehaviorProfile': 'fas fa-user-shield',
        'app.AdaptiveQoSRule': 'fas fa-tachometer-alt',
        'app.NetworkIntelligence': 'fas fa-brain',
        
        # System Update Models
        'app.SystemUpdate': 'fas fa-sync-alt',
        'app.UpdateSettings': 'fas fa-tools',
        
        # Backup & VLAN Models
        'app.BackupSettings': 'fas fa-archive',
        'app.DatabaseBackup': 'fas fa-hdd',
        'app.VLANSettings': 'fas fa-sitemap',
        
        # ZeroTier Remote Monitoring
        'app.ZeroTierSettings': 'fas fa-satellite-dish',
        
        # Port Prioritization/QoS
        'app.PortPrioritization': 'fas fa-sort-amount-up',
        
        # Portal Management
        'app.PortalSettings': 'fas fa-desktop',
        'app.PortalText': 'fas fa-align-left',
    },
    
    # Custom CSS and JS
    'custom_css': 'css/dashboard-enhanced.css',
    'custom_js': None,
    
    # UI Tweaks
    
    # Form layouts
    'changeform_format': 'horizontal_tabs',
    'changeform_format_overrides': {
        'auth.user': 'collapsible', 
        'auth.group': 'vertical_tabs',
        'app.settings': 'horizontal_tabs',
        'app.securitysettings': 'horizontal_tabs'
    },
    
    # Related modal and dashboard enhancements
    'related_modal_active': False,
    
    # Language chooser
    'language_chooser': False,
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": True,
    "footer_small_text": True,
    "body_small_text": True,
    "brand_small_text": True,
    "brand_colour": "navbar-primary",
    "accent": "accent-primary",
    "navbar": "navbar-primary navbar-dark",
    "no_navbar_border": False,
    "navbar_fixed": False,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": False,
    "sidebar": "sidebar-dark-primary",
    "sidebar_nav_small_text": True,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": False,
    "sidebar_nav_compact_style": True,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "default",
    "dark_mode_theme": None,
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success"
    },
    "actions_sticky_top": False
}

REST_FRAMEWORK = {
    # Use Django's standard `django.contrib.auth` permissions,
    # or allow read-only access for unauthenticated users.
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ]
}

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Shanghai'

USE_I18N = True

USE_L10N = True

USE_TZ = True

STATIC_URL = '/static/'

# In development, serve files directly from app directories
if DEBUG or DEV_MODE:
    STATICFILES_DIRS = [
        os.path.join(BASE_DIR, "app/static/"),
    ]
else:
    # In production, use collected static files
    STATIC_ROOT = os.path.join(BASE_DIR, "static/")

MEDIA_ROOT = os.path.join(BASE_DIR, "media/")
MEDIA_URL = '/media/'

# Default primary key field type for Django 5.x
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Increase field limits for admin interfaces with many inline forms
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'pisowifi.log'),
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG' if DEBUG else 'WARNING',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'security': {
            'level': 'WARNING',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'security.log'),
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'app': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'security': {
            'handlers': ['security'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

# Create logs directory if it doesn't exist
import os
log_dir = os.path.join(BASE_DIR, 'logs')
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# ========================
# ADVANCED SECURITY SETTINGS
# ========================

# Django-Axes Configuration (Login Security) - DISABLED
# Using custom progressive rate limiting instead
AXES_ENABLED = False

# Django-OTP Configuration (Two-Factor Authentication)
OTP_TOTP_ISSUER = 'PISOWifi Management'
OTP_LOGIN_URL = '/admin/login/'

# Security Middleware Configuration
MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10MB
ADMIN_IP_WHITELIST = get_env_variable('ADMIN_IP_WHITELIST', '').split(',') if get_env_variable('ADMIN_IP_WHITELIST', '') else []

# Cache Configuration (Required for rate limiting and security features)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'pisowifi-security-cache',
        'OPTIONS': {
            'MAX_ENTRIES': 10000,
        }
    }
}

# Rate Limiting Configuration
RATELIMIT_USE_CACHE = 'default'
RATELIMIT_ENABLE = True

# Security Headers
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'

# Additional Security Settings
# SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')  # Disabled for HTTP-only
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

# Login/Logout URLs
LOGIN_URL = '/admin/login/'
LOGIN_REDIRECT_URL = '/admin/'
LOGOUT_REDIRECT_URL = '/admin/login/'

# Password Validation Enhancement
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 12,  # Increased from default 8
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
    {
        'NAME': 'app.security.validators.ComplexPasswordValidator',
    },
]

# Security Event Logging
SECURITY_LOG_LEVEL = 'WARNING'
SECURITY_LOG_EVENTS = [
    'login_failure',
    'rate_limit_exceeded',
    'suspicious_activity',
    'ip_blocked',
    'admin_access',
    'security_violation'
]

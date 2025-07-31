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
DEBUG = get_env_variable('DEBUG', 'False').lower() == 'true'

# SECURITY: Only allow specific hosts
ALLOWED_HOSTS_STR = get_env_variable('ALLOWED_HOSTS', 'localhost,127.0.0.1')
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

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
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

# HTTPS Settings (enable in production)
if not DEBUG and not DEV_MODE:
    SECURE_SSL_REDIRECT = get_env_variable('SECURE_SSL_REDIRECT', 'True').lower() == 'true'
    SECURE_HSTS_SECONDS = int(get_env_variable('SECURE_HSTS_SECONDS', '31536000'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# Session Security
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 3600  # 1 hour
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
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
    
    # Search model
    'search_model': ['app.Clients', 'app.Whitelist'],
    
    # Top Menu
    'topmenu_links': [
        {'name': 'Dashboard', 'url': 'admin:index', 'permissions': ['auth.view_user'], 'icon': 'fas fa-tachometer-alt'},
        {'name': 'Live Monitor', 'url': 'admin:app_clients_changelist', 'permissions': ['auth.view_user'], 'icon': 'fas fa-eye'},
        {'name': 'Analytics', 'url': 'admin:app_salesreport_changelist', 'permissions': ['auth.view_user'], 'icon': 'fas fa-chart-bar'},
        {'name': 'Security', 'url': 'admin:app_securitysettings_changelist', 'permissions': ['auth.view_user'], 'icon': 'fas fa-shield-alt'},
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
    
    # Hide user info from sidebar
    'user_avatar': None,
    'show_ui_builder': False,
    
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
        'auth.user': 'fas fa-user',
        'auth.Group': 'fas fa-users',
        
        # Core PISOWifi Models
        'app': 'fas fa-wifi',
        'app.Clients': 'fas fa-users',
        'app.Settings': 'fas fa-cog',
        'app.Device': 'fas fa-laptop',
        'app.Network': 'fas fa-network-wired',
        'app.Whitelist': 'fas fa-check-circle',
        'app.Rates': 'fas fa-dollar-sign',
        'app.Vouchers': 'fas fa-ticket-alt',
        
        # Financial Models
        'app.CoinSlot': 'fas fa-donate',
        'app.CoinQueue': 'fas fa-coins',
        'app.Ledger': 'fas fa-book',
        'app.SalesReport': 'fas fa-chart-line',
        
        # Security & Monitoring Models
        'app.SecuritySettings': 'fas fa-shield-alt',
        'app.TrafficMonitor': 'fas fa-eye',
        'app.BlockedDevices': 'fas fa-ban',
        'app.ConnectionTracker': 'fas fa-route',
        'app.TTLFirewallRule': 'fas fa-fire',
        'app.DeviceFingerprint': 'fas fa-fingerprint',
        'app.TrafficAnalysis': 'fas fa-chart-area',
        'app.DeviceBehaviorProfile': 'fas fa-user-shield',
        'app.AdaptiveQoSRule': 'fas fa-traffic-light',
        'app.NetworkIntelligence': 'fas fa-brain',
        
        # System Update Models
        'app.SystemUpdate': 'fas fa-download',
        
        # Backup & VLAN Models
        'app.BackupSettings': 'fas fa-archive',
        'app.DatabaseBackup': 'fas fa-database',
        'app.VLANSettings': 'fas fa-sitemap',
        
        # ZeroTier Remote Monitoring
        'app.ZeroTierSettings': 'fas fa-satellite-dish',
        'app.ZeroTierMonitoringData': 'fas fa-chart-line',
        
        # Port Prioritization/QoS
        'app.PortPrioritization': 'fas fa-layer-group',
        
        # Portal Management
        'app.PortalSettings': 'fas fa-desktop',
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

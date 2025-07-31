# Security Guide for PISOWifi Management System

## 🔒 Pre-Deployment Security Checklist

### ✅ Environment Configuration
- [ ] Generate new SECRET_KEY for production
- [ ] Set DEBUG=False in production
- [ ] Configure specific ALLOWED_HOSTS (no wildcards)
- [ ] Set up environment variables (.env file)
- [ ] Configure secure database credentials

### ✅ Database Security
- [ ] Use PostgreSQL instead of SQLite for production
- [ ] Enable database SSL connections
- [ ] Create dedicated database user with minimal privileges
- [ ] Regular database backups with encryption

### ✅ HTTPS and SSL
- [ ] Enable HTTPS with valid SSL certificate
- [ ] Configure HSTS headers
- [ ] Enable secure cookie settings
- [ ] Redirect HTTP to HTTPS

### ✅ Authentication and Authorization
- [ ] Change default admin credentials
- [ ] Enable strong password requirements
- [ ] Implement session timeouts
- [ ] Review user permissions

### ✅ Network Security
- [ ] Configure firewall rules
- [ ] Disable unnecessary services
- [ ] Use VPN for remote administration
- [ ] Regular security updates

## 🚨 Critical Security Fixes Applied

### 1. Secret Key Management
- **Fixed**: Hardcoded SECRET_KEY removed
- **Solution**: Environment variable with auto-generation fallback
- **Location**: `opw/settings.py:20`

### 2. Debug Mode
- **Fixed**: DEBUG=True in production
- **Solution**: Environment-controlled debug mode
- **Location**: `opw/settings.py:23`

### 3. Host Validation
- **Fixed**: ALLOWED_HOSTS wildcard
- **Solution**: Specific host configuration
- **Location**: `opw/settings.py:26-27`

### 4. CSRF Protection
- **Fixed**: CSRF exemptions removed
- **Solution**: Proper CSRF tokens implemented
- **Location**: `app/views.py:1668, 1695, 1748`

### 5. Command Injection
- **Fixed**: Unsafe subprocess calls
- **Solution**: Input validation and safe execution
- **Location**: `app/utils/security.py`

### 6. Input Validation
- **Fixed**: Missing form validation
- **Solution**: Comprehensive form validation
- **Location**: `app/forms.py`

## 🛡️ Security Features

### Input Validation
- IP address format validation
- MAC address format validation
- Voucher code sanitization
- SQL injection prevention

### Command Execution Safety
- Whitelist of allowed executables
- Input sanitization for subprocess calls
- Timeout protection
- No shell=True usage

### Session Security
- HTTPOnly cookies
- Secure cookie flags in HTTPS
- Session timeout (1 hour)
- CSRF protection

### Security Headers
```python
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000
```

## 📝 Logging and Monitoring

### Security Logging
- Authentication attempts
- Command execution
- Input validation failures
- TTL detection attempts

### Log Locations
- Application logs: `logs/pisowifi.log`
- Security logs: `logs/security.log`
- System logs: Check system logging

## ⚠️ Known Limitations

1. **SQLite in Development**: Switch to PostgreSQL for production
2. **Local File Storage**: Consider cloud storage for media files  
3. **No Rate Limiting**: Implement rate limiting for API endpoints
4. **Basic Authentication**: Consider 2FA for admin accounts

## 🚀 Deployment Instructions

### 1. Environment Setup
```bash
cp .env.example .env
# Edit .env with your production values
```

### 2. Database Migration
```bash
python manage.py migrate
python manage.py collectstatic
```

### 3. Production Server
```bash
gunicorn opw.wsgi:application --bind 0.0.0.0:8000
```

### 4. Web Server Configuration
Configure Nginx/Apache as reverse proxy with SSL termination.

## 📞 Security Incident Response

If you discover a security vulnerability:
1. Do not create public issue
2. Document the vulnerability
3. Apply temporary mitigation
4. Contact system administrator
5. Apply permanent fix
6. Document lessons learned

## 🔄 Regular Security Maintenance

### Weekly
- [ ] Review security logs
- [ ] Check for failed login attempts
- [ ] Monitor unusual network activity

### Monthly  
- [ ] Update dependencies
- [ ] Review user accounts
- [ ] Test backup/restore procedures
- [ ] Security configuration review

### Quarterly
- [ ] Penetration testing
- [ ] Security audit
- [ ] Update security documentation
- [ ] Staff security training

---

**Remember**: Security is an ongoing process, not a one-time setup!
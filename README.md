# OJO PISOWIFI
Advanced, Easy to use full-fledged WiFi Vending Solution with Auto-Update System

### 🚀 Key Features:

#### Core WiFi Vending Features:
1. **Time-based WiFi Vending** - Flexible time packages for customers
2. **Paperless Operation** - Digital coin slot integration
3. **WiFi Vouchers** - Generate and manage voucher codes
4. **Portal Customization** - Branded captive portal experience
5. **Advanced Admin Dashboard** - Comprehensive management interface
6. **Open Source** - Free and customizable solution

#### 🔄 System Update & Management:
7. **Auto-Update System** - Download and install updates from GitHub automatically
8. **Real-time Progress Tracking** - Monitor download and installation progress
9. **Safe Installation** - Automatic backups with rollback capability
10. **Multi-channel Updates** - Stable, beta, and development release channels

#### 🛡️ Security & Monitoring:
11. **Advanced Security Settings** - TTL detection and connection limiting
12. **Traffic Monitoring** - Real-time network usage analytics
13. **Device Management** - Block/unblock devices with reasons
14. **Connection Tracking** - Monitor client connections and behavior

#### 💰 Business Intelligence:
15. **Sales Analytics** - Comprehensive revenue reporting and charts
16. **Client Management** - Enhanced client control with individual actions
17. **Financial Tracking** - Detailed transaction logs and profit analysis
18. **Network Intelligence** - Traffic pattern analysis and optimization

#### 🔧 Technical Compatibility:
19. **Raspberry Pi 3/4 Compatible** - Optimized for ARM architecture
20. **Orange Pi One Compatible** - Supports various SBC platforms
21. **Modern Web Interface** - Bootstrap 5 with Jazzmin admin theme
22. **RESTful API** - Integration-ready backend services

## 🔄 System Update Feature

The latest version includes a comprehensive **Auto-Update System** that allows you to:

- **Check for Updates**: Automatically check GitHub for new releases
- **Download Progress**: Real-time progress tracking with pause/resume capability
- **Safe Installation**: Creates automatic backups before installing updates
- **Rollback Support**: Easily rollback to previous version if needed
- **Multiple Channels**: Choose between stable, beta, or development updates

### How to Use System Updates:

1. **Access Admin Panel** → Navigate to **System Updates**
2. **Check for Updates** → Click "Check for Updates" button
3. **Download** → Click "Download" on available updates
4. **Install** → Click "Install" once download completes
5. **Configure** → Use **Update Settings** to enable auto-updates

## 📋 Quick Start Guide

### Prerequisites:
- Python 3.8+ 
- Django 5.x
- SQLite or PostgreSQL
- Modern web browser

### Installation:

```bash
# Clone the repository
git clone https://github.com/regolet/pisowifi.git
cd pisowifi

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Initialize system settings
python initialize_security.py
python initialize_update_system.py

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic

# Run the server
python manage.py runserver 3000
```

### Access Points:
- **Admin Dashboard**: `http://localhost:3000/admin/`
- **Captive Portal**: `http://localhost:3000/`
- **API Endpoints**: `http://localhost:3000/api/`

## 🛠️ Configuration

### System Update Settings:
- **Repository**: `regolet/pisowifi` (default GitHub repository)
- **Update Channel**: Stable, Beta, or Development
- **Auto-Download**: Automatically download new updates
- **Auto-Install**: Automatically install downloaded updates
- **Backup Retention**: Number of backups to keep (default: 3)

### Security Features:
- **TTL Detection**: Prevent connection sharing via TTL analysis
- **Connection Limiting**: Limit simultaneous connections per device
- **Traffic Monitoring**: Real-time bandwidth usage tracking
- **Device Blocking**: Temporary or permanent device restrictions

## 📊 Admin Interface Overview

### Dashboard Sections:
1. **Clients** - Manage connected devices and authentication
2. **Sales Report** - Revenue analytics and transaction history
3. **Rates** - Configure pricing and time packages
4. **Settings** - System configuration and preferences  
5. **Network** - WiFi and network management
6. **Whitelist** - Authorized devices (free access)
7. **Blocked Devices** - Restricted devices with reasons
8. **System Updates** - Auto-update management
9. **Security Settings** - Advanced security configurations
10. **Traffic Monitor** - Network usage analytics

## 🔐 Security Features

### Connection Security:
- **TTL-based Sharing Detection** - Prevents unauthorized connection sharing
- **MAC Address Filtering** - Control device access by hardware address
- **Time-limited Sessions** - Automatic disconnection after time expires
- **Concurrent Connection Limits** - Prevent abuse by limiting simultaneous connections

### Administrative Security:
- **Django Admin Authentication** - Secure admin panel access
- **CSRF Protection** - Cross-site request forgery prevention
- **SQL Injection Protection** - Django ORM security
- **Automatic Backup System** - Protects against data loss during updates

## 🚀 Advanced Features

### Business Intelligence:
- **Revenue Analytics** - Daily, weekly, monthly sales reports
- **Customer Insights** - Usage patterns and popular time packages
- **Peak Hour Analysis** - Optimize pricing based on demand
- **Device Statistics** - Popular device types and connection trends

### Network Management:
- **Bandwidth Control** - Per-client upload/download limits
- **QoS Management** - Prioritize traffic types
- **Connection Monitoring** - Real-time client status tracking
- **Automatic Disconnection** - Clean up expired sessions

### System Maintenance:
- **Auto-Update System** - Keep system current with latest features
- **Database Optimization** - Automatic cleanup and maintenance
- **Log Management** - Comprehensive system logging
- **Backup Management** - Automated backup creation and rotation

## 🔧 Hardware Compatibility

### Tested Platforms:
- **Raspberry Pi 3 Model B+** - Recommended for small installations
- **Raspberry Pi 4** - Best performance for high-traffic locations
- **Orange Pi One** - Budget-friendly alternative
- **Standard Linux Servers** - Ubuntu 20/22 LTS, Debian 11/12

### Network Requirements:
- **WiFi Access Point** - For client connections
- **Internet Connection** - For update downloads and time synchronization
- **Ethernet Port** - For management interface access

## 📞 Support & Documentation

### Getting Help:
- **Issues**: Report bugs on [GitHub Issues](https://github.com/regolet/pisowifi/issues)
- **Documentation**: Check the `/docs` folder for detailed guides
- **Community**: Join discussions in repository discussions

### Contributing:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

## 🎯 Roadmap

### Upcoming Features:
- **Mobile App** - Android/iOS client management app
- **Multi-Location Support** - Manage multiple PISOWiFi installations
- **Advanced Analytics** - Machine learning insights
- **Payment Integration** - Credit card and digital wallet support
- **SMS Integration** - Voucher delivery via SMS

---

### System Screenshots
<img src="/docs/images/1.jpg" width="25%">  <img src="/docs/images/2.jpg" width="25%">  <img src="/docs/images/3.jpg" width="25%"><img src="/docs/images/4.jpg" width="25%">  <img src="/docs/images/5.jpg" width="25%">  <img src="/docs/images/6.jpg" width="25%">  <img src="/docs/images/7.jpg" width="25%">  <img src="/docs/images/8.jpg" width="25%">  <img src="/docs/images/9.jpg" width="25%">  <img src="/docs/images/10.jpg" width="25%">

**Made with ❤️ for the PISOWiFi Community**


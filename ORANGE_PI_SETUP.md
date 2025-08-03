# Orange Pi PISOWifi Setup Guide

## Quick Deployment

### 1. Initial Setup (One-time)
```bash
# Install system dependencies
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git nginx sqlite3 supervisor

# Clone repository
cd /opt
sudo git clone https://github.com/regolet/pisowifi.git pisowifi
sudo chown -R $USER:$USER /opt/pisowifi

# Setup Python environment
cd /opt/pisowifi
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Initialize database
python manage.py migrate
python manage.py createsuperuser

# Setup auto-start service
sudo cp deployment/supervisor/pisowifi.conf /etc/supervisor/conf.d/
sudo supervisorctl reread
sudo supervisorctl update
```

### 2. Configure Update Settings
1. Access admin panel: `http://orange-pi-ip/admin/`
2. Go to **Update Settings**
3. Ensure these settings:
   - GitHub Repository: `regolet/pisowifi`
   - Update Channel: `stable`
   - Auto Update: `Enabled` (optional)
   - Auto Backup: `Enabled`

### 3. Updating the System
**Method 1: Via Admin Panel (Recommended)**
- Navigate to System Update
- Click "Check for Updates"
- Download and install available updates

**Method 2: Manual Update**
```bash
cd /opt/pisowifi
git pull origin master
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo supervisorctl restart pisowifi
```

## Development Workflow

### From Windows Development Machine:
1. Make changes in your Windows environment
2. Test locally: `python manage.py runserver 3000`
3. Commit and push to GitHub:
   ```bash
   git add .
   git commit -m "Your changes"
   git push origin master
   ```
4. Create a GitHub release:
   ```bash
   git tag -a v2.2.5 -m "Release version 2.2.5"
   git push origin v2.2.5
   ```

### On Orange Pi:
1. Access admin panel
2. Go to System Update
3. Download and install the update
4. System automatically restarts

## Network Configuration

### WiFi Access Point Setup
```bash
# Install required packages
sudo apt install -y hostapd dnsmasq

# Configure hostapd
sudo nano /etc/hostapd/hostapd.conf
```

Add:
```
interface=wlan0
driver=nl80211
ssid=PISOWiFi
hw_mode=g
channel=6
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
```

### Enable IP Forwarding
```bash
echo 'net.ipv4.ip_forward=1' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

## Troubleshooting

### Service not starting
```bash
# Check logs
sudo supervisorctl tail -f pisowifi
sudo journalctl -u pisowifi -f
```

### Permission issues
```bash
# Fix permissions
sudo chown -R www-data:www-data /opt/pisowifi/media
sudo chown -R www-data:www-data /opt/pisowifi/static
```

### Update failures
```bash
# Manual recovery
cd /opt/pisowifi
git stash
git pull origin master
git stash pop
sudo supervisorctl restart pisowifi
```

## Performance Optimization

### For Orange Pi 3/4/5:
```bash
# Set CPU governor to performance
echo 'governor=performance' | sudo tee -a /boot/armbianEnv.txt
```

### Database optimization
```bash
# Run monthly
cd /opt/pisowifi
python manage.py dbshell
VACUUM;
ANALYZE;
.exit
```

## Backup Strategy

The system automatically creates backups before updates. Manual backup:
```bash
cd /opt/pisowifi
python manage.py create_backup --full
```

## Security Notes

1. Change default passwords
2. Use firewall rules:
   ```bash
   sudo ufw allow 22/tcp
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   sudo ufw enable
   ```
3. Regular updates via the System Update feature

## Support

- GitHub Issues: https://github.com/regolet/pisowifi/issues
- Documentation: Check `/docs` folder
- Logs: `/var/log/pisowifi/`
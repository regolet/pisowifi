# 🍊 PISOWifi Orange Pi Setup

**Super Easy Installation - Just 3 Commands!**

## 🚀 Quick Setup

### Step 1: Clone Repository
```bash
git clone https://github.com/regolet/pisowifi.git
cd pisowifi
```

### Step 2: Run Automated Setup
```bash
python3 setup_orangepi.py
```

### Step 3: Connect WiFi Router
- Connect WiFi router to Orange Pi's USB-LAN adapter
- Configure router as Access Point (disable DHCP)
- Set WiFi name to "PISOWifi" (open network)

## ✅ What the Setup Script Does

**Automatically configures everything:**
- ✅ Detects your network interfaces (`end0`, `enx...`)
- ✅ Installs all system packages (nginx, dnsmasq, etc.)
- ✅ Configures network routing and DHCP
- ✅ Sets up PISOWifi application
- ✅ Configures firewall and captive portal
- ✅ Creates admin user account
- ✅ Starts all services

## 🌐 Access Your PISOWifi

After setup completes:
- **Admin Panel:** `http://YOUR_ORANGE_PI_IP/admin/`
- **Client Portal:** `http://10.0.0.1/`

## 🔧 Hardware Setup

**Required:**
- Orange Pi One board
- USB-to-Ethernet adapter
- WiFi Router (any router that can work as AP)
- 2x Ethernet cables

**Connections:**
```
Internet → [Main Router] → [Orange Pi eth0] → [Orange Pi USB-LAN] → [WiFi Router]
```

## 📋 Network Configuration

The script automatically configures:
- **WAN Interface:** Gets internet from main router
- **LAN Interface:** Provides network to WiFi router (10.0.0.1/24)
- **DHCP Range:** 10.0.0.10 - 10.0.0.250
- **Captive Portal:** Redirects all traffic to login page

## 🛠️ Manual Commands (if needed)

**Check Services:**
```bash
sudo systemctl status nginx dnsmasq supervisor
sudo supervisorctl status pisowifi
```

**View Logs:**
```bash
sudo tail -f /var/log/pisowifi.log
sudo tail -f /var/log/dnsmasq.log
```

**Restart Services:**
```bash
sudo systemctl restart nginx dnsmasq
sudo supervisorctl restart pisowifi
```

## 🔍 Troubleshooting

**No internet for clients:**
```bash
# Check IP forwarding
cat /proc/sys/net/ipv4/ip_forward  # should be 1

# Check NAT rules
sudo iptables -t nat -L -v -n
```

**Captive portal not working:**
```bash
# Check if services are running
sudo supervisorctl status pisowifi
sudo systemctl status nginx

# Test internal connection
curl http://127.0.0.1:8000
```

**WiFi router not getting IP:**
```bash
# Check DNSMASQ leases
cat /var/lib/misc/dnsmasq.leases

# Restart DNSMASQ
sudo systemctl restart dnsmasq
```

## 💡 Features Included

- **Coin-operated WiFi access**
- **Voucher system**
- **Time-based billing**
- **Client management**
- **Revenue analytics**
- **System monitoring**
- **Mobile-friendly interface**
- **Captive portal**

## 🎯 Next Steps

1. **Configure Pricing:** Admin → Rates
2. **Customize Portal:** Admin → Portal Settings  
3. **Generate Vouchers:** Admin → Vouchers
4. **Monitor Usage:** Admin → Analytics
5. **System Health:** Admin → System Info

---

**That's it! Your PISOWifi business is ready to make money! 💰**
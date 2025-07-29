# TTL Detection & Internet Sharing Prevention

## Overview

This PisoWiFi system now includes **TTL (Time To Live) Detection** to prevent internet sharing through hotspot tethering. This is a common security measure used in commercial WiFi systems to ensure fair usage and prevent revenue loss.

## How TTL Detection Works

### What is TTL?
TTL (Time To Live) is a field in IP packets that indicates how many hops a packet can make before being discarded. Different operating systems use different default TTL values:

- **Windows**: 128
- **Linux/Android**: 64  
- **macOS/iOS**: 64
- **Router/Shared Connection**: Usually decremented by 1

### Detection Logic
When a device shares its internet connection (mobile hotspot, WiFi tethering), the TTL value of packets from connected devices is decremented by 1. This creates a signature that can be detected:

- **Direct Connection**: TTL = 64 (Android) or 128 (Windows)
- **Shared Connection**: TTL = 63 (Android hotspot) or 127 (Windows hotspot)

## Features Implemented

### 1. **Security Models**
- `SecuritySettings`: Configuration for TTL detection parameters
- `TrafficMonitor`: Logs TTL values and suspicious activity
- `BlockedDevices`: Manages blocked devices and auto-unblocking

### 2. **TTL Analysis**
- Real-time TTL extraction from client IP addresses
- Configurable tolerance levels for false positives
- Automatic violation counting and escalation

### 3. **Auto-Blocking System**
- Devices are automatically blocked after N violations (default: 3)
- Configurable block duration (default: 1 hour)
- Automatic unblocking when time expires

### 4. **Admin Interface**
- **Security Settings**: Configure TTL detection parameters
- **Traffic Monitor**: View TTL analysis logs
- **Blocked Devices**: Manage blocked devices manually

## Configuration

### Default Settings
```python
TTL_Detection_Enabled = True
Default_TTL_Value = 64          # Expected TTL (Linux/Android)
TTL_Tolerance = 2               # Allow ±2 variance
Block_Shared_Connections = True
Max_TTL_Violations = 3          # Block after 3 violations
Block_Duration = 1 hour         # Auto-unblock after 1 hour
```

### Customization
Access the admin panel at `/admin` and navigate to:
1. **Security Settings** - Configure TTL detection parameters
2. **Traffic Monitor** - View real-time TTL analysis
3. **Blocked Devices** - Manage blocked devices

## Usage Examples

### Scenario 1: Normal Android Device
```
Client connects with IP: 192.168.1.100
Detected TTL: 64
Expected TTL: 64 (±2 tolerance)
Result: ✅ Allowed - TTL within normal range
```

### Scenario 2: Android Hotspot Sharing
```
Client connects with IP: 192.168.1.101  
Detected TTL: 63 (decremented due to sharing)
Expected TTL: 64 (±2 tolerance)
Result: ⚠️ Suspicious - TTL indicates sharing
Action: Log violation, increment counter
```

### Scenario 3: Multiple Violations
```
Client: aa:bb:cc:dd:ee:ff
Violation 1: TTL=63 (Warning logged)
Violation 2: TTL=62 (Warning logged) 
Violation 3: TTL=63 (Auto-blocked for 1 hour)
```

## Portal Behavior

### For Normal Devices
- Standard captive portal interface
- Insert coins and browse normally
- TTL monitoring happens transparently

### For Blocked Devices  
- Portal shows "Device Blocked" message
- Displays block reason and duration
- Shows TTL analysis details
- Coin insertion interface is hidden

## Technical Implementation

### TTL Extraction
```python
def get_ttl_from_ip(ip_address):
    # Uses ping command to extract TTL
    # Supports Windows and Linux systems
    # Returns TTL value or None if failed
```

### Analysis Function
```python
def analyze_ttl_for_sharing(mac_address, ttl_value):
    # Compares detected TTL with expected value
    # Logs traffic data for analysis
    # Auto-blocks after max violations
```

### Integration Points
- **Portal View**: TTL analysis on every page load
- **Client Connection**: TTL check before allowing access
- **Admin Interface**: Real-time monitoring and management

## Limitations & Considerations

### False Positives
- Some devices may have non-standard TTL values
- VPN usage can alter TTL values  
- Adjust tolerance settings to minimize false blocks

### Bypass Methods
- Advanced users may manipulate TTL values
- Consider combining with other detection methods
- Monitor traffic patterns for additional indicators

### Performance Impact
- TTL detection adds minimal overhead
- Ping operations have ~5ms timeout
- Traffic logs should be cleaned periodically

## Advanced Configuration

### Windows vs Linux Detection
```python
# For mixed device environments
if client_os == 'windows':
    expected_ttl = 128
elif client_os == 'linux_android':
    expected_ttl = 64
```

### Custom Block Durations
```python
# Different penalties for different violations
first_violation = 30 minutes
repeat_violation = 2 hours  
persistent_violator = 24 hours
```

## Monitoring & Maintenance

### Regular Tasks
1. **Review Traffic Monitor** - Check for false positives
2. **Adjust TTL Settings** - Fine-tune based on device mix
3. **Clean Old Logs** - Remove outdated traffic data
4. **Update Block Lists** - Manually review blocked devices

### Performance Optimization
- Archive old TrafficMonitor records
- Index frequently queried fields
- Monitor database size growth

## Troubleshooting

### Common Issues
1. **High False Positives**: Increase TTL tolerance
2. **No Detection**: Check ping connectivity
3. **Performance Issues**: Clean old traffic logs
4. **Admin Access**: Ensure proper permissions

### Debug Mode
Enable detailed logging to troubleshoot detection issues:
```python
# In views.py - add debug prints
print(f"TTL Detection: IP={ip}, TTL={ttl_value}")
```

## Security Benefits

### Revenue Protection
- Prevents multiple users sharing single connection
- Ensures fair usage policies
- Maintains intended pricing model

### Network Management  
- Reduces unauthorized bandwidth usage
- Improves performance for legitimate users
- Provides usage analytics and insights

### Compliance
- Helps meet ISP terms of service
- Supports fair usage enforcement
- Provides audit trail for violations

---

**Note**: TTL detection is one layer of protection. For comprehensive internet sharing prevention, consider combining with additional methods like device fingerprinting, traffic analysis, and connection limits.
# Connection Limiting & TTL-Based Internet Sharing Prevention

## Overview

The PisoWiFi system now implements **Connection Limiting** instead of complete device blocking to prevent internet sharing. This approach is more user-friendly while still effectively preventing hotspot tethering and maintaining fair usage.

## How Connection Limiting Works

### The Problem
When users share their WiFi connection through mobile hotspots or WiFi tethering:
- Multiple devices connect through a single MAC address
- Revenue is lost as multiple users access the internet for the price of one
- Network performance degrades due to unexpected traffic volume

### The Solution: Smart Connection Limits
Instead of completely blocking devices with suspicious TTL values, the system applies dynamic connection limits:

- **Normal Devices** (TTL within expected range): Allow multiple connections (default: 3)
- **Suspicious Devices** (TTL indicates sharing): Limit to minimal connections (default: 1)
- **Repeat Violators**: Apply even stricter limits or optional blocking

## Features Implemented

### 1. **Dynamic Connection Limits**
```python
# Default Configuration
Normal_Device_Connections = 3      # Normal devices can have 3 simultaneous connections
Suspicious_Device_Connections = 1  # Suspicious devices limited to 1 connection
Max_TTL_Violations = 5            # After 5 violations, apply strictest limits
```

### 2. **Real-Time Connection Tracking**
- `ConnectionTracker` model logs all active sessions
- Tracks TTL classification per connection
- Automatic cleanup of expired sessions (30-minute timeout)
- Session uniqueness prevents duplicate counting

### 3. **TTL-Based Classification**
- **Normal TTL**: Device gets full connection allowance
- **Suspicious TTL**: Device limited to 1 connection (prevents sharing)
- **Unknown TTL**: Treated as normal with fallback limits

### 4. **User-Friendly Portal Experience**
- Connection status displayed prominently
- Clear indicators when limits are reached
- Warning messages for suspicious TTL patterns
- "Surf the Net" button disabled when limit exceeded

## User Experience Examples

### Scenario 1: Normal Android Device
```
Device connects with TTL=64 (normal)
Portal shows: "Connection Status: 0/3 active connections [Normal TTL]"
User can connect normally and use up to 3 simultaneous sessions
```

### Scenario 2: Android Hotspot Detected
```
Device connects with TTL=63 (suspicious - sharing detected)
Portal shows: "Connection Status: 0/1 active connections [Suspicious TTL]"
Warning: "TTL Warning: Internet sharing detected (TTL 63, expected 64)"
User limited to 1 connection, preventing effective sharing
```

### Scenario 3: Limit Reached
```
Suspicious device already has 1 active connection
Portal shows: "Connection Status: 1/1 active connections [Suspicious TTL]"
"Surf the Net" button shows "Connection Limit Reached" and is disabled
User must wait for session to expire or end current session
```

## Technical Implementation

### Connection Limiting Logic
```python
def check_connection_limit(mac_address, request=None):
    # Clean up expired sessions
    ConnectionTracker.cleanup_expired_sessions()
    
    # Get current active connections
    current_connections = ConnectionTracker.get_active_connections_for_device(mac_address)
    
    # Determine limit based on TTL analysis
    ttl_analysis = analyze_ttl_for_sharing(mac_address, ttl_value)
    connection_limit = ttl_analysis['connection_limit']
    
    return {
        'can_connect': current_connections < connection_limit,
        'current_connections': current_connections,
        'connection_limit': connection_limit
    }
```

### Session Registration
```python
def register_connection(mac_address, ip_address, session_id, ttl_classification):
    # Register new connection session
    connection = ConnectionTracker.objects.create(
        Device_MAC=mac_address,
        Connection_IP=ip_address,
        Session_ID=session_id,
        TTL_Classification=ttl_classification,
        Is_Active=True
    )
```

## Admin Interface

### Security Settings Configuration
Navigate to `/admin` → **Security Settings**:

#### TTL Detection Settings
- **Enable TTL Detection**: Enable/disable TTL analysis
- **Expected TTL**: Expected TTL value for normal devices (default: 64)
- **TTL Tolerance**: Allowed deviation from expected TTL (default: ±2)

#### Connection Limiting Settings
- **Limit Connections**: Enable/disable connection limiting
- **Normal Device Limit**: Max connections for devices with normal TTL (default: 3)
- **Suspicious Device Limit**: Max connections for devices with suspicious TTL (default: 1)
- **Max TTL Violations**: Violations before applying strictest limits (default: 5)

#### Optional Device Blocking
- **Enable Device Blocking**: Fallback to complete blocking (not recommended)
- **Block Duration**: How long to block if blocking is enabled

### Connection Tracking
Navigate to `/admin` → **Connection Tracker**:
- View all active connection sessions
- See TTL classification per connection
- Monitor connection patterns
- Manually activate/deactivate connections
- Cleanup expired sessions

### Traffic Monitoring
Navigate to `/admin` → **Traffic Monitor**:
- Review TTL analysis logs
- Identify devices with suspicious patterns
- Track violation counts over time

## Configuration Examples

### Lenient Configuration (More User-Friendly)
```python
Normal_Device_Connections = 5      # Allow more connections
Suspicious_Device_Connections = 2  # Still allow some sharing
TTL_Tolerance = 3                  # More forgiving TTL detection
Max_TTL_Violations = 10            # Higher threshold
```

### Strict Configuration (Maximum Protection)
```python
Normal_Device_Connections = 2      # Limit even normal devices
Suspicious_Device_Connections = 1  # Strict sharing prevention
TTL_Tolerance = 1                  # Sensitive TTL detection
Max_TTL_Violations = 3             # Quick escalation
```

### Balanced Configuration (Recommended)
```python
Normal_Device_Connections = 3      # Reasonable for legitimate use
Suspicious_Device_Connections = 1  # Prevents effective sharing
TTL_Tolerance = 2                  # Accounts for network variations
Max_TTL_Violations = 5             # Fair violation threshold
```

## Benefits Over Complete Blocking

### 1. **User Experience**
- No sudden disconnections or access denial
- Clear feedback about connection status
- Gradual enforcement rather than harsh blocking

### 2. **Revenue Protection**
- Sharing becomes impractical with 1-connection limit
- Legitimate users retain access
- Maintains intended pricing model

### 3. **Network Stability**
- Prevents connection overflow from sharing
- Maintains predictable network load
- Reduces support issues from blocked users

### 4. **Administrative Flexibility**
- Fine-tuned control over limits
- Real-time monitoring of connections
- Easy adjustment of policies

## Troubleshooting

### Common Issues

#### High False Positives
- **Symptom**: Normal devices classified as suspicious
- **Solution**: Increase TTL tolerance or adjust expected TTL values
- **Check**: Review Traffic Monitor for TTL patterns

#### Users Bypassing Limits
- **Symptom**: Multiple connections from suspicious devices
- **Solution**: Reduce suspicious device limit to 1, enable stricter monitoring
- **Check**: Review Connection Tracker for session patterns

#### Performance Issues
- **Symptom**: Slow portal loading or connection delays
- **Solution**: Regular cleanup of expired sessions, optimize database
- **Check**: Monitor ConnectionTracker table size

### Debug Commands
```python
# Check active connections for a device
ConnectionTracker.get_active_connections_for_device('aa:bb:cc:dd:ee:ff')

# Manual cleanup of expired sessions
ConnectionTracker.cleanup_expired_sessions()

# Review TTL analysis for troubleshooting
analyze_ttl_for_sharing('aa:bb:cc:dd:ee:ff', 63)
```

## Monitoring & Maintenance

### Regular Tasks
1. **Review Connection Patterns** - Check Connection Tracker for abuse
2. **Analyze TTL Data** - Review Traffic Monitor for false positives
3. **Adjust Limits** - Fine-tune based on usage patterns
4. **Clean Database** - Remove old tracking data periodically

### Performance Optimization
- Index frequently queried fields (Device_MAC, Is_Active)
- Archive old connection logs monthly
- Monitor database growth and performance

### Security Considerations
- Connection limits prevent most sharing scenarios
- TTL analysis provides early warning of violations
- Session tracking enables detailed audit trails
- Optional blocking available for extreme cases

## Migration from Blocking System

If upgrading from the previous blocking-based system:

1. **Disable Complete Blocking**: Set `Enable_Device_Blocking = False`
2. **Configure Connection Limits**: Set appropriate normal/suspicious limits
3. **Monitor Traffic**: Review patterns for first few days
4. **Fine-Tune Settings**: Adjust limits based on observed behavior
5. **Clean Blocked Devices**: Remove existing blocked device entries

## Future Enhancements

### Planned Features
- **Device Fingerprinting**: Enhanced detection beyond TTL
- **Bandwidth Limiting**: Reduce speed instead of blocking connections
- **Time-Based Limits**: Different limits for peak/off-peak hours
- **User Authentication**: Account-based connection tracking

### Advanced Detection
- **Traffic Pattern Analysis**: Detect sharing through data patterns
- **Connection Behavior**: Monitor for automation or bot usage
- **Geographic Analysis**: Cross-reference connection locations

---

**Note**: Connection limiting provides an excellent balance between security and user experience. It effectively prevents internet sharing while maintaining a friendly portal experience for legitimate users.
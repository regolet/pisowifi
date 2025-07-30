# Validity/Expiration System Implementation Guide

## Overview
The validity system allows both rates and vouchers to have expiration periods, meaning purchased time must be used within a certain timeframe.

## ✅ IMPLEMENTATION COMPLETE
The validity/expiration system has been fully implemented and is ready for use.

### Features Implemented:
- ✅ Portal displays validity expiration with color-coded warnings
- ✅ Validity checking prevents expired time usage
- ✅ Automatic time cleanup when validity expires
- ✅ Coin purchases respect rate validity settings
- ✅ Voucher redemption respects voucher validity settings
- ✅ Admin interfaces show validity settings for both rates and vouchers

## Database Changes Made
1. **Rates Model**:
   - Added `Validity_Days` (integer): Number of days the purchased time is valid
   - Added `Validity_Hours` (integer): Additional hours for validity period
   - Added methods: `get_validity_duration()` and `get_validity_display()`

2. **Vouchers Model**:
   - Added `Validity_Days` (integer): Number of days the voucher time is valid once redeemed
   - Added `Validity_Hours` (integer): Additional hours for validity period
   - Added methods: `get_validity_duration()` and `get_validity_display()`

3. **Clients Model**:
   - Added `Validity_Expires_On` (datetime): When purchased time expires and can no longer be used

## How to Implement the Validity Logic

### 1. When Adding Time (Coins/Vouchers)
When a client purchases time through coins or vouchers, the system should:

```python
# In the connection/time addition logic:
def add_time_with_validity(client, time_to_add, rate=None):
    # Check if there's a validity period from the rate
    if rate and (rate.Validity_Days > 0 or rate.Validity_Hours > 0):
        validity_duration = rate.get_validity_duration()
        
        # Set or update validity expiration
        if not client.Validity_Expires_On:
            # First time purchase - set validity from now
            client.Validity_Expires_On = timezone.now() + validity_duration
        else:
            # Existing validity - check if expired
            if timezone.now() > client.Validity_Expires_On:
                # Previous validity expired, start new validity period
                client.Validity_Expires_On = timezone.now() + validity_duration
                # Clear any expired time
                client.Time_Left = timedelta(0)
    
    # Add the time as usual
    client.Connect(time_to_add)
```

### 2. Before Connecting
Check if the client's time is still valid:

```python
def can_connect(client):
    # Check validity expiration
    if client.Validity_Expires_On and timezone.now() > client.Validity_Expires_On:
        # Time has expired - clear it
        client.Time_Left = timedelta(0)
        client.Expire_On = None
        client.Validity_Expires_On = None
        client.save()
        return False, "Your purchased time has expired"
    
    return True, "OK"
```

### 3. In the Portal Display
Show validity expiration to users:

```python
# Add to portal context
if client.Validity_Expires_On:
    time_until_expiry = client.Validity_Expires_On - timezone.now()
    if time_until_expiry.total_seconds() > 0:
        context['validity_expires_in'] = time_until_expiry
        context['validity_expires_on'] = client.Validity_Expires_On
```

### 4. Scheduled Task (Optional)
Create a management command to clean up expired time:

```python
# management/commands/cleanup_expired_time.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from app.models import Clients

class Command(BaseCommand):
    def handle(self, *args, **options):
        expired_clients = Clients.objects.filter(
            Validity_Expires_On__lt=timezone.now(),
            Time_Left__gt=timedelta(0)
        )
        
        for client in expired_clients:
            client.Time_Left = timedelta(0)
            client.Validity_Expires_On = None
            client.save()
            self.stdout.write(f"Cleared expired time for {client.MAC_Address}")
```

## UI Considerations

1. **Admin Interface**: Already updated to show validity settings in Rates admin

2. **Portal**: Should display:
   - Time remaining
   - Validity expiration date/time
   - Warning when validity is about to expire

3. **Color Coding**:
   - Green: No expiration or > 7 days
   - Orange: 1-7 days until expiration
   - Red: < 24 hours until expiration

## Testing
1. Create a rate with 1 day validity
2. Purchase time with that rate
3. Check that Validity_Expires_On is set correctly
4. Test connecting before and after expiration
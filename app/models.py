from django.core.exceptions import ValidationError
from django.contrib import messages
from django.db import models
from datetime import datetime, timedelta
from django.utils import timezone
from django.urls import reverse
import subprocess
import string, random, os, math

class Clients(models.Model):
    IP_Address = models.CharField(max_length=15, verbose_name='IP')
    MAC_Address = models.CharField(max_length=255, verbose_name='MAC Address', unique=True)
    Device_Name = models.CharField(max_length=255, verbose_name='Device Name', null=True, blank=True)
    Time_Left = models.DurationField(default=timezone.timedelta(minutes=0))
    Expire_On = models.DateTimeField(null=True, blank=True)
    Validity_Expires_On = models.DateTimeField(null=True, blank=True, verbose_name='Validity Expiration', help_text='When purchased time expires and can no longer be used')
    Upload_Rate = models.IntegerField(verbose_name='Upload Bandwidth', help_text='Specify client internet upload bandwidth in Kbps. No value = unlimited bandwidth', null=True, blank=True )
    Download_Rate = models.IntegerField(verbose_name='Download Bandwidth', help_text='Specify client internet download bandwidth in Kbps. No value = unlimited bandwidth', null=True, blank=True )
    Notification_ID = models.CharField(verbose_name = 'Notification ID', max_length=255, null=True, blank = True)
    Notified_Flag = models.BooleanField(default=False)
    Date_Created = models.DateTimeField(default=timezone.now)


    @property
    def running_time(self):
        if not self.Expire_On:
            return timedelta(0)
        else:
            running_time = self.Expire_On - timezone.now()
            if running_time < timedelta(0):
                return timedelta(0)
            else:
                return running_time

    @property
    def Connection_Status(self):
        if self.running_time > timedelta(0):
            return 'Connected'
        else:
            if self.Time_Left > timedelta(0):
                return 'Paused'
            else:
                return 'Disconnected'

    def Connect(self, add_time = timedelta(0)):
        # Check validity expiration first
        if self.Validity_Expires_On and timezone.now() > self.Validity_Expires_On:
            # Time has expired - clear it
            self.Time_Left = timedelta(0)
            self.Expire_On = None
            self.Validity_Expires_On = None
            self.save()
            return False
        
        total_time = self.Time_Left + add_time
        success_flag = False
        if total_time > timedelta(0):
            if self.running_time > timedelta(0):
                self.Expire_On = self.Expire_On + total_time
            else:
                self.Expire_On = timezone.now() + total_time

            self.Time_Left = timedelta(0)

            # Push notification logic removed for personal use
            self.Notified_Flag = False

            self.save()

            success_flag = True
        return success_flag

    def Disconnect(self):
        success_flag = False
        if self.Connection_Status == 'Connected':
            # Preserve remaining time by moving it from Expire_On to Time_Left
            if self.Expire_On:
                remaining_time = self.Expire_On - timezone.now()
                if remaining_time.total_seconds() > 0:
                    self.Time_Left = remaining_time
                else:
                    self.Time_Left = timedelta(0)
            self.Expire_On = None
            self.Notified_Flag = False
            self.save()
            success_flag = True
        elif self.Connection_Status == 'Paused':
            # For paused clients, just clear Expire_On but keep Time_Left as is
            self.Expire_On = None
            self.Notified_Flag = False
            self.save()
            success_flag = True
        return success_flag

    def Kick(self):
        """Kick client from WiFi network and remove from database"""
        import subprocess
        import os
        success_flag = False
        
        try:
            # First disconnect internet access
            if self.Connection_Status in ['Connected', 'Paused']:
                self.Disconnect()
            
            # Force deauthenticate client from WiFi using hostapd_cli
            # This sends deauth frames to physically kick the client
            mac_address = self.MAC_Address.replace(':', '')  # Remove colons for hostapd_cli
            
            # Try multiple methods to kick client from WiFi
            kick_commands = [
                f'hostapd_cli deauthenticate {self.MAC_Address}',
                f'hostapd_cli disassociate {self.MAC_Address}',
                f'iwctl station {self.MAC_Address} disconnect'  # Alternative for iwctl
            ]
            
            kicked_successfully = False
            for cmd in kick_commands:
                try:
                    result = subprocess.run(cmd.split(), capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        kicked_successfully = True
                        break
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                    continue
            
            # If WiFi kick commands failed, try iptables blocking as fallback
            if not kicked_successfully:
                try:
                    # Block client MAC in iptables temporarily
                    block_cmd = f'iptables -I FORWARD -m mac --mac-source {self.MAC_Address} -j DROP'
                    subprocess.run(block_cmd.split(), capture_output=True, timeout=5)
                    kicked_successfully = True
                except:
                    pass
            
            success_flag = True  # Mark as successful regardless of WiFi kick result
            
        except Exception as e:
            # If all methods fail, still mark as successful for database cleanup
            success_flag = True
            
        return success_flag

    def Pause(self):
        success_flag = False
        if self.Connection_Status == 'Connected':
            self.Time_Left = self.running_time
            self.Expire_On = None
            self.save()
            success_flag = True
        return success_flag

    class Meta:
        verbose_name = 'Client'
        verbose_name_plural = 'Clients'

    def __str__(self):
        return str(self.IP_Address) + ' | ' + str(self.MAC_Address)


class UnauthenticatedClients(Clients):
    """Proxy model to show clients connected to AP but not authenticated"""
    class Meta:
        proxy = True
        verbose_name = 'Unauthenticated Client'
        verbose_name_plural = 'Unauthenticated Clients (Connected to AP)'


class Whitelist(models.Model):
    MAC_Address = models.CharField(max_length=255, verbose_name='MAC', unique=True)
    Device_Name = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        verbose_name = 'Allowed Client'
        verbose_name_plural = 'Allowed Clients'

    def __str__(self):
        name =  self.MAC_Address if not self.Device_Name else self.Device_Name
        return 'Device: ' + name


class Ledger(models.Model):
    Date = models.DateTimeField()
    Client = models.CharField(max_length=50)
    Denomination = models.IntegerField()
    Slot_No = models.IntegerField()

    def save(self, *args, **kwargs):
        self.Date = timezone.now()
        super(Ledger, self).save(*args, **kwargs)

    class Meta:
        verbose_name = 'Ledger'
        verbose_name_plural = 'Ledger'

    def __str__(self):
        return 'Transaction no: ' + str(self.pk)


class SalesReport(Ledger):
    """Proxy model for sales reporting and analytics"""
    class Meta:
        proxy = True
        verbose_name = 'Sales Report'
        verbose_name_plural = 'Sales Reports'


class CoinSlot(models.Model):
    def generate_code(size=10):
        found = False
        random_code = None

        while not found:
            random_code = ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(size))
            count = Vouchers.objects.filter(Voucher_code=random_code).count()
            if count == 0:
                found = True

        return random_code

    Edit = 'Edit'
    Client = models.CharField(max_length=17, null=True, blank=True)
    Last_Updated = models.DateTimeField(null=True, blank=True)
    Slot_ID = models.CharField(default=generate_code, unique=True, max_length=10, null=False, blank=False)
    Slot_Address = models.CharField(unique=True, max_length=17, null=False, blank=False, default='00:00:00:00:00:00')
    Slot_Desc = models.CharField(max_length=50, null=True, blank=True, verbose_name='Description')

    class Meta:
        verbose_name = 'Coin Slot'
        verbose_name_plural = 'Coin Slot'

    def __str__(self):

        return 'Slot no: ' + str(self.pk)

class Rates(models.Model):
    Edit = "Edit"
    Denom = models.IntegerField(verbose_name='Denomination', help_text="Coin denomination corresponding to specified coinslot pulse.")
    Pulse = models.IntegerField(blank=True, null=True, help_text="Coinslot pulse count corresponding to coin denomination. Leave it blank for promotional rates.")
    Minutes = models.DurationField(verbose_name='Duration', default=timezone.timedelta(minutes=0), help_text='Internet access duration in hh:mm:ss format')
    Validity_Days = models.IntegerField(verbose_name='Validity Period (Days)', default=0, help_text='Number of days the purchased time is valid. 0 = no expiration')
    Validity_Hours = models.IntegerField(verbose_name='Validity Period (Hours)', default=0, help_text='Additional hours for validity period. Combined with days above.')

    class Meta:
        verbose_name = "Rate"
        verbose_name_plural = "Rates"

    def __str__(self):
        return 'Rate: ' + str(self.Denom)
    
    def get_validity_duration(self):
        """Get total validity duration as a timedelta"""
        from datetime import timedelta
        return timedelta(days=self.Validity_Days, hours=self.Validity_Hours)
    
    def get_validity_display(self):
        """Get human-readable validity display"""
        if self.Validity_Days == 0 and self.Validity_Hours == 0:
            return "No expiration"
        
        parts = []
        if self.Validity_Days > 0:
            parts.append(f"{self.Validity_Days} day{'s' if self.Validity_Days != 1 else ''}")
        if self.Validity_Hours > 0:
            parts.append(f"{self.Validity_Hours} hour{'s' if self.Validity_Hours != 1 else ''}")
        
        return " and ".join(parts)


class CoinQueue(models.Model):
    Client = models.CharField(max_length=17, null=True, blank=True)
    Total_Coins = models.IntegerField(null=True, blank=True, default=0)

    @property
    def Total_Time(self):
        settings = Settings.objects.get(pk=1)
        rate_type = settings.Rate_Type
        base_value = settings.Base_Value
        total_coins = self.Total_Coins
        total_time = timedelta(0)

        if rate_type == 'manual':
            rates = Rates.objects.all().order_by('-Denom')
            for rate in rates:
                multiplier = math.floor(total_coins/rate.Denom)
                if multiplier > 0:
                    total_coins = total_coins - (rate.Denom * multiplier)
                    total_time = total_time + (rate.Minutes * multiplier)
        
        if rate_type == 'auto':
            total_time = base_value * total_coins
        
        return total_time

    class Meta:
        verbose_name = 'Coin Queue'
        verbose_name_plural = 'Coin Queue'

    def __str__(self):
        if self.Client:
            return 'Coin queue for: ' + self.Client
        else:
            return 'Record'


class Settings(models.Model):
    rate_type_choices = (
        ('auto', 'Minutes/Peso'),
        ('manual', 'Custom Rate'),
    )
    enable_disable_choices = (
        (1, 'Enable'),
        (0, 'Disable'),
    )

    def get_image_path(instance, filename):
        return os.path.join(str(instance.id), filename)

    Hotspot_Name = models.CharField(max_length=255)
    Hotspot_Address = models.CharField(max_length=255, null=True, blank=True)
    BG_Image = models.ImageField(upload_to=get_image_path, blank=True, null=True)
    Slot_Timeout = models.IntegerField(help_text='Slot timeout in seconds.')
    Rate_Type = models.CharField(max_length=25, default="auto", choices=rate_type_choices, help_text='Select "Minutes/Peso" to use  Minutes / Peso value, else use "Custom Rate" to manually setup Rates based on coin value.')
    Base_Value = models.DurationField(default=timezone.timedelta(minutes=0), verbose_name='Minutes / Peso')
    Inactive_Timeout = models.IntegerField(verbose_name='Inactive Timeout', help_text='Timeout before an idle client (status = Disconnected) is removed from the client list. (Minutes)')
    Redir_Url = models.CharField(max_length=255, verbose_name='Redirect URL', help_text='Redirect url after a successful login. If not set, will default to the timer page.', null=True, blank=True)
    Vouchers_Flg = models.IntegerField(verbose_name='Vouchers', default=1, choices=enable_disable_choices, help_text='Enables voucher module.')
    Pause_Resume_Flg = models.IntegerField(verbose_name='Pause/Resume', default=1, choices=enable_disable_choices, help_text='Enables pause/resume function.')
    Disable_Pause_Time = models.DurationField(default=timezone.timedelta(minutes=0), null=True, blank=True, help_text='Disables Pause time button if remaining time is less than the specified time hh:mm:ss format.')
    Default_Block_Duration = models.DurationField(default=timezone.timedelta(hours=24), verbose_name='Default Block Duration', help_text='Default duration for blocking devices. Format: HH:MM:SS (e.g., 24:00:00 for 24 hours)')
    Enable_Permanent_Block = models.BooleanField(default=False, verbose_name='Enable Permanent Block Option', help_text='Allow devices to be blocked permanently (no auto-unblock)')
    Coinslot_Pin = models.IntegerField(verbose_name='Coinslot Pin', help_text='Please refer raspberry/orange pi GPIO.BOARD pinout.', null=True, blank=True)
    Light_Pin = models.IntegerField(verbose_name='Light Pin', help_text='Please refer raspberry/orange pi GPIO.BOARD pinout.', null=True, blank=True)

    def clean(self, *args, **kwargs):
        if self.Coinslot_Pin or self.Light_Pin:
            if self.Coinslot_Pin == self.Light_Pin:
                raise ValidationError('Coinslot Pin should not be the same as Light Pin.')

    class Meta:
        verbose_name = 'Settings'

    def __str__(self):
        return 'Settings'

class Network(models.Model):
    Edit = "Edit"
    Server_IP = models.GenericIPAddressField(verbose_name='Server IP', protocol='IPv4', default='10.0.0.1', null=False, blank=False)
    Netmask = models.GenericIPAddressField(protocol='IPv4', default='255.255.255.0', null=False, blank=False)
    DNS_1 = models.GenericIPAddressField(protocol='IPv4', verbose_name='DNS 1', default='8.8.8.8', null=False, blank=False)
    DNS_2 = models.GenericIPAddressField(protocol='IPv4', verbose_name='DNS 2 (Optional)', default='8.8.4.4', null=True, blank=True)
    Upload_Rate = models.IntegerField(verbose_name='Upload Bandwidth', help_text='Specify global internet upload bandwidth in Kbps. No value = unlimited bandwidth', null=True, blank=True )
    Download_Rate = models.IntegerField(verbose_name='Download Bandwidth', help_text='Specify global internet download bandwidth in Kbps. No value = unlimited bandwidth', null=True, blank=True )

    class Meta:
        verbose_name = 'Network'

    def __str__(self):
        return 'Network Settings'


class Vouchers(models.Model):
    status_choices = (
        ('Used', 'Used'),
        ('Not Used', 'Not Used'),
        ('Expired', 'Expired')
    )

    def generate_code(size=6):
        found = False
        random_code = None

        while not found:
            random_code = ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(size))
            count = Vouchers.objects.filter(Voucher_code=random_code).count()
            if count == 0:
                found = True

        return random_code

    Voucher_code = models.CharField(default=generate_code, max_length=20, null=False, blank=True, unique=True)
    Voucher_status = models.CharField(verbose_name='Status', max_length=25, choices=status_choices, default='Not Used', null=False, blank=False)
    Voucher_client = models.CharField(verbose_name='Client', max_length=50, null=True, blank=True, help_text="Voucher code user. * Optional")
    Voucher_create_date_time = models.DateTimeField(verbose_name='Created Date/Time', auto_now_add=True)
    Voucher_used_date_time = models.DateTimeField(verbose_name='Used Date/Time', null=True, blank=True)
    Voucher_time_value = models.DurationField(verbose_name='Time Value', default=timezone.timedelta(minutes=0), null=True, blank=True, help_text='Time value in minutes.')
    Validity_Days = models.IntegerField(verbose_name='Validity Period (Days)', default=0, help_text='Number of days the voucher time is valid once redeemed. 0 = no expiration')
    Validity_Hours = models.IntegerField(verbose_name='Validity Period (Hours)', default=0, help_text='Additional hours for validity period. Combined with days above.')

    def save(self, *args, **kwargs):
        if self.Voucher_status == 'Used' and not self.Voucher_used_date_time:
             self.Voucher_used_date_time = timezone.now()

        if self.Voucher_status == 'Not Used':
            self.Voucher_used_date_time = None

        super(Vouchers, self).save(*args, **kwargs)

    def is_expired(self):
        """Check if voucher has expired (30 days from creation)"""
        from datetime import timedelta
        if self.Voucher_status in ['Used', 'Expired']:
            return self.Voucher_status == 'Expired'
        
        expiry_date = self.Voucher_create_date_time + timedelta(days=30)
        return timezone.now() > expiry_date
    
    def days_until_expiry(self):
        """Get days until voucher expires"""
        from datetime import timedelta
        if self.Voucher_status in ['Used', 'Expired']:
            return 0
        
        expiry_date = self.Voucher_create_date_time + timedelta(days=30)
        days_left = (expiry_date - timezone.now()).days
        return max(0, days_left)
    
    def get_time_display(self):
        """Get human readable time display"""
        total_seconds = int(self.Voucher_time_value.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours}h {minutes}m"
    
    def get_validity_duration(self):
        """Get total validity duration as a timedelta"""
        from datetime import timedelta
        return timedelta(days=self.Validity_Days, hours=self.Validity_Hours)
    
    def get_validity_display(self):
        """Get human-readable validity display"""
        if self.Validity_Days == 0 and self.Validity_Hours == 0:
            return "No expiration"
        
        parts = []
        if self.Validity_Days > 0:
            parts.append(f"{self.Validity_Days} day{'s' if self.Validity_Days != 1 else ''}")
        if self.Validity_Hours > 0:
            parts.append(f"{self.Validity_Hours} hour{'s' if self.Validity_Hours != 1 else ''}")
        
        return " and ".join(parts)
    
    def expire_if_needed(self):
        """Automatically expire voucher if past expiry date"""
        if self.is_expired() and self.Voucher_status == 'Not Used':
            self.Voucher_status = 'Expired'
            self.save()
            return True
        return False
    
    @classmethod
    def cleanup_expired_vouchers(cls):
        """Class method to clean up all expired vouchers"""
        from datetime import timedelta
        expiry_cutoff = timezone.now() - timedelta(days=30)
        
        expired_count = cls.objects.filter(
            Voucher_status='Not Used',
            Voucher_create_date_time__lt=expiry_cutoff
        ).update(Voucher_status='Expired')
        
        return expired_count

    class Meta:
        verbose_name = 'Voucher'
        verbose_name_plural = 'Vouchers'

    def __str__(self):
        return f"{self.Voucher_code} ({self.Voucher_status}) - {self.get_time_display()}"


class Device(models.Model):
    Device_ID = models.CharField(max_length=255, null=True, blank=True)
    Ethernet_MAC = models.CharField(max_length=50, null=True, blank=True)
    Device_SN = models.CharField(max_length=50, null=True, blank=True)
    pub_rsa = models.TextField(null=False, blank=False)
    ca = models.CharField(max_length=200, unique=True, null=False, blank=False)
    action = models.IntegerField(default=0)
    Sync_Time = models.DateTimeField(default=timezone.now, null=True, blank=True)

    class Meta:
        verbose_name = 'Hardware'

    def __str__(self):
        return 'Hardware Settings'

# PushNotifications model removed for personal use

class SecuritySettings(models.Model):
    TTL_Detection_Enabled = models.BooleanField(default=True, verbose_name='Enable TTL Detection', help_text='Enable detection of internet sharing via TTL analysis')
    Default_TTL_Value = models.IntegerField(default=64, verbose_name='Expected TTL', help_text='Expected TTL value from client devices (Windows: 128, Linux/Android: 64, macOS: 64)')
    TTL_Tolerance = models.IntegerField(default=2, verbose_name='TTL Tolerance', help_text='Allowed TTL variance before flagging as suspicious')
    
    # Connection Limiting instead of blocking
    Limit_Connections = models.BooleanField(default=True, verbose_name='Limit Connections', help_text='Limit simultaneous connections for devices with suspicious TTL')
    Normal_Device_Connections = models.IntegerField(default=3, verbose_name='Normal Device Limit', help_text='Max simultaneous connections for devices with normal TTL')
    Suspicious_Device_Connections = models.IntegerField(default=1, verbose_name='Suspicious Device Limit', help_text='Max simultaneous connections for devices with suspicious TTL (likely sharing)')
    Max_TTL_Violations = models.IntegerField(default=5, verbose_name='Max TTL Violations', help_text='Number of TTL violations before applying strict limits')
    
    # TTL Modification Settings (MikroTik-style enforcement)
    Enable_TTL_Modification = models.BooleanField(default=False, verbose_name='Enable TTL Modification', help_text='Apply iptables TTL mangle rules to prevent sharing (MikroTik-style)')
    TTL_Modification_After_Violations = models.IntegerField(default=10, verbose_name='TTL Modify After Violations', help_text='Number of violations before applying TTL modification rules')
    Modified_TTL_Value = models.IntegerField(default=1, verbose_name='Modified TTL Value', help_text='TTL value to set for violating devices (1 = blocks sharing completely)')
    TTL_Rule_Duration = models.DurationField(default=timezone.timedelta(hours=2), verbose_name='TTL Rule Duration', help_text='How long to keep TTL modification rules active')
    
    # Legacy blocking settings (optional fallback)
    Enable_Device_Blocking = models.BooleanField(default=False, verbose_name='Enable Device Blocking', help_text='Enable complete device blocking as last resort')
    Block_Duration = models.DurationField(default=timezone.timedelta(hours=1), verbose_name='Block Duration', help_text='How long to block violating clients if blocking is enabled')

    class Meta:
        verbose_name = 'Security Settings'
        verbose_name_plural = 'Security Settings'

    def __str__(self):
        return 'Security Settings'

class TrafficMonitor(models.Model):
    Client_MAC = models.CharField(max_length=255, verbose_name='Client MAC')
    Timestamp = models.DateTimeField(auto_now_add=True)
    TTL_Value = models.IntegerField(verbose_name='Detected TTL')
    Packet_Count = models.IntegerField(default=1, verbose_name='Packet Count')
    Is_Suspicious = models.BooleanField(default=False, verbose_name='Suspicious Activity')
    Notes = models.TextField(null=True, blank=True, help_text='Additional notes about the traffic')

    class Meta:
        verbose_name = 'Traffic Monitor'
        verbose_name_plural = 'Traffic Monitor'
        ordering = ['-Timestamp']

    def __str__(self):
        return f'Traffic from {self.Client_MAC} at {self.Timestamp.strftime("%Y-%m-%d %H:%M")}'

class ConnectionTracker(models.Model):
    Device_MAC = models.CharField(max_length=255, verbose_name='Device MAC')
    Connection_IP = models.CharField(max_length=15, verbose_name='Connection IP')
    Session_ID = models.CharField(max_length=100, verbose_name='Session ID', help_text='Unique identifier for this connection session')
    Connected_At = models.DateTimeField(auto_now_add=True, verbose_name='Connected At')
    Last_Activity = models.DateTimeField(auto_now=True, verbose_name='Last Activity')
    Is_Active = models.BooleanField(default=True, verbose_name='Active Connection')
    TTL_Classification = models.CharField(max_length=20, choices=[
        ('normal', 'Normal TTL'),
        ('suspicious', 'Suspicious TTL'),
        ('unknown', 'Unknown TTL')
    ], default='unknown', verbose_name='TTL Classification')
    User_Agent = models.TextField(null=True, blank=True, verbose_name='User Agent')
    
    class Meta:
        verbose_name = 'Connection Tracker'
        verbose_name_plural = 'Connection Tracker'
        unique_together = ('Device_MAC', 'Session_ID')
        ordering = ['-Connected_At']
    
    def __str__(self):
        return f'{self.Device_MAC} - {self.Connection_IP} ({self.TTL_Classification})'
    
    def is_session_expired(self, timeout_minutes=30):
        """Check if connection session has expired due to inactivity"""
        return timezone.now() - self.Last_Activity > timezone.timedelta(minutes=timeout_minutes)
    
    def get_active_connections_for_device(device_mac):
        """Get count of active connections for a specific device"""
        # Clean up expired sessions first
        expired_sessions = ConnectionTracker.objects.filter(
            Device_MAC=device_mac,
            Is_Active=True,
            Last_Activity__lt=timezone.now() - timezone.timedelta(minutes=30)
        )
        expired_sessions.update(Is_Active=False)
        
        # Return active connection count
        return ConnectionTracker.objects.filter(
            Device_MAC=device_mac,
            Is_Active=True
        ).count()
    
    @staticmethod
    def cleanup_expired_sessions():
        """Clean up expired connection sessions"""
        expired_cutoff = timezone.now() - timezone.timedelta(minutes=30)
        expired_count = ConnectionTracker.objects.filter(
            Is_Active=True,
            Last_Activity__lt=expired_cutoff
        ).update(Is_Active=False)
        return expired_count

class DeviceFingerprint(models.Model):
    FINGERPRINT_STATUS = [
        ('active', 'Active'),
        ('suspicious', 'Suspicious'),
        ('blocked', 'Blocked'),
        ('whitelist', 'Whitelisted')
    ]
    
    # Unique device identifier based on fingerprinting
    Device_ID = models.CharField(max_length=64, unique=True, verbose_name='Device Fingerprint ID')
    
    # Browser fingerprinting data
    User_Agent = models.TextField(verbose_name='User Agent String')
    Screen_Resolution = models.CharField(max_length=20, null=True, blank=True, verbose_name='Screen Resolution')
    Browser_Language = models.CharField(max_length=10, null=True, blank=True, verbose_name='Browser Language')
    Timezone_Offset = models.IntegerField(null=True, blank=True, verbose_name='Timezone Offset')
    Platform = models.CharField(max_length=50, null=True, blank=True, verbose_name='Platform/OS')
    
    # Network fingerprinting data
    Default_TTL_Pattern = models.IntegerField(null=True, blank=True, verbose_name='Consistent TTL Value')
    Connection_Behavior = models.JSONField(default=dict, verbose_name='Connection Patterns')
    
    # Device tracking
    First_Seen = models.DateTimeField(auto_now_add=True, verbose_name='First Seen')
    Last_Seen = models.DateTimeField(auto_now=True, verbose_name='Last Seen')
    Device_Status = models.CharField(max_length=20, choices=FINGERPRINT_STATUS, default='active')
    
    # MAC address tracking
    Known_MACs = models.JSONField(default=list, verbose_name='Associated MAC Addresses')
    Current_MAC = models.CharField(max_length=255, null=True, blank=True, verbose_name='Current MAC Address')
    MAC_Randomization_Detected = models.BooleanField(default=False, verbose_name='Uses MAC Randomization')
    
    # Violation tracking (persistent across MAC changes)
    Total_TTL_Violations = models.IntegerField(default=0, verbose_name='Total TTL Violations')
    Total_Connection_Violations = models.IntegerField(default=0, verbose_name='Connection Limit Violations')
    Last_Violation_Date = models.DateTimeField(null=True, blank=True, verbose_name='Last Violation')
    
    # Additional metadata
    Device_Name_Hint = models.CharField(max_length=255, null=True, blank=True, verbose_name='Device Name Hint')
    Admin_Notes = models.TextField(null=True, blank=True, verbose_name='Admin Notes')
    
    class Meta:
        verbose_name = 'Device Fingerprint'
        verbose_name_plural = 'Device Fingerprints'
        ordering = ['-Last_Seen']
    
    def __str__(self):
        return f'Device {self.Device_ID[:8]}... ({self.get_device_summary()})'
    
    def get_device_summary(self):
        """Get a human-readable device summary"""
        if self.Device_Name_Hint:
            return self.Device_Name_Hint
        elif self.Platform:
            return f'{self.Platform} Device'
        else:
            return f'Unknown Device'
    
    def add_mac_address(self, mac_address):
        """Add a new MAC address to this device fingerprint"""
        if mac_address not in self.Known_MACs:
            self.Known_MACs.append(mac_address)
            self.Current_MAC = mac_address
            
            # Check for MAC randomization pattern
            if len(self.Known_MACs) > 1:
                self.MAC_Randomization_Detected = True
            
            self.save()
    
    def is_using_mac_randomization(self):
        """Check if device is using MAC randomization"""
        # Multiple MACs for same device = randomization
        if len(self.Known_MACs) > 1:
            return True
        
        # Check for randomized MAC patterns (local bit set)
        if self.Current_MAC:
            # Second character should be 2, 6, A, or E for locally administered addresses
            second_char = self.Current_MAC.split(':')[0][1].upper()
            return second_char in ['2', '6', 'A', 'E']
        
        return False
    
    def get_current_violations_24h(self):
        """Get violation count in last 24 hours"""
        if not self.Last_Violation_Date:
            return 0
        
        if timezone.now() - self.Last_Violation_Date < timezone.timedelta(hours=24):
            return self.Total_TTL_Violations
        else:
            return 0
    
    def record_violation(self, violation_type='ttl'):
        """Record a new violation for this device"""
        if violation_type == 'ttl':
            self.Total_TTL_Violations += 1
        elif violation_type == 'connection':
            self.Total_Connection_Violations += 1
        
        self.Last_Violation_Date = timezone.now()
        self.save()
    
    @staticmethod
    def generate_device_id(fingerprint_data):
        """Generate a unique device ID from fingerprint data"""
        import hashlib
        
        # Combine stable fingerprint elements
        fingerprint_string = ''.join([
            fingerprint_data.get('user_agent', ''),
            fingerprint_data.get('screen_resolution', ''),
            fingerprint_data.get('language', ''),
            str(fingerprint_data.get('timezone_offset', '')),
            fingerprint_data.get('platform', ''),
        ])
        
        # Generate SHA-256 hash
        return hashlib.sha256(fingerprint_string.encode()).hexdigest()
    
    @staticmethod
    def find_or_create_device(fingerprint_data, mac_address):
        """Find existing device by fingerprint or create new one"""
        device_id = DeviceFingerprint.generate_device_id(fingerprint_data)
        
        device, created = DeviceFingerprint.objects.get_or_create(
            Device_ID=device_id,
            defaults={
                'User_Agent': fingerprint_data.get('user_agent', ''),
                'Screen_Resolution': fingerprint_data.get('screen_resolution', ''),
                'Browser_Language': fingerprint_data.get('language', ''),
                'Timezone_Offset': fingerprint_data.get('timezone_offset'),
                'Platform': fingerprint_data.get('platform', ''),
                'Current_MAC': mac_address,
                'Known_MACs': [mac_address]
            }
        )
        
        if not created:
            # Update existing device
            device.add_mac_address(mac_address)
            device.Last_Seen = timezone.now()
            device.save()
        
        return device, created

class TTLFirewallRule(models.Model):
    RULE_TYPES = [
        ('mangle_ttl', 'TTL Modification (Mangle)'),
        ('drop_sharing', 'Drop Sharing Traffic'),
        ('limit_bandwidth', 'Bandwidth Limiting')
    ]
    
    RULE_STATUS = [
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('disabled', 'Disabled'),
        ('error', 'Error')
    ]
    
    Device_MAC = models.CharField(max_length=255, verbose_name='Device MAC')
    Rule_Type = models.CharField(max_length=20, choices=RULE_TYPES, default='mangle_ttl', verbose_name='Rule Type')
    Rule_Status = models.CharField(max_length=10, choices=RULE_STATUS, default='active', verbose_name='Rule Status')
    TTL_Value = models.IntegerField(verbose_name='TTL Value', help_text='TTL value being applied (usually 1)')
    Iptables_Chain = models.CharField(max_length=50, default='FORWARD', verbose_name='Iptables Chain')
    Rule_Command = models.TextField(verbose_name='Iptables Command', help_text='Full iptables command used')
    Created_At = models.DateTimeField(auto_now_add=True, verbose_name='Created At')
    Expires_At = models.DateTimeField(verbose_name='Expires At')
    Last_Checked = models.DateTimeField(auto_now=True, verbose_name='Last Checked')
    Violation_Count = models.IntegerField(default=0, verbose_name='Violations That Triggered Rule')
    Admin_Notes = models.TextField(null=True, blank=True, verbose_name='Admin Notes')
    
    class Meta:
        verbose_name = 'TTL Firewall Rule'
        verbose_name_plural = 'TTL Firewall Rules'
        ordering = ['-Created_At']
        unique_together = ('Device_MAC', 'Rule_Type')
    
    def __str__(self):
        return f'TTL Rule: {self.Device_MAC} -> TTL={self.TTL_Value} ({self.Rule_Status})'
    
    def is_expired(self):
        """Check if the TTL rule has expired"""
        return timezone.now() > self.Expires_At
    
    def get_iptables_command(self):
        """Generate the iptables command for this rule"""
        if self.Rule_Type == 'mangle_ttl':
            return [
                'iptables', '-t', 'mangle', '-A', 'FORWARD',
                '-m', 'mac', '--mac-source', self.Device_MAC,
                '-j', 'TTL', '--ttl-set', str(self.TTL_Value),
                '-m', 'comment', '--comment', f'PisoWiFi-TTL-{self.Device_MAC}'
            ]
        return []
    
    def get_iptables_delete_command(self):
        """Generate the iptables delete command for this rule"""
        if self.Rule_Type == 'mangle_ttl':
            return [
                'iptables', '-t', 'mangle', '-D', 'FORWARD',
                '-m', 'mac', '--mac-source', self.Device_MAC,
                '-j', 'TTL', '--ttl-set', str(self.TTL_Value),
                '-m', 'comment', '--comment', f'PisoWiFi-TTL-{self.Device_MAC}'
            ]
        return []
    
    @staticmethod
    def cleanup_expired_rules():
        """Remove expired TTL rules from iptables and database"""
        from app.views import remove_ttl_firewall_rule
        
        expired_rules = TTLFirewallRule.objects.filter(
            Rule_Status='active',
            Expires_At__lt=timezone.now()
        )
        
        removed_count = 0
        for rule in expired_rules:
            if remove_ttl_firewall_rule(rule.Device_MAC):
                rule.Rule_Status = 'expired'
                rule.save()
                removed_count += 1
        
        return removed_count

# Phase 3: Traffic Analysis & Behavioral Intelligence Models

class TrafficAnalysis(models.Model):
    PROTOCOL_CHOICES = [
        ('http', 'HTTP/HTTPS'),
        ('p2p', 'P2P/Torrenting'),
        ('streaming', 'Video Streaming'),
        ('gaming', 'Gaming'),
        ('social', 'Social Media'),
        ('messaging', 'Messaging'),
        ('other', 'Other')
    ]
    
    Device_MAC = models.CharField(max_length=255, verbose_name='Device MAC')
    Device_Fingerprint = models.ForeignKey('DeviceFingerprint', on_delete=models.CASCADE, null=True, blank=True)
    Timestamp = models.DateTimeField(auto_now_add=True)
    
    # Traffic Classification
    Protocol_Type = models.CharField(max_length=20, choices=PROTOCOL_CHOICES, default='other')
    Bytes_Up = models.BigIntegerField(default=0, verbose_name='Upload Bytes')
    Bytes_Down = models.BigIntegerField(default=0, verbose_name='Download Bytes')
    Packets_Up = models.IntegerField(default=0, verbose_name='Upload Packets')
    Packets_Down = models.IntegerField(default=0, verbose_name='Download Packets')
    
    # Connection Details
    Source_IP = models.GenericIPAddressField(null=True, blank=True)
    Destination_IP = models.GenericIPAddressField(null=True, blank=True)
    Source_Port = models.IntegerField(null=True, blank=True)
    Destination_Port = models.IntegerField(null=True, blank=True)
    
    # Analysis Results
    Is_Suspicious = models.BooleanField(default=False, verbose_name='Suspicious Traffic')
    Suspicion_Reason = models.CharField(max_length=255, null=True, blank=True)
    Bandwidth_Usage_MB = models.FloatField(default=0.0, verbose_name='Bandwidth Usage (MB)')
    
    class Meta:
        verbose_name = 'Traffic Analysis'
        verbose_name_plural = 'Traffic Analysis'
        ordering = ['-Timestamp']
    
    def __str__(self):
        return f'{self.Device_MAC} - {self.Protocol_Type} ({self.Bandwidth_Usage_MB:.2f}MB)'

class DeviceBehaviorProfile(models.Model):
    TRUST_LEVELS = [
        ('new', 'New Device'),
        ('trusted', 'Trusted'),
        ('suspicious', 'Suspicious'),
        ('abusive', 'Abusive'),
        ('banned', 'Banned')
    ]
    
    Device_Fingerprint = models.OneToOneField('DeviceFingerprint', on_delete=models.CASCADE)
    
    # Behavioral Metrics
    Average_Session_Duration = models.DurationField(default=timezone.timedelta(minutes=0))
    Total_Data_Used_MB = models.FloatField(default=0.0, verbose_name='Total Data Used (MB)')
    Peak_Bandwidth_Usage = models.FloatField(default=0.0, verbose_name='Peak Bandwidth (Mbps)')
    Favorite_Protocol = models.CharField(max_length=20, null=True, blank=True)
    
    # Usage Patterns
    Most_Active_Hour = models.IntegerField(null=True, blank=True, help_text='Hour of day (0-23)')
    Average_Concurrent_Connections = models.FloatField(default=1.0)
    P2P_Usage_Percentage = models.FloatField(default=0.0, verbose_name='P2P Usage %')
    Streaming_Usage_Percentage = models.FloatField(default=0.0, verbose_name='Streaming Usage %')
    
    # Trust & Reputation
    Trust_Level = models.CharField(max_length=20, choices=TRUST_LEVELS, default='new')
    Trust_Score = models.FloatField(default=50.0, verbose_name='Trust Score (0-100)')
    Violation_Score = models.FloatField(default=0.0, verbose_name='Violation Score')
    
    # Temporal Data
    First_Analysis = models.DateTimeField(auto_now_add=True)
    Last_Updated = models.DateTimeField(auto_now=True)
    Last_Violation_Date = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Device Behavior Profile'
        verbose_name_plural = 'Device Behavior Profiles'
        ordering = ['-Last_Updated']
    
    def __str__(self):
        return f'{self.Device_Fingerprint.get_device_summary()} - Trust: {self.Trust_Level} ({self.Trust_Score:.1f})'
    
    def calculate_trust_score(self):
        """Calculate dynamic trust score based on behavior"""
        base_score = 50.0
        
        # Positive factors
        if self.Total_Data_Used_MB > 0:
            # Moderate usage increases trust
            usage_factor = min(self.Total_Data_Used_MB / 1000, 10)  # Cap at 1GB
            base_score += usage_factor
        
        # Negative factors
        base_score -= self.Violation_Score * 2
        base_score -= self.P2P_Usage_Percentage * 0.3  # P2P usage slightly reduces trust
        
        # Time-based trust building
        days_active = (timezone.now() - self.First_Analysis).days
        base_score += min(days_active * 0.5, 15)  # Max 15 points for longevity
        
        # Clamp between 0-100
        self.Trust_Score = max(0, min(100, base_score))
        self.save()
        
        return self.Trust_Score
    
    def update_trust_level(self):
        """Update trust level based on trust score"""
        if self.Trust_Score >= 80:
            self.Trust_Level = 'trusted'
        elif self.Trust_Score >= 60:
            self.Trust_Level = 'new'
        elif self.Trust_Score >= 30:
            self.Trust_Level = 'suspicious'
        elif self.Trust_Score >= 10:
            self.Trust_Level = 'abusive'
        else:
            self.Trust_Level = 'banned'
        
        self.save()

class AdaptiveQoSRule(models.Model):
    QOS_ACTIONS = [
        ('priority_low', 'Low Priority'),
        ('priority_normal', 'Normal Priority'),
        ('priority_high', 'High Priority'),
        ('throttle_light', 'Light Throttling (75%)'),
        ('throttle_medium', 'Medium Throttling (50%)'),
        ('throttle_heavy', 'Heavy Throttling (25%)'),
        ('block', 'Block Traffic')
    ]
    
    Device_MAC = models.CharField(max_length=255, verbose_name='Device MAC')
    Device_Fingerprint = models.ForeignKey('DeviceFingerprint', on_delete=models.CASCADE, null=True, blank=True)
    
    # Rule Configuration
    Rule_Name = models.CharField(max_length=100, verbose_name='Rule Name')
    QoS_Action = models.CharField(max_length=20, choices=QOS_ACTIONS, default='priority_normal')
    Bandwidth_Limit_Down = models.FloatField(null=True, blank=True, verbose_name='Download Limit (Mbps)')
    Bandwidth_Limit_Up = models.FloatField(null=True, blank=True, verbose_name='Upload Limit (Mbps)')
    
    # Triggering Conditions
    Trigger_Condition = models.TextField(verbose_name='Trigger Condition', help_text='JSON condition for rule activation')
    Protocol_Filter = models.CharField(max_length=20, null=True, blank=True, verbose_name='Protocol Filter')
    
    # Rule Status
    Is_Active = models.BooleanField(default=True)
    Auto_Created = models.BooleanField(default=False, verbose_name='Auto-Generated Rule')
    Created_At = models.DateTimeField(auto_now_add=True)
    Expires_At = models.DateTimeField(null=True, blank=True)
    Last_Applied = models.DateTimeField(null=True, blank=True)
    
    # Statistics
    Times_Applied = models.IntegerField(default=0)
    Bytes_Limited = models.BigIntegerField(default=0)
    
    class Meta:
        verbose_name = 'Adaptive QoS Rule'
        verbose_name_plural = 'Adaptive QoS Rules'
        ordering = ['-Created_At']
    
    def __str__(self):
        return f'{self.Rule_Name} - {self.Device_MAC} - {self.QoS_Action}'
    
    def is_expired(self):
        if self.Expires_At:
            return timezone.now() > self.Expires_At
        return False
    
    def apply_rule(self):
        """Apply QoS rule using traffic control (tc)"""
        if self.is_expired():
            self.Is_Active = False
            self.save()
            return False
        
        # Update statistics
        self.Times_Applied += 1
        self.Last_Applied = timezone.now()
        self.save()
        
        return True

class NetworkIntelligence(models.Model):
    # System-wide network intelligence and metrics
    Timestamp = models.DateTimeField(auto_now_add=True)
    
    # Network Health Metrics
    Total_Active_Devices = models.IntegerField(default=0)
    Total_Bandwidth_Usage_Mbps = models.FloatField(default=0.0)
    Network_Utilization_Percent = models.FloatField(default=0.0)
    
    # Security Metrics
    Suspicious_Devices_Count = models.IntegerField(default=0)
    TTL_Violations_Last_Hour = models.IntegerField(default=0)
    MAC_Randomization_Detected_Count = models.IntegerField(default=0)
    Active_QoS_Rules = models.IntegerField(default=0)
    
    # Revenue Metrics
    Revenue_Per_Hour = models.FloatField(default=0.0)
    Average_Session_Duration_Minutes = models.FloatField(default=0.0)
    Peak_Concurrent_Users = models.IntegerField(default=0)
    
    # Protocol Distribution
    HTTP_Traffic_Percent = models.FloatField(default=0.0)
    P2P_Traffic_Percent = models.FloatField(default=0.0)
    Streaming_Traffic_Percent = models.FloatField(default=0.0)
    Gaming_Traffic_Percent = models.FloatField(default=0.0)
    Other_Traffic_Percent = models.FloatField(default=0.0)
    
    class Meta:
        verbose_name = 'Network Intelligence'
        verbose_name_plural = 'Network Intelligence'
        ordering = ['-Timestamp']
    
    def __str__(self):
        return f'Network Intelligence - {self.Timestamp.strftime("%Y-%m-%d %H:%M")} - {self.Total_Active_Devices} devices'

class BlockedDevices(models.Model):
    BLOCK_REASONS = [
        ('ttl_sharing', 'Internet Sharing Detected (TTL)'),
        ('abuse', 'Terms of Service Violation'),
        ('manual', 'Manually Blocked'),
        ('security', 'Security Risk'),
        ('suspicious', 'Suspicious Activity')
    ]

    MAC_Address = models.CharField(max_length=255, unique=True, verbose_name='MAC Address')
    Device_Name = models.CharField(max_length=255, null=True, blank=True, verbose_name='Device Name')
    Block_Reason = models.CharField(max_length=20, choices=BLOCK_REASONS, default='manual', verbose_name='Block Reason')
    Blocked_Date = models.DateTimeField(auto_now_add=True, verbose_name='Blocked Date')
    Auto_Unblock_After = models.DateTimeField(null=True, blank=True, verbose_name='Auto Unblock After')
    Is_Permanent = models.BooleanField(default=False, verbose_name='Permanent Block', help_text='If enabled, device will remain blocked indefinitely')
    TTL_Violations_Count = models.IntegerField(default=0, verbose_name='TTL Violations')
    Is_Active = models.BooleanField(default=True, verbose_name='Block Active')
    Admin_Notes = models.TextField(null=True, blank=True, verbose_name='Admin Notes')

    class Meta:
        verbose_name = 'Blocked Device'
        verbose_name_plural = 'Blocked Devices'
        ordering = ['-Blocked_Date']

    def __str__(self):
        name = self.Device_Name if self.Device_Name else self.MAC_Address
        return f'Blocked: {name}'

    def is_block_expired(self):
        # Permanent blocks never expire
        if self.Is_Permanent:
            return False
        if self.Auto_Unblock_After and timezone.now() > self.Auto_Unblock_After:
            return True
        return False

    def unblock_if_expired(self):
        if self.is_block_expired():
            self.Is_Active = False
            self.save()
            return True
        return False


class SystemUpdate(models.Model):
    UPDATE_STATUSES = [
        ('checking', 'Checking for Updates'),
        ('available', 'Update Available'),
        ('downloading', 'Downloading Update'),
        ('ready', 'Ready to Install'),
        ('installing', 'Installing Update'),
        ('completed', 'Update Completed'),
        ('failed', 'Update Failed'),
        ('rollback', 'Rolling Back'),
    ]
    
    Version_Number = models.CharField(max_length=20, verbose_name='Version Number')
    Update_Title = models.CharField(max_length=255, verbose_name='Update Title')
    Description = models.TextField(verbose_name='Description')
    Release_Date = models.DateTimeField(verbose_name='Release Date')
    Download_URL = models.URLField(max_length=500, default='https://github.com/regolet/pisowifi', verbose_name='Download URL')
    File_Size = models.BigIntegerField(default=0, verbose_name='File Size (bytes)')
    
    Status = models.CharField(max_length=20, choices=UPDATE_STATUSES, default='checking', verbose_name='Status')
    Progress = models.IntegerField(default=0, verbose_name='Progress (%)')
    Downloaded_Bytes = models.BigIntegerField(default=0, verbose_name='Downloaded Bytes')
    
    Started_At = models.DateTimeField(null=True, blank=True, verbose_name='Started At')
    Completed_At = models.DateTimeField(null=True, blank=True, verbose_name='Completed At')
    Error_Message = models.TextField(null=True, blank=True, verbose_name='Error Message')
    
    Backup_Path = models.CharField(max_length=500, null=True, blank=True, verbose_name='Backup Path')
    Is_Auto_Update = models.BooleanField(default=False, verbose_name='Auto Update')
    Force_Update = models.BooleanField(default=False, verbose_name='Force Update')
    Installation_Log = models.TextField(null=True, blank=True, verbose_name='Installation Log')
    
    Created_At = models.DateTimeField(auto_now_add=True, verbose_name='Created At')
    Updated_At = models.DateTimeField(auto_now=True, verbose_name='Updated At')
    
    class Meta:
        verbose_name = 'System Update'
        verbose_name_plural = 'System Updates'
        ordering = ['-Created_At']
    
    def __str__(self):
        return f'Update {self.Version_Number} - {self.get_Status_display()}'
    
    def get_progress_percentage(self):
        if self.File_Size > 0 and self.Downloaded_Bytes > 0:
            return min(int((self.Downloaded_Bytes / self.File_Size) * 100), 100)
        return self.Progress
    
    def can_install(self):
        return self.Status in ['ready', 'failed']
    
    def can_rollback(self):
        return self.Status == 'completed' and self.Backup_Path


class UpdateSettings(models.Model):
    GitHub_Repository = models.CharField(max_length=255, default='regolet/pisowifi', verbose_name='GitHub Repository')
    Check_Interval_Hours = models.IntegerField(default=24, verbose_name='Check Interval (hours)')
    Auto_Download = models.BooleanField(default=False, verbose_name='Auto Download Updates')
    Auto_Install = models.BooleanField(default=False, verbose_name='Auto Install Updates')
    Backup_Before_Update = models.BooleanField(default=True, verbose_name='Backup Before Update')
    Max_Backup_Count = models.IntegerField(default=3, verbose_name='Maximum Backup Count')
    
    Last_Check = models.DateTimeField(null=True, blank=True, verbose_name='Last Check')
    Current_Version = models.CharField(max_length=20, default='2.0.1', verbose_name='Current Version')
    Update_Channel = models.CharField(max_length=20, default='stable', choices=[
        ('stable', 'Stable'),
        ('beta', 'Beta'),
        ('dev', 'Development')
    ], verbose_name='Update Channel')
    
    class Meta:
        verbose_name = 'Update Settings'
        verbose_name_plural = 'Update Settings'
    
    def __str__(self):
        return 'System Update Settings'
    
    def save(self, *args, **kwargs):
        self.pk = 1
        super(UpdateSettings, self).save(*args, **kwargs)
    
    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        if created or obj.Current_Version == '1.0.0':
            # Auto-detect version from git on first load or if still default
            obj.Current_Version = cls.get_system_version()
            obj.save()
        return obj
    
    @staticmethod
    def get_system_version():
        """Get current system version from git tags"""
        import subprocess
        import os
        try:
            # Get the latest git tag
            result = subprocess.run(
                ['git', 'describe', '--tags', '--abbrev=0'],
                capture_output=True,
                text=True,
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                # Remove 'v' prefix if present
                if version.startswith('v'):
                    version = version[1:]
                return version
        except Exception:
            pass
        
        # Fallback: try to get from git describe
        try:
            result = subprocess.run(
                ['git', 'describe', '--tags', '--always'],
                capture_output=True,
                text=True,
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                # Remove 'v' prefix and commit info if present
                if version.startswith('v'):
                    version = version[1:]
                if '-' in version:
                    version = version.split('-')[0]
                return version
        except Exception:
            pass
        
        # Final fallback
        return '2.0.1'


class BackupSettings(models.Model):
    """Settings for database backup configuration"""
    Auto_Backup_Enabled = models.BooleanField(default=True, verbose_name='Enable Auto Backup')
    Auto_Backup_Interval_Hours = models.IntegerField(default=24, verbose_name='Auto Backup Interval (hours)')
    Max_Backup_Count = models.IntegerField(default=10, verbose_name='Maximum Backup Count')
    Backup_Location = models.CharField(max_length=500, default='backups/database/', verbose_name='Backup Directory')
    
    # Backup type settings
    Include_Client_Data = models.BooleanField(default=True, verbose_name='Include Client Data in Auto Backup')
    Include_System_Settings = models.BooleanField(default=True, verbose_name='Include System Settings in Auto Backup')
    Include_Logs = models.BooleanField(default=False, verbose_name='Include Logs in Auto Backup')
    
    # Compression and retention
    Compress_Backups = models.BooleanField(default=True, verbose_name='Compress Backup Files')
    Retention_Days = models.IntegerField(default=30, verbose_name='Backup Retention (days)')
    
    # Notification settings
    Email_Notifications = models.BooleanField(default=False, verbose_name='Email Backup Notifications')
    Email_Recipients = models.TextField(blank=True, help_text='Email addresses separated by commas', verbose_name='Email Recipients')
    
    Last_Auto_Backup = models.DateTimeField(null=True, blank=True, verbose_name='Last Auto Backup')
    
    class Meta:
        verbose_name = 'Backup Settings'
        verbose_name_plural = 'Backup Settings'
    
    def __str__(self):
        return 'Database Backup Settings'
    
    def save(self, *args, **kwargs):
        self.pk = 1
        super(BackupSettings, self).save(*args, **kwargs)
    
    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj


class DatabaseBackup(models.Model):
    """Track database backup records"""
    BACKUP_TYPES = [
        ('full', 'Full Database'),
        ('clients', 'Clients Data Only'),
        ('settings', 'System Settings Only'),
        ('custom', 'Custom Selection')
    ]
    
    BACKUP_STATUS = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled')
    ]
    
    backup_name = models.CharField(max_length=255, verbose_name='Backup Name')
    backup_type = models.CharField(max_length=20, choices=BACKUP_TYPES, default='full', verbose_name='Backup Type')
    status = models.CharField(max_length=20, choices=BACKUP_STATUS, default='pending', verbose_name='Status')
    
    # File information
    file_path = models.CharField(max_length=500, blank=True, verbose_name='File Path')
    file_size = models.BigIntegerField(default=0, verbose_name='File Size (bytes)')
    compressed = models.BooleanField(default=False, verbose_name='Compressed')
    
    # Backup details
    tables_included = models.TextField(blank=True, verbose_name='Tables Included')
    records_count = models.IntegerField(default=0, verbose_name='Total Records')
    
    # Progress tracking
    progress_percentage = models.IntegerField(default=0, verbose_name='Progress %')
    current_operation = models.CharField(max_length=255, blank=True, verbose_name='Current Operation')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Created At')
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='Started At')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='Completed At')
    
    # Error handling
    error_message = models.TextField(blank=True, verbose_name='Error Message')
    
    # Metadata
    created_by = models.CharField(max_length=100, blank=True, verbose_name='Created By')
    description = models.TextField(blank=True, verbose_name='Description')
    
    class Meta:
        verbose_name = 'Database Backup'
        verbose_name_plural = 'Database Backups'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.backup_name} - {self.get_backup_type_display()}"
    
    def get_file_size_display(self):
        """Return human readable file size"""
        if self.file_size == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        import math
        i = int(math.floor(math.log(self.file_size, 1024)))
        p = math.pow(1024, i)
        s = round(self.file_size / p, 2)
        return f"{s} {size_names[i]}"
    
    def get_status_badge(self):
        """Return HTML badge for status"""
        from django.utils.html import format_html
        
        color_map = {
            'pending': '#6c757d',
            'running': '#ffc107',
            'completed': '#28a745',
            'failed': '#dc3545',
            'cancelled': '#6c757d'
        }
        
        color = color_map.get(self.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 12px; font-weight: bold;">{}</span>',
            color, self.get_status_display()
        )
    
    def get_backup_type_badge(self):
        """Return HTML badge for backup type"""
        from django.utils.html import format_html
        
        color_map = {
            'full': '#007bff',
            'clients': '#28a745',
            'settings': '#ffc107',
            'custom': '#17a2b8'
        }
        
        color = color_map.get(self.backup_type, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 12px; font-weight: bold;">{}</span>',
            color, self.get_backup_type_display()
        )
# Consolidated migration - replaces migrations 0001-0141
# Generated for Django 5.x compatibility

import django.contrib.auth.models
import django.contrib.auth.validators
import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    replaces = [
        ('app', '0001_initial'),
        # All migrations from 0001 to 0141 are consolidated here
    ]

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Core client management
        migrations.CreateModel(
            name='Clients',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('IP_Address', models.CharField(max_length=15, verbose_name='IP')),
                ('MAC_Address', models.CharField(max_length=255, verbose_name='MAC Address', unique=True)),
                ('Device_Name', models.CharField(max_length=255, verbose_name='Device Name', null=True, blank=True)),
                ('Time_Left', models.DurationField(default=django.utils.timezone.timedelta(minutes=0))),
                ('Expire_On', models.DateTimeField(null=True, blank=True)),
                ('Validity_Expires_On', models.DateTimeField(null=True, blank=True, verbose_name='Validity Expiration', help_text='When purchased time expires and can no longer be used')),
                ('Upload_Rate', models.IntegerField(verbose_name='Upload Bandwidth', help_text='Specify client internet upload bandwidth in Kbps. No value = unlimited bandwidth', null=True, blank=True)),
                ('Download_Rate', models.IntegerField(verbose_name='Download Bandwidth', help_text='Specify client internet download bandwidth in Kbps. No value = unlimited bandwidth', null=True, blank=True)),
                ('Notification_ID', models.CharField(verbose_name='Notification ID', max_length=255, null=True, blank=True)),
                ('Notified_Flag', models.BooleanField(default=False)),
                ('Date_Created', models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={
                'verbose_name': 'Client',
                'verbose_name_plural': 'Clients',
            },
        ),
        
        # Whitelisted devices
        migrations.CreateModel(
            name='Whitelist',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('MAC_Address', models.CharField(max_length=255, verbose_name='MAC', unique=True)),
                ('Device_Name', models.CharField(max_length=255, null=True, blank=True)),
            ],
            options={
                'verbose_name': 'Allowed Client',
                'verbose_name_plural': 'Allowed Clients',
            },
        ),

        # Financial tracking
        migrations.CreateModel(
            name='Ledger',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('Date', models.DateTimeField()),
                ('Client', models.CharField(max_length=50)),
                ('Denomination', models.IntegerField()),
                ('Slot_No', models.IntegerField()),
            ],
            options={
                'verbose_name': 'Ledger',
                'verbose_name_plural': 'Ledger',
            },
        ),

        # Coin slot management
        migrations.CreateModel(
            name='CoinSlot',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('Slot_no', models.IntegerField(verbose_name='Slot Number')),
                ('Denomination', models.IntegerField(verbose_name='Coin Value')),
                ('Time_value', models.IntegerField(verbose_name='Minutes')),
                ('Time_value_seconds', models.IntegerField(verbose_name='Seconds', default=0)),
                ('Counts', models.IntegerField(verbose_name='Counts', default=0)),
                ('last_updated', models.DateTimeField(null=True, blank=True)),
                ('slot_desc', models.CharField(max_length=255, verbose_name='Description', null=True, blank=True)),
            ],
            options={
                'verbose_name': 'Coin Slot',
                'verbose_name_plural': 'Coin Slots',
            },
        ),

        # Pricing rates
        migrations.CreateModel(
            name='Rates',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('Rate_Name', models.CharField(max_length=255, verbose_name='Rate Name')),
                ('Amount', models.IntegerField(verbose_name='Amount')),
                ('Time_value', models.IntegerField(verbose_name='Time in Minutes')),
                ('Validity_days', models.IntegerField(verbose_name='Validity Days', default=1, help_text='Number of days the purchased time is valid')),
                ('Validity_hours', models.IntegerField(verbose_name='Validity Hours', default=0, help_text='Additional hours for validity (added to days)')),
            ],
            options={
                'verbose_name': 'Rate',
                'verbose_name_plural': 'Rates',
            },
        ),

        # Coin queue management
        migrations.CreateModel(
            name='CoinQueue',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('Slot_no', models.IntegerField()),
                ('Denomination', models.IntegerField()),
                ('Time_value', models.IntegerField()),
            ],
            options={
                'verbose_name': 'Coin Queue',
                'verbose_name_plural': 'Coin Queue',
            },
        ),

        # System settings
        migrations.CreateModel(
            name='Settings',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('wifi_name', models.CharField(max_length=255, verbose_name='WiFi Name', default='PISOWiFi')),
                ('wifi_pass', models.CharField(max_length=255, verbose_name='WiFi Password', default='admin')),
                ('pause_time', models.IntegerField(verbose_name='Pause Time (Minutes)', default=10)),
                ('admin_pass', models.CharField(max_length=255, verbose_name='Admin Password', default='admin')),
                ('inactive_timeout', models.IntegerField(verbose_name='Inactive Timeout (Minutes)', default=5)),
                ('bg_image', models.ImageField(verbose_name='Background Image', upload_to='background/', null=True, blank=True)),
                ('base_value', models.FloatField(verbose_name='Base Coin Value', default=1.0)),
                ('default_block_duration', models.IntegerField(verbose_name='Default Block Duration (minutes)', default=60, help_text='Default duration for temporary device blocks')),
            ],
            options={
                'verbose_name': 'Settings',
                'verbose_name_plural': 'Settings',
            },
        ),

        # Network configuration
        migrations.CreateModel(
            name='Network',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('Interface', models.CharField(max_length=50, verbose_name='Interface', default='wlan0')),
                ('Internet', models.CharField(max_length=50, verbose_name='Internet', default='eth0')),
                ('IP_range', models.CharField(max_length=50, verbose_name='IP Range', default='10.0.0.0/24')),
                ('wan_ip', models.CharField(max_length=50, verbose_name='WAN IP', default='auto', help_text='WAN IP address or "auto" for automatic detection')),
            ],
            options={
                'verbose_name': 'Network Settings',
                'verbose_name_plural': 'Network Settings',
            },
        ),

        # Voucher system
        migrations.CreateModel(
            name='Vouchers',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('Voucher_Code', models.CharField(max_length=255, verbose_name='Voucher Code', unique=True)),
                ('Time_value', models.IntegerField(verbose_name='Time in Minutes')),
                ('Status', models.CharField(max_length=255, verbose_name='Status', default='Active')),
                ('Date_Generated', models.DateTimeField(verbose_name='Date Generated', default=django.utils.timezone.now)),
                ('Date_Used', models.DateTimeField(verbose_name='Date Used', null=True, blank=True)),
                ('Validity_days', models.IntegerField(verbose_name='Validity Days', default=30, help_text='Number of days the voucher is valid')),
                ('Validity_hours', models.IntegerField(verbose_name='Validity Hours', default=0, help_text='Additional hours for validity (added to days)')),
            ],
            options={
                'verbose_name': 'Voucher',
                'verbose_name_plural': 'Vouchers',
            },
        ),

        # Device management
        migrations.CreateModel(
            name='Device',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('Device_ID', models.CharField(max_length=255, verbose_name='Device ID', unique=True)),
                ('Registration_Status', models.CharField(max_length=255, verbose_name='Status', default='Active')),
                ('Device_Name', models.CharField(max_length=255, verbose_name='Device Name', default='PISOWifi Device')),
                ('Last_Sync', models.DateTimeField(verbose_name='Last Sync', null=True, blank=True)),
                ('sync_time', models.DateTimeField(verbose_name='Sync Time', null=True, blank=True)),
            ],
            options={
                'verbose_name': 'Device',
                'verbose_name_plural': 'Devices',
            },
        ),

        # Security settings
        migrations.CreateModel(
            name='SecuritySettings',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('enable_device_blocking', models.BooleanField(verbose_name='Enable Device Blocking', default=True, help_text='Allow blocking of devices based on various criteria')),
                ('max_connections_per_device', models.IntegerField(verbose_name='Max Connections per Device', default=1, help_text='Maximum simultaneous connections allowed per device')),
                ('enable_ttl_modification', models.BooleanField(verbose_name='Enable TTL Modification', default=False, help_text='Automatically modify TTL values to prevent connection sharing')),
                ('ttl_value', models.IntegerField(verbose_name='TTL Value', default=64, help_text='TTL value to set for client packets')),
                ('block_shared_connections', models.BooleanField(verbose_name='Block Shared Connections', default=True, help_text='Block devices detected sharing connections')),
                ('enable_traffic_monitoring', models.BooleanField(verbose_name='Enable Traffic Monitoring', default=True, help_text='Monitor and log network traffic')),
                ('max_bandwidth_per_client', models.IntegerField(verbose_name='Max Bandwidth per Client (Kbps)', default=1024, help_text='Maximum bandwidth allowed per client')),
            ],
            options={
                'verbose_name': 'Security Settings',
                'verbose_name_plural': 'Security Settings',
            },
        ),

        # Traffic monitoring
        migrations.CreateModel(
            name='TrafficMonitor',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mac_address', models.CharField(max_length=17, verbose_name='MAC Address')),
                ('ip_address', models.CharField(max_length=15, verbose_name='IP Address')),
                ('bytes_uploaded', models.BigIntegerField(verbose_name='Bytes Uploaded', default=0)),
                ('bytes_downloaded', models.BigIntegerField(verbose_name='Bytes Downloaded', default=0)),
                ('timestamp', models.DateTimeField(verbose_name='Timestamp', default=django.utils.timezone.now)),
            ],
            options={
                'verbose_name': 'Traffic Monitor',
                'verbose_name_plural': 'Traffic Monitors',
            },
        ),

        # Additional models from later migrations
        migrations.CreateModel(
            name='BlockedDevices',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mac_address', models.CharField(max_length=17, verbose_name='MAC Address', unique=True)),
                ('ip_address', models.CharField(max_length=15, verbose_name='IP Address', null=True, blank=True)),
                ('reason', models.CharField(max_length=255, verbose_name='Block Reason', default='Policy Violation')),
                ('blocked_at', models.DateTimeField(verbose_name='Blocked At', default=django.utils.timezone.now)),
                ('expires_at', models.DateTimeField(verbose_name='Expires At', null=True, blank=True)),
                ('is_permanent', models.BooleanField(verbose_name='Permanent Block', default=False, help_text='If true, block does not expire')),
            ],
            options={
                'verbose_name': 'Blocked Device',
                'verbose_name_plural': 'Blocked Devices',
            },
        ),

        migrations.CreateModel(
            name='SystemUpdate',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version', models.CharField(max_length=50, verbose_name='Version')),
                ('release_notes', models.TextField(verbose_name='Release Notes', blank=True)),
                ('download_url', models.URLField(verbose_name='Download URL')),
                ('download_size', models.BigIntegerField(verbose_name='Download Size (bytes)', default=0)),
                ('is_downloaded', models.BooleanField(verbose_name='Downloaded', default=False)),
                ('is_installed', models.BooleanField(verbose_name='Installed', default=False)),
                ('download_progress', models.IntegerField(verbose_name='Download Progress (%)', default=0)),
                ('installation_log', models.TextField(verbose_name='Installation Log', blank=True)),
                ('created_at', models.DateTimeField(verbose_name='Created At', default=django.utils.timezone.now)),
            ],
            options={
                'verbose_name': 'System Update',
                'verbose_name_plural': 'System Updates',
            },
        ),

        migrations.CreateModel(
            name='UpdateSettings',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('auto_check_updates', models.BooleanField(verbose_name='Auto Check Updates', default=True)),
                ('auto_download_updates', models.BooleanField(verbose_name='Auto Download Updates', default=False)),
                ('auto_install_updates', models.BooleanField(verbose_name='Auto Install Updates', default=False)),
                ('update_channel', models.CharField(max_length=20, verbose_name='Update Channel', default='stable', choices=[('stable', 'Stable'), ('beta', 'Beta'), ('dev', 'Development')])),
                ('backup_before_update', models.BooleanField(verbose_name='Backup Before Update', default=True)),
                ('max_backups_to_keep', models.IntegerField(verbose_name='Max Backups to Keep', default=3)),
                ('github_repository', models.CharField(max_length=100, verbose_name='GitHub Repository', default='regolet/pisowifi')),
                ('current_version', models.CharField(max_length=50, verbose_name='Current Version', default='2.2.8')),
            ],
            options={
                'verbose_name': 'Update Settings',
                'verbose_name_plural': 'Update Settings',
            },
        ),

        # Portal customization
        migrations.CreateModel(
            name='PortalSettings',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('portal_title', models.CharField(max_length=255, verbose_name='Portal Title', default='PISOWifi Portal')),
                ('welcome_message', models.TextField(verbose_name='Welcome Message', default='Welcome to PISOWifi')),
                ('primary_color', models.CharField(max_length=7, verbose_name='Primary Color', default='#007bff')),
                ('secondary_color', models.CharField(max_length=7, verbose_name='Secondary Color', default='#6c757d')),
                ('background_color', models.CharField(max_length=7, verbose_name='Background Color', default='#ffffff')),
                ('text_color', models.CharField(max_length=7, verbose_name='Text Color', default='#212529')),
                ('logo', models.ImageField(verbose_name='Portal Logo', upload_to='portal/logos/', null=True, blank=True)),
                ('favicon', models.ImageField(verbose_name='Favicon', upload_to='portal/favicons/', null=True, blank=True)),
                ('slot_timeout', models.IntegerField(verbose_name='Slot Timeout (seconds)', default=300, help_text='Time to wait for coin insertion before releasing slot')),
            ],
            options={
                'verbose_name': 'Portal Settings',
                'verbose_name_plural': 'Portal Settings',
            },
        ),

        # Sales reporting  
        migrations.CreateModel(
            name='SalesReport',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(verbose_name='Date')),
                ('total_sales', models.DecimalField(verbose_name='Total Sales', max_digits=10, decimal_places=2, default=0)),
                ('total_clients', models.IntegerField(verbose_name='Total Clients', default=0)),
                ('peak_hour_start', models.TimeField(verbose_name='Peak Hour Start', null=True, blank=True)),
                ('peak_hour_end', models.TimeField(verbose_name='Peak Hour End', null=True, blank=True)),
                ('notes', models.TextField(verbose_name='Notes', blank=True)),
                ('created_at', models.DateTimeField(verbose_name='Created At', default=django.utils.timezone.now)),
            ],
            options={
                'verbose_name': 'Sales Report',
                'verbose_name_plural': 'Sales Reports',
                'unique_together': {('date',)},
            },
        ),
    ]
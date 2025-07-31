"""
Django management command to setup fail2ban for PISOWifi security
"""

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import os
import logging
from app.security.fail2ban_config import fail2ban_manager

logger = logging.getLogger('security')


class Command(BaseCommand):
    help = 'Setup and configure fail2ban for PISOWifi security'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--install',
            action='store_true',
            help='Install fail2ban configuration files',
        )
        parser.add_argument(
            '--status',
            action='store_true',
            help='Show fail2ban status',
        )
        parser.add_argument(
            '--unban',
            type=str,
            help='Unban specific IP address',
        )
        parser.add_argument(
            '--list-banned',
            action='store_true',
            help='List all banned IP addresses',
        )
        parser.add_argument(
            '--test-config',
            action='store_true',
            help='Test fail2ban configuration',
        )
    
    def handle(self, *args, **options):
        if options['install']:
            self.install_fail2ban()
        elif options['status']:
            self.show_status()
        elif options['unban']:
            self.unban_ip(options['unban'])
        elif options['list_banned']:
            self.list_banned_ips()
        elif options['test_config']:
            self.test_configuration()
        else:
            self.stdout.write(
                self.style.WARNING(
                    'Please specify an action: --install, --status, --unban, --list-banned, or --test-config'
                )
            )
    
    def install_fail2ban(self):
        """Install fail2ban configuration"""
        self.stdout.write('Installing fail2ban configuration for PISOWifi...')
        
        # Check if fail2ban is installed
        if not self.check_fail2ban_installed():
            self.stdout.write(
                self.style.ERROR(
                    'fail2ban is not installed. Please install it first:\n'
                    '  Ubuntu/Debian: sudo apt-get install fail2ban\n'
                    '  CentOS/RHEL: sudo yum install fail2ban\n'
                    '  Arch: sudo pacman -S fail2ban'
                )
            )
            return
        
        # Install configuration
        success = fail2ban_manager.install_configuration()
        
        if success:
            self.stdout.write(
                self.style.SUCCESS(
                    'Fail2ban configuration installed successfully!\n\n'
                    'Configuration files created:\n'
                    f'  - {fail2ban_manager.jail_local_path}\n'
                    f'  - {fail2ban_manager.filter_dir}/pisowifi-*.conf\n'
                    f'  - {fail2ban_manager.action_dir}/pisowifi-notify.conf\n\n'
                    'Please ensure the following:\n'
                    '1. Update the script path in pisowifi-notify.conf to match your installation\n'
                    '2. Ensure the security log path is correct in jail.local\n'
                    '3. Restart fail2ban service: sudo systemctl restart fail2ban\n'
                    '4. Check status with: python manage.py setup_fail2ban --status'
                )
            )
        else:
            self.stdout.write(
                self.style.ERROR('Failed to install fail2ban configuration')
            )
    
    def show_status(self):
        """Show fail2ban status"""
        self.stdout.write('Checking fail2ban status...\n')
        
        jail_status = fail2ban_manager.get_jail_status()
        
        if not jail_status:
            self.stdout.write(
                self.style.WARNING(
                    'No PISOWifi jails found or fail2ban is not running.\n'
                    'Make sure fail2ban is installed and PISOWifi configuration is loaded.'
                )
            )
            return
        
        for jail_name, status in jail_status.items():
            self.stdout.write(f'\n🏛️ Jail: {jail_name}')
            self.stdout.write(f'  Status: {"✅ Enabled" if status["enabled"] else "❌ Disabled"}')
            self.stdout.write(f'  Currently Failed: {status["currently_failed"]}')
            self.stdout.write(f'  Total Failed: {status["total_failed"]}')
            self.stdout.write(f'  Currently Banned: {status["currently_banned"]}')
            self.stdout.write(f'  Total Banned: {status["total_banned"]}')
            
            if status['banned_ips']:
                self.stdout.write(f'  Banned IPs: {", ".join(status["banned_ips"])}')
            else:
                self.stdout.write('  Banned IPs: None')
    
    def unban_ip(self, ip_address):
        """Unban specific IP address"""
        self.stdout.write(f'Unbanning IP address: {ip_address}')
        
        success = fail2ban_manager.unban_ip(ip_address)
        
        if success:
            self.stdout.write(
                self.style.SUCCESS(f'Successfully unbanned {ip_address}')
            )
        else:
            self.stdout.write(
                self.style.ERROR(f'Failed to unban {ip_address}')
            )
    
    def list_banned_ips(self):
        """List all banned IP addresses"""
        self.stdout.write('Getting list of banned IP addresses...\n')
        
        banned_ips = fail2ban_manager.get_banned_ips()
        
        if banned_ips:
            self.stdout.write('🚫 Currently banned IP addresses:')
            for ip in banned_ips:
                self.stdout.write(f'  - {ip}')
        else:
            self.stdout.write('✅ No IP addresses are currently banned')
    
    def test_configuration(self):
        """Test fail2ban configuration"""
        self.stdout.write('Testing fail2ban configuration...\n')
        
        # Test if configuration files exist
        config_files = [
            (fail2ban_manager.jail_local_path, 'Jail configuration'),
            (os.path.join(fail2ban_manager.filter_dir, 'pisowifi-auth.conf'), 'Auth filter'),
            (os.path.join(fail2ban_manager.filter_dir, 'pisowifi-admin.conf'), 'Admin filter'),
            (os.path.join(fail2ban_manager.filter_dir, 'pisowifi-scanner.conf'), 'Scanner filter'),
            (os.path.join(fail2ban_manager.filter_dir, 'pisowifi-injection.conf'), 'Injection filter'),
            (os.path.join(fail2ban_manager.filter_dir, 'pisowifi-dos.conf'), 'DoS filter'),
            (os.path.join(fail2ban_manager.action_dir, 'pisowifi-notify.conf'), 'Notification action'),
        ]
        
        all_good = True
        
        for file_path, description in config_files:
            if os.path.exists(file_path):
                self.stdout.write(f'✅ {description}: Found')
            else:
                self.stdout.write(f'❌ {description}: Missing ({file_path})')
                all_good = False
        
        # Test log file path
        log_path = getattr(settings, 'SECURITY_LOG_PATH', '/var/log/pisowifi/security.log')
        log_dir = os.path.dirname(log_path)
        
        if os.path.exists(log_dir):
            self.stdout.write(f'✅ Security log directory: Found ({log_dir})')
        else:
            self.stdout.write(f'❌ Security log directory: Missing ({log_dir})')
            all_good = False
        
        # Test notify script
        notify_script = os.path.join(settings.BASE_DIR, 'app', 'security', 'fail2ban_notify.py')
        if os.path.exists(notify_script) and os.access(notify_script, os.X_OK):
            self.stdout.write(f'✅ Notification script: Found and executable')
        else:
            self.stdout.write(f'❌ Notification script: Missing or not executable ({notify_script})')
            all_good = False
        
        if all_good:
            self.stdout.write('\n🎉 All configuration tests passed!')
        else:
            self.stdout.write('\n⚠️ Some configuration issues found. Please run --install to fix them.')
    
    def check_fail2ban_installed(self):
        """Check if fail2ban is installed"""
        import subprocess
        
        try:
            result = subprocess.run(['fail2ban-client', '--version'], 
                                  capture_output=True, text=True)
            return result.returncode == 0
        except FileNotFoundError:
            return False
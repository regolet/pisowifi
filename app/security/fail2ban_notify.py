#!/usr/bin/env python3
"""
Fail2ban notification script for PISOWifi
This script is called by fail2ban when IPs are banned/unbanned
"""

import sys
import os
import django
from datetime import datetime

# Add Django project to Python path
sys.path.append('/path/to/your/pisowifi/project')  # Update this path
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'opw.settings')

try:
    django.setup()
    from app.security.monitoring import security_monitor
    from app.security.handlers import block_ip_address, unblock_ip_address
    
    def handle_ban(ip_address):
        """Handle IP ban notification from fail2ban"""
        try:
            # Log the ban event
            security_monitor.log_security_event(
                'fail2ban_auto_ban',
                ip_address,
                {
                    'banned_by': 'fail2ban_automatic',
                    'timestamp': datetime.now().isoformat(),
                    'method': 'fail2ban'
                }
            )
            
            # Update our internal IP blocking system
            block_ip_address(ip_address, 'Automatic ban by fail2ban', 'fail2ban_system')
            
            print(f"PISOWifi: Successfully logged ban for {ip_address}")
            
        except Exception as e:
            print(f"PISOWifi: Error logging ban for {ip_address}: {e}")
    
    def handle_unban(ip_address):
        """Handle IP unban notification from fail2ban"""
        try:
            # Log the unban event
            security_monitor.log_security_event(
                'fail2ban_auto_unban',
                ip_address,
                {
                    'unbanned_by': 'fail2ban_automatic',
                    'timestamp': datetime.now().isoformat(),
                    'method': 'fail2ban'
                }
            )
            
            # Update our internal IP blocking system
            unblock_ip_address(ip_address, 'fail2ban_system')
            
            print(f"PISOWifi: Successfully logged unban for {ip_address}")
            
        except Exception as e:
            print(f"PISOWifi: Error logging unban for {ip_address}: {e}")
    
    if __name__ == "__main__":
        if len(sys.argv) != 3:
            print("Usage: fail2ban_notify.py <action> <ip_address>")
            sys.exit(1)
        
        action = sys.argv[1].lower()
        ip_address = sys.argv[2]
        
        if action == 'ban':
            handle_ban(ip_address)
        elif action == 'unban':
            handle_unban(ip_address)
        else:
            print(f"Unknown action: {action}")
            sys.exit(1)

except ImportError as e:
    print(f"PISOWifi: Django import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"PISOWifi: Unexpected error: {e}")
    sys.exit(1)
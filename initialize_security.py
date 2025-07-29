#!/usr/bin/env python
"""
Initialize Security Settings for TTL Detection
Run this script to create default security settings.
"""

import os
import sys
import django

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'opw.settings')

django.setup()

from app.models import SecuritySettings
from django.utils import timezone

def initialize_security_settings():
    """Create default security settings if they don't exist."""
    
    security_settings, created = SecuritySettings.objects.get_or_create(
        pk=1,
        defaults={
            'TTL_Detection_Enabled': True,
            'Default_TTL_Value': 64,  # Linux/Android default
            'TTL_Tolerance': 2,
            'Limit_Connections': True,
            'Normal_Device_Connections': 3,
            'Suspicious_Device_Connections': 1,
            'Max_TTL_Violations': 5,
            # TTL Modification (MikroTik-style)
            'Enable_TTL_Modification': False,  # Disabled by default (requires iptables)
            'TTL_Modification_After_Violations': 10,
            'Modified_TTL_Value': 1,
            'TTL_Rule_Duration': timezone.timedelta(hours=2),
            # Legacy blocking
            'Enable_Device_Blocking': False,  # Connection limiting preferred
            'Block_Duration': timezone.timedelta(hours=1)
        }
    )
    
    if created:
        print("[SUCCESS] TTL Detection with MikroTik-style enforcement initialized!")
        print(f"   - TTL Detection: Enabled")
        print(f"   - Expected TTL: {security_settings.Default_TTL_Value}")
        print(f"   - TTL Tolerance: +/-{security_settings.TTL_Tolerance}")
        print(f"   - Connection Limiting: Enabled")
        print(f"   - Normal Device Limit: {security_settings.Normal_Device_Connections} connections")
        print(f"   - Suspicious Device Limit: {security_settings.Suspicious_Device_Connections} connection")
        print(f"   - Max Violations: {security_settings.Max_TTL_Violations}")
        print(f"   - TTL Modification (MikroTik-style): {'Enabled' if security_settings.Enable_TTL_Modification else 'Disabled (enable in admin)'}")
        print(f"   - TTL Modify After: {security_settings.TTL_Modification_After_Violations} violations")
        print(f"   - Modified TTL Value: {security_settings.Modified_TTL_Value}")
        print(f"   - TTL Rule Duration: {security_settings.TTL_Rule_Duration}")
        print("\n[INFO] You can modify these settings in the admin panel under 'Security Settings'")
        print("[WARNING] TTL Modification requires iptables and root privileges on Linux/Pi systems")
    else:
        print("[INFO] Security settings already exist.")
        print(f"   - TTL Detection: {'Enabled' if security_settings.TTL_Detection_Enabled else 'Disabled'}")
        print(f"   - Connection Limiting: {'Enabled' if security_settings.Limit_Connections else 'Disabled'}")
        print(f"   - Normal/Suspicious Limits: {security_settings.Normal_Device_Connections if hasattr(security_settings, 'Normal_Device_Connections') else 'N/A'}/{security_settings.Suspicious_Device_Connections if hasattr(security_settings, 'Suspicious_Device_Connections') else 'N/A'}")
        print(f"   - Expected TTL: {security_settings.Default_TTL_Value}")

if __name__ == '__main__':
    initialize_security_settings()
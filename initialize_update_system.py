#!/usr/bin/env python
"""
Initialize the System Update feature
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'opw.settings')
django.setup()

from app.models import UpdateSettings

def initialize_update_system():
    """Initialize the update system with default settings"""
    try:
        # Create or get the update settings
        settings, created = UpdateSettings.objects.get_or_create(pk=1)
        
        if created:
            print("[OK] UpdateSettings created with default values")
        else:
            print("[OK] UpdateSettings already exists")
        
        print(f"  - Repository: {settings.GitHub_Repository}")
        print(f"  - Update Channel: {settings.Update_Channel}")
        print(f"  - Current Version: {settings.Current_Version}")
        print(f"  - Auto Download: {settings.Auto_Download}")
        print(f"  - Auto Install: {settings.Auto_Install}")
        print(f"  - Backup Before Update: {settings.Backup_Before_Update}")
        
        print("\n[OK] System Update feature is ready!")
        print("\nTo access the system update interface:")
        print("1. Go to Django Admin")
        print("2. Navigate to 'System Updates' to view/manage updates")
        print("3. Navigate to 'Update Settings' to configure auto-update behavior")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Error initializing update system: {e}")
        return False

if __name__ == '__main__':
    print("Initializing PISOWifi System Update Feature...")
    print("=" * 50)
    
    success = initialize_update_system()
    
    if success:
        print("\n" + "=" * 50)
        print("System Update Feature Initialization Complete!")
    else:
        print("\n" + "=" * 50)
        print("System Update Feature Initialization Failed!")
        sys.exit(1)
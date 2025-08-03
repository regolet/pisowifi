#!/usr/bin/env python
"""
Admin Authentication Fix Script
Ensures admin users have proper token authentication set up
"""
import os
import sys
import django
from pathlib import Path

# Setup Django
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'opw.settings')
django.setup()

from django.contrib.auth.models import User
from app.services.admin_token_service import admin_token_service

def fix_admin_auth():
    """Generate admin tokens for all staff users"""
    try:
        staff_users = User.objects.filter(is_staff=True)
        
        if not staff_users.exists():
            print("No staff users found. Creating default admin user...")
            # Create default admin user
            admin_user = User.objects.create_user(
                username='admin',
                email='admin@localhost',
                password='admin123',
                is_staff=True,
                is_superuser=True
            )
            staff_users = [admin_user]
            print(f"Created admin user: {admin_user.username}")
        
        print(f"Found {len(staff_users)} staff users")
        
        for user in staff_users:
            token = admin_token_service.generate_admin_token(user)
            if token:
                print(f"Generated admin token for user: {user.username}")
                print(f"Token (first 20 chars): {token[:20]}...")
            else:
                print(f"Failed to generate token for user: {user.username}")
        
        print("\nAdmin token authentication is now configured.")
        print("Users should refresh their browser to get the new token cookies.")
        
        return True
        
    except Exception as e:
        print(f"Error fixing admin authentication: {e}")
        return False

if __name__ == '__main__':
    success = fix_admin_auth()
    sys.exit(0 if success else 1)
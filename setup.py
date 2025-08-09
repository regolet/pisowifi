#!/usr/bin/env python3
"""
OJO PISOWifi Automated Setup Script
==================================

This script will automatically:
1. Check system requirements
2. Install Python dependencies
3. Setup database
4. Configure environment variables
5. Create admin user
6. Start the application

Just run: python setup.py
"""

import os
import sys
import subprocess
import platform
import getpass
import secrets
import sqlite3
from pathlib import Path

class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

class PISOWifiSetup:
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.venv_dir = self.base_dir / "venv"
        self.is_windows = platform.system() == "Windows"
        self.python_exe = sys.executable
        
    def print_header(self):
        print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}")
        print("🚀 OJO PISOWifi Automated Setup")
        print("Setting up your PISOWifi management system...")
        print(f"{'='*60}{Colors.END}\n")

    def print_step(self, step, description):
        print(f"{Colors.BOLD}Step {step}: {Colors.BLUE}{description}{Colors.END}")

    def print_success(self, message):
        print(f"{Colors.GREEN}✅ {message}{Colors.END}")

    def print_warning(self, message):
        print(f"{Colors.YELLOW}⚠️  {message}{Colors.END}")

    def print_error(self, message):
        print(f"{Colors.RED}❌ {message}{Colors.END}")

    def run_command(self, command, description=None, check=True):
        """Run a system command"""
        if description:
            print(f"   {description}...")
        
        try:
            if isinstance(command, str):
                result = subprocess.run(command, shell=True, check=check, 
                                      capture_output=True, text=True)
            else:
                result = subprocess.run(command, check=check, 
                                      capture_output=True, text=True)
            
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                if description:
                    self.print_error(f"Failed: {description}")
                    if result.stderr:
                        print(f"   Error: {result.stderr}")
                return None
        except subprocess.CalledProcessError as e:
            if description:
                self.print_error(f"Failed: {description}")
                print(f"   Error: {e}")
            return None
        except FileNotFoundError:
            if description:
                self.print_error(f"Command not found: {command}")
            return None

    def check_python_version(self):
        """Check if Python version is compatible"""
        self.print_step(1, "Checking Python version")
        
        version = sys.version_info
        if version.major < 3 or (version.major == 3 and version.minor < 8):
            self.print_error(f"Python 3.8+ required. Found Python {version.major}.{version.minor}")
            self.print_warning("Please install Python 3.8 or later from https://python.org")
            return False
        
        self.print_success(f"Python {version.major}.{version.minor}.{version.micro} is compatible")
        return True

    def create_virtual_environment(self):
        """Create Python virtual environment"""
        self.print_step(2, "Creating virtual environment")
        
        if self.venv_dir.exists():
            self.print_warning("Virtual environment already exists, skipping...")
            return True
        
        result = self.run_command(f'"{self.python_exe}" -m venv "{self.venv_dir}"', 
                                "Creating virtual environment")
        
        if result is not None:
            self.print_success("Virtual environment created")
            return True
        else:
            self.print_error("Failed to create virtual environment")
            return False

    def get_venv_python(self):
        """Get the Python executable from virtual environment"""
        if self.is_windows:
            return self.venv_dir / "Scripts" / "python.exe"
        else:
            return self.venv_dir / "bin" / "python"

    def get_venv_pip(self):
        """Get the pip executable from virtual environment"""
        if self.is_windows:
            return self.venv_dir / "Scripts" / "pip.exe"
        else:
            return self.venv_dir / "bin" / "pip"

    def install_requirements(self):
        """Install Python dependencies"""
        self.print_step(3, "Installing Python dependencies")
        
        pip_exe = self.get_venv_pip()
        
        # Upgrade pip first
        self.run_command(f'"{pip_exe}" install --upgrade pip', 
                        "Upgrading pip")
        
        # Install requirements
        requirements_file = self.base_dir / "requirements.txt"
        if not requirements_file.exists():
            self.print_warning("requirements.txt not found, installing basic dependencies...")
            basic_deps = [
                "django>=5.0.0",
                "psutil>=5.9.0",
                "djangorestframework>=3.14.0",
                "django-jazzmin>=2.6.0",
                "python-decouple>=3.6",
                "django-cors-headers>=4.0.0",
                "pillow>=9.0.0"
            ]
            
            for dep in basic_deps:
                result = self.run_command(f'"{pip_exe}" install {dep}', 
                                        f"Installing {dep}")
                if result is None:
                    self.print_error(f"Failed to install {dep}")
                    return False
        else:
            result = self.run_command(f'"{pip_exe}" install -r "{requirements_file}"', 
                                    "Installing requirements from requirements.txt")
            if result is None:
                self.print_error("Failed to install requirements")
                return False
        
        self.print_success("All dependencies installed")
        return True

    def create_env_file(self):
        """Create .env file with configuration"""
        self.print_step(4, "Creating environment configuration")
        
        env_file = self.base_dir / ".env"
        if env_file.exists():
            self.print_warning(".env file already exists, skipping...")
            return True
        
        # Generate secret key
        secret_key = secrets.token_urlsafe(50)
        
        env_content = f"""# OJO PISOWifi Environment Configuration
# Generated automatically by setup.py

# Django Settings
SECRET_KEY={secret_key}
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0

# Database (SQLite for easy setup)
DATABASE_URL=sqlite:///{self.base_dir}/db.sqlite3

# Security Settings
SESSION_COOKIE_AGE=3600
CSRF_COOKIE_SECURE=False
SESSION_COOKIE_SECURE=False

# PISOWifi Settings
DEFAULT_RATE_PER_HOUR=5.00
MAX_CONCURRENT_USERS=50
VOUCHER_EXPIRY_HOURS=24

# System Monitoring
ENABLE_SYSTEM_MONITORING=True
SYSTEM_ALERT_THRESHOLD_CPU=85
SYSTEM_ALERT_THRESHOLD_MEMORY=90
SYSTEM_ALERT_THRESHOLD_DISK=85
"""
        
        try:
            with open(env_file, 'w') as f:
                f.write(env_content)
            self.print_success("Environment configuration created")
            return True
        except Exception as e:
            self.print_error(f"Failed to create .env file: {e}")
            return False

    def setup_database(self):
        """Setup database and run migrations"""
        self.print_step(5, "Setting up database")
        
        python_exe = self.get_venv_python()
        
        # Run migrations
        result = self.run_command(f'"{python_exe}" manage.py migrate', 
                                "Running database migrations")
        if result is None:
            self.print_error("Failed to run migrations")
            return False
        
        self.print_success("Database setup completed")
        return True

    def collect_static_files(self):
        """Collect static files"""
        self.print_step(6, "Collecting static files")
        
        python_exe = self.get_venv_python()
        
        result = self.run_command(f'"{python_exe}" manage.py collectstatic --noinput', 
                                "Collecting static files")
        if result is None:
            self.print_warning("Static files collection failed (this is usually okay)")
        else:
            self.print_success("Static files collected")
        
        return True

    def create_admin_user(self):
        """Create admin user"""
        self.print_step(7, "Creating admin user")
        
        print("\n📝 Please provide admin user details:")
        
        while True:
            username = input("   Admin username (default: admin): ").strip() or "admin"
            if username:
                break
            print("   Username cannot be empty!")
        
        while True:
            email = input("   Admin email (default: admin@localhost): ").strip() or "admin@localhost"
            if "@" in email:
                break
            print("   Please enter a valid email address!")
        
        while True:
            password = getpass.getpass("   Admin password (min 8 chars): ").strip()
            if len(password) >= 8:
                password_confirm = getpass.getpass("   Confirm password: ").strip()
                if password == password_confirm:
                    break
                else:
                    print("   Passwords don't match! Please try again.")
            else:
                print("   Password must be at least 8 characters long!")
        
        # Create superuser using Django management command
        python_exe = self.get_venv_python()
        
        # Create a temporary script to create superuser
        create_user_script = f"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'opw.settings')
django.setup()

from django.contrib.auth.models import User
from django.db import IntegrityError

try:
    if User.objects.filter(username='{username}').exists():
        print('Admin user already exists')
    else:
        user = User.objects.create_superuser('{username}', '{email}', '{password}')
        print('Admin user created successfully')
except IntegrityError:
    print('Admin user already exists')
except Exception as e:
    print(f'Error creating admin user: {{e}}')
"""
        
        script_file = self.base_dir / "temp_create_admin.py"
        try:
            with open(script_file, 'w') as f:
                f.write(create_user_script)
            
            result = self.run_command(f'"{python_exe}" temp_create_admin.py', 
                                    "Creating admin user")
            
            script_file.unlink()  # Delete temporary script
            
            if result is not None:
                self.print_success(f"Admin user '{username}' created successfully")
                return True
            else:
                self.print_error("Failed to create admin user")
                return False
                
        except Exception as e:
            self.print_error(f"Failed to create admin user: {e}")
            if script_file.exists():
                script_file.unlink()
            return False

    def create_startup_scripts(self):
        """Create startup scripts for easy launching"""
        self.print_step(8, "Creating startup scripts")
        
        python_exe = self.get_venv_python()
        
        if self.is_windows:
            # Create Windows batch file
            batch_content = f"""@echo off
echo Starting OJO PISOWifi Server...
echo.
echo Dashboard will be available at: http://localhost:8000/admin/
echo Press Ctrl+C to stop the server
echo.
"{python_exe}" manage.py runserver 0.0.0.0:8000
pause
"""
            with open(self.base_dir / "start_pisowifi.bat", 'w') as f:
                f.write(batch_content)
            
            self.print_success("Created start_pisowifi.bat")
            
        else:
            # Create Unix shell script
            script_content = f"""#!/bin/bash
echo "Starting OJO PISOWifi Server..."
echo
echo "Dashboard will be available at: http://localhost:8000/admin/"
echo "Press Ctrl+C to stop the server"
echo
"{python_exe}" manage.py runserver 0.0.0.0:8000
"""
            script_file = self.base_dir / "start_pisowifi.sh"
            with open(script_file, 'w') as f:
                f.write(script_content)
            
            # Make executable
            os.chmod(script_file, 0o755)
            self.print_success("Created start_pisowifi.sh")
        
        return True

    def print_completion_message(self):
        """Print setup completion message"""
        print(f"\n{Colors.BOLD}{Colors.GREEN}{'='*60}")
        print("🎉 SETUP COMPLETED SUCCESSFULLY!")
        print(f"{'='*60}{Colors.END}")
        
        print(f"\n{Colors.BOLD}📋 What's Next:{Colors.END}")
        print("1. Your PISOWifi system is ready to use!")
        print("2. Start the server using one of these methods:")
        
        if self.is_windows:
            print(f"   • Double-click: {Colors.BLUE}start_pisowifi.bat{Colors.END}")
            print(f"   • Command line: {Colors.BLUE}python manage.py runserver 0.0.0.0:8000{Colors.END}")
        else:
            print(f"   • Terminal: {Colors.BLUE}./start_pisowifi.sh{Colors.END}")
            print(f"   • Command line: {Colors.BLUE}python manage.py runserver 0.0.0.0:8000{Colors.END}")
        
        print(f"\n{Colors.BOLD}🌐 Access Your Dashboard:{Colors.END}")
        print(f"   • Admin Panel: {Colors.BLUE}http://localhost:8000/admin/{Colors.END}")
        print(f"   • Client Portal: {Colors.BLUE}http://localhost:8000/app/portal/{Colors.END}")
        
        print(f"\n{Colors.BOLD}📁 Important Files:{Colors.END}")
        print(f"   • Configuration: {Colors.BLUE}.env{Colors.END}")
        print(f"   • Database: {Colors.BLUE}db.sqlite3{Colors.END}")
        print(f"   • Logs: {Colors.BLUE}logs/{Colors.END} (created when server starts)")
        
        print(f"\n{Colors.BOLD}🔧 Need Help?{Colors.END}")
        print("   • Check the documentation in the project folder")
        print("   • View logs if something isn't working")
        print("   • Make sure port 8000 is not blocked by firewall")
        
        print(f"\n{Colors.GREEN}Enjoy your PISOWifi system! 🚀{Colors.END}\n")

    def run_setup(self):
        """Run the complete setup process"""
        self.print_header()
        
        try:
            # Step-by-step setup
            if not self.check_python_version():
                return False
            
            if not self.create_virtual_environment():
                return False
            
            if not self.install_requirements():
                return False
            
            if not self.create_env_file():
                return False
            
            if not self.setup_database():
                return False
            
            if not self.collect_static_files():
                return False
            
            if not self.create_admin_user():
                return False
            
            if not self.create_startup_scripts():
                return False
            
            self.print_completion_message()
            return True
            
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}Setup interrupted by user.{Colors.END}")
            return False
        except Exception as e:
            self.print_error(f"Unexpected error: {e}")
            return False

def main():
    """Main setup function"""
    setup = PISOWifiSetup()
    
    # Check if we're in the right directory
    if not (Path.cwd() / "manage.py").exists():
        print(f"{Colors.RED}❌ Error: This script must be run from the project root directory!")
        print(f"   Make sure you're in the folder containing manage.py{Colors.END}")
        return 1
    
    success = setup.run_setup()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
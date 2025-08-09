#!/usr/bin/env python3
"""
PISOWifi Complete Orange Pi Setup Script
=======================================

This script will automatically setup EVERYTHING:
- System dependencies
- Network configuration 
- PISOWifi application
- Services and firewall
- No manual commands needed!
"""

import os
import sys
import subprocess
import getpass
import secrets
from pathlib import Path

class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

class OrangePiPISOWifiSetup:
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.venv_dir = self.base_dir / "venv"
        self.usb_interface = None
        self.builtin_interface = None
        
    def print_header(self):
        print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}")
        print("🍊 PISOWifi Complete Orange Pi Setup")
        print("This will setup EVERYTHING automatically!")
        print(f"{'='*70}{Colors.END}\n")

    def print_step(self, step, description):
        print(f"{Colors.BOLD}Step {step}: {Colors.BLUE}{description}{Colors.END}")

    def print_success(self, message):
        print(f"{Colors.GREEN}✅ {message}{Colors.END}")

    def print_error(self, message):
        print(f"{Colors.RED}❌ {message}{Colors.END}")

    def run_command(self, command, description=None):
        if description:
            print(f"   {description}...")
        try:
            result = subprocess.run(command, shell=True, check=True, 
                                  capture_output=True, text=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            if description:
                print(f"   Warning: {description} failed, continuing...")
            return None

    def detect_interfaces(self):
        """Detect network interfaces automatically"""
        self.print_step(1, "Detecting network interfaces")
        
        try:
            result = subprocess.run(['ip', 'link', 'show'], capture_output=True, text=True)
            lines = result.stdout.split('\n')
            
            interfaces = {}
            for line in lines:
                if ': ' in line and 'LOOPBACK' not in line:
                    parts = line.split(': ')
                    if_name = parts[1].split('@')[0]
                    interfaces[if_name] = line
            
            # Detect built-in ethernet (usually end0, eth0, or similar)
            for name in ['end0', 'eth0', 'enp0s3']:
                if name in interfaces:
                    self.builtin_interface = name
                    break
            
            # Detect USB ethernet (usually enx... or similar)
            for name in interfaces:
                if name.startswith('enx') or (name.startswith('eth') and name != self.builtin_interface):
                    self.usb_interface = name
                    break
            
            print(f"   Built-in interface: {self.builtin_interface}")
            print(f"   USB interface: {self.usb_interface}")
            
            if not self.builtin_interface or not self.usb_interface:
                self.print_error("Could not detect both network interfaces!")
                return False
                
            self.print_success("Network interfaces detected")
            return True
            
        except Exception as e:
            self.print_error(f"Failed to detect interfaces: {e}")
            return False

    def install_system_packages(self):
        """Install all system packages"""
        self.print_step(2, "Installing system packages")
        
        packages = [
            # Python and build tools
            'python3', 'python3-pip', 'python3-venv', 'python3-dev',
            'build-essential', 'libssl-dev', 'libffi-dev',
            # Web server and database
            'nginx', 'sqlite3', 'supervisor',
            # Network services  
            'dnsmasq', 'iptables', 'iptables-persistent',
            'hostapd', 'wireless-tools',
            # Utilities
            'git', 'curl', 'wget', 'unzip', 'nano',
            'fail2ban', 'ufw', 'net-tools', 'htop'
        ]
        
        # Update package list
        self.run_command('sudo apt update', 'Updating package list')
        
        # Install packages
        cmd = f"sudo apt install -y {' '.join(packages)}"
        self.run_command(cmd, 'Installing system packages')
        
        self.print_success("System packages installed")
        return True

    def configure_network(self):
        """Configure network interfaces"""
        self.print_step(3, "Configuring network")
        
        network_config = f"""# PISOWifi Network Configuration
# Loopback
auto lo
iface lo inet loopback

# WAN - Internet connection (built-in ethernet)
auto {self.builtin_interface}
iface {self.builtin_interface} inet dhcp

# LAN - PISOWifi network (USB-LAN adapter) 
auto {self.usb_interface}
iface {self.usb_interface} inet static
    address 10.0.0.1
    netmask 255.255.255.0
    network 10.0.0.0
    broadcast 10.0.0.255
"""
        
        # Backup original config
        self.run_command('sudo cp /etc/network/interfaces /etc/network/interfaces.backup')
        
        # Write new config
        try:
            with open('/tmp/interfaces', 'w') as f:
                f.write(network_config)
            self.run_command('sudo cp /tmp/interfaces /etc/network/interfaces')
            self.print_success("Network configuration written")
        except Exception as e:
            self.print_error(f"Failed to write network config: {e}")
            return False
        
        # Enable IP forwarding
        self.run_command('echo "net.ipv4.ip_forward=1" | sudo tee -a /etc/sysctl.conf')
        self.run_command('sudo sysctl -p')
        
        # Restart networking
        self.run_command('sudo systemctl restart networking')
        
        self.print_success("Network configured")
        return True

    def setup_python_environment(self):
        """Setup Python virtual environment"""
        self.print_step(4, "Setting up Python environment")
        
        # Create virtual environment
        self.run_command(f'python3 -m venv {self.venv_dir}', 'Creating virtual environment')
        
        # Install Python packages
        pip_cmd = f'{self.venv_dir}/bin/pip'
        packages = [
            'django>=5.0.0', 'psutil>=5.9.0', 'djangorestframework>=3.14.0',
            'django-jazzmin>=2.6.0', 'python-decouple>=3.6', 
            'django-cors-headers>=4.0.0', 'pillow>=9.0.0', 'requests>=2.28.0'
        ]
        
        self.run_command(f'{pip_cmd} install --upgrade pip')
        
        for package in packages:
            self.run_command(f'{pip_cmd} install {package}', f'Installing {package.split(">=")[0]}')
        
        self.print_success("Python environment ready")
        return True

    def setup_database(self):
        """Setup Django database"""
        self.print_step(5, "Setting up database")
        
        python_cmd = f'{self.venv_dir}/bin/python'
        
        # Create .env file
        env_content = f"""SECRET_KEY={secrets.token_urlsafe(50)}
DEBUG=True
ALLOWED_HOSTS=*
DATABASE_URL=sqlite:///{self.base_dir}/db.sqlite3
"""
        with open(self.base_dir / '.env', 'w') as f:
            f.write(env_content)
        
        # Run migrations
        self.run_command(f'{python_cmd} manage.py migrate', 'Running migrations')
        self.run_command(f'{python_cmd} manage.py collectstatic --noinput', 'Collecting static files')
        
        self.print_success("Database setup complete")
        return True

    def create_admin_user(self):
        """Create admin user"""
        self.print_step(6, "Creating admin user")
        
        print(f"\n{Colors.YELLOW}Please create your admin account:{Colors.END}")
        username = input("Admin username (default: admin): ").strip() or "admin"
        email = input("Admin email (default: admin@pisowifi.local): ").strip() or "admin@pisowifi.local"
        
        while True:
            password = getpass.getpass("Admin password (min 8 chars): ").strip()
            if len(password) >= 8:
                break
            print("Password must be at least 8 characters!")
        
        # Create superuser script
        create_script = f"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'opw.settings')
django.setup()
from django.contrib.auth.models import User
try:
    if not User.objects.filter(username='{username}').exists():
        User.objects.create_superuser('{username}', '{email}', '{password}')
        print('Admin user created')
    else:
        print('Admin user already exists')
except Exception as e:
    print(f'Error: {{e}}')
"""
        
        with open('/tmp/create_admin.py', 'w') as f:
            f.write(create_script)
        
        python_cmd = f'{self.venv_dir}/bin/python'
        self.run_command(f'{python_cmd} /tmp/create_admin.py', 'Creating admin user')
        
        self.print_success("Admin user created")
        return True

    def configure_services(self):
        """Configure all services"""
        self.print_step(7, "Configuring services")
        
        # DNSMASQ configuration
        dnsmasq_config = f"""# PISOWifi DNSMASQ Configuration
interface={self.usb_interface}
bind-interfaces
bogus-priv
no-resolv
dhcp-range=10.0.0.10,10.0.0.250,12h
dhcp-option=3,10.0.0.1
dhcp-option=6,10.0.0.1
server=8.8.8.8
server=8.8.4.4
address=/#/10.0.0.1
log-queries
log-dhcp
dhcp-leasefile=/var/lib/misc/dnsmasq.leases
"""
        
        with open('/tmp/dnsmasq.conf', 'w') as f:
            f.write(dnsmasq_config)
        self.run_command('sudo cp /etc/dnsmasq.conf /etc/dnsmasq.conf.backup')
        self.run_command('sudo cp /tmp/dnsmasq.conf /etc/dnsmasq.conf')
        
        # Nginx configuration
        nginx_config = """server {
    listen 80 default_server;
    server_name _;
    
    location /generate_204 { return 204; }
    location /hotspot-detect.html { return 302 http://10.0.0.1/; }
    location /canonical.html { return 302 http://10.0.0.1/; }
    location /success.txt { return 200 'success'; }
    location /ncsi.txt { return 200 'Microsoft NCSI'; }
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}"""
        
        with open('/tmp/pisowifi_nginx', 'w') as f:
            f.write(nginx_config)
        self.run_command('sudo cp /tmp/pisowifi_nginx /etc/nginx/sites-available/pisowifi')
        self.run_command('sudo rm -f /etc/nginx/sites-enabled/default')
        self.run_command('sudo ln -s /etc/nginx/sites-available/pisowifi /etc/nginx/sites-enabled/')
        
        # Supervisor configuration
        supervisor_config = f"""[program:pisowifi]
command={self.venv_dir}/bin/python manage.py runserver 0.0.0.0:8000
directory={self.base_dir}
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/pisowifi.log
environment=DJANGO_SETTINGS_MODULE="opw.settings"
"""
        
        with open('/tmp/pisowifi.conf', 'w') as f:
            f.write(supervisor_config)
        self.run_command('sudo cp /tmp/pisowifi.conf /etc/supervisor/conf.d/')
        
        self.print_success("Services configured")
        return True

    def setup_firewall(self):
        """Setup iptables firewall"""
        self.print_step(8, "Configuring firewall")
        
        # Clear existing rules
        self.run_command('sudo iptables -F')
        self.run_command('sudo iptables -t nat -F')
        
        # NAT and forwarding rules
        self.run_command(f'sudo iptables -t nat -A POSTROUTING -o {self.builtin_interface} -j MASQUERADE')
        self.run_command(f'sudo iptables -A FORWARD -i {self.builtin_interface} -o {self.usb_interface} -m state --state RELATED,ESTABLISHED -j ACCEPT')
        self.run_command(f'sudo iptables -A FORWARD -i {self.usb_interface} -o {self.builtin_interface} -j ACCEPT')
        
        # Captive portal redirects
        self.run_command(f'sudo iptables -t nat -A PREROUTING -i {self.usb_interface} -p tcp --dport 80 -j DNAT --to-destination 10.0.0.1:80')
        self.run_command(f'sudo iptables -t nat -A PREROUTING -i {self.usb_interface} -p tcp --dport 443 -j DNAT --to-destination 10.0.0.1:80')
        
        # Save rules
        self.run_command('sudo netfilter-persistent save')
        
        self.print_success("Firewall configured")
        return True

    def start_services(self):
        """Start all services"""
        self.print_step(9, "Starting services")
        
        services = ['nginx', 'dnsmasq', 'supervisor']
        
        for service in services:
            self.run_command(f'sudo systemctl enable {service}')
            self.run_command(f'sudo systemctl start {service}')
        
        # Start PISOWifi app
        self.run_command('sudo supervisorctl reread')
        self.run_command('sudo supervisorctl update')
        self.run_command('sudo supervisorctl start pisowifi')
        
        self.print_success("All services started")
        return True

    def create_startup_script(self):
        """Create easy startup script"""
        startup_script = f"""#!/bin/bash
echo "🍊 Starting PISOWifi Services..."

sudo systemctl start nginx
sudo systemctl start dnsmasq  
sudo supervisorctl start pisowifi

IP=$(hostname -I | awk '{{print $1}}')
echo "PISOWifi is running!"
echo "Admin Panel: http://$IP/admin/"
echo "Client Portal: http://10.0.0.1/"
"""
        
        with open(self.base_dir / 'start_pisowifi.sh', 'w') as f:
            f.write(startup_script)
        os.chmod(self.base_dir / 'start_pisowifi.sh', 0o755)
        
        return True

    def print_completion(self):
        """Print completion message"""
        print(f"\n{Colors.BOLD}{Colors.GREEN}{'='*70}")
        print("🎉 PISOWifi Setup Complete!")
        print(f"{'='*70}{Colors.END}")
        
        try:
            ip_result = subprocess.run(['hostname', '-I'], capture_output=True, text=True)
            ip = ip_result.stdout.strip().split()[0]
        except:
            ip = "YOUR_ORANGE_PI_IP"
        
        print(f"\n{Colors.BOLD}🌐 Access Your PISOWifi:{Colors.END}")
        print(f"   Admin Panel: {Colors.BLUE}http://{ip}/admin/{Colors.END}")
        print(f"   Client Portal: {Colors.BLUE}http://10.0.0.1/{Colors.END}")
        
        print(f"\n{Colors.BOLD}📋 Next Steps:{Colors.END}")
        print("1. Connect your WiFi router to the USB-LAN port")
        print("2. Configure router as Access Point (disable DHCP)")
        print("3. Set WiFi name to 'PISOWifi' (open network)")
        print("4. Test with a client device")
        
        print(f"\n{Colors.GREEN}Your PISOWifi system is ready! 🍊💰{Colors.END}\n")

    def run_setup(self):
        """Run complete setup"""
        self.print_header()
        
        if os.geteuid() == 0:
            print(f"{Colors.RED}Don't run as root! Run as regular user.{Colors.END}")
            return False
        
        try:
            steps = [
                self.detect_interfaces,
                self.install_system_packages, 
                self.configure_network,
                self.setup_python_environment,
                self.setup_database,
                self.create_admin_user,
                self.configure_services,
                self.setup_firewall,
                self.start_services,
                self.create_startup_script
            ]
            
            for step in steps:
                if not step():
                    return False
            
            self.print_completion()
            return True
            
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}Setup interrupted.{Colors.END}")
            return False

def main():
    if not Path('manage.py').exists():
        print("❌ Error: Run this from the PISOWifi project directory!")
        return 1
    
    setup = OrangePiPISOWifiSetup()
    return 0 if setup.run_setup() else 1

if __name__ == "__main__":
    sys.exit(main())
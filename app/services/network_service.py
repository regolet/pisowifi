"""
Network Configuration Service
Handles VLAN and USB-to-LAN mode switching
"""
import os
import subprocess
import logging
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class NetworkConfigurationService:
    """Service for handling network mode configuration"""
    
    def __init__(self):
        self.config_dir = '/etc/network'
        self.interfaces_file = '/etc/network/interfaces'
        self.dhcpcd_conf = '/etc/dhcpcd.conf'
        self.hostapd_conf = '/etc/hostapd/hostapd.conf'
        
    def apply_network_mode(self, vlan_settings):
        """Apply network configuration based on VLAN settings"""
        try:
            # Pre-flight checks for VLAN compatibility
            if vlan_settings.network_mode == 'vlan':
                success, message = self._check_vlan_prerequisites()
                if not success:
                    return False, f"VLAN prerequisites not met: {message}"
                
                return self._configure_vlan_mode(vlan_settings)
            else:
                return self._configure_usb_to_lan_mode(vlan_settings)
                
        except Exception as e:
            logger.error(f"Error applying network mode: {e}")
            return False, str(e)
    
    def _configure_vlan_mode(self, vlan_settings):
        """Configure system for VLAN mode"""
        logger.info(f"Configuring VLAN mode with VLAN ID: {vlan_settings.vlan_id}")
        
        # Create VLAN interface configuration
        vlan_config = self._generate_vlan_config(vlan_settings)
        
        # Update network interfaces
        success = self._update_network_interfaces(vlan_config)
        if not success:
            return False, "Failed to update network interfaces"
        
        # Update hostapd configuration for VLAN
        success = self._update_hostapd_vlan_config(vlan_settings)
        if not success:
            return False, "Failed to update hostapd configuration"
        
        # Update system status
        vlan_settings.current_status = f'VLAN Mode Active (VLAN ID: {vlan_settings.vlan_id})'
        vlan_settings.last_mode_change = timezone.now()
        vlan_settings.save()
        
        return True, f"VLAN mode configured successfully with VLAN ID {vlan_settings.vlan_id}"
    
    def _configure_usb_to_lan_mode(self, vlan_settings):
        """Configure system for USB-to-LAN mode"""
        logger.info("Configuring USB-to-LAN mode")
        
        # Create USB-to-LAN configuration
        usb_config = self._generate_usb_to_lan_config(vlan_settings)
        
        # Update network interfaces
        success = self._update_network_interfaces(usb_config)
        if not success:
            return False, "Failed to update network interfaces"
        
        # Update hostapd configuration for USB WiFi
        success = self._update_hostapd_usb_config(vlan_settings)
        if not success:
            return False, "Failed to update hostapd configuration"
        
        # Update system status
        vlan_settings.current_status = 'USB to LAN Mode Active'
        vlan_settings.last_mode_change = timezone.now()
        vlan_settings.save()
        
        return True, "USB-to-LAN mode configured successfully"
    
    def _generate_vlan_config(self, vlan_settings):
        """Generate network configuration for VLAN mode"""
        config = f"""# Network configuration for VLAN mode
# Generated automatically - do not edit manually

auto lo
iface lo inet loopback

# Ethernet interface for VLAN
auto {vlan_settings.eth_interface}
iface {vlan_settings.eth_interface} inet manual

# VLAN interface
auto {vlan_settings.eth_interface}.{vlan_settings.vlan_id}
iface {vlan_settings.eth_interface}.{vlan_settings.vlan_id} inet dhcp
    vlan-raw-device {vlan_settings.eth_interface}

# USB WiFi interface for hotspot
auto {vlan_settings.usb_interface}
iface {vlan_settings.usb_interface} inet static
    address 192.168.4.1
    netmask 255.255.255.0
    network 192.168.4.0
    broadcast 192.168.4.255
"""
        return config
    
    def _generate_usb_to_lan_config(self, vlan_settings):
        """Generate network configuration for USB-to-LAN mode"""
        config = f"""# Network configuration for USB-to-LAN mode
# Generated automatically - do not edit manually

auto lo
iface lo inet loopback

# Ethernet interface for WAN
auto {vlan_settings.eth_interface}
iface {vlan_settings.eth_interface} inet dhcp

# USB WiFi interface for hotspot
auto {vlan_settings.usb_interface}
iface {vlan_settings.usb_interface} inet static
    address 192.168.4.1
    netmask 255.255.255.0
    network 192.168.4.0
    broadcast 192.168.4.255
"""
        return config
    
    def _update_network_interfaces(self, config):
        """Update /etc/network/interfaces file"""
        try:
            # Backup current configuration
            backup_file = f"{self.interfaces_file}.backup.{timezone.now().strftime('%Y%m%d_%H%M%S')}"
            if os.path.exists(self.interfaces_file):
                subprocess.run(['sudo', 'cp', self.interfaces_file, backup_file], check=True)
            
            # Write new configuration
            with open('/tmp/interfaces_new', 'w') as f:
                f.write(config)
            
            # Move to final location with sudo
            subprocess.run(['sudo', 'mv', '/tmp/interfaces_new', self.interfaces_file], check=True)
            subprocess.run(['sudo', 'chmod', '644', self.interfaces_file], check=True)
            
            logger.info("Network interfaces updated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error updating network interfaces: {e}")
            return False
    
    def _update_hostapd_vlan_config(self, vlan_settings):
        """Update hostapd configuration for VLAN mode"""
        try:
            config = f"""# Hostapd configuration for VLAN mode
interface={vlan_settings.usb_interface}
driver=nl80211
ssid=PisoWiFi-VLAN{vlan_settings.vlan_id}
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=0
"""
            
            with open('/tmp/hostapd_new', 'w') as f:
                f.write(config)
            
            subprocess.run(['sudo', 'mv', '/tmp/hostapd_new', self.hostapd_conf], check=True)
            subprocess.run(['sudo', 'chmod', '644', self.hostapd_conf], check=True)
            
            logger.info("Hostapd VLAN configuration updated")
            return True
            
        except Exception as e:
            logger.error(f"Error updating hostapd VLAN config: {e}")
            return False
    
    def _update_hostapd_usb_config(self, vlan_settings):
        """Update hostapd configuration for USB-to-LAN mode"""
        try:
            config = f"""# Hostapd configuration for USB-to-LAN mode
interface={vlan_settings.usb_interface}
driver=nl80211
ssid=PisoWiFi
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=0
"""
            
            with open('/tmp/hostapd_new', 'w') as f:
                f.write(config)
            
            subprocess.run(['sudo', 'mv', '/tmp/hostapd_new', self.hostapd_conf], check=True)
            subprocess.run(['sudo', 'chmod', '644', self.hostapd_conf], check=True)
            
            logger.info("Hostapd USB configuration updated")
            return True
            
        except Exception as e:
            logger.error(f"Error updating hostapd USB config: {e}")
            return False
    
    def restart_network_services(self):
        """Restart network services to apply changes"""
        try:
            logger.info("Restarting network services...")
            
            # Stop services
            subprocess.run(['sudo', 'systemctl', 'stop', 'hostapd'], check=False)
            subprocess.run(['sudo', 'systemctl', 'stop', 'dnsmasq'], check=False)
            
            # Restart networking
            subprocess.run(['sudo', 'systemctl', 'restart', 'networking'], check=True)
            
            # Start services
            subprocess.run(['sudo', 'systemctl', 'start', 'dnsmasq'], check=True)
            subprocess.run(['sudo', 'systemctl', 'start', 'hostapd'], check=True)
            
            logger.info("Network services restarted successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error restarting network services: {e}")
            return False
    
    def restart_system(self):
        """Restart the entire system"""
        try:
            logger.info("Initiating system restart...")
            subprocess.run(['sudo', 'shutdown', '-r', '+1'], check=True)
            return True
            
        except Exception as e:
            logger.error(f"Error initiating system restart: {e}")
            return False
    
    def get_current_network_status(self):
        """Get current network interface status"""
        try:
            # Get interface status
            result = subprocess.run(['ip', 'addr', 'show'], 
                                  capture_output=True, text=True, check=True)
            
            # Get VLAN interfaces
            vlan_result = subprocess.run(['ip', 'link', 'show', 'type', 'vlan'], 
                                       capture_output=True, text=True, check=False)
            
            return {
                'interfaces': result.stdout,
                'vlans': vlan_result.stdout,
                'status': 'active'
            }
            
        except Exception as e:
            logger.error(f"Error getting network status: {e}")
            return {
                'interfaces': '',
                'vlans': '',
                'status': 'error',
                'error': str(e)
            }
    
    def validate_vlan_id(self, vlan_id):
        """Validate VLAN ID range"""
        try:
            vlan_id = int(vlan_id)
            if 1 <= vlan_id <= 4094:
                return True, "Valid VLAN ID"
            else:
                return False, "VLAN ID must be between 1 and 4094"
        except ValueError:
            return False, "VLAN ID must be a number"
    
    def _check_vlan_prerequisites(self):
        """Check if system has VLAN support prerequisites"""
        try:
            # Check if VLAN package is installed
            result = subprocess.run(['dpkg', '-l', 'vlan'], 
                                  capture_output=True, text=True, check=False)
            if result.returncode != 0:
                # Try to install VLAN package
                logger.info("Installing VLAN package...")
                install_result = subprocess.run(['sudo', 'apt-get', 'update'], check=False)
                install_result = subprocess.run(['sudo', 'apt-get', 'install', '-y', 'vlan'], 
                                             capture_output=True, text=True, check=False)
                if install_result.returncode != 0:
                    return False, "Failed to install VLAN package. Please install manually: sudo apt-get install vlan"
            
            # Check if 8021q module is available
            modprobe_result = subprocess.run(['sudo', 'modprobe', '8021q'], 
                                           capture_output=True, text=True, check=False)
            if modprobe_result.returncode != 0:
                return False, "VLAN kernel module (8021q) not available on this system"
            
            # Ensure 8021q module loads on boot
            modules_file = '/etc/modules'
            try:
                with open(modules_file, 'r') as f:
                    content = f.read()
                if '8021q' not in content:
                    with open('/tmp/modules_new', 'w') as f:
                        f.write(content + '\n8021q\n')
                    subprocess.run(['sudo', 'mv', '/tmp/modules_new', modules_file], check=True)
                    subprocess.run(['sudo', 'chmod', '644', modules_file], check=True)
            except Exception as e:
                logger.warning(f"Could not update /etc/modules: {e}")
            
            return True, "VLAN prerequisites satisfied"
            
        except Exception as e:
            logger.error(f"Error checking VLAN prerequisites: {e}")
            return False, f"Error checking VLAN support: {str(e)}"
    
    def detect_network_interfaces(self):
        """Detect available network interfaces"""
        try:
            # Get all network interfaces
            result = subprocess.run(['ip', 'link', 'show'], 
                                  capture_output=True, text=True, check=True)
            
            ethernet_interfaces = []
            wifi_interfaces = []
            
            for line in result.stdout.split('\n'):
                if 'state UP' in line or 'state DOWN' in line:
                    # Extract interface name
                    parts = line.split(':')
                    if len(parts) >= 2:
                        interface = parts[1].strip()
                        
                        # Skip loopback and virtual interfaces
                        if interface in ['lo'] or interface.startswith('veth'):
                            continue
                            
                        # Classify interface type
                        if interface.startswith(('eth', 'en')):
                            ethernet_interfaces.append(interface)
                        elif interface.startswith(('wlan', 'wl')):
                            wifi_interfaces.append(interface)
            
            return {
                'ethernet': ethernet_interfaces,
                'wifi': wifi_interfaces,
                'detected': True
            }
            
        except Exception as e:
            logger.error(f"Error detecting network interfaces: {e}")
            return {
                'ethernet': ['eth0'],  # Fallback defaults
                'wifi': ['wlan0'],
                'detected': False,
                'error': str(e)
            }
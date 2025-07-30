"""
ZeroTier Remote Monitoring Service
Handles ZeroTier API communication and system monitoring
"""
import json
import subprocess
import psutil
import logging
import requests
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


class ZeroTierService:
    """Service for ZeroTier remote monitoring and management"""
    
    def __init__(self):
        self.local_api_url = 'http://localhost:9993'
        self.zerotier_cli = '/usr/sbin/zerotier-cli'
        
    def check_zerotier_installed(self):
        """Check if ZeroTier is installed on the system"""
        try:
            result = subprocess.run(['which', 'zerotier-cli'], 
                                  capture_output=True, text=True, check=False)
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Error checking ZeroTier installation: {e}")
            return False
    
    def install_zerotier(self):
        """Install ZeroTier on the system"""
        try:
            logger.info("Installing ZeroTier...")
            
            # Download and install ZeroTier
            install_cmd = 'curl -s https://install.zerotier.com | sudo bash'
            result = subprocess.run(install_cmd, shell=True, 
                                  capture_output=True, text=True, check=False)
            
            if result.returncode == 0:
                logger.info("ZeroTier installed successfully")
                return True, "ZeroTier installed successfully"
            else:
                logger.error(f"ZeroTier installation failed: {result.stderr}")
                return False, f"Installation failed: {result.stderr}"
                
        except Exception as e:
            logger.error(f"Error installing ZeroTier: {e}")
            return False, str(e)
    
    def get_zerotier_status(self):
        """Get ZeroTier service status"""
        try:
            if not self.check_zerotier_installed():
                return {
                    'installed': False,
                    'running': False,
                    'version': None,
                    'node_id': None
                }
            
            # Check if service is running
            service_result = subprocess.run(['sudo', 'systemctl', 'is-active', 'zerotier-one'], 
                                          capture_output=True, text=True, check=False)
            running = service_result.stdout.strip() == 'active'
            
            if not running:
                return {
                    'installed': True,
                    'running': False,
                    'version': None,
                    'node_id': None
                }
            
            # Get version and node ID
            version_result = subprocess.run([self.zerotier_cli, '-v'], 
                                          capture_output=True, text=True, check=False)
            version = version_result.stdout.strip() if version_result.returncode == 0 else None
            
            info_result = subprocess.run([self.zerotier_cli, 'info'], 
                                       capture_output=True, text=True, check=False)
            node_id = None
            if info_result.returncode == 0:
                # Extract node ID from info output
                info_parts = info_result.stdout.strip().split()
                if len(info_parts) > 2:
                    node_id = info_parts[2]
            
            return {
                'installed': True,
                'running': running,
                'version': version,
                'node_id': node_id
            }
            
        except Exception as e:
            logger.error(f"Error getting ZeroTier status: {e}")
            return {
                'installed': False,
                'running': False,
                'version': None,
                'node_id': None,
                'error': str(e)
            }
    
    def join_network(self, network_id):
        """Join a ZeroTier network"""
        try:
            if not self.check_zerotier_installed():
                return False, "ZeroTier is not installed"
            
            result = subprocess.run([self.zerotier_cli, 'join', network_id], 
                                  capture_output=True, text=True, check=False)
            
            if result.returncode == 0:
                logger.info(f"Successfully joined ZeroTier network: {network_id}")
                return True, f"Joined network {network_id}"
            else:
                logger.error(f"Failed to join network {network_id}: {result.stderr}")
                return False, result.stderr
                
        except Exception as e:
            logger.error(f"Error joining ZeroTier network: {e}")
            return False, str(e)
    
    def leave_network(self, network_id):
        """Leave a ZeroTier network"""
        try:
            result = subprocess.run([self.zerotier_cli, 'leave', network_id], 
                                  capture_output=True, text=True, check=False)
            
            if result.returncode == 0:
                logger.info(f"Successfully left ZeroTier network: {network_id}")
                return True, f"Left network {network_id}"
            else:
                logger.error(f"Failed to leave network {network_id}: {result.stderr}")
                return False, result.stderr
                
        except Exception as e:
            logger.error(f"Error leaving ZeroTier network: {e}")
            return False, str(e)
    
    def get_network_info(self, network_id):
        """Get information about joined network"""
        try:
            result = subprocess.run([self.zerotier_cli, 'listnetworks'], 
                                  capture_output=True, text=True, check=False)
            
            if result.returncode != 0:
                return None
            
            # Parse network list output
            lines = result.stdout.strip().split('\n')
            for line in lines[1:]:  # Skip header
                parts = line.split()
                if len(parts) >= 8 and parts[2] == network_id:
                    return {
                        'network_id': network_id,
                        'name': parts[3],
                        'status': parts[5],
                        'type': parts[6],
                        'dev': parts[7],
                        'zt_ip': parts[8] if len(parts) > 8 else None
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting network info: {e}")
            return None
    
    def get_system_metrics(self):
        """Collect system metrics for monitoring"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            
            # Network bandwidth (simplified)
            net_io = psutil.net_io_counters()
            
            return {
                'cpu_usage': cpu_percent,
                'memory_usage': memory_percent,
                'disk_usage': disk_percent,
                'bytes_sent': net_io.bytes_sent,
                'bytes_recv': net_io.bytes_recv,
                'timestamp': timezone.now()
            }
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            return None
    
    def get_pisowifi_metrics(self):
        """Collect PisoWiFi-specific metrics"""
        try:
            from app.models import Clients, Vouchers, CoinQueue, SalesReport
            
            # Connected clients
            connected_clients = Clients.objects.filter(
                Connection_Status='Connected'
            ).count()
            
            # Active vouchers
            active_vouchers = Vouchers.objects.filter(
                status='active'
            ).count()
            
            # Coin queue
            coin_queue_count = CoinQueue.objects.count()
            
            # Total revenue (last 24 hours)
            yesterday = timezone.now() - timedelta(days=1)
            from django.db import models
            recent_sales = SalesReport.objects.filter(
                created_at__gte=yesterday
            ).aggregate(
                total_revenue=models.Sum('total_amount')
            )
            total_revenue = recent_sales['total_revenue'] or 0
            
            return {
                'connected_clients': connected_clients,
                'active_vouchers': active_vouchers,
                'coin_queue_count': coin_queue_count,
                'total_revenue': float(total_revenue),
                'timestamp': timezone.now()
            }
            
        except Exception as e:
            logger.error(f"Error collecting PisoWiFi metrics: {e}")
            return {
                'connected_clients': 0,
                'active_vouchers': 0,
                'coin_queue_count': 0,
                'total_revenue': 0,
                'timestamp': timezone.now()
            }
    
    def send_monitoring_data_to_central(self, zt_settings, monitoring_data):
        """Send monitoring data to ZeroTier Central via API"""
        try:
            if not zt_settings.api_token:
                return False, "No API token configured"
            
            headers = {
                'Authorization': f'Bearer {zt_settings.api_token}',
                'Content-Type': 'application/json'
            }
            
            # Prepare payload
            payload = {
                'device_name': zt_settings.device_name,
                'timestamp': monitoring_data['timestamp'].isoformat(),
                'system_metrics': {
                    'cpu_usage': monitoring_data.get('cpu_usage'),
                    'memory_usage': monitoring_data.get('memory_usage'),
                    'disk_usage': monitoring_data.get('disk_usage')
                },
                'pisowifi_metrics': {
                    'connected_clients': monitoring_data.get('connected_clients', 0),
                    'active_vouchers': monitoring_data.get('active_vouchers', 0),
                    'total_revenue': monitoring_data.get('total_revenue', 0)
                }
            }
            
            # Note: ZeroTier Central API doesn't have a built-in monitoring endpoint
            # This would require a custom webhook or external monitoring service
            # For now, we'll store locally and provide API endpoint for external monitoring
            
            logger.info("Monitoring data prepared for transmission")
            return True, "Monitoring data ready"
            
        except Exception as e:
            logger.error(f"Error sending monitoring data: {e}")
            return False, str(e)
    
    def collect_and_store_monitoring_data(self, zt_settings):
        """Collect system and PisoWiFi metrics and store them"""
        try:
            from app.models import ZeroTierMonitoringData
            
            # Get ZeroTier status
            zt_status = self.get_zerotier_status()
            
            # Get network info
            network_info = None
            if zt_settings.network_id and zt_status['running']:
                network_info = self.get_network_info(zt_settings.network_id)
            
            # Collect metrics
            system_metrics = self.get_system_metrics()
            pisowifi_metrics = self.get_pisowifi_metrics()
            
            if not system_metrics or not pisowifi_metrics:
                return False, "Failed to collect metrics"
            
            # Create monitoring data record
            monitoring_data = ZeroTierMonitoringData.objects.create(
                network_online=zt_status['running'] and network_info is not None,
                zerotier_version=zt_status.get('version', ''),
                node_id=zt_status.get('node_id', ''),
                cpu_usage=system_metrics['cpu_usage'],
                memory_usage=system_metrics['memory_usage'],
                disk_usage=system_metrics['disk_usage'],
                connected_clients=pisowifi_metrics['connected_clients'],
                total_bandwidth_up=system_metrics['bytes_sent'],
                total_bandwidth_down=system_metrics['bytes_recv'],
                active_vouchers=pisowifi_metrics['active_vouchers'],
                total_revenue=pisowifi_metrics['total_revenue'],
                coin_queue_count=pisowifi_metrics['coin_queue_count']
            )
            
            # Update ZeroTier settings status
            if network_info:
                zt_settings.connection_status = 'Connected'
                zt_settings.zerotier_ip = network_info.get('zt_ip')
            else:
                zt_settings.connection_status = 'Disconnected'
                
            zt_settings.last_monitoring_update = timezone.now()
            zt_settings.save()
            
            logger.info("Monitoring data collected and stored successfully")
            return True, "Monitoring data collected successfully"
            
        except Exception as e:
            logger.error(f"Error collecting monitoring data: {e}")
            return False, str(e)
    
    def start_monitoring_service(self, zt_settings):
        """Start ZeroTier monitoring service"""
        try:
            if not zt_settings.is_monitoring_enabled():
                return False, "ZeroTier monitoring is not enabled or configured"
            
            # Check/install ZeroTier
            if not self.check_zerotier_installed():
                success, message = self.install_zerotier()
                if not success:
                    return False, f"Failed to install ZeroTier: {message}"
            
            # Start ZeroTier service
            service_result = subprocess.run(['sudo', 'systemctl', 'start', 'zerotier-one'], 
                                          capture_output=True, text=True, check=False)
            if service_result.returncode != 0:
                return False, "Failed to start ZeroTier service"
            
            # Join network
            if zt_settings.network_id:
                success, message = self.join_network(zt_settings.network_id)
                if not success:
                    return False, f"Failed to join network: {message}"
            
            # Enable service on boot
            subprocess.run(['sudo', 'systemctl', 'enable', 'zerotier-one'], check=False)
            
            # Initial monitoring data collection
            self.collect_and_store_monitoring_data(zt_settings)
            
            return True, "ZeroTier monitoring service started successfully"
            
        except Exception as e:
            logger.error(f"Error starting monitoring service: {e}")
            return False, str(e)
    
    def stop_monitoring_service(self, zt_settings):
        """Stop ZeroTier monitoring service"""
        try:
            # Leave network if configured
            if zt_settings.network_id:
                self.leave_network(zt_settings.network_id)
            
            # Update status
            zt_settings.connection_status = 'Disconnected'
            zt_settings.zerotier_ip = None
            zt_settings.save()
            
            return True, "ZeroTier monitoring service stopped"
            
        except Exception as e:
            logger.error(f"Error stopping monitoring service: {e}")
            return False, str(e)
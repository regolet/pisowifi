"""
System information utilities for PISOWifi dashboard
"""
import psutil
import platform
import socket
import subprocess
import os
import time
from datetime import timedelta, datetime
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def get_cpu_usage():
    """Get current CPU usage percentage"""
    try:
        return psutil.cpu_percent(interval=1)
    except Exception as e:
        logger.error(f"Error getting CPU usage: {e}")
        return 0

def get_cpu_info():
    """Get CPU information"""
    try:
        return {
            'physical_cores': psutil.cpu_count(logical=False),
            'total_cores': psutil.cpu_count(logical=True),
            'max_frequency': psutil.cpu_freq().max if psutil.cpu_freq() else 0,
            'current_frequency': psutil.cpu_freq().current if psutil.cpu_freq() else 0,
        }
    except Exception as e:
        logger.error(f"Error getting CPU info: {e}")
        return {
            'physical_cores': 0,
            'total_cores': 0,
            'max_frequency': 0,
            'current_frequency': 0,
        }

def get_memory_usage():
    """Get memory usage information"""
    try:
        memory = psutil.virtual_memory()
        return {
            'total': memory.total,
            'available': memory.available,
            'used': memory.used,
            'free': memory.free,
            'percent': memory.percent,
            'total_gb': round(memory.total / (1024**3), 2),
            'used_gb': round(memory.used / (1024**3), 2),
            'free_gb': round(memory.available / (1024**3), 2),
        }
    except Exception as e:
        logger.error(f"Error getting memory usage: {e}")
        return {
            'total': 0, 'available': 0, 'used': 0, 'free': 0, 'percent': 0,
            'total_gb': 0, 'used_gb': 0, 'free_gb': 0,
        }

def get_disk_usage():
    """Get disk usage information"""
    try:
        # Get the disk usage of the project directory
        base_dir = getattr(settings, 'BASE_DIR', '/')
        disk = psutil.disk_usage(base_dir)
        
        return {
            'total': disk.total,
            'used': disk.used,
            'free': disk.free,
            'percent': round((disk.used / disk.total) * 100, 1),
            'total_gb': round(disk.total / (1024**3), 2),
            'used_gb': round(disk.used / (1024**3), 2),
            'free_gb': round(disk.free / (1024**3), 2),
        }
    except Exception as e:
        logger.error(f"Error getting disk usage: {e}")
        return {
            'total': 0, 'used': 0, 'free': 0, 'percent': 0,
            'total_gb': 0, 'used_gb': 0, 'free_gb': 0,
        }

def get_system_temperature():
    """Get system temperature (if available)"""
    try:
        # Try to get temperature sensors
        temps = psutil.sensors_temperatures()
        if temps:
            # Look for common temperature sensors
            for sensor_name, sensor_list in temps.items():
                if 'cpu' in sensor_name.lower() or 'coretemp' in sensor_name.lower():
                    if sensor_list:
                        return {
                            'sensor': sensor_name,
                            'current': sensor_list[0].current,
                            'high': sensor_list[0].high if sensor_list[0].high else None,
                            'critical': sensor_list[0].critical if sensor_list[0].critical else None,
                        }
            
            # If no CPU temp found, return first available sensor
            first_sensor = list(temps.keys())[0]
            if temps[first_sensor]:
                return {
                    'sensor': first_sensor,
                    'current': temps[first_sensor][0].current,
                    'high': temps[first_sensor][0].high if temps[first_sensor][0].high else None,
                    'critical': temps[first_sensor][0].critical if temps[first_sensor][0].critical else None,
                }
        
        # Try reading from common temperature files on Linux/Raspberry Pi
        temp_paths = [
            '/sys/class/thermal/thermal_zone0/temp',  # Common Linux
            '/sys/class/hwmon/hwmon0/temp1_input',    # Some systems
        ]
        
        for path in temp_paths:
            if os.path.exists(path):
                try:
                    with open(path, 'r') as f:
                        temp_raw = int(f.read().strip())
                        temp_celsius = temp_raw / 1000.0 if temp_raw > 1000 else temp_raw
                        return {
                            'sensor': 'System',
                            'current': temp_celsius,
                            'high': None,
                            'critical': None,
                        }
                except:
                    continue
        
        return None
    except Exception as e:
        logger.error(f"Error getting temperature: {e}")
        return None

def get_system_uptime():
    """Get system uptime"""
    try:
        boot_time = psutil.boot_time()
        uptime_seconds = time.time() - boot_time
        uptime_delta = timedelta(seconds=int(uptime_seconds))
        
        return {
            'boot_time': datetime.fromtimestamp(boot_time),
            'uptime_seconds': int(uptime_seconds),
            'uptime_string': str(uptime_delta),
            'uptime_days': uptime_delta.days,
            'uptime_hours': uptime_delta.seconds // 3600,
            'uptime_minutes': (uptime_delta.seconds % 3600) // 60,
        }
    except Exception as e:
        logger.error(f"Error getting uptime: {e}")
        return {
            'boot_time': None,
            'uptime_seconds': 0,
            'uptime_string': 'Unknown',
            'uptime_days': 0,
            'uptime_hours': 0,
            'uptime_minutes': 0,
        }

def get_network_info():
    """Get network interface information"""
    try:
        interfaces = {}
        net_io = psutil.net_io_counters(pernic=True)
        net_if_addrs = psutil.net_if_addrs()
        
        for interface, addrs in net_if_addrs.items():
            if interface in net_io:
                ip_addresses = []
                for addr in addrs:
                    if addr.family == socket.AF_INET:  # IPv4
                        ip_addresses.append(addr.address)
                
                interfaces[interface] = {
                    'ip_addresses': ip_addresses,
                    'bytes_sent': net_io[interface].bytes_sent,
                    'bytes_recv': net_io[interface].bytes_recv,
                    'packets_sent': net_io[interface].packets_sent,
                    'packets_recv': net_io[interface].packets_recv,
                    'is_up': psutil.net_if_stats()[interface].isup if interface in psutil.net_if_stats() else False,
                }
        
        return interfaces
    except Exception as e:
        logger.error(f"Error getting network info: {e}")
        return {}

def get_process_info():
    """Get process information"""
    try:
        current_process = psutil.Process()
        return {
            'pid': current_process.pid,
            'name': current_process.name(),
            'cpu_percent': current_process.cpu_percent(),
            'memory_percent': current_process.memory_percent(),
            'memory_info': current_process.memory_info(),
            'num_threads': current_process.num_threads(),
            'create_time': datetime.fromtimestamp(current_process.create_time()),
        }
    except Exception as e:
        logger.error(f"Error getting process info: {e}")
        return {
            'pid': 0, 'name': 'Unknown', 'cpu_percent': 0, 'memory_percent': 0,
            'memory_info': None, 'num_threads': 0, 'create_time': None,
        }

def get_system_info():
    """Get basic system information"""
    try:
        return {
            'system': platform.system(),
            'node_name': platform.node(),
            'release': platform.release(),
            'version': platform.version(),
            'machine': platform.machine(),
            'processor': platform.processor(),
            'architecture': platform.architecture()[0],
            'python_version': platform.python_version(),
        }
    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        return {
            'system': 'Unknown', 'node_name': 'Unknown', 'release': 'Unknown',
            'version': 'Unknown', 'machine': 'Unknown', 'processor': 'Unknown',
            'architecture': 'Unknown', 'python_version': 'Unknown',
        }

def get_load_average():
    """Get system load average (Unix-like systems only)"""
    try:
        if hasattr(os, 'getloadavg'):
            load1, load5, load15 = os.getloadavg()
            return {
                'load1': round(load1, 2),
                'load5': round(load5, 2),
                'load15': round(load15, 2),
            }
        return None
    except Exception as e:
        logger.error(f"Error getting load average: {e}")
        return None

def get_users():
    """Get logged in users"""
    try:
        users = []
        for user in psutil.users():
            users.append({
                'name': user.name,
                'terminal': user.terminal,
                'host': user.host,
                'started': datetime.fromtimestamp(user.started),
            })
        return users
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        return []

def get_all_system_info():
    """Get comprehensive system information"""
    return {
        'timestamp': datetime.now(),
        'cpu': {
            'usage': get_cpu_usage(),
            'info': get_cpu_info(),
        },
        'memory': get_memory_usage(),
        'disk': get_disk_usage(),
        'temperature': get_system_temperature(),
        'uptime': get_system_uptime(),
        'network': get_network_info(),
        'process': get_process_info(),
        'system': get_system_info(),
        'load_average': get_load_average(),
        'users': get_users(),
    }

def format_bytes(bytes_value):
    """Format bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f} PB"

def get_disk_io():
    """Get disk I/O statistics"""
    try:
        disk_io = psutil.disk_io_counters()
        if disk_io:
            return {
                'read_count': disk_io.read_count,
                'write_count': disk_io.write_count,
                'read_bytes': disk_io.read_bytes,
                'write_bytes': disk_io.write_bytes,
                'read_time': disk_io.read_time,
                'write_time': disk_io.write_time,
            }
        return None
    except Exception as e:
        logger.error(f"Error getting disk I/O: {e}")
        return None
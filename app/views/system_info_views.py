"""
System Information Views for PISOWifi Admin Dashboard
"""
from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from app.utils.system_info import (
    get_all_system_info, get_cpu_usage, get_memory_usage, 
    get_disk_usage, get_system_temperature, get_system_uptime,
    format_bytes, get_disk_io, get_network_info
)
import json
from datetime import datetime


@staff_member_required
def system_info_dashboard(request):
    """System information dashboard view"""
    context = {
        'title': 'System Information',
        'system_info': get_all_system_info(),
    }
    return render(request, 'admin/system_info/dashboard.html', context)


@staff_member_required
@require_http_methods(["GET"])
def system_info_api(request):
    """API endpoint for live system information updates"""
    try:
        system_info = get_all_system_info()
        
        # Format the data for JSON response
        formatted_info = {
            'timestamp': system_info['timestamp'].isoformat(),
            'cpu': {
                'usage': system_info['cpu']['usage'],
                'cores': system_info['cpu']['info']['total_cores'],
                'physical_cores': system_info['cpu']['info']['physical_cores'],
                'frequency': system_info['cpu']['info']['current_frequency'],
                'max_frequency': system_info['cpu']['info']['max_frequency'],
            },
            'memory': {
                'used_percent': system_info['memory']['percent'],
                'used_gb': system_info['memory']['used_gb'],
                'total_gb': system_info['memory']['total_gb'],
                'free_gb': system_info['memory']['free_gb'],
                'available_gb': system_info['memory']['free_gb'],
            },
            'disk': {
                'used_percent': system_info['disk']['percent'],
                'used_gb': system_info['disk']['used_gb'],
                'total_gb': system_info['disk']['total_gb'],
                'free_gb': system_info['disk']['free_gb'],
            },
            'temperature': system_info['temperature'],
            'uptime': {
                'days': system_info['uptime']['uptime_days'],
                'hours': system_info['uptime']['uptime_hours'],
                'minutes': system_info['uptime']['uptime_minutes'],
                'string': system_info['uptime']['uptime_string'],
                'boot_time': system_info['uptime']['boot_time'].isoformat() if system_info['uptime']['boot_time'] else None,
            },
            'system': system_info['system'],
            'load_average': system_info['load_average'],
            'process': {
                'pid': system_info['process']['pid'],
                'cpu_percent': system_info['process']['cpu_percent'],
                'memory_percent': system_info['process']['memory_percent'],
                'threads': system_info['process']['num_threads'],
            },
            'users': len(system_info['users']),
            'network_interfaces': len(system_info['network']),
        }
        
        # Add network info
        main_interfaces = {}
        for interface, info in system_info['network'].items():
            if info['is_up'] and info['ip_addresses']:
                main_interfaces[interface] = {
                    'ip': info['ip_addresses'][0] if info['ip_addresses'] else 'N/A',
                    'bytes_sent': info['bytes_sent'],
                    'bytes_recv': info['bytes_recv'],
                    'is_up': info['is_up'],
                }
        formatted_info['network'] = main_interfaces
        
        return JsonResponse(formatted_info)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@staff_member_required
@require_http_methods(["GET"])
def system_info_detailed_api(request):
    """Detailed system information API"""
    try:
        system_info = get_all_system_info()
        
        # Get disk I/O stats
        disk_io = get_disk_io()
        
        detailed_info = {
            'timestamp': system_info['timestamp'].isoformat(),
            'system_details': {
                'hostname': system_info['system']['node_name'],
                'platform': system_info['system']['system'],
                'release': system_info['system']['release'],
                'architecture': system_info['system']['architecture'],
                'processor': system_info['system']['processor'],
                'python_version': system_info['system']['python_version'],
            },
            'cpu_details': {
                'usage_percent': system_info['cpu']['usage'],
                'physical_cores': system_info['cpu']['info']['physical_cores'],
                'logical_cores': system_info['cpu']['info']['total_cores'],
                'frequency_mhz': system_info['cpu']['info']['current_frequency'],
                'max_frequency_mhz': system_info['cpu']['info']['max_frequency'],
            },
            'memory_details': {
                'total_bytes': system_info['memory']['total'],
                'used_bytes': system_info['memory']['used'],
                'free_bytes': system_info['memory']['free'],
                'available_bytes': system_info['memory']['available'],
                'usage_percent': system_info['memory']['percent'],
                'total_formatted': format_bytes(system_info['memory']['total']),
                'used_formatted': format_bytes(system_info['memory']['used']),
                'free_formatted': format_bytes(system_info['memory']['available']),
            },
            'disk_details': {
                'total_bytes': system_info['disk']['total'],
                'used_bytes': system_info['disk']['used'],
                'free_bytes': system_info['disk']['free'],
                'usage_percent': system_info['disk']['percent'],
                'total_formatted': format_bytes(system_info['disk']['total']),
                'used_formatted': format_bytes(system_info['disk']['used']),
                'free_formatted': format_bytes(system_info['disk']['free']),
            },
            'disk_io': disk_io,
            'network_details': system_info['network'],
            'process_details': {
                'pid': system_info['process']['pid'],
                'name': system_info['process']['name'],
                'cpu_percent': system_info['process']['cpu_percent'],
                'memory_percent': system_info['process']['memory_percent'],
                'threads': system_info['process']['num_threads'],
                'memory_rss': system_info['process']['memory_info'].rss if system_info['process']['memory_info'] else 0,
                'memory_vms': system_info['process']['memory_info'].vms if system_info['process']['memory_info'] else 0,
                'create_time': system_info['process']['create_time'].isoformat() if system_info['process']['create_time'] else None,
            },
            'temperature': system_info['temperature'],
            'uptime_details': system_info['uptime'],
            'load_average': system_info['load_average'],
            'logged_users': system_info['users'],
        }
        
        return JsonResponse(detailed_info)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def get_system_status():
    """Get system status for dashboard cards"""
    try:
        info = get_all_system_info()
        
        # Determine status levels based on usage
        cpu_status = 'success' if info['cpu']['usage'] < 70 else 'warning' if info['cpu']['usage'] < 90 else 'danger'
        memory_status = 'success' if info['memory']['percent'] < 70 else 'warning' if info['memory']['percent'] < 85 else 'danger'
        disk_status = 'success' if info['disk']['percent'] < 80 else 'warning' if info['disk']['percent'] < 90 else 'danger'
        
        temp_status = 'success'
        if info['temperature']:
            temp = info['temperature']['current']
            if temp > 80:
                temp_status = 'danger'
            elif temp > 70:
                temp_status = 'warning'
        
        return {
            'cpu': {
                'usage': info['cpu']['usage'],
                'status': cpu_status,
                'cores': info['cpu']['info']['total_cores'],
            },
            'memory': {
                'usage': info['memory']['percent'],
                'status': memory_status,
                'used_gb': info['memory']['used_gb'],
                'total_gb': info['memory']['total_gb'],
            },
            'disk': {
                'usage': info['disk']['percent'],
                'status': disk_status,
                'used_gb': info['disk']['used_gb'],
                'total_gb': info['disk']['total_gb'],
                'free_gb': info['disk']['free_gb'],
            },
            'temperature': {
                'value': info['temperature']['current'] if info['temperature'] else None,
                'status': temp_status,
                'sensor': info['temperature']['sensor'] if info['temperature'] else None,
            },
            'uptime': {
                'days': info['uptime']['uptime_days'],
                'hours': info['uptime']['uptime_hours'],
                'minutes': info['uptime']['uptime_minutes'],
            },
            'system': {
                'hostname': info['system']['node_name'],
                'platform': info['system']['system'],
                'architecture': info['system']['architecture'],
            },
        }
    except Exception as e:
        # Return safe defaults on error
        return {
            'cpu': {'usage': 0, 'status': 'secondary', 'cores': 0},
            'memory': {'usage': 0, 'status': 'secondary', 'used_gb': 0, 'total_gb': 0},
            'disk': {'usage': 0, 'status': 'secondary', 'used_gb': 0, 'total_gb': 0, 'free_gb': 0},
            'temperature': {'value': None, 'status': 'secondary', 'sensor': None},
            'uptime': {'days': 0, 'hours': 0, 'minutes': 0},
            'system': {'hostname': 'Unknown', 'platform': 'Unknown', 'architecture': 'Unknown'},
            'error': str(e),
        }
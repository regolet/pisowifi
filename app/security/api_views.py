"""
API Key management views for PISOWifi admin
"""

from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from django.contrib.auth.models import User
from django.contrib import messages
from django.urls import reverse
from django.http import HttpResponseRedirect
from .api_auth import api_key_manager, APIKeyManager
import json


@method_decorator([login_required, staff_member_required], name='dispatch')
class APIKeyManagementView(TemplateView):
    """
    API Key management interface
    """
    template_name = 'admin/security/api_keys.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get available permissions
        permissions = APIKeyManager.PERMISSIONS
        
        # Get users for selection
        users = User.objects.filter(is_staff=True)
        
        context.update({
            'permissions': permissions,
            'users': users,
            'page_title': 'API Key Management',
        })
        
        return context


@login_required
@staff_member_required
def create_api_key_view(request):
    """
    Create a new API key
    """
    if request.method == 'POST':
        try:
            name = request.POST.get('name')
            user_id = request.POST.get('user_id')
            permissions = request.POST.getlist('permissions')
            expires_days = request.POST.get('expires_days')
            
            if not name:
                return JsonResponse({
                    'success': False,
                    'error': 'Name is required'
                }, status=400)
            
            # Get user
            user = None
            if user_id:
                try:
                    user = User.objects.get(id=user_id)
                except User.DoesNotExist:
                    return JsonResponse({
                        'success': False,
                        'error': 'Invalid user selected'
                    }, status=400)
            
            # Parse expiration days
            expires_days_int = None
            if expires_days:
                try:
                    expires_days_int = int(expires_days)
                    if expires_days_int <= 0:
                        expires_days_int = None
                except ValueError:
                    return JsonResponse({
                        'success': False,
                        'error': 'Invalid expiration days'
                    }, status=400)
            
            # Create API key
            api_key = api_key_manager.generate_api_key(
                user=user or request.user,
                name=name,
                permissions=permissions,
                expires_days=expires_days_int
            )
            
            return JsonResponse({
                'success': True,
                'message': 'API key created successfully',
                'api_key': {
                    'key_id': api_key.key_id,
                    'key_secret': api_key.key_secret,
                    'name': api_key.name,
                    'permissions': api_key.permissions,
                    'expires_at': api_key.expires_at.isoformat() if api_key.expires_at else None
                }
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'error': 'Invalid request method'
    }, status=405)


@login_required
@staff_member_required
def revoke_api_key_view(request):
    """
    Revoke an API key
    """
    if request.method == 'POST':
        key_id = request.POST.get('key_id')
        
        if not key_id:
            return JsonResponse({
                'success': False,
                'error': 'Key ID is required'
            }, status=400)
        
        try:
            success = api_key_manager.revoke_api_key(key_id, request.user.username)
            
            if success:
                return JsonResponse({
                    'success': True,
                    'message': f'API key {key_id} has been revoked'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'API key not found'
                }, status=404)
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'error': 'Invalid request method'
    }, status=405)


@login_required
@staff_member_required
def test_api_key_view(request):
    """
    Test an API key
    """
    if request.method == 'POST':
        key_id = request.POST.get('key_id')
        
        if not key_id:
            return JsonResponse({
                'success': False,
                'error': 'Key ID is required'
            }, status=400)
        
        try:
            api_key = api_key_manager._get_api_key(key_id)
            
            if not api_key:
                return JsonResponse({
                    'success': False,
                    'error': 'API key not found'
                }, status=404)
            
            # Check if key is valid
            is_valid = api_key.is_valid()
            
            return JsonResponse({
                'success': True,
                'api_key_status': {
                    'key_id': api_key.key_id,
                    'name': api_key.name,
                    'is_valid': is_valid,
                    'expires_at': api_key.expires_at.isoformat() if api_key.expires_at else None,
                    'last_used': api_key.last_used.isoformat() if api_key.last_used else None,
                    'usage_count': api_key.usage_count,
                    'permissions': api_key.permissions
                }
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'error': 'Invalid request method'
    }, status=405)


# Example protected API endpoints
from .api_auth import require_api_permission, api_rate_limit


@require_api_permission('read_clients')
@api_rate_limit(max_requests=100, window_minutes=60)
def api_clients_list(request):
    """
    API endpoint to list clients (example)
    """
    try:
        from app.models import Clients
        
        clients = Clients.objects.all()[:50]  # Limit to 50 for example
        
        client_data = []
        for client in clients:
            client_data.append({
                'id': client.id,
                'mac_address': client.mac_address,
                'device_name': client.device_name,
                'status': client.status,
                'time_remaining': str(client.time_remaining) if client.time_remaining else None,
                'data_remaining': client.data_remaining,
                'connected_at': client.connected_at.isoformat() if client.connected_at else None
            })
        
        return JsonResponse({
            'success': True,
            'clients': client_data,
            'total_count': len(client_data)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_api_permission('read_reports')
@api_rate_limit(max_requests=50, window_minutes=60)
def api_sales_summary(request):
    """
    API endpoint to get sales summary (example)
    """
    try:
        from app.models import SalesReport
        from django.db.models import Sum
        from datetime import datetime, timedelta
        
        # Get sales for last 30 days
        thirty_days_ago = datetime.now() - timedelta(days=30)
        
        total_sales = SalesReport.objects.filter(
            date__gte=thirty_days_ago
        ).aggregate(
            total=Sum('total_amount')
        )['total'] or 0
        
        return JsonResponse({
            'success': True,
            'sales_summary': {
                'period': '30_days',
                'total_sales': float(total_sales),
                'currency': 'PHP'
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_api_permission('read_system')
@api_rate_limit(max_requests=30, window_minutes=60)
def api_system_status(request):
    """
    API endpoint to get system status (example)
    """
    try:
        from app.models import Clients
        
        total_clients = Clients.objects.count()
        active_clients = Clients.objects.filter(status='connected').count()
        
        return JsonResponse({
            'success': True,
            'system_status': {
                'total_clients': total_clients,
                'active_clients': active_clients,
                'uptime': 'N/A',  # Would need to implement uptime tracking
                'memory_usage': 'N/A',  # Would need to implement system monitoring
                'disk_usage': 'N/A'
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
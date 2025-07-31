"""
Security dashboard views for PISOWifi
"""

from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from .monitoring import security_monitor
from .fail2ban_config import fail2ban_manager
import json


@method_decorator([login_required, staff_member_required], name='dispatch')
class SecurityDashboardView(TemplateView):
    """
    Security dashboard with real-time monitoring data
    """
    template_name = 'admin/security/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get dashboard data
        dashboard_data = security_monitor.get_security_dashboard_data()
        
        # Get fail2ban status
        try:
            fail2ban_status = fail2ban_manager.get_jail_status()
            fail2ban_banned_ips = fail2ban_manager.get_banned_ips()
        except Exception:
            fail2ban_status = {}
            fail2ban_banned_ips = []
        
        # Add fail2ban data to dashboard
        dashboard_data['fail2ban'] = {
            'jail_status': fail2ban_status,
            'banned_ips': fail2ban_banned_ips,
            'total_banned': len(fail2ban_banned_ips)
        }
        
        # Add additional context
        context.update({
            'dashboard_data': dashboard_data,
            'dashboard_data_json': json.dumps(dashboard_data, default=str),
            'page_title': 'Security Dashboard',
            'site_title': 'PISOWifi Security',
        })
        
        return context


@login_required
@staff_member_required
def security_dashboard_api(request):
    """
    API endpoint for real-time dashboard data
    """
    try:
        dashboard_data = security_monitor.get_security_dashboard_data()
        return JsonResponse({
            'success': True,
            'data': dashboard_data
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required 
@staff_member_required
def security_report_view(request):
    """
    Generate security report
    """
    days = int(request.GET.get('days', 7))
    
    try:
        report_data = security_monitor.generate_security_report(days)
        
        if request.GET.get('format') == 'json':
            return JsonResponse({
                'success': True,
                'report': report_data
            })
        
        return render(request, 'admin/security/report.html', {
            'report': report_data,
            'days': days,
            'page_title': f'Security Report - Last {days} Days',
        })
        
    except Exception as e:
        if request.GET.get('format') == 'json':
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
        
        return render(request, 'admin/security/report.html', {
            'error': str(e),
            'days': days,
            'page_title': 'Security Report - Error',
        })


@login_required
@staff_member_required
def security_alerts_view(request):
    """
    View recent security alerts
    """
    from django.core.cache import cache
    
    alerts = cache.get("security_alerts", [])
    
    return render(request, 'admin/security/alerts.html', {
        'alerts': alerts[-50:],  # Show last 50 alerts
        'page_title': 'Security Alerts',
    })


@login_required
@staff_member_required
def block_ip_view(request):
    """
    Manually block an IP address
    """
    if request.method == 'POST':
        ip_address = request.POST.get('ip_address')
        reason = request.POST.get('reason', 'Manual block by admin')
        
        if ip_address:
            from .handlers import block_ip_address
            
            try:
                block_ip_address(ip_address, reason, request.user.username)
                
                # Log the action
                security_monitor.log_security_event(
                    'admin_ip_block',
                    ip_address,
                    {
                        'reason': reason,
                        'blocked_by': request.user.username,
                        'manual_block': True
                    }
                )
                
                return JsonResponse({
                    'success': True,
                    'message': f'IP {ip_address} has been blocked'
                })
                
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'error': str(e)
                }, status=500)
    
    return JsonResponse({
        'success': False,
        'error': 'Invalid request'
    }, status=400)


@login_required
@staff_member_required
def fail2ban_unban_view(request):
    """
    Unban IP from fail2ban
    """
    if request.method == 'POST':
        ip_address = request.POST.get('ip_address')
        
        if ip_address:
            try:
                success = fail2ban_manager.unban_ip(ip_address)
                
                if success:
                    # Log the action
                    security_monitor.log_security_event(
                        'fail2ban_manual_unban',
                        ip_address,
                        {
                            'unbanned_by': request.user.username,
                            'manual_unban': True,
                            'method': 'admin_dashboard'
                        }
                    )
                    
                    return JsonResponse({
                        'success': True,
                        'message': f'IP {ip_address} has been unbanned from fail2ban'
                    })
                else:
                    return JsonResponse({
                        'success': False,
                        'error': 'Failed to unban IP from fail2ban'
                    }, status=500)
                    
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'error': str(e)
                }, status=500)
    
    return JsonResponse({
        'success': False,
        'error': 'Invalid request'
    }, status=400)


@login_required
@staff_member_required
def unblock_ip_view(request):
    """
    Manually unblock an IP address
    """
    if request.method == 'POST':
        ip_address = request.POST.get('ip_address')
        
        if ip_address:
            from .handlers import unblock_ip_address
            
            try:
                unblock_ip_address(ip_address, request.user.username)
                
                # Log the action
                security_monitor.log_security_event(
                    'admin_ip_unblock',
                    ip_address,
                    {
                        'unblocked_by': request.user.username,
                        'manual_unblock': True
                    }
                )
                
                return JsonResponse({
                    'success': True,
                    'message': f'IP {ip_address} has been unblocked'
                })
                
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'error': str(e)
                }, status=500)
    
    return JsonResponse({
        'success': False,
        'error': 'Invalid request'
    }, status=400)


@login_required
@staff_member_required
def fail2ban_unban_view(request):
    """
    Unban IP from fail2ban
    """
    if request.method == 'POST':
        ip_address = request.POST.get('ip_address')
        
        if ip_address:
            try:
                success = fail2ban_manager.unban_ip(ip_address)
                
                if success:
                    # Log the action
                    security_monitor.log_security_event(
                        'fail2ban_manual_unban',
                        ip_address,
                        {
                            'unbanned_by': request.user.username,
                            'manual_unban': True,
                            'method': 'admin_dashboard'
                        }
                    )
                    
                    return JsonResponse({
                        'success': True,
                        'message': f'IP {ip_address} has been unbanned from fail2ban'
                    })
                else:
                    return JsonResponse({
                        'success': False,
                        'error': 'Failed to unban IP from fail2ban'
                    }, status=500)
                    
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'error': str(e)
                }, status=500)
    
    return JsonResponse({
        'success': False,
        'error': 'Invalid request'
    }, status=400)
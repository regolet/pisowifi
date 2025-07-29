from django.core.exceptions import ObjectDoesNotExist
from django.contrib import admin, messages
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils import timezone
from app import models, forms

def client_check(request):
    # Licensing disabled for personal use
    return True


class Singleton(admin.ModelAdmin):
    # Use default Jazzmin change form template

    def get_urls(self):
        urls = super(Singleton, self).get_urls()
        model_name = self.model._meta.model_name
        self.model._meta.verbose_name_plural = self.model._meta.verbose_name
        url_name_prefix = '%(app_name)s_%(model_name)s' % {
            'app_name': self.model._meta.app_label,
            'model_name': model_name,
        }
        custom_urls = [
            path('',
                self.admin_site.admin_view(self.change_view),
                {'object_id': str(1)},
                name='%s_change' % url_name_prefix),
        ]
        return custom_urls + urls

    # def response_change(self, request, obj):
    #     msg = '%s changed successfully' % obj
    #     self.message_user(request, msg)
    #     return HttpResponseRedirect("../../")


class ClientsAdmin(admin.ModelAdmin):
    list_display = ('IP_Address', 'MAC_Address', 'Device_Name', 'auth_status', 'Connection_Status', 'block_status', 'Time_Left', 'running_time', 'action_buttons')
    readonly_fields = ('IP_Address', 'MAC_Address', 'Expire_On', 'Notification_ID', 'Notified_Flag', 'Date_Created')
    actions = None  # Disable bulk actions since we have individual buttons
    list_filter = (('Expire_On', admin.EmptyFieldListFilter),)  # Add filter for authenticated/unauthenticated

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context.update({
            'title': 'All Clients'
        })
        return super(ClientsAdmin, self).changelist_view(request, extra_context=extra_context)
    
    def auth_status(self, obj):
        """Show authentication status"""
        from django.utils.html import format_html
        if obj.Expire_On and obj.Expire_On > timezone.now():
            return format_html('<span style="color: green; font-weight: bold;">✓ Authenticated</span>')
        else:
            return format_html('<span style="color: red; font-weight: bold;">✗ Unauthenticated</span>')
    
    auth_status.short_description = 'Auth Status'
    auth_status.admin_order_field = 'Expire_On'

    def message_user(self, request, message, level=messages.INFO, extra_tags='', fail_silently=False):
        # Allow messages for admin actions
        messages.add_message(request, level, message, extra_tags=extra_tags, fail_silently=fail_silently)

    def Connect(self, request, queryset):
        for obj in queryset:
            res = obj.Connect()
            device_name = obj.MAC_Address if not obj.Device_Name else obj.Device_Name
            if res:
                messages.add_message(request, messages.SUCCESS, 'Device {} is now connected.'. format(device_name))
            else:
                messages.add_message(request, messages.WARNING, 'Unable to connect device {}'. format(device_name))

    def Disconnect(self, request, queryset):
        for obj in queryset:
            res = obj.Disconnect()
            device_name = obj.MAC_Address if not obj.Device_Name else obj.Device_Name
            if res:
                messages.add_message(request, messages.SUCCESS, 'Device {} is now disconnected.'. format(device_name))
            else:
                messages.add_message(request, messages.WARNING, 'Device {} is already disconnected/paused.'. format(device_name))

    def Pause(self, request, queryset):
        for obj in queryset:
            res = obj.Pause()
            device_name = obj.MAC_Address if not obj.Device_Name else obj.Device_Name
            if res:
                messages.add_message(request, messages.SUCCESS, 'Device {} is now paused.'. format(device_name))
            else:
                messages.add_message(request, messages.WARNING, 'Device {} is already paused/disconnected.'. format(device_name))


    def Whitelist(self, request, queryset):      
        for obj in queryset:
            device, created = models.Whitelist.objects.get_or_create(MAC_Address=obj.MAC_Address, defaults={'Device_Name': obj.Device_Name})
            device_name = obj.MAC_Address if not obj.Device_Name else obj.Device_Name
            if created:
                messages.add_message(request, messages.SUCCESS, 'Device {} is sucessfully added to whitelisted devices'.format(device_name))
                obj.delete()
            else:
                messages.add_message(request, messages.WARNING, 'Device {} was already added on the whitelisted devices'.format(device_name))

    @admin.display(description='Block Status')
    def block_status(self, obj):
        """Show current block status of the device"""
        try:
            blocked_device = models.BlockedDevices.objects.get(MAC_Address=obj.MAC_Address, Is_Active=True)
            if blocked_device.is_block_expired():
                blocked_device.unblock_if_expired()
                return "Active"
            return f"Blocked ({blocked_device.get_Block_Reason_display()})"
        except models.BlockedDevices.DoesNotExist:
            return "Active"

    def action_buttons(self, obj):
        """Show all action buttons for each client"""
        from django.utils.html import format_html
        from django.utils.safestring import mark_safe
        
        # Check if device is blocked
        try:
            blocked_device = models.BlockedDevices.objects.get(MAC_Address=obj.MAC_Address, Is_Active=True)
            if blocked_device.is_block_expired():
                blocked_device.unblock_if_expired()
                is_blocked = False
            else:
                is_blocked = True
        except models.BlockedDevices.DoesNotExist:
            is_blocked = False
        
        buttons = []
        
        # Connection status based buttons
        connection_status = obj.Connection_Status
        time_left_seconds = obj.Time_Left.total_seconds()
        
        if connection_status == 'Connected':
            # Disconnect button
            disconnect_url = f"/admin/app/clients/{obj.pk}/disconnect/"
            buttons.append(format_html(
                '<a class="button" href="{}" onclick="return confirm(\'Disconnect this device?\');" '
                'style="background-color: #fd7e14; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px; white-space: nowrap;" '
                'title="Disconnect Device">'
                '<i class="fas fa-unlink" style="margin-right: 3px;"></i>Disconnect</a>',
                disconnect_url
            ))
            
            # Pause button
            pause_url = f"/admin/app/clients/{obj.pk}/pause/"
            buttons.append(format_html(
                '<a class="button" href="{}" onclick="return confirm(\'Pause this device?\');" '
                'style="background-color: #ffc107; color: black; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px; white-space: nowrap;" '
                'title="Pause Device">'
                '<i class="fas fa-pause" style="margin-right: 3px;"></i>Pause</a>',
                pause_url
            ))
        elif connection_status == 'Paused':
            # Connect button (resume)
            connect_url = f"/admin/app/clients/{obj.pk}/connect/"
            buttons.append(format_html(
                '<a class="button" href="{}" onclick="return confirm(\'Resume this device?\');" '
                'style="background-color: #28a745; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px; white-space: nowrap;" '
                'title="Resume Device">'
                '<i class="fas fa-play" style="margin-right: 3px;"></i>Resume</a>',
                connect_url
            ))
        elif connection_status == 'Disconnected':
            # Connect button for disconnected clients
            connect_url = f"/admin/app/clients/{obj.pk}/connect/"
            if obj.Time_Left.total_seconds() > 0:
                # Has time left - green connect button
                buttons.append(format_html(
                    '<a class="button" href="{}" onclick="return confirm(\'Connect this device?\');" '
                    'style="background-color: #28a745; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px; white-space: nowrap;" '
                    'title="Connect Device">'
                    '<i class="fas fa-link" style="margin-right: 3px;"></i>Connect</a>',
                    connect_url
                ))
            else:
                # No time left - disabled style connect button
                buttons.append(format_html(
                    '<a class="button" href="{}" onclick="return confirm(\'This device has no time left. Connect anyway?\');" '
                    'style="background-color: #6c757d; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px; white-space: nowrap;" '
                    'title="Connect Device (No Time Left)">'
                    '<i class="fas fa-link" style="margin-right: 3px;"></i>Connect</a>',
                    connect_url
                ))
        
        # Edit button (always visible)
        edit_url = f"/admin/app/clients/{obj.pk}/change/"
        buttons.append(format_html(
            '<a class="button" href="{}" '
            'style="background-color: #6f42c1; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px; white-space: nowrap;" '
            'title="Edit Client">'
            '<i class="fas fa-edit" style="margin-right: 3px;"></i>Edit</a>',
            edit_url
        ))
        
        # Block/Unblock buttons
        if is_blocked:
            unblock_url = f"/admin/app/clients/{obj.pk}/unblock/"
            buttons.append(format_html(
                '<a class="button" href="{}" onclick="return confirm(\'Unblock this device?\');" '
                'style="background-color: #17a2b8; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px; white-space: nowrap;" '
                'title="Unblock Device">'
                '<i class="fas fa-check" style="margin-right: 3px;"></i>Unblock</a>',
                unblock_url
            ))
        else:
            block_url = f"/admin/app/clients/{obj.pk}/block/"
            buttons.append(format_html(
                '<a class="button" href="{}" onclick="return confirm(\'Block this device?\');" '
                'style="background-color: #dc3545; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px; white-space: nowrap;" '
                'title="Block Device">'
                '<i class="fas fa-ban" style="margin-right: 3px;"></i>Block</a>',
                block_url
            ))
        
        # Join all buttons and return as safe HTML
        all_buttons = ''.join(buttons)
        return format_html('<div style="white-space: nowrap; display: flex; gap: 2px;">{}</div>', mark_safe(all_buttons))
    
    action_buttons.short_description = 'Actions'
    action_buttons.allow_tags = True

    def get_urls(self):
        """Add custom URLs for all client actions"""
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('<int:client_id>/block/', self.admin_site.admin_view(self.block_client_view), name='app_clients_block'),
            path('<int:client_id>/unblock/', self.admin_site.admin_view(self.unblock_client_view), name='app_clients_unblock'),
            path('<int:client_id>/connect/', self.admin_site.admin_view(self.connect_client_view), name='app_clients_connect'),
            path('<int:client_id>/disconnect/', self.admin_site.admin_view(self.disconnect_client_view), name='app_clients_disconnect'),
            path('<int:client_id>/pause/', self.admin_site.admin_view(self.pause_client_view), name='app_clients_pause'),
        ]
        return custom_urls + urls

    def block_client_view(self, request, client_id):
        """Handle individual client blocking"""
        from django.shortcuts import get_object_or_404, redirect
        from django.contrib import messages
        
        client = get_object_or_404(models.Clients, pk=client_id)
        device_name = client.Device_Name if client.Device_Name else client.MAC_Address
        
        # Check if any blocked device record exists for this MAC (active or inactive)
        try:
            existing_block = models.BlockedDevices.objects.get(MAC_Address=client.MAC_Address)
            
            # If it's already active and not expired
            if existing_block.Is_Active and not existing_block.is_block_expired():
                messages.warning(request, f'Device {device_name} is already blocked.')
                return redirect('admin:app_clients_changelist')
            
            # If it's expired or inactive, reactivate it
            existing_block.Is_Active = True
            existing_block.Blocked_Date = timezone.now()
            existing_block.Auto_Unblock_After = timezone.now() + timezone.timedelta(hours=24)
            existing_block.Block_Reason = 'manual'
            if existing_block.Admin_Notes:
                existing_block.Admin_Notes += f' | Reactivated by {request.user.username} on {timezone.now().strftime("%Y-%m-%d %H:%M")}'
            else:
                existing_block.Admin_Notes = f'Reactivated by {request.user.username} on {timezone.now().strftime("%Y-%m-%d %H:%M")}'
            existing_block.save()
            
            messages.success(request, f'Device {device_name} has been blocked successfully.')
            
        except models.BlockedDevices.DoesNotExist:
            # Create new block record
            models.BlockedDevices.objects.create(
                MAC_Address=client.MAC_Address,
                Device_Name=device_name,
                Block_Reason='manual',
                Auto_Unblock_After=timezone.now() + timezone.timedelta(hours=24),  # 24 hour default
                Admin_Notes=f'Manually blocked from Clients admin by {request.user.username} on {timezone.now().strftime("%Y-%m-%d %H:%M")}'
            )
            messages.success(request, f'Device {device_name} has been blocked successfully.')
        
        # Disconnect the device if currently connected
        if client.Connection_Status == 'Connected':
            client.Disconnect()
        
        return redirect('admin:app_clients_changelist')

    def unblock_client_view(self, request, client_id):
        """Handle individual client unblocking"""
        from django.shortcuts import get_object_or_404, redirect
        from django.contrib import messages
        
        client = get_object_or_404(models.Clients, pk=client_id)
        device_name = client.Device_Name if client.Device_Name else client.MAC_Address
        
        try:
            blocked_device = models.BlockedDevices.objects.get(MAC_Address=client.MAC_Address, Is_Active=True)
            blocked_device.Is_Active = False
            blocked_device.Admin_Notes += f' | Manually unblocked by {request.user.username} on {timezone.now().strftime("%Y-%m-%d %H:%M")}'
            blocked_device.save()
            messages.success(request, f'Device {device_name} has been unblocked successfully.')
        except models.BlockedDevices.DoesNotExist:
            messages.info(request, f'Device {device_name} was not blocked.')
        
        return redirect('admin:app_clients_changelist')

    def connect_client_view(self, request, client_id):
        """Handle individual client connection"""
        from django.shortcuts import get_object_or_404, redirect
        from django.contrib import messages
        
        client = get_object_or_404(models.Clients, pk=client_id)
        device_name = client.Device_Name if client.Device_Name else client.MAC_Address
        
        if client.Time_Left.total_seconds() <= 0:
            messages.warning(request, f'Device {device_name} has no time left. Cannot connect.')
            return redirect('admin:app_clients_changelist')
        
        success = client.Connect()
        if success:
            messages.success(request, f'Device {device_name} has been connected successfully.')
        else:
            messages.warning(request, f'Failed to connect device {device_name}. Device may already be connected or have no time left.')
        
        return redirect('admin:app_clients_changelist')

    def disconnect_client_view(self, request, client_id):
        """Handle individual client disconnection"""
        from django.shortcuts import get_object_or_404, redirect
        from django.contrib import messages
        
        client = get_object_or_404(models.Clients, pk=client_id)
        device_name = client.Device_Name if client.Device_Name else client.MAC_Address
        
        success = client.Disconnect()
        if success:
            messages.success(request, f'Device {device_name} has been disconnected successfully.')
        else:
            messages.warning(request, f'Device {device_name} is not currently connected.')
        
        return redirect('admin:app_clients_changelist')

    def pause_client_view(self, request, client_id):
        """Handle individual client pause"""
        from django.shortcuts import get_object_or_404, redirect
        from django.contrib import messages
        
        client = get_object_or_404(models.Clients, pk=client_id)
        device_name = client.Device_Name if client.Device_Name else client.MAC_Address
        
        success = client.Pause()
        if success:
            messages.success(request, f'Device {device_name} has been paused successfully.')
        else:
            messages.warning(request, f'Device {device_name} is not currently connected or already paused.')
        
        return redirect('admin:app_clients_changelist')


class UnauthenticatedClientsAdmin(admin.ModelAdmin):
    """Admin for clients connected to AP but not authenticated"""
    list_display = ('IP_Address', 'MAC_Address', 'Device_Name', 'Date_Created', 'quick_actions')
    readonly_fields = ('IP_Address', 'MAC_Address', 'Expire_On', 'Notification_ID', 'Notified_Flag', 'Date_Created')
    actions = None
    
    def changelist_view(self, request, extra_context=None):
        extra_context = {'title': 'Unauthenticated Clients (Connected to Access Point)'}
        return super(UnauthenticatedClientsAdmin, self).changelist_view(request, extra_context=extra_context)
    
    def get_queryset(self, request):
        """Only show clients that are disconnected (not authenticated)"""
        qs = super().get_queryset(request)
        # Filter to only show disconnected clients (those connected to AP but not authenticated)
        return qs.filter(
            Q(Expire_On__isnull=True) | 
            Q(Expire_On__lt=timezone.now())
        ).exclude(
            MAC_Address__in=models.BlockedDevices.objects.filter(Is_Active=True).values_list('MAC_Address', flat=True)
        )
    
    def quick_actions(self, obj):
        """Show quick action buttons for unauthenticated clients"""
        from django.utils.html import format_html
        from django.utils.safestring import mark_safe
        
        buttons = []
        
        # Authenticate button (if has time)
        if obj.Time_Left.total_seconds() > 0:
            connect_url = f"/admin/app/clients/{obj.pk}/connect/"
            buttons.append(format_html(
                '<a class="button" href="{}" '
                'style="background-color: #28a745; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px;" '
                'title="Authenticate Client">'
                '<i class="fas fa-check-circle" style="margin-right: 3px;"></i>Authenticate</a>',
                connect_url
            ))
        
        # Edit button
        edit_url = f"/admin/app/clients/{obj.pk}/change/"
        buttons.append(format_html(
            '<a class="button" href="{}" '
            'style="background-color: #6f42c1; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px;" '
            'title="Edit Client">'
            '<i class="fas fa-edit" style="margin-right: 3px;"></i>Edit</a>',
            edit_url
        ))
        
        # Block button
        block_url = f"/admin/app/clients/{obj.pk}/block/"
        buttons.append(format_html(
            '<a class="button" href="{}" onclick="return confirm(\'Block this device?\');" '
            'style="background-color: #dc3545; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px;" '
            'title="Block Device">'
            '<i class="fas fa-ban" style="margin-right: 3px;"></i>Block</a>',
            block_url
        ))
        
        all_buttons = ''.join(buttons)
        return format_html('<div style="white-space: nowrap;">{}</div>', mark_safe(all_buttons))
    
    quick_actions.short_description = 'Quick Actions'
    quick_actions.allow_tags = True
    
    def has_add_permission(self, request):
        """Prevent manual addition of unauthenticated clients"""
        return False


class WhitelistAdmin(admin.ModelAdmin):
    list_display = ('MAC_Address', 'Device_Name')

    def changelist_view(self, request, extra_context=None):
        extra_context = {'title': 'Whitelisted Devices'}
        return super(WhitelistAdmin, self).changelist_view(request, extra_context=extra_context)


class CoinSlotAdmin(admin.ModelAdmin):
    list_display = ('Edit', 'Slot_ID', 'Client', 'Last_Updated', 'Slot_Status', 'Time_Remaining')
    readonly_fields = ('Slot_ID',)
    
    def Slot_Status(self, obj):
        """Show current slot status"""
        if not obj.Client:
            return "Available"
        
        # Check if slot has expired
        if obj.Last_Updated:
            from django.utils import timezone
            from datetime import timedelta
            settings = models.Settings.objects.get(pk=1)
            timeout = settings.Slot_Timeout
            time_diff = timezone.now() - obj.Last_Updated
            if time_diff.total_seconds() > timeout:
                return "Expired"
            else:
                return f"Active ({obj.Client})"
        else:
            return "Active (No timestamp)"
    
    def Time_Remaining(self, obj):
        """Show time remaining before slot expires"""
        if not obj.Client or not obj.Last_Updated:
            return "-"
        
        from django.utils import timezone
        from datetime import timedelta
        settings = models.Settings.objects.get(pk=1)
        timeout = settings.Slot_Timeout
        time_diff = timezone.now() - obj.Last_Updated
        remaining = timeout - time_diff.total_seconds()
        
        if remaining <= 0:
            return "Expired"
        else:
            return f"{int(remaining)}s"
    
    Time_Remaining.short_description = 'Time Left'
    Slot_Status.short_description = 'Status'

    def has_add_permission(self, *args, **kwargs):
        return not models.CoinSlot.objects.exists()

    def has_delete_permission(self, *args, **kwargs):
        return False


class LedgerAdmin(admin.ModelAdmin):
    list_display = ('Date', 'Client', 'Denomination', 'Slot_No')
    list_filter = ('Client', 'Date')

    def changelist_view(self, request, extra_context=None):
        extra_context = {'title': 'Transaction Ledger'}
        return super(LedgerAdmin, self).changelist_view(request, extra_context=extra_context)


class SalesReportAdmin(admin.ModelAdmin):
    """Comprehensive sales reporting admin"""
    list_display = ('Transaction_ID', 'Date_Display', 'Client_Display', 'Device_Name', 'Slot_No', 'Denomination_Display', 'Revenue')
    list_filter = ('Date', 'Slot_No', 'Client', 'Denomination')
    search_fields = ('Client', 'Slot_No')
    date_hierarchy = 'Date'
    ordering = ('-Date',)
    list_per_page = 50
    
    def Transaction_ID(self, obj):
        return f"#{obj.pk:06d}"
    Transaction_ID.short_description = 'Transaction ID'
    Transaction_ID.admin_order_field = 'pk'
    
    def Date_Display(self, obj):
        return obj.Date.strftime('%Y-%m-%d %H:%M:%S')
    Date_Display.short_description = 'Date & Time'
    Date_Display.admin_order_field = 'Date'
    
    def Client_Display(self, obj):
        """Show formatted MAC address"""
        if obj.Client and len(obj.Client) == 17:
            # Format MAC address for better readability
            return obj.Client.upper()
        return obj.Client or 'Unknown'
    Client_Display.short_description = 'Client MAC'
    Client_Display.admin_order_field = 'Client'
    
    def Device_Name(self, obj):
        """Show device name if client exists"""
        try:
            from . import models
            client = models.Clients.objects.get(MAC_Address=obj.Client)
            return client.Device_Name or 'Unknown Device'
        except models.Clients.DoesNotExist:
            return 'Device Not Found'
    Device_Name.short_description = 'Device Name'
    
    def Denomination_Display(self, obj):
        """Show denomination as currency"""
        return f"₱{obj.Denomination}.00"
    Denomination_Display.short_description = 'Coin Value'
    Denomination_Display.admin_order_field = 'Denomination'
    
    def Revenue(self, obj):
        """Show revenue (same as denomination for individual transactions)"""
        return f"₱{obj.Denomination}.00"
    Revenue.short_description = 'Revenue'
    Revenue.admin_order_field = 'Denomination'
    
    def changelist_view(self, request, extra_context=None):
        from django.db.models import Sum, Count, Avg
        from django.utils import timezone
        from datetime import timedelta, datetime
        import json
        
        # Get date range from request
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        
        # Default to showing last 30 days if no date specified
        if not date_from:
            date_from = (timezone.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        if not date_to:
            date_to = timezone.now().strftime('%Y-%m-%d')
        
        # Parse dates
        try:
            start_date = datetime.strptime(date_from, '%Y-%m-%d')
            end_date = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)  # Include entire end day
        except:
            start_date = timezone.now() - timedelta(days=30)
            end_date = timezone.now()
        
        # Make dates timezone aware
        start_date = timezone.make_aware(start_date) if timezone.is_naive(start_date) else start_date
        end_date = timezone.make_aware(end_date) if timezone.is_naive(end_date) else end_date
        
        # Get all transactions in date range
        qs = self.model.objects.filter(Date__gte=start_date, Date__lt=end_date)
        
        # Calculate statistics with null-safe aggregations
        summary = qs.aggregate(
            total_sales=Sum('Denomination'),
            transaction_count=Count('id'),
            average_transaction=Avg('Denomination')
        )
        # Ensure no None values
        summary['total_sales'] = summary['total_sales'] or 0
        summary['transaction_count'] = summary['transaction_count'] or 0
        summary['average_transaction'] = summary['average_transaction'] or 0
        
        # Today's sales
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_sales = self.model.objects.filter(Date__gte=today_start).aggregate(
            total=Sum('Denomination'),
            count=Count('id')
        )
        today_sales['total'] = today_sales['total'] or 0
        today_sales['count'] = today_sales['count'] or 0
        
        # This month's sales
        month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_sales = self.model.objects.filter(Date__gte=month_start).aggregate(
            total=Sum('Denomination'),
            count=Count('id')
        )
        month_sales['total'] = month_sales['total'] or 0
        month_sales['count'] = month_sales['count'] or 0
        
        # All time sales
        all_time_sales = self.model.objects.aggregate(
            total=Sum('Denomination'),
            count=Count('id')
        )
        all_time_sales['total'] = all_time_sales['total'] or 0
        all_time_sales['count'] = all_time_sales['count'] or 0
        
        # Daily sales for chart (last 7 days)
        daily_sales = []
        for i in range(7):
            date = timezone.now() - timedelta(days=i)
            day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            
            day_total = self.model.objects.filter(
                Date__gte=day_start,
                Date__lt=day_end
            ).aggregate(total=Sum('Denomination'))['total'] or 0
            
            daily_sales.append({
                'date': date.strftime('%Y-%m-%d'),
                'day': date.strftime('%a'),
                'total': day_total
            })
        
        daily_sales.reverse()  # Order from oldest to newest
        
        # Sales by slot
        slot_sales = qs.values('Slot_No').annotate(
            total=Sum('Denomination'),
            count=Count('id')
        ).order_by('-total')
        
        # Sales by denomination
        denomination_sales = qs.values('Denomination').annotate(
            count=Count('id'),
            total=Sum('Denomination')
        ).order_by('-Denomination')
        
        # Hourly distribution for selected period
        hourly_sales = []
        for hour in range(24):
            hour_total = qs.filter(Date__hour=hour).aggregate(
                total=Sum('Denomination'),
                count=Count('id')
            )
            hourly_sales.append({
                'hour': hour,
                'total': hour_total['total'] or 0,
                'count': hour_total['count'] or 0
            })
        
        extra_context = extra_context or {}
        extra_context.update({
            'title': 'Sales Reports & Analytics',
            'summary': summary,
            'today_sales': today_sales,
            'month_sales': month_sales,
            'all_time_sales': all_time_sales,
            'daily_sales': json.dumps(daily_sales),
            'slot_sales': list(slot_sales),
            'denomination_sales': list(denomination_sales),
            'hourly_sales': json.dumps(hourly_sales),
            'date_from': date_from,
            'date_to': date_to,
            'has_filters': True,
        })
        
        return super().changelist_view(request, extra_context=extra_context)
    
    def has_add_permission(self, request):
        return False  # Sales reports are read-only
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False  # Sales reports are read-only


class SettingsAdmin(Singleton, admin.ModelAdmin):
    form = forms.SettingsForm
    list_display = ('Hotspot_Name', 'Hotspot_Address', 'Slot_Timeout', 'Rate_Type', 'Base_Value', 'Inactive_Timeout', 'Coinslot_Pin', 'Light_Pin')
    
    def background_preview(self, obj):
        return obj.background_preview

    background_preview.short_description = 'Background Preview'
    background_preview.allow_tags = True

    def changelist_view(self, request, extra_context=None):
        extra_context = {'title': 'Wifi Settings'}
        return super(SettingsAdmin, self).changelist_view(request, extra_context=extra_context)

    def has_add_permission(self, *args, **kwargs):
        return not models.Settings.objects.exists()

    def has_delete_permission(self, *args, **kwargs):
        return False

    def has_change_permission(self, request, *args, **kwargs):
        res = client_check(request)
        return res

    def message_user(self, *args): # overridden method
        pass

    def save_model(self, request, obj, form, change):
        messages.add_message(request, messages.INFO, 'Wifi Settings updated successfully.')
        super(SettingsAdmin, self).save_model(request, obj, form, change)


class NetworkAdmin(Singleton, admin.ModelAdmin):
    form = forms.NetworkForm
    list_display = ('Edit', 'Upload_Rate', 'Download_Rate')
    # list_editable = ('Upload_Rate', 'Download_Rate')

    def changelist_view(self, request, extra_context=None):
        extra_context = {'title': 'Global Network Settings'}
        return super(NetworkAdmin, self).changelist_view(request, extra_context=extra_context)

    def has_add_permission(self, *args, **kwargs):
        return not models.Network.objects.exists()

    def has_delete_permission(self, *args, **kwargs):
        return False

    def has_change_permission(self, request, *args, **kwargs):
        res = client_check(request)
        return res

    def message_user(self, *args): # overridden method
        pass

    def save_model(self, request, obj, form, change):
        messages.add_message(request, messages.INFO, 'Global Network Settings updated successfully.')
        super(NetworkAdmin, self).save_model(request, obj, form, change)


class CoinQueueAdmin(admin.ModelAdmin):
    list_display = ('Edit', 'Client', 'Device_Name', 'Total_Coins', 'Credit_Value', 'Total_Time_Display', 'Time_Minutes')
    search_fields = ('Client',)
    readonly_fields = ('Total_Time_Display', 'Time_Minutes', 'Credit_Value', 'Device_Name')
    
    def Edit(self, obj):
        return 'Edit'
    Edit.short_description = 'Edit'
    
    def Device_Name(self, obj):
        """Show device name if client exists"""
        try:
            client = models.Clients.objects.get(MAC_Address=obj.Client)
            return client.Device_Name or 'Unknown Device'
        except models.Clients.DoesNotExist:
            return 'Device Not Found'
    Device_Name.short_description = 'Device Name'
    
    def Credit_Value(self, obj):
        """Show peso value of accumulated coins"""
        return f"₱{obj.Total_Coins or 0}.00"
    Credit_Value.short_description = 'Credit Value'
    
    def Total_Time_Display(self, obj):
        """Display total time in HH:MM:SS format"""
        total_time = obj.Total_Time
        if total_time:
            total_seconds = int(total_time.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return "00:00:00"
    Total_Time_Display.short_description = 'Total Time (HH:MM:SS)'
    
    def Time_Minutes(self, obj):
        """Show time in minutes for quick reference"""
        total_time = obj.Total_Time
        if total_time:
            minutes = int(total_time.total_seconds() / 60)
            return f"{minutes} min"
        return "0 min"
    Time_Minutes.short_description = 'Minutes'
    
    def changelist_view(self, request, extra_context=None):
        extra_context = {'title': 'Coin Queue - Client Credits'}
        return super(CoinQueueAdmin, self).changelist_view(request, extra_context=extra_context)


class RatesAdmin(admin.ModelAdmin):
    list_display = ('Edit', 'Denom', 'Pulse', 'Minutes')
    field_order = ('Minutes', 'Denom')

    def changelist_view(self, request, extra_context=None):
        extra_context = {'title': 'Wifi Custom Rates'}
        return super(RatesAdmin, self).changelist_view(request, extra_context=extra_context)

    def has_module_permission(self, *args, **kwargs):
        settings = models.Settings.objects.get(pk=1)
        if settings.Rate_Type == 'manual':
            return  True
        else:
            return  False

    def has_change_permission(self, request, *args, **kwargs):
        res = client_check(request)
        return res


class DeviceAdmin(Singleton, admin.ModelAdmin):
    list_display = ('Device_SN', 'Ethernet_MAC')

    def has_add_permission(self, *args, **kwargs):
        return not models.Device.objects.exists()

    def has_delete_permission(self, *args, **kwargs):
        return False

    def message_user(self, *args): # overridden method
        pass

    def save_model(self, request, obj, form, change):
        messages.add_message(request, messages.INFO, 'Hardware Settings updated successfully.')
        super(DeviceAdmin, self).save_model(request, obj, form, change)

class VouchersAdmin(admin.ModelAdmin):
    list_display = ('Voucher_code', 'Voucher_status', 'Voucher_client', 'Voucher_create_date_time', 'Voucher_used_date_time', 'Voucher_time_value')
    readonly_fields = ('Voucher_code', 'Voucher_used_date_time')

    def changelist_view(self, request, extra_context=None):
        extra_context = {'title': 'Wifi Vouchers'}
        return super(VouchersAdmin, self).changelist_view(request, extra_context=extra_context)

    def has_module_permission(self, *args, **kwargs):
        settings = models.Settings.objects.get(pk=1)
        if settings.Vouchers_Flg:
            return True
        else:
            return False

# PushNotificationsAdmin removed for personal use

# Model registrations moved to bottom after custom admin site creation

class SecuritySettingsAdmin(Singleton, admin.ModelAdmin):
    list_display = ('TTL_Detection_Enabled', 'Default_TTL_Value', 'TTL_Tolerance', 'Limit_Connections', 'Enable_TTL_Modification')
    fieldsets = (
        ('TTL Detection Settings', {
            'fields': ('TTL_Detection_Enabled', 'Default_TTL_Value', 'TTL_Tolerance')
        }),
        ('Connection Limiting Settings', {
            'fields': ('Limit_Connections', 'Normal_Device_Connections', 'Suspicious_Device_Connections', 'Max_TTL_Violations')
        }),
        ('TTL Modification Settings (MikroTik-style)', {
            'fields': ('Enable_TTL_Modification', 'TTL_Modification_After_Violations', 'Modified_TTL_Value', 'TTL_Rule_Duration'),
            'description': 'Apply iptables TTL mangle rules to completely prevent sharing (like MikroTik)'
        }),
        ('Device Blocking Settings (Legacy)', {
            'fields': ('Enable_Device_Blocking', 'Block_Duration'),
            'description': 'Complete device blocking as last resort (use TTL modification instead)'
        }),
    )

    def changelist_view(self, request, extra_context=None):
        extra_context = {'title': 'Security Settings'}
        return super(SecuritySettingsAdmin, self).changelist_view(request, extra_context=extra_context)

    def has_add_permission(self, *args, **kwargs):
        return not models.SecuritySettings.objects.exists()

    def has_delete_permission(self, *args, **kwargs):
        return False

    def has_change_permission(self, request, *args, **kwargs):
        res = client_check(request)
        return res

class TrafficMonitorAdmin(admin.ModelAdmin):
    list_display = ('Client_MAC', 'Timestamp', 'TTL_Value', 'Packet_Count', 'Is_Suspicious')
    list_filter = ('Is_Suspicious', 'Timestamp', 'TTL_Value')
    search_fields = ('Client_MAC',)
    readonly_fields = ('Client_MAC', 'Timestamp', 'TTL_Value', 'Packet_Count', 'Is_Suspicious')
    
    def changelist_view(self, request, extra_context=None):
        extra_context = {'title': 'Traffic Monitor - TTL Analysis'}
        return super(TrafficMonitorAdmin, self).changelist_view(request, extra_context=extra_context)

    def has_add_permission(self, *args, **kwargs):
        return False

class BlockedDevicesAdmin(admin.ModelAdmin):
    list_display = ('MAC_Address', 'Device_Name', 'Block_Reason', 'Blocked_Date', 'TTL_Violations_Count', 'Is_Active')
    list_filter = ('Block_Reason', 'Is_Active', 'Blocked_Date')
    search_fields = ('MAC_Address', 'Device_Name')
    readonly_fields = ('Blocked_Date', 'TTL_Violations_Count')
    actions = ['unblock_devices', 'block_devices']

    def changelist_view(self, request, extra_context=None):
        extra_context = {'title': 'Blocked Devices'}
        return super(BlockedDevicesAdmin, self).changelist_view(request, extra_context=extra_context)

    def unblock_devices(self, request, queryset):
        updated = queryset.update(Is_Active=False)
        messages.add_message(request, messages.SUCCESS, f'{updated} device(s) have been unblocked.')

    def block_devices(self, request, queryset):
        updated = queryset.update(Is_Active=True)
        messages.add_message(request, messages.SUCCESS, f'{updated} device(s) have been blocked.')

    unblock_devices.short_description = "Unblock selected devices"
    block_devices.short_description = "Block selected devices"

class ConnectionTrackerAdmin(admin.ModelAdmin):
    list_display = ('Device_MAC', 'Connection_IP', 'TTL_Classification', 'Connected_At', 'Last_Activity', 'Is_Active')
    list_filter = ('TTL_Classification', 'Is_Active', 'Connected_At')
    search_fields = ('Device_MAC', 'Connection_IP')
    readonly_fields = ('Device_MAC', 'Connection_IP', 'Session_ID', 'Connected_At', 'Last_Activity', 'TTL_Classification', 'User_Agent')
    actions = ['deactivate_connections', 'activate_connections', 'cleanup_expired']
    
    def changelist_view(self, request, extra_context=None):
        extra_context = {'title': 'Active Connection Tracker'}
        return super(ConnectionTrackerAdmin, self).changelist_view(request, extra_context=extra_context)

    def has_add_permission(self, *args, **kwargs):
        return False

    def deactivate_connections(self, request, queryset):
        updated = queryset.update(Is_Active=False)
        messages.add_message(request, messages.SUCCESS, f'{updated} connection(s) have been deactivated.')

    def activate_connections(self, request, queryset):
        updated = queryset.update(Is_Active=True)
        messages.add_message(request, messages.SUCCESS, f'{updated} connection(s) have been activated.')

    def cleanup_expired(self, request, queryset):
        # This will affect all expired connections, not just selected ones
        expired_count = models.ConnectionTracker.cleanup_expired_sessions()
        messages.add_message(request, messages.SUCCESS, f'{expired_count} expired connection(s) have been cleaned up.')

    deactivate_connections.short_description = "Deactivate selected connections"
    activate_connections.short_description = "Activate selected connections"
    cleanup_expired.short_description = "Cleanup all expired connections"

class TTLFirewallRuleAdmin(admin.ModelAdmin):
    list_display = ('Device_MAC', 'Rule_Type', 'TTL_Value', 'Rule_Status', 'Created_At', 'Expires_At', 'Violation_Count')
    list_filter = ('Rule_Type', 'Rule_Status', 'TTL_Value', 'Created_At')
    search_fields = ('Device_MAC',)
    readonly_fields = ('Device_MAC', 'Rule_Command', 'Created_At', 'Last_Checked', 'Violation_Count')
    actions = ['activate_rules', 'deactivate_rules', 'cleanup_expired_rules', 'remove_from_iptables']
    
    fieldsets = (
        ('Rule Information', {
            'fields': ('Device_MAC', 'Rule_Type', 'Rule_Status', 'TTL_Value')
        }),
        ('Timing', {
            'fields': ('Created_At', 'Expires_At', 'Last_Checked')
        }),
        ('Implementation Details', {
            'fields': ('Iptables_Chain', 'Rule_Command'),
            'classes': ('collapse',)
        }),
        ('Additional Info', {
            'fields': ('Violation_Count', 'Admin_Notes')
        }),
    )
    
    def changelist_view(self, request, extra_context=None):
        extra_context = {'title': 'TTL Firewall Rules (MikroTik-style)'}
        return super(TTLFirewallRuleAdmin, self).changelist_view(request, extra_context=extra_context)

    def has_add_permission(self, *args, **kwargs):
        return False  # Rules are created automatically

    def activate_rules(self, request, queryset):
        from app.views import apply_ttl_firewall_rule
        
        activated = 0
        for rule in queryset.filter(Rule_Status__in=['disabled', 'expired']):
            ttl_rule = apply_ttl_firewall_rule(rule.Device_MAC, rule.TTL_Value, 2)
            if ttl_rule:
                activated += 1
        
        messages.add_message(request, messages.SUCCESS, f'{activated} TTL rule(s) have been activated.')

    def deactivate_rules(self, request, queryset):
        from app.views import remove_ttl_firewall_rule
        
        deactivated = 0
        for rule in queryset.filter(Rule_Status='active'):
            if remove_ttl_firewall_rule(rule.Device_MAC):
                deactivated += 1
        
        messages.add_message(request, messages.SUCCESS, f'{deactivated} TTL rule(s) have been deactivated.')

    def cleanup_expired_rules(self, request, queryset):
        # This affects all expired rules, not just selected ones
        cleaned_count = models.TTLFirewallRule.cleanup_expired_rules()
        messages.add_message(request, messages.SUCCESS, f'{cleaned_count} expired TTL rule(s) have been cleaned up.')

    def remove_from_iptables(self, request, queryset):
        from app.views import remove_ttl_firewall_rule
        
        removed = 0
        for rule in queryset:
            if remove_ttl_firewall_rule(rule.Device_MAC):
                removed += 1
        
        messages.add_message(request, messages.SUCCESS, f'{removed} TTL rule(s) have been removed from iptables.')

    activate_rules.short_description = "Activate selected TTL rules"
    deactivate_rules.short_description = "Deactivate selected TTL rules"
    cleanup_expired_rules.short_description = "Cleanup all expired TTL rules"
    remove_from_iptables.short_description = "Force remove from iptables"

class DeviceFingerprintAdmin(admin.ModelAdmin):
    list_display = ('device_id_short', 'get_device_summary', 'Platform', 'MAC_Randomization_Detected', 'Total_TTL_Violations', 'Device_Status', 'Last_Seen')
    list_filter = ('Device_Status', 'MAC_Randomization_Detected', 'Platform', 'Last_Seen')
    search_fields = ('Device_ID', 'User_Agent', 'Current_MAC', 'Device_Name_Hint')
    readonly_fields = ('Device_ID', 'First_Seen', 'Last_Seen', 'Known_MACs', 'Total_TTL_Violations', 'Total_Connection_Violations', 'Last_Violation_Date')
    actions = ['mark_suspicious', 'mark_active', 'whitelist_devices', 'block_devices']
    
    fieldsets = (
        ('Device Identity', {
            'fields': ('Device_ID', 'Device_Name_Hint', 'Device_Status')
        }),
        ('Browser Fingerprinting', {
            'fields': ('User_Agent', 'Screen_Resolution', 'Browser_Language', 'Timezone_Offset', 'Platform'),
            'classes': ('collapse',)
        }),
        ('MAC Address Tracking', {
            'fields': ('Current_MAC', 'Known_MACs', 'MAC_Randomization_Detected')
        }),
        ('Network Behavior', {
            'fields': ('Default_TTL_Pattern', 'Connection_Behavior'),
            'classes': ('collapse',)
        }),
        ('Violation History', {
            'fields': ('Total_TTL_Violations', 'Total_Connection_Violations', 'Last_Violation_Date')
        }),
        ('Timestamps', {
            'fields': ('First_Seen', 'Last_Seen')
        }),
        ('Notes', {
            'fields': ('Admin_Notes',)
        }),
    )
    
    def device_id_short(self, obj):
        return f"{obj.Device_ID[:8]}..."
    device_id_short.short_description = "Fingerprint ID"
    
    def changelist_view(self, request, extra_context=None):
        extra_context = {'title': 'Device Fingerprints - MAC Randomization Tracking'}
        return super(DeviceFingerprintAdmin, self).changelist_view(request, extra_context=extra_context)

    def has_add_permission(self, *args, **kwargs):
        return False  # Fingerprints are created automatically

    def mark_suspicious(self, request, queryset):
        updated = queryset.update(Device_Status='suspicious')
        messages.add_message(request, messages.SUCCESS, f'{updated} device(s) marked as suspicious.')

    def mark_active(self, request, queryset):
        updated = queryset.update(Device_Status='active')
        messages.add_message(request, messages.SUCCESS, f'{updated} device(s) marked as active.')

    def whitelist_devices(self, request, queryset):
        updated = queryset.update(Device_Status='whitelist')
        messages.add_message(request, messages.SUCCESS, f'{updated} device(s) added to whitelist.')

    def block_devices(self, request, queryset):
        updated = queryset.update(Device_Status='blocked')
        messages.add_message(request, messages.SUCCESS, f'{updated} device(s) blocked.')

    mark_suspicious.short_description = "Mark selected devices as suspicious"
    mark_active.short_description = "Mark selected devices as active"
    whitelist_devices.short_description = "Whitelist selected devices"
    block_devices.short_description = "Block selected devices"

# Phase 3: Traffic Analysis & Intelligence Admin Classes

class TrafficAnalysisAdmin(admin.ModelAdmin):
    list_display = ('Device_MAC', 'device_summary', 'Protocol_Type', 'Bandwidth_Usage_MB', 'Is_Suspicious', 'Timestamp')
    list_filter = ('Protocol_Type', 'Is_Suspicious', 'Timestamp')
    search_fields = ('Device_MAC', 'Source_IP', 'Destination_IP')
    readonly_fields = ('Device_MAC', 'Device_Fingerprint', 'Timestamp', 'Bandwidth_Usage_MB', 'Is_Suspicious', 'Suspicion_Reason')
    
    fieldsets = (
        ('Device Information', {
            'fields': ('Device_MAC', 'Device_Fingerprint', 'Timestamp')
        }),
        ('Traffic Classification', {
            'fields': ('Protocol_Type', 'Bandwidth_Usage_MB', 'Bytes_Up', 'Bytes_Down', 'Packets_Up', 'Packets_Down')
        }),
        ('Connection Details', {
            'fields': ('Source_IP', 'Destination_IP', 'Source_Port', 'Destination_Port'),
            'classes': ('collapse',)
        }),
        ('Analysis Results', {
            'fields': ('Is_Suspicious', 'Suspicion_Reason')
        }),
    )
    
    def device_summary(self, obj):
        if obj.Device_Fingerprint:
            return obj.Device_Fingerprint.get_device_summary()
        return 'N/A'
    device_summary.short_description = 'Device'
    
    def changelist_view(self, request, extra_context=None):
        extra_context = {'title': 'Traffic Analysis - Protocol & Bandwidth Intelligence'}
        return super(TrafficAnalysisAdmin, self).changelist_view(request, extra_context=extra_context)

    def has_add_permission(self, *args, **kwargs):
        return False  # Traffic analysis is auto-generated

class DeviceBehaviorProfileAdmin(admin.ModelAdmin):
    list_display = ('device_summary', 'Trust_Level', 'Trust_Score', 'Total_Data_Used_MB', 'P2P_Usage_Percentage', 'Favorite_Protocol', 'Last_Updated')
    list_filter = ('Trust_Level', 'Favorite_Protocol', 'Last_Updated')
    search_fields = ('Device_Fingerprint__Device_ID', 'Device_Fingerprint__User_Agent')
    readonly_fields = ('Device_Fingerprint', 'First_Analysis', 'Last_Updated', 'Trust_Score')
    actions = ['update_trust_scores', 'mark_trusted', 'mark_suspicious', 'reset_profiles']
    
    fieldsets = (
        ('Device Information', {
            'fields': ('Device_Fingerprint', 'Trust_Level', 'Trust_Score')
        }),
        ('Usage Metrics', {
            'fields': ('Total_Data_Used_MB', 'Peak_Bandwidth_Usage', 'Average_Session_Duration', 'Average_Concurrent_Connections')
        }),
        ('Protocol Preferences', {
            'fields': ('Favorite_Protocol', 'P2P_Usage_Percentage', 'Streaming_Usage_Percentage')
        }),
        ('Behavioral Patterns', {
            'fields': ('Most_Active_Hour', 'Violation_Score', 'Last_Violation_Date'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('First_Analysis', 'Last_Updated')
        }),
    )
    
    def device_summary(self, obj):
        return obj.Device_Fingerprint.get_device_summary()
    device_summary.short_description = 'Device'
    
    def changelist_view(self, request, extra_context=None):
        extra_context = {'title': 'Device Behavior Profiles - Trust & Intelligence'}
        return super(DeviceBehaviorProfileAdmin, self).changelist_view(request, extra_context=extra_context)

    def has_add_permission(self, *args, **kwargs):
        return False  # Profiles are auto-generated
    
    def update_trust_scores(self, request, queryset):
        updated = 0
        for profile in queryset:
            profile.calculate_trust_score()
            profile.update_trust_level()
            updated += 1
        messages.add_message(request, messages.SUCCESS, f'{updated} trust score(s) updated.')
    
    def mark_trusted(self, request, queryset):
        updated = queryset.update(Trust_Level='trusted', Trust_Score=85.0)
        messages.add_message(request, messages.SUCCESS, f'{updated} device(s) marked as trusted.')
    
    def mark_suspicious(self, request, queryset):
        updated = queryset.update(Trust_Level='suspicious', Trust_Score=25.0)
        messages.add_message(request, messages.SUCCESS, f'{updated} device(s) marked as suspicious.')
    
    def reset_profiles(self, request, queryset):
        updated = queryset.update(
            Trust_Level='new',
            Trust_Score=50.0,
            Violation_Score=0.0,
            Total_Data_Used_MB=0.0,
            P2P_Usage_Percentage=0.0,
            Streaming_Usage_Percentage=0.0
        )
        messages.add_message(request, messages.SUCCESS, f'{updated} profile(s) reset to defaults.')
    
    update_trust_scores.short_description = "Recalculate trust scores"
    mark_trusted.short_description = "Mark selected devices as trusted"
    mark_suspicious.short_description = "Mark selected devices as suspicious"
    reset_profiles.short_description = "Reset selected profiles to defaults"

class AdaptiveQoSRuleAdmin(admin.ModelAdmin):
    list_display = ('Rule_Name', 'Device_MAC', 'device_summary', 'QoS_Action', 'bandwidth_limits', 'Is_Active', 'Created_At', 'Expires_At')
    list_filter = ('QoS_Action', 'Is_Active', 'Auto_Created', 'Created_At')
    search_fields = ('Device_MAC', 'Rule_Name', 'Device_Fingerprint__Device_ID')
    readonly_fields = ('Device_MAC', 'Device_Fingerprint', 'Created_At', 'Last_Applied', 'Times_Applied', 'Bytes_Limited')
    actions = ['activate_rules', 'deactivate_rules', 'extend_expiration', 'cleanup_expired']
    
    fieldsets = (
        ('Rule Information', {
            'fields': ('Rule_Name', 'Device_MAC', 'Device_Fingerprint', 'QoS_Action')
        }),
        ('Bandwidth Limits', {
            'fields': ('Bandwidth_Limit_Down', 'Bandwidth_Limit_Up', 'Protocol_Filter')
        }),
        ('Conditions & Status', {
            'fields': ('Trigger_Condition', 'Is_Active', 'Auto_Created')
        }),
        ('Timing', {
            'fields': ('Created_At', 'Expires_At', 'Last_Applied')
        }),
        ('Statistics', {
            'fields': ('Times_Applied', 'Bytes_Limited'),
            'classes': ('collapse',)
        }),
    )
    
    def device_summary(self, obj):
        if obj.Device_Fingerprint:
            return obj.Device_Fingerprint.get_device_summary()
        return 'N/A'
    device_summary.short_description = 'Device'
    
    def bandwidth_limits(self, obj):
        if obj.Bandwidth_Limit_Down or obj.Bandwidth_Limit_Up:
            down = f"{obj.Bandwidth_Limit_Down}↓" if obj.Bandwidth_Limit_Down else ""
            up = f"{obj.Bandwidth_Limit_Up}↑" if obj.Bandwidth_Limit_Up else ""
            return f"{down} {up} Mbps".strip()
        return "No limits"
    bandwidth_limits.short_description = 'Bandwidth Limits'
    
    def changelist_view(self, request, extra_context=None):
        extra_context = {'title': 'Adaptive QoS Rules - Intelligent Traffic Management'}
        return super(AdaptiveQoSRuleAdmin, self).changelist_view(request, extra_context=extra_context)
    
    def activate_rules(self, request, queryset):
        activated = 0
        for rule in queryset.filter(Is_Active=False):
            if rule.apply_rule():
                rule.Is_Active = True
                rule.save()
                activated += 1
        messages.add_message(request, messages.SUCCESS, f'{activated} QoS rule(s) activated.')
    
    def deactivate_rules(self, request, queryset):
        updated = queryset.update(Is_Active=False)
        messages.add_message(request, messages.SUCCESS, f'{updated} QoS rule(s) deactivated.')
    
    def extend_expiration(self, request, queryset):
        from django.utils import timezone
        new_expiration = timezone.now() + timezone.timedelta(hours=24)
        updated = queryset.update(Expires_At=new_expiration)
        messages.add_message(request, messages.SUCCESS, f'{updated} rule(s) extended by 24 hours.')
    
    def cleanup_expired(self, request, queryset):
        expired_count = queryset.filter(
            Expires_At__lt=timezone.now()
        ).update(Is_Active=False)
        messages.add_message(request, messages.SUCCESS, f'{expired_count} expired rule(s) cleaned up.')
    
    activate_rules.short_description = "Activate selected QoS rules"
    deactivate_rules.short_description = "Deactivate selected QoS rules"
    extend_expiration.short_description = "Extend expiration by 24 hours"
    cleanup_expired.short_description = "Cleanup expired rules"

class NetworkIntelligenceAdmin(admin.ModelAdmin):
    list_display = ('Timestamp', 'Total_Active_Devices', 'Suspicious_Devices_Count', 'Network_Utilization_Percent', 'top_protocol', 'Active_QoS_Rules')
    list_filter = ('Timestamp',)
    readonly_fields = ('Timestamp', 'Total_Active_Devices', 'Total_Bandwidth_Usage_Mbps', 'Network_Utilization_Percent', 
                      'Suspicious_Devices_Count', 'TTL_Violations_Last_Hour', 'MAC_Randomization_Detected_Count',
                      'Active_QoS_Rules', 'Revenue_Per_Hour', 'Average_Session_Duration_Minutes', 'Peak_Concurrent_Users',
                      'HTTP_Traffic_Percent', 'P2P_Traffic_Percent', 'Streaming_Traffic_Percent', 'Gaming_Traffic_Percent', 'Other_Traffic_Percent')
    actions = ['generate_current_intelligence']
    
    fieldsets = (
        ('Network Health', {
            'fields': ('Timestamp', 'Total_Active_Devices', 'Total_Bandwidth_Usage_Mbps', 'Network_Utilization_Percent')
        }),
        ('Security Metrics', {
            'fields': ('Suspicious_Devices_Count', 'TTL_Violations_Last_Hour', 'MAC_Randomization_Detected_Count', 'Active_QoS_Rules')
        }),
        ('Revenue & Usage', {
            'fields': ('Revenue_Per_Hour', 'Average_Session_Duration_Minutes', 'Peak_Concurrent_Users'),
            'classes': ('collapse',)
        }),
        ('Protocol Distribution', {
            'fields': ('HTTP_Traffic_Percent', 'P2P_Traffic_Percent', 'Streaming_Traffic_Percent', 'Gaming_Traffic_Percent', 'Other_Traffic_Percent'),
            'classes': ('collapse',)
        }),
    )
    
    def top_protocol(self, obj):
        protocols = {
            'HTTP': obj.HTTP_Traffic_Percent,
            'P2P': obj.P2P_Traffic_Percent,
            'Streaming': obj.Streaming_Traffic_Percent,
            'Gaming': obj.Gaming_Traffic_Percent,
            'Other': obj.Other_Traffic_Percent
        }
        if protocols:
            top = max(protocols, key=protocols.get)
            return f"{top} ({protocols[top]:.1f}%)"
        return "N/A"
    top_protocol.short_description = 'Top Protocol'
    
    def changelist_view(self, request, extra_context=None):
        extra_context = {'title': 'Network Intelligence - Real-time Analytics & Insights'}
        return super(NetworkIntelligenceAdmin, self).changelist_view(request, extra_context=extra_context)

    def has_add_permission(self, *args, **kwargs):
        return False  # Intelligence is auto-generated
    
    def generate_current_intelligence(self, request, queryset):
        from app.views import generate_network_intelligence
        intelligence = generate_network_intelligence()
        if intelligence:
            messages.add_message(request, messages.SUCCESS, 'Current network intelligence generated successfully.')
        else:
            messages.add_message(request, messages.ERROR, 'Failed to generate network intelligence.')
    
    generate_current_intelligence.short_description = "Generate current network intelligence"

# Security and network admin classes will be registered after custom admin site creation

# Custom admin site class to handle dynamic titles
class PisoWifiAdminSite(admin.AdminSite):
    def __init__(self, name='admin'):
        super().__init__(name)
        self.site_header = "OJO PISOWifi Admin"
        self.site_title = "OJO PISOWifi Admin"
        self.index_title = "Welcome to OJO PISOWifi Admin"
        # Use default Jazzmin template instead of custom index2.html
    
    def index(self, request, extra_context=None):
        # Safely get dynamic title only when admin is actually accessed
        try:
            if models.Settings.objects.exists():
                settings = models.Settings.objects.get(pk=1)
                self.site_header = settings.Hotspot_Name
                self.site_title = settings.Hotspot_Name
        except:
            pass
        
        # Get dashboard analytics data
        dashboard_data = self.get_dashboard_data()
        
        if extra_context is None:
            extra_context = {}
        extra_context.update(dashboard_data)
        
        return super().index(request, extra_context)
    
    def get_dashboard_data(self):
        """Get analytics data for the dashboard"""
        from django.db.models import Sum, Count, Q
        from django.utils import timezone
        from datetime import datetime, timedelta
        import json
        
        try:
            # Basic client statistics
            total_clients = models.Clients.objects.count()
            active_clients = models.Clients.objects.filter(
                Q(Expire_On__gt=timezone.now()) | Q(Time_Left__gt=timedelta(0))
            ).count()
            
            # Revenue statistics
            today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_revenue = models.Ledger.objects.filter(
                Date__gte=today
            ).aggregate(total=Sum('Denomination'))['total'] or 0
            
            # Revenue data for chart (last 7 days)
            revenue_data = []
            revenue_labels = []
            for i in range(6, -1, -1):
                date = today - timedelta(days=i)
                day_end = date + timedelta(days=1)
                day_revenue = models.Ledger.objects.filter(
                    Date__gte=date, Date__lt=day_end
                ).aggregate(total=Sum('Denomination'))['total'] or 0
                revenue_data.append(float(day_revenue))
                revenue_labels.append(date.strftime('%m/%d'))
            
            # Client status distribution
            connected_count = models.Clients.objects.filter(Expire_On__gt=timezone.now()).count()
            paused_count = models.Clients.objects.filter(
                Expire_On__isnull=True, Time_Left__gt=timedelta(0)
            ).count()
            disconnected_count = total_clients - connected_count - paused_count
            
            # Recent activities
            recent_activities = []
            recent_clients = models.Clients.objects.order_by('-Date_Created')[:5]
            for client in recent_clients:
                recent_activities.append({
                    'action': 'Client Connected' if client.Connection_Status == 'Connected' else 'Client Registered',
                    'device': client.Device_Name or client.MAC_Address,
                    'time': client.Date_Created,
                    'status': 'online' if client.Connection_Status == 'Connected' else 'warning'
                })
            
            # System health check
            system_health = {
                'database': 'online',
                'database_message': 'Database operational',
                'network': 'online',
                'network_message': 'Network services running',
                'security': 'online',
                'security_message': 'Security monitoring active'
            }
            
            # Check for security issues
            if models.BlockedDevices.objects.filter(Is_Active=True).exists():
                system_health['security'] = 'warning'
                system_health['security_message'] = 'Blocked devices detected'
            
            return {
                'total_clients': total_clients,
                'active_clients': active_clients,
                'today_revenue': today_revenue,
                'network_status': 'Operational',
                'revenue_data': json.dumps(revenue_data),
                'revenue_labels': json.dumps(revenue_labels),
                'client_status_data': json.dumps([connected_count, paused_count, disconnected_count]),
                'recent_activities': recent_activities,
                'system_health': system_health,
            }
            
        except Exception as e:
            # Fallback data if there's an error
            return {
                'total_clients': 0,
                'active_clients': 0,
                'today_revenue': 0,
                'network_status': 'Unknown',
                'revenue_data': json.dumps([0, 0, 0, 0, 0, 0, 0]),
                'revenue_labels': json.dumps(['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']),
                'client_status_data': json.dumps([0, 0, 0]),
                'recent_activities': [],
                'system_health': {
                    'database': 'offline',
                    'database_message': 'Database error',
                    'network': 'offline', 
                    'network_message': 'Network error',
                    'security': 'offline',
                    'security_message': 'Security error'
                },
            }

class SystemUpdateAdmin(admin.ModelAdmin):
    list_display = ('Version_Number', 'Update_Title', 'Status', 'progress_bar', 'Release_Date', 'action_buttons')
    list_filter = ('Status', 'Is_Auto_Update', 'Force_Update')
    readonly_fields = ('Progress', 'Downloaded_Bytes', 'Started_At', 'Completed_At', 'Error_Message', 'Backup_Path', 'Created_At', 'Updated_At')
    search_fields = ('Version_Number', 'Update_Title', 'Description')
    
    fieldsets = (
        ('Update Information', {
            'fields': ('Version_Number', 'Update_Title', 'Description', 'Release_Date', 'Download_URL', 'File_Size')
        }),
        ('Status & Progress', {
            'fields': ('Status', 'Progress', 'Downloaded_Bytes'),
            'classes': ('wide',)
        }),
        ('Options', {
            'fields': ('Is_Auto_Update', 'Force_Update', 'Backup_Path')
        }),
        ('Timestamps & Errors', {
            'fields': ('Started_At', 'Completed_At', 'Error_Message', 'Created_At', 'Updated_At'),
            'classes': ('collapse',)
        })
    )
    
    def progress_bar(self, obj):
        from django.utils.html import format_html
        progress = obj.get_progress_percentage()
        color = 'success' if progress == 100 else 'info'
        return format_html(
            '<div class="progress" style="width: 150px; height: 20px;">'
            '<div class="progress-bar bg-{}" role="progressbar" style="width: {}%;" '
            'aria-valuenow="{}" aria-valuemin="0" aria-valuemax="100">{}%</div>'
            '</div>',
            color, progress, progress, progress
        )
    progress_bar.short_description = 'Progress'
    
    def progress_bar_display(self, obj):
        return self.progress_bar(obj)
    progress_bar_display.short_description = 'Download Progress'
    
    def action_buttons(self, obj):
        from django.utils.html import format_html
        buttons = []
        
        if obj.Status == 'available':
            buttons.append(format_html(
                '<a class="btn btn-sm btn-primary" href="#" onclick="startDownload({}); return false;">Download</a>',
                obj.pk
            ))
        elif obj.Status == 'downloading':
            buttons.append(format_html(
                '<a class="btn btn-sm btn-warning" href="#" onclick="pauseDownload({}); return false;">Pause</a>',
                obj.pk
            ))
        elif obj.Status == 'ready':
            buttons.append(format_html(
                '<a class="btn btn-sm btn-success" href="#" onclick="installUpdate({}); return false;">Install</a>',
                obj.pk
            ))
        elif obj.Status == 'completed' and obj.can_rollback():
            buttons.append(format_html(
                '<a class="btn btn-sm btn-danger" href="#" onclick="rollbackUpdate({}); return false;">Rollback</a>',
                obj.pk
            ))
        
        return format_html(' '.join(str(button) for button in buttons))
    action_buttons.short_description = 'Actions'
    
    class Media:
        js = ('admin/js/system_update.js',)
        css = {
            'all': ('admin/css/system_update.css',)
        }
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context.update({
            'title': 'System Updates',
            'check_updates_button': True,
            'has_add_permission': False,  # Don't show Add button since updates come from GitHub
        })
        
        return super().changelist_view(request, extra_context=extra_context)
    
    def has_add_permission(self, request):
        """Disable manual adding of updates - they come from GitHub"""
        return False
    
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('check-updates/', self.admin_site.admin_view(self.check_updates_view), name='app_systemupdate_check'),
            path('<int:pk>/download/', self.admin_site.admin_view(self.download_update_view), name='app_systemupdate_download'),
            path('<int:pk>/install/', self.admin_site.admin_view(self.install_update_view), name='app_systemupdate_install'),
            path('<int:pk>/rollback/', self.admin_site.admin_view(self.rollback_update_view), name='app_systemupdate_rollback'),
            path('<int:pk>/progress/', self.admin_site.admin_view(self.progress_view), name='app_systemupdate_progress'),
            path('<int:pk>/install-progress/', self.admin_site.admin_view(self.install_progress_view), name='app_systemupdate_install_progress'),
        ]
        return custom_urls + urls
    
    def check_updates_view(self, request):
        from django.http import JsonResponse
        from app.services.update_service import GitHubUpdateService
        
        try:
            service = GitHubUpdateService()
            result = service.check_for_updates()
            
            if result['status'] == 'success' and result['updates_available']:
                # Create update objects
                service.create_system_updates(result['updates'])
            
            return JsonResponse(result)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    
    def download_update_view(self, request, pk):
        from django.http import JsonResponse
        from app.services.update_service import UpdateDownloadService
        import threading
        
        try:
            update = models.SystemUpdate.objects.get(pk=pk)
            
            # Start download in background thread
            def download_in_background():
                service = UpdateDownloadService(update)
                service.download_update()
            
            thread = threading.Thread(target=download_in_background)
            thread.daemon = True
            thread.start()
            
            return JsonResponse({'status': 'success', 'message': 'Download started'})
        except models.SystemUpdate.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Update not found'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    
    def install_update_view(self, request, pk):
        from django.http import JsonResponse
        from app.services.update_service import UpdateInstallService
        import threading
        
        try:
            update = models.SystemUpdate.objects.get(pk=pk)
            
            if update.Status != 'ready':
                return JsonResponse({'status': 'error', 'message': 'Update not ready for installation'})
            
            # Start installation in background thread
            def install_in_background():
                service = UpdateInstallService(update)
                service.install_update()
            
            thread = threading.Thread(target=install_in_background)
            thread.daemon = True
            thread.start()
            
            return JsonResponse({'status': 'success', 'message': 'Installation started'})
        except models.SystemUpdate.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Update not found'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    
    def rollback_update_view(self, request, pk):
        from django.http import JsonResponse
        from app.services.update_service import UpdateInstallService
        
        try:
            update = models.SystemUpdate.objects.get(pk=pk)
            service = UpdateInstallService(update)
            result = service.rollback_update()
            
            return JsonResponse(result)
        except models.SystemUpdate.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Update not found'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    
    def progress_view(self, request, pk):
        from django.http import JsonResponse
        
        try:
            update = models.SystemUpdate.objects.get(pk=pk)
            return JsonResponse({
                'status': update.Status,
                'progress': update.get_progress_percentage(),
                'downloaded_bytes': update.Downloaded_Bytes,
                'file_size': update.File_Size,
                'error': update.Error_Message
            })
        except models.SystemUpdate.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Update not found'})
    
    def install_progress_view(self, request, pk):
        from django.http import JsonResponse
        
        try:
            update = models.SystemUpdate.objects.get(pk=pk)
            return JsonResponse({
                'status': update.Status,
                'progress': update.Progress,
                'error': update.Error_Message
            })
        except models.SystemUpdate.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Update not found'})


class UpdateSettingsAdmin(Singleton):
    fieldsets = (
        ('Repository Settings', {
            'fields': ('GitHub_Repository', 'Update_Channel', 'Current_Version')
        }),
        ('Auto Update Configuration', {
            'fields': ('Check_Interval_Hours', 'Auto_Download', 'Auto_Install', 'Last_Check')
        }),
        ('Backup Settings', {
            'fields': ('Backup_Before_Update', 'Max_Backup_Count')
        })
    )
    
    readonly_fields = ('Last_Check', 'Current_Version')
    
    def changelist_view(self, request, extra_context=None):
        return HttpResponseRedirect(reverse('admin:app_updatesettings_change', args=[1]))


# Replace the default admin site
admin.site = PisoWifiAdminSite()
admin.sites.site = admin.site

# Re-register all models with the new admin site
admin.site.register(models.CoinSlot, CoinSlotAdmin)
admin.site.register(models.Clients, ClientsAdmin)
# UnauthenticatedClients now shown within ClientsAdmin view
# admin.site.register(models.UnauthenticatedClients, UnauthenticatedClientsAdmin)
admin.site.register(models.Whitelist, WhitelistAdmin)
admin.site.register(models.Ledger, LedgerAdmin)
admin.site.register(models.SalesReport, SalesReportAdmin)
admin.site.register(models.CoinQueue, CoinQueueAdmin)
admin.site.register(models.Settings, SettingsAdmin)
admin.site.register(models.Network, NetworkAdmin)
admin.site.register(models.Rates, RatesAdmin)
admin.site.register(models.Device, DeviceAdmin)
admin.site.register(models.Vouchers, VouchersAdmin)
admin.site.register(models.SecuritySettings, SecuritySettingsAdmin)
admin.site.register(models.TrafficMonitor, TrafficMonitorAdmin)
admin.site.register(models.BlockedDevices, BlockedDevicesAdmin)
admin.site.register(models.ConnectionTracker, ConnectionTrackerAdmin)
admin.site.register(models.TTLFirewallRule, TTLFirewallRuleAdmin)
admin.site.register(models.DeviceFingerprint, DeviceFingerprintAdmin)
admin.site.register(models.TrafficAnalysis, TrafficAnalysisAdmin)
admin.site.register(models.DeviceBehaviorProfile, DeviceBehaviorProfileAdmin)
admin.site.register(models.AdaptiveQoSRule, AdaptiveQoSRuleAdmin)
admin.site.register(models.NetworkIntelligence, NetworkIntelligenceAdmin)
admin.site.register(models.SystemUpdate, SystemUpdateAdmin)
admin.site.register(models.UpdateSettings, UpdateSettingsAdmin)

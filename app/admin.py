from django.core.exceptions import ObjectDoesNotExist
from django.contrib import admin, messages
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
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
    list_display = ('IP_Address', 'MAC_Address', 'Device_Name', 'auth_status', 'Connection_Status', 'block_status', 'actual_time_left', 'action_buttons')
    readonly_fields = ('IP_Address', 'MAC_Address', 'Expire_On', 'Validity_Expires_On', 'Date_Created', 'Connection_Status', 'running_time')
    exclude = ('Notification_ID', 'Notified_Flag')  # Hide notification fields
    actions = None  # Disable bulk actions since we have individual buttons
    list_filter = (('Expire_On', admin.EmptyFieldListFilter),)  # Add filter for authenticated/unauthenticated
    
    fieldsets = (
        ('Client Information', {
            'fields': ('IP_Address', 'MAC_Address', 'Device_Name')
        }),
        ('Connection Status', {
            'fields': ('Connection_Status', 'running_time', 'Time_Left', 'Expire_On', 'Validity_Expires_On'),
            'description': 'Time Left is used for paused sessions. Running Time shows current session time remaining. Validity Expiration shows when purchased time expires.'
        }),
        ('Bandwidth Settings', {
            'fields': ('Upload_Rate', 'Download_Rate'),
            'description': 'Specify bandwidth limits in Kbps. Leave empty for unlimited.'
        }),
        ('System Information', {
            'fields': ('Date_Created',),
            'classes': ('collapse',)
        }),
    )
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Add better labels and help text
        if 'Time_Left' in form.base_fields:
            form.base_fields['Time_Left'].label = 'Time Left (Paused Sessions)'
            form.base_fields['Time_Left'].help_text = 'Duration stored when session is paused. For connected clients, see Running Time above.'
        if 'Device_Name' in form.base_fields:
            form.base_fields['Device_Name'].help_text = 'Optional device name or description'
        return form

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

    @admin.display(description='Time Remaining')
    def actual_time_left(self, obj):
        """Show actual time remaining based on connection status"""
        from django.utils.html import format_html
        from datetime import timedelta
        
        if obj.Connection_Status == 'Connected':
            # For connected clients, show running_time
            time_left = obj.running_time
        elif obj.Connection_Status == 'Paused':
            # For paused clients, show Time_Left
            time_left = obj.Time_Left
        else:
            # For disconnected clients, show 0
            time_left = timedelta(0)
        
        # Format the time display
        if time_left.total_seconds() <= 0:
            return format_html('<span style="color: gray;">0:00:00</span>')
        
        total_seconds = int(time_left.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        # Color code based on time remaining
        if total_seconds < 300:  # Less than 5 minutes
            color = 'red'
        elif total_seconds < 1800:  # Less than 30 minutes
            color = 'orange'
        else:
            color = 'green'
        
        time_str = f"{hours}:{minutes:02d}:{seconds:02d}"
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, time_str
        )
    
    @admin.display(description='Running Time')
    def running_time(self, obj):
        """Display running time in edit form"""
        from django.utils.html import format_html
        from datetime import timedelta
        
        time_left = obj.running_time
        
        if time_left.total_seconds() <= 0:
            return format_html('<span style="color: gray;">0:00:00</span>')
        
        total_seconds = int(time_left.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        time_str = f"{hours}:{minutes:02d}:{seconds:02d}"
        return format_html('<span style="font-weight: bold;">{}</span>', time_str)
    
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
            # Connect button (resume if connected to WiFi)
            connect_url = f"/admin/app/clients/{obj.pk}/connect/"
            buttons.append(format_html(
                '<a class="button" href="{}" onclick="return confirm(\'Resume this device?\');" '
                'style="background-color: #28a745; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px; white-space: nowrap;" '
                'title="Resume Device (WiFi Required)">'
                '<i class="fas fa-play" style="margin-right: 3px;"></i>Resume</a>',
                connect_url
            ))
            
            # Force Resume button (countdown regardless of WiFi)
            resume_url = f"/admin/app/clients/{obj.pk}/resume/"
            buttons.append(format_html(
                '<a class="button" href="{}" onclick="return confirm(\'Force time countdown? Time will run out even if not connected to WiFi.\');" '
                'style="background-color: #dc3545; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px; white-space: nowrap;" '
                'title="Force Time Countdown (No WiFi Required)">'
                '<i class="fas fa-hourglass-start" style="margin-right: 3px;"></i>Force Resume</a>',
                resume_url
            ))
            
            # Disconnect button for paused clients too
            disconnect_url = f"/admin/app/clients/{obj.pk}/disconnect/"
            buttons.append(format_html(
                '<a class="button" href="{}" onclick="return confirm(\'Disconnect this device?\');" '
                'style="background-color: #fd7e14; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px; white-space: nowrap;" '
                'title="Disconnect Device">'
                '<i class="fas fa-unlink" style="margin-right: 3px;"></i>Disconnect</a>',
                disconnect_url
            ))
        elif connection_status == 'Disconnected':
            # Connect button for disconnected clients
            connect_url = f"/admin/app/clients/{obj.pk}/connect/"
            if obj.Time_Left.total_seconds() > 0:
                # Has time left - green connect button
                buttons.append(format_html(
                    '<a class="button" href="{}" onclick="return confirm(\'Connect this device?\');" '
                    'style="background-color: #28a745; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px; white-space: nowrap;" '
                    'title="Connect Device (WiFi Required)">'
                    '<i class="fas fa-link" style="margin-right: 3px;"></i>Connect</a>',
                    connect_url
                ))
                
                # Force Resume button for disconnected clients with time
                resume_url = f"/admin/app/clients/{obj.pk}/resume/"
                buttons.append(format_html(
                    '<a class="button" href="{}" onclick="return confirm(\'Force time countdown? Time will run out even if not connected to WiFi.\');" '
                    'style="background-color: #dc3545; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px; white-space: nowrap;" '
                    'title="Force Time Countdown (No WiFi Required)">'
                    '<i class="fas fa-hourglass-start" style="margin-right: 3px;"></i>Force Resume</a>',
                    resume_url
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
        # Kick button - available for all clients
        kick_url = f"/admin/app/clients/{obj.pk}/kick/"
        if connection_status in ['Connected', 'Paused']:
            # Kick active clients (disconnect but preserve time)
            buttons.append(format_html(
                '<a class="button" href="{}" onclick="return confirm(\'Kick this device from WiFi? (Time will be preserved)\');" '
                'style="background-color: #e83e8c; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px; white-space: nowrap;" '
                'title="Kick from WiFi (Time Preserved)">'
                '<i class="fas fa-user-times" style="margin-right: 3px;"></i>Kick</a>',
                kick_url
            ))
        else:
            # Remove disconnected clients from list
            remove_url = f"{kick_url}?remove=true"
            buttons.append(format_html(
                '<a class="button" href="{}" onclick="return confirm(\'Remove this device from list?\');" '
                'style="background-color: #6f42c1; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px; white-space: nowrap;" '
                'title="Remove from List">'
                '<i class="fas fa-trash-alt" style="margin-right: 3px;"></i>Remove</a>',
                remove_url
            ))
        
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
            # Check if permanent block is enabled in settings
            try:
                settings = models.Settings.objects.get(pk=1)
                permanent_enabled = settings.Enable_Permanent_Block
            except:
                permanent_enabled = False
            
            # Regular block button
            block_url = f"/admin/app/clients/{obj.pk}/block/"
            buttons.append(format_html(
                '<a class="button" href="{}" onclick="return confirm(\'Block this device temporarily?\');" '
                'style="background-color: #dc3545; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px; white-space: nowrap;" '
                'title="Block Device (Temporary)">'
                '<i class="fas fa-ban" style="margin-right: 3px;"></i>Block</a>',
                block_url
            ))
            
            # Permanent block button (if enabled)
            if permanent_enabled:
                permanent_block_url = f"/admin/app/clients/{obj.pk}/block/?permanent=true"
                buttons.append(format_html(
                    '<a class="button" href="{}" onclick="return confirm(\'Block this device PERMANENTLY? This cannot be automatically undone.\');" '
                    'style="background-color: #6f42c1; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px; white-space: nowrap;" '
                    'title="Block Device (Permanent)">'
                    '<i class="fas fa-lock" style="margin-right: 3px;"></i>Permanent</a>',
                    permanent_block_url
                ))
        
        # Join all buttons and return as safe HTML
        all_buttons = ''.join(buttons)
        return format_html('<div style="white-space: nowrap; display: flex; gap: 2px;">{}</div>', mark_safe(all_buttons))
    
    action_buttons.short_description = 'Actions'
    action_buttons.allow_tags = True
    
    @admin.display(description='Actions')
    def action_buttons_display(self, obj):
        """Alternative display method for newer Django versions"""
        return self.action_buttons(obj)

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
            path('<int:client_id>/resume/', self.admin_site.admin_view(self.resume_client_view), name='app_clients_resume'),
            path('<int:client_id>/kick/', self.admin_site.admin_view(self.kick_client_view), name='app_clients_kick'),
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
            settings = models.Settings.objects.get(pk=1)
            
            # Check if permanent block should be applied (GET parameter or setting)
            permanent_block = request.GET.get('permanent', 'false').lower() == 'true'
            
            existing_block.Is_Active = True
            existing_block.Blocked_Date = timezone.now()
            existing_block.Is_Permanent = permanent_block
            
            if permanent_block:
                existing_block.Auto_Unblock_After = None  # No auto-unblock for permanent
            else:
                block_duration = settings.Default_Block_Duration
                existing_block.Auto_Unblock_After = timezone.now() + block_duration
            
            existing_block.Block_Reason = 'manual'
            if existing_block.Admin_Notes:
                existing_block.Admin_Notes += f' | Reactivated by {request.user.username} on {timezone.now().strftime("%Y-%m-%d %H:%M")}'
            else:
                existing_block.Admin_Notes = f'Reactivated by {request.user.username} on {timezone.now().strftime("%Y-%m-%d %H:%M")}'
            existing_block.save()
            
            messages.success(request, f'Device {device_name} has been blocked successfully.')
            
        except models.BlockedDevices.DoesNotExist:
            # Create new block record using settings
            settings = models.Settings.objects.get(pk=1)
            
            # Check if permanent block should be applied
            permanent_block = request.GET.get('permanent', 'false').lower() == 'true'
            
            auto_unblock_after = None if permanent_block else timezone.now() + settings.Default_Block_Duration
            
            models.BlockedDevices.objects.create(
                MAC_Address=client.MAC_Address,
                Device_Name=device_name,
                Block_Reason='manual',
                Auto_Unblock_After=auto_unblock_after,
                Is_Permanent=permanent_block,
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

    def kick_client_view(self, request, client_id):
        """Handle individual client kick (disconnect from WiFi + remove from database)"""
        from django.shortcuts import get_object_or_404, redirect
        from django.contrib import messages
        
        client = get_object_or_404(models.Clients, pk=client_id)
        device_name = client.Device_Name if client.Device_Name else client.MAC_Address
        connection_status = client.Connection_Status
        
        # Check if we should just remove from database without WiFi kick
        remove_only = request.GET.get('remove', 'false').lower() == 'true'
        
        if remove_only:
            # Remove client from database only (for already disconnected clients)
            client.delete()
            messages.success(request, f'Device {device_name} has been removed from the clients list.')
        else:
            # Full kick: disconnect from WiFi but preserve client data and time
            success = client.Kick()  # This now includes WiFi deauth
            if success:
                # Don't delete from database - just ensure they're disconnected
                # The client record stays so they keep their time when reconnecting
                if connection_status in ['Connected', 'Paused']:
                    messages.success(request, f'Device {device_name} has been kicked from WiFi successfully. Time preserved.')
                else:
                    messages.success(request, f'Device {device_name} has been disconnected. Time preserved.')
            else:
                messages.warning(request, f'Failed to kick device {device_name}.')
        
        return redirect('admin:app_clients_changelist')

    def resume_client_view(self, request, client_id):
        """Handle individual client resume (force time countdown regardless of WiFi connection)"""
        from django.shortcuts import get_object_or_404, redirect
        from django.contrib import messages
        from django.utils import timezone
        
        client = get_object_or_404(models.Clients, pk=client_id)
        device_name = client.Device_Name if client.Device_Name else client.MAC_Address
        
        # Check if client has time left to resume
        if client.Time_Left.total_seconds() <= 0:
            messages.warning(request, f'Device {device_name} has no time left to resume.')
            return redirect('admin:app_clients_changelist')
        
        # Force start time countdown by setting Expire_On, regardless of WiFi connection
        client.Expire_On = timezone.now() + client.Time_Left
        client.Time_Left = client.Time_Left  # Keep the original Time_Left as backup
        client.save()
        
        # Calculate time remaining for display
        time_remaining = client.Time_Left
        hours = int(time_remaining.total_seconds() // 3600)
        minutes = int((time_remaining.total_seconds() % 3600) // 60)
        
        messages.success(request, f'Device {device_name} time resumed - {hours}h {minutes}m will now count down. Time will expire even if not connected to WiFi.')
        
        return redirect('admin:app_clients_changelist')

    def changelist_view(self, request, extra_context=None):
        """Add silent live refresh functionality to clients list"""
        extra_context = extra_context or {}
        extra_context.update({
            'title': 'Clients Management - Live View',
            'live_refresh_script': '''
<script>
document.addEventListener('DOMContentLoaded', function() {
    if (!window.location.pathname.includes('/admin/app/clients/')) return;
    
    let refreshTimer;
    
    function refreshNow() {
        const scrollY = window.scrollY;
        
        fetch(window.location.href, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        })
        .then(response => response.text())
        .then(html => {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const newTable = doc.querySelector('#result_list');
            const currentTable = document.querySelector('#result_list');
            
            if (newTable && currentTable) {
                currentTable.innerHTML = newTable.innerHTML;
            }
            
            window.scrollTo(0, scrollY);
        })
        .catch(error => {
            console.error('Refresh failed:', error);
        });
    }
    
    function startAutoRefresh() {
        if (refreshTimer) clearInterval(refreshTimer);
        refreshTimer = setInterval(() => {
            if (document.visibilityState === 'visible') {
                refreshNow();
            }
        }, 1000);
    }
    
    startAutoRefresh();
    
    document.addEventListener('visibilitychange', function() {
        if (document.visibilityState === 'hidden') {
            clearInterval(refreshTimer);
        } else {
            startAutoRefresh();
        }
    });
});
</script>
            '''
        })
        return super().changelist_view(request, extra_context)

    class Media:
        js = ('admin/js/live_refresh.js',)
        css = {
            'all': ('admin/css/live_refresh.css',)
        }


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
            portal_settings = models.PortalSettings.objects.first()
            timeout = portal_settings.slot_timeout if portal_settings else 300
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
        portal_settings = models.PortalSettings.objects.first()
        timeout = portal_settings.slot_timeout if portal_settings else 300
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
    list_display = ('rate_display', 'inactive_timeout_display', 'security_display', 'hardware_display')
    
    def rate_display(self, obj):
        """Display rate configuration"""
        from django.utils.html import format_html
        rate_type = obj.Rate_Type.upper() if obj.Rate_Type else 'MANUAL'
        base_value = f" ({obj.Base_Value})" if obj.Rate_Type == 'auto' and obj.Base_Value else ""
        return format_html(
            '<div><strong style="color: #1976d2;">{}</strong>{}</div>',
            rate_type, base_value
        )
    rate_display.short_description = 'Rate System'
    
    def inactive_timeout_display(self, obj):
        """Display inactive timeout"""
        from django.utils.html import format_html
        return format_html(
            '<span style="background: #fff3e0; color: #f57c00; padding: 2px 6px; border-radius: 3px; font-weight: bold;">{} min</span>',
            obj.Inactive_Timeout
        )
    inactive_timeout_display.short_description = 'Session Timeout'
    
    def security_display(self, obj):
        """Display security settings"""
        from django.utils.html import format_html
        block_duration = f"{obj.Default_Block_Duration}".replace(':', 'h ').replace(':00', 'm')
        permanent = "✓" if obj.Enable_Permanent_Block else "✗"
        return format_html(
            '<div><strong>Block:</strong> {}<br><strong>Permanent:</strong> {}</div>',
            block_duration, permanent
        )
    security_display.short_description = 'Security Settings'
    
    def hardware_display(self, obj):
        """Display hardware configuration"""
        from django.utils.html import format_html
        return format_html(
            '<div><strong>Coin Pin:</strong> GPIO {}<br><strong>Light Pin:</strong> GPIO {}</div>',
            obj.Coinslot_Pin, obj.Light_Pin
        )
    hardware_display.short_description = 'Hardware Pins'

    def changelist_view(self, request, extra_context=None):
        extra_context = {
            'title': 'WiFi Settings - Network & Hardware Configuration',
            'subtitle': 'Configure WiFi rates, timeouts, security, and hardware settings'
        }
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
        messages.add_message(request, messages.INFO, 'WiFi Settings updated successfully.')
        super(SettingsAdmin, self).save_model(request, obj, form, change)


class NetworkAdmin(Singleton, admin.ModelAdmin):
    form = forms.NetworkForm
    list_display = ('Edit', 'WAN_IP', 'Upload_Rate', 'Download_Rate', 'Client_Upload_Rate', 'Client_Download_Rate')
    readonly_fields = ('wan_ip_display', 'WAN_Last_Updated')
    # list_editable = ('Upload_Rate', 'Download_Rate')
    
    fieldsets = (
        ('Network Configuration', {
            'fields': ('Server_IP', 'Netmask', 'DNS_1', 'DNS_2')
        }),
        ('WAN Information', {
            'fields': ('wan_ip_display', 'WAN_Last_Updated'),
            'description': 'IP address assigned by router to this system (automatically detected)'
        }),
        ('Global Bandwidth Limits', {
            'fields': ('Upload_Rate', 'Download_Rate'),
            'description': 'Overall bandwidth limits for the entire network'
        }),
        ('Default Client Bandwidth Limits', {
            'fields': ('Client_Upload_Rate', 'Client_Download_Rate'),
            'description': 'Default bandwidth limits applied to each individual client when they connect'
        }),
    )

    def refresh_wan_ip(self, request, queryset):
        """Refresh WAN IP for selected network settings"""
        for network in queryset:
            wan_ip = network.detect_wan_ip()
            if wan_ip:
                messages.success(request, f'WAN IP updated to: {wan_ip}')
            else:
                messages.warning(request, 'Failed to detect WAN IP. Please check internet connection.')
    
    refresh_wan_ip.short_description = "Refresh WAN IP Address"
    actions = ['refresh_wan_ip']

    def changelist_view(self, request, extra_context=None):
        extra_context = {'title': 'Global Network Settings'}
        return super(NetworkAdmin, self).changelist_view(request, extra_context=extra_context)
    
    def save_model(self, request, obj, form, change):
        # Auto-detect WAN IP when saving network settings
        if not obj.WAN_IP or not obj.WAN_Last_Updated:
            wan_ip = obj.detect_wan_ip()
            if wan_ip:
                messages.info(request, f'WAN IP automatically detected: {wan_ip}')
        
        messages.add_message(request, messages.INFO, 'Global Network Settings updated successfully.')
        super(NetworkAdmin, self).save_model(request, obj, form, change)

    def has_add_permission(self, *args, **kwargs):
        return not models.Network.objects.exists()

    def has_delete_permission(self, *args, **kwargs):
        return False

    def has_change_permission(self, request, *args, **kwargs):
        res = client_check(request)
        return res

    def message_user(self, *args): # overridden method
        pass


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
    list_display = ('Edit', 'Denom', 'Pulse', 'Minutes', 'validity_display')
    field_order = ('Minutes', 'Denom')
    
    fieldsets = (
        ('Rate Configuration', {
            'fields': ('Denom', 'Pulse', 'Minutes')
        }),
        ('Validity/Expiration Settings', {
            'fields': ('Validity_Days', 'Validity_Hours'),
            'description': 'Set how long purchased time remains valid. Leave both as 0 for no expiration.'
        }),
        ('Coin System Status', {
            'fields': ('coin_slots_status', 'coin_queue_status'),
            'classes': ('collapse',),
            'description': 'Current status of coin slots and queue. Use the buttons above to manage coin slots and queue.'
        }),
    )
    
    readonly_fields = ('coin_slots_status', 'coin_queue_status')
    
    def coin_slots_status(self, obj):
        """Display current coin slots status"""
        from django.utils.html import format_html
        try:
            coin_slots = models.CoinSlot.objects.all()
            total_slots = coin_slots.count()
            occupied_slots = coin_slots.filter(Client__isnull=False).count()
            available_slots = total_slots - occupied_slots
            
            return format_html(
                '<div style="background: #f8f9fa; padding: 10px; border-radius: 5px;">'
                '<strong>Coin Slots Overview:</strong><br>'
                'Total Slots: <span style="color: #007bff; font-weight: bold;">{}</span><br>'
                'Available: <span style="color: #28a745; font-weight: bold;">{}</span><br>'
                'Occupied: <span style="color: #dc3545; font-weight: bold;">{}</span><br>'
                '<a href="/admin/app/coinslot/" style="color: #007bff; text-decoration: none;">→ Manage Coin Slots</a>'
                '</div>',
                total_slots, available_slots, occupied_slots
            )
        except Exception as e:
            return format_html('<span style="color: #dc3545;">Error loading coin slots status</span>')
    coin_slots_status.short_description = 'Coin Slots Status'
    
    def coin_queue_status(self, obj):
        """Display current coin queue status"""
        from django.utils.html import format_html
        try:
            coin_queue = models.CoinQueue.objects.all()
            total_queued = coin_queue.count()
            total_coins = sum(queue.Total_Coins or 0 for queue in coin_queue)
            
            return format_html(
                '<div style="background: #f8f9fa; padding: 10px; border-radius: 5px;">'
                '<strong>Coin Queue Overview:</strong><br>'
                'Queued Clients: <span style="color: #007bff; font-weight: bold;">{}</span><br>'
                'Total Coins: <span style="color: #ffc107; font-weight: bold;">{}</span><br>'
                '<a href="/admin/app/coinqueue/" style="color: #007bff; text-decoration: none;">→ Manage Coin Queue</a>'
                '</div>',
                total_queued, total_coins
            )
        except Exception as e:
            return format_html('<span style="color: #dc3545;">Error loading coin queue status</span>')
    coin_queue_status.short_description = 'Coin Queue Status'

    @admin.display(description='Validity Period')
    def validity_display(self, obj):
        """Display validity period in list view"""
        from django.utils.html import format_html
        validity_text = obj.get_validity_display()
        
        if validity_text == "No expiration":
            return format_html('<span style="color: green;">No expiration</span>')
        else:
            return format_html('<span style="color: orange; font-weight: bold;">{}</span>', validity_text)

    def changelist_view(self, request, extra_context=None):
        extra_context = {'title': 'WiFi Custom Rates & Validity Settings'}
        return super(RatesAdmin, self).changelist_view(request, extra_context=extra_context)

    def has_module_permission(self, *args, **kwargs):
        try:
            settings = models.Settings.objects.get(pk=1)
            return settings.Rate_Type == 'manual'
        except models.Settings.DoesNotExist:
            return False

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
    """
    Enhanced Vouchers Admin with Batch Generation Features:
    
    Features:
    - Batch voucher generation with custom parameters (time, validity, export options)
    - Quick batch actions for common voucher configurations
    - CSV export functionality for selected vouchers
    - Individual voucher management (expire, view, edit)
    - Live statistics and status badges
    
    Batch Generation Options:
    - Custom Batch: Full control over count, time, validity, code length, export format
    - Quick Batches: Pre-configured common voucher types
    - Export Formats: Screen display, CSV download, TXT download
    
    Access: /admin/app/vouchers/ -> "Batch Generate Vouchers" button
    """
    list_display = ('Voucher_code', 'voucher_status_badge', 'Voucher_client', 'voucher_time_display', 'validity_display', 'Voucher_create_date_time', 'Voucher_used_date_time', 'days_until_expiry', 'action_buttons')
    list_filter = ('Voucher_status', 'Voucher_create_date_time', 'Voucher_used_date_time')
    search_fields = ('Voucher_code', 'Voucher_client')
    readonly_fields = ('Voucher_used_date_time', 'Voucher_create_date_time')
    list_per_page = 25
    ordering = ('-Voucher_create_date_time',)
    actions = ['generate_bulk_vouchers', 'generate_quick_batch_5_30min', 'generate_quick_batch_20_2hours', 'export_selected_vouchers', 'mark_as_expired', 'delete_expired_vouchers']
    
    fieldsets = (
        ('Voucher Information', {
            'fields': ('Voucher_code', 'Voucher_status', 'Voucher_time_value')
        }),
        ('Validity/Expiration Settings', {
            'fields': ('Validity_Days', 'Validity_Hours'),
            'description': 'Set how long the voucher time remains valid after redemption. Leave both as 0 for no expiration.'
        }),
        ('Client Information', {
            'fields': ('Voucher_client',)
        }),
        ('Timestamps', {
            'fields': ('Voucher_create_date_time', 'Voucher_used_date_time'),
            'classes': ('collapse',)
        }),
    )
    
    def get_fields(self, request, obj=None):
        """Make Voucher_code editable only when creating new voucher"""
        if obj:  # Editing existing voucher
            self.readonly_fields = ('Voucher_code', 'Voucher_used_date_time', 'Voucher_create_date_time')
        else:  # Creating new voucher
            self.readonly_fields = ('Voucher_used_date_time', 'Voucher_create_date_time')
        return super().get_fields(request, obj)
    
    def get_form(self, request, obj=None, **kwargs):
        """Override form to show placeholder for new vouchers"""
        form = super().get_form(request, obj, **kwargs)
        if not obj:  # Creating new voucher
            form.base_fields['Voucher_code'].initial = ''
            form.base_fields['Voucher_code'].help_text = 'Leave blank to auto-generate a unique code'
            form.base_fields['Voucher_code'].widget.attrs['placeholder'] = 'Auto-generated if left blank'
        return form
    
    def save_model(self, request, obj, form, change):
        """Handle voucher code generation for new vouchers"""
        if not change and not obj.Voucher_code:  # New voucher without code
            # Generate code once and save it
            obj.Voucher_code = models.Vouchers.generate_code()
        
        # Show the actual code that will be saved
        if not change:
            messages.success(request, f'Voucher created with code: {obj.Voucher_code}')
        
        super().save_model(request, obj, form, change)
    
    @admin.display(description='Status')
    def voucher_status_badge(self, obj):
        from django.utils.html import format_html
        color_map = {
            'Not Used': '#28a745',
            'Used': '#6c757d',
            'Expired': '#dc3545'
        }
        color = color_map.get(obj.Voucher_status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 12px; font-weight: bold;">{}</span>',
            color, obj.Voucher_status
        )
    
    @admin.display(description='Time Value')
    def voucher_time_display(self, obj):
        total_seconds = int(obj.Voucher_time_value.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours}h {minutes}m"
    
    @admin.display(description='Validity Period')
    def validity_display(self, obj):
        """Display validity period in list view"""
        from django.utils.html import format_html
        validity_text = obj.get_validity_display()
        
        if validity_text == "No expiration":
            return format_html('<span style="color: green;">No expiration</span>')
        else:
            return format_html('<span style="color: orange; font-weight: bold;">{}</span>', validity_text)
    
    @admin.display(description='Days Until Expiry')
    def days_until_expiry(self, obj):
        from django.utils import timezone
        from datetime import timedelta
        
        if obj.Voucher_status == 'Used' or obj.Voucher_status == 'Expired':
            return '-'
        
        expiry_date = obj.Voucher_create_date_time + timedelta(days=30)
        days_left = (expiry_date - timezone.now()).days
        
        if days_left < 0:
            return 'Expired'
        elif days_left <= 3:
            return format_html('<span style="color: red; font-weight: bold;">{} days</span>', days_left)
        elif days_left <= 7:
            return format_html('<span style="color: orange; font-weight: bold;">{} days</span>', days_left)
        else:
            return f"{days_left} days"
    
    def action_buttons(self, obj):
        from django.utils.html import format_html
        buttons = []
        
        if obj.Voucher_status == 'Not Used':
            buttons.append(format_html(
                '<a class="button" href="/admin/app/vouchers/{}/expire/" '
                'onclick="return confirm(\'Mark this voucher as expired?\');" '
                'style="background-color: #dc3545; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px;">'
                '<i class="fas fa-times" style="margin-right: 3px;"></i>Expire</a>',
                obj.pk
            ))
        
        buttons.append(format_html(
            '<a class="button" href="/admin/app/vouchers/{}/change/" '
            'style="background-color: #007bff; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px;">'
            '<i class="fas fa-eye" style="margin-right: 3px;"></i>View</a>',
            obj.pk
        ))
        
        return format_html(' '.join(buttons))
    
    action_buttons.short_description = 'Actions'
    
    
    def generate_bulk_vouchers(self, request, queryset):
        """Keep simple bulk action for backward compatibility"""
        from django.shortcuts import redirect
        from django.contrib import messages
        from datetime import timedelta
        
        count = 10
        time_value = timedelta(hours=1)
        validity_days = 7
        
        created_vouchers = []
        for i in range(count):
            voucher_code = models.Vouchers.generate_code()
            voucher = models.Vouchers.objects.create(
                Voucher_code=voucher_code,
                Voucher_status='Not Used',
                Voucher_time_value=time_value,
                Validity_Days=validity_days,
                Validity_Hours=0
            )
            created_vouchers.append(voucher_code)
        
        messages.success(request, f'Successfully created {count} vouchers: {", ".join(created_vouchers[:5])}{"..." if len(created_vouchers) > 5 else ""}')
        return redirect(request.get_full_path())
    
    generate_bulk_vouchers.short_description = "Quick: Generate 10 vouchers (1h, 7d validity)"
    
    def export_selected_vouchers(self, request, queryset):
        """Export selected vouchers to CSV"""
        from django.http import HttpResponse
        import csv
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="selected_vouchers.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Voucher Code', 'Status', 'Time Value', 'Validity Period', 'Client', 'Created Date', 'Used Date'])
        
        for voucher in queryset:
            time_display = f"{int(voucher.Voucher_time_value.total_seconds())//3600}h {(int(voucher.Voucher_time_value.total_seconds())%3600)//60}m"
            validity_display = voucher.get_validity_display()
            
            writer.writerow([
                voucher.Voucher_code,
                voucher.Voucher_status,
                time_display,
                validity_display,
                voucher.Voucher_client or '',
                voucher.Voucher_create_date_time.strftime('%Y-%m-%d %H:%M:%S'),
                voucher.Voucher_used_date_time.strftime('%Y-%m-%d %H:%M:%S') if voucher.Voucher_used_date_time else ''
            ])
        
        return response
    
    export_selected_vouchers.short_description = "Export selected vouchers to CSV"
    
    def generate_quick_batch_5_30min(self, request, queryset):
        """Quick generate 5 vouchers with 30 minutes each"""
        from django.shortcuts import redirect
        from django.contrib import messages
        from datetime import timedelta
        
        count = 5
        time_value = timedelta(minutes=30)
        validity_days = 3
        
        created_codes = []
        for i in range(count):
            voucher_code = models.Vouchers.generate_code()
            models.Vouchers.objects.create(
                Voucher_code=voucher_code,
                Voucher_status='Not Used',
                Voucher_time_value=time_value,
                Validity_Days=validity_days,
                Validity_Hours=0
            )
            created_codes.append(voucher_code)
        
        messages.success(request, f'Generated {count} vouchers (30min, 3d validity): {", ".join(created_codes)}')
        return redirect(request.get_full_path())
    
    generate_quick_batch_5_30min.short_description = "Quick: 5 vouchers × 30min (3d validity)"
    
    def generate_quick_batch_20_2hours(self, request, queryset):
        """Quick generate 20 vouchers with 2 hours each"""
        from django.shortcuts import redirect
        from django.contrib import messages
        from datetime import timedelta
        
        count = 20
        time_value = timedelta(hours=2)
        validity_days = 14
        
        created_codes = []
        for i in range(count):
            voucher_code = models.Vouchers.generate_code()
            models.Vouchers.objects.create(
                Voucher_code=voucher_code,
                Voucher_status='Not Used',
                Voucher_time_value=time_value,
                Validity_Days=validity_days,
                Validity_Hours=0
            )
            created_codes.append(voucher_code)
        
        messages.success(request, f'Generated {count} vouchers (2h, 14d validity): {", ".join(created_codes[:5])}{"..." if len(created_codes) > 5 else ""}')
        return redirect(request.get_full_path())
    
    generate_quick_batch_20_2hours.short_description = "Quick: 20 vouchers × 2h (14d validity)"
    
    def mark_as_expired(self, request, queryset):
        from django.contrib import messages
        updated = queryset.filter(Voucher_status='Not Used').update(Voucher_status='Expired')
        messages.success(request, f'Successfully marked {updated} vouchers as expired.')
    
    mark_as_expired.short_description = "Mark selected vouchers as expired"
    
    def delete_expired_vouchers(self, request, queryset):
        from django.contrib import messages
        expired_vouchers = queryset.filter(Voucher_status='Expired')
        count = expired_vouchers.count()
        expired_vouchers.delete()
        messages.success(request, f'Successfully deleted {count} expired vouchers.')
    
    delete_expired_vouchers.short_description = "Delete expired vouchers"

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('<int:voucher_id>/expire/', self.admin_site.admin_view(self.expire_voucher_view), name='vouchers_expire'),
            path('generate-batch/', self.admin_site.admin_view(self.generate_batch_view), name='app_vouchers_generate_batch'),
        ]
        return custom_urls + urls
    
    def generate_batch_view(self, request):
        """Generate multiple vouchers using the new add_form.html template"""
        from django import forms
        from django.shortcuts import render, redirect
        from django.contrib import messages
        from django.urls import reverse
        from datetime import timedelta
        
        class BatchVoucherForm(forms.Form):
            count = forms.IntegerField(
                label='Number of Vouchers',
                initial=10,
                min_value=1,
                max_value=1000,
                help_text='How many vouchers to generate (1-1000)',
                widget=forms.NumberInput(attrs={'class': 'form-control'})
            )
            code_length = forms.IntegerField(
                label='Code Length',
                initial=6,
                min_value=4,
                max_value=20,
                help_text='Length of voucher codes (4-20 characters)',
                widget=forms.NumberInput(attrs={'class': 'form-control'})
            )
            hours = forms.IntegerField(
                label='Hours',
                initial=1,
                min_value=0,
                max_value=168,
                help_text='Hours of internet time (0-168)',
                widget=forms.NumberInput(attrs={'class': 'form-control'})
            )
            minutes = forms.IntegerField(
                label='Minutes',
                initial=0,
                min_value=0,
                max_value=59,
                help_text='Additional minutes (0-59)',
                widget=forms.NumberInput(attrs={'class': 'form-control'})
            )
            validity_days = forms.IntegerField(
                label='Validity Days',
                initial=7,
                min_value=0,
                max_value=365,
                help_text='Days until unused time expires (0-365)',
                widget=forms.NumberInput(attrs={'class': 'form-control'})
            )
            validity_hours = forms.IntegerField(
                label='Validity Hours',
                initial=0,
                min_value=0,
                max_value=23,
                help_text='Additional hours (0-23)',
                widget=forms.NumberInput(attrs={'class': 'form-control'})
            )
        
        if request.method == 'POST':
            form = BatchVoucherForm(request.POST)
            if form.is_valid():
                # Get form data
                count = form.cleaned_data['count']
                code_length = form.cleaned_data['code_length']
                hours = form.cleaned_data['hours']
                minutes = form.cleaned_data['minutes']
                validity_days = form.cleaned_data['validity_days']
                validity_hours = form.cleaned_data['validity_hours']
                
                # Validate time values
                total_minutes = hours * 60 + minutes
                if total_minutes == 0:
                    messages.error(request, 'Time value must be greater than 0. Please set at least some hours or minutes.')
                else:
                    # Create vouchers
                    voucher_time = timedelta(hours=hours, minutes=minutes)
                    created_vouchers = []
                    
                    for i in range(count):
                        voucher = models.Vouchers.objects.create(
                            Voucher_code=models.Vouchers.generate_code(size=code_length),
                            Voucher_time_value=voucher_time,
                            Validity_Days=validity_days,
                            Validity_Hours=validity_hours,
                            Voucher_status='Not Used'
                        )
                        created_vouchers.append(voucher.Voucher_code)
                    
                    messages.success(
                        request, 
                        f'Successfully generated {count} vouchers with {hours}h {minutes}m time value. '
                        f'Codes: {", ".join(created_vouchers[:5])}'
                        + (f' and {count-5} more...' if count > 5 else '')
                    )
                    
                    return redirect(reverse('admin:app_vouchers_changelist'))
        else:
            form = BatchVoucherForm()
        
        # Custom fieldsets for better organization
        custom_fieldsets = [
            {
                'name': 'Voucher Configuration',
                'fields': ['count', 'code_length'],
                'description': 'Basic voucher generation settings'
            },
            {
                'name': 'Time Value',
                'fields': ['hours', 'minutes'],
                'description': 'Internet time allocation per voucher'
            },
            {
                'name': 'Validity Period', 
                'fields': ['validity_days', 'validity_hours'],
                'description': 'How long the voucher time remains usable after redemption (0 for no expiration)'
            }
        ]
        
        # Get the admin site context which includes available_apps for sidebar
        admin_context = self.admin_site.each_context(request)
        
        context = {
            'form': form,
            'title': 'Generate Multiple Vouchers',
            'opts': self.model._meta,
            'form_url': '',
            'submit_label': 'Generate Vouchers',
            'cancel_url': reverse('admin:app_vouchers_changelist'),
            'custom_fieldsets': custom_fieldsets,
            'has_file_field': False,
            'show_save_and_add_another': False,
            **admin_context,  # Include all admin context including available_apps
        }
        
        return render(request, 'admin/add_form.html', context)

    def expire_voucher_view(self, request, voucher_id):
        from django.shortcuts import get_object_or_404, redirect
        from django.contrib import messages
        from django.utils import timezone
        
        voucher = get_object_or_404(models.Vouchers, pk=voucher_id)
        
        if voucher.Voucher_status == 'Not Used':
            voucher.Voucher_status = 'Expired'
            voucher.save()
            messages.success(request, f'Voucher {voucher.Voucher_code} has been marked as expired.')
        else:
            messages.warning(request, f'Voucher {voucher.Voucher_code} cannot be expired (current status: {voucher.Voucher_status}).')
        
        return redirect('admin:app_vouchers_changelist')

    def changelist_view(self, request, extra_context=None):
        from django.db.models import Count, Q
        from django.utils.html import format_html
        
        if extra_context is None:
            extra_context = {}
        
        stats = models.Vouchers.objects.aggregate(
            total=Count('id'),
            not_used=Count('id', filter=Q(Voucher_status='Not Used')),
            used=Count('id', filter=Q(Voucher_status='Used')),
            expired=Count('id', filter=Q(Voucher_status='Expired'))
        )
        
        extra_context = extra_context or {}
        extra_context.update({
            'title': 'WiFi Vouchers Management',
            'voucher_stats': stats,
            'subtitle': f"Total: {stats['total']} | Available: {stats['not_used']} | Used: {stats['used']} | Expired: {stats['expired']}"
        })
        return super(VouchersAdmin, self).changelist_view(request, extra_context=extra_context)

    def has_module_permission(self, *args, **kwargs):
        try:
            settings = models.Settings.objects.get(pk=1)
            return settings.Vouchers_Flg
        except models.Settings.DoesNotExist:
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
        ('Security Monitoring Status', {
            'fields': ('traffic_monitor_status', 'connection_tracker_status', 'ttl_firewall_status', 'traffic_analysis_status', 'device_behavior_status', 'network_intelligence_status'),
            'classes': ('collapse',),
            'description': 'Current status of security monitoring systems. Use the buttons above to manage each security feature.'
        }),
    )
    
    readonly_fields = ('traffic_monitor_status', 'connection_tracker_status', 'ttl_firewall_status', 'traffic_analysis_status', 'device_behavior_status', 'network_intelligence_status')

    def traffic_monitor_status(self, obj):
        """Display traffic monitor status"""
        from django.utils.html import format_html
        try:
            traffic_logs = models.TrafficMonitor.objects.all()
            total_logs = traffic_logs.count()
            recent_logs = traffic_logs.filter(Timestamp__gte=timezone.now() - timezone.timedelta(hours=24)).count()
            
            return format_html(
                '<div style="background: #f8f9fa; padding: 10px; border-radius: 5px;">'
                '<strong>Traffic Monitor:</strong><br>'
                'Total Logs: <span style="color: #007bff; font-weight: bold;">{}</span><br>'
                'Last 24h: <span style="color: #28a745; font-weight: bold;">{}</span><br>'
                '<a href="/admin/app/trafficmonitor/" style="color: #007bff; text-decoration: none;">→ View Traffic Logs</a>'
                '</div>',
                total_logs, recent_logs
            )
        except Exception as e:
            return format_html('<span style="color: #dc3545;">Error loading traffic monitor status</span>')
    traffic_monitor_status.short_description = 'Traffic Monitor'
    
    def connection_tracker_status(self, obj):
        """Display connection tracker status"""
        from django.utils.html import format_html
        try:
            connections = models.ConnectionTracker.objects.all()
            total_connections = connections.count()
            active_connections = connections.filter(Is_Active=True).count()
            
            return format_html(
                '<div style="background: #f8f9fa; padding: 10px; border-radius: 5px;">'
                '<strong>Connection Tracker:</strong><br>'
                'Total Connections: <span style="color: #007bff; font-weight: bold;">{}</span><br>'
                'Active: <span style="color: #28a745; font-weight: bold;">{}</span><br>'
                '<a href="/admin/app/connectiontracker/" style="color: #007bff; text-decoration: none;">→ View Connections</a>'
                '</div>',
                total_connections, active_connections
            )
        except Exception as e:
            return format_html('<span style="color: #dc3545;">Error loading connection tracker status</span>')
    connection_tracker_status.short_description = 'Connection Tracker'
    
    def ttl_firewall_status(self, obj):
        """Display TTL firewall rules status"""
        from django.utils.html import format_html
        try:
            rules = models.TTLFirewallRule.objects.all()
            total_rules = rules.count()
            active_rules = rules.filter(Rule_Status='active').count()
            
            return format_html(
                '<div style="background: #f8f9fa; padding: 10px; border-radius: 5px;">'
                '<strong>TTL Firewall Rules:</strong><br>'
                'Total Rules: <span style="color: #007bff; font-weight: bold;">{}</span><br>'
                'Active: <span style="color: #28a745; font-weight: bold;">{}</span><br>'
                '<a href="/admin/app/ttlfirewallrule/" style="color: #007bff; text-decoration: none;">→ Manage Rules</a>'
                '</div>',
                total_rules, active_rules
            )
        except Exception as e:
            return format_html('<span style="color: #dc3545;">Error loading TTL firewall status</span>')
    ttl_firewall_status.short_description = 'TTL Firewall Rules'
    
    def traffic_analysis_status(self, obj):
        """Display traffic analysis status"""
        from django.utils.html import format_html
        try:
            analyses = models.TrafficAnalysis.objects.all()
            total_analyses = analyses.count()
            recent_analyses = analyses.filter(Timestamp__gte=timezone.now() - timezone.timedelta(hours=24)).count()
            
            return format_html(
                '<div style="background: #f8f9fa; padding: 10px; border-radius: 5px;">'
                '<strong>Traffic Analysis:</strong><br>'
                'Total Reports: <span style="color: #007bff; font-weight: bold;">{}</span><br>'
                'Last 24h: <span style="color: #28a745; font-weight: bold;">{}</span><br>'
                '<a href="/admin/app/trafficanalysis/" style="color: #007bff; text-decoration: none;">→ View Analysis</a>'
                '</div>',
                total_analyses, recent_analyses
            )
        except Exception as e:
            return format_html('<span style="color: #dc3545;">Error loading traffic analysis status</span>')
    traffic_analysis_status.short_description = 'Traffic Analysis'
    
    def device_behavior_status(self, obj):
        """Display device behavior profiles status"""
        from django.utils.html import format_html
        try:
            profiles = models.DeviceBehaviorProfile.objects.all()
            total_profiles = profiles.count()
            flagged_profiles = profiles.filter(Trust_Level__in=['suspicious', 'abusive', 'banned']).count()
            
            return format_html(
                '<div style="background: #f8f9fa; padding: 10px; border-radius: 5px;">'
                '<strong>Device Behavior Profiles:</strong><br>'
                'Total Profiles: <span style="color: #007bff; font-weight: bold;">{}</span><br>'
                'Flagged: <span style="color: #dc3545; font-weight: bold;">{}</span><br>'
                '<a href="/admin/app/devicebehaviorprofile/" style="color: #007bff; text-decoration: none;">→ View Profiles</a>'
                '</div>',
                total_profiles, flagged_profiles
            )
        except Exception as e:
            return format_html('<span style="color: #dc3545;">Error loading device behavior status</span>')
    device_behavior_status.short_description = 'Device Behavior Profiles'
    
    def network_intelligence_status(self, obj):
        """Display network intelligence status"""
        from django.utils.html import format_html
        try:
            intelligence = models.NetworkIntelligence.objects.all()
            total_reports = intelligence.count()
            recent_reports = intelligence.filter(Timestamp__gte=timezone.now() - timezone.timedelta(hours=24)).count()
            
            return format_html(
                '<div style="background: #f8f9fa; padding: 10px; border-radius: 5px;">'
                '<strong>Network Intelligence:</strong><br>'
                'Total Reports: <span style="color: #007bff; font-weight: bold;">{}</span><br>'
                'Last 24h: <span style="color: #28a745; font-weight: bold;">{}</span><br>'
                '<a href="/admin/app/networkintelligence/" style="color: #007bff; text-decoration: none;">→ View Intelligence</a>'
                '</div>',
                total_reports, recent_reports
            )
        except Exception as e:
            return format_html('<span style="color: #dc3545;">Error loading network intelligence status</span>')
    network_intelligence_status.short_description = 'Network Intelligence'

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
    list_display = ('MAC_Address', 'Device_Name', 'Block_Reason', 'block_type_display', 'Blocked_Date', 'unblock_date_display', 'TTL_Violations_Count', 'Is_Active')
    list_filter = ('Block_Reason', 'Is_Active', 'Is_Permanent', 'Blocked_Date')
    search_fields = ('MAC_Address', 'Device_Name')
    readonly_fields = ('Blocked_Date', 'TTL_Violations_Count')
    actions = ['unblock_devices', 'block_devices']
    
    def block_type_display(self, obj):
        if obj.Is_Permanent:
            return format_html('<span style="color: #6f42c1; font-weight: bold;"><i class="fas fa-lock"></i> Permanent</span>')
        else:
            return format_html('<span style="color: #dc3545;"><i class="fas fa-clock"></i> Temporary</span>')
    block_type_display.short_description = 'Block Type'
    block_type_display.allow_tags = True
    
    def unblock_date_display(self, obj):
        if obj.Is_Permanent:
            return format_html('<span style="color: #6f42c1;">Never (Permanent)</span>')
        elif obj.Auto_Unblock_After:
            if obj.is_block_expired():
                return format_html('<span style="color: #28a745;">Expired</span>')
            else:
                formatted_date = obj.Auto_Unblock_After.strftime('%B %d, %Y %I:%M %p')
                return format_html('<span style="color: #dc3545;">{}</span>', formatted_date)
        else:
            return format_html('<span style="color: #6c757d;">Not Set</span>')
    unblock_date_display.short_description = 'Unblock Date'
    unblock_date_display.allow_tags = True

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
            
            # Total revenue (all time)
            total_revenue = models.Ledger.objects.aggregate(total=Sum('Denomination'))['total'] or 0
            
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
                'total_revenue': total_revenue,
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
                'total_revenue': 0,
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
    list_display = ('version_display', 'Update_Title', 'Status', 'progress_bar', 'Release_Date', 'action_buttons')
    list_filter = ('Status', 'Is_Auto_Update', 'Force_Update')
    readonly_fields = ('Progress', 'Downloaded_Bytes', 'Started_At', 'Completed_At', 'Error_Message', 'Backup_Path', 'Installation_Log', 'Created_At', 'Updated_At')
    search_fields = ('Version_Number', 'Update_Title', 'Description')
    ordering = ('-Release_Date', '-Created_At')  # Sort by latest release date first
    
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
            'fields': ('Started_At', 'Completed_At', 'Error_Message', 'Installation_Log', 'Created_At', 'Updated_At'),
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
    
    def version_display(self, obj):
        from django.utils.html import format_html
        from app.models import UpdateSettings
        
        # Get current version
        current_version = UpdateSettings.load().Current_Version
        version_html = obj.Version_Number
        
        # Add indicator if this is the current version
        if obj.Version_Number == current_version:
            version_html = format_html(
                '<span class="current-version-badge">{}</span> <span class="current-version-label">CURRENT</span>',
                obj.Version_Number
            )
        elif obj.Status == 'completed':
            # This version was installed but not current (rolled back?)
            version_html = format_html(
                '<span class="installed-version-badge">{}</span> <span class="installed-version-label">INSTALLED</span>',
                obj.Version_Number
            )
        elif self._is_newer_version(obj.Version_Number, current_version):
            # Only show NEWER badge if this version is actually newer than the current version
            # AND if there's no completed version that's newer than this one
            all_completed = models.SystemUpdate.objects.filter(Status='completed').exclude(Version_Number=current_version)
            has_newer_completed = any(self._is_newer_version(completed.Version_Number, obj.Version_Number) for completed in all_completed)
            
            if not has_newer_completed:
                # This is truly a newer version available
                version_html = format_html(
                    '<span class="newer-version-badge">{}</span> <span class="newer-version-label">NEWER</span>',
                    obj.Version_Number
                )
        
        return version_html
    version_display.short_description = 'Version'
    version_display.admin_order_field = 'Version_Number'
    
    def _is_newer_version(self, version1, version2):
        """Check if version1 is newer than version2"""
        try:
            v1_parts = [int(x) for x in version1.split('.')]
            v2_parts = [int(x) for x in version2.split('.')]
            
            max_len = max(len(v1_parts), len(v2_parts))
            v1_parts.extend([0] * (max_len - len(v1_parts)))
            v2_parts.extend([0] * (max_len - len(v2_parts)))
            
            return v1_parts > v2_parts
        except ValueError:
            return version1 > version2
    
    def action_buttons(self, obj):
        from django.utils.html import format_html
        buttons = []
        
        if obj.Status == 'available':
            buttons.append(format_html(
                '<a class="button" href="#" onclick="startDownload({}); return false;" title="Download update" '
                'style="background-color: #007bff; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px; white-space: nowrap;">'
                '<i class="fas fa-download" style="margin-right: 3px;"></i>Download</a>',
                obj.pk
            ))
            buttons.append(format_html(
                '<a class="button" href="#" onclick="removeUpdate({}); return false;" title="Remove update" '
                'style="background-color: #dc3545; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px; white-space: nowrap;">'
                '<i class="fas fa-trash" style="margin-right: 3px;"></i>Remove</a>',
                obj.pk
            ))
        elif obj.Status == 'downloading':
            buttons.append(format_html(
                '<a class="button" href="#" onclick="pauseDownload({}); return false;" title="Pause download" '
                'style="background-color: #ffc107; color: black; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px; white-space: nowrap;">'
                '<i class="fas fa-pause" style="margin-right: 3px;"></i>Pause</a>',
                obj.pk
            ))
            buttons.append(format_html(
                '<a class="button" href="#" onclick="removeUpdate({}); return false;" title="Cancel and remove" '
                'style="background-color: #dc3545; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px; white-space: nowrap;">'
                '<i class="fas fa-trash" style="margin-right: 3px;"></i>Remove</a>',
                obj.pk
            ))
        elif obj.Status == 'ready':
            buttons.append(format_html(
                '<a class="button" href="#" onclick="installUpdate({}); return false;" title="Install update" '
                'style="background-color: #28a745; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px; white-space: nowrap;">'
                '<i class="fas fa-rocket" style="margin-right: 3px;"></i>Install</a>',
                obj.pk
            ))
            buttons.append(format_html(
                '<a class="button" href="#" onclick="removeUpdate({}); return false;" title="Remove update" '
                'style="background-color: #dc3545; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px; white-space: nowrap;">'
                '<i class="fas fa-trash" style="margin-right: 3px;"></i>Remove</a>',
                obj.pk
            ))
        elif obj.Status == 'installing':
            # Check if the installation seems stuck (more than 30 minutes)
            from django.utils import timezone
            import datetime
            
            if obj.Started_At and (timezone.now() - obj.Started_At) > datetime.timedelta(minutes=30):
                # Show retry and repair options if stuck
                buttons.append(format_html(
                    '<a class="button" href="#" onclick="retryUpdate({}); return false;" title="Retry installation" '
                    'style="background-color: #007bff; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px; white-space: nowrap;">'
                    '<i class="fas fa-redo" style="margin-right: 3px;"></i>Retry</a>',
                    obj.pk
                ))
                buttons.append(format_html(
                    '<a class="button" href="#" onclick="repairUpdate({}); return false;" title="Repair installation" '
                    'style="background-color: #17a2b8; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px; white-space: nowrap;">'
                    '<i class="fas fa-wrench" style="margin-right: 3px;"></i>Repair</a>',
                    obj.pk
                ))
            else:
                # Show loading indicator for active installations
                buttons.append(format_html(
                    '<span class="button" style="background-color: #6c757d; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px; white-space: nowrap;">'
                    '<i class="fas fa-spinner fa-spin" style="margin-right: 3px;"></i>Installing...</span>'
                ))
            
            # Always show option to force stop
            buttons.append(format_html(
                '<a class="button" href="#" onclick="if(confirm(\'Force stop installation? This may leave the system in an inconsistent state.\')) {{ removeUpdate({}); }} return false;" title="Force stop" '
                'style="background-color: #dc3545; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px; white-space: nowrap;">'
                '<i class="fas fa-stop" style="margin-right: 3px;"></i>Force Stop</a>',
                obj.pk
            ))
        elif obj.Status == 'completed':
            if obj.can_rollback():
                buttons.append(format_html(
                    '<a class="button" href="#" onclick="rollbackUpdate({}); return false;" title="Rollback to previous version" '
                    'style="background-color: #ffc107; color: black; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px; white-space: nowrap;">'
                    '<i class="fas fa-undo" style="margin-right: 3px;"></i>Rollback</a>',
                    obj.pk
                ))
            buttons.append(format_html(
                '<a class="button" href="#" onclick="repairUpdate({}); return false;" title="Repair installation" '
                'style="background-color: #17a2b8; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px; white-space: nowrap;">'
                '<i class="fas fa-wrench" style="margin-right: 3px;"></i>Repair</a>',
                obj.pk
            ))
            buttons.append(format_html(
                '<a class="button" href="#" onclick="removeUpdate({}); return false;" title="Remove update record" '
                'style="background-color: transparent; color: #dc3545; padding: 4px 8px; text-decoration: none; border: 1px solid #dc3545; border-radius: 3px; margin: 1px; font-size: 11px; white-space: nowrap;">'
                '<i class="fas fa-trash" style="margin-right: 3px;"></i>Remove</a>',
                obj.pk
            ))
        elif obj.Status == 'failed':
            buttons.append(format_html(
                '<a class="button" href="#" onclick="retryUpdate({}); return false;" title="Retry installation" '
                'style="background-color: #007bff; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px; white-space: nowrap;">'
                '<i class="fas fa-redo" style="margin-right: 3px;"></i>Retry</a>',
                obj.pk
            ))
            buttons.append(format_html(
                '<a class="button" href="#" onclick="repairUpdate({}); return false;" title="Repair installation" '
                'style="background-color: #17a2b8; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px; white-space: nowrap;">'
                '<i class="fas fa-wrench" style="margin-right: 3px;"></i>Repair</a>',
                obj.pk
            ))
            buttons.append(format_html(
                '<a class="button" href="#" onclick="removeUpdate({}); return false;" title="Remove update" '
                'style="background-color: transparent; color: #dc3545; padding: 4px 8px; text-decoration: none; border: 1px solid #dc3545; border-radius: 3px; margin: 1px; font-size: 11px; white-space: nowrap;">'
                '<i class="fas fa-trash" style="margin-right: 3px;"></i>Remove</a>',
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
        from django.urls import reverse
        extra_context = extra_context or {}
        extra_context.update({
            'title': 'System Updates',
            'check_updates_button': True,
            'update_settings_button': True,
            'update_settings_url': reverse('admin:app_updatesettings_change', args=[1]),
            'has_add_permission': False,  # Don't show Add button since updates come from GitHub
        })
        
        return super().changelist_view(request, extra_context=extra_context)
    
    
    def has_add_permission(self, request):
        """Disable manual adding of updates - they come from GitHub"""
        return False
    
    def get_urls(self):
        from django.urls import path
        from django.views.decorators.csrf import csrf_exempt
        from django.contrib.admin.views.decorators import staff_member_required
        
        # Create a properly wrapped view with both authentication and CSRF exemption
        wrapped_check_updates = csrf_exempt(staff_member_required(self.check_updates_view))
        
        urls = super().get_urls()
        custom_urls = [
            path('check-updates/', wrapped_check_updates, name='app_systemupdate_check'),
            path('<int:pk>/download/', self.admin_site.admin_view(self.download_update_view), name='app_systemupdate_download'),
            path('<int:pk>/install/', self.admin_site.admin_view(self.install_update_view), name='app_systemupdate_install'),
            path('<int:pk>/rollback/', self.admin_site.admin_view(self.rollback_update_view), name='app_systemupdate_rollback'),
            path('<int:pk>/progress/', self.admin_site.admin_view(self.progress_view), name='app_systemupdate_progress'),
            path('<int:pk>/install-progress/', self.admin_site.admin_view(self.install_progress_view), name='app_systemupdate_install_progress'),
            path('<int:pk>/installation-logs/', self.admin_site.admin_view(self.installation_logs_view), name='app_systemupdate_installation_logs'),
            path('<int:pk>/remove/', self.admin_site.admin_view(self.remove_update_view), name='app_systemupdate_remove'),
            path('<int:pk>/repair/', self.admin_site.admin_view(self.repair_update_view), name='app_systemupdate_repair'),
            path('<int:pk>/retry/', self.admin_site.admin_view(self.retry_update_view), name='app_systemupdate_retry'),
        ]
        return custom_urls + urls
    
    def check_updates_view(self, request):
        from django.http import JsonResponse
        from app.services.update_service import GitHubUpdateService
        import logging
        
        logger = logging.getLogger(__name__)
        logger.info(f"Check updates view called by user: {request.user}, is_staff: {request.user.is_staff if request.user.is_authenticated else 'Anonymous'}")
        
        try:
            service = GitHubUpdateService()
            result = service.check_for_updates()
            
            if result['status'] == 'success' and result['updates_available']:
                # Create update objects
                service.create_system_updates(result['updates'])
            
            return JsonResponse(result)
        except Exception as e:
            logger.error(f"Error in check_updates_view: {str(e)}")
            return JsonResponse({'status': 'error', 'message': str(e)})
    
    def download_update_view(self, request, pk):
        from django.http import JsonResponse
        from app.services.update_service import UpdateDownloadService
        import threading
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            update = models.SystemUpdate.objects.get(pk=pk)
            
            # Start download in background thread
            def download_in_background():
                try:
                    # Refresh the update object from database
                    fresh_update = models.SystemUpdate.objects.get(pk=pk)
                    service = UpdateDownloadService(fresh_update)
                    service.download_update()
                except Exception as e:
                    logger.error(f"Background download error: {e}")
                    try:
                        error_update = models.SystemUpdate.objects.get(pk=pk)
                        error_update.Status = 'failed'
                        error_update.Error_Message = str(e)
                        error_update.save(update_fields=['Status', 'Error_Message'])
                    except:
                        pass
            
            thread = threading.Thread(target=download_in_background)
            thread.daemon = True
            thread.start()
            
            return JsonResponse({'status': 'success', 'message': 'Download started'})
        except models.SystemUpdate.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Update not found'})
        except Exception as e:
            logger.error(f"Error in download_update_view: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)})
    
    def install_update_view(self, request, pk):
        from django.http import JsonResponse
        from app.services.update_service import UpdateInstallService
        import threading
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            update = models.SystemUpdate.objects.get(pk=pk)
            
            if update.Status != 'ready':
                return JsonResponse({'status': 'error', 'message': 'Update not ready for installation'})
            
            # Start installation in background thread
            def install_in_background():
                try:
                    # Refresh the update object from database
                    fresh_update = models.SystemUpdate.objects.get(pk=pk)
                    service = UpdateInstallService(fresh_update)
                    service.install_update()
                except Exception as e:
                    logger.error(f"Background installation error: {e}")
                    try:
                        error_update = models.SystemUpdate.objects.get(pk=pk)
                        error_update.Status = 'failed'
                        error_update.Error_Message = str(e)
                        error_update.save(update_fields=['Status', 'Error_Message'])
                    except:
                        pass
            
            thread = threading.Thread(target=install_in_background)
            thread.daemon = True
            thread.start()
            
            return JsonResponse({'status': 'success', 'message': 'Installation started'})
        except models.SystemUpdate.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Update not found'})
        except Exception as e:
            logger.error(f"Error in install_update_view: {e}")
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
        import logging
        logger = logging.getLogger(__name__)
        
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
        except Exception as e:
            logger.error(f"Error in progress_view: {e}")
            return JsonResponse({
                'status': 'error', 
                'message': f'Server error: {str(e)}',
                'progress': 0,
                'downloaded_bytes': 0,
                'file_size': 0,
                'error': str(e)
            })
    
    def install_progress_view(self, request, pk):
        from django.http import JsonResponse
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            update = models.SystemUpdate.objects.get(pk=pk)
            return JsonResponse({
                'status': update.Status,
                'progress': update.Progress,
                'error': update.Error_Message
            })
        except models.SystemUpdate.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Update not found'})
        except Exception as e:
            logger.error(f"Error in install_progress_view: {e}")
            return JsonResponse({
                'status': 'error', 
                'message': f'Server error: {str(e)}',
                'progress': 0
            })
    
    def installation_logs_view(self, request, pk):
        from django.http import JsonResponse
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            update = models.SystemUpdate.objects.get(pk=pk)
            return JsonResponse({
                'status': 'success',
                'logs': update.Installation_Log or ''
            })
        except models.SystemUpdate.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Update not found'})
        except Exception as e:
            logger.error(f"Error in installation_logs_view: {e}")
            return JsonResponse({
                'status': 'error', 
                'message': f'Server error: {str(e)}',
                'logs': ''
            })
    
    def remove_update_view(self, request, pk):
        from django.http import JsonResponse
        import logging
        import os
        from django.conf import settings
        logger = logging.getLogger(__name__)
        
        try:
            update = models.SystemUpdate.objects.get(pk=pk)
            
            # Clean up downloaded files
            temp_path = os.path.join(settings.BASE_DIR, 'temp', 'updates')
            update_file = os.path.join(temp_path, f"update_{update.Version_Number}.zip")
            extract_path = os.path.join(temp_path, f"extracted_{update.Version_Number}")
            
            # Remove files if they exist
            if os.path.exists(update_file):
                os.remove(update_file)
                logger.info(f"Removed update file: {update_file}")
            
            if os.path.exists(extract_path):
                import shutil
                shutil.rmtree(extract_path)
                logger.info(f"Removed extracted directory: {extract_path}")
            
            # Remove the update record
            version_number = update.Version_Number
            update.delete()
            
            return JsonResponse({
                'status': 'success', 
                'message': f'Update {version_number} removed successfully'
            })
            
        except models.SystemUpdate.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Update not found'})
        except Exception as e:
            logger.error(f"Error in remove_update_view: {e}")
            return JsonResponse({
                'status': 'error', 
                'message': f'Failed to remove update: {str(e)}'
            })
    
    def repair_update_view(self, request, pk):
        from django.http import JsonResponse
        from app.services.update_service import UpdateInstallService
        import threading
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            update = models.SystemUpdate.objects.get(pk=pk)
            
            if update.Status not in ['completed', 'failed']:
                return JsonResponse({
                    'status': 'error', 
                    'message': 'Update repair only available for completed or failed updates'
                })
            
            # Start repair in background thread
            def repair_in_background():
                try:
                    fresh_update = models.SystemUpdate.objects.get(pk=pk)
                    service = UpdateInstallService(fresh_update)
                    
                    # Use the dedicated repair method
                    service.repair_installation()
                    
                except Exception as e:
                    logger.error(f"Background repair error: {e}")
                    try:
                        error_update = models.SystemUpdate.objects.get(pk=pk)
                        error_update.Status = 'failed'
                        error_update.Error_Message = f"Repair failed: {str(e)}"
                        error_update.save()
                    except:
                        pass
            
            thread = threading.Thread(target=repair_in_background)
            thread.daemon = True
            thread.start()
            
            return JsonResponse({
                'status': 'success', 
                'message': 'Update repair started'
            })
            
        except models.SystemUpdate.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Update not found'})
        except Exception as e:
            logger.error(f"Error in repair_update_view: {e}")
            return JsonResponse({
                'status': 'error', 
                'message': f'Failed to start repair: {str(e)}'
            })
    
    def retry_update_view(self, request, pk):
        from django.http import JsonResponse
        from app.services.update_service import UpdateInstallService
        import threading
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            update = models.SystemUpdate.objects.get(pk=pk)
            
            # Allow retry for both failed and stuck installing updates
            if update.Status not in ['failed', 'installing']:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Retry only available for failed or stuck updates'
                })
            
            # Check if we need to download first or can directly install
            if not update.can_install():
                # Need to download first
                return JsonResponse({
                    'status': 'error', 
                    'message': 'Update needs to be downloaded first'
                })
            
            # Start retry in background thread
            def retry_in_background():
                try:
                    fresh_update = models.SystemUpdate.objects.get(pk=pk)
                    service = UpdateInstallService(fresh_update)
                    
                    # Clean up any stuck state first
                    service.cleanup_stuck_update()
                    
                    # Reset status and clear previous errors
                    fresh_update.Status = 'installing'
                    fresh_update.Progress = 0
                    fresh_update.Error_Message = None
                    fresh_update.Installation_Log = None
                    fresh_update.save()
                    
                    # Retry installation
                    service.install_update()
                    
                except Exception as e:
                    logger.error(f"Background retry error: {e}")
                    try:
                        error_update = models.SystemUpdate.objects.get(pk=pk)
                        error_update.Status = 'failed'
                        error_update.Error_Message = str(e)
                        error_update.save()
                    except:
                        pass
            
            thread = threading.Thread(target=retry_in_background)
            thread.daemon = True
            thread.start()
            
            return JsonResponse({
                'status': 'success', 
                'message': 'Update retry started'
            })
            
        except models.SystemUpdate.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Update not found'})
        except Exception as e:
            logger.error(f"Error in retry_update_view: {e}")
            return JsonResponse({
                'status': 'error', 
                'message': f'Failed to retry update: {str(e)}'
            })


class UpdateSettingsAdmin(Singleton):
    fieldsets = (
        ('Repository Settings', {
            'fields': ('GitHub_Repository', 'Update_Channel', 'current_version_display', 'Check_Interval_Hours', 'Auto_Download', 'Auto_Install', 'Last_Check', 'Backup_Before_Update', 'Max_Backup_Count')
        }),
    )
    
    readonly_fields = ('Last_Check', 'current_version_display')
    
    def current_version_display(self, obj):
        from django.utils.html import format_html
        return format_html(
            '<div style="display: flex; align-items: center; gap: 10px;">'
            '<span style="font-weight: bold; color: #28a745;">{}</span>'
            '<a href="#" onclick="refreshVersion(); return false;" '
            'style="background-color: #17a2b8; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; font-size: 11px;">'
            '<i class="fas fa-sync" style="margin-right: 3px;"></i>Refresh</a>'
            '</div>'
            '<script>'
            'function refreshVersion() {{'
            '    if (confirm("Refresh current version from git tags?")) {{'
            '        fetch("/admin/app/updatesettings/refresh-version/", {{'
            '            method: "POST",'
            '            headers: {{'
            '                "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value,'
            '                "Content-Type": "application/json"'
            '            }}'
            '        }})'
            '.then(response => response.json())'
            '.then(data => {{'
            '            if (data.status === "success") {{'
            '                alert("Version updated to: " + data.version);'
            '                location.reload();'
            '            }} else {{'
            '                alert("Error: " + data.message);'
            '            }}'
            '        }})'
            '.catch(error => alert("Network error: " + error));'
            '    }}'
            '}}'
            '</script>',
            obj.Current_Version
        )
    current_version_display.short_description = 'Current Version'
    
    def changelist_view(self, request, extra_context=None):
        return HttpResponseRedirect(reverse('admin:app_updatesettings_change', args=[1]))
    
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('refresh-version/', self.admin_site.admin_view(self.refresh_version_view), name='app_updatesettings_refresh_version'),
        ]
        return custom_urls + urls
    
    def refresh_version_view(self, request):
        from django.http import JsonResponse
        if request.method == 'POST':
            try:
                settings = models.UpdateSettings.load()
                new_version = models.UpdateSettings.get_system_version()
                settings.Current_Version = new_version
                settings.save()
                return JsonResponse({
                    'status': 'success',
                    'version': new_version,
                    'message': f'Version updated to {new_version}'
                })
            except Exception as e:
                return JsonResponse({
                    'status': 'error',
                    'message': str(e)
                })
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'})


class BackupSettingsAdmin(Singleton):
    """Admin for backup settings configuration"""
    fieldsets = (
        ('Auto Backup Settings', {
            'fields': ('Auto_Backup_Enabled', 'Auto_Backup_Interval_Hours', 'Max_Backup_Count', 'Backup_Location')
        }),
        ('Backup Content', {
            'fields': ('Include_Client_Data', 'Include_System_Settings', 'Include_Logs')
        }),
        ('Storage & Retention', {
            'fields': ('Compress_Backups', 'Retention_Days')
        }),
        ('Notifications', {
            'fields': ('Email_Notifications', 'Email_Recipients')
        }),
        ('Status', {
            'fields': ('Last_Auto_Backup',),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ('Last_Auto_Backup',)
    
    def changelist_view(self, request, extra_context=None):
        return HttpResponseRedirect(reverse('admin:app_backupsettings_change', args=[1]))


class DatabaseBackupAdmin(admin.ModelAdmin):
    """Admin for database backup management"""
    list_display = ('backup_name', 'backup_type_badge', 'status_badge', 'file_size_display', 'progress_bar', 'created_at', 'action_buttons')
    list_filter = ('backup_type', 'status', 'compressed', 'created_at')
    readonly_fields = ('file_path', 'file_size', 'tables_included', 'records_count', 'progress_percentage', 
                      'current_operation', 'started_at', 'completed_at', 'error_message', 'created_at')
    search_fields = ('backup_name', 'description', 'created_by')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Backup Information', {
            'fields': ('backup_name', 'backup_type', 'description', 'status')
        }),
        ('File Details', {
            'fields': ('file_path', 'file_size', 'compressed', 'tables_included', 'records_count')
        }),
        ('Progress', {
            'fields': ('progress_percentage', 'current_operation'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'started_at', 'completed_at'),
            'classes': ('collapse',)
        }),
        ('Error Information', {
            'fields': ('error_message',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by',),
            'classes': ('collapse',)
        })
    )
    
    def backup_type_badge(self, obj):
        return obj.get_backup_type_badge()
    backup_type_badge.short_description = 'Type'
    
    def status_badge(self, obj):
        return obj.get_status_badge()
    status_badge.short_description = 'Status'
    
    def file_size_display(self, obj):
        return obj.get_file_size_display()
    file_size_display.short_description = 'Size'
    
    def progress_bar(self, obj):
        from django.utils.html import format_html
        if obj.status == 'running':
            color = 'warning'
        elif obj.status == 'completed':
            color = 'success'
        elif obj.status == 'failed':
            color = 'danger'
        else:
            color = 'secondary'
            
        return format_html(
            '<div class="progress" style="width: 150px; height: 20px;">'
            '<div class="progress-bar bg-{}" role="progressbar" style="width: {}%;" '
            'aria-valuenow="{}" aria-valuemin="0" aria-valuemax="100">{}%</div>'
            '</div>',
            color, obj.progress_percentage, obj.progress_percentage, obj.progress_percentage
        )
    progress_bar.short_description = 'Progress'
    
    def action_buttons(self, obj):
        from django.utils.html import format_html
        buttons = []
        
        if obj.status == 'completed':
            # Download button
            buttons.append(format_html(
                '<a class="button" href="#" onclick="downloadBackup({}); return false;" title="Download backup file" '
                'style="background-color: #007bff; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px; white-space: nowrap;">'
                '<i class="fas fa-download" style="margin-right: 3px;"></i>Download</a>',
                obj.pk
            ))
            
            # Restore button
            buttons.append(format_html(
                '<a class="button" href="#" onclick="restoreBackup({}); return false;" title="Restore from backup" '
                'style="background-color: #28a745; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px; white-space: nowrap;">'
                '<i class="fas fa-undo" style="margin-right: 3px;"></i>Restore</a>',
                obj.pk
            ))
        
        if obj.status in ['completed', 'failed']:
            # Delete button
            buttons.append(format_html(
                '<a class="button" href="#" onclick="deleteBackup({}); return false;" title="Delete backup" '
                'style="background-color: #dc3545; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px; white-space: nowrap;">'
                '<i class="fas fa-trash" style="margin-right: 3px;"></i>Delete</a>',
                obj.pk
            ))
        
        if obj.status == 'running':
            # Cancel button
            buttons.append(format_html(
                '<a class="button" href="#" onclick="cancelBackup({}); return false;" title="Cancel backup" '
                'style="background-color: #ffc107; color: black; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px; white-space: nowrap;">'
                '<i class="fas fa-times" style="margin-right: 3px;"></i>Cancel</a>',
                obj.pk
            ))
        
        return format_html(' '.join(str(button) for button in buttons))
    action_buttons.short_description = 'Actions'
    
    def has_add_permission(self, request):
        """Disable manual adding - backups are created through actions"""
        return False
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        
        extra_context.update({
            'title': 'Database Backups',
            'has_add_permission': False,
        })
        
        return super().changelist_view(request, extra_context=extra_context)
    
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('create-backup/', self.admin_site.admin_view(self.create_backup_view), name='app_databasebackup_create'),
            path('<int:pk>/download/', self.admin_site.admin_view(self.download_backup_view), name='app_databasebackup_download'),
            path('<int:pk>/restore/', self.admin_site.admin_view(self.restore_backup_view), name='app_databasebackup_restore'),
            path('<int:pk>/delete-backup/', self.admin_site.admin_view(self.delete_backup_view), name='app_databasebackup_delete'),
            path('<int:pk>/cancel/', self.admin_site.admin_view(self.cancel_backup_view), name='app_databasebackup_cancel'),
            path('<int:pk>/progress/', self.admin_site.admin_view(self.progress_view), name='app_databasebackup_progress'),
        ]
        return custom_urls + urls
    
    def create_backup_view(self, request):
        from django.http import JsonResponse
        from .services.database_backup_service import run_backup_async
        from .models import DatabaseBackup
        
        if request.method == 'POST':
            try:
                import json
                data = json.loads(request.body)
                
                backup_name = data.get('backup_name', f'Manual Backup {timezone.now().strftime("%Y-%m-%d %H:%M")}')
                backup_type = data.get('backup_type', 'full')
                description = data.get('description', '')
                compressed = data.get('compressed', True)
                
                # Create backup record
                backup = DatabaseBackup.objects.create(
                    backup_name=backup_name,
                    backup_type=backup_type,
                    description=description,
                    compressed=compressed,
                    created_by=request.user.username if hasattr(request.user, 'username') else 'admin',
                    status='pending'
                )
                
                # Start backup asynchronously
                run_backup_async(backup.id, backup_type)
                
                return JsonResponse({
                    'status': 'success',
                    'backup_id': backup.id,
                    'message': f'Backup "{backup_name}" started successfully'
                })
                
            except Exception as e:
                return JsonResponse({
                    'status': 'error',
                    'message': str(e)
                })
        
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'})
    
    def download_backup_view(self, request, pk):
        from django.http import HttpResponse, Http404
        import os
        
        try:
            backup = models.DatabaseBackup.objects.get(pk=pk)
            
            if not backup.file_path or not os.path.exists(backup.file_path):
                raise Http404("Backup file not found")
            
            # Serve file for download
            with open(backup.file_path, 'rb') as f:
                response = HttpResponse(f.read(), content_type='application/octet-stream')
                filename = os.path.basename(backup.file_path)
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                return response
                
        except models.DatabaseBackup.DoesNotExist:
            raise Http404("Backup not found")
    
    def restore_backup_view(self, request, pk):
        from django.http import JsonResponse
        from .services.database_backup_service import run_restore_async
        
        if request.method == 'POST':
            try:
                backup = models.DatabaseBackup.objects.get(pk=pk)
                
                if backup.status != 'completed':
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Only completed backups can be restored'
                    })
                
                # Start restore asynchronously
                run_restore_async(backup.id)
                
                return JsonResponse({
                    'status': 'success',
                    'message': f'Restore of "{backup.backup_name}" started'
                })
                
            except models.DatabaseBackup.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Backup not found'
                })
            except Exception as e:
                return JsonResponse({
                    'status': 'error',
                    'message': str(e)
                })
        
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'})
    
    def delete_backup_view(self, request, pk):
        from django.http import JsonResponse
        import os
        
        if request.method == 'POST':
            try:
                backup = models.DatabaseBackup.objects.get(pk=pk)
                
                # Delete file if exists
                if backup.file_path and os.path.exists(backup.file_path):
                    os.remove(backup.file_path)
                
                backup_name = backup.backup_name
                backup.delete()
                
                return JsonResponse({
                    'status': 'success',
                    'message': f'Backup "{backup_name}" deleted successfully'
                })
                
            except models.DatabaseBackup.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Backup not found'
                })
            except Exception as e:
                return JsonResponse({
                    'status': 'error',
                    'message': str(e)
                })
        
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'})
    
    def cancel_backup_view(self, request, pk):
        from django.http import JsonResponse
        
        if request.method == 'POST':
            try:
                backup = models.DatabaseBackup.objects.get(pk=pk)
                
                if backup.status == 'running':
                    backup.status = 'cancelled'
                    backup.current_operation = 'Cancelled by user'
                    backup.completed_at = timezone.now()
                    backup.save()
                    
                    return JsonResponse({
                        'status': 'success',
                        'message': f'Backup "{backup.backup_name}" cancelled'
                    })
                else:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Only running backups can be cancelled'
                    })
                
            except models.DatabaseBackup.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Backup not found'
                })
        
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'})
    
    def progress_view(self, request, pk):
        from django.http import JsonResponse
        
        try:
            backup = models.DatabaseBackup.objects.get(pk=pk)
            
            return JsonResponse({
                'status': 'success',
                'backup_status': backup.status,
                'progress': backup.progress_percentage,
                'current_operation': backup.current_operation,
                'error_message': backup.error_message
            })
            
        except models.DatabaseBackup.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Backup not found'
            })
    
    class Media:
        js = ('admin/js/database_backup.js',)
        css = {
            'all': ('admin/css/database_backup.css',)
        }


class VLANSettingsAdmin(Singleton):
    """Admin for VLAN network configuration"""
    fieldsets = (
        ('Network Mode Configuration', {
            'fields': ('network_mode', 'vlan_id', 'current_status_display')
        }),
        ('Network Interfaces', {
            'fields': ('eth_interface', 'usb_interface'),
            'classes': ('collapse',)
        }),
        ('Advanced Settings', {
            'fields': ('auto_restart_on_change',),
            'classes': ('collapse',)
        }),
        ('Status Information', {
            'fields': ('last_mode_change',),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ('current_status_display', 'last_mode_change')
    
    def current_status_display(self, obj):
        from django.utils.html import format_html
        
        status_color = '#28a745' if 'Active' in obj.current_status else '#6c757d'
        
        return format_html(
            '<span style="font-weight: bold; color: {};">{}</span>',
            status_color,
            obj.current_status
        )
    current_status_display.short_description = 'Current Status'
    
    def changelist_view(self, request, extra_context=None):
        return HttpResponseRedirect(reverse('admin:app_vlansettings_change', args=[1]))
    
    def has_add_permission(self, request):
        return False  # Singleton - no add permission
    
    def has_delete_permission(self, request, obj=None):
        return False  # Singleton - no delete permission
    
    def get_object(self, request, object_id, from_field=None):
        """Return singleton instance or create it if it doesn't exist"""
        return models.VLANSettings.load()
    
    def response_change(self, request, obj):
        """Override to remove save and add another, save and continue editing buttons"""
        # Always redirect back to the same change page after save
        return HttpResponseRedirect(reverse('admin:app_vlansettings_change', args=[obj.pk]))
    
    def save_model(self, request, obj, form, change):
        from django.contrib import messages
        from app.services.network_service import NetworkConfigurationService
        
        # Save the model first
        super().save_model(request, obj, form, change)
        
        try:
            # Apply network configuration immediately after save
            service = NetworkConfigurationService()
            success, message = service.apply_network_mode(obj)
            
            if success:
                if obj.auto_restart_on_change:
                    messages.add_message(
                        request, 
                        messages.SUCCESS, 
                        f'VLAN Settings saved and applied successfully. {message}. System will restart in 1 minute to activate changes.'
                    )
                    # Schedule system restart
                    service.restart_system()
                else:
                    messages.add_message(
                        request, 
                        messages.SUCCESS, 
                        f'VLAN Settings saved and applied successfully. {message}. Manual restart recommended.'
                    )
            else:
                messages.add_message(
                    request, 
                    messages.ERROR, 
                    f'VLAN Settings saved but failed to apply network configuration: {message}'
                )
                
        except Exception as e:
            messages.add_message(
                request, 
                messages.ERROR, 
                f'VLAN Settings saved but error applying configuration: {str(e)}'
            )
    
    class Media:
        js = ('admin/js/vlan_settings.js',)


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
admin.site.register(models.BackupSettings, BackupSettingsAdmin)
admin.site.register(models.DatabaseBackup, DatabaseBackupAdmin)
admin.site.register(models.VLANSettings, VLANSettingsAdmin)


# ZeroTier Monitoring Data Inline Admin
class ZeroTierMonitoringDataInline(admin.TabularInline):
    model = models.ZeroTierMonitoringData
    extra = 0
    max_num = 20  # Limit number of monitoring records shown
    
    fields = ('timestamp', 'network_status_inline', 'connected_clients', 'cpu_usage', 'memory_usage', 'total_revenue_inline')
    readonly_fields = ('timestamp', 'network_status_inline', 'connected_clients', 'cpu_usage', 'memory_usage', 'total_revenue_inline')
    ordering = ['-timestamp']
    
    def network_status_inline(self, obj):
        if obj.network_online:
            return format_html('<span style="color: #28a745; font-weight: 600;">🟢 ONLINE</span>')
        return format_html('<span style="color: #dc3545; font-weight: 600;">🔴 OFFLINE</span>')
    network_status_inline.short_description = 'Network'
    
    def total_revenue_inline(self, obj):
        if obj.total_revenue:
            return format_html('<span style="color: #28a745; font-weight: 600;">₱{:.2f}</span>', obj.total_revenue)
        return format_html('<span style="color: #6c757d;">₱0.00</span>')
    total_revenue_inline.short_description = 'Revenue'
    
    def has_add_permission(self, request, obj):
        return False  # Monitoring data is auto-generated
    
    def has_delete_permission(self, request, obj):
        return True  # Allow cleanup of old monitoring data


class ZeroTierSettingsAdmin(Singleton):
    """Admin for ZeroTier remote monitoring configuration"""
    inlines = [ZeroTierMonitoringDataInline]
    
    fieldsets = (
        ('Status Information', {
            'fields': ('network_id', 'network_name', 'connection_status_display', 'zerotier_ip', 'last_seen', 'last_monitoring_update'),
            'classes': ('collapse',)
        }),
        ('API Configuration', {
            'fields': ('api_token', 'central_url')
        }),
        ('Device Configuration', {
            'fields': ('device_name', 'device_description', 'enable_monitoring', 'auto_authorize', 'monitoring_interval')
        })
    )
    
    readonly_fields = ('connection_status_display', 'zerotier_ip', 'last_seen', 'last_monitoring_update')
    
    def connection_status_display(self, obj):
        from django.utils.html import format_html
        from app.services.zerotier_service import ZeroTierService
        
        service = ZeroTierService()
        zt_status = service.get_zerotier_status()
        
        # Installation status
        install_status = "✅ Installed" if zt_status['installed'] else "❌ Not Installed"
        service_status = "🟢 Running" if zt_status['running'] else "🔴 Stopped"
        
        return format_html(
            '<div style="margin-bottom: 10px;">'
            '<strong>ZeroTier Status:</strong><br>'
            'Installation: {}<br>'
            'Service: {}<br>'
            'Version: {}<br>'
            'Node ID: {}<br>'
            '</div>'
            '<div style="display: flex; gap: 10px; margin-top: 15px;">'
            '<a href="#" onclick="toggleMonitoring(); return false;" '
            'style="background-color: #007bff; color: white; padding: 6px 12px; text-decoration: none; border-radius: 3px; font-size: 12px;">'
            '<i class="fas fa-power-off" style="margin-right: 5px;"></i>Toggle Service</a>'
            '<a href="#" onclick="testConnection(); return false;" '
            'style="background-color: #28a745; color: white; padding: 6px 12px; text-decoration: none; border-radius: 3px; font-size: 12px;">'
            '<i class="fas fa-satellite-dish" style="margin-right: 5px;"></i>Test Connection</a>'
            '<a href="#" onclick="collectMetrics(); return false;" '
            'style="background-color: #17a2b8; color: white; padding: 6px 12px; text-decoration: none; border-radius: 3px; font-size: 12px;">'
            '<i class="fas fa-chart-line" style="margin-right: 5px;"></i>Collect Metrics</a>'
            '</div>'
            '<script>'
            'function toggleMonitoring() {{'
            '    if (confirm("Toggle ZeroTier monitoring service?")) {{'
            '        fetch("/admin/app/zerotiersettings/toggle-service/", {{'
            '            method: "POST",'
            '            headers: {{'
            '                "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value,'
            '                "Content-Type": "application/json"'
            '            }}'
            '        }})'
            '.then(response => response.json())'
            '.then(data => {{'
            '            alert(data.message);'
            '            location.reload();'
            '        }})'
            '.catch(error => alert("Error: " + error));'
            '    }}'
            '}}'
            'function testConnection() {{'
            '    fetch("/admin/app/zerotiersettings/test-connection/", {{'
            '        method: "POST",'
            '        headers: {{'
            '            "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value,'
            '            "Content-Type": "application/json"'
            '        }}'
            '    }})'
            '.then(response => response.json())'
            '.then(data => alert(data.message))'
            '.catch(error => alert("Error: " + error));'
            '}}'
            'function collectMetrics() {{'
            '    fetch("/admin/app/zerotiersettings/collect-metrics/", {{'
            '        method: "POST",'
            '        headers: {{'
            '            "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value,'
            '            "Content-Type": "application/json"'
            '        }}'
            '    }})'
            '.then(response => response.json())'
            '.then(data => alert(data.message))'
            '.catch(error => alert("Error: " + error));'
            '}}'
            '</script>',
            install_status,
            service_status,
            zt_status.get('version', 'Unknown'),
            zt_status.get('node_id', 'Unknown')
        )
    connection_status_display.short_description = 'ZeroTier Status & Controls'
    
    def changelist_view(self, request, extra_context=None):
        return HttpResponseRedirect(reverse('admin:app_zerotiersettings_change', args=[1]))
    
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('toggle-service/', self.admin_site.admin_view(self.toggle_service_view), name='app_zerotiersettings_toggle_service'),
            path('test-connection/', self.admin_site.admin_view(self.test_connection_view), name='app_zerotiersettings_test_connection'),
            path('collect-metrics/', self.admin_site.admin_view(self.collect_metrics_view), name='app_zerotiersettings_collect_metrics'),
        ]
        return custom_urls + urls
    
    def toggle_service_view(self, request):
        from django.http import JsonResponse
        from app.services.zerotier_service import ZeroTierService
        
        if request.method == 'POST':
            try:
                zt_settings = models.ZeroTierSettings.load()
                service = ZeroTierService()
                
                if zt_settings.enable_monitoring:
                    success, message = service.start_monitoring_service(zt_settings)
                else:
                    success, message = service.stop_monitoring_service(zt_settings)
                
                return JsonResponse({
                    'status': 'success' if success else 'error',
                    'message': message
                })
                
            except Exception as e:
                return JsonResponse({
                    'status': 'error',
                    'message': str(e)
                })
        
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'})
    
    def test_connection_view(self, request):
        from django.http import JsonResponse
        from app.services.zerotier_service import ZeroTierService
        
        if request.method == 'POST':
            try:
                zt_settings = models.ZeroTierSettings.load()
                service = ZeroTierService()
                
                # Get ZeroTier status
                zt_status = service.get_zerotier_status()
                
                if not zt_status['installed']:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'ZeroTier is not installed'
                    })
                
                if not zt_status['running']:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'ZeroTier service is not running'
                    })
                
                # Get network info
                network_info = None
                if zt_settings.network_id:
                    network_info = service.get_network_info(zt_settings.network_id)
                
                if network_info:
                    return JsonResponse({
                        'status': 'success',
                        'message': f'Connected to network {zt_settings.network_id}. IP: {network_info.get("zt_ip", "Unknown")}'
                    })
                else:
                    return JsonResponse({
                        'status': 'warning',
                        'message': 'ZeroTier is running but not connected to configured network'
                    })
                
            except Exception as e:
                return JsonResponse({
                    'status': 'error',
                    'message': str(e)
                })
        
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'})
    
    def collect_metrics_view(self, request):
        from django.http import JsonResponse
        from app.services.zerotier_service import ZeroTierService
        
        if request.method == 'POST':
            try:
                zt_settings = models.ZeroTierSettings.load()
                service = ZeroTierService()
                
                success, message = service.collect_and_store_monitoring_data(zt_settings)
                
                return JsonResponse({
                    'status': 'success' if success else 'error',
                    'message': message
                })
                
            except Exception as e:
                return JsonResponse({
                    'status': 'error',
                    'message': str(e)
                })
        
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'})
    
    def get_object(self, request, object_id, from_field=None):
        """Return singleton instance or create it if it doesn't exist"""
        return models.ZeroTierSettings.load()
    
    def has_add_permission(self, request):
        return False  # Singleton - no add permission
    
    def has_delete_permission(self, request, obj=None):
        return False  # Singleton - no delete permission
    
    def response_change(self, request, obj):
        """Override to remove save and add another, save and continue editing buttons"""
        # Always redirect back to the same change page after save
        return HttpResponseRedirect(reverse('admin:app_zerotiersettings_change', args=[obj.pk]))
    
    def save_model(self, request, obj, form, change):
        from django.contrib import messages
        messages.add_message(request, messages.INFO, 'ZeroTier settings updated successfully.')
        super().save_model(request, obj, form, change)






admin.site.register(models.ZeroTierSettings, ZeroTierSettingsAdmin)
# Note: ZeroTierMonitoringData is now managed as inline within ZeroTierSettings
# admin.site.register(models.ZeroTierMonitoringData, ZeroTierMonitoringDataAdmin)


class PortPrioritizationAdmin(admin.ModelAdmin):
    list_display = ('rule_name', 'traffic_type_display', 'priority_level_display', 'ports_summary', 'protocol', 'bandwidth_summary', 'is_active', 'created_at')
    list_filter = ('priority_level', 'traffic_type', 'protocol', 'is_active', 'apply_to_all_clients')
    search_fields = ('rule_name', 'ports')
    readonly_fields = ('created_at', 'updated_at')
    list_editable = ('is_active',)
    ordering = ['priority_level', 'rule_name']
    
    fieldsets = (
        ('Basic Configuration', {
            'fields': ('rule_name', 'traffic_type', 'priority_level')
        }),
        ('Port Configuration', {
            'fields': ('ports', 'protocol'),
            'description': 'Specify ports and protocols for this rule. Use commas for multiple ports and dashes for ranges (e.g., 80,443,8000-9000)'
        }),
        ('Bandwidth Settings', {
            'fields': ('guaranteed_bandwidth_up', 'guaranteed_bandwidth_down', 'max_bandwidth_up', 'max_bandwidth_down'),
            'description': 'Configure bandwidth guarantees and limits for this traffic type'
        }),
        ('Advanced Settings', {
            'fields': ('dscp_marking', 'burst_allowance'),
            'classes': ('collapse',),
            'description': 'Advanced QoS settings for network engineers'
        }),
        ('Rule Status', {
            'fields': ('is_active', 'apply_to_all_clients', 'created_at', 'updated_at')
        })
    )
    
    def traffic_type_display(self, obj):
        from django.utils.html import format_html
        colors = {
            'browsing': '#007bff',     # Blue
            'gaming': '#dc3545',       # Red  
            'streaming': '#fd7e14',    # Orange
            'voip': '#28a745',         # Green
            'downloading': '#6f42c1',  # Purple
            'p2p': '#6c757d',          # Gray
            'social': '#e83e8c',       # Pink
            'email': '#20c997',        # Teal
            'custom': '#ffc107'        # Yellow
        }
        color = colors.get(obj.traffic_type, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_traffic_type_display()
        )
    traffic_type_display.short_description = 'Traffic Type'
    
    def priority_level_display(self, obj):
        from django.utils.html import format_html
        colors = {
            'critical': '#dc3545',  # Red
            'high': '#fd7e14',      # Orange  
            'normal': '#28a745',    # Green
            'low': '#6c757d'        # Gray
        }
        icons = {
            'critical': 'fas fa-exclamation-triangle',
            'high': 'fas fa-arrow-up',
            'normal': 'fas fa-minus', 
            'low': 'fas fa-arrow-down'
        }
        color = colors.get(obj.priority_level, '#6c757d')
        icon = icons.get(obj.priority_level, 'fas fa-minus')
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;"><i class="{}"></i> {}</span>',
            color, icon, obj.get_priority_level_display()
        )
    priority_level_display.short_description = 'Priority'
    
    def ports_summary(self, obj):
        ports = obj.ports
        if len(ports) > 30:
            return f"{ports[:30]}..."
        return ports
    ports_summary.short_description = 'Ports'
    
    def bandwidth_summary(self, obj):
        from django.utils.html import format_html
        summary = []
        
        if obj.guaranteed_bandwidth_down:
            summary.append(f"↓{obj.guaranteed_bandwidth_down//1000}M")
        if obj.guaranteed_bandwidth_up:
            summary.append(f"↑{obj.guaranteed_bandwidth_up//1000}M")
        if obj.max_bandwidth_down and not obj.guaranteed_bandwidth_down:
            summary.append(f"Max↓{obj.max_bandwidth_down//1000}M")
        if obj.max_bandwidth_up and not obj.guaranteed_bandwidth_up:
            summary.append(f"Max↑{obj.max_bandwidth_up//1000}M")
            
        if not summary:
            return format_html('<span style="color: #6c757d;">No limits</span>')
        
        return format_html(
            '<span style="font-family: monospace; font-size: 11px;">{}</span>',
            ' | '.join(summary)
        )
    bandwidth_summary.short_description = 'Bandwidth'
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context.update({
            'title': 'Port Prioritization Rules - Traffic QoS Management',
            'subtitle': 'Configure bandwidth prioritization based on port and traffic type'
        })
        return super().changelist_view(request, extra_context=extra_context)
    
    actions = ['activate_rules', 'deactivate_rules', 'apply_traffic_control', 'create_default_rules']
    
    def activate_rules(self, request, queryset):
        updated = queryset.update(is_active=True)
        
        # Apply traffic control for activated rules
        for rule in queryset.filter(is_active=True):
            rule.apply_traffic_control()
        
        self.message_user(request, f'{updated} rule(s) activated and traffic control applied.')
    activate_rules.short_description = "Activate selected rules and apply traffic control"
    
    def deactivate_rules(self, request, queryset):
        # Remove traffic control for deactivated rules
        for rule in queryset.filter(is_active=True):
            rule.remove_traffic_control()
        
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} rule(s) deactivated and traffic control removed.')
    deactivate_rules.short_description = "Deactivate selected rules and remove traffic control"
    
    def apply_traffic_control(self, request, queryset):
        success_count = 0
        for rule in queryset.filter(is_active=True):
            if rule.apply_traffic_control():
                success_count += 1
        
        self.message_user(request, f'Traffic control applied to {success_count} rule(s).')
    apply_traffic_control.short_description = "Apply traffic control to selected rules"
    
    def create_default_rules(self, request, queryset):
        created_count = models.PortPrioritization.create_default_rules()
        if created_count > 0:
            self.message_user(request, f'{created_count} default port prioritization rules created.')
        else:
            self.message_user(request, 'Default rules already exist.')
    create_default_rules.short_description = "Create default port prioritization rules"
    
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('create-defaults/', self.admin_site.admin_view(self.create_defaults_view), name='app_portprioritization_create_defaults'),
        ]
        return custom_urls + urls
    
    def create_defaults_view(self, request):
        from django.http import JsonResponse
        
        if request.method == 'POST':
            try:
                created_count = models.PortPrioritization.create_default_rules()
                if created_count > 0:
                    return JsonResponse({
                        'status': 'success',
                        'message': f'{created_count} default port prioritization rules created.',
                        'created_count': created_count
                    })
                else:
                    return JsonResponse({
                        'status': 'info',
                        'message': 'Default rules already exist.',
                        'created_count': 0
                    })
            except Exception as e:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Error creating default rules: {str(e)}'
                })
        
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'})
    
    def save_model(self, request, obj, form, change):
        """Handle saving port prioritization rules and apply traffic control"""
        from django.contrib import messages
        
        # Save the model first
        super().save_model(request, obj, form, change)
        
        # If the rule is active, apply traffic control automatically
        if obj.is_active:
            try:
                if obj.apply_traffic_control():
                    if not change:  # New rule
                        messages.success(request, f'Port prioritization rule "{obj.rule_name}" created and traffic control applied successfully.')
                    else:  # Updated rule
                        messages.success(request, f'Port prioritization rule "{obj.rule_name}" updated and traffic control applied successfully.')
                else:
                    messages.warning(request, f'Port prioritization rule "{obj.rule_name}" saved but traffic control application failed.')
            except Exception as e:
                messages.error(request, f'Port prioritization rule "{obj.rule_name}" saved but error applying traffic control: {str(e)}')
        else:
            # If rule is inactive, remove traffic control
            try:
                obj.remove_traffic_control()
                if not change:
                    messages.success(request, f'Port prioritization rule "{obj.rule_name}" created (inactive).')
                else:
                    messages.success(request, f'Port prioritization rule "{obj.rule_name}" updated (inactive) and traffic control removed.')
            except Exception as e:
                messages.warning(request, f'Port prioritization rule "{obj.rule_name}" saved but error removing traffic control: {str(e)}')

admin.site.register(models.PortPrioritization, PortPrioritizationAdmin)


# Portal Banner Inline Admin
class PortalBannerInline(admin.TabularInline):
    model = models.PortalBanner
    extra = 0
    max_num = 10  # Limit number of banners
    
    fields = ('image_preview', 'name', 'banner_type', 'image', 'is_active', 'display_order', 'link_url', 'advanced_toggle')
    readonly_fields = ('image_preview', 'advanced_toggle')
    ordering = ['display_order', 'name']
    
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width: 60px; max-height: 40px; object-fit: cover; border-radius: 4px; border: 1px solid #ddd;" />',
                obj.image.url
            )
        return format_html('<span style="color: #999; font-style: italic; font-size: 11px;">No image</span>')
    image_preview.short_description = 'Preview'
    
    def advanced_toggle(self, obj):
        if obj.pk:
            return format_html(
                '<a href="#" onclick="toggleAdvanced({}); return false;" style="color: #007cba; text-decoration: none; font-size: 11px;">⚙️ Advanced</a>',
                obj.pk
            )
        return '-'
    advanced_toggle.short_description = 'Options'
    
    class Media:
        css = {
            'all': ('admin/css/portal_banner_inline.css',)
        }


# Portal Audio Inline Admin
class PortalAudioInline(admin.TabularInline):
    model = models.PortalAudio
    extra = 0
    max_num = 10  # Limit number of audio files
    
    fields = ('audio_preview', 'name', 'audio_type', 'audio_file', 'is_active', 'volume_display', 'loop_display')
    readonly_fields = ('audio_preview', 'volume_display', 'loop_display')
    ordering = ['audio_type', 'name']
    
    def audio_preview(self, obj):
        if obj.audio_file:
            return format_html(
                '<audio controls style="width: 160px; height: 25px;"><source src="{}" type="audio/mpeg">Audio not supported</audio>',
                obj.audio_file.url
            )
        return format_html('<span style="color: #999; font-style: italic; font-size: 11px;">No audio</span>')
    audio_preview.short_description = 'Preview'
    
    def volume_display(self, obj):
        volume = obj.volume or 50
        return format_html(
            '<div style="display: flex; align-items: center; gap: 6px; min-width: 80px;">'
            '<div style="width: 50px; height: 6px; background: #e0e0e0; border-radius: 3px; overflow: hidden;">'
            '<div style="height: 100%; width: {}%; background: linear-gradient(90deg, #4caf50 0%, #2196f3 50%, #ff9800 100%); border-radius: 3px;"></div>'
            '</div>'
            '<span style="font-size: 10px; color: #666; font-weight: 500;">{}%</span>'
            '</div>',
            volume, volume
        )
    volume_display.short_description = 'Volume'
    
    def loop_display(self, obj):
        if obj.loop:
            return format_html('<span style="color: #2e7d32; font-size: 11px; font-weight: 600;">LOOP</span>')
        return format_html('<span style="color: #757575; font-size: 11px;">ONCE</span>')
    loop_display.short_description = 'Loop'
    
    class Media:
        css = {
            'all': ('admin/css/portal_audio_inline.css',)
        }


class PortalSettingsAdmin(admin.ModelAdmin):
    list_display = ('portal_title', 'hotspot_name', 'logo_preview', 'color_preview', 'maintenance_status', 'features_summary', 'updated_at')
    
    # Include Banner and Audio management as inlines
    inlines = [PortalBannerInline, PortalAudioInline]
    
    class Media:
        css = {
            'all': ('admin/css/portal_settings.css', 'admin/css/portal_banner_inline.css', 'admin/css/portal_audio_inline.css')
        }
    
    fieldsets = (
        ('Basic Portal Information', {
            'fields': (
                'portal_title',
                'portal_subtitle', 
                'hotspot_name',
                'hotspot_address',
                'created_at',
                'updated_at'
            )
        }),
        ('Portal Features & Behavior', {
            'fields': (
                'enable_vouchers',
                'enable_pause_resume',
                'pause_resume_min_time',
                'enable_social_login',
                'redirect_url',
                'show_timer',
                'show_data_usage',
                'auto_refresh_interval',
                'slot_timeout'
            ),
            'description': 'Configure portal features, functionality, and display behavior'
        }),
        ('Branding & Logo', {
            'fields': (
                'logo',
                'favicon',
                'primary_color',
                'secondary_color',
                'background_color',
                'text_color'
            ),
            'description': 'Upload logo and favicon for your portal. Customize portal colors and theme using hex color codes (e.g., #007bff). Banner images are managed in the Portal Banners section below.'
        }),
        ('Maintenance Mode', {
            'fields': (
                'maintenance_mode',
                'maintenance_message'
            ),
            'classes': ('collapse',),
            'description': 'Maintenance mode settings'
        })
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    def logo_preview(self, obj):
        """Show logo preview in admin list"""
        from django.utils.html import format_html
        if obj.logo:
            return format_html(
                '<img src="{}" style="max-height: 40px; max-width: 60px; object-fit: contain; border-radius: 4px;" alt="Logo"/>',
                obj.logo.url
            )
        return format_html('<span style="color: #999; font-style: italic;">No logo</span>')
    logo_preview.short_description = 'Logo'
    
    def color_preview(self, obj):
        """Show color scheme preview"""
        from django.utils.html import format_html
        primary = obj.primary_color or '#007bff'
        secondary = obj.secondary_color or '#0056b3'
        return format_html(
            '<div style="display: flex; gap: 2px; align-items: center;">'
            '<div style="width: 20px; height: 20px; background-color: {}; border-radius: 3px; border: 1px solid #ddd;" title="Primary: {}"></div>'
            '<div style="width: 20px; height: 20px; background-color: {}; border-radius: 3px; border: 1px solid #ddd;" title="Secondary: {}"></div>'
            '<span style="font-size: 11px; color: #666; margin-left: 5px;">Theme</span>'
            '</div>',
            primary, primary, secondary, secondary
        )
    color_preview.short_description = 'Colors'
    
    def maintenance_status(self, obj):
        """Show maintenance mode status"""
        from django.utils.html import format_html
        if obj.maintenance_mode:
            return format_html(
                '<span class="maintenance-status maintenance-active" style="background-color: #ffebee; color: #d32f2f; border: 1px solid #ffcdd2; padding: 4px 8px; border-radius: 12px; font-size: 12px; font-weight: 600;">MAINTENANCE</span>'
            )
        else:
            return format_html(
                '<span class="maintenance-status maintenance-inactive" style="background-color: #e8f5e8; color: #2e7d32; border: 1px solid #c8e6c9; padding: 4px 8px; border-radius: 12px; font-size: 12px; font-weight: 600;">ACTIVE</span>'
            )
    maintenance_status.short_description = 'Status'
    maintenance_status.admin_order_field = 'maintenance_mode'
    
    def features_summary(self, obj):
        """Show enabled features summary"""
        from django.utils.html import format_html
        from django.utils.safestring import mark_safe
        
        features = []
        if obj.enable_vouchers:
            features.append('<span style="background: #e3f2fd; color: #1976d2; padding: 1px 4px; border-radius: 3px; font-size: 10px;">VOUCHER</span>')
        if obj.enable_pause_resume:
            features.append('<span style="background: #fff3e0; color: #f57c00; padding: 1px 4px; border-radius: 3px; font-size: 10px;">PAUSE</span>')
        if obj.enable_social_login:
            features.append('<span style="background: #e8f5e8; color: #2e7d32; padding: 1px 4px; border-radius: 3px; font-size: 10px;">SOCIAL</span>')
        if obj.show_timer:
            features.append('<span style="background: #fce4ec; color: #c2185b; padding: 1px 4px; border-radius: 3px; font-size: 10px;">TIMER</span>')
        
        if features:
            html_content = '<div style="display: flex; flex-wrap: wrap; gap: 2px;">{}</div>'.format(''.join(features))
            return mark_safe(html_content)
        else:
            return format_html('<span style="color: #999; font-style: italic;">Basic</span>')
    features_summary.short_description = 'Features'
    
    def has_add_permission(self, request):
        # Only allow one instance (singleton)
        return not models.PortalSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # Don't allow deletion of portal settings
        return False
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context.update({
            'title': 'Portal Settings - Complete Portal Management',
            'subtitle': 'Configure portal settings, banners, audio files, and all portal features in one place'
        })
        response = super().changelist_view(request, extra_context=extra_context)
        # Add custom CSS class to the response context
        if hasattr(response, 'context_data'):
            response.context_data['cl_css_classes'] = getattr(response.context_data.get('cl'), 'css_classes', '') + ' portal-settings-admin'
        return response


class PortalBannerAdmin(admin.ModelAdmin):
    list_display = ('name', 'banner_type', 'is_active', 'display_order', 'schedule_status', 'image_preview', 'created_at')
    list_filter = ('banner_type', 'is_active', 'start_date', 'end_date')
    search_fields = ('name', 'alt_text')
    ordering = ['display_order', 'name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'banner_type', 'image', 'alt_text')
        }),
        ('Banner Link', {
            'fields': ('link_url', 'open_in_new_tab'),
            'description': 'Optional: Make banner clickable with a link'
        }),
        ('Display Settings', {
            'fields': ('is_active', 'display_order'),
            'description': 'Control banner visibility and display order'
        }),
        ('Schedule Settings', {
            'fields': ('start_date', 'end_date'),
            'classes': ('collapse',),
            'description': 'Optional: Schedule when banner should be displayed'
        }),
        ('Image Constraints', {
            'fields': ('max_width', 'max_height'),
            'classes': ('collapse',),
            'description': 'Maximum dimensions for uploaded images'
        })
    )
    
    def image_preview(self, obj):
        if obj.image:
            from django.utils.html import format_html
            return format_html(
                '<img src="{}" style="max-width: 100px; max-height: 60px; object-fit: cover;" />',
                obj.image.url
            )
        return "No image"
    image_preview.short_description = 'Preview'
    
    def schedule_status(self, obj):
        from django.utils.html import format_html
        if not obj.start_date and not obj.end_date:
            return format_html('<span style="color: #28a745;">Always Active</span>')
        
        if obj.is_scheduled_active():
            return format_html('<span style="color: #28a745;">Active</span>')
        else:
            return format_html('<span style="color: #dc3545;">Scheduled Inactive</span>')
    schedule_status.short_description = 'Schedule Status'
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context.update({
            'title': 'Portal - Banner Images',
            'subtitle': 'Upload and manage portal banner images with scheduling'
        })
        return super().changelist_view(request, extra_context=extra_context)
    
    actions = ['activate_banners', 'deactivate_banners', 'reset_display_order']
    
    def activate_banners(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} banner(s) activated.')
    activate_banners.short_description = "Activate selected banners"
    
    def deactivate_banners(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} banner(s) deactivated.')
    deactivate_banners.short_description = "Deactivate selected banners"
    
    def reset_display_order(self, request, queryset):
        for i, banner in enumerate(queryset.order_by('created_at'), 1):
            banner.display_order = i * 10
            banner.save()
        self.message_user(request, f'Display order reset for {queryset.count()} banner(s).')
    reset_display_order.short_description = "Reset display order (10, 20, 30...)"


class PortalAudioAdmin(admin.ModelAdmin):
    list_display = ('name', 'audio_type_display', 'audio_preview', 'volume_display', 'loop_display', 'is_active')
    list_filter = ('audio_type', 'is_active')
    search_fields = ('name',)
    
    class Media:
        css = {
            'all': ('admin/css/portal_audio.css',)
        }
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'audio_type', 'audio_file')
        }),
        ('Audio Settings', {
            'fields': ('is_active', 'volume', 'loop'),
            'description': 'Configure audio playback settings'
        }),
        ('Audio Properties', {
            'fields': ('duration', 'file_size'),
            'classes': ('collapse',),
            'description': 'Audio file properties (auto-populated)'
        })
    )
    
    readonly_fields = ('duration', 'file_size')
    
    def audio_type_display(self, obj):
        """Display audio type with styled badge"""
        from django.utils.html import format_html
        type_class = f"audio-type-{obj.audio_type}"
        return format_html(
            '<span class="audio-type-badge {}">{}</span>',
            type_class, obj.get_audio_type_display()
        )
    audio_type_display.short_description = 'Type'
    audio_type_display.admin_order_field = 'audio_type'
    
    def audio_preview(self, obj):
        """Display audio preview player in the list view"""
        if obj.audio_file:
            from django.utils.html import format_html
            return format_html(
                '<div class="portal-audio-preview">'
                '<audio controls preload="none" style="width: 200px; height: 32px;">'
                '<source src="{}" type="audio/mpeg">'
                'Your browser does not support the audio element.'
                '</audio>'
                '</div>',
                obj.audio_file.url
            )
        return format_html('<span style="color: #999; font-style: italic;">No audio file</span>')
    audio_preview.short_description = 'Preview'
    audio_preview.allow_tags = True
    
    def volume_display(self, obj):
        """Display volume with progress bar"""
        from django.utils.html import format_html
        volume = obj.volume or 50
        return format_html(
            '<div class="volume-progress-container" title="{}%">'
            '<div class="volume-progress-bar">'
            '<div class="volume-progress-fill" style="width: {}%"></div>'
            '</div>'
            '<span class="volume-percentage">{}%</span>'
            '</div>',
            volume, volume, volume
        )
    volume_display.short_description = 'Volume'
    volume_display.admin_order_field = 'volume'
    
    def loop_display(self, obj):
        """Display loop status without emojis"""
        from django.utils.html import format_html
        if obj.loop:
            return format_html('<span class="loop-status loop-yes" title="Audio will loop continuously">Yes</span>')
        else:
            return format_html('<span class="loop-status loop-no" title="Audio plays once only">No</span>')
    loop_display.short_description = 'Loop'
    loop_display.admin_order_field = 'loop'
    
    def file_info(self, obj):
        if obj.audio_file:
            from django.utils.html import format_html
            
            # Handle file_size safely
            try:
                if obj.file_size and isinstance(obj.file_size, (int, float)):
                    file_size_mb = obj.file_size / (1024 * 1024)
                else:
                    # Try to get file size from the file object
                    file_size_mb = obj.audio_file.size / (1024 * 1024) if hasattr(obj.audio_file, 'size') else 0
            except (TypeError, AttributeError, ZeroDivisionError):
                file_size_mb = 0
            
            return format_html(
                '<span style="font-family: monospace;">{:.1f} MB</span><br/>'
                '<audio controls style="width: 200px; height: 30px;">'
                '<source src="{}" type="audio/mpeg">'
                'Your browser does not support the audio element.'
                '</audio>',
                file_size_mb, obj.audio_file.url
            )
        return "No file"
    file_info.short_description = 'File Info & Preview'
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context.update({
            'title': 'Portal - Audio Files',
            'subtitle': 'Upload and manage portal audio files (background music, sound effects)'
        })
        response = super().changelist_view(request, extra_context=extra_context)
        # Add custom CSS class to the response context
        if hasattr(response, 'context_data'):
            response.context_data['cl_css_classes'] = getattr(response.context_data.get('cl'), 'css_classes', '') + ' portal-audio-admin'
        return response
    
    # actions = ['activate_audio', 'deactivate_audio', 'set_default_volume']
    
    def activate_audio(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} audio file(s) activated.')
    activate_audio.short_description = "Activate selected audio files"
    
    def deactivate_audio(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} audio file(s) deactivated.')
    deactivate_audio.short_description = "Deactivate selected audio files"
    
    def set_default_volume(self, request, queryset):
        updated = queryset.update(volume=50)
        self.message_user(request, f'Volume set to 50% for {updated} audio file(s).')
    set_default_volume.short_description = "Set volume to 50% for selected files"


class PortalTextAdmin(admin.ModelAdmin):
    list_display = ('name', 'text_type', 'language', 'is_active', 'content_preview', 'allow_html', 'updated_at')
    list_filter = ('text_type', 'language', 'is_active', 'allow_html')
    search_fields = ('name', 'content')
    list_editable = ('is_active',)
    ordering = ['text_type', 'language', 'display_order']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'text_type', 'language', 'content')
        }),
        ('Text Formatting', {
            'fields': ('allow_html', 'font_size', 'font_weight', 'text_align'),
            'description': 'Configure text appearance and formatting'
        }),
        ('Display Settings', {
            'fields': ('is_active', 'display_order'),
            'description': 'Control text visibility and display order'
        })
    )
    
    def content_preview(self, obj):
        content = obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
        if obj.allow_html:
            from django.utils.html import format_html
            return format_html('<span style="color: #e83e8c;">[HTML]</span> {}', content)
        return content
    content_preview.short_description = 'Content Preview'
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context.update({
            'title': 'Portal - Text Content',
            'subtitle': 'Customize portal text messages and content in multiple languages'
        })
        return super().changelist_view(request, extra_context=extra_context)
    
    actions = ['activate_texts', 'deactivate_texts', 'create_default_texts']
    
    def activate_texts(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} text(s) activated.')
    activate_texts.short_description = "Activate selected texts"
    
    def deactivate_texts(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} text(s) deactivated.')
    deactivate_texts.short_description = "Deactivate selected texts"
    
    def create_default_texts(self, request, queryset):
        """Create default portal texts"""
        default_texts = [
            {
                'name': 'Default Welcome Message',
                'text_type': 'welcome_message',
                'content': 'Welcome to our PISOWifi Portal! Insert coins to get connected to the internet.',
                'language': 'en'
            },
            {
                'name': 'Default Connection Instructions',
                'text_type': 'instructions',
                'content': '1. Insert coins to purchase internet time\n2. Wait for connection confirmation\n3. Browse the internet\n4. Use pause/resume to control your session',
                'language': 'en'
            },
            {
                'name': 'Default Contact Info',
                'text_type': 'contact_info',
                'content': 'For technical support, please contact the hotspot administrator.',
                'language': 'en'
            }
        ]
        
        created_count = 0
        for text_data in default_texts:
            text, created = models.PortalText.objects.get_or_create(
                name=text_data['name'],
                text_type=text_data['text_type'],
                language=text_data['language'],
                defaults=text_data
            )
            if created:
                created_count += 1
        
        if created_count > 0:
            self.message_user(request, f'{created_count} default portal text(s) created.')
        else:
            self.message_user(request, 'Default portal texts already exist.')
    create_default_texts.short_description = "Create default portal texts"


# Register Portal Models
admin.site.register(models.PortalSettings, PortalSettingsAdmin)
# Note: PortalBanner and PortalAudio are now managed as inlines within PortalSettings
# admin.site.register(models.PortalBanner, PortalBannerAdmin)
# admin.site.register(models.PortalAudio, PortalAudioAdmin)
admin.site.register(models.PortalText, PortalTextAdmin)

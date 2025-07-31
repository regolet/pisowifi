from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden, HttpResponse, Http404
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.utils.decorators import method_decorator
from app.security.decorators import (
    high_security, voucher_rate_limit, payment_rate_limit, 
    portal_rate_limit, require_local_ip, log_security_event
)
from django.shortcuts import render, redirect
from django.views import View
from django.views.generic.edit import UpdateView
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum, F
from django.db.models.functions import Greatest
from django.contrib import messages
from datetime import timedelta
from getmac import getmac
# Licensing imports removed for personal use
from app import models
import subprocess
import time, math, json
import socket
import struct
import os
import logging
from django.conf import settings

# Get logger for this module
logger = logging.getLogger('app')
security_logger = logging.getLogger('security')

local_ip = ['::1', '127.0.0.1', '10.0.0.1']

def get_available_banner_images():
    """
    Get list of available banner images from Portal admin models only
    Returns list of image data (url, alt_text, link_url) for portal display
    """
    from . import models
    
    banner_images = []
    
    # Get banners from Portal admin models only
    try:
        # Get the active portal settings first
        portal_settings = models.PortalSettings.objects.first()
        if portal_settings:
            active_banners = models.PortalBanner.objects.filter(
                portal_settings=portal_settings,
                is_active=True,
                banner_type='carousel'
            ).order_by('display_order', 'name')
            
            for banner in active_banners:
                # Check if banner is scheduled to be active
                if banner.is_scheduled_active():
                    banner_images.append({
                        'url': banner.image.url if banner.image else '',
                        'alt_text': banner.alt_text or banner.name,
                        'link_url': banner.link_url,
                        'open_in_new_tab': banner.open_in_new_tab,
                        'source': 'database'
                    })
    except Exception as e:
        logger.error(f"Error loading portal banners: {e}")
    
    return banner_images

def get_portal_audio_files():
    """
    Get active portal audio files from database only
    Returns dict with audio file URLs by type
    """
    from . import models
    
    audio_files = {}
    
    try:
        # Get the active portal settings first
        portal_settings = models.PortalSettings.objects.first()
        if portal_settings:
            active_audio = models.PortalAudio.objects.filter(
                portal_settings=portal_settings,
                is_active=True
            )
            
            for audio in active_audio:
                if audio.audio_file:
                    audio_files[audio.audio_type] = {
                        'url': audio.audio_file.url,
                        'volume': audio.volume,
                        'loop': audio.loop,
                        'name': audio.name
                    }
    except Exception as e:
        logger.error(f"Error loading portal audio files: {e}")
    
    return audio_files

def get_portal_settings():
    """
    Get portal settings from database or return defaults
    """
    from . import models
    
    try:
        portal_settings = models.PortalSettings.objects.first()
        if portal_settings:
            return {
                'portal_title': portal_settings.portal_title,
                'portal_subtitle': portal_settings.portal_subtitle,
                'hotspot_name': portal_settings.hotspot_name,
                'hotspot_address': portal_settings.hotspot_address,
                'logo': portal_settings.logo.url if portal_settings.logo else None,
                'favicon': portal_settings.favicon.url if portal_settings.favicon else None,
                'primary_color': portal_settings.primary_color,
                'secondary_color': portal_settings.secondary_color,
                'background_color': portal_settings.background_color,
                'text_color': portal_settings.text_color,
                'redirect_url': portal_settings.redirect_url,
                'show_timer': portal_settings.show_timer,
                'show_data_usage': portal_settings.show_data_usage,
                'auto_refresh_interval': portal_settings.auto_refresh_interval,
                'enable_vouchers': portal_settings.enable_vouchers,
                'enable_pause_resume': portal_settings.enable_pause_resume,
                'pause_resume_min_time': portal_settings.pause_resume_min_time,
                'enable_social_login': portal_settings.enable_social_login,
                'maintenance_mode': portal_settings.maintenance_mode,
                'maintenance_message': portal_settings.maintenance_message
            }
    except Exception as e:
        print(f"Error loading portal settings: {e}")
    
    # Return defaults if no settings found
    return {
        'portal_title': 'PISOWifi Portal',
        'portal_subtitle': '',
        'hotspot_name': 'PISOWifi Hotspot',
        'hotspot_address': '',
        'logo': None,
        'favicon': None,
        'primary_color': '#007bff',
        'secondary_color': '#6c757d',
        'background_color': '#ffffff',
        'text_color': '#212529',
        'redirect_url': '',
        'show_timer': True,
        'show_data_usage': True,
        'auto_refresh_interval': 30,
        'enable_vouchers': True,
        'enable_pause_resume': True,
        'pause_resume_min_time': None,
        'enable_social_login': False,
        'maintenance_mode': False,
        'maintenance_message': ''
    }

def get_portal_texts():
    """
    Get portal text content from database
    """
    from . import models
    
    texts = {}
    
    try:
        active_texts = models.PortalText.objects.filter(is_active=True, language='en')
        
        for text in active_texts:
            texts[text.text_type] = {
                'content': text.get_safe_content(),
                'font_size': text.font_size,
                'font_weight': text.font_weight,
                'text_align': text.text_align
            }
    except Exception as e:
        print(f"Error loading portal texts: {e}")
    
    return texts

def check_internet_connectivity():
    """
    Check if the server has internet connectivity
    Returns True if connected, False otherwise
    """
    try:
        import requests
        # Try to reach a reliable endpoint with short timeout
        response = requests.get('https://8.8.8.8', timeout=5)
        return True
    except:
        try:
            # Fallback: try DNS resolution
            import socket
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return True
        except:
            return False

def get_ttl_from_ip(ip_address):
    """
    Extract TTL value from IP packet using ping
    Returns None if unable to detect TTL
    """
    try:
        from .utils.security import safe_ping_command, validate_ip_address
        
        # Validate IP address first
        if not validate_ip_address(ip_address):
            return None
        
        result = safe_ping_command(ip_address)
        if not result:
            return None
            
        output = result.stdout
        
        # Parse TTL from ping output
        if "ttl=" in output.lower():
            ttl_part = output.lower().split("ttl=")[1].split()[0]
            ttl_value = int(ttl_part)
            return ttl_value
        elif "ttl " in output.lower():
            # Alternative parsing for different ping formats
            lines = output.split('\n')
            for line in lines:
                if 'ttl' in line.lower():
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if 'ttl' in part.lower() and i + 1 < len(parts):
                            try:
                                return int(parts[i + 1])
                            except ValueError:
                                continue
        return None
    except Exception as e:
        logger.warning(f"TTL detection error for {ip_address}: {e}")
        security_logger.warning(f"TTL detection attempt failed for IP {ip_address}")
        return None

def analyze_ttl_for_sharing(mac_address, ttl_value, request=None):
    """
    Analyze TTL value to detect potential internet sharing
    Returns dict with analysis results and connection limits
    """
    try:
        security_settings = models.SecuritySettings.objects.get(pk=1)
    except models.SecuritySettings.DoesNotExist:
        # Create default security settings if not exists
        security_settings = models.SecuritySettings.objects.create()
    
    if not security_settings.TTL_Detection_Enabled or ttl_value is None:
        return {
            'is_suspicious': False, 
            'reason': 'TTL detection disabled or no TTL data',
            'connection_limit': security_settings.Normal_Device_Connections,
            'ttl_classification': 'unknown'
        }
    
    expected_ttl = security_settings.Default_TTL_Value
    tolerance = security_settings.TTL_Tolerance
    
    # Calculate TTL deviation
    ttl_deviation = abs(ttl_value - expected_ttl)
    is_suspicious = ttl_deviation > tolerance
    
    # Determine TTL classification
    if is_suspicious:
        ttl_classification = 'suspicious'
        connection_limit = security_settings.Suspicious_Device_Connections
    else:
        ttl_classification = 'normal'
        connection_limit = security_settings.Normal_Device_Connections
    
    # Log traffic data
    models.TrafficMonitor.objects.create(
        Client_MAC=mac_address,
        TTL_Value=ttl_value,
        Is_Suspicious=is_suspicious,
        Notes=f"Expected: {expected_ttl}, Detected: {ttl_value}, Deviation: {ttl_deviation}"
    )
    
    analysis_result = {
        'is_suspicious': is_suspicious,
        'ttl_value': ttl_value,
        'expected_ttl': expected_ttl,
        'deviation': ttl_deviation,
        'tolerance': tolerance,
        'ttl_classification': ttl_classification,
        'connection_limit': connection_limit,
        'reason': f'TTL deviation of {ttl_deviation} {"exceeds" if is_suspicious else "within"} tolerance of {tolerance}'
    }
    
    # Check for repeated violations
    if is_suspicious:
        recent_violations = models.TrafficMonitor.objects.filter(
            Client_MAC=mac_address,
            Is_Suspicious=True,
            Timestamp__gte=timezone.now() - timezone.timedelta(hours=1)
        ).count()
        
        analysis_result['recent_violations'] = recent_violations
        
        # Apply stricter limits for repeat violators
        if recent_violations >= security_settings.Max_TTL_Violations:
            analysis_result['connection_limit'] = 1  # Even stricter limit
            analysis_result['strict_mode'] = True
            
            # Check for TTL modification (MikroTik-style enforcement)
            if check_ttl_modification_needed(mac_address, analysis_result):
                ttl_rule = apply_ttl_firewall_rule(
                    mac_address, 
                    ttl_value=security_settings.Modified_TTL_Value,
                    duration_hours=int(security_settings.TTL_Rule_Duration.total_seconds() / 3600)
                )
                
                if ttl_rule:
                    analysis_result['ttl_rule_applied'] = True
                    analysis_result['ttl_rule_value'] = ttl_rule.TTL_Value
                    analysis_result['ttl_rule_expires'] = ttl_rule.Expires_At
                    analysis_result['enforcement_level'] = 'network_level'  # MikroTik-style
                else:
                    analysis_result['ttl_rule_failed'] = True
            
            # Optional: Block device completely if enabled (fallback)
            if security_settings.Enable_Device_Blocking:
                try:
                    blocked_device = models.BlockedDevices.objects.get(MAC_Address=mac_address, Is_Active=True)
                    analysis_result['already_blocked'] = True
                except models.BlockedDevices.DoesNotExist:
                    auto_unblock_time = timezone.now() + security_settings.Block_Duration
                    
                    models.BlockedDevices.objects.create(
                        MAC_Address=mac_address,
                        Block_Reason='ttl_sharing',
                        Auto_Unblock_After=auto_unblock_time,
                        TTL_Violations_Count=recent_violations,
                        Admin_Notes=f'Auto-blocked due to {recent_violations} TTL violations in 1 hour'
                    )
                    
                    analysis_result['auto_blocked'] = True
                    analysis_result['block_duration'] = security_settings.Block_Duration
    
    return analysis_result

def check_connection_limit(mac_address, request=None):
    """
    Check if device has reached its connection limit
    Returns dict with connection status and limits
    """
    try:
        security_settings = models.SecuritySettings.objects.get(pk=1)
    except models.SecuritySettings.DoesNotExist:
        security_settings = models.SecuritySettings.objects.create()
    
    if not security_settings.Limit_Connections:
        return {
            'can_connect': True,
            'reason': 'Connection limiting disabled',
            'current_connections': 0,
            'connection_limit': 999
        }
    
    # Clean up expired sessions
    models.ConnectionTracker.cleanup_expired_sessions()
    
    # Get current active connections for this device
    current_connections = models.ConnectionTracker.get_active_connections_for_device(mac_address)
    
    # Get TTL analysis to determine connection limit
    device_ip = getDeviceInfo(request)['ip'] if request else None
    ttl_value = get_ttl_from_ip(device_ip) if device_ip else None
    
    if ttl_value:
        ttl_analysis = analyze_ttl_for_sharing(mac_address, ttl_value, request)
        connection_limit = ttl_analysis['connection_limit']
        ttl_classification = ttl_analysis['ttl_classification']
    else:
        connection_limit = security_settings.Normal_Device_Connections
        ttl_classification = 'unknown'
    
    can_connect = current_connections < connection_limit
    
    return {
        'can_connect': can_connect,
        'current_connections': current_connections,
        'connection_limit': connection_limit,
        'ttl_classification': ttl_classification,
        'reason': f'Device has {current_connections}/{connection_limit} connections ({ttl_classification} TTL)'
    }

def register_connection(mac_address, ip_address, session_id, ttl_classification='unknown', user_agent=None):
    """
    Register a new connection session
    """
    connection, created = models.ConnectionTracker.objects.get_or_create(
        Device_MAC=mac_address,
        Session_ID=session_id,
        defaults={
            'Connection_IP': ip_address,
            'TTL_Classification': ttl_classification,
            'User_Agent': user_agent,
            'Is_Active': True
        }
    )
    
    if not created:
        # Update existing connection
        connection.Connection_IP = ip_address
        connection.TTL_Classification = ttl_classification
        connection.User_Agent = user_agent
        connection.Is_Active = True
        connection.save()
    
    return connection

def apply_ttl_firewall_rule(mac_address, ttl_value=1, duration_hours=2):
    """
    Apply iptables TTL mangle rule for a specific device (MikroTik-style)
    This sets TTL to 1 which prevents internet sharing completely
    """
    try:
        # Check if rule already exists
        existing_rule = models.TTLFirewallRule.objects.filter(
            Device_MAC=mac_address,
            Rule_Type='mangle_ttl',
            Rule_Status='active'
        ).first()
        
        if existing_rule:
            # Update expiration time
            existing_rule.Expires_At = timezone.now() + timezone.timedelta(hours=duration_hours)
            existing_rule.save()
            return existing_rule
        
        # Create new TTL rule
        expires_at = timezone.now() + timezone.timedelta(hours=duration_hours)
        
        ttl_rule = models.TTLFirewallRule(
            Device_MAC=mac_address,
            Rule_Type='mangle_ttl',
            TTL_Value=ttl_value,
            Expires_At=expires_at,
            Rule_Command='',  # Will be set below
            Violation_Count=0
        )
        
        # Generate iptables command  
        iptables_cmd = ttl_rule.get_iptables_command()
        ttl_rule.Rule_Command = ' '.join(iptables_cmd)
        
        # Apply the iptables rule safely
        from .utils.security import safe_iptables_command
        result = safe_iptables_command(iptables_cmd[1:])  # Remove 'iptables' from command
        
        if result.returncode == 0:
            ttl_rule.Rule_Status = 'active'
            ttl_rule.save()
            print(f"[TTL] Applied TTL={ttl_value} rule for {mac_address}")
            return ttl_rule
        else:
            ttl_rule.Rule_Status = 'error'
            ttl_rule.Admin_Notes = f"iptables error: {result.stderr}"
            ttl_rule.save()
            print(f"[TTL] Failed to apply TTL rule for {mac_address}: {result.stderr}")
            return None
            
    except Exception as e:
        print(f"[TTL] Error applying TTL rule for {mac_address}: {e}")
        return None

def remove_ttl_firewall_rule(mac_address):
    """
    Remove iptables TTL mangle rule for a specific device
    """
    try:
        # Find active rule
        ttl_rule = models.TTLFirewallRule.objects.filter(
            Device_MAC=mac_address,
            Rule_Type='mangle_ttl',
            Rule_Status='active'
        ).first()
        
        if not ttl_rule:
            return True  # No rule to remove
        
        # Generate delete command
        delete_cmd = ttl_rule.get_iptables_delete_command()
        
        # Remove the iptables rule safely
        from .utils.security import safe_iptables_command
        result = safe_iptables_command(delete_cmd[1:])  # Remove 'iptables' from command
        
        # Update rule status regardless of iptables result (rule might not exist)
        ttl_rule.Rule_Status = 'disabled'
        ttl_rule.save()
        
        if result.returncode == 0:
            print(f"[TTL] Removed TTL rule for {mac_address}")
            return True
        else:
            print(f"[TTL] iptables delete warning for {mac_address}: {result.stderr}")
            return True  # Still count as success since rule is disabled in DB
            
    except Exception as e:
        print(f"[TTL] Error removing TTL rule for {mac_address}: {e}")
        return False

def check_ttl_modification_needed(mac_address, ttl_analysis):
    """
    Check if TTL modification should be applied based on violation count
    """
    try:
        security_settings = models.SecuritySettings.objects.get(pk=1)
    except models.SecuritySettings.DoesNotExist:
        return False
    
    if not security_settings.Enable_TTL_Modification:
        return False
    
    # Count recent violations
    recent_violations = models.TrafficMonitor.objects.filter(
        Client_MAC=mac_address,
        Is_Suspicious=True,
        Timestamp__gte=timezone.now() - timezone.timedelta(hours=24)
    ).count()
    
    return recent_violations >= security_settings.TTL_Modification_After_Violations

def get_ttl_rule_status(mac_address):
    """
    Get current TTL modification status for a device
    """
    try:
        ttl_rule = models.TTLFirewallRule.objects.filter(
            Device_MAC=mac_address,
            Rule_Type='mangle_ttl',
            Rule_Status='active'
        ).first()
        
        if ttl_rule:
            if ttl_rule.is_expired():
                # Rule expired, clean it up
                remove_ttl_firewall_rule(mac_address)
                return None
            
            return {
                'has_ttl_rule': True,
                'ttl_value': ttl_rule.TTL_Value,
                'expires_at': ttl_rule.Expires_At,
                'created_at': ttl_rule.Created_At,
                'violation_count': ttl_rule.Violation_Count
            }
        else:
            return {
                'has_ttl_rule': False
            }
            
    except Exception as e:
        print(f"[TTL] Error checking TTL rule status for {mac_address}: {e}")
        return {'has_ttl_rule': False}

def extract_browser_fingerprint(request):
    """
    Extract browser fingerprinting data from HTTP request
    """
    fingerprint_data = {}
    
    # Basic browser information
    fingerprint_data['user_agent'] = request.META.get('HTTP_USER_AGENT', '')
    fingerprint_data['accept_language'] = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
    fingerprint_data['accept_encoding'] = request.META.get('HTTP_ACCEPT_ENCODING', '')
    
    # Try to extract additional data from request headers
    fingerprint_data['dnt'] = request.META.get('HTTP_DNT', '')  # Do Not Track
    fingerprint_data['connection'] = request.META.get('HTTP_CONNECTION', '')
    
    # Parse User-Agent for platform detection
    user_agent = fingerprint_data['user_agent'].lower()
    if 'windows' in user_agent:
        fingerprint_data['platform'] = 'Windows'
    elif 'mac os' in user_agent or 'macos' in user_agent:
        fingerprint_data['platform'] = 'macOS'
    elif 'android' in user_agent:
        fingerprint_data['platform'] = 'Android'
    elif 'iphone' in user_agent or 'ipad' in user_agent:
        fingerprint_data['platform'] = 'iOS'
    elif 'linux' in user_agent:
        fingerprint_data['platform'] = 'Linux'
    else:
        fingerprint_data['platform'] = 'Unknown'
    
    # Extract language preference
    accept_lang = fingerprint_data['accept_language']
    if accept_lang:
        # Take first language preference
        fingerprint_data['language'] = accept_lang.split(',')[0].split(';')[0].strip()
    
    return fingerprint_data

def get_client_side_fingerprint(request):
    """
    Get additional fingerprinting data that requires JavaScript
    This will be populated via AJAX calls from the frontend
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
            return {
                'screen_resolution': data.get('screen_resolution'),
                'timezone_offset': data.get('timezone_offset'),
                'screen_color_depth': data.get('screen_color_depth'),
                'available_fonts': data.get('available_fonts', []),
                'canvas_fingerprint': data.get('canvas_fingerprint'),
                'webgl_fingerprint': data.get('webgl_fingerprint'),
            }
        except (json.JSONDecodeError, KeyError):
            pass
    
    return {}

def detect_mac_randomization(mac_address, device_fingerprint=None):
    """
    Detect if a MAC address is randomized
    """
    analysis = {
        'is_randomized': False,
        'confidence': 0.0,
        'indicators': [],
        'mac_type': 'unknown'
    }
    
    if not mac_address:
        return analysis
    
    # Check for locally administered address (randomized)
    try:
        # Convert first octet to binary and check local bit (second least significant bit)
        first_octet = int(mac_address.split(':')[0], 16)
        local_bit = (first_octet >> 1) & 1
        
        if local_bit == 1:
            analysis['is_randomized'] = True
            analysis['confidence'] += 0.8
            analysis['indicators'].append('Local bit set in MAC address')
            analysis['mac_type'] = 'locally_administered'
        else:
            analysis['mac_type'] = 'universally_administered'
    except (ValueError, IndexError):
        analysis['indicators'].append('Invalid MAC address format')
        return analysis
    
    # Check for common randomization patterns
    mac_upper = mac_address.upper()
    
    # iOS randomization patterns
    if mac_upper.startswith(('02:', '06:', '0A:', '0E:')):
        analysis['is_randomized'] = True
        analysis['confidence'] += 0.6
        analysis['indicators'].append('iOS randomization pattern detected')
    
    # Android randomization patterns
    if mac_upper.startswith(('DA:', 'DE:')):
        analysis['confidence'] += 0.5
        analysis['indicators'].append('Android randomization pattern detected')
    
    # Check against device fingerprint for MAC history
    if device_fingerprint:
        if len(device_fingerprint.Known_MACs) > 1:
            analysis['confidence'] += 0.7
            analysis['indicators'].append(f'Device has used {len(device_fingerprint.Known_MACs)} different MACs')
        
        if device_fingerprint.MAC_Randomization_Detected:
            analysis['confidence'] += 0.5
            analysis['indicators'].append('Previously detected MAC randomization')
    
    # Determine final randomization status
    analysis['is_randomized'] = analysis['confidence'] >= 0.5
    
    return analysis

def get_or_create_device_fingerprint(mac_address, request):
    """
    Get or create device fingerprint, handling MAC randomization
    """
    # Extract browser fingerprint
    browser_fp = extract_browser_fingerprint(request)
    
    # Try to find existing device by fingerprint
    device, created = models.DeviceFingerprint.find_or_create_device(browser_fp, mac_address)
    
    # Analyze MAC randomization
    mac_analysis = detect_mac_randomization(mac_address, device)
    
    # Update device with MAC analysis
    if mac_analysis['is_randomized']:
        device.MAC_Randomization_Detected = True
        device.save()
    
    return {
        'device': device,
        'created': created,
        'mac_analysis': mac_analysis,
        'fingerprint_data': browser_fp
    }

def enhanced_ttl_analysis_with_fingerprinting(mac_address, ttl_value, request=None):
    """
    Enhanced TTL analysis that considers device fingerprinting
    """
    # Get device fingerprint
    fingerprint_result = get_or_create_device_fingerprint(mac_address, request) if request else None
    
    # Run standard TTL analysis
    ttl_analysis = analyze_ttl_for_sharing(mac_address, ttl_value, request)
    
    if fingerprint_result:
        device = fingerprint_result['device']
        mac_analysis = fingerprint_result['mac_analysis']
        
        # Use device fingerprint for persistent violation tracking
        device_violations = device.get_current_violations_24h()
        
        # Override MAC-based violation count with device-based count
        ttl_analysis['device_violations'] = device_violations
        ttl_analysis['fingerprint_id'] = device.Device_ID[:8]
        ttl_analysis['mac_randomization'] = mac_analysis
        ttl_analysis['device_summary'] = device.get_device_summary()
        
        # Record violation if suspicious
        if ttl_analysis.get('is_suspicious'):
            device.record_violation('ttl')
            
            # Use device violations for enforcement decisions
            security_settings = models.SecuritySettings.objects.get(pk=1)
            
            # Check TTL modification based on device violations (not MAC violations)
            if (device_violations >= security_settings.TTL_Modification_After_Violations and 
                security_settings.Enable_TTL_Modification):
                
                ttl_rule = apply_ttl_firewall_rule(
                    mac_address,  # Still apply to current MAC
                    ttl_value=security_settings.Modified_TTL_Value,
                    duration_hours=int(security_settings.TTL_Rule_Duration.total_seconds() / 3600)
                )
                
                if ttl_rule:
                    # Update TTL rule with device fingerprint reference
                    ttl_rule.Violation_Count = device_violations
                    ttl_rule.Admin_Notes = f'Applied to device {device.Device_ID[:8]} with {device_violations} violations'
                    ttl_rule.save()
                    
                    ttl_analysis['ttl_rule_applied'] = True
                    ttl_analysis['ttl_rule_value'] = ttl_rule.TTL_Value
                    ttl_analysis['ttl_rule_expires'] = ttl_rule.Expires_At
                    ttl_analysis['enforcement_level'] = 'network_level_fingerprinted'
    
    return ttl_analysis

def is_device_blocked(mac_address):
    """
    Check if a device is currently blocked
    Also handles automatic unblocking of expired blocks
    """
    try:
        blocked_device = models.BlockedDevices.objects.get(MAC_Address=mac_address, Is_Active=True)
        
        # Check if block has expired
        if blocked_device.unblock_if_expired():
            return False
        
        return True
    except models.BlockedDevices.DoesNotExist:
        return False

# Phase 3: Traffic Analysis & Intelligent QoS Functions

def analyze_traffic_packet(packet_data):
    """
    Analyze individual network packet for protocol classification
    """
    import re
    
    protocol_patterns = {
        'p2p': [
            r'BitTorrent protocol',
            r'announce.*torrent',
            r'\.torrent',
            r'peer_id=',
            r'info_hash='
        ],
        'streaming': [
            r'youtube\.com',
            r'netflix\.com',
            r'video/',
            r'\.mp4',
            r'\.mkv',
            r'\.avi',
            r'streaming'
        ],
        'gaming': [
            r'steam',
            r'battle\.net',
            r'riot.*games',
            r'epicgames',
            r'game.*server'
        ],
        'social': [
            r'facebook\.com',
            r'twitter\.com',
            r'instagram\.com',
            r'tiktok\.com',
            r'snapchat'
        ],
        'messaging': [
            r'whatsapp',
            r'telegram',
            r'discord',
            r'messenger',
            r'signal'
        ]
    }
    
    # Default to HTTP if no specific pattern matches
    detected_protocol = 'http'
    
    # Check packet content against patterns
    packet_content = str(packet_data).lower()
    
    for protocol, patterns in protocol_patterns.items():
        for pattern in patterns:
            if re.search(pattern, packet_content):
                detected_protocol = protocol
                break
        if detected_protocol != 'http':
            break
    
    return detected_protocol

def record_traffic_analysis(mac_address, device_fingerprint, protocol_type, bytes_up, bytes_down, packets_up=1, packets_down=1, source_ip=None, dest_ip=None, source_port=None, dest_port=None):
    """
    Record traffic analysis data for a device
    """
    try:
        bandwidth_mb = (bytes_up + bytes_down) / (1024 * 1024)  # Convert to MB
        
        # Check for suspicious patterns
        is_suspicious = False
        suspicion_reason = None
        
        # P2P traffic detection
        if protocol_type == 'p2p':
            is_suspicious = True
            suspicion_reason = "P2P/Torrenting traffic detected"
        
        # Excessive bandwidth usage
        if bandwidth_mb > 100:  # More than 100MB in single analysis
            is_suspicious = True
            suspicion_reason = f"Excessive bandwidth usage: {bandwidth_mb:.2f}MB"
        
        # High upload ratio (possible sharing)
        if bytes_up > 0 and bytes_down > 0:
            upload_ratio = bytes_up / bytes_down
            if upload_ratio > 0.5:  # Upload > 50% of download
                is_suspicious = True
                suspicion_reason = f"High upload ratio: {upload_ratio:.2f} (possible sharing)"
        
        # Record traffic analysis
        traffic_analysis = models.TrafficAnalysis.objects.create(
            Device_MAC=mac_address,
            Device_Fingerprint=device_fingerprint,
            Protocol_Type=protocol_type,
            Bytes_Up=bytes_up,
            Bytes_Down=bytes_down,
            Packets_Up=packets_up,
            Packets_Down=packets_down,
            Source_IP=source_ip,
            Destination_IP=dest_ip,
            Source_Port=source_port,
            Destination_Port=dest_port,
            Is_Suspicious=is_suspicious,
            Suspicion_Reason=suspicion_reason,
            Bandwidth_Usage_MB=bandwidth_mb
        )
        
        # Update device behavior profile
        if device_fingerprint:
            update_device_behavior_profile(device_fingerprint, traffic_analysis)
        
        return traffic_analysis
        
    except Exception as e:
        print(f"[TRAFFIC] Error recording traffic analysis for {mac_address}: {e}")
        return None

def update_device_behavior_profile(device_fingerprint, traffic_analysis):
    """
    Update device behavioral profile based on traffic analysis
    """
    try:
        # Get or create behavior profile
        behavior_profile, created = models.DeviceBehaviorProfile.objects.get_or_create(
            Device_Fingerprint=device_fingerprint,
            defaults={
                'Total_Data_Used_MB': 0.0,
                'Peak_Bandwidth_Usage': 0.0,
                'Trust_Score': 50.0
            }
        )
        
        # Update data usage
        behavior_profile.Total_Data_Used_MB += traffic_analysis.Bandwidth_Usage_MB
        
        # Update peak bandwidth
        current_bandwidth = traffic_analysis.Bandwidth_Usage_MB
        if current_bandwidth > behavior_profile.Peak_Bandwidth_Usage:
            behavior_profile.Peak_Bandwidth_Usage = current_bandwidth
        
        # Update protocol preferences
        if not behavior_profile.Favorite_Protocol:
            behavior_profile.Favorite_Protocol = traffic_analysis.Protocol_Type
        else:
            # Calculate most used protocol (simplified)
            protocol_counts = {}
            recent_traffic = models.TrafficAnalysis.objects.filter(
                Device_Fingerprint=device_fingerprint,
                Timestamp__gte=timezone.now() - timezone.timedelta(days=7)
            )
            
            for traffic in recent_traffic:
                protocol_counts[traffic.Protocol_Type] = protocol_counts.get(traffic.Protocol_Type, 0) + 1
            
            if protocol_counts:
                behavior_profile.Favorite_Protocol = max(protocol_counts, key=protocol_counts.get)
        
        # Calculate protocol usage percentages
        total_traffic = models.TrafficAnalysis.objects.filter(
            Device_Fingerprint=device_fingerprint
        ).count()
        
        if total_traffic > 0:
            p2p_count = models.TrafficAnalysis.objects.filter(
                Device_Fingerprint=device_fingerprint,
                Protocol_Type='p2p'
            ).count()
            
            streaming_count = models.TrafficAnalysis.objects.filter(
                Device_Fingerprint=device_fingerprint,
                Protocol_Type='streaming'
            ).count()
            
            behavior_profile.P2P_Usage_Percentage = (p2p_count / total_traffic) * 100
            behavior_profile.Streaming_Usage_Percentage = (streaming_count / total_traffic) * 100
        
        # Update violation score if suspicious
        if traffic_analysis.Is_Suspicious:
            behavior_profile.Violation_Score += 1.0
            behavior_profile.Last_Violation_Date = timezone.now()
        
        # Update most active hour
        current_hour = timezone.now().hour
        behavior_profile.Most_Active_Hour = current_hour
        
        behavior_profile.save()
        
        # Recalculate trust score
        behavior_profile.calculate_trust_score()
        behavior_profile.update_trust_level()
        
        # Check if adaptive QoS rules should be applied
        check_and_apply_adaptive_qos(device_fingerprint, behavior_profile)
        
        return behavior_profile
        
    except Exception as e:
        print(f"[BEHAVIOR] Error updating behavior profile: {e}")
        return None

def check_and_apply_adaptive_qos(device_fingerprint, behavior_profile):
    """
    Check if adaptive QoS rules should be applied based on device behavior
    """
    try:
        mac_address = device_fingerprint.Current_MAC
        
        # Remove expired rules first
        expired_rules = models.AdaptiveQoSRule.objects.filter(
            Device_MAC=mac_address,
            Is_Active=True
        )
        for rule in expired_rules:
            if rule.is_expired():
                rule.Is_Active = False
                rule.save()
        
        # Apply rules based on trust level
        if behavior_profile.Trust_Level == 'trusted':
            # Trusted devices get high priority
            apply_qos_rule(
                mac_address=mac_address,
                device_fingerprint=device_fingerprint,
                rule_name="Trusted Device Priority",
                qos_action='priority_high',
                trigger_condition='{"trust_level": "trusted"}',
                duration_hours=24
            )
            
        elif behavior_profile.Trust_Level == 'suspicious':
            # Suspicious devices get throttled
            apply_qos_rule(
                mac_address=mac_address,
                device_fingerprint=device_fingerprint,
                rule_name="Suspicious Device Throttling",
                qos_action='throttle_light',
                bandwidth_limit_down=10.0,  # 10 Mbps limit
                bandwidth_limit_up=2.0,     # 2 Mbps upload limit
                trigger_condition='{"trust_level": "suspicious"}',
                duration_hours=2
            )
            
        elif behavior_profile.Trust_Level == 'abusive':
            # Abusive devices get heavy throttling
            apply_qos_rule(
                mac_address=mac_address,
                device_fingerprint=device_fingerprint,
                rule_name="Abusive Device Heavy Throttling",
                qos_action='throttle_heavy',
                bandwidth_limit_down=2.0,   # 2 Mbps limit
                bandwidth_limit_up=0.5,     # 0.5 Mbps upload limit
                trigger_condition='{"trust_level": "abusive"}',
                duration_hours=4
            )
        
        # P2P specific throttling
        if behavior_profile.P2P_Usage_Percentage > 30:  # More than 30% P2P usage
            apply_qos_rule(
                mac_address=mac_address,
                device_fingerprint=device_fingerprint,
                rule_name="P2P Traffic Throttling",
                qos_action='throttle_medium',
                protocol_filter='p2p',
                trigger_condition='{"p2p_usage_percent": ">30"}',
                duration_hours=1
            )
        
    except Exception as e:
        print(f"[QOS] Error checking adaptive QoS for {device_fingerprint.Device_ID}: {e}")

def apply_qos_rule(mac_address, device_fingerprint, rule_name, qos_action, bandwidth_limit_down=None, bandwidth_limit_up=None, protocol_filter=None, trigger_condition='{}', duration_hours=1):
    """
    Apply adaptive QoS rule to a device
    """
    try:
        # Check if similar rule already exists
        existing_rule = models.AdaptiveQoSRule.objects.filter(
            Device_MAC=mac_address,
            Rule_Name=rule_name,
            Is_Active=True
        ).first()
        
        if existing_rule:
            # Update expiration time
            existing_rule.Expires_At = timezone.now() + timezone.timedelta(hours=duration_hours)
            existing_rule.save()
            return existing_rule
        
        # Create new QoS rule
        expires_at = timezone.now() + timezone.timedelta(hours=duration_hours)
        
        qos_rule = models.AdaptiveQoSRule.objects.create(
            Device_MAC=mac_address,
            Device_Fingerprint=device_fingerprint,
            Rule_Name=rule_name,
            QoS_Action=qos_action,
            Bandwidth_Limit_Down=bandwidth_limit_down,
            Bandwidth_Limit_Up=bandwidth_limit_up,
            Trigger_Condition=trigger_condition,
            Protocol_Filter=protocol_filter,
            Auto_Created=True,
            Expires_At=expires_at
        )
        
        # Apply the rule (implementation would depend on network setup)
        if qos_rule.apply_rule():
            print(f"[QOS] Applied {rule_name} to {mac_address}: {qos_action}")
        
        return qos_rule
        
    except Exception as e:
        print(f"[QOS] Error applying QoS rule {rule_name} to {mac_address}: {e}")
        return None

def generate_network_intelligence():
    """
    Generate network-wide intelligence metrics
    """
    try:
        # Count active devices
        active_devices = models.ConnectionTracker.objects.filter(
            Is_Active=True,
            Last_Activity__gte=timezone.now() - timezone.timedelta(minutes=30)
        ).values('Device_MAC').distinct().count()
        
        # Count suspicious devices
        suspicious_devices = models.DeviceBehaviorProfile.objects.filter(
            Trust_Level__in=['suspicious', 'abusive']
        ).count()
        
        # Count recent TTL violations
        ttl_violations = models.TrafficMonitor.objects.filter(
            Is_Suspicious=True,
            Timestamp__gte=timezone.now() - timezone.timedelta(hours=1)
        ).count()
        
        # Count MAC randomization detected
        mac_randomization_count = models.DeviceFingerprint.objects.filter(
            MAC_Randomization_Detected=True
        ).count()
        
        # Count active QoS rules
        active_qos_rules = models.AdaptiveQoSRule.objects.filter(
            Is_Active=True
        ).count()
        
        # Calculate protocol distribution
        total_traffic = models.TrafficAnalysis.objects.filter(
            Timestamp__gte=timezone.now() - timezone.timedelta(hours=24)
        ).count()
        
        protocol_percentages = {}
        if total_traffic > 0:
            for protocol, _ in models.TrafficAnalysis.PROTOCOL_CHOICES:
                count = models.TrafficAnalysis.objects.filter(
                    Protocol_Type=protocol,
                    Timestamp__gte=timezone.now() - timezone.timedelta(hours=24)
                ).count()
                protocol_percentages[protocol] = (count / total_traffic) * 100
        
        # Calculate revenue metrics (simplified)
        active_clients = models.Clients.objects.filter(
            Expire_On__isnull=False
        ).count()
        
        # Create network intelligence record
        intelligence = models.NetworkIntelligence.objects.create(
            Total_Active_Devices=active_devices,
            Suspicious_Devices_Count=suspicious_devices,
            TTL_Violations_Last_Hour=ttl_violations,
            MAC_Randomization_Detected_Count=mac_randomization_count,
            Active_QoS_Rules=active_qos_rules,
            Peak_Concurrent_Users=active_clients,
            HTTP_Traffic_Percent=protocol_percentages.get('http', 0),
            P2P_Traffic_Percent=protocol_percentages.get('p2p', 0),
            Streaming_Traffic_Percent=protocol_percentages.get('streaming', 0),
            Gaming_Traffic_Percent=protocol_percentages.get('gaming', 0),
            Other_Traffic_Percent=protocol_percentages.get('other', 0)
        )
        
        return intelligence
        
    except Exception as e:
        print(f"[INTELLIGENCE] Error generating network intelligence: {e}")
        return None

def api_response(code):
    response = dict()

    if code == 200:
        response['code'] = code
        response['status'] = 'Success'
        response['description'] = ''

    if code == 300:
        response['code'] = code
        response['status'] = 'Error'
        response['description'] = 'Pay error.'

    if code == 400:
        response['code'] = code
        response['status'] = 'Error'
        response['description'] = 'Pay error. Slot Not Found.'

    if code == 500:
        response['code'] = code
        response['status'] = 'Error'
        response['description'] = 'Session Timeout. <strong><a href="/app/portal">Click to refresh your browser.</a></strong>'

    if code == 600:
        response['code'] = code
        response['status'] = 'Error'
        response['description'] = 'Someone is still paying. Try again.'

    if code == 700:
        response['code'] = code
        response['status'] = 'Error'
        response['description'] = 'Invalid action.'

    if code == 800:
        response['code'] = code
        response['status'] = 'Error'
        response['description'] = 'Client not found.'

    if code == 900:
        response['code'] = code
        response['status'] = 'Error'
        response['description'] = 'Unknown coin inserted.'

    if code == 110:
        response['code'] = code
        response['status'] = 'Error'
        response['description'] = 'Invalid / Used / Expired voucher code.'

    return  response


def getDeviceInfo(request):
        info = dict()
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')

        # Try multiple methods to get MAC address
        mac = None
        
        # Method 1: Try getmac by IP
        try:
            mac = getmac.get_mac_address(ip=ip)
        except:
            pass
            
        # Method 2: Try getmac by interface (for local development)
        if not mac and ip in ['127.0.0.1', 'localhost']:
            try:
                mac = getmac.get_mac_address()  # Get default interface MAC
            except:
                pass
        
        # Method 3: Check ARP table (Linux/Windows)
        if not mac and ip != '127.0.0.1':
            try:
                from .utils.security import safe_arp_command
                import re
                result = safe_arp_command(ip)
                if result and result.returncode == 0:
                    # Parse MAC from ARP output
                    mac_match = re.search(r'([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}', result.stdout)
                    if mac_match:
                        mac = mac_match.group().replace('-', ':').lower()
            except:
                pass
        
        # Fallback: Use session-based MAC for development
        if not mac:
            session_key = request.session.session_key
            if session_key:
                # Generate consistent MAC from session for development
                import hashlib
                hash_object = hashlib.md5(session_key.encode())
                hex_dig = hash_object.hexdigest()
                mac = ':'.join([hex_dig[i:i+2] for i in range(0, 12, 2)])
            else:
                mac = '00:00:00:00:00:00'  # Final fallback
        
        info['ip'] = ip
        info['mac'] = mac
        return info


@method_decorator(ensure_csrf_cookie, name='dispatch')
@method_decorator(portal_rate_limit(), name='dispatch')
class Portal(View):
    template_name = 'captive.html'
    
    def getClientInfo(self, ip, mac, request=None):
        info = dict()

        # Check if device is blocked first
        if is_device_blocked(mac):
            # Return blocked status
            blocked_device = models.BlockedDevices.objects.get(MAC_Address=mac, Is_Active=True)
            info['ip'] = ip
            info['mac'] = mac
            info['whitelisted'] = False
            info['status'] = 'Blocked'
            info['time_left'] = 0
            info['total_coins'] = 0
            info['vouchers'] = None
            info['appNotification_ID'] = ''
            info['block_reason'] = blocked_device.get_Block_Reason_display()
            info['blocked_until'] = blocked_device.Auto_Unblock_After
            return info

        # Check connection limits and TTL analysis for non-whitelisted devices
        ttl_analysis = None
        connection_status = None
        if not models.Whitelist.objects.filter(MAC_Address=mac).exists():
            # Check connection limits
            connection_status = check_connection_limit(mac, self.request if hasattr(self, 'request') else None)
            
            # Perform enhanced TTL analysis with device fingerprinting
            ttl_value = get_ttl_from_ip(ip)
            if ttl_value:
                ttl_analysis = enhanced_ttl_analysis_with_fingerprinting(mac, ttl_value, request)
                
                # If device was just auto-blocked due to TTL violations (only if blocking is enabled)
                if ttl_analysis.get('auto_blocked'):
                    info['ip'] = ip
                    info['mac'] = mac
                    info['whitelisted'] = False
                    info['status'] = 'Blocked'
                    info['time_left'] = 0
                    info['total_coins'] = 0
                    info['vouchers'] = None
                    info['appNotification_ID'] = ''
                    info['block_reason'] = 'Internet Sharing Detected (TTL)'
                    info['ttl_analysis'] = ttl_analysis
                    return info

        if models.Whitelist.objects.filter(MAC_Address=mac).exists():
            whitelisted_flg = True
            status = 'Connected'
            time_left = timedelta(0)
            total_coins = 0
            notif_id = ''
            vouchers = None

        else:
            whitelisted_flg = False
            client, created = models.Clients.objects.get_or_create(MAC_Address=mac, defaults={'IP_Address': ip})
            if not created:
                if client.IP_Address != ip:
                    client.IP_Address = ip
                    client.save()

            try:
                coin_queue = models.CoinQueue.objects.get(Client=mac)
                total_coins = coin_queue.Total_Coins
            except ObjectDoesNotExist:
                total_coins = 0

            try:
                vouchers = models.Vouchers.objects.filter(Voucher_client=mac, Voucher_status='Not Used')
            except ObjectDoesNotExist:
                vouchers = None

            status = client.Connection_Status

            if status == 'Connected':
                time_left = client.running_time

            elif status == 'Disconnected':
                time_left = timedelta(0)

            elif status == 'Paused':
                time_left = client.Time_Left

            notif_id = client.Notification_ID
            
            # Add validity/expiration information
            if client.Validity_Expires_On:
                validity_expires_on = client.Validity_Expires_On
                validity_expires_in = validity_expires_on - timezone.now()
                
                # Determine color based on time remaining
                if validity_expires_in.total_seconds() < 86400:  # Less than 24 hours
                    validity_color = 'red'
                elif validity_expires_in.total_seconds() < 604800:  # Less than 7 days
                    validity_color = 'orange'
                else:
                    validity_color = 'green'
                
                info['validity_expires_on'] = validity_expires_on
                info['validity_expires_in'] = validity_expires_in
                info['validity_color'] = validity_color

        info['ip'] = ip
        info['mac'] = mac
        info['whitelisted'] = whitelisted_flg
        info['status'] = status
        info['time_left'] = int(timedelta.total_seconds(time_left))
        info['total_coins'] = total_coins
        info['vouchers'] = vouchers
        info['appNotification_ID'] = notif_id
        
        # Add TTL analysis data if available
        if ttl_analysis:
            info['ttl_analysis'] = ttl_analysis
        
        # Add connection status information
        if connection_status:
            info['connection_status'] = connection_status
        
        # Add TTL rule status information
        ttl_rule_status = get_ttl_rule_status(mac)
        if ttl_rule_status:
            info['ttl_rule_status'] = ttl_rule_status
        
        # Add device fingerprint information if request is available
        if request and not models.Whitelist.objects.filter(MAC_Address=mac).exists():
            try:
                fingerprint_result = get_or_create_device_fingerprint(mac, request)
                device = fingerprint_result['device']
                
                device_fingerprint_info = {
                    'device_summary': device.get_device_summary(),
                    'mac_randomization_detected': device.MAC_Randomization_Detected,
                    'known_mac_count': len(device.Known_MACs),
                    'total_violations': device.Total_TTL_Violations,
                    'platform': device.Platform,
                    'fingerprint_id': device.Device_ID[:8],
                    'device_status': device.Device_Status
                }
                
                info['device_fingerprint_info'] = device_fingerprint_info
            except Exception as e:
                print(f"[FINGERPRINT] Error getting device fingerprint for {mac}: {e}")

        return info

    def getSettings(self):
        info = dict()
        settings = models.Settings.objects.get(pk=1)

        rate_type = settings.Rate_Type
        if rate_type == 'auto':
            base_rate = settings.Base_Value
            rates = models.Rates.objects.annotate(auto_rate=F('Denom')*int(base_rate.total_seconds())).values('Denom', 'auto_rate')
            info['rates'] = rates
        else:
            info['rates'] = models.Rates.objects.all()

        info['push_notif'] = None

        info['rate_type'] = rate_type
        info['base_value'] = settings.Base_Value if rate_type == 'auto' else None
        info['hotspot'] = settings.Hotspot_Name
        # Get slot timeout from Portal Settings
        portal_settings = models.PortalSettings.objects.first()
        info['slot_timeout'] = portal_settings.slot_timeout if portal_settings else 300
        info['background'] = settings.BG_Image
        info['voucher_flg'] = settings.Vouchers_Flg
        info['pause_resume_flg'] = settings.Pause_Resume_Flg
        info['pause_resume_enable_time'] = 0 if not settings.Disable_Pause_Time else int(timedelta.total_seconds(settings.Disable_Pause_Time))
        info['redir_url'] = settings.Redir_Url
        info['inactive_timeout'] = settings.Inactive_Timeout
        info['internet_connected'] = check_internet_connectivity()
        info['banner_images'] = get_available_banner_images()
        
        # Add Portal-specific settings from new models
        portal_settings = get_portal_settings()
        portal_audio = get_portal_audio_files()
        portal_texts = get_portal_texts()
        
        # Merge portal settings into info
        info.update(portal_settings)
        info['portal_audio'] = portal_audio
        info['portal_texts'] = portal_texts
        
        # Override some settings with portal settings if available
        if portal_settings.get('redirect_url'):
            info['redir_url'] = portal_settings['redirect_url']
        if portal_settings.get('hotspot_name'):
            info['hotspot'] = portal_settings['hotspot_name']
        
        # Map Portal Settings to legacy template variables for compatibility
        if portal_settings.get('enable_pause_resume') is not None:
            info['pause_resume_flg'] = 1 if portal_settings['enable_pause_resume'] else 0
        if portal_settings.get('enable_vouchers') is not None:
            info['voucher_flg'] = portal_settings['enable_vouchers']
        
        # Use Portal Settings pause_resume_min_time instead of Settings Disable_Pause_Time
        portal_settings_model = models.PortalSettings.objects.first()
        if portal_settings_model and portal_settings_model.pause_resume_min_time:
            info['pause_resume_enable_time'] = int(timedelta.total_seconds(portal_settings_model.pause_resume_min_time))
        else:
            info['pause_resume_enable_time'] = 0

        return info

    def get(self, request, template_name=template_name):
        try:
            device_info = getDeviceInfo(request)
            ip = device_info['ip']
            mac = device_info['mac']
            info = self.getClientInfo(ip, mac, request)
            settings = self.getSettings()

            context = {**settings, **info}
            return render(request, template_name, context=context)
        except Exception as e:
            # Fallback with basic context for debugging
            context = {
                'ip': '127.0.0.1',
                'mac': '00:00:00:00:00:00',
                'status': 'Connected',
                'time_left': 0,
                'total_coins': 0,
                'whitelisted': False,
                'error_debug': str(e)
            }
            return render(request, template_name, context=context)

    def post(self, request):
        data = json.loads(request.body.decode("utf-8"))

        action = data.get('action')
        mac = data.get('mac')

        resp = api_response(700)

        if action == 'update_notif_id':
            notif_id = data.get('notifId', None)
            client = models.Clients.objects.get(MAC_Address=mac)
            if client.Notification_ID != notif_id and notif_id:
                client.Notification_ID = notif_id
                client.save()
                resp = api_response(200)

        return JsonResponse(resp, safe=False)


class Slot(View):

    def get(self, request):
        """Handle coin status checking from portal"""
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            try:
                device_info = getDeviceInfo(request)
                mac = device_info['mac']
                portal_settings = models.PortalSettings.objects.first()
                timeout = portal_settings.slot_timeout if portal_settings else 300
                
                # Check if this is a request to claim the slot (when opening insert coin modal)
                claim_slot = request.GET.get('claim', False)
                
                # Check coin slot availability
                slot_available = False
                slot_status = "busy"
                slot_claimed = False
                
                try:
                    slot_info = models.CoinSlot.objects.get(pk=1)
                    if slot_info.Client == mac:
                        # This client already has the slot
                        slot_available = True
                        slot_status = "active"
                    elif slot_info.Client is None or slot_info.Client == '':
                        # Slot is free
                        if claim_slot:
                            # Claim the slot for this client
                            slot_info.Client = mac
                            slot_info.Last_Updated = timezone.now()
                            slot_info.save()
                            slot_claimed = True
                            slot_status = "claimed"
                        slot_available = True
                        if not claim_slot:
                            slot_status = "available"
                    else:
                        # Check if current slot owner's time has expired
                        if slot_info.Last_Updated:
                            time_diff = timezone.now() - slot_info.Last_Updated
                            if time_diff.total_seconds() > timeout:
                                if claim_slot:
                                    # Claim the expired slot for this client
                                    slot_info.Client = mac
                                    slot_info.Last_Updated = timezone.now()
                                    slot_info.save()
                                    slot_claimed = True
                                    slot_status = "claimed"
                                slot_available = True
                                if not claim_slot:
                                    slot_status = "available"
                            else:
                                slot_available = False
                                slot_status = "busy"
                        else:
                            # No last updated time, consider it expired
                            if claim_slot:
                                slot_info.Client = mac
                                slot_info.Last_Updated = timezone.now()
                                slot_info.save()
                                slot_claimed = True
                                slot_status = "claimed"
                            slot_available = True
                            if not claim_slot:
                                slot_status = "available"
                                
                except models.CoinSlot.DoesNotExist:
                    # Create the coin slot record if it doesn't exist
                    if claim_slot:
                        slot_info = models.CoinSlot.objects.create(
                            pk=1,
                            Client=mac,
                            Last_Updated=timezone.now(),
                            Slot_Address='00:00:00:00:00:00'  # Default address
                        )
                        slot_claimed = True
                        slot_status = "claimed"
                    slot_available = True
                    if not claim_slot:
                        slot_status = "available"
                
                # Portal is now the timer authority - no keep-alive needed
                
                # Check if there's an active coin queue for this client
                total_coins = 0
                available_time = 0
                
                try:
                    coin_queue = models.CoinQueue.objects.get(Client=mac)
                    total_coins = coin_queue.Total_Coins or 0
                    available_time = coin_queue.Total_Time.total_seconds() / 60 if total_coins > 0 else 0
                except models.CoinQueue.DoesNotExist:
                    pass
                
                resp = {
                    'status_code': 200,
                    'Total_Coins': total_coins,
                    'Available_Time': available_time,
                    'Slot_Available': slot_available,
                    'Slot_Status': slot_status,
                    'Slot_Claimed': slot_claimed
                }
                
                return JsonResponse(resp, safe=False)
            except Exception as e:
                resp = {
                    'status_code': 500,
                    'description': 'Error checking coin status',
                    'error': str(e)
                }
                return JsonResponse(resp, safe=False)
        else:
            raise Http404("Page not found")

    def post(self, request):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            mac = request.POST.get('mac')

            try:
                portal_settings = models.PortalSettings.objects.first()
                timeout = portal_settings.slot_timeout if portal_settings else 300
                client = models.Clients.objects.get(MAC_Address=mac)

            except ObjectDoesNotExist as e:
                resp = api_response(500)

            else:
                try:
                    slot_info = models.CoinSlot.objects.get(pk=1, Client=mac)
                    # Portal is timer authority - no timestamp updates here
                    # slot_info.Last_Updated = timezone.now()
                    # slot_info.save()

                    # subprocess.run(['gpio', '-1', 'write', str(settings.Light_Pin), '1'])
                    resp = api_response(200)

                except ObjectDoesNotExist:
                    slot_info = models.CoinSlot.objects.get(pk=1)
                    time_diff = timedelta.total_seconds(timezone.now()-slot_info.Last_Updated)
                    if timedelta(seconds=time_diff).total_seconds() > timeout:
                        slot_info.Client = mac
                        # Portal handles timing - only set initial timestamp
                        slot_info.Last_Updated = timezone.now()
                        slot_info.save()

                        # subprocess.run(['gpio', '-1', 'write', str(settings.Light_Pin), '1'])
                        resp = api_response(200)
                    else:
                        resp = api_response(600)
                
            return JsonResponse(resp, safe=False)
        else:
            raise Http404("Page not found")

@method_decorator(csrf_protect, name='dispatch')
class SlotRelease(View):
    def post(self, request):
        """Release coin slot when client closes modal or times out"""
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            try:
                device_info = getDeviceInfo(request)
                mac = device_info['mac']
                
                # Release the slot if this client owns it
                try:
                    slot_info = models.CoinSlot.objects.get(pk=1, Client=mac)
                    slot_info.Client = None
                    slot_info.Last_Updated = None
                    slot_info.save()
                    
                    resp = {'status_code': 200, 'description': 'Slot released'}
                except models.CoinSlot.DoesNotExist:
                    resp = {'status_code': 200, 'description': 'No slot to release'}
                
                return JsonResponse(resp, safe=False)
            except Exception as e:
                resp = {'status_code': 500, 'description': 'Error releasing slot', 'error': str(e)}
                return JsonResponse(resp, safe=False)
        else:
            raise Http404("Page not found")

@method_decorator(csrf_protect, name='dispatch')
class SlotUpdate(View):
    def post(self, request):
        """Update coin slot timer from portal countdown"""
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            try:
                device_info = getDeviceInfo(request)
                mac = device_info['mac']
                
                # Get countdown status from portal
                data = json.loads(request.body.decode("utf-8"))
                remaining_seconds = data.get('remaining_seconds', 0)
                action = data.get('action', 'update')  # 'update' or 'expired'
                
                import logging
                logger = logging.getLogger('app')
                logger.debug(f"SlotUpdate: MAC={mac}, remaining_seconds={remaining_seconds}, action={action}")
                
                try:
                    slot_info = models.CoinSlot.objects.get(pk=1, Client=mac)
                    
                    if action == 'expired' or remaining_seconds <= 0:
                        # Portal countdown expired, release the slot
                        slot_info.Client = None
                        slot_info.Last_Updated = None
                        slot_info.save()
                        resp = {'status_code': 200, 'description': 'Slot expired and released'}
                    else:
                        # Update timestamp to reflect portal countdown
                        portal_settings = models.PortalSettings.objects.first()
                        timeout = portal_settings.slot_timeout if portal_settings else 300
                        elapsed_seconds = timeout - remaining_seconds
                        new_timestamp = timezone.now() - timezone.timedelta(seconds=elapsed_seconds)
                        
                        slot_info.Last_Updated = new_timestamp
                        slot_info.save()
                        resp = {'status_code': 200, 'description': 'Slot timer updated'}
                        
                except models.CoinSlot.DoesNotExist:
                    logger.warning(f"Slot not found for client {mac}")
                    resp = {'status_code': 404, 'description': 'Slot not found or not owned by this client'}
                
                return JsonResponse(resp, safe=False)
            except Exception as e:
                resp = {'status_code': 500, 'description': 'Error updating slot', 'error': str(e)}
                return JsonResponse(resp, safe=False)
        else:
            raise Http404("Page not found")

@method_decorator(csrf_protect, name='dispatch')
@method_decorator(payment_rate_limit(), name='dispatch')
@method_decorator(log_security_event('payment_access'), name='dispatch')
class Pay(View):
    template_name = 'pay.html'
    
    def get(self, request):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' and request.META['REMOTE_ADDR'] in local_ip:
            dev = models.Device.objects.get(pk=1)
            # Hardware fingerprinting removed for personal use
            dev.action = 0
            sync_time = dev.Sync_Time
            dev.save()

            settings = models.Settings.objects.values('Coinslot_Pin', 'Light_Pin', 'Slot_Timeout', 'Inactive_Timeout').get(pk=1)
            clients = models.Clients.objects.filter(Expire_On__isnull=False)
            for client in clients:
                time_diff = client.Expire_On - dev.Sync_Time
                if time_diff > timedelta(0):
                    client.Time_Left += time_diff
                    client.Expire_On = None
                    client.save()

            context = dict()
            context['device'] = {'Sync_Time': sync_time}
            context['settings'] = settings
            return JsonResponse(context, safe=False)
        else:
            # Handle regular browser requests
            try:
                settings = models.Settings.objects.get(pk=1)
                rates = models.Rates.objects.all()
                
                # Calculate display time for each rate
                rates_with_display = []
                for rate in rates:
                    rate_dict = {
                        'id': rate.id,
                        'Rate': rate.Denom,  # Denom is the price/rate
                        'Pulse': rate.Pulse,
                        'Minutes': rate.Minutes  # Minutes is the duration
                    }
                    
                    # Calculate display time
                    total_seconds = rate.Minutes.total_seconds()
                    if total_seconds >= 3600:
                        hours = total_seconds / 3600
                        if hours >= 2:
                            rate_dict['display_time'] = f"{hours:.1f} hours"
                        else:
                            rate_dict['display_time'] = f"{hours:.1f} hour"
                    else:
                        minutes = total_seconds / 60
                        rate_dict['display_time'] = f"{int(minutes)} minutes"
                    
                    rates_with_display.append(rate_dict)
                
                context = {
                    'settings': settings,
                    'rates': rates_with_display,
                    'hotspot_name': settings.Hotspot_Name
                }
                return render(request, self.template_name, context)
            except Exception as e:
                context = {
                    'error': 'Service temporarily unavailable',
                    'error_debug': str(e)
                }
                return render(request, self.template_name, context)

    def post(self, request):
        if not request.headers.get('X-Requested-With') == 'XMLHttpRequest': # and request.META['REMOTE_ADDR'] in local_ip:
            device = getDeviceInfo(request)
            # slot_id = request.POST.get('slot_id')
            device_MAC = device['mac']
            identifier = request.POST.get('identifier')
            pulse = int(request.POST.get('pulse', 0))

            try:
                slot_info = models.CoinSlot.objects.get(Slot_Address=device_MAC, Slot_ID=identifier)
            except ObjectDoesNotExist:
                resp = api_response(400)

            else:
                try:
                    rates = models.Rates.objects.get(Pulse=pulse)
                except ObjectDoesNotExist:
                    resp = api_response(900)
                else:
                    connected_client = slot_info.Client
                    portal_settings = models.PortalSettings.objects.first()
                    timeout = portal_settings.slot_timeout if portal_settings else 300
                    time_diff = timedelta.total_seconds(timezone.now()-slot_info.Last_Updated)

                    if connected_client and timedelta(seconds=time_diff).total_seconds() < timeout:
                        ledger = models.Ledger()
                        ledger.Client = connected_client
                        ledger.Denomination = rates.Denom
                        ledger.Slot_No = slot_info.pk
                        ledger.save()

                        q, _ = models.CoinQueue.objects.get_or_create(Client=connected_client)
                        q.Total_Coins += rates.Denom
                        q.save()

                        # Portal is timer authority - don't reset timestamp on coin insertion
                        # slot_info.Last_Updated = timezone.now()
                        # slot_info.save()

                        resp = api_response(200)
                    else:
                        resp = api_response(300)

            return JsonResponse(resp, safe=False)
        else:
            raise Http404("Page not found")


class Commit(View):
    def get(self, request):
        if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            raise Http404("Page not found")

        else:
            data = dict()
            client = request.GET.get('mac')
            
            if not client:
                data['Total_Coins'] = 0
                data['Total_Time'] = 0
                data['Status'] = 'Available'
                return JsonResponse(data)

            try:
                portal_settings = models.PortalSettings.objects.first()
                timeout = portal_settings.slot_timeout if portal_settings else 300

                # Check if client has an active slot (optional - for status only)
                try:
                    slot = models.CoinSlot.objects.get(pk=1, Client=client)
                    time_diff = timedelta.total_seconds(timezone.now()-slot.Last_Updated)
                    if timedelta(seconds=time_diff).total_seconds() > timeout:
                        data['Status'] = 'Available'
                    else:
                        data['Status'] = 'Not Available'
                except models.CoinSlot.DoesNotExist:
                    data['Status'] = 'Available'

                # Get coin queue data (main purpose of this endpoint)
                try:
                    queue = models.CoinQueue.objects.get(Client=client)
                    data['Total_Coins'] = queue.Total_Coins or 0
                    data['Total_Time'] = int(queue.Total_Time.total_seconds()) if queue.Total_Time else 0
                except models.CoinQueue.DoesNotExist:
                    data['Total_Coins'] = 0
                    data['Total_Time'] = 0

            except Exception as e:
                # Fallback in case of any error
                data['Total_Coins'] = 0
                data['Total_Time'] = 0
                data['Status'] = 'Available'
                data['Error'] = str(e)

            return JsonResponse(data)

class Browse(View):

    def get(self, request):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            ip = request.GET.get('ip')
            mac = request.GET.get('mac')
            
            # Validate required parameters
            if not ip or not mac:
                resp = api_response(700)
                resp['description'] = 'Missing IP or MAC address parameters'
                return JsonResponse(data=resp)

            # Check connection limits before allowing connection
            try:
                connection_status = check_connection_limit(mac, request)
                
                if not connection_status['can_connect']:
                    resp = api_response(700)
                    resp['description'] = f"Connection limit exceeded: {connection_status['reason']}"
                    return JsonResponse(data=resp)
            except Exception as e:
                print(f"Error checking connection limits: {e}")
                # Continue without connection limit check
                connection_status = {'can_connect': True, 'connection_limit': 'unlimited'}

            try:
                coin_queue = models.CoinQueue.objects.get(Client=mac)
                addtl_time = coin_queue.Total_Time
                
                # Check if we need to set validity based on rates
                client = models.Clients.objects.get(MAC_Address=mac)
                
                # Find the rate that was used for this purchase to get validity settings
                # We'll use the first rate that matches the purchased time
                matching_rate = None
                for rate in models.Rates.objects.all():
                    if rate.Minutes == addtl_time:
                        matching_rate = rate
                        break
                
                # Set validity if the rate has validity settings
                if matching_rate and (matching_rate.Validity_Days > 0 or matching_rate.Validity_Hours > 0):
                    validity_duration = matching_rate.get_validity_duration()
                    
                    # Set or update validity expiration
                    if not client.Validity_Expires_On:
                        # First time purchase - set validity from now
                        client.Validity_Expires_On = timezone.now() + validity_duration
                    else:
                        # Existing validity - check if expired
                        if timezone.now() > client.Validity_Expires_On:
                            # Previous validity expired, start new validity period
                            client.Validity_Expires_On = timezone.now() + validity_duration
                            # Clear any expired time
                            client.Time_Left = timedelta(0)
                    
                    client.save()
                
                coin_queue.delete()
                client.Connect(addtl_time)

                # Register this connection session
                import uuid
                session_id = str(uuid.uuid4())
                user_agent = request.META.get('HTTP_USER_AGENT', '')
                
                # Get TTL classification for connection tracking
                ttl_value = get_ttl_from_ip(ip)
                if ttl_value:
                    ttl_analysis = analyze_ttl_for_sharing(mac, ttl_value, request)
                    ttl_classification = ttl_analysis.get('ttl_classification', 'unknown')
                else:
                    ttl_classification = 'unknown'
                
                register_connection(mac, ip, session_id, ttl_classification, user_agent)

                # Portal is now timer authority - no timestamp manipulation needed
                # subprocess.run(['gpio', '-1', 'write', str(settings.Light_Pin), '0'])

                resp = api_response(200)
                resp['connection_info'] = {
                    'session_id': session_id,
                    'ttl_classification': ttl_classification,
                    'connection_limit': connection_status['connection_limit']
                }

            except models.CoinQueue.DoesNotExist:
                resp = api_response(700)
                resp['description'] = 'No coins inserted. Please insert coins first.'
            except models.Clients.DoesNotExist:
                resp = api_response(700)
                resp['description'] = 'Client not found. Please refresh the page.'
            except Exception as e:
                print(f"Browse view error: {e}")
                resp = api_response(700)
                resp['description'] = f'Connection error: {str(e)}'

            return JsonResponse(data=resp)
        else:
            raise Http404("Page not found")


class Pause(View):
    def get(self, request):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            ip = request.GET.get('ip')
            mac = request.GET.get('mac')
            action = request.GET.get('action')

            try:
                client = models.Clients.objects.get(MAC_Address=mac)

                if action == 'pause':
                    client.Pause()

                    resp = api_response(200)
                    resp['description'] = 'Paused'

                elif action == 'resume':
                    client.Connect()

                    resp = api_response(200)
                    resp['description'] = 'Connected'
                else:
                    resp = api_response(700)

            except ObjectDoesNotExist:
                resp = api_response(800)

            return JsonResponse(data=resp)

        else:
            raise Http404("Page not found")

class GenerateVoucher(View):
    def get(self, request):
        client = request.GET.get("mac")
        data = dict()
        if not client:
            data['status'] = 'Error. Invalid Action'

        try:
            queue = models.CoinQueue.objects.get(Client=client)
            total_coins = queue.Total_Coins
            total_time = queue.Total_Time
            
            voucher = models.Vouchers()
            voucher.Voucher_status = 'Not Used'
            voucher.Voucher_client = client
            voucher.Voucher_time_value = total_time
            voucher.save()

            queue.delete()

            coin_slot = models.CoinSlot.objects.get(pk=1)
            coin_slot.Client = None
            coin_slot.save()

            data['voucher_code'] = voucher.Voucher_code
            data['status'] = 'OK'

        except ObjectDoesNotExist:
            data['status'] = 'Error. No coin(s) inserted.'
            
        return JsonResponse(data)

class Redeem(View):

    @method_decorator(voucher_rate_limit())
    @method_decorator(log_security_event('voucher_redeem'))
    def post(self, request):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            voucher_code = request.POST.get('voucher', None)
            mac = request.POST.get('mac', None)
            
            # Validate input parameters
            if not voucher_code or not mac:
                resp = api_response(400)
                resp['description'] = 'Voucher code and MAC address are required'
                return JsonResponse(resp)
            
            # Clean and validate voucher code
            voucher_code = voucher_code.strip().upper()
            if len(voucher_code) < 6:
                resp = api_response(110)
                resp['description'] = 'Invalid voucher code format (minimum 6 characters)'
                return JsonResponse(resp)
            
            try:
                # Check if voucher exists and is not used
                voucher = models.Vouchers.objects.get(Voucher_code=voucher_code, Voucher_status='Not Used')
                
                # Check if voucher has expired (30 days from creation)
                from datetime import timedelta
                expiry_date = voucher.Voucher_create_date_time + timedelta(days=30)
                if timezone.now() > expiry_date:
                    # Mark as expired
                    voucher.Voucher_status = 'Expired'
                    voucher.save()
                    resp = api_response(110)
                    resp['description'] = 'Voucher has expired'
                    return JsonResponse(resp)
                
                time_value = voucher.Voucher_time_value
                
                # Assign voucher to client if not already assigned
                if voucher.Voucher_client != mac:
                    voucher.Voucher_client = mac
                    voucher.save()

                try:
                    # Get or create client
                    client, created = models.Clients.objects.get_or_create(
                        MAC_Address=mac,
                        defaults={
                            'Connection_Status': 'Disconnected',
                            'Time_Left': timedelta(0),
                            'Expire_Date': timezone.now()
                        }
                    )
                    
                    import logging
                    logger = logging.getLogger('app')
                    logger.info(f"Voucher redemption: Client {client.MAC_Address} adding {time_value.total_seconds()} seconds")
                    
                    # Check if voucher has validity period and set Validity_Expires_On
                    validity_duration = voucher.get_validity_duration()
                    if validity_duration.total_seconds() > 0:
                        # Set validity expiration if voucher has validity period
                        if not client.Validity_Expires_On:
                            # First time purchase - set validity from now
                            client.Validity_Expires_On = timezone.now() + validity_duration
                        else:
                            # Existing validity - check if expired
                            if timezone.now() > client.Validity_Expires_On:
                                # Previous validity expired, start new validity period
                                client.Validity_Expires_On = timezone.now() + validity_duration
                                # Clear any expired time
                                client.Time_Left = timedelta(0)
                            # If not expired, extend validity period
                            else:
                                client.Validity_Expires_On = max(
                                    client.Validity_Expires_On,
                                    timezone.now() + validity_duration
                                )
                        client.save()
                    
                    # Connect the client with voucher time
                    connect_success = client.Connect(time_value)
                    
                    logger.info(f"Voucher connection result for {mac}: {'Success' if connect_success else 'Failed'}")
                    
                    if connect_success:
                        # Mark voucher as used
                        voucher.Voucher_status = 'Used'
                        voucher.Voucher_used_date_time = timezone.now()
                        voucher.save()
                        
                        logger.info(f"Voucher redeemed successfully: {voucher.Voucher_code}")
                        
                        # Success response with validity info
                        resp = api_response(200)
                        resp['voucher_code'] = voucher.Voucher_code
                        resp['voucher_time'] = int(time_value.total_seconds())
                        
                        # Include validity info in description
                        time_desc = f'{int(time_value.total_seconds() / 3600)}h {int((time_value.total_seconds() % 3600) / 60)}m added'
                        validity_desc = ""
                        if validity_duration.total_seconds() > 0:
                            validity_desc = f" (Valid for {voucher.get_validity_display()})"
                        
                        resp['description'] = f'Voucher redeemed successfully. {time_desc}{validity_desc}.'
                    else:
                        logger.warning(f"Voucher connection failed for client {mac}")
                        resp = api_response(800)
                        resp['description'] = 'Failed to add time to client account'
                        return JsonResponse(resp)
                    
                except Exception as e:
                    # Log the error and return client error
                    print(f"Error connecting client {mac}: {e}")
                    import traceback
                    traceback.print_exc()
                    resp = api_response(800)
                    resp['description'] = 'Failed to connect client'
                    return JsonResponse(resp)

            except models.Vouchers.DoesNotExist:
                # Voucher not found or already used
                resp = api_response(110)
                resp['description'] = 'Invalid, used, or expired voucher code'
                return JsonResponse(resp)
            
            except Exception as e:
                # General error handling
                print(f"Voucher redemption error: {e}")
                resp = api_response(500)
                resp['description'] = 'Internal server error during voucher redemption'
                return JsonResponse(resp)

            return JsonResponse(resp)

        else:
            raise Http404("Page not found")

# Control Section

# Activation classes removed for personal use

class Sweep(View):

    @method_decorator(require_local_ip)
    @method_decorator(log_security_event('system_sweep'))
    def get(self, request):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' and request.META['REMOTE_ADDR'] in local_ip:
            models.Device.objects.filter(pk=1).update(Sync_Time=timezone.now())
            device = models.Device.objects.get(pk=1)
            settings = models.Settings.objects.get(pk=1)
            del_clients = models.Clients.objects.all()
            for del_client in del_clients:
                if del_client.Connection_Status == 'Disconnected':
                    if del_client.Expire_On:
                        diff = timezone.now() - del_client.Expire_On
                    else:
                        diff = timezone.now() - del_client.Date_Created
                    if diff > timedelta(minutes=settings.Inactive_Timeout):
                        del_client.delete()

            clients = models.Clients.objects.all().values()
            context = dict()

            context['clients'] = list(client for client in clients if client['Expire_On'] and (client['Expire_On'] - timezone.now() > timedelta(0)))
            context['system_action'] = device.action
            whitelist = models.Whitelist.objects.all().values_list('MAC_Address')
            context['whitelist'] = list(x[0] for x in whitelist)
            context['push_notif'] = None
            context['push_notif_clients'] = None

            return JsonResponse(context, safe=False)
        else:
            raise Http404("Page not found")

class EloadPortal(View):
    template_name = 'admin/index.html'
    def get(self, request, template_name=template_name):
        return render(request, template_name, context={})

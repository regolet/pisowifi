"""
Security monitoring and alerting system for PISOWifi
"""

import logging
import json
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from django.core.cache import cache
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from typing import Dict, List, Any
import re


logger = logging.getLogger('security')


class SecurityMonitor:
    """
    Real-time security monitoring system
    """
    
    # Threat levels
    THREAT_LEVELS = {
        'LOW': 1,
        'MEDIUM': 2,
        'HIGH': 3,
        'CRITICAL': 4
    }
    
    # Alert thresholds
    ALERT_THRESHOLDS = {
        'failed_logins_per_hour': 10,
        'blocked_ips_per_hour': 5,
        'rate_limits_per_hour': 20,
        'suspicious_activities_per_hour': 15,
        'injection_attempts_per_hour': 3,
        'scanner_detections_per_hour': 2
    }
    
    def __init__(self):
        self.alerts = []
        
    def log_security_event(self, event_type: str, ip_address: str, details: dict = None):
        """
        Log a security event with context
        """
        event_data = {
            'timestamp': timezone.now().isoformat(),
            'type': event_type,
            'ip': ip_address,
            'details': details or {},
            'threat_level': self._assess_threat_level(event_type, details)
        }
        
        # Store in cache for real-time monitoring
        daily_key = f"security_events:{timezone.now().strftime('%Y-%m-%d')}"
        events = cache.get(daily_key, [])
        events.append(event_data)
        
        # Keep only last 10000 events per day
        events = events[-10000:]
        cache.set(daily_key, events, 86400)  # 24 hours
        
        # Log to file
        logger.warning(f"SECURITY_EVENT: {event_type} from {ip_address} - {json.dumps(details)}")
        
        # Check for alert conditions
        self._check_alert_conditions(event_type, ip_address, event_data)
        
        return event_data
    
    def _assess_threat_level(self, event_type: str, details: dict = None) -> str:
        """
        Assess threat level based on event type and details
        """
        critical_events = [
            'sql_injection_attempt',
            'code_injection_attempt', 
            'admin_account_compromise',
            'system_intrusion'
        ]
        
        high_events = [
            'brute_force_attack',
            'scanner_detected',
            'multiple_failed_logins',
            'suspicious_file_access'
        ]
        
        medium_events = [
            'rate_limit_exceeded',
            'unusual_activity_pattern',
            'unauthorized_access_attempt'
        ]
        
        if event_type in critical_events:
            return 'CRITICAL'
        elif event_type in high_events:
            return 'HIGH'
        elif event_type in medium_events:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def _check_alert_conditions(self, event_type: str, ip_address: str, event_data: dict):
        """
        Check if alert conditions are met
        """
        now = timezone.now()
        hour_ago = now - timedelta(hours=1)
        
        # Get events from the last hour
        daily_key = f"security_events:{now.strftime('%Y-%m-%d')}"
        all_events = cache.get(daily_key, [])
        
        # Filter events from last hour
        recent_events = [
            e for e in all_events 
            if datetime.fromisoformat(e['timestamp']) >= hour_ago
        ]
        
        # Count events by type
        event_counts = Counter([e['type'] for e in recent_events])
        
        # Check thresholds
        alerts_triggered = []
        
        if event_counts.get('failed_login', 0) >= self.ALERT_THRESHOLDS['failed_logins_per_hour']:
            alerts_triggered.append('High number of failed logins detected')
        
        if event_counts.get('ip_blocked', 0) >= self.ALERT_THRESHOLDS['blocked_ips_per_hour']:
            alerts_triggered.append('Multiple IPs blocked in short time')
        
        if event_counts.get('rate_limit_exceeded', 0) >= self.ALERT_THRESHOLDS['rate_limits_per_hour']:
            alerts_triggered.append('Excessive rate limiting triggered')
        
        # Count injection attempts
        injection_events = [
            'sql_injection_attempt', 'xss_attempt', 'code_injection_attempt'
        ]
        injection_count = sum(event_counts.get(event, 0) for event in injection_events)
        
        if injection_count >= self.ALERT_THRESHOLDS['injection_attempts_per_hour']:
            alerts_triggered.append('Multiple injection attempts detected')
        
        # Scanner detection
        if event_counts.get('scanner_detected', 0) >= self.ALERT_THRESHOLDS['scanner_detections_per_hour']:
            alerts_triggered.append('Security scanner detected')
        
        # Send alerts if any conditions are met
        for alert_message in alerts_triggered:
            self.send_security_alert(alert_message, event_data['threat_level'], {
                'recent_events': len(recent_events),
                'event_counts': dict(event_counts),
                'triggering_ip': ip_address,
                'timestamp': now.isoformat()
            })
    
    def send_security_alert(self, message: str, threat_level: str, context: dict = None):
        """
        Send security alert via configured channels
        """
        alert_data = {
            'timestamp': timezone.now().isoformat(),
            'message': message,
            'threat_level': threat_level,
            'context': context or {}
        }
        
        # Store alert
        alert_key = "security_alerts"
        alerts = cache.get(alert_key, [])
        alerts.append(alert_data)
        alerts = alerts[-100:]  # Keep last 100 alerts
        cache.set(alert_key, alerts, 86400 * 7)  # 1 week
        
        # Log alert
        logger.error(f"SECURITY_ALERT: [{threat_level}] {message}")
        
        # Send email alert for high/critical threats
        if threat_level in ['HIGH', 'CRITICAL'] and hasattr(settings, 'ADMINS'):
            self._send_email_alert(alert_data)
    
    def _send_email_alert(self, alert_data: dict):
        """
        Send email alert to administrators
        """
        subject = f"PISOWifi Security Alert - {alert_data['threat_level']} Threat"
        
        message = f"""
Security Alert: {alert_data['message']}

Threat Level: {alert_data['threat_level']}
Timestamp: {alert_data['timestamp']}

Context:
{json.dumps(alert_data['context'], indent=2)}

Please review the security logs and take appropriate action.

PISOWifi Security Monitoring System
        """
        
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [admin[1] for admin in settings.ADMINS],
                fail_silently=False,
            )
        except Exception as e:
            logger.error(f"Failed to send security alert email: {e}")
    
    def get_security_dashboard_data(self) -> dict:
        """
        Get data for security dashboard
        """
        now = timezone.now()
        today = now.strftime('%Y-%m-%d')
        
        # Get today's events
        daily_key = f"security_events:{today}"
        events = cache.get(daily_key, [])
        
        # Recent events (last hour)
        hour_ago = now - timedelta(hours=1)
        recent_events = [
            e for e in events 
            if datetime.fromisoformat(e['timestamp']) >= hour_ago
        ]
        
        # Count events by type
        event_counts = Counter([e['type'] for e in events])
        recent_counts = Counter([e['type'] for e in recent_events])
        
        # Threat level distribution
        threat_levels = Counter([e['threat_level'] for e in events])
        
        # Top attacking IPs
        ip_counts = Counter([e['ip'] for e in events])
        top_ips = ip_counts.most_common(10)
        
        # Recent alerts
        alerts = cache.get("security_alerts", [])
        recent_alerts = [
            a for a in alerts 
            if datetime.fromisoformat(a['timestamp']) >= hour_ago
        ]
        
        # Blocked IPs count
        blocked_ips = self._get_blocked_ips_count()
        
        return {
            'summary': {
                'total_events_today': len(events),
                'events_last_hour': len(recent_events),
                'active_alerts': len(recent_alerts),
                'blocked_ips': blocked_ips,
                'threat_level_distribution': dict(threat_levels)
            },
            'event_counts': {
                'today': dict(event_counts),
                'last_hour': dict(recent_counts)
            },
            'top_attacking_ips': top_ips,
            'recent_alerts': recent_alerts[-10:],  # Last 10 alerts
            'recent_events': recent_events[-20:],  # Last 20 events
            'system_status': self._get_system_status()
        }
    
    def _get_blocked_ips_count(self) -> int:
        """
        Get count of currently blocked IPs
        """
        # This is a simplified version - in production you'd track this properly
        blocked_count = 0
        try:
            # Count cache keys that start with "blocked_ip:"
            # This is implementation-specific to your cache backend
            pass
        except:
            pass
        return blocked_count
    
    def _get_system_status(self) -> dict:
        """
        Get overall system security status
        """
        now = timezone.now()
        hour_ago = now - timedelta(hours=1)
        
        # Get recent events
        daily_key = f"security_events:{now.strftime('%Y-%m-%d')}"
        events = cache.get(daily_key, [])
        recent_events = [
            e for e in events 
            if datetime.fromisoformat(e['timestamp']) >= hour_ago
        ]
        
        # Calculate threat score
        threat_score = 0
        for event in recent_events:
            threat_score += self.THREAT_LEVELS.get(event['threat_level'], 1)
        
        # Determine status
        if threat_score >= 50:
            status = 'CRITICAL'
            status_color = 'red'
        elif threat_score >= 20:
            status = 'HIGH_RISK'
            status_color = 'orange'
        elif threat_score >= 10:
            status = 'ELEVATED'
            status_color = 'yellow'
        else:
            status = 'NORMAL'
            status_color = 'green'
        
        return {
            'status': status,
            'status_color': status_color,
            'threat_score': threat_score,
            'last_updated': now.isoformat()
        }
    
    def generate_security_report(self, days: int = 7) -> dict:
        """
        Generate security report for the specified number of days
        """
        report_data = {
            'period': f"Last {days} days",
            'generated_at': timezone.now().isoformat(),
            'summary': {},
            'trends': {},
            'top_threats': {},
            'recommendations': []
        }
        
        # Collect data for each day
        all_events = []
        for i in range(days):
            date = (timezone.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            daily_key = f"security_events:{date}"
            daily_events = cache.get(daily_key, [])
            all_events.extend(daily_events)
        
        if not all_events:
            report_data['summary']['message'] = "No security events recorded in the specified period."
            return report_data
        
        # Summary statistics
        report_data['summary'] = {
            'total_events': len(all_events),
            'unique_ips': len(set([e['ip'] for e in all_events])),
            'threat_distribution': dict(Counter([e['threat_level'] for e in all_events])),
            'most_common_events': dict(Counter([e['type'] for e in all_events]).most_common(10))
        }
        
        # Top threatening IPs
        ip_threat_scores = defaultdict(int)
        for event in all_events:
            ip_threat_scores[event['ip']] += self.THREAT_LEVELS.get(event['threat_level'], 1)
        
        report_data['top_threats'] = {
            'ips': sorted(ip_threat_scores.items(), key=lambda x: x[1], reverse=True)[:10]
        }
        
        # Generate recommendations
        report_data['recommendations'] = self._generate_security_recommendations(all_events)
        
        return report_data
    
    def _generate_security_recommendations(self, events: List[dict]) -> List[str]:
        """
        Generate security recommendations based on events
        """
        recommendations = []
        
        event_types = Counter([e['type'] for e in events])
        
        if event_types.get('failed_login', 0) > 50:
            recommendations.append("Consider implementing stronger password policies due to high number of failed login attempts.")
        
        if event_types.get('scanner_detected', 0) > 10:
            recommendations.append("Multiple security scanners detected. Consider implementing IP geolocation blocking.")
        
        if event_types.get('rate_limit_exceeded', 0) > 100:
            recommendations.append("High rate limiting activity detected. Review rate limit thresholds.")
        
        injection_events = sum([
            event_types.get('sql_injection_attempt', 0),
            event_types.get('xss_attempt', 0),
            event_types.get('code_injection_attempt', 0)
        ])
        
        if injection_events > 20:
            recommendations.append("Multiple injection attempts detected. Ensure input validation is properly implemented.")
        
        if not recommendations:
            recommendations.append("Security posture appears normal. Continue monitoring.")
        
        return recommendations


# Global monitor instance
security_monitor = SecurityMonitor()
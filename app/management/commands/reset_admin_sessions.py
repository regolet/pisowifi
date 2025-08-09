"""
Management command to reset admin sessions and clear expired sessions
"""
from django.core.management.base import BaseCommand
from django.contrib.sessions.models import Session
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Reset admin sessions and clear expired sessions'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--clear-all',
            action='store_true',
            help='Clear all sessions including active ones',
        )
        parser.add_argument(
            '--extend-active',
            action='store_true',
            help='Extend all active sessions by 7 days',
        )
    
    def handle(self, *args, **options):
        self.stdout.write('Starting session reset...')
        
        # Clear expired sessions
        expired_count = self.clear_expired_sessions()
        self.stdout.write(
            self.style.SUCCESS(f'Cleared {expired_count} expired sessions')
        )
        
        if options['clear_all']:
            # Clear all sessions
            all_count = Session.objects.count()
            Session.objects.all().delete()
            self.stdout.write(
                self.style.WARNING(f'Cleared all {all_count} sessions')
            )
        
        if options['extend_active']:
            # Extend active sessions
            extended_count = self.extend_active_sessions()
            self.stdout.write(
                self.style.SUCCESS(f'Extended {extended_count} active sessions')
            )
        
        self.stdout.write(
            self.style.SUCCESS('Session reset completed successfully!')
        )
    
    def clear_expired_sessions(self):
        """Clear expired sessions"""
        expired_sessions = Session.objects.filter(expire_date__lt=timezone.now())
        count = expired_sessions.count()
        expired_sessions.delete()
        return count
    
    def extend_active_sessions(self):
        """Extend active sessions by 7 days"""
        active_sessions = Session.objects.filter(expire_date__gt=timezone.now())
        count = active_sessions.count()
        
        # Extend each session
        for session in active_sessions:
            session.expire_date = timezone.now() + timedelta(days=7)
            session.save()
        
        return count
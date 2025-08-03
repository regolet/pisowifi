"""
Management command to generate permanent admin tokens
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from app.services.admin_token_service import admin_token_service
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Generate permanent admin token for a user'
    
    def add_arguments(self, parser):
        parser.add_argument(
            'username',
            type=str,
            help='Username to generate token for',
        )
        parser.add_argument(
            '--show-token',
            action='store_true',
            help='Display the generated token (security warning: only use in secure environments)',
        )
    
    def handle(self, *args, **options):
        username = options['username']
        
        try:
            # Get user
            user = User.objects.get(username=username)
            
            if not user.is_staff:
                self.stdout.write(
                    self.style.ERROR(f'User {username} is not a staff member')
                )
                return
            
            # Generate token
            token = admin_token_service.generate_admin_token(user)
            
            if token:
                self.stdout.write(
                    self.style.SUCCESS(f'Generated admin token for user {username}')
                )
                
                if options['show_token']:
                    self.stdout.write(
                        self.style.WARNING('Security Warning: This token provides admin access')
                    )
                    self.stdout.write(f'Token: {token}')
                    self.stdout.write(
                        self.style.WARNING('Keep this token secure and do not share it')
                    )
                else:
                    self.stdout.write(
                        'Token generated and stored. Use --show-token to display it.'
                    )
                
                # Show usage instructions
                self.stdout.write('\nUsage instructions:')
                self.stdout.write('1. The token is automatically set as a cookie when you log in')
                self.stdout.write('2. You can also use it in the X-Admin-Token header for API requests')
                self.stdout.write('3. Token is valid for 1 year and survives server restarts')
                self.stdout.write('4. Token provides session-independent admin authentication')
                
            else:
                self.stdout.write(
                    self.style.ERROR('Failed to generate token')
                )
                
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'User {username} not found')
            )
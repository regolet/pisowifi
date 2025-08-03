"""
Management command to test restart functionality safely
"""
from django.core.management.base import BaseCommand
from app.services.server_control_service import ServerControlService, get_server_status
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Test server restart functionality without actually restarting'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Test without actually restarting',
        )
        parser.add_argument(
            '--delay',
            type=int,
            default=5,
            help='Restart delay in seconds (default: 5)',
        )
    
    def handle(self, *args, **options):
        self.stdout.write('Testing server restart functionality...')
        self.stdout.write('=' * 50)
        
        # Test server info
        self.stdout.write('Getting server information...')
        try:
            info_result = get_server_status()
            if info_result['status'] == 'success':
                server_info = info_result['server_info']
                self.stdout.write(
                    self.style.SUCCESS('Server info retrieved successfully:')
                )
                for key, value in server_info.items():
                    self.stdout.write(f'  {key}: {value}')
            else:
                self.stdout.write(
                    self.style.ERROR(f'Failed to get server info: {info_result["message"]}')
                )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error getting server info: {e}')
            )
        
        self.stdout.write('')
        
        # Test restart functionality
        if options['dry_run']:
            self.stdout.write('Dry run mode - testing restart logic without actual restart...')
            try:
                service = ServerControlService()
                delay = options['delay']
                
                self.stdout.write(f'Would restart server with {delay} second delay')
                self.stdout.write(f'Server type: {service._detect_server_type()}')
                self.stdout.write(f'Gunicorn detected: {service._is_gunicorn()}')
                self.stdout.write(f'uWSGI detected: {service._is_uwsgi()}')
                
                self.stdout.write(
                    self.style.SUCCESS('Restart functionality test completed (dry run)')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error in restart test: {e}')
                )
        else:
            self.stdout.write(
                self.style.WARNING('Use --dry-run to test without actually restarting')
            )
        
        self.stdout.write('')
        self.stdout.write('=' * 50)
        self.stdout.write('Test completed successfully!')
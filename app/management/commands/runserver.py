"""
Custom runserver command that disables auto-reload by default
This prevents issues with system updates that require a stable server state
"""

from django.contrib.staticfiles.management.commands.runserver import Command as StaticfilesRunserverCommand


class Command(StaticfilesRunserverCommand):
    help = 'Start a lightweight Web server for PISOWifi development with auto-reload disabled by default'
    
    def add_arguments(self, parser):
        super().add_arguments(parser)
        
        # Override the noreload argument to be True by default
        parser.set_defaults(use_reloader=False)
        
        # Add a new argument to explicitly enable reloading if needed
        parser.add_argument(
            '--enable-reload',
            action='store_true',
            dest='use_reloader',
            help='Enable auto-reloader (disabled by default for system stability)',
        )
    
    def execute(self, *args, **options):
        # Always disable reloader unless explicitly enabled
        if not options.get('use_reloader', False):
            options['use_reloader'] = False
        
        return super().execute(*args, **options)
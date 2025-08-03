"""
Server Control Service for Manual Operations
Handles manual server restart and control operations
"""
import os
import sys
import signal
import subprocess
import threading
import time
from django.conf import settings
from django.core.management import call_command
import logging

logger = logging.getLogger(__name__)

class ServerControlService:
    """
    Service for controlling server operations like manual restart
    """
    
    def __init__(self):
        self.restart_requested = False
        self.restart_delay = 3  # seconds before restart
    
    def request_manual_restart(self, delay_seconds=3):
        """
        Request a manual server restart with optional delay
        """
        try:
            self.restart_delay = delay_seconds
            self.restart_requested = True
            
            logger.info(f"Manual server restart requested with {delay_seconds}s delay")
            
            # Start restart in background thread
            restart_thread = threading.Thread(
                target=self._perform_restart,
                daemon=True,
                name="ManualServerRestart"
            )
            restart_thread.start()
            
            return {
                'status': 'success',
                'message': f'Server restart scheduled in {delay_seconds} seconds',
                'delay': delay_seconds
            }
            
        except Exception as e:
            logger.error(f"Failed to request manual restart: {e}")
            return {
                'status': 'error',
                'message': f'Failed to schedule restart: {str(e)}'
            }
    
    def _perform_restart(self):
        """
        Perform the actual server restart
        """
        try:
            logger.info(f"Waiting {self.restart_delay} seconds before restart...")
            time.sleep(self.restart_delay)
            
            if not self.restart_requested:
                logger.info("Restart was cancelled")
                return
            
            logger.info("Performing manual server restart...")
            
            # Check if we're running under Django development server
            if 'runserver' in sys.argv:
                logger.info("Detected Django development server - performing graceful restart")
                self._restart_development_server()
            else:
                logger.info("Detected production environment - attempting graceful restart")
                self._restart_production_server()
                
        except Exception as e:
            logger.error(f"Error during manual restart: {e}")
    
    def _restart_development_server(self):
        """
        Restart Django development server
        """
        try:
            # For development server, we need to exit and let the process manager restart
            logger.info("Shutting down Django development server for restart...")
            
            # Send SIGTERM to current process
            if hasattr(os, 'kill'):
                os.kill(os.getpid(), signal.SIGTERM)
            else:
                # Fallback for Windows
                sys.exit(0)
                
        except Exception as e:
            logger.error(f"Error restarting development server: {e}")
            # Fallback to hard exit
            sys.exit(1)
    
    def _restart_production_server(self):
        """
        Restart production server (gunicorn, uwsgi, etc.)
        """
        try:
            # Try to detect the server type and restart accordingly
            
            # Check for gunicorn
            if self._is_gunicorn():
                logger.info("Detected Gunicorn - sending HUP signal for graceful restart")
                os.kill(os.getppid(), signal.SIGHUP)
                return
            
            # Check for uwsgi
            if self._is_uwsgi():
                logger.info("Detected uWSGI - sending SIGHUP for graceful restart")
                os.kill(os.getppid(), signal.SIGHUP)
                return
            
            # Check for systemd service
            if self._try_systemd_restart():
                return
            
            # Fallback - just exit and hope process manager restarts
            logger.info("Unknown server type - performing exit restart")
            sys.exit(0)
            
        except Exception as e:
            logger.error(f"Error restarting production server: {e}")
            sys.exit(1)
    
    def _is_gunicorn(self):
        """Check if running under Gunicorn"""
        try:
            import psutil
            current_process = psutil.Process()
            parent = current_process.parent()
            return parent and 'gunicorn' in parent.name().lower()
        except:
            return 'gunicorn' in str(sys.argv[0]).lower()
    
    def _is_uwsgi(self):
        """Check if running under uWSGI"""
        try:
            import uwsgi
            return True
        except ImportError:
            return False
    
    def _try_systemd_restart(self):
        """Try to restart via systemd service"""
        try:
            # Common service names for PisoWiFi
            service_names = ['pisowifi', 'pisowifi-server', 'django-pisowifi', 'opw']
            
            for service_name in service_names:
                try:
                    # Check if service exists
                    result = subprocess.run([
                        'systemctl', 'is-active', service_name
                    ], capture_output=True, text=True, timeout=5)
                    
                    if result.returncode == 0:
                        logger.info(f"Found systemd service: {service_name}")
                        # Restart the service
                        subprocess.run([
                            'sudo', 'systemctl', 'restart', service_name
                        ], timeout=10)
                        logger.info(f"Restarted systemd service: {service_name}")
                        return True
                        
                except subprocess.TimeoutExpired:
                    continue
                except subprocess.CalledProcessError:
                    continue
            
            return False
            
        except Exception as e:
            logger.error(f"Error trying systemd restart: {e}")
            return False
    
    def cancel_restart(self):
        """
        Cancel a pending restart request
        """
        self.restart_requested = False
        logger.info("Manual restart request cancelled")
        return {
            'status': 'success',
            'message': 'Restart request cancelled'
        }
    
    def get_server_info(self):
        """
        Get information about the current server environment
        """
        try:
            info = {
                'python_executable': sys.executable,
                'python_version': sys.version,
                'django_version': getattr(settings, 'DJANGO_VERSION', 'Unknown'),
                'process_id': os.getpid(),
                'parent_process_id': os.getppid(),
                'command_line': ' '.join(sys.argv),
                'server_type': self._detect_server_type(),
                'restart_available': True
            }
            
            return {
                'status': 'success',
                'server_info': info
            }
            
        except Exception as e:
            logger.error(f"Error getting server info: {e}")
            return {
                'status': 'error',
                'message': f'Failed to get server info: {str(e)}'
            }
    
    def _detect_server_type(self):
        """Detect what type of server we're running under"""
        if 'runserver' in sys.argv:
            return 'Django Development Server'
        elif self._is_gunicorn():
            return 'Gunicorn'
        elif self._is_uwsgi():
            return 'uWSGI'
        else:
            return 'Unknown'

# Global instance
server_control = ServerControlService()

def request_server_restart(delay_seconds=3):
    """
    Convenience function to request server restart
    """
    return server_control.request_manual_restart(delay_seconds)

def cancel_server_restart():
    """
    Convenience function to cancel server restart
    """
    return server_control.cancel_restart()

def get_server_status():
    """
    Convenience function to get server information
    """
    return server_control.get_server_info()
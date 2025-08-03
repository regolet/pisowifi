"""
Daemon Interface Service
Provides interface between Django admin and the update daemon
"""
import os
import json
import subprocess
import logging
from pathlib import Path
from django.conf import settings
from django.http import JsonResponse
from app.services.update_daemon import (
    start_daemon, stop_daemon, is_daemon_running, 
    get_daemon_status, get_update_progress
)

logger = logging.getLogger(__name__)

class DaemonInterface:
    """
    Interface for communicating with the update daemon
    """
    
    def __init__(self):
        self.daemon_dir = Path(settings.BASE_DIR) / 'temp' / 'daemon'
        self.daemon_dir.mkdir(parents=True, exist_ok=True)
        
    def ensure_daemon_running(self):
        """Ensure the update daemon is running"""
        try:
            if not is_daemon_running():
                logger.info("Starting update daemon")
                
                # Start daemon as subprocess
                daemon_script = Path(__file__).parent / 'update_daemon.py'
                subprocess.Popen([
                    'python', str(daemon_script), 'start'
                ], cwd=settings.BASE_DIR)
                
                # Give it a moment to start
                import time
                time.sleep(2)
                
                if is_daemon_running():
                    logger.info("Update daemon started successfully")
                    return True
                else:
                    logger.error("Failed to start update daemon")
                    return False
            else:
                logger.debug("Update daemon is already running")
                return True
                
        except Exception as e:
            logger.error(f"Error ensuring daemon is running: {e}")
            return False
            
    def queue_update_installation(self, update):
        """Queue an update for installation by the daemon"""
        try:
            # Ensure daemon is running
            if not self.ensure_daemon_running():
                return {
                    'status': 'error',
                    'message': 'Failed to start update daemon'
                }
                
            # Mark update for daemon processing
            update.Status = 'daemon_pending'
            update.save()
            
            logger.info(f"Queued update {update.Version_Number} for daemon processing")
            
            return {
                'status': 'success',
                'message': f'Update {update.Version_Number} queued for installation',
                'update_id': update.id
            }
            
        except Exception as e:
            logger.error(f"Error queueing update: {e}")
            return {
                'status': 'error',
                'message': f'Failed to queue update: {str(e)}'
            }
            
    def get_installation_progress(self, update_id):
        """Get installation progress for a specific update"""
        try:
            progress_data = get_update_progress()
            
            if not progress_data:
                # Check if update exists in database
                from app.models import SystemUpdate
                try:
                    update = SystemUpdate.objects.get(pk=update_id)
                    return {
                        'status': update.Status,
                        'progress': update.Progress or 0,
                        'error': update.Error_Message
                    }
                except SystemUpdate.DoesNotExist:
                    return {
                        'status': 'error',
                        'message': 'Update not found'
                    }
                    
            # Return daemon progress if available
            if progress_data.get('update_id') == update_id:
                return progress_data
            else:
                # Progress is for different update, check database
                from app.models import SystemUpdate
                try:
                    update = SystemUpdate.objects.get(pk=update_id)
                    return {
                        'status': update.Status,
                        'progress': update.Progress or 0,
                        'error': update.Error_Message
                    }
                except SystemUpdate.DoesNotExist:
                    return {
                        'status': 'error',
                        'message': 'Update not found'
                    }
                    
        except Exception as e:
            logger.error(f"Error getting installation progress: {e}")
            return {
                'status': 'error',
                'message': f'Failed to get progress: {str(e)}'
            }
            
    def get_installation_logs(self, update_id):
        """Get installation logs for a specific update"""
        try:
            progress_data = get_update_progress()
            
            if progress_data and progress_data.get('update_id') == update_id:
                # Return logs from daemon progress file
                logs = progress_data.get('logs', [])
                return {
                    'status': 'success',
                    'logs': '\n'.join(logs) if logs else 'No logs available'
                }
            else:
                # Check database for logs
                from app.models import SystemUpdate
                try:
                    update = SystemUpdate.objects.get(pk=update_id)
                    return {
                        'status': 'success',
                        'logs': update.Installation_Log or 'No logs available'
                    }
                except SystemUpdate.DoesNotExist:
                    return {
                        'status': 'error',
                        'message': 'Update not found'
                    }
                    
        except Exception as e:
            logger.error(f"Error getting installation logs: {e}")
            return {
                'status': 'error',
                'message': f'Failed to get logs: {str(e)}',
                'logs': ''
            }
            
    def get_daemon_info(self):
        """Get information about the daemon status"""
        try:
            status = get_daemon_status()
            running = is_daemon_running()
            
            return {
                'status': 'success',
                'daemon_running': running,
                'daemon_status': status,
                'daemon_available': True
            }
            
        except Exception as e:
            logger.error(f"Error getting daemon info: {e}")
            return {
                'status': 'error',
                'message': f'Failed to get daemon info: {str(e)}',
                'daemon_running': False,
                'daemon_available': False
            }
            
    def stop_daemon_service(self):
        """Stop the update daemon"""
        try:
            if stop_daemon():
                logger.info("Update daemon stopped successfully")
                return {
                    'status': 'success',
                    'message': 'Update daemon stopped successfully'
                }
            else:
                return {
                    'status': 'error',
                    'message': 'Failed to stop update daemon'
                }
                
        except Exception as e:
            logger.error(f"Error stopping daemon: {e}")
            return {
                'status': 'error',
                'message': f'Failed to stop daemon: {str(e)}'
            }
            
    def restart_daemon_service(self):
        """Restart the update daemon"""
        try:
            # Stop daemon
            stop_result = self.stop_daemon_service()
            if stop_result['status'] != 'success':
                return stop_result
                
            # Wait a moment
            import time
            time.sleep(2)
            
            # Start daemon
            if self.ensure_daemon_running():
                logger.info("Update daemon restarted successfully")
                return {
                    'status': 'success',
                    'message': 'Update daemon restarted successfully'
                }
            else:
                return {
                    'status': 'error',
                    'message': 'Failed to restart update daemon'
                }
                
        except Exception as e:
            logger.error(f"Error restarting daemon: {e}")
            return {
                'status': 'error',
                'message': f'Failed to restart daemon: {str(e)}'
            }

# Global interface instance
daemon_interface = DaemonInterface()

def queue_update_for_daemon(update):
    """Convenience function to queue update for daemon processing"""
    return daemon_interface.queue_update_installation(update)

def get_daemon_progress(update_id):
    """Convenience function to get daemon progress"""
    return daemon_interface.get_installation_progress(update_id)

def get_daemon_logs(update_id):
    """Convenience function to get daemon logs"""
    return daemon_interface.get_installation_logs(update_id)

def ensure_daemon_is_running():
    """Convenience function to ensure daemon is running"""
    return daemon_interface.ensure_daemon_running()

def get_daemon_status_info():
    """Convenience function to get daemon status"""
    return daemon_interface.get_daemon_info()
"""
Update Daemon Service
Handles system updates in a separate process to avoid server downtime
"""
import os
import sys
import json
import time
import signal
import logging
import threading
import subprocess
from pathlib import Path
from datetime import datetime
from django.conf import settings
from django.utils import timezone

# Add project root to Python path for Django imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'opw.settings')

import django
django.setup()

from app.models import SystemUpdate
from app.services.update_service import UpdateInstallService

logger = logging.getLogger(__name__)

class UpdateDaemon:
    """
    Standalone update daemon that runs independently of the main Django server
    """
    
    def __init__(self):
        self.daemon_dir = Path(settings.BASE_DIR) / 'temp' / 'daemon'
        self.daemon_dir.mkdir(parents=True, exist_ok=True)
        
        # Daemon control files
        self.pid_file = self.daemon_dir / 'update_daemon.pid'
        self.status_file = self.daemon_dir / 'update_status.json'
        self.progress_file = self.daemon_dir / 'update_progress.json'
        self.log_file = self.daemon_dir / 'update_daemon.log'
        
        # Daemon state
        self.running = False
        self.current_update_id = None
        self.shutdown_requested = False
        
        # Setup logging
        self._setup_logging()
        
    def _setup_logging(self):
        """Setup daemon-specific logging"""
        daemon_logger = logging.getLogger('update_daemon')
        daemon_logger.setLevel(logging.INFO)
        
        # File handler
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        
        daemon_logger.addHandler(file_handler)
        
        # Set as default logger for this module
        global logger
        logger = daemon_logger
        
    def start_daemon(self):
        """Start the update daemon"""
        try:
            # Check if daemon is already running
            if self.is_running():
                logger.warning("Update daemon is already running")
                return False
                
            # Write PID file
            with open(self.pid_file, 'w') as f:
                f.write(str(os.getpid()))
                
            # Initialize status file
            self._write_status({
                'status': 'idle',
                'started_at': datetime.now().isoformat(),
                'current_update': None,
                'message': 'Update daemon started'
            })
            
            self.running = True
            logger.info(f"Update daemon started with PID {os.getpid()}")
            
            # Setup signal handlers
            signal.signal(signal.SIGTERM, self._signal_handler)
            signal.signal(signal.SIGINT, self._signal_handler)
            
            # Start main daemon loop
            self._daemon_loop()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start daemon: {e}")
            return False
            
    def _daemon_loop(self):
        """Main daemon loop"""
        logger.info("Starting daemon main loop")
        
        while self.running and not self.shutdown_requested:
            try:
                # Check for pending update requests
                pending_update = self._check_for_pending_updates()
                
                if pending_update:
                    logger.info(f"Found pending update: {pending_update.id}")
                    self._process_update(pending_update)
                else:
                    # Sleep for a short interval before checking again
                    time.sleep(2)
                    
            except Exception as e:
                logger.error(f"Error in daemon loop: {e}")
                time.sleep(5)  # Wait longer on error
                
        logger.info("Daemon loop ended")
        self._cleanup()
        
    def _check_for_pending_updates(self):
        """Check database for pending update installations"""
        try:
            # Look for updates that are marked for daemon processing
            return SystemUpdate.objects.filter(
                Status='daemon_pending'
            ).first()
        except Exception as e:
            logger.error(f"Error checking for pending updates: {e}")
            return None
            
    def _process_update(self, update):
        """Process a single update installation"""
        self.current_update_id = update.id
        
        try:
            logger.info(f"Starting installation of update {update.Version_Number}")
            
            # Update status
            self._write_status({
                'status': 'installing',
                'current_update': update.id,
                'version': update.Version_Number,
                'started_at': datetime.now().isoformat(),
                'message': f'Installing update {update.Version_Number}'
            })
            
            # Initialize progress tracking
            self._write_progress({
                'update_id': update.id,
                'progress': 0,
                'status': 'installing',
                'message': 'Starting installation',
                'logs': []
            })
            
            # Mark update as being processed by daemon
            update.Status = 'installing'
            update.Progress = 0
            update.Started_At = timezone.now()
            update.save()
            
            # Create install service and run installation
            install_service = UpdateInstallService(update)
            
            # Override the install service's logging to also write to our progress file
            original_log = install_service._log
            def enhanced_log(message, level="INFO"):
                original_log(message, level)
                self._append_log(update.id, f"[{level}] {message}")
                
            install_service._log = enhanced_log
            
            # Run the installation
            result = install_service.install_update()
            
            if result.get('status') == 'success':
                logger.info(f"Update {update.Version_Number} installed successfully")
                
                self._write_status({
                    'status': 'completed',
                    'current_update': update.id,
                    'version': update.Version_Number,
                    'completed_at': datetime.now().isoformat(),
                    'message': f'Update {update.Version_Number} installed successfully'
                })
                
                self._write_progress({
                    'update_id': update.id,
                    'progress': 100,
                    'status': 'completed',
                    'message': 'Installation completed successfully'
                })
                
                # Schedule server restart if recommended
                if result.get('restart_recommended'):
                    self._schedule_server_restart()
                    
            else:
                error_msg = result.get('message', 'Unknown error')
                logger.error(f"Update {update.Version_Number} failed: {error_msg}")
                
                self._write_status({
                    'status': 'failed',
                    'current_update': update.id,
                    'version': update.Version_Number,
                    'failed_at': datetime.now().isoformat(),
                    'message': f'Update failed: {error_msg}',
                    'error': error_msg
                })
                
                self._write_progress({
                    'update_id': update.id,
                    'progress': update.Progress or 0,
                    'status': 'failed',
                    'message': f'Installation failed: {error_msg}',
                    'error': error_msg
                })
                
        except Exception as e:
            logger.error(f"Unexpected error processing update {update.id}: {e}")
            
            self._write_status({
                'status': 'failed',
                'current_update': update.id,
                'failed_at': datetime.now().isoformat(),
                'message': f'Unexpected error: {str(e)}',
                'error': str(e)
            })
            
        finally:
            self.current_update_id = None
            
    def _schedule_server_restart(self):
        """Schedule server restart after successful update"""
        try:
            logger.info("Scheduling server restart after successful update")
            
            # Import here to avoid circular imports
            from app.services.server_control_service import request_server_restart
            
            # Schedule restart in 10 seconds to allow status updates to be read
            result = request_server_restart(delay_seconds=10)
            
            if result.get('status') == 'success':
                logger.info("Server restart scheduled successfully")
                self._write_status({
                    'status': 'restart_scheduled',
                    'message': 'Server restart scheduled in 10 seconds',
                    'restart_in': 10
                })
            else:
                logger.warning(f"Failed to schedule server restart: {result.get('message')}")
                
        except Exception as e:
            logger.error(f"Error scheduling server restart: {e}")
            
    def _append_log(self, update_id, message):
        """Append log message to progress file"""
        try:
            progress_data = self._read_progress()
            if not progress_data:
                progress_data = {'logs': []}
                
            if 'logs' not in progress_data:
                progress_data['logs'] = []
                
            timestamp = datetime.now().strftime('%H:%M:%S')
            progress_data['logs'].append(f"[{timestamp}] {message}")
            
            # Keep only last 100 log entries
            if len(progress_data['logs']) > 100:
                progress_data['logs'] = progress_data['logs'][-100:]
                
            self._write_progress(progress_data)
            
        except Exception as e:
            logger.error(f"Error appending log: {e}")
            
    def _write_status(self, status_data):
        """Write daemon status to file"""
        try:
            with open(self.status_file, 'w') as f:
                json.dump(status_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error writing status: {e}")
            
    def _read_status(self):
        """Read daemon status from file"""
        try:
            if self.status_file.exists():
                with open(self.status_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error reading status: {e}")
        return None
        
    def _write_progress(self, progress_data):
        """Write update progress to file"""
        try:
            progress_data['updated_at'] = datetime.now().isoformat()
            with open(self.progress_file, 'w') as f:
                json.dump(progress_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error writing progress: {e}")
            
    def _read_progress(self):
        """Read update progress from file"""
        try:
            if self.progress_file.exists():
                with open(self.progress_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error reading progress: {e}")
        return None
        
    def is_running(self):
        """Check if daemon is currently running"""
        try:
            if not self.pid_file.exists():
                return False
                
            with open(self.pid_file, 'r') as f:
                pid = int(f.read().strip())
                
            # Check if process exists
            try:
                os.kill(pid, 0)  # Doesn't actually kill, just checks if process exists
                return True
            except OSError:
                # Process doesn't exist, clean up stale PID file
                self.pid_file.unlink()
                return False
                
        except Exception as e:
            logger.error(f"Error checking daemon status: {e}")
            return False
            
    def stop_daemon(self):
        """Stop the daemon gracefully"""
        try:
            if not self.is_running():
                logger.info("Daemon is not running")
                return True
                
            with open(self.pid_file, 'r') as f:
                pid = int(f.read().strip())
                
            logger.info(f"Stopping daemon with PID {pid}")
            os.kill(pid, signal.SIGTERM)
            
            # Wait for daemon to stop
            for _ in range(30):  # Wait up to 30 seconds
                if not self.is_running():
                    logger.info("Daemon stopped successfully")
                    return True
                time.sleep(1)
                
            # Force kill if it didn't stop gracefully
            logger.warning("Daemon didn't stop gracefully, force killing")
            os.kill(pid, signal.SIGKILL)
            return True
            
        except Exception as e:
            logger.error(f"Error stopping daemon: {e}")
            return False
            
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down daemon")
        self.shutdown_requested = True
        self.running = False
        
    def _cleanup(self):
        """Clean up daemon resources"""
        try:
            # Update status
            self._write_status({
                'status': 'stopped',
                'stopped_at': datetime.now().isoformat(),
                'message': 'Update daemon stopped'
            })
            
            # Remove PID file
            if self.pid_file.exists():
                self.pid_file.unlink()
                
            logger.info("Daemon cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

def start_daemon():
    """Start the update daemon"""
    daemon = UpdateDaemon()
    return daemon.start_daemon()

def stop_daemon():
    """Stop the update daemon"""
    daemon = UpdateDaemon()
    return daemon.stop_daemon()

def is_daemon_running():
    """Check if update daemon is running"""
    daemon = UpdateDaemon()
    return daemon.is_running()

def get_daemon_status():
    """Get current daemon status"""
    daemon = UpdateDaemon()
    return daemon._read_status()

def get_update_progress():
    """Get current update progress"""
    daemon = UpdateDaemon()
    return daemon._read_progress()

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Update Daemon Control')
    parser.add_argument('action', choices=['start', 'stop', 'status', 'restart'],
                       help='Action to perform')
    
    args = parser.parse_args()
    
    if args.action == 'start':
        if start_daemon():
            print("Update daemon started successfully")
        else:
            print("Failed to start update daemon")
            sys.exit(1)
            
    elif args.action == 'stop':
        if stop_daemon():
            print("Update daemon stopped successfully")
        else:
            print("Failed to stop update daemon")
            sys.exit(1)
            
    elif args.action == 'restart':
        print("Stopping daemon...")
        stop_daemon()
        time.sleep(2)
        print("Starting daemon...")
        if start_daemon():
            print("Update daemon restarted successfully")
        else:
            print("Failed to restart update daemon")
            sys.exit(1)
            
    elif args.action == 'status':
        if is_daemon_running():
            print("Update daemon is running")
            status = get_daemon_status()
            if status:
                print(f"Status: {status}")
        else:
            print("Update daemon is not running")
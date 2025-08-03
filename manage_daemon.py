#!/usr/bin/env python
"""
Update Daemon Management Script
Provides easy CLI interface for managing the update daemon
"""
import os
import sys
import django
from pathlib import Path

# Add project to path and setup Django
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'opw.settings')
django.setup()

from app.services.update_daemon import (
    start_daemon, stop_daemon, is_daemon_running, 
    get_daemon_status, get_update_progress
)

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Update Daemon Management')
    parser.add_argument('action', choices=['start', 'stop', 'restart', 'status', 'progress'],
                       help='Action to perform')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    
    args = parser.parse_args()
    
    if args.action == 'start':
        print("Starting update daemon...")
        if is_daemon_running():
            print("Update daemon is already running")
            sys.exit(0)
            
        success = start_daemon()
        if success:
            print("Update daemon started successfully")
        else:
            print("Failed to start update daemon")
            sys.exit(1)
            
    elif args.action == 'stop':
        print("Stopping update daemon...")
        if not is_daemon_running():
            print("Update daemon is not running")
            sys.exit(0)
            
        success = stop_daemon()
        if success:
            print("Update daemon stopped successfully")
        else:
            print("Failed to stop update daemon")
            sys.exit(1)
            
    elif args.action == 'restart':
        print("Restarting update daemon...")
        
        if is_daemon_running():
            print("Stopping daemon...")
            stop_daemon()
            import time
            time.sleep(2)
            
        print("Starting daemon...")
        success = start_daemon()
        if success:
            print("Update daemon restarted successfully")
        else:
            print("Failed to restart update daemon")
            sys.exit(1)
            
    elif args.action == 'status':
        running = is_daemon_running()
        print(f"Update daemon running: {running}")
        
        if running:
            status = get_daemon_status()
            if status:
                print(f"Status: {status.get('status', 'unknown')}")
                print(f"Message: {status.get('message', 'no message')}")
                if 'current_update' in status and status['current_update']:
                    print(f"Current update: {status['current_update']}")
                if args.verbose:
                    print(f"Full status: {status}")
            else:
                print("Could not retrieve daemon status")
        
    elif args.action == 'progress':
        progress = get_update_progress()
        if progress:
            print(f"Update ID: {progress.get('update_id', 'none')}")
            print(f"Status: {progress.get('status', 'unknown')}")
            print(f"Progress: {progress.get('progress', 0)}%")
            print(f"Message: {progress.get('message', 'no message')}")
            
            if args.verbose and 'logs' in progress:
                print("\nRecent logs:")
                logs = progress['logs']
                if isinstance(logs, list):
                    for log in logs[-10:]:  # Show last 10 log entries
                        print(f"  {log}")
                else:
                    print(f"  {logs}")
        else:
            print("No update progress available")

if __name__ == '__main__':
    main()
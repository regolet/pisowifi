"""
Database Backup Service
Handles database backup and restore operations
"""
import os
import json
import gzip
import shutil
import sqlite3
import subprocess
from datetime import datetime, timedelta
from django.conf import settings
from django.db import connection
from django.utils import timezone
from django.core.management import call_command
from io import StringIO
import threading
import time


class DatabaseBackupService:
    """Service class for handling database backup operations"""
    
    def __init__(self):
        self.backup_dir = os.path.join(settings.BASE_DIR, 'backups', 'database')
        self.ensure_backup_directory()
    
    def ensure_backup_directory(self):
        """Ensure backup directory exists"""
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def create_backup(self, backup_obj, backup_type='full', tables=None):
        """Create a database backup"""
        from ..models import DatabaseBackup
        
        try:
            # Update backup status
            backup_obj.status = 'running'
            backup_obj.started_at = timezone.now()
            backup_obj.current_operation = 'Starting backup...'
            backup_obj.save()
            
            # Generate backup filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{backup_type}_backup_{timestamp}.sql"
            if backup_obj.compressed:
                filename += '.gz'
            
            backup_path = os.path.join(self.backup_dir, filename)
            backup_obj.file_path = backup_path
            backup_obj.save()
            
            # Perform backup based on type
            if backup_type == 'full':
                self._create_full_backup(backup_obj, backup_path)
            elif backup_type == 'clients':
                self._create_clients_backup(backup_obj, backup_path)
            elif backup_type == 'settings':
                self._create_settings_backup(backup_obj, backup_path)
            elif backup_type == 'custom':
                self._create_custom_backup(backup_obj, backup_path, tables)
            
            # Update final status
            backup_obj.status = 'completed'
            backup_obj.completed_at = timezone.now()
            backup_obj.progress_percentage = 100
            backup_obj.current_operation = 'Backup completed'
            
            # Get file size
            if os.path.exists(backup_path):
                backup_obj.file_size = os.path.getsize(backup_path)
            
            backup_obj.save()
            
            return True, "Backup completed successfully"
            
        except Exception as e:
            backup_obj.status = 'failed'
            backup_obj.error_message = str(e)
            backup_obj.completed_at = timezone.now()
            backup_obj.save()
            return False, str(e)
    
    def _create_full_backup(self, backup_obj, backup_path):
        """Create full database backup"""
        backup_obj.current_operation = 'Creating full database backup...'
        backup_obj.progress_percentage = 10
        backup_obj.save()
        
        # Get all tables
        tables = self._get_all_tables()
        backup_obj.tables_included = ', '.join(tables)
        backup_obj.progress_percentage = 20
        backup_obj.save()
        
        # Create backup using Django's dumpdata
        backup_obj.current_operation = 'Exporting data...'
        backup_obj.progress_percentage = 30
        backup_obj.save()
        
        self._export_data(backup_obj, backup_path, None)
    
    def _create_clients_backup(self, backup_obj, backup_path):
        """Create backup of client-related data only"""
        backup_obj.current_operation = 'Creating clients data backup...'
        backup_obj.progress_percentage = 10
        backup_obj.save()
        
        # Client-related tables
        client_tables = [
            'app.clients',
            'app.unauthenticatedclients',
            'app.whitelist',
            'app.ledger',
            'app.coinqueue',
            'app.connectiontracker',
            'app.devicefingerprint',
            'app.trafficanalysis',
            'app.devicebehaviorprofile'
        ]
        
        backup_obj.tables_included = ', '.join(client_tables)
        backup_obj.progress_percentage = 30
        backup_obj.save()
        
        self._export_data(backup_obj, backup_path, client_tables)
    
    def _create_settings_backup(self, backup_obj, backup_path):
        """Create backup of system settings only"""
        backup_obj.current_operation = 'Creating settings backup...'
        backup_obj.progress_percentage = 10
        backup_obj.save()
        
        # System settings tables
        settings_tables = [
            'app.settings',
            'app.network',
            'app.rates',
            'app.device',
            'app.securitysettings',
            'app.updatesettings',
            'app.backupsettings',
            'app.ttlfirewallrule',
            'app.adaptiveqosrule',
            'app.networkintelligence'
        ]
        
        backup_obj.tables_included = ', '.join(settings_tables)
        backup_obj.progress_percentage = 30
        backup_obj.save()
        
        self._export_data(backup_obj, backup_path, settings_tables)
    
    def _create_custom_backup(self, backup_obj, backup_path, tables):
        """Create backup of custom selected tables"""
        backup_obj.current_operation = 'Creating custom backup...'
        backup_obj.progress_percentage = 10
        backup_obj.save()
        
        if tables:
            backup_obj.tables_included = ', '.join(tables)
        backup_obj.progress_percentage = 30
        backup_obj.save()
        
        self._export_data(backup_obj, backup_path, tables)
    
    def _export_data(self, backup_obj, backup_path, tables=None):
        """Export data using Django's dumpdata command"""
        backup_obj.current_operation = 'Serializing data...'
        backup_obj.progress_percentage = 50
        backup_obj.save()
        
        try:
            # Capture dumpdata output
            output = StringIO()
            
            if tables:
                # Export specific tables
                call_command('dumpdata', *tables, stdout=output, indent=2)
            else:
                # Export all data except sessions and contenttypes
                call_command('dumpdata', 
                           '--exclude=sessions',
                           '--exclude=contenttypes',
                           '--exclude=admin.LogEntry',
                           stdout=output, indent=2)
            
            backup_obj.current_operation = 'Writing backup file...'
            backup_obj.progress_percentage = 70
            backup_obj.save()
            
            # Get the data
            data = output.getvalue()
            output.close()
            
            # Count records
            import json
            try:
                json_data = json.loads(data)
                backup_obj.records_count = len(json_data)
            except:
                backup_obj.records_count = 0
            
            backup_obj.progress_percentage = 80
            backup_obj.save()
            
            # Write to file (compressed or uncompressed)
            if backup_obj.compressed:
                with gzip.open(backup_path, 'wt', encoding='utf-8') as f:
                    f.write(data)
            else:
                with open(backup_path, 'w', encoding='utf-8') as f:
                    f.write(data)
            
            backup_obj.current_operation = 'Finalizing backup...'
            backup_obj.progress_percentage = 90
            backup_obj.save()
            
        except Exception as e:
            raise Exception(f"Error during data export: {str(e)}")
    
    def restore_backup(self, backup_obj):
        """Restore from a backup file"""
        try:
            backup_obj.current_operation = 'Starting restore...'
            backup_obj.progress_percentage = 0
            backup_obj.save()
            
            if not os.path.exists(backup_obj.file_path):
                raise Exception("Backup file not found")
            
            backup_obj.current_operation = 'Reading backup file...'
            backup_obj.progress_percentage = 20
            backup_obj.save()
            
            # Read backup file
            if backup_obj.compressed:
                with gzip.open(backup_obj.file_path, 'rt', encoding='utf-8') as f:
                    data = f.read()
            else:
                with open(backup_obj.file_path, 'r', encoding='utf-8') as f:
                    data = f.read()
            
            backup_obj.current_operation = 'Restoring data...'
            backup_obj.progress_percentage = 50
            backup_obj.save()
            
            # Create temporary file for loaddata
            temp_file = backup_obj.file_path + '.temp.json'
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(data)
            
            backup_obj.current_operation = 'Loading data into database...'
            backup_obj.progress_percentage = 70
            backup_obj.save()
            
            # Load data using Django's loaddata
            call_command('loaddata', temp_file)
            
            # Clean up temp file
            os.remove(temp_file)
            
            backup_obj.current_operation = 'Restore completed'
            backup_obj.progress_percentage = 100
            backup_obj.save()
            
            return True, "Restore completed successfully"
            
        except Exception as e:
            backup_obj.current_operation = f'Restore failed: {str(e)}'
            backup_obj.save()
            return False, str(e)
    
    def cleanup_old_backups(self, max_count=10, retention_days=30):
        """Clean up old backup files"""
        from ..models import DatabaseBackup
        
        # Delete old backup records and files
        cutoff_date = timezone.now() - timedelta(days=retention_days)
        old_backups = DatabaseBackup.objects.filter(created_at__lt=cutoff_date)
        
        for backup in old_backups:
            if backup.file_path and os.path.exists(backup.file_path):
                try:
                    os.remove(backup.file_path)
                except:
                    pass
            backup.delete()
        
        # Keep only the most recent backups
        if max_count > 0:
            excess_backups = DatabaseBackup.objects.all()[max_count:]
            for backup in excess_backups:
                if backup.file_path and os.path.exists(backup.file_path):
                    try:
                        os.remove(backup.file_path)
                    except:
                        pass
                backup.delete()
    
    def _get_all_tables(self):
        """Get list of all database tables"""
        with connection.cursor() as cursor:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            # Filter out Django system tables
            app_tables = [table for table in tables if table.startswith('app_')]
            return app_tables
    
    def get_backup_statistics(self):
        """Get backup statistics"""
        from ..models import DatabaseBackup
        
        total_backups = DatabaseBackup.objects.count()
        completed_backups = DatabaseBackup.objects.filter(status='completed').count()
        failed_backups = DatabaseBackup.objects.filter(status='failed').count()
        
        # Calculate total backup size
        completed = DatabaseBackup.objects.filter(status='completed')
        total_size = sum([backup.file_size for backup in completed])
        
        return {
            'total_backups': total_backups,
            'completed_backups': completed_backups,
            'failed_backups': failed_backups,
            'total_size': total_size,
            'total_size_display': self._format_file_size(total_size)
        }
    
    def _format_file_size(self, size_bytes):
        """Format file size in human readable format"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        import math
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_names[i]}"


def run_backup_async(backup_id, backup_type='full', tables=None):
    """Run backup operation asynchronously"""
    from ..models import DatabaseBackup
    
    def backup_thread():
        try:
            backup_obj = DatabaseBackup.objects.get(id=backup_id)
            service = DatabaseBackupService()
            service.create_backup(backup_obj, backup_type, tables)
        except Exception as e:
            print(f"Backup thread error: {e}")
    
    thread = threading.Thread(target=backup_thread)
    thread.daemon = True
    thread.start()


def run_restore_async(backup_id):
    """Run restore operation asynchronously"""
    from ..models import DatabaseBackup
    
    def restore_thread():
        try:
            backup_obj = DatabaseBackup.objects.get(id=backup_id)
            service = DatabaseBackupService()
            service.restore_backup(backup_obj)
        except Exception as e:
            print(f"Restore thread error: {e}")
    
    thread = threading.Thread(target=restore_thread)
    thread.daemon = True
    thread.start()
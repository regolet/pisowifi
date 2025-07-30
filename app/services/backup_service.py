import os
import shutil
import subprocess
import logging
from datetime import datetime
from django.conf import settings
from django.utils import timezone
from app.models import SystemBackup, SystemUpdate

logger = logging.getLogger(__name__)


class BackupService:
    def __init__(self):
        self.backup_base_path = os.path.join(settings.BASE_DIR, 'backups')
        os.makedirs(self.backup_base_path, exist_ok=True)
    
    def create_manual_backup(self, name, description='', created_by='System'):
        """Create a manual backup"""
        backup = SystemBackup.objects.create(
            Backup_Name=name,
            Backup_Type='manual',
            Status='creating',
            Description=description,
            Created_By=created_by,
            Backup_Path='pending'
        )
        
        try:
            # Create backup directory
            backup_dir = self._create_backup_directory(backup)
            backup.Backup_Path = backup_dir
            backup.save()
            
            # Perform backup
            self._perform_backup(backup, backup_dir)
            
            # Calculate backup size
            backup.Backup_Size = self._calculate_directory_size(backup_dir)
            backup.Status = 'completed'
            backup.save()
            
            return {
                'status': 'success',
                'backup_id': backup.id,
                'message': f'Backup "{name}" created successfully'
            }
            
        except Exception as e:
            backup.Status = 'failed'
            backup.Error_Message = str(e)
            backup.save()
            
            logger.error(f"Backup creation failed: {e}")
            return {
                'status': 'error',
                'message': f'Backup failed: {str(e)}'
            }
    
    def create_update_backup(self, system_update):
        """Create a backup before system update"""
        backup_name = f"Pre-Update Backup - v{system_update.Version_Number}"
        
        backup = SystemBackup.objects.create(
            Backup_Name=backup_name,
            Backup_Type='auto_update',
            Status='creating',
            Description=f'Automatic backup before updating to version {system_update.Version_Number}',
            Related_Update=system_update,
            Created_By='System Update',
            Backup_Path='pending'
        )
        
        try:
            # Create backup directory
            backup_dir = self._create_backup_directory(backup)
            backup.Backup_Path = backup_dir
            backup.save()
            
            # Perform backup
            self._perform_backup(backup, backup_dir)
            
            # Calculate backup size
            backup.Backup_Size = self._calculate_directory_size(backup_dir)
            backup.Status = 'completed'
            backup.save()
            
            return backup_dir
            
        except Exception as e:
            backup.Status = 'failed'
            backup.Error_Message = str(e)
            backup.save()
            raise Exception(f"Backup creation failed: {str(e)}")
    
    def restore_backup(self, backup, restored_by='System'):
        """Restore a backup"""
        if not backup.can_restore():
            return {
                'status': 'error',
                'message': 'Backup cannot be restored'
            }
        
        backup.Status = 'restoring'
        backup.save()
        
        try:
            # Create a safety backup first
            safety_backup_name = f"Safety Backup - Before Restore {backup.id}"
            safety_result = self.create_manual_backup(
                name=safety_backup_name,
                description=f"Safety backup before restoring backup: {backup.Backup_Name}",
                created_by=restored_by
            )
            
            if safety_result['status'] != 'success':
                raise Exception("Failed to create safety backup")
            
            # Restore files
            self._restore_files(backup.Backup_Path)
            
            # Run migrations
            subprocess.run([
                'python', 'manage.py', 'migrate'
            ], cwd=settings.BASE_DIR, check=True, capture_output=True)
            
            # Update backup status
            backup.Status = 'restored'
            backup.Restored_At = timezone.now()
            backup.Restored_By = restored_by
            backup.save()
            
            return {
                'status': 'success',
                'message': f'Backup "{backup.Backup_Name}" restored successfully'
            }
            
        except Exception as e:
            backup.Status = 'completed'  # Revert to completed status
            backup.Error_Message = f"Restore failed: {str(e)}"
            backup.save()
            
            logger.error(f"Backup restore failed: {e}")
            return {
                'status': 'error',
                'message': f'Restore failed: {str(e)}'
            }
    
    def _create_backup_directory(self, backup):
        """Create a unique backup directory"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        dir_name = f"backup_{backup.id}_{timestamp}"
        backup_dir = os.path.join(self.backup_base_path, dir_name)
        os.makedirs(backup_dir, exist_ok=True)
        return backup_dir
    
    def _perform_backup(self, backup, backup_dir):
        """Perform the actual backup"""
        # Define what to backup
        backup_items = []
        
        if backup.Has_Database:
            # Backup database
            db_path = os.path.join(settings.BASE_DIR, 'db.sqlite3')
            if os.path.exists(db_path):
                shutil.copy2(db_path, os.path.join(backup_dir, 'db.sqlite3'))
                backup_items.append('Database')
        
        if backup.Has_Code:
            # Backup code directories
            code_dirs = ['app/', 'opw/']
            for dir_name in code_dirs:
                src = os.path.join(settings.BASE_DIR, dir_name)
                if os.path.exists(src):
                    dst = os.path.join(backup_dir, dir_name)
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                    backup_items.append(dir_name)
            
            # Backup critical files
            critical_files = ['manage.py', 'requirements.txt']
            for file_name in critical_files:
                src = os.path.join(settings.BASE_DIR, file_name)
                if os.path.exists(src):
                    shutil.copy2(src, os.path.join(backup_dir, file_name))
                    backup_items.append(file_name)
        
        if backup.Has_Static:
            # Backup static files
            static_dir = os.path.join(settings.BASE_DIR, 'static/')
            if os.path.exists(static_dir):
                dst = os.path.join(backup_dir, 'static/')
                shutil.copytree(static_dir, dst, dirs_exist_ok=True)
                backup_items.append('Static files')
        
        if backup.Has_Media:
            # Backup media files
            media_dir = os.path.join(settings.BASE_DIR, 'media/')
            if os.path.exists(media_dir):
                dst = os.path.join(backup_dir, 'media/')
                shutil.copytree(media_dir, dst, dirs_exist_ok=True)
                backup_items.append('Media files')
        
        # Create backup info file
        info_file = os.path.join(backup_dir, 'backup_info.txt')
        with open(info_file, 'w') as f:
            f.write(f"Backup Name: {backup.Backup_Name}\n")
            f.write(f"Created At: {backup.Created_At}\n")
            f.write(f"Created By: {backup.Created_By}\n")
            f.write(f"Backup Items: {', '.join(backup_items)}\n")
            f.write(f"Description: {backup.Description}\n")
    
    def _restore_files(self, backup_path):
        """Restore files from backup"""
        if not os.path.exists(backup_path):
            raise Exception("Backup path does not exist")
        
        # Restore files
        for item in os.listdir(backup_path):
            if item == 'backup_info.txt':
                continue
                
            src = os.path.join(backup_path, item)
            dst = os.path.join(settings.BASE_DIR, item)
            
            # Remove existing destination if it exists
            if os.path.exists(dst):
                if os.path.isdir(dst):
                    shutil.rmtree(dst)
                else:
                    os.remove(dst)
            
            # Copy from backup
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
    
    def _calculate_directory_size(self, path):
        """Calculate total size of a directory"""
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if os.path.exists(filepath):
                    total_size += os.path.getsize(filepath)
        return total_size
    
    def cleanup_old_backups(self, max_count=None):
        """Clean up old backups based on settings"""
        from app.models import UpdateSettings
        
        if max_count is None:
            settings_obj = UpdateSettings.load()
            max_count = settings_obj.Max_Backup_Count
        
        # Get all auto_update backups ordered by creation date
        auto_backups = SystemBackup.objects.filter(
            Backup_Type='auto_update',
            Status='completed'
        ).order_by('-Created_At')
        
        # Delete old backups if we exceed the limit
        if auto_backups.count() > max_count:
            for backup in auto_backups[max_count:]:
                if backup.can_delete():
                    backup.delete_backup_files()
                    backup.delete()
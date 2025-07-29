import os
import json
import requests
import zipfile
import shutil
import subprocess
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.core.files.storage import default_storage
from app.models import SystemUpdate, UpdateSettings
import logging

logger = logging.getLogger(__name__)

class GitHubUpdateService:
    def __init__(self):
        self.settings = UpdateSettings.load()
        self.api_base = "https://api.github.com"
        self.repo = self.settings.GitHub_Repository
        
    def check_for_updates(self):
        """Check GitHub for new releases"""
        try:
            url = f"{self.api_base}/repos/{self.repo}/releases"
            
            # Get only stable releases unless beta/dev channel is selected
            if self.settings.Update_Channel == 'stable':
                url += "?prerelease=false"
            
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            releases = response.json()
            current_version = self.settings.Current_Version
            
            new_updates = []
            for release in releases:
                version = release['tag_name'].lstrip('v')
                
                # Skip if this version already exists
                if SystemUpdate.objects.filter(Version_Number=version).exists():
                    continue
                
                # Check if this is a newer version
                if self._is_newer_version(version, current_version):
                    update_data = self._parse_release_data(release)
                    new_updates.append(update_data)
            
            # Update last check time
            self.settings.Last_Check = timezone.now()
            self.settings.save()
            
            return {
                'status': 'success',
                'updates_available': len(new_updates) > 0,
                'updates': new_updates
            }
            
        except requests.RequestException as e:
            logger.error(f"GitHub API error: {e}")
            return {
                'status': 'error',
                'message': f'Failed to connect to GitHub: {str(e)}'
            }
        except Exception as e:
            logger.error(f"Update check error: {e}")
            return {
                'status': 'error',
                'message': f'Update check failed: {str(e)}'
            }
    
    def _parse_release_data(self, release):
        """Parse GitHub release data into our format"""
        return {
            'version': release['tag_name'].lstrip('v'),
            'title': release['name'] or release['tag_name'],
            'description': release['body'] or 'No description available',
            'release_date': datetime.strptime(release['published_at'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc),
            'download_url': release['zipball_url'],
            'file_size': 0  # Will be determined during download
        }
    
    def _is_newer_version(self, version1, version2):
        """Compare version strings"""
        try:
            # Simple version comparison - can be enhanced for semantic versioning
            v1_parts = [int(x) for x in version1.split('.')]
            v2_parts = [int(x) for x in version2.split('.')]
            
            # Pad shorter version with zeros
            max_len = max(len(v1_parts), len(v2_parts))
            v1_parts.extend([0] * (max_len - len(v1_parts)))
            v2_parts.extend([0] * (max_len - len(v2_parts)))
            
            return v1_parts > v2_parts
        except ValueError:
            # Fallback to string comparison
            return version1 > version2
    
    def create_system_updates(self, updates_data):
        """Create SystemUpdate objects from GitHub data"""
        created_updates = []
        
        for update_data in updates_data:
            update, created = SystemUpdate.objects.get_or_create(
                Version_Number=update_data['version'],
                defaults={
                    'Update_Title': update_data['title'],
                    'Description': update_data['description'],
                    'Release_Date': update_data['release_date'],
                    'Download_URL': update_data['download_url'],
                    'File_Size': update_data['file_size'],
                    'Status': 'available'
                }
            )
            
            if created:
                created_updates.append(update)
        
        return created_updates


class UpdateDownloadService:
    def __init__(self, system_update):
        self.update = system_update
        self.download_path = os.path.join(settings.BASE_DIR, 'temp', 'updates')
        self.backup_path = os.path.join(settings.BASE_DIR, 'backups')
        
        # Ensure directories exist
        os.makedirs(self.download_path, exist_ok=True)
        os.makedirs(self.backup_path, exist_ok=True)
    
    def download_update(self):
        """Download update from GitHub"""
        try:
            self.update.Status = 'downloading'
            self.update.Started_At = timezone.now()
            self.update.Progress = 0
            self.update.save()
            
            response = requests.get(self.update.Download_URL, stream=True, timeout=30)
            response.raise_for_status()
            
            # Get file size
            total_size = int(response.headers.get('content-length', 0))
            self.update.File_Size = total_size
            self.update.save()
            
            # Download file
            filename = f"update_{self.update.Version_Number}.zip"
            filepath = os.path.join(self.download_path, filename)
            
            downloaded = 0
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Update progress
                        if total_size > 0:
                            progress = int((downloaded / total_size) * 100)
                            self.update.Progress = progress
                            self.update.Downloaded_Bytes = downloaded
                            self.update.save()
            
            # Verify download
            if os.path.getsize(filepath) == total_size or total_size == 0:
                self.update.Status = 'ready'
                self.update.Progress = 100
                self.update.save()
                
                return {'status': 'success', 'filepath': filepath}
            else:
                self.update.Status = 'failed'
                self.update.Error_Message = 'Download verification failed'
                self.update.save()
                return {'status': 'error', 'message': 'Download verification failed'}
                
        except requests.RequestException as e:
            self.update.Status = 'failed'
            self.update.Error_Message = f'Download error: {str(e)}'
            self.update.save()
            return {'status': 'error', 'message': str(e)}
        except Exception as e:
            self.update.Status = 'failed'
            self.update.Error_Message = f'Unexpected error: {str(e)}'
            self.update.save()
            return {'status': 'error', 'message': str(e)}


class UpdateInstallService:
    def __init__(self, system_update):
        self.update = system_update
        self.backup_path = os.path.join(settings.BASE_DIR, 'backups')
        self.temp_path = os.path.join(settings.BASE_DIR, 'temp', 'updates')
        
    def create_backup(self):
        """Create backup of current system"""
        try:
            backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            backup_dir = os.path.join(self.backup_path, backup_name)
            
            # Create backup directory
            os.makedirs(backup_dir, exist_ok=True)
            
            # Backup critical files and directories
            critical_paths = [
                'app/',
                'opw/',
                'manage.py',
                'db.sqlite3',
                'requirements.txt'
            ]
            
            for path in critical_paths:
                src = os.path.join(settings.BASE_DIR, path)
                if os.path.exists(src):
                    dst = os.path.join(backup_dir, path)
                    if os.path.isdir(src):
                        shutil.copytree(src, dst, dirs_exist_ok=True)
                    else:
                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                        shutil.copy2(src, dst)
            
            return backup_dir
            
        except Exception as e:
            logger.error(f"Backup creation failed: {e}")
            raise Exception(f"Backup creation failed: {str(e)}")
    
    def install_update(self):
        """Install the downloaded update"""
        try:
            self.update.Status = 'installing'
            self.update.Progress = 0
            self.update.save()
            
            # Create backup if enabled
            if UpdateSettings.load().Backup_Before_Update:
                backup_path = self.create_backup()
                self.update.Backup_Path = backup_path
                self.update.Progress = 20
                self.update.save()
            
            # Extract update
            update_file = os.path.join(self.temp_path, f"update_{self.update.Version_Number}.zip")
            extract_path = os.path.join(self.temp_path, f"extracted_{self.update.Version_Number}")
            
            with zipfile.ZipFile(update_file, 'r') as zip_ref:
                zip_ref.extractall(extract_path)
            
            self.update.Progress = 50
            self.update.save()
            
            # Find the extracted directory (GitHub creates a subdirectory)
            extracted_dirs = [d for d in os.listdir(extract_path) if os.path.isdir(os.path.join(extract_path, d))]
            if not extracted_dirs:
                raise Exception("No extracted directory found")
            
            source_dir = os.path.join(extract_path, extracted_dirs[0])
            
            # Copy files to project directory
            self._copy_update_files(source_dir)
            
            self.update.Progress = 80
            self.update.save()
            
            # Run post-install tasks
            self._run_post_install_tasks()
            
            self.update.Status = 'completed'
            self.update.Progress = 100
            self.update.Completed_At = timezone.now()
            self.update.save()
            
            # Update current version
            settings_obj = UpdateSettings.load()
            settings_obj.Current_Version = self.update.Version_Number
            settings_obj.save()
            
            return {'status': 'success'}
            
        except Exception as e:
            self.update.Status = 'failed'
            self.update.Error_Message = str(e)
            self.update.save()
            return {'status': 'error', 'message': str(e)}
    
    def _copy_update_files(self, source_dir):
        """Copy update files to project directory"""
        # Files/directories to exclude from copying
        exclude_patterns = [
            '.git',
            '.gitignore',
            'README.md',
            'LICENSE',
            'db.sqlite3',
            '__pycache__',
            '*.pyc',
            'temp/',
            'backups/',
            'static/background/'
        ]
        
        for root, dirs, files in os.walk(source_dir):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if not any(d.startswith(pattern.rstrip('/*')) for pattern in exclude_patterns)]
            
            for file in files:
                # Skip excluded files
                if any(file.endswith(pattern.lstrip('*')) or file == pattern for pattern in exclude_patterns):
                    continue
                
                src_file = os.path.join(root, file)
                rel_path = os.path.relpath(src_file, source_dir)
                dst_file = os.path.join(settings.BASE_DIR, rel_path)
                
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                
                # Copy file
                shutil.copy2(src_file, dst_file)
    
    def _run_post_install_tasks(self):
        """Run post-installation tasks"""
        try:
            # Run database migrations
            subprocess.run([
                'python', 'manage.py', 'migrate'
            ], cwd=settings.BASE_DIR, check=True, capture_output=True)
            
            # Collect static files
            subprocess.run([
                'python', 'manage.py', 'collectstatic', '--noinput'
            ], cwd=settings.BASE_DIR, check=True, capture_output=True)
            
        except subprocess.CalledProcessError as e:
            logger.warning(f"Post-install task failed: {e}")
            # Don't fail the entire update for post-install issues
    
    def rollback_update(self):
        """Rollback to previous version"""
        try:
            if not self.update.Backup_Path or not os.path.exists(self.update.Backup_Path):
                return {'status': 'error', 'message': 'No backup available for rollback'}
            
            self.update.Status = 'rollback'
            self.update.save()
            
            # Restore from backup
            backup_dir = self.update.Backup_Path
            
            # Copy backup files back
            for root, dirs, files in os.walk(backup_dir):
                for file in files:
                    src_file = os.path.join(root, file)
                    rel_path = os.path.relpath(src_file, backup_dir)
                    dst_file = os.path.join(settings.BASE_DIR, rel_path)
                    
                    # Create directory if it doesn't exist
                    os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                    
                    # Copy file
                    shutil.copy2(src_file, dst_file)
            
            # Run migrations to ensure database consistency
            subprocess.run([
                'python', 'manage.py', 'migrate'
            ], cwd=settings.BASE_DIR, check=True, capture_output=True)
            
            return {'status': 'success'}
            
        except Exception as e:
            return {'status': 'error', 'message': str(e)}


def cleanup_old_backups():
    """Clean up old backup files"""
    try:
        settings_obj = UpdateSettings.load()
        backup_path = os.path.join(settings.BASE_DIR, 'backups')
        
        if not os.path.exists(backup_path):
            return
        
        # Get all backup directories
        backups = []
        for item in os.listdir(backup_path):
            item_path = os.path.join(backup_path, item)
            if os.path.isdir(item_path) and item.startswith('backup_'):
                backups.append((item_path, os.path.getctime(item_path)))
        
        # Sort by creation time (newest first)
        backups.sort(key=lambda x: x[1], reverse=True)
        
        # Remove old backups
        if len(backups) > settings_obj.Max_Backup_Count:
            for backup_path, _ in backups[settings_obj.Max_Backup_Count:]:
                shutil.rmtree(backup_path)
                logger.info(f"Removed old backup: {backup_path}")
        
    except Exception as e:
        logger.error(f"Backup cleanup error: {e}")


def auto_check_updates():
    """Automatically check for updates based on settings"""
    try:
        settings_obj = UpdateSettings.load()
        
        if not settings_obj.Last_Check:
            # First time check
            should_check = True
        else:
            # Check if enough time has passed
            time_since_check = timezone.now() - settings_obj.Last_Check
            should_check = time_since_check.total_seconds() >= (settings_obj.Check_Interval_Hours * 3600)
        
        if should_check:
            service = GitHubUpdateService()
            result = service.check_for_updates()
            
            if result['status'] == 'success' and result['updates_available']:
                # Create update objects
                service.create_system_updates(result['updates'])
                
                # Auto-download if enabled
                if settings_obj.Auto_Download:
                    for update_data in result['updates']:
                        update = SystemUpdate.objects.get(Version_Number=update_data['version'])
                        download_service = UpdateDownloadService(update)
                        download_result = download_service.download_update()
                        
                        # Auto-install if enabled and download successful
                        if settings_obj.Auto_Install and download_result['status'] == 'success':
                            install_service = UpdateInstallService(update)
                            install_service.install_update()
            
            # Cleanup old backups
            cleanup_old_backups()
            
    except Exception as e:
        logger.error(f"Auto update check failed: {e}")
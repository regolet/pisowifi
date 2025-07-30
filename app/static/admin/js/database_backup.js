// Database Backup JavaScript functionality
(function() {
    'use strict';
    
    // Prevent multiple executions
    if (window.databaseBackupLoaded) {
        return;
    }
    window.databaseBackupLoaded = true;

    let progressUpdateInterval = null;
    let currentBackupId = null;

    // Create backup functions
    function createBackup(backupType) {
        const backupName = prompt(`Enter name for ${backupType} backup:`, `${backupType.charAt(0).toUpperCase() + backupType.slice(1)} Backup ${new Date().toLocaleString()}`);
        
        if (!backupName) return;
        
        const data = {
            backup_name: backupName,
            backup_type: backupType,
            description: `${backupType.charAt(0).toUpperCase() + backupType.slice(1)} database backup`,
            compressed: true
        };
        
        startBackupOperation(data);
    }

    function showCustomBackupDialog() {
        document.getElementById('custom-backup-modal').style.display = 'block';
        document.getElementById('backup-name').value = `Custom Backup ${new Date().toLocaleString()}`;
    }

    function hideCustomBackupDialog() {
        document.getElementById('custom-backup-modal').style.display = 'none';
    }

    function createCustomBackup() {
        const backupName = document.getElementById('backup-name').value.trim();
        const description = document.getElementById('backup-description').value.trim();
        const compressed = document.getElementById('compress-backup').checked;
        
        if (!backupName) {
            alert('Please enter a backup name');
            return;
        }
        
        const data = {
            backup_name: backupName,
            backup_type: 'custom',
            description: description,
            compressed: compressed
        };
        
        hideCustomBackupDialog();
        startBackupOperation(data);
    }

    function startBackupOperation(data) {
        showProgressModal('Creating Backup...');
        
        fetch('/admin/app/databasebackup/create-backup/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        })
        .then(response => response.json())
        .then(result => {
            if (result.status === 'success') {
                currentBackupId = result.backup_id;
                startProgressTracking(result.backup_id);
                showNotification(result.message, 'success');
            } else {
                hideProgressModal();
                showNotification('Error: ' + result.message, 'error');
            }
        })
        .catch(error => {
            hideProgressModal();
            showNotification('Network error: ' + error, 'error');
        });
    }

    // Backup management functions
    function downloadBackup(backupId) {
        window.location.href = `/admin/app/databasebackup/${backupId}/download/`;
    }

    function restoreBackup(backupId) {
        if (!confirm('Are you sure you want to restore this backup? This will overwrite current data and cannot be undone.')) {
            return;
        }
        
        showProgressModal('Restoring Backup...');
        currentBackupId = backupId;
        
        fetch(`/admin/app/databasebackup/${backupId}/restore/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'Content-Type': 'application/json',
            }
        })
        .then(response => response.json())
        .then(result => {
            if (result.status === 'success') {
                startProgressTracking(backupId);
                showNotification(result.message, 'success');
            } else {
                hideProgressModal();
                showNotification('Error: ' + result.message, 'error');
            }
        })
        .catch(error => {
            hideProgressModal();
            showNotification('Network error: ' + error, 'error');
        });
    }

    function deleteBackup(backupId) {
        if (!confirm('Are you sure you want to delete this backup? This action cannot be undone.')) {
            return;
        }
        
        fetch(`/admin/app/databasebackup/${backupId}/delete-backup/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'Content-Type': 'application/json',
            }
        })
        .then(response => response.json())
        .then(result => {
            if (result.status === 'success') {
                showNotification(result.message, 'success');
                setTimeout(() => location.reload(), 1000);
            } else {
                showNotification('Error: ' + result.message, 'error');
            }
        })
        .catch(error => {
            showNotification('Network error: ' + error, 'error');
        });
    }

    function cancelBackup(backupId) {
        if (!confirm('Are you sure you want to cancel this backup?')) {
            return;
        }
        
        fetch(`/admin/app/databasebackup/${backupId}/cancel/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'Content-Type': 'application/json',
            }
        })
        .then(response => response.json())
        .then(result => {
            if (result.status === 'success') {
                showNotification(result.message, 'success');
                setTimeout(() => location.reload(), 1000);
            } else {
                showNotification('Error: ' + result.message, 'error');
            }
        })
        .catch(error => {
            showNotification('Network error: ' + error, 'error');
        });
    }

    // Progress tracking
    function startProgressTracking(backupId) {
        progressUpdateInterval = setInterval(() => {
            fetch(`/admin/app/databasebackup/${backupId}/progress/`)
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    updateProgressDisplay(data.progress, data.current_operation, data.backup_status);
                    
                    if (data.backup_status === 'completed') {
                        stopProgressTracking();
                        showProgressComplete('Operation completed successfully!');
                        setTimeout(() => {
                            hideProgressModal();
                            location.reload();
                        }, 2000);
                    } else if (data.backup_status === 'failed') {
                        stopProgressTracking();
                        showProgressError(data.error_message || 'Operation failed');
                    } else if (data.backup_status === 'cancelled') {
                        stopProgressTracking();
                        hideProgressModal();
                        location.reload();
                    }
                }
            })
            .catch(error => {
                console.error('Progress tracking error:', error);
            });
        }, 2000); // Check every 2 seconds
    }

    function stopProgressTracking() {
        if (progressUpdateInterval) {
            clearInterval(progressUpdateInterval);
            progressUpdateInterval = null;
        }
    }

    function updateProgressDisplay(progress, operation, status) {
        const progressBar = document.getElementById('backup-progress-bar');
        const operationText = document.getElementById('progress-operation');
        
        if (progressBar) {
            progressBar.style.width = progress + '%';
            progressBar.textContent = progress + '%';
            
            // Update color based on status
            if (status === 'completed') {
                progressBar.style.background = '#28a745';
            } else if (status === 'failed') {
                progressBar.style.background = '#dc3545';
            } else if (status === 'running') {
                progressBar.style.background = '#007bff';
            }
        }
        
        if (operationText && operation) {
            operationText.textContent = operation;
        }
    }

    // Modal functions
    function showProgressModal(title) {
        document.getElementById('backup-progress-modal').style.display = 'block';
        document.getElementById('progress-title').textContent = title;
        document.getElementById('backup-progress-bar').style.width = '0%';
        document.getElementById('backup-progress-bar').textContent = '0%';
        document.getElementById('progress-operation').textContent = 'Initializing...';
        document.getElementById('progress-close-btn').style.display = 'none';
    }

    function hideProgressModal() {
        document.getElementById('backup-progress-modal').style.display = 'none';
        stopProgressTracking();
        currentBackupId = null;
    }

    function showProgressComplete(message) {
        document.getElementById('progress-title').textContent = 'Complete!';
        document.getElementById('progress-operation').textContent = message;
        document.getElementById('progress-close-btn').style.display = 'inline-block';
    }

    function showProgressError(message) {
        document.getElementById('progress-title').textContent = 'Error';
        document.getElementById('progress-operation').textContent = message;
        document.getElementById('progress-close-btn').style.display = 'inline-block';
        document.getElementById('backup-progress-bar').style.background = '#dc3545';
    }

    // Utility functions
    function showNotification(message, type) {
        const alertClass = type === 'success' ? 'alert-success' : 
                         type === 'error' ? 'alert-danger' : 
                         type === 'info' ? 'alert-info' : 'alert-warning';
        
        const notification = document.createElement('div');
        notification.className = `alert ${alertClass} alert-dismissible fade show position-fixed`;
        notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px; padding: 12px 16px;';
        notification.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span>${message}</span>
                <button type="button" class="close" onclick="this.parentElement.parentElement.remove()" 
                        style="background: none; border: none; font-size: 18px; color: inherit; cursor: pointer; padding: 0; margin-left: 10px;"
                        aria-label="Close">
                    <span aria-hidden="true">&times;</span>
                </button>
            </div>
        `;
        
        document.body.appendChild(notification);
        
        // Auto remove after 5 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 5000);
    }

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    // Initialize when DOM is loaded
    document.addEventListener('DOMContentLoaded', function() {
        // Auto-refresh page every 30 seconds to update backup status
        setInterval(() => {
            if (!progressUpdateInterval) { // Only refresh if not tracking progress
                location.reload();
            }
        }, 30000);
    });

    // Export functions to global scope
    window.createBackup = createBackup;
    window.showCustomBackupDialog = showCustomBackupDialog;
    window.hideCustomBackupDialog = hideCustomBackupDialog;
    window.createCustomBackup = createCustomBackup;
    window.downloadBackup = downloadBackup;
    window.restoreBackup = restoreBackup;
    window.deleteBackup = deleteBackup;
    window.cancelBackup = cancelBackup;
    window.hideProgressModal = hideProgressModal;

})(); // End IIFE
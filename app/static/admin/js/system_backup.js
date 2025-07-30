// System Backup JavaScript functionality

// Create a new backup
function createBackup() {
    const name = prompt("Enter backup name:", `Manual Backup ${new Date().toLocaleString()}`);
    if (!name) return;
    
    const description = prompt("Enter backup description (optional):");
    
    showLoadingOverlay('Creating backup...');
    
    fetch('/admin/app/systembackup/create-backup/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: `name=${encodeURIComponent(name)}&description=${encodeURIComponent(description || '')}`
    })
    .then(response => response.json())
    .then(data => {
        hideLoadingOverlay();
        if (data.status === 'success') {
            showNotification('Backup created successfully!', 'success');
            setTimeout(() => location.reload(), 1000);
        } else {
            showNotification('Backup creation failed: ' + data.message, 'error');
        }
    })
    .catch(error => {
        hideLoadingOverlay();
        showNotification('Network error while creating backup', 'error');
        console.error('Error:', error);
    });
}

// Restore a backup
function restoreBackup(backupId) {
    if (!confirm('Are you sure you want to restore this backup? This will replace the current system files and may require a restart.')) {
        return;
    }
    
    showLoadingOverlay('Restoring backup... Please do not close this page.');
    
    fetch(`/admin/app/systembackup/${backupId}/restore/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json',
        },
    })
    .then(response => response.json())
    .then(data => {
        hideLoadingOverlay();
        if (data.status === 'success') {
            showNotification('Backup restored successfully! Please restart the application.', 'success');
            setTimeout(() => location.reload(), 3000);
        } else {
            showNotification('Restore failed: ' + data.message, 'error');
        }
    })
    .catch(error => {
        hideLoadingOverlay();
        showNotification('Network error while restoring backup', 'error');
        console.error('Error:', error);
    });
}

// Delete a backup
function deleteBackup(backupId) {
    if (!confirm('Are you sure you want to delete this backup? This action cannot be undone.')) {
        return;
    }
    
    showLoadingOverlay('Deleting backup...');
    
    fetch(`/admin/app/systembackup/${backupId}/delete/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json',
        },
    })
    .then(response => response.json())
    .then(data => {
        hideLoadingOverlay();
        if (data.status === 'success') {
            showNotification('Backup deleted successfully!', 'success');
            setTimeout(() => location.reload(), 1000);
        } else {
            showNotification('Delete failed: ' + data.message, 'error');
        }
    })
    .catch(error => {
        hideLoadingOverlay();
        showNotification('Network error while deleting backup', 'error');
        console.error('Error:', error);
    });
}

// Utility functions
function showLoadingOverlay(message) {
    const overlay = document.createElement('div');
    overlay.id = 'backup-loading-overlay';
    overlay.innerHTML = `
        <div class="loading-content">
            <div class="spinner-border text-primary" role="status">
                <span class="sr-only">Loading...</span>
            </div>
            <p class="mt-3">${message}</p>
        </div>
    `;
    document.body.appendChild(overlay);
}

function hideLoadingOverlay() {
    const overlay = document.getElementById('backup-loading-overlay');
    if (overlay) {
        overlay.remove();
    }
}

function showNotification(message, type) {
    const alertClass = type === 'success' ? 'alert-success' : 
                     type === 'error' ? 'alert-danger' : 
                     type === 'info' ? 'alert-info' : 'alert-warning';
    
    const notification = document.createElement('div');
    notification.className = `alert ${alertClass} alert-dismissible fade show position-fixed`;
    notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
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
    // Add Create Backup button if on the backup list page
    if (window.location.pathname.includes('/systembackup/')) {
        const pageHeader = document.querySelector('.content-header') || 
                          document.querySelector('h1') || 
                          document.querySelector('.page-header');
        
        if (pageHeader && window.location.pathname.endsWith('/systembackup/')) {
            const createButton = document.createElement('button');
            createButton.className = 'btn btn-success';
            createButton.innerHTML = '<i class="fas fa-plus"></i> Create Backup';
            createButton.style.cssText = 'margin-left: 15px;';
            createButton.onclick = function(e) {
                e.preventDefault();
                createBackup();
            };
            
            // Find the right place to insert the button
            const headerText = pageHeader.firstChild;
            if (headerText && headerText.nodeType === Node.TEXT_NODE) {
                pageHeader.insertBefore(createButton, headerText.nextSibling);
            } else {
                pageHeader.appendChild(createButton);
            }
        }
    }
    
    // Add action button styles
    const style = document.createElement('style');
    style.textContent = `
        .btn-group .btn {
            margin-right: 5px;
        }
        .btn-group .btn:last-child {
            margin-right: 0;
        }
        #backup-loading-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.7);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 10000;
        }
        .loading-content {
            background: white;
            padding: 30px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
        }
        .loading-content p {
            margin: 0;
            color: #333;
            font-size: 16px;
        }
    `;
    document.head.appendChild(style);
});
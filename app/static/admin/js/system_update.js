// System Update JavaScript functionality

let updateProgressInterval = null;

// Check for updates from GitHub
function checkForUpdates() {
    showLoadingOverlay('Checking for updates...');
    
    fetch('/admin/app/systemupdate/check-updates/', {
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
            if (data.updates_available) {
                showNotification('Updates available!', 'success');
                setTimeout(() => location.reload(), 1000);
            } else {
                showNotification('System is up to date', 'info');
            }
        } else {
            showNotification('Error checking for updates: ' + data.message, 'error');
        }
    })
    .catch(error => {
        hideLoadingOverlay();
        showNotification('Network error while checking for updates', 'error');
        console.error('Error:', error);
    });
}

// Start download for a specific update
function startDownload(updateId) {
    showLoadingOverlay('Starting download...');
    
    fetch(`/admin/app/systemupdate/${updateId}/download/`, {
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
            showNotification('Download started', 'success');
            startProgressTracking(updateId);
        } else {
            showNotification('Error starting download: ' + data.message, 'error');
        }
    })
    .catch(error => {
        hideLoadingOverlay();
        showNotification('Network error while starting download', 'error');
        console.error('Error:', error);
    });
}

// Pause download
function pauseDownload(updateId) {
    fetch(`/admin/app/systemupdate/${updateId}/pause/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json',
        },
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            showNotification('Download paused', 'info');
            stopProgressTracking();
        }
    });
}

// Install update
function installUpdate(updateId) {
    if (!confirm('Are you sure you want to install this update? The system will be temporarily unavailable.')) {
        return;
    }
    
    showLoadingOverlay('Installing update... Please do not close this page.');
    
    fetch(`/admin/app/systemupdate/${updateId}/install/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json',
        },
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            showNotification('Update installation started', 'success');
            startInstallTracking(updateId);
        } else {
            hideLoadingOverlay();
            showNotification('Error installing update: ' + data.message, 'error');
        }
    })
    .catch(error => {
        hideLoadingOverlay();
        showNotification('Network error while installing update', 'error');
        console.error('Error:', error);
    });
}

// Rollback update
function rollbackUpdate(updateId) {
    if (!confirm('Are you sure you want to rollback this update? This will restore the previous version.')) {
        return;
    }
    
    showLoadingOverlay('Rolling back update...');
    
    fetch(`/admin/app/systemupdate/${updateId}/rollback/`, {
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
            showNotification('Rollback completed successfully', 'success');
            setTimeout(() => location.reload(), 2000);
        } else {
            showNotification('Error during rollback: ' + data.message, 'error');
        }
    })
    .catch(error => {
        hideLoadingOverlay();
        showNotification('Network error during rollback', 'error');
        console.error('Error:', error);
    });
}

// Progress tracking for downloads
function startProgressTracking(updateId) {
    updateProgressInterval = setInterval(() => {
        fetch(`/admin/app/systemupdate/${updateId}/progress/`)
        .then(response => response.json())
        .then(data => {
            updateProgressDisplay(updateId, data.progress, data.status);
            
            if (data.status === 'completed' || data.status === 'failed') {
                stopProgressTracking();
                setTimeout(() => location.reload(), 1000);
            }
        })
        .catch(error => {
            console.error('Progress tracking error:', error);
        });
    }, 2000); // Check every 2 seconds
}

// Progress tracking for installations
function startInstallTracking(updateId) {
    updateProgressInterval = setInterval(() => {
        fetch(`/admin/app/systemupdate/${updateId}/install-progress/`)
        .then(response => response.json())
        .then(data => {
            updateProgressDisplay(updateId, data.progress, data.status);
            
            if (data.status === 'completed') {
                stopProgressTracking();
                hideLoadingOverlay();
                showNotification('Update installed successfully! Reloading...', 'success');
                setTimeout(() => location.reload(), 2000);
            } else if (data.status === 'failed') {
                stopProgressTracking();
                hideLoadingOverlay();
                showNotification('Update installation failed: ' + data.error, 'error');
                setTimeout(() => location.reload(), 1000);
            }
        })
        .catch(error => {
            console.error('Install tracking error:', error);
        });
    }, 3000); // Check every 3 seconds for installations
}

function stopProgressTracking() {
    if (updateProgressInterval) {
        clearInterval(updateProgressInterval);
        updateProgressInterval = null;
    }
}

// Update progress display
function updateProgressDisplay(updateId, progress, status) {
    const progressBar = document.querySelector(`tr[data-update-id="${updateId}"] .progress-bar`);
    if (progressBar) {
        progressBar.style.width = progress + '%';
        progressBar.textContent = progress + '%';
        
        // Update color based on status
        progressBar.className = 'progress-bar';
        if (status === 'completed') {
            progressBar.classList.add('bg-success');
        } else if (status === 'failed') {
            progressBar.classList.add('bg-danger');
        } else if (status === 'installing') {
            progressBar.classList.add('bg-warning');
        } else {
            progressBar.classList.add('bg-info');
        }
    }
}

// Utility functions
function showLoadingOverlay(message) {
    const overlay = document.createElement('div');
    overlay.id = 'update-loading-overlay';
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
    const overlay = document.getElementById('update-loading-overlay');
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
    // Add check updates button if it doesn't exist
    const addButton = document.querySelector('.addlink');
    if (addButton) {
        const checkButton = document.createElement('a');
        checkButton.className = 'btn btn-primary ml-2';
        checkButton.href = '#';
        checkButton.innerHTML = '<i class="fas fa-sync"></i> Check for Updates';
        checkButton.onclick = function(e) {
            e.preventDefault();
            checkForUpdates();
        };
        addButton.parentNode.insertBefore(checkButton, addButton.nextSibling);
    }
    
    // Add update-id data attributes to table rows for progress tracking
    const rows = document.querySelectorAll('#result_list tbody tr');
    rows.forEach((row, index) => {
        const link = row.querySelector('a[href*="/change/"]');
        if (link) {
            const href = link.getAttribute('href');
            const match = href.match(/\/(\d+)\/change\//);
            if (match) {
                row.setAttribute('data-update-id', match[1]);
            }
        }
    });
});
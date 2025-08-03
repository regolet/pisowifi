// System Update JavaScript functionality
(function() {
    'use strict';
    
    // Prevent multiple executions
    if (window.systemUpdateLoaded) {
        return;
    }
    window.systemUpdateLoaded = true;

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
    .then(handleJsonResponse)
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
        handleFetchError(error, 'Network error while checking for updates');
    });
}

// Start download for a specific update
    function startDownload(updateId) {
    // Update button to loading state
    updateDownloadButtonState(updateId, 'loading');
    showLoadingOverlay('Starting download...');
    
    fetch(`/admin/app/systemupdate/${updateId}/download/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json',
        },
    })
    .then(handleJsonResponse)
    .then(data => {
        hideLoadingOverlay();
        if (data.status === 'success') {
            showNotification('Download started', 'success');
            startProgressTracking(updateId);
        } else {
            showNotification('Error starting download: ' + data.message, 'error');
            updateDownloadButtonState(updateId, 'error');
        }
    })
    .catch(error => {
        hideLoadingOverlay();
        handleFetchError(error, 'Network error while starting download');
        updateDownloadButtonState(updateId, 'error');
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
    .then(handleJsonResponse)
    .then(data => {
        if (data.status === 'success') {
            showNotification('Download paused', 'info');
            stopProgressTracking();
        }
    });
}

// Install update
    function installUpdate(updateId) {
    if (!confirm('Are you sure you want to install this update? The system will be temporarily unavailable.\n\nNOTE: During installation, the server may restart which will log you out. This is normal - just log back in after a few moments.')) {
        return;
    }
    
    showLoadingOverlay('Installing update... Please do not close this page.');
    showTerminal(updateId);
    
    // Token authentication handles everything - no session management needed
    
    fetch(`/admin/app/systemupdate/${updateId}/install/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json',
        },
    })
    .then(handleJsonResponse)
    .then(data => {
        if (data.status === 'success') {
            showNotification('Update installation started', 'success');
            startInstallTracking(updateId);
        } else {
            hideLoadingOverlay();
            hideTerminal();
            if (data.requires_noreload) {
                alert('IMPORTANT: Update cannot be installed while auto-reload is active!\n\n' +
                      'Please follow these steps:\n\n' +
                      '1. Stop the server (Ctrl+C in terminal)\n' +
                      '2. Restart with: python manage.py runserver 3000 --noreload\n' +
                      '3. Try the installation again\n\n' +
                      'This prevents the server from restarting mid-update.');
            } else {
                showNotification('Error installing update: ' + data.message, 'error');
            }
        }
    })
    .catch(error => {
        hideLoadingOverlay();
        hideTerminal();
        handleFetchError(error, 'Network error while installing update');
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
    .then(handleJsonResponse)
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

// Remove update
    function removeUpdate(updateId) {
    if (!confirm('Are you sure you want to remove this update? This will delete all downloaded files and the update record.')) {
        return;
    }
    
    showLoadingOverlay('Removing update...');
    
    fetch(`/admin/app/systemupdate/${updateId}/remove/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json',
        },
    })
    .then(handleJsonResponse)
    .then(data => {
        hideLoadingOverlay();
        if (data.status === 'success') {
            showNotification('Update removed successfully', 'success');
            setTimeout(() => location.reload(), 1000);
        } else {
            showNotification('Error removing update: ' + data.message, 'error');
        }
    })
    .catch(error => {
        hideLoadingOverlay();
        handleFetchError(error, 'Network error while removing update');
    });
}

// Repair update
    function repairUpdate(updateId) {
    if (!confirm('Are you sure you want to repair this update? This will re-run post-installation tasks.')) {
        return;
    }
    
    showLoadingOverlay('Repairing update...');
    showTerminal(updateId);
    
    fetch(`/admin/app/systemupdate/${updateId}/repair/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json',
        },
    })
    .then(handleJsonResponse)
    .then(data => {
        if (data.status === 'success') {
            showNotification('Update repair started', 'success');
            startInstallTracking(updateId);
        } else {
            hideLoadingOverlay();
            hideTerminal();
            showNotification('Error starting repair: ' + data.message, 'error');
        }
    })
    .catch(error => {
        hideLoadingOverlay();
        hideTerminal();
        handleFetchError(error, 'Network error while starting repair');
    });
}

// Retry update
    function retryUpdate(updateId) {
    if (!confirm('Are you sure you want to retry this update installation?')) {
        return;
    }
    
    showLoadingOverlay('Retrying update installation...');
    showTerminal(updateId);
    
    fetch(`/admin/app/systemupdate/${updateId}/retry/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json',
        },
    })
    .then(handleJsonResponse)
    .then(data => {
        if (data.status === 'success') {
            showNotification('Update retry started', 'success');
            startInstallTracking(updateId);
        } else {
            hideLoadingOverlay();
            hideTerminal();
            showNotification('Error starting retry: ' + data.message, 'error');
        }
    })
    .catch(error => {
        hideLoadingOverlay();
        hideTerminal();
        handleFetchError(error, 'Network error while starting retry');
    });
}

// Progress tracking for downloads
    function startProgressTracking(updateId) {
    updateProgressInterval = setInterval(() => {
        fetch(`/admin/app/systemupdate/${updateId}/progress/`)
        .then(response => response.json())
        .then(data => {
            updateProgressDisplay(updateId, data.progress, data.status);
            
            if (data.status === 'ready') {
                stopProgressTracking();
                updateDownloadButtonState(updateId, 'ready');
                showNotification('Download completed! Ready to install.', 'success');
            } else if (data.status === 'failed') {
                stopProgressTracking();
                updateDownloadButtonState(updateId, 'failed');
                setTimeout(() => location.reload(), 1000);
            }
        })
        .catch(error => {
            console.error('Progress tracking error:', error);
            // Don't stop tracking on individual errors, just log them
        });
    }, 2000); // Check every 2 seconds
}

// Progress tracking for installations
    function startInstallTracking(updateId) {
    updateProgressInterval = setInterval(() => {
        fetch(`/admin/app/systemupdate/${updateId}/install-progress/`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            // Check if response is JSON or HTML (login page)
            const contentType = response.headers.get("content-type");
            if (contentType && contentType.indexOf("application/json") !== -1) {
                return response.json();
            } else {
                // Likely redirected to login page
                throw new Error('Session expired - please refresh the page and login again');
            }
        })
        .then(data => {
            if (data.status === 'error') {
                console.error('Server error in install progress:', data.message);
                stopProgressTracking();
                hideLoadingOverlay();
                hideTerminal();
                showNotification('Installation tracking error: ' + data.message, 'error');
                return;
            }
            
            updateProgressDisplay(updateId, data.progress, data.status);
            
            if (data.status === 'completed') {
                stopProgressTracking();
                hideLoadingOverlay();
                hideTerminal();
                showNotification('Update installed successfully! Reloading...', 'success');
                setTimeout(() => location.reload(), 2000);
            } else if (data.status === 'failed') {
                stopProgressTracking();
                hideLoadingOverlay();
                hideTerminal();
                showNotification('Update installation failed: ' + (data.error || 'Unknown error'), 'error');
                setTimeout(() => location.reload(), 1000);
            }
        })
        .catch(error => {
            console.error('Install tracking error:', error);
            stopProgressTracking();
            hideLoadingOverlay();
            hideTerminal();
            if (error.message.includes('Session expired')) {
                showNotification('Session expired. Please refresh the page and login again.', 'error');
                setTimeout(() => location.reload(), 3000);
            } else {
                showNotification('Connection error during installation tracking', 'error');
            }
        });
        
        // Also fetch installation logs
        fetchInstallationLogs(updateId);
    }, 3000); // Check every 3 seconds for installations
}

    function stopProgressTracking() {
    if (updateProgressInterval) {
        clearInterval(updateProgressInterval);
        updateProgressInterval = null;
    }
    
    // Token auth handles everything - no cleanup needed
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

// Helper function to handle JSON responses and detect authentication errors
function handleJsonResponse(response) {
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    // Check if response is JSON or HTML (login page)
    const contentType = response.headers.get("content-type");
    if (contentType && contentType.indexOf("application/json") !== -1) {
        return response.json();
    } else {
        // Likely redirected to login page
        throw new Error('Session expired - please refresh the page and login again');
    }
}

// Helper function to handle errors consistently
function handleFetchError(error, defaultMessage) {
    console.error('Error:', error);
    if (error.message && error.message.includes('Session expired')) {
        showNotification('Session expired. Please refresh the page and login again.', 'error');
        setTimeout(() => location.reload(), 3000);
    } else {
        showNotification(defaultMessage || 'Network error occurred', 'error');
    }
}

// Terminal functions
    function showTerminal(updateId) {
    const terminal = document.createElement('div');
    terminal.id = 'installation-terminal';
    terminal.innerHTML = `
        <div class="terminal-header">
            <h4><i class="fas fa-terminal"></i> Installation Console</h4>
            <button type="button" class="btn-close" onclick="hideTerminal()"></button>
        </div>
        <div class="terminal-body">
            <div id="terminal-content">Starting installation...</div>
        </div>
    `;
    document.body.appendChild(terminal);
}

    function hideTerminal() {
    const terminal = document.getElementById('installation-terminal');
    if (terminal) {
        terminal.remove();
    }
}

    function fetchInstallationLogs(updateId) {
    fetch(`/admin/app/systemupdate/${updateId}/installation-logs/`)
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        // Check if response is JSON or HTML (login page)
        const contentType = response.headers.get("content-type");
        if (contentType && contentType.indexOf("application/json") !== -1) {
            return response.json();
        } else {
            // Likely redirected to login page
            throw new Error('Session expired - please refresh the page and login again');
        }
    })
    .then(data => {
        if (data.status === 'success') {
            updateTerminalContent(data.logs);
        } else {
            console.error('Error in installation logs response:', data.message);
        }
    })
    .catch(error => {
        console.error('Error fetching installation logs:', error);
        // Don't show error notification for logs as it's not critical
    });
}

    function updateTerminalContent(logs) {
    const terminalContent = document.getElementById('terminal-content');
    if (terminalContent && logs) {
        terminalContent.innerHTML = logs.replace(/\n/g, '<br>');
        terminalContent.scrollTop = terminalContent.scrollHeight;
    }
}

// Button state management
    function updateDownloadButtonState(updateId, state) {
    const row = document.querySelector(`tr[data-update-id="${updateId}"]`);
    if (!row) {
        // Fallback: look for any row containing the update ID
        const allRows = document.querySelectorAll('#result_list tbody tr');
        for (let r of allRows) {
            const link = r.querySelector('a[href*="/change/"]');
            if (link && link.href.includes(`/${updateId}/change/`)) {
                updateButtonsInRow(r, updateId, state);
                return;
            }
        }
        return;
    }
    
    updateButtonsInRow(row, updateId, state);
}

function updateButtonsInRow(row, updateId, state) {
    // Find the action buttons column (usually the last column)
    const actionCell = row.querySelector('td:last-child');
    if (!actionCell) return;
    
    let buttonHtml = '';
    
    switch (state) {
        case 'loading':
            buttonHtml = '<span class="button" style="background-color: #6c757d; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px; white-space: nowrap;"><i class="fas fa-spinner fa-spin" style="margin-right: 3px;"></i>Downloading...</span>';
            break;
        case 'ready':
            buttonHtml = `<a class="button" href="#" onclick="installUpdate(${updateId}); return false;" title="Install update" style="background-color: #28a745; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px; white-space: nowrap;"><i class="fas fa-rocket" style="margin-right: 3px;"></i>Install</a>`;
            break;
        case 'failed':
            buttonHtml = `<a class="button" href="#" onclick="startDownload(${updateId}); return false;" title="Retry download" style="background-color: #007bff; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px; white-space: nowrap;"><i class="fas fa-redo" style="margin-right: 3px;"></i>Retry Download</a>`;
            break;
        case 'error':
            buttonHtml = `<a class="button" href="#" onclick="startDownload(${updateId}); return false;" title="Download update" style="background-color: #007bff; color: white; padding: 4px 8px; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px; white-space: nowrap;"><i class="fas fa-download" style="margin-right: 3px;"></i>Download</a>`;
            break;
    }
    
    if (buttonHtml) {
        actionCell.innerHTML = buttonHtml;
    }
}

    // Initialize when DOM is loaded
    document.addEventListener('DOMContentLoaded', function() {
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
    
    }); // End DOMContentLoaded

    // Export functions to global scope
    window.checkForUpdates = checkForUpdates;
    window.startDownload = startDownload;
    window.pauseDownload = pauseDownload;
    window.installUpdate = installUpdate;
    window.rollbackUpdate = rollbackUpdate;
    window.removeUpdate = removeUpdate;
    window.repairUpdate = repairUpdate;
    window.retryUpdate = retryUpdate;
    window.hideTerminal = hideTerminal;

})(); // End IIFE
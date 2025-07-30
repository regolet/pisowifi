(function() {
    let autoRefreshEnabled = true;
    let refreshInterval = 5000; // 5 seconds
    let refreshTimer;
    let lastRefreshTime = Date.now();
    
    // Add auto-refresh controls to the page
    function addRefreshControls() {
        const toolbar = document.querySelector('.object-tools') || document.querySelector('.actions');
        if (toolbar && !document.getElementById('refresh-controls')) {
            const refreshControls = document.createElement('div');
            refreshControls.id = 'refresh-controls';
            refreshControls.className = 'refresh-controls';
            
            refreshControls.innerHTML = `
                <span class="refresh-status-container">
                    <i class="fas fa-sync-alt" id="refresh-icon"></i>
                    <span id="refresh-status">Auto-refresh: ON</span>
                </span>
                <button type="button" id="toggle-refresh" class="refresh-btn">
                    <i class="fas fa-pause"></i> Pause
                </button>
                <button type="button" id="manual-refresh" class="refresh-btn">
                    <i class="fas fa-sync"></i> Refresh Now
                </button>
                <span class="last-update">
                    Last updated: <span id="last-update">now</span>
                </span>
            `;
            
            toolbar.parentNode.insertBefore(refreshControls, toolbar);
            
            // Add event listeners
            document.getElementById('toggle-refresh').addEventListener('click', toggleAutoRefresh);
            document.getElementById('manual-refresh').addEventListener('click', refreshNow);
        }
    }
    
    // Toggle auto-refresh
    function toggleAutoRefresh() {
        autoRefreshEnabled = !autoRefreshEnabled;
        const toggleBtn = document.getElementById('toggle-refresh');
        const statusSpan = document.getElementById('refresh-status');
        
        if (autoRefreshEnabled) {
            toggleBtn.innerHTML = '<i class="fas fa-pause"></i> Pause';
            statusSpan.textContent = 'Auto-refresh: ON';
            statusSpan.className = 'status-on';
            startAutoRefresh();
        } else {
            toggleBtn.innerHTML = '<i class="fas fa-play"></i> Resume';
            statusSpan.textContent = 'Auto-refresh: OFF';
            statusSpan.className = 'status-off';
            stopAutoRefresh();
        }
    }
    
    // Manual refresh
    function refreshNow() {
        const refreshIcon = document.getElementById('refresh-icon');
        refreshIcon.classList.add('spinning');
        
        // Store current scroll position
        const scrollY = window.scrollY;
        
        // Refresh the page content
        fetch(window.location.href, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
            }
        })
        .then(response => response.text())
        .then(html => {
            // Parse the response and update the table
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const newTable = doc.querySelector('#result_list');
            const currentTable = document.querySelector('#result_list');
            
            if (newTable && currentTable) {
                currentTable.innerHTML = newTable.innerHTML;
            }
            
            // Update last refresh time
            updateLastRefreshTime();
            
            // Restore scroll position
            window.scrollTo(0, scrollY);
            
            // Stop spinning animation
            refreshIcon.classList.remove('spinning');
        })
        .catch(error => {
            console.error('Refresh failed:', error);
            refreshIcon.classList.remove('spinning');
        });
    }
    
    // Update last refresh time display
    function updateLastRefreshTime() {
        const lastUpdateSpan = document.getElementById('last-update');
        if (lastUpdateSpan) {
            const now = new Date();
            lastUpdateSpan.textContent = now.toLocaleTimeString();
            lastRefreshTime = Date.now();
        }
    }
    
    // Start auto-refresh
    function startAutoRefresh() {
        if (refreshTimer) clearInterval(refreshTimer);
        refreshTimer = setInterval(() => {
            if (autoRefreshEnabled && document.visibilityState === 'visible') {
                refreshNow();
            }
        }, refreshInterval);
    }
    
    // Stop auto-refresh
    function stopAutoRefresh() {
        if (refreshTimer) {
            clearInterval(refreshTimer);
            refreshTimer = null;
        }
    }
    
    // Initialize when page loads
    document.addEventListener('DOMContentLoaded', function() {
        // Only add refresh controls on clients changelist page
        if (window.location.pathname.includes('/admin/app/clients/')) {
            addRefreshControls();
            updateLastRefreshTime();
            
            // Start auto-refresh
            if (autoRefreshEnabled) {
                startAutoRefresh();
            }
            
            // Pause auto-refresh when page is not visible
            document.addEventListener('visibilitychange', function() {
                if (document.visibilityState === 'hidden') {
                    stopAutoRefresh();
                } else if (autoRefreshEnabled) {
                    startAutoRefresh();
                }
            });
        }
    });
})();
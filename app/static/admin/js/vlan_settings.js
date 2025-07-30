// VLAN Settings JavaScript functionality
(function() {
    'use strict';
    
    // Prevent multiple executions
    if (window.vlanSettingsLoaded) {
        return;
    }
    window.vlanSettingsLoaded = true;

    function updateVlanIdField() {
        const networkModeField = document.getElementById('id_network_mode');
        const vlanIdField = document.getElementById('id_vlan_id');
        const vlanIdWrapper = vlanIdField ? vlanIdField.closest('.field-vlan_id') : null;
        const vlanIdLabel = vlanIdWrapper ? vlanIdWrapper.querySelector('label') : null;
        
        if (!networkModeField || !vlanIdField) {
            return;
        }
        
        const selectedMode = networkModeField.value;
        
        if (selectedMode === 'vlan') {
            // Enable VLAN ID field for VLAN mode
            vlanIdField.disabled = false;
            vlanIdField.style.backgroundColor = '';
            vlanIdField.style.color = '';
            vlanIdField.required = true;
            if (vlanIdWrapper) {
                vlanIdWrapper.style.opacity = '1';
            }
            if (vlanIdLabel) {
                vlanIdLabel.style.color = '';
                vlanIdLabel.innerHTML = vlanIdLabel.innerHTML.replace(' (disabled)', '');
            }
            
            // Add visual indicator that field is required for VLAN mode
            if (vlanIdLabel && !vlanIdLabel.innerHTML.includes('*')) {
                vlanIdLabel.innerHTML = vlanIdLabel.innerHTML.replace(':', ':*');
            }
        } else {
            // Disable VLAN ID field for USB-to-LAN mode
            vlanIdField.disabled = true;
            vlanIdField.style.backgroundColor = '#f8f9fa';
            vlanIdField.style.color = '#6c757d';
            vlanIdField.required = false;
            if (vlanIdWrapper) {
                vlanIdWrapper.style.opacity = '0.6';
            }
            if (vlanIdLabel) {
                vlanIdLabel.style.color = '#6c757d';
                if (!vlanIdLabel.innerHTML.includes('(disabled)')) {
                    vlanIdLabel.innerHTML = vlanIdLabel.innerHTML.replace(':', ' (disabled):');
                }
                // Remove required indicator
                vlanIdLabel.innerHTML = vlanIdLabel.innerHTML.replace(':*', ':');
            }
        }
    }
    
    function validateVlanId() {
        const vlanIdField = document.getElementById('id_vlan_id');
        const networkModeField = document.getElementById('id_network_mode');
        
        if (!vlanIdField || !networkModeField || networkModeField.value !== 'vlan') {
            return;
        }
        
        const vlanId = parseInt(vlanIdField.value);
        
        if (isNaN(vlanId) || vlanId < 1 || vlanId > 4094) {
            vlanIdField.style.borderColor = '#dc3545';
            vlanIdField.style.boxShadow = '0 0 0 0.2rem rgba(220,53,69,.25)';
            
            // Show validation message
            let errorMsg = vlanIdField.parentNode.querySelector('.vlan-error');
            if (!errorMsg) {
                errorMsg = document.createElement('div');
                errorMsg.className = 'vlan-error';
                errorMsg.style.cssText = 'color: #dc3545; font-size: 12px; margin-top: 4px;';
                vlanIdField.parentNode.appendChild(errorMsg);
            }
            errorMsg.textContent = 'VLAN ID must be between 1 and 4094';
        } else {
            vlanIdField.style.borderColor = '';
            vlanIdField.style.boxShadow = '';
            
            // Remove validation message
            const errorMsg = vlanIdField.parentNode.querySelector('.vlan-error');
            if (errorMsg) {
                errorMsg.remove();
            }
        }
    }
    
    function initializeVlanSettings() {
        const networkModeField = document.getElementById('id_network_mode');
        const vlanIdField = document.getElementById('id_vlan_id');
        
        if (networkModeField) {
            // Set initial state
            updateVlanIdField();
            
            // Add event listener for changes
            networkModeField.addEventListener('change', updateVlanIdField);
        }
        
        if (vlanIdField) {
            // Add VLAN ID validation
            vlanIdField.addEventListener('input', validateVlanId);
            vlanIdField.addEventListener('blur', validateVlanId);
        }
    }
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeVlanSettings);
    } else {
        initializeVlanSettings();
    }
    
    // Also initialize when page loads (fallback)
    window.addEventListener('load', initializeVlanSettings);

})(); // End IIFE
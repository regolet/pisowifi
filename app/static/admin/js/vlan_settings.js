// VLAN Settings JavaScript functionality
(function() {
    'use strict';
    
    // Prevent multiple executions
    if (window.vlanSettingsLoaded) {
        return;
    }
    window.vlanSettingsLoaded = true;

    // Store field references globally for updateVlanIdField
    let globalNetworkModeField = null;
    let globalVlanIdField = null;
    
    function updateVlanIdField() {
        console.log('updateVlanIdField called');
        const networkModeField = globalNetworkModeField || document.getElementById('id_network_mode');
        const vlanIdField = globalVlanIdField || document.getElementById('id_vlan_id');
        const vlanIdWrapper = vlanIdField ? vlanIdField.closest('.field-vlan_id') : null;
        const vlanIdLabel = vlanIdWrapper ? vlanIdWrapper.querySelector('label') : null;
        
        console.log('Elements found:', {
            networkModeField: !!networkModeField,
            vlanIdField: !!vlanIdField,
            vlanIdWrapper: !!vlanIdWrapper,
            vlanIdLabel: !!vlanIdLabel
        });
        
        if (!networkModeField || !vlanIdField) {
            console.log('Required fields not found, exiting');
            return;
        }
        
        const selectedMode = networkModeField.value;
        console.log('Selected mode:', selectedMode);
        
        if (selectedMode === 'vlan') {
            console.log('Enabling VLAN ID field for VLAN mode');
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
            console.log('VLAN ID field enabled, disabled state:', vlanIdField.disabled);
        } else {
            console.log('Disabling VLAN ID field for USB-to-LAN mode');
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
            console.log('VLAN ID field disabled, disabled state:', vlanIdField.disabled);
        }
    }
    
    function validateVlanId() {
        const vlanIdField = globalVlanIdField || document.getElementById('id_vlan_id');
        const networkModeField = globalNetworkModeField || document.getElementById('id_network_mode');
        
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
        // Debug: Log all form fields to console
        console.log('VLAN Settings Debug: Looking for form fields...');
        const allInputs = document.querySelectorAll('input, select');
        allInputs.forEach(input => {
            if (input.id && (input.id.includes('network') || input.id.includes('vlan'))) {
                console.log('Found field:', input.id, input.type, input);
            }
        });
        
        // Try multiple ways to find the fields
        let networkModeField = document.getElementById('id_network_mode');
        let vlanIdField = document.getElementById('id_vlan_id');
        
        // Alternative selectors if IDs don't match
        if (!networkModeField) {
            networkModeField = document.querySelector('select[name="network_mode"]') || 
                              document.querySelector('[name*="network_mode"]');
            console.log('Network mode field found via name selector:', networkModeField);
        }
        
        if (!vlanIdField) {
            vlanIdField = document.querySelector('input[name="vlan_id"]') || 
                         document.querySelector('[name*="vlan_id"]');
            console.log('VLAN ID field found via name selector:', vlanIdField);
        }
        
        console.log('Final field selection:');
        console.log('Network mode field:', networkModeField);
        console.log('VLAN ID field:', vlanIdField);
        
        // Store global references
        globalNetworkModeField = networkModeField;
        globalVlanIdField = vlanIdField;
        
        if (networkModeField) {
            console.log('Network mode field found, current value:', networkModeField.value);
            // Set initial state
            updateVlanIdField();
            
            // Add event listener for changes
            networkModeField.addEventListener('change', function() {
                console.log('Network mode changed to:', networkModeField.value);
                updateVlanIdField();
            });
        } else {
            console.log('Network mode field NOT found');
        }
        
        if (vlanIdField) {
            console.log('VLAN ID field found');
            // Add VLAN ID validation
            vlanIdField.addEventListener('input', validateVlanId);
            vlanIdField.addEventListener('blur', validateVlanId);
        } else {
            console.log('VLAN ID field NOT found');
        }
    }
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            setTimeout(initializeVlanSettings, 100); // Small delay to ensure fields are rendered
        });
    } else {
        setTimeout(initializeVlanSettings, 100);
    }
    
    // Also initialize when page loads (fallback)
    window.addEventListener('load', function() {
        setTimeout(initializeVlanSettings, 200);
    });

})(); // End IIFE
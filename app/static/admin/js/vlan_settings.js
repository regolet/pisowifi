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
        const networkModeField = globalNetworkModeField || document.getElementById('id_network_mode');
        const vlanIdField = globalVlanIdField || document.getElementById('id_vlan_id');
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
    
    function findFields() {
        // Try multiple selectors to find the fields
        const selectors = {
            networkMode: [
                '#id_network_mode',
                'select[name="network_mode"]',
                'select[name*="network_mode"]',
                'select[id*="network_mode"]'
            ],
            vlanId: [
                '#id_vlan_id', 
                'input[name="vlan_id"]',
                'input[name*="vlan_id"]',
                'input[id*="vlan_id"]'
            ]
        };
        
        let networkModeField = null;
        let vlanIdField = null;
        
        // Try each selector until we find the fields
        for (const selector of selectors.networkMode) {
            networkModeField = document.querySelector(selector);
            if (networkModeField) {
                break;
            }
        }
        
        for (const selector of selectors.vlanId) {
            vlanIdField = document.querySelector(selector);
            if (vlanIdField) {
                break;
            }
        }
        
        return { networkModeField, vlanIdField };
    }
    
    function initializeVlanSettings() {
        // Find the fields
        const { networkModeField, vlanIdField } = findFields();
        
        // Store global references
        globalNetworkModeField = networkModeField;
        globalVlanIdField = vlanIdField;
        
        if (networkModeField) {
            // Check if this field is using Select2
            const isSelect2 = networkModeField.classList.contains('select2-hidden-accessible');
            
            // Set initial state
            updateVlanIdField();
            
            if (isSelect2) {
                // For Select2 fields, use jQuery event listener
                if (typeof $ !== 'undefined') {
                    $(networkModeField).on('change', function() {
                        updateVlanIdField();
                    });
                    
                    // Also try Select2-specific events
                    $(networkModeField).on('select2:select', function() {
                        setTimeout(updateVlanIdField, 50); // Small delay to ensure value is updated
                    });
                } else {
                    // Fallback: try to find the Select2 container and add click listener
                    const select2Container = document.querySelector('.select2-container');
                    if (select2Container) {
                        select2Container.addEventListener('click', function() {
                            setTimeout(updateVlanIdField, 100);
                        });
                    }
                }
            } else {
                // For regular select fields, use standard event listener
                networkModeField.addEventListener('change', function() {
                    updateVlanIdField();
                });
            }
        }
        
        if (vlanIdField) {
            // Add VLAN ID validation
            vlanIdField.addEventListener('input', validateVlanId);
            vlanIdField.addEventListener('blur', validateVlanId);
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
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
                console.log('Network mode field found with selector:', selector, networkModeField);
                break;
            }
        }
        
        for (const selector of selectors.vlanId) {
            vlanIdField = document.querySelector(selector);
            if (vlanIdField) {
                console.log('VLAN ID field found with selector:', selector, vlanIdField);
                break;
            }
        }
        
        return { networkModeField, vlanIdField };
    }
    
    function initializeVlanSettings() {
        console.log('VLAN Settings Debug: Initializing...');
        
        // Debug: Log all form fields
        const allInputs = document.querySelectorAll('input, select');
        console.log('All form inputs and selects:', allInputs);
        allInputs.forEach(input => {
            if (input.name || input.id) {
                console.log(`Field: name="${input.name}" id="${input.id}" type="${input.type}"`);
            }
        });
        
        // Find the fields
        const { networkModeField, vlanIdField } = findFields();
        
        console.log('Final field selection:');
        console.log('Network mode field:', networkModeField);
        console.log('VLAN ID field:', vlanIdField);
        
        // Store global references
        globalNetworkModeField = networkModeField;
        globalVlanIdField = vlanIdField;
        
        if (networkModeField) {
            console.log('Network mode field found, current value:', networkModeField.value);
            
            // Check if this field is using Select2
            const isSelect2 = networkModeField.classList.contains('select2-hidden-accessible');
            console.log('Field is using Select2:', isSelect2);
            
            // Set initial state
            updateVlanIdField();
            
            if (isSelect2) {
                // For Select2 fields, use jQuery event listener
                if (typeof $ !== 'undefined') {
                    console.log('Using Select2/jQuery event listener');
                    $(networkModeField).on('change', function() {
                        console.log('Network mode changed via Select2 to:', this.value);
                        updateVlanIdField();
                    });
                    
                    // Also try Select2-specific events
                    $(networkModeField).on('select2:select', function() {
                        console.log('Select2 select event triggered, value:', this.value);
                        setTimeout(updateVlanIdField, 50); // Small delay to ensure value is updated
                    });
                } else {
                    console.log('jQuery not available for Select2 events');
                    // Fallback: try to find the Select2 container and add click listener
                    const select2Container = document.querySelector('.select2-container');
                    if (select2Container) {
                        console.log('Found Select2 container, adding click listener');
                        select2Container.addEventListener('click', function() {
                            setTimeout(function() {
                                console.log('Select2 clicked, checking for value change...');
                                updateVlanIdField();
                            }, 100);
                        });
                    }
                }
            } else {
                // For regular select fields, use standard event listener
                console.log('Using standard event listener');
                networkModeField.addEventListener('change', function() {
                    console.log('Network mode changed to:', networkModeField.value);
                    updateVlanIdField();
                });
            }
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
    
    // Export functions for manual testing
    window.debugVlanSettings = function() {
        console.log('=== Manual VLAN Settings Debug ===');
        initializeVlanSettings();
        
        if (globalNetworkModeField && globalVlanIdField) {
            console.log('Manually calling updateVlanIdField...');
            updateVlanIdField();
        } else {
            console.log('Fields not found - cannot update');
        }
    };
    
    window.testVlanFieldToggle = function() {
        if (globalNetworkModeField && globalVlanIdField) {
            console.log('Testing field toggle...');
            console.log('Current network mode:', globalNetworkModeField.value);
            console.log('Current VLAN ID disabled state:', globalVlanIdField.disabled);
            updateVlanIdField();
        } else {
            console.log('Fields not available for testing');
        }
    };
    
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
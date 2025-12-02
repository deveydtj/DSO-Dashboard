// Header view module - Compact mode toggle functionality
// Pure JavaScript - no external dependencies

/**
 * Check for density URL parameter and apply compact mode
 */
export function checkDensityMode() {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('density') === 'compact') {
        document.body.classList.add('compact');
        console.log('📏 Compact mode enabled');
    }
}

/**
 * Setup the density (compact) mode toggle button with click handler
 */
export function setupDensityToggle() {
    const toggle = document.getElementById('densityToggle');
    if (!toggle) return;

    // Read current mode from body class
    const isCompactMode = document.body.classList.contains('compact');
    
    // Set toggle UI state
    if (isCompactMode) {
        toggle.classList.add('active');
    }

    // Add click handler
    toggle.addEventListener('click', () => {
        const isCurrentlyCompact = document.body.classList.contains('compact');
        
        if (isCurrentlyCompact) {
            // Disable compact mode
            document.body.classList.remove('compact');
            toggle.classList.remove('active');
            console.log('📏 Compact mode disabled');
            
            // Remove density parameter from URL
            const url = new URL(window.location);
            url.searchParams.delete('density');
            window.history.replaceState({}, '', url);
        } else {
            // Enable compact mode
            document.body.classList.add('compact');
            toggle.classList.add('active');
            console.log('📏 Compact mode enabled');
            
            // Add density=compact parameter to URL
            const url = new URL(window.location);
            url.searchParams.set('density', 'compact');
            window.history.replaceState({}, '', url);
        }
    });
}

/**
 * Initialize all header toggles
 * Call this from DashboardApp.init()
 */
export function initHeaderToggles() {
    checkDensityMode();
    setupDensityToggle();
}

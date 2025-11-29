// Header view module - TV/Compact/Wallboard toggle functionality
// Pure JavaScript - no external dependencies

/**
 * Check for TV mode URL parameter and apply to body class
 */
export function checkTVMode() {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('tv') === '1') {
        document.body.classList.add('tv');
        console.log('📺 TV mode enabled');
    }
}

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
 * Update the wallboard button state based on current TV and compact modes
 */
export function updateWallboardButtonState() {
    const button = document.getElementById('wallboardPreset');
    if (!button) return;

    const isTVMode = document.body.classList.contains('tv');
    const isCompactMode = document.body.classList.contains('compact');
    const isBothEnabled = isTVMode && isCompactMode;

    // Update button active state based on whether both modes are enabled
    if (isBothEnabled) {
        button.classList.add('active');
    } else {
        button.classList.remove('active');
    }
}

/**
 * Setup the TV mode toggle button with click handler
 */
export function setupTVToggle() {
    const toggle = document.getElementById('tvToggle');
    if (!toggle) return;

    // Read current mode from body class
    const isTVMode = document.body.classList.contains('tv');
    
    // Set toggle UI state
    if (isTVMode) {
        toggle.classList.add('active');
    }

    // Add click handler
    toggle.addEventListener('click', () => {
        const isCurrentlyTV = document.body.classList.contains('tv');
        
        if (isCurrentlyTV) {
            // Disable TV mode
            document.body.classList.remove('tv');
            toggle.classList.remove('active');
            console.log('📺 TV mode disabled');
            
            // Remove tv parameter from URL
            const url = new URL(window.location);
            url.searchParams.delete('tv');
            window.history.replaceState({}, '', url);
        } else {
            // Enable TV mode
            document.body.classList.add('tv');
            toggle.classList.add('active');
            console.log('📺 TV mode enabled');
            
            // Add tv=1 parameter to URL
            const url = new URL(window.location);
            url.searchParams.set('tv', '1');
            window.history.replaceState({}, '', url);
        }
        
        // Update wallboard button state
        updateWallboardButtonState();
    });
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
            
            // Add density=compact parameter to URL (preserving other params like tv)
            const url = new URL(window.location);
            url.searchParams.set('density', 'compact');
            window.history.replaceState({}, '', url);
        }
        
        // Update wallboard button state
        updateWallboardButtonState();
    });
}

/**
 * Setup the wallboard preset button (enables both TV and Compact modes)
 */
export function setupWallboardPreset() {
    const button = document.getElementById('wallboardPreset');
    if (!button) return;

    // Set initial button state
    updateWallboardButtonState();

    // Add click handler
    button.addEventListener('click', () => {
        const isCurrentlyTVMode = document.body.classList.contains('tv');
        const isCurrentlyCompactMode = document.body.classList.contains('compact');
        const isBothEnabled = isCurrentlyTVMode && isCurrentlyCompactMode;
        
        if (isBothEnabled) {
            // Disable wallboard mode (turn off both TV and Compact)
            document.body.classList.remove('tv');
            document.body.classList.remove('compact');
            
            // Also update individual toggle buttons
            const tvToggle = document.getElementById('tvToggle');
            const densityToggle = document.getElementById('densityToggle');
            if (tvToggle) tvToggle.classList.remove('active');
            if (densityToggle) densityToggle.classList.remove('active');
            
            console.log('🖥️ Wallboard mode disabled');
            
            // Remove both parameters from URL
            const url = new URL(window.location);
            url.searchParams.delete('tv');
            url.searchParams.delete('density');
            window.history.replaceState({}, '', url);
        } else {
            // Enable wallboard mode (turn on both TV and Compact)
            document.body.classList.add('tv');
            document.body.classList.add('compact');
            
            // Also update individual toggle buttons
            const tvToggle = document.getElementById('tvToggle');
            const densityToggle = document.getElementById('densityToggle');
            if (tvToggle) tvToggle.classList.add('active');
            if (densityToggle) densityToggle.classList.add('active');
            
            console.log('🖥️ Wallboard mode enabled');
            
            // Add both parameters to URL
            const url = new URL(window.location);
            url.searchParams.set('tv', '1');
            url.searchParams.set('density', 'compact');
            window.history.replaceState({}, '', url);
        }
        
        // Update wallboard button state
        updateWallboardButtonState();
    });
}

/**
 * Initialize all header toggles
 * Call this from DashboardApp.init()
 */
export function initHeaderToggles() {
    checkTVMode();
    checkDensityMode();
    setupTVToggle();
    setupDensityToggle();
    setupWallboardPreset();
}

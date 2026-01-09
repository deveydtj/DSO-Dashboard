// Header view module - Compact mode and DSO Mode toggle functionality
// Pure JavaScript - no external dependencies

/**
 * DSO Mode localStorage key
 */
const DSO_MODE_STORAGE_KEY = 'dso-mode-enabled';

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
 * Get DSO Mode state from localStorage (defaults to enabled)
 * @returns {boolean} - True if DSO Mode is enabled
 */
export function isDsoModeEnabled() {
    const stored = localStorage.getItem(DSO_MODE_STORAGE_KEY);
    // Default to enabled if not set
    return stored === null ? true : stored === 'true';
}

/**
 * Set DSO Mode state in localStorage
 * @param {boolean} enabled - True to enable DSO Mode
 */
export function setDsoModeEnabled(enabled) {
    localStorage.setItem(DSO_MODE_STORAGE_KEY, enabled.toString());
}

/**
 * Update pipeline section title based on DSO Mode state
 * @param {boolean} enabled - True if DSO Mode is enabled
 */
export function updatePipelineSectionTitle(enabled) {
    const title = document.getElementById('pipelineSectionTitle');
    if (!title) return;
    
    if (enabled) {
        title.textContent = '🔧 Infra / Runner Issues (Verified Unknown Included)';
    } else {
        title.textContent = '🔧 Recent Pipelines';
    }
}

/**
 * Setup the DSO Mode toggle button with click handler
 * @param {Function} onToggle - Callback function when toggle state changes (receives boolean enabled)
 */
export function setupDsoModeToggle(onToggle) {
    const toggle = document.getElementById('dsoModeToggle');
    if (!toggle) return;

    // Read current mode from localStorage
    const isDsoMode = isDsoModeEnabled();
    
    // Set toggle UI state
    if (isDsoMode) {
        toggle.classList.add('active');
    }
    
    // Set initial title
    updatePipelineSectionTitle(isDsoMode);

    // Add click handler
    toggle.addEventListener('click', () => {
        const isCurrentlyEnabled = toggle.classList.contains('active');
        const newState = !isCurrentlyEnabled;
        
        if (newState) {
            // Enable DSO Mode
            toggle.classList.add('active');
            console.log('🎯 DSO Mode enabled');
        } else {
            // Disable DSO Mode
            toggle.classList.remove('active');
            console.log('🎯 DSO Mode disabled');
        }
        
        // Save to localStorage
        setDsoModeEnabled(newState);
        
        // Update section title
        updatePipelineSectionTitle(newState);
        
        // Notify caller to reload data
        if (onToggle) {
            onToggle(newState);
        }
    });
}

/**
 * Initialize all header toggles
 * Call this from DashboardApp.init()
 * @param {Function} onDsoModeToggle - Callback for DSO Mode toggle
 */
export function initHeaderToggles(onDsoModeToggle) {
    checkDensityMode();
    setupDensityToggle();
    setupDsoModeToggle(onDsoModeToggle);
}

// Chart visibility state management
// Manages visibility state for chart lines with localStorage persistence

const STORAGE_KEY = 'dso_dashboard_job_chart_visibility_v1';

// Default visibility state - all metrics visible by default
const DEFAULT_VISIBILITY = {
    avg: true,
    p95: true,
    p99: true
};

/**
 * Load visibility state from localStorage
 * @returns {Object} - Visibility state object
 */
export function getVisibility() {
    try {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored) {
            const parsed = JSON.parse(stored);
            // Merge with defaults to handle missing keys
            return { ...DEFAULT_VISIBILITY, ...parsed };
        }
    } catch (error) {
        console.warn('Failed to load chart visibility from localStorage:', error);
    }
    
    // Return default state if nothing stored or error occurred
    return { ...DEFAULT_VISIBILITY };
}

/**
 * Save visibility state to localStorage
 * @param {Object} visibility - Visibility state object
 */
export function setVisibility(visibility) {
    // Check if localStorage is available
    if (typeof localStorage === 'undefined') {
        return;
    }
    
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(visibility));
    } catch (error) {
        console.warn('Failed to save chart visibility to localStorage:', error);
    }
}

/**
 * Toggle visibility for a specific metric
 * @param {string} metric - Metric name (avg, p95, p99)
 * @returns {Object} - Updated visibility state
 */
export function toggleMetric(metric) {
    const visibility = getVisibility();
    
    if (visibility.hasOwnProperty(metric)) {
        visibility[metric] = !visibility[metric];
        setVisibility(visibility);
    }
    
    return visibility;
}

/**
 * Reset visibility to default state
 * @returns {Object} - Default visibility state
 */
export function resetVisibility() {
    const defaultState = { ...DEFAULT_VISIBILITY };
    setVisibility(defaultState);
    return defaultState;
}

// DOM manipulation utilities
// Pure JavaScript - no external dependencies

/**
 * Show an error message in a container or log to console
 * @param {string} message - Error message to display
 * @param {string} [containerId] - Optional container element ID to show error in
 */
export function showError(message, containerId = null) {
    const errorHtml = `<div class="error">⚠️ ${message}</div>`;
    
    if (containerId) {
        const container = document.getElementById(containerId);
        if (container) {
            container.innerHTML = errorHtml;
        }
    } else {
        console.error(message);
    }
}

/**
 * Update the status indicator to show online/offline state
 * @param {boolean} isOnline - Whether the backend is online
 * @param {Object} cachedData - Cached data object to check if cache exists
 */
export function updateStatusIndicator(isOnline, cachedData) {
    const indicator = document.getElementById('statusIndicator');
    const lastUpdated = document.getElementById('lastUpdated');
    if (indicator) {
        indicator.className = `status-indicator ${isOnline ? 'online' : 'offline'}`;
    }
    // Show stale data notice when offline
    if (!isOnline && lastUpdated) {
        const hasCache = cachedData.summary || cachedData.repos || cachedData.pipelines || cachedData.services;
        if (hasCache) {
            lastUpdated.textContent = '⚠️ Showing cached data (backend offline)';
        }
    }
}

/**
 * Update the last updated timestamp display
 */
export function updateLastUpdated() {
    const element = document.getElementById('lastUpdated');
    if (element) {
        const now = new Date();
        element.textContent = `Last updated: ${now.toLocaleTimeString()}`;
    }
}

/**
 * Show a partial stale warning (some endpoints succeeded, some failed)
 */
export function showPartialStaleWarning() {
    const element = document.getElementById('lastUpdated');
    if (element) {
        const now = new Date();
        element.textContent = `⚠️ Partially stale (updated: ${now.toLocaleTimeString()})`;
    }
}

/**
 * Show a warning when all data endpoints failed
 * @param {Object} cachedData - Cached data object to check if cache exists
 */
export function showAllStaleWarning(cachedData) {
    const element = document.getElementById('lastUpdated');
    const indicator = document.getElementById('statusIndicator');
    if (element) {
        const hasCache = cachedData.summary || cachedData.repos || cachedData.pipelines || cachedData.services;
        if (hasCache) {
            element.textContent = '⚠️ All data stale (using cache)';
        } else {
            element.textContent = '❌ Failed to load data';
        }
    }
    // Update indicator to offline when all endpoints fail
    if (indicator) {
        indicator.className = 'status-indicator offline';
    }
}

/**
 * Update the mock data badge visibility
 * @param {boolean} isMock - Whether mock data is being used
 */
export function updateMockBadge(isMock) {
    const badge = document.getElementById('mockBadge');
    if (badge) {
        if (isMock === true) {
            badge.style.display = 'inline-flex';
        } else {
            badge.style.display = 'none';
        }
    }
}

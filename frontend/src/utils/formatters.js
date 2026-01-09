// Utility functions for formatting data
// Pure JavaScript - no external dependencies

/**
 * Escape HTML special characters to prevent XSS attacks
 * @param {string} text - The text to escape
 * @returns {string} - HTML-escaped text
 */
export function escapeHtml(text) {
    if (text === null || text === undefined) return '';

    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return String(text).replace(/[&<>"']/g, char => map[char]);
}

/**
 * Format a date string as relative time (e.g., "5m ago", "2h ago")
 * @param {string} dateString - ISO date string
 * @returns {string} - Formatted relative time
 */
export function formatDate(dateString) {
    try {
        const date = new Date(dateString);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;
        
        return date.toLocaleDateString();
    } catch (error) {
        return dateString;
    }
}

/**
 * Format duration in seconds as human-readable string (e.g., "5m 30s")
 * @param {number} seconds - Duration in seconds
 * @returns {string} - Formatted duration
 */
export function formatDuration(seconds) {
    if (seconds == null || seconds < 0) return '--';
    
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    
    if (mins === 0) return `${secs}s`;
    return `${mins}m ${secs}s`;
}

/**
 * Format a date string as human-readable timestamp
 * @param {string} dateString - ISO date string
 * @returns {string} - Formatted date and time
 */
export function formatTimestamp(dateString) {
    // Handle missing or empty values gracefully
    if (dateString === null || dateString === undefined || dateString === '') {
        return '--';
    }

    try {
        const date = new Date(dateString);
        
        // Guard against invalid dates (e.g., from null/undefined or bad strings)
        if (isNaN(date.getTime())) {
            return '--';
        }
        
        // Format as "Jan 20, 2024 10:30 AM"
        const options = {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: 'numeric',
            minute: '2-digit',
            hour12: true
        };
        
        return date.toLocaleString('en-US', options);
    } catch (error) {
        return '--';
    }
}

/**
 * Format duration value with both scaled units and raw seconds
 * @param {number} seconds - Duration in seconds
 * @param {Object} scale - Scale object with unit, label, and divisor
 * @returns {Object} - Object with scaled and raw formatted values
 */
export function formatDurationWithScale(seconds, scale) {
    if (seconds == null || seconds < 0) {
        return { scaled: '--', raw: '--' };
    }
    
    // Scaled value
    const scaledValue = seconds / scale.divisor;
    const scaledFormatted = (scale.divisor === 1) 
        ? `${Math.round(scaledValue)} ${scale.unit}`
        : `${scaledValue.toFixed(1)} ${scale.unit}`;
    
    // Raw seconds
    const rawFormatted = `${seconds.toFixed(1)}s`;
    
    return {
        scaled: scaledFormatted,
        raw: rawFormatted
    };
}

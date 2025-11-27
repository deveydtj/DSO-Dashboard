// Status normalization utilities
// Pure JavaScript - no external dependencies

/**
 * Normalize GitLab pipeline status to a safe whitelist for CSS classes
 * Handles null/undefined/empty, case differences, and underscores
 * @param {string} rawStatus - Raw status string from GitLab API
 * @returns {string} - Normalized status (success, failed, running, pending, canceled, skipped, manual, other)
 */
export function normalizeStatus(rawStatus) {
    if (!rawStatus) return 'other';
    
    // Normalize: lowercase and replace underscores/dashes with spaces for matching
    const normalized = String(rawStatus).toLowerCase().replace(/[_-]/g, ' ').trim();
    
    // Map GitLab statuses to our whitelist
    const statusMap = {
        // Success states
        'success': 'success',
        'passed': 'success',
        
        // Failed states
        'failed': 'failed',
        'failure': 'failed',
        
        // Running states
        'running': 'running',
        'in progress': 'running',
        
        // Pending/waiting states
        'pending': 'pending',
        'created': 'pending',
        'scheduled': 'pending',
        'preparing': 'pending',
        'waiting for resource': 'pending',
        'waiting for callback': 'pending',
        
        // Canceled states
        'canceled': 'canceled',
        'cancelled': 'canceled',
        
        // Skipped states
        'skipped': 'skipped',
        
        // Manual intervention needed
        'manual': 'manual'
    };
    
    // Return mapped status or 'other' for unknown statuses
    return statusMap[normalized] || 'other';
}

/**
 * Normalize service status to UP, DOWN, or UNKNOWN
 * @param {string} rawStatus - Raw status string from service health check
 * @returns {string} - Normalized status (UP, DOWN, UNKNOWN)
 */
export function normalizeServiceStatus(rawStatus) {
    if (!rawStatus) return 'UNKNOWN';
    
    const status = String(rawStatus).toUpperCase().trim();
    
    if (status === 'UP' || status === 'HEALTHY' || status === 'OK' || status === 'ONLINE') {
        return 'UP';
    }
    if (status === 'DOWN' || status === 'UNHEALTHY' || status === 'ERROR' || status === 'OFFLINE') {
        return 'DOWN';
    }
    return 'UNKNOWN';
}

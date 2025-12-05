// Service view module - Service card rendering
// Pure JavaScript - no external dependencies

import { escapeHtml } from '../utils/formatters.js';
import { normalizeServiceStatus } from '../utils/status.js';

/**
 * Format latency value for display
 * @param {number|null|undefined} latencyMs - Latency in milliseconds
 * @returns {string} - Formatted latency string (e.g., "42 ms" or "N/A")
 */
export function formatLatency(latencyMs) {
    if (latencyMs == null) return 'N/A';
    return `${Math.round(latencyMs)} ms`;
}

/**
 * Get a stable unique key for a service
 * @param {Object} service - Service object
 * @returns {string} - Stable key for the service
 */
export function getServiceKey(service) {
    // Prefer id, fallback to name, then url
    if (service.id != null) {
        return String(service.id);
    }
    if (service.name) {
        return service.name;
    }
    return service.url || 'unknown';
}

/**
 * Generate sparkline HTML for a history array of latency values.
 * Normalizes latencies relative to the max value in history into 5 height buckets.
 * Color is based on deviation from median: normal values are green, spikes are warning/error.
 * Returns empty string if history has fewer than 2 numeric entries.
 * 
 * @param {Array<number>|null} history - Array of latency_ms values
 * @returns {string} - Sparkline HTML or empty string
 */
export function createServiceSparkline(history) {
    // Return empty if no history or fewer than 2 numeric entries
    if (!Array.isArray(history)) return '';
    
    const numericValues = history.filter(v => typeof v === 'number' && Number.isFinite(v) && v >= 0);
    if (numericValues.length < 2) return '';
    
    // Find max value for normalization (relative scaling per service)
    const maxVal = Math.max(...numericValues);
    if (maxVal <= 0) return '';
    
    // Calculate median for determining spike thresholds
    const sorted = [...numericValues].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    const median = sorted.length % 2 !== 0 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
    
    // Define spike thresholds that scale with median while ensuring a reasonable minimum increase
    // This makes spike detection more sensitive for low-latency services while preventing false positives
    // warning: > 1.5x median OR > median + 50ms, error: > 2x median OR > median + 75ms
    const warningThreshold = Math.max(median * 1.5, median + 50);
    const errorThreshold = Math.max(median * 2, median + 75);
    
    // Generate bars with height based on max, and color based on spike detection
    const bars = numericValues.map(val => {
        const ratio = val / maxVal;
        // Convert to height bucket (1-5)
        const bucket = Math.min(5, Math.max(1, Math.ceil(ratio * 5)));
        
        // Determine color class based on deviation from median
        let colorClass = '';  // default: green (healthy)
        if (val > errorThreshold) {
            colorClass = ' sparkline-bar--spike-error';
        } else if (val > warningThreshold) {
            colorClass = ' sparkline-bar--spike-warning';
        }
        
        return `<span class="sparkline-bar sparkline-bar--h${bucket}${colorClass}"></span>`;
    }).join('');
    
    return `<div class="sparkline sparkline--service" aria-label="Recent latency trend">${bars}</div>`;
}

/**
 * Create HTML for a single service card
 * @param {Object} service - Service data
 * @param {Array<number>|null} [history=null] - Optional history array of latency values for sparkline
 * @returns {string} - HTML string for the service card
 */
export function createServiceCard(service, history = null) {
    const name = service.name || service.id || service.url || 'Unknown Service';
    const status = normalizeServiceStatus(service.status);
    const statusClass = `service-status-${status.toLowerCase()}`;
    
    // Latency warning class when latency_trend is "warning"
    const latencyWarningClass = service.latency_trend === 'warning' ? 'service-latency-warning' : '';
    
    // Latency display - current latency
    const currentLatency = formatLatency(service.latency_ms);
    
    // Average latency (may not be available on first sample)
    const hasAverageLatency = service.average_latency_ms != null;
    const averageLatency = formatLatency(service.average_latency_ms);
    
    // HTTP status display (optional)
    const httpStatus = service.http_status 
        ? `HTTP ${service.http_status}`
        : '';
    
    // Error message (optional)
    const errorHtml = service.error 
        ? `<div class="service-error">${escapeHtml(service.error)}</div>`
        : '';
    
    // Optional link to open service URL
    const linkHtml = service.url 
        ? `<a href="${escapeHtml(service.url)}" target="_blank" rel="noopener noreferrer" class="service-link" title="Open ${escapeHtml(name)}">Open →</a>`
        : '';
    
    // Latency warning badge (shown when latency_trend is "warning")
    const latencyWarningBadgeHtml = service.latency_trend === 'warning'
        ? '<span class="service-latency-warning-badge">Latency elevated</span>'
        : '';

    // Generate sparkline for latency trend (placed near latency section)
    const sparklineHtml = createServiceSparkline(history);

    // Combine CSS classes, filtering out empty strings to avoid extra whitespace
    const cardClasses = ['service-card', statusClass, latencyWarningClass]
        .filter(Boolean)
        .join(' ');

    return `
        <div class="${cardClasses}">
            <div class="service-header">
                <h3 class="service-name">${escapeHtml(name)}</h3>
                <span class="service-status-chip ${status.toLowerCase()}">
                    <span class="status-dot"></span>
                    <span>${escapeHtml(status)}</span>
                </span>
            </div>
            ${latencyWarningBadgeHtml}
            <div class="service-latency-section">
                <div class="service-latency-item">
                    <span class="latency-label">Current</span>
                    <span class="latency-value">${currentLatency}</span>
                </div>
                ${hasAverageLatency ? `
                <div class="service-latency-item">
                    <span class="latency-label">Average</span>
                    <span class="latency-value">${averageLatency}</span>
                </div>
                ` : ''}
            </div>
            ${sparklineHtml}
            ${httpStatus ? `
            <div class="service-metrics">
                <div class="service-metric">
                    <span class="metric-label">Status</span>
                    <span class="metric-value">${httpStatus}</span>
                </div>
            </div>
            ` : ''}
            ${errorHtml}
            ${linkHtml}
        </div>
    `;
}

/**
 * Render services grid to the DOM
 * @param {Array} services - Array of service objects
 * @param {Map} [historyMap=undefined] - Optional Map of service key to history array (latency values)
 */
export function renderServices(services, historyMap = undefined) {
    const container = document.getElementById('servicesGrid');
    if (!container) return;

    if (services.length === 0) {
        container.innerHTML = '<div class="services-empty">No services configured</div>';
        return;
    }

    container.innerHTML = services.map(service => {
        // Get history for this service (if available)
        const key = getServiceKey(service);
        const history = historyMap?.get(key) ?? null;
        return createServiceCard(service, history);
    }).join('');
}

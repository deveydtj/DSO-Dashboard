// Service view module - Service card rendering
// Pure JavaScript - no external dependencies

import { escapeHtml, formatDate } from '../utils/formatters.js';
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
 * Create HTML for a single service card
 * @param {Object} service - Service data
 * @returns {string} - HTML string for the service card
 */
export function createServiceCard(service) {
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
    
    // Last checked display
    const lastChecked = service.last_checked 
        ? formatDate(service.last_checked)
        : '--';
    
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

    return `
        <div class="service-card ${statusClass} ${latencyWarningClass}">
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
            <div class="service-metrics">
                <div class="service-metric">
                    <span class="metric-label">Last Check</span>
                    <span class="metric-value">${lastChecked}</span>
                </div>
                ${httpStatus ? `
                <div class="service-metric">
                    <span class="metric-label">Status</span>
                    <span class="metric-value">${httpStatus}</span>
                </div>
                ` : ''}
            </div>
            ${errorHtml}
            ${linkHtml}
        </div>
    `;
}

/**
 * Render services grid to the DOM
 * @param {Array} services - Array of service objects
 */
export function renderServices(services) {
    const container = document.getElementById('servicesGrid');
    if (!container) return;

    if (services.length === 0) {
        container.innerHTML = '<div class="services-empty">No services configured</div>';
        return;
    }

    container.innerHTML = services.map(service => createServiceCard(service)).join('');
}

// Chart tooltip module for interactive hover functionality
// Pure JavaScript - no external dependencies

import { escapeHtml, formatTimestamp, formatDurationWithScale } from './formatters.js';

/**
 * Build tooltip content HTML from data point and metric information
 * @param {Object} dataPoint - Analytics data point
 * @param {string} metricName - Name of the metric (avg/p95/p99)
 * @param {number} metricValue - Value of the metric in seconds
 * @param {Object} scale - Duration scale object with unit, label, and divisor
 * @param {string} projectName - Optional project name
 * @returns {string} - HTML content for tooltip
 */
export function buildTooltipContent(dataPoint, metricName, metricValue, scale, projectName = null) {
    // Format duration with both scaled and raw values
    const duration = formatDurationWithScale(metricValue, scale);
    
    // Format timestamp
    const timestamp = formatTimestamp(dataPoint.created_at);
    
    // Determine metric label and CSS class
    const metricLabels = {
        'avg': 'Average Duration',
        'p95': 'P95 Duration',
        'p99': 'P99 Duration'
    };
    const metricLabel = metricLabels[metricName] || metricName;
    const metricClass = `chart-tooltip-metric-value--${metricName}`;
    
    // Build HTML content
    let html = '<div class="chart-tooltip-header">';
    if (projectName) {
        html += escapeHtml(projectName);
    } else {
        html += 'Pipeline Details';
    }
    html += '</div>';
    
    // Pipeline metadata
    html += '<div class="chart-tooltip-row">';
    html += '<span class="chart-tooltip-label">Pipeline ID:</span>';
    html += `<span class="chart-tooltip-value">${escapeHtml(String(dataPoint.pipeline_id || '--'))}</span>`;
    html += '</div>';
    
    html += '<div class="chart-tooltip-row">';
    html += '<span class="chart-tooltip-label">Branch:</span>';
    html += `<span class="chart-tooltip-value">${escapeHtml(String(dataPoint.pipeline_ref || '--'))}</span>`;
    html += '</div>';
    
    html += '<div class="chart-tooltip-row">';
    html += '<span class="chart-tooltip-label">Status:</span>';
    html += `<span class="chart-tooltip-value">${escapeHtml(String(dataPoint.pipeline_status || '--'))}</span>`;
    html += '</div>';
    
    html += '<div class="chart-tooltip-row">';
    html += '<span class="chart-tooltip-label">Created:</span>';
    html += `<span class="chart-tooltip-value">${escapeHtml(timestamp)}</span>`;
    html += '</div>';
    
    // Metric section
    html += '<div class="chart-tooltip-metric">';
    html += `<div class="chart-tooltip-metric-name">${escapeHtml(metricLabel)}</div>`;
    html += `<div class="chart-tooltip-metric-value ${metricClass}">${escapeHtml(duration.scaled)}</div>`;
    html += '<div class="chart-tooltip-row chart-tooltip-raw-seconds">';
    html += '<span class="chart-tooltip-label">Raw seconds:</span>';
    html += `<span class="chart-tooltip-value">${escapeHtml(duration.raw)}</span>`;
    html += '</div>';
    html += '</div>';
    
    return html;
}

/**
 * Show tooltip at specified position
 * @param {HTMLElement} tooltip - Tooltip element
 * @param {number} x - X coordinate (screen)
 * @param {number} y - Y coordinate (screen)
 * @param {string} content - HTML content for tooltip
 */
export function showTooltip(tooltip, x, y, content) {
    if (!tooltip) return;
    
    // Set content
    tooltip.innerHTML = content;
    
    // Show tooltip
    tooltip.style.display = 'block';
    
    // Position tooltip with offset and boundary checking
    const offset = 10;
    const rect = tooltip.getBoundingClientRect();
    
    // Calculate position
    let left = x + offset;
    let top = y + offset;
    
    // Check right boundary
    if (left + rect.width > window.innerWidth) {
        left = x - rect.width - offset;
    }
    
    // Check bottom boundary
    if (top + rect.height > window.innerHeight) {
        top = y - rect.height - offset;
    }
    
    // Check left boundary
    if (left < 0) {
        left = offset;
    }
    
    // Check top boundary
    if (top < 0) {
        top = offset;
    }
    
    tooltip.style.left = `${left}px`;
    tooltip.style.top = `${top}px`;
}

/**
 * Hide tooltip
 * @param {HTMLElement} tooltip - Tooltip element
 */
export function hideTooltip(tooltip) {
    if (!tooltip) return;
    tooltip.style.display = 'none';
}

/**
 * Find nearest data point to cursor position
 * @param {number} mouseX - Mouse X coordinate
 * @param {number} mouseY - Mouse Y coordinate
 * @param {Array} pointCoordinates - Array of point coordinates with {x, y, dataPoint, metricName, metricValue}
 * @param {number} maxDistance - Maximum distance to consider (in pixels)
 * @returns {Object|null} - Nearest point data or null if none found within maxDistance
 */
export function findNearestPoint(mouseX, mouseY, pointCoordinates, maxDistance = 20) {
    if (!pointCoordinates || pointCoordinates.length === 0) {
        return null;
    }
    
    let nearestPoint = null;
    let minDistance = maxDistance;
    
    for (const point of pointCoordinates) {
        const dx = point.x - mouseX;
        const dy = point.y - mouseY;
        const distance = Math.sqrt(dx * dx + dy * dy);
        
        if (distance < minDistance) {
            minDistance = distance;
            nearestPoint = point;
        }
    }
    
    return nearestPoint;
}

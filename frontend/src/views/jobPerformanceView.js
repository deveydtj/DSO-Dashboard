// Job Performance Modal View
// Pure JavaScript - no external dependencies

import { escapeHtml } from '../utils/formatters.js';
import { openModal, setModalContent, setModalLoading } from '../utils/modal.js';
import { fetchJobAnalytics, refreshJobAnalytics } from '../api/apiClient.js';
import { renderJobPerformanceChart } from '../utils/chart.js';
import { showTooltip, hideTooltip, findNearestPoint, buildTooltipContent } from '../utils/tooltip.js';
import { getVisibility, toggleMetric } from '../utils/chartVisibility.js';

// HTTP status code constants
const HTTP_NOT_FOUND = 404;
const HTTP_CONFLICT = 409;
const HTTP_INTERNAL_SERVER_ERROR = 500;
const HTTP_SERVICE_UNAVAILABLE = 503;

// WeakMap to store refresh button handlers for cleanup
let refreshButtonHandlers = new WeakMap();

// WeakMap to store error timeout IDs for cleanup
let errorTimeouts = new WeakMap();

// WeakMap to store resize handlers for cleanup
let resizeHandlers = new WeakMap();

// WeakMap to store resize timeout IDs for cleanup
let resizeTimeouts = new WeakMap();

// WeakMap to store mouse handlers for cleanup
let mouseHandlers = new WeakMap();

// Flag to prevent multiple concurrent modal opens
let isModalOpening = false;

/**
 * Open the job performance modal for a specific project
 * @param {Object} project - Project object with id, name, etc.
 * @param {string} apiBase - Base URL for API
 */
export async function openJobPerformanceModal(project, apiBase) {
    // Prevent concurrent opens
    if (isModalOpening) {
        console.warn('Modal is already opening, ignoring duplicate request');
        return;
    }
    
    isModalOpening = true;
    
    try {
        const modalId = 'jobPerformanceModal';
        
        // Update modal title with project name
        const modal = document.getElementById(modalId);
        if (!modal) {
            console.error('Job performance modal not found in DOM');
            return;
        }
        
        const modalTitle = modal.querySelector('.modal-title');
        if (modalTitle) {
            // Use textContent for safety (already safe, but consistent with codebase practices)
            modalTitle.textContent = `Job Performance: ${project.name}`;
        }
    
        // Open modal and show loading state
        openModal(modalId);
        setModalLoading(modalId, 'Loading job analytics...');
        
        // Fetch analytics data
        try {
            const analytics = await fetchJobAnalytics(apiBase, project.id);
            renderJobAnalytics(modalId, analytics, project, apiBase);
        } catch (error) {
            console.error('Error fetching job analytics:', error);
            handleJobAnalyticsError(modalId, error, project, apiBase);
        }
    } finally {
        // Reset flag after operation completes (success or error)
        isModalOpening = false;
    }
}

/**
 * Render job analytics in the modal
 * @param {string} modalId - Modal element ID
 * @param {Object} analytics - Analytics data from API
 * @param {Object} project - Project object
 * @param {string} apiBase - Base URL for API
 */
function renderJobAnalytics(modalId, analytics, project, apiBase) {
    // Check if data exists
    if (!analytics.data || analytics.data.length === 0) {
        setModalContent(modalId, `
            <div class="modal-not-available">
                <div class="modal-not-available-icon">📊</div>
                <div class="modal-not-available-title">No Analytics Data Available</div>
                <div class="modal-not-available-message">
                    No job performance data has been collected for this project yet.
                    ${renderRefreshButton(project.id, apiBase, 'Try computing analytics')}
                </div>
            </div>
        `);
        attachRefreshHandler(modalId, project, apiBase);
        return;
    }
    
    // Get current visibility state
    const visibility = getVisibility();
    
    // Render chart container with data
    const content = `
        <div class="chart-container">
            <div class="chart-header">
                <div class="chart-title">7-Day Job Performance Trend</div>
                ${renderRefreshButton(project.id, apiBase, '🔄 Refresh')}
            </div>
            <div class="chart-controls">
                <span class="chart-controls-label">Show:</span>
                <label class="chart-control">
                    <input type="checkbox" id="toggleAvg" ${visibility.avg ? 'checked' : ''}>
                    <span>Avg</span>
                </label>
                <label class="chart-control">
                    <input type="checkbox" id="toggleP95" ${visibility.p95 ? 'checked' : ''}>
                    <span>P95</span>
                </label>
                <label class="chart-control">
                    <input type="checkbox" id="toggleP99" ${visibility.p99 ? 'checked' : ''}>
                    <span>P99</span>
                </label>
            </div>
            <div class="chart-canvas-wrapper">
                <canvas id="jobPerformanceChart" role="img" aria-label="Job performance chart showing average, P95, and P99 job durations over 7 days"></canvas>
            </div>
            <div class="chart-legend">
                <div class="legend-item ${visibility.avg ? '' : 'is-hidden'}" data-metric="avg">
                    <div class="legend-color legend-color--avg"></div>
                    <span>Average Duration</span>
                </div>
                <div class="legend-item ${visibility.p95 ? '' : 'is-hidden'}" data-metric="p95">
                    <div class="legend-color legend-color--p95"></div>
                    <span>P95 Duration</span>
                </div>
                <div class="legend-item ${visibility.p99 ? '' : 'is-hidden'}" data-metric="p99">
                    <div class="legend-color legend-color--p99"></div>
                    <span>P99 Duration</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color legend-color--default"></div>
                    <span>Solid = Default Branch</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color legend-color--mr"></div>
                    <span>Dashed = Merge Requests</span>
                </div>
            </div>
        </div>
        <div class="chart-info">
            <strong>Window:</strong> ${escapeHtml(String(analytics.window_days || 7))} days | 
            <strong>Pipelines:</strong> ${escapeHtml(String(analytics.data.length))} | 
            <strong>Computed:</strong> ${escapeHtml(formatComputedTime(analytics.computed_at))}
        </div>
    `;
    
    setModalContent(modalId, content);
    
    // Attach toggle event handlers
    attachToggleHandlers(modalId, analytics, project, apiBase);
    
    // Render chart on canvas
    const canvas = document.getElementById('jobPerformanceChart');
    if (canvas && analytics.data) {
        const currentVisibility = getVisibility();
        renderJobPerformanceChart(canvas, analytics.data, { 
            window_days: analytics.window_days || 7,
            visibility: currentVisibility
        });
        
        // Get tooltip element
        const tooltip = document.getElementById('chartTooltip');
        
        // Clean up old mouse handlers if they exist
        const oldMouseHandlers = mouseHandlers.get(canvas);
        if (oldMouseHandlers) {
            canvas.removeEventListener('mousemove', oldMouseHandlers.mousemove);
            canvas.removeEventListener('mouseout', oldMouseHandlers.mouseout);
        }
        
        // Add mouse event handlers for tooltip
        const mousemoveHandler = (event) => {
            // Get canvas-relative coordinates
            const rect = canvas.getBoundingClientRect();
            const mouseX = event.clientX - rect.left;
            const mouseY = event.clientY - rect.top;
            
            // Find nearest point
            const pointCoordinates = canvas._pointCoordinates || [];
            const nearestPoint = findNearestPoint(mouseX, mouseY, pointCoordinates, 20);
            
            if (nearestPoint && tooltip) {
                // Build tooltip content
                const scale = canvas._durationScale || { unit: 's', label: 'seconds', divisor: 1 };
                const content = buildTooltipContent(
                    nearestPoint.dataPoint,
                    nearestPoint.metricName,
                    nearestPoint.metricValue,
                    scale,
                    project.name
                );
                
                // Show tooltip at cursor position
                showTooltip(tooltip, event.clientX, event.clientY, content);
            } else if (tooltip) {
                hideTooltip(tooltip);
            }
        };
        
        const mouseoutHandler = () => {
            if (tooltip) {
                hideTooltip(tooltip);
            }
        };
        
        canvas.addEventListener('mousemove', mousemoveHandler);
        canvas.addEventListener('mouseout', mouseoutHandler);
        
        // Store handlers for cleanup
        mouseHandlers.set(canvas, {
            mousemove: mousemoveHandler,
            mouseout: mouseoutHandler
        });
        
        // Clean up old resize handler and timeout if exists
        const oldResizeHandler = resizeHandlers.get(canvas);
        if (oldResizeHandler) {
            window.removeEventListener('resize', oldResizeHandler);
        }
        const oldResizeTimeout = resizeTimeouts.get(canvas);
        if (oldResizeTimeout) {
            clearTimeout(oldResizeTimeout);
            resizeTimeouts.delete(canvas);
        }
        
        const resizeHandler = () => {
            // Debounce: only re-render after resize stops for 200ms
            const oldTimeout = resizeTimeouts.get(canvas);
            if (oldTimeout) {
                clearTimeout(oldTimeout);
            }
            const timeoutId = setTimeout(() => {
                // Check if canvas still exists before rendering
                if (document.contains(canvas)) {
                    const currentVisibility = getVisibility();
                    renderJobPerformanceChart(canvas, analytics.data, { 
                        window_days: analytics.window_days || 7,
                        visibility: currentVisibility
                    });
                    
                    // Remove old handlers before re-attaching to prevent duplicates
                    const handlers = mouseHandlers.get(canvas);
                    if (handlers) {
                        canvas.removeEventListener('mousemove', handlers.mousemove);
                        canvas.removeEventListener('mouseout', handlers.mouseout);
                    }
                    
                    // Re-attach mouse handlers after resize
                    canvas.addEventListener('mousemove', mousemoveHandler);
                    canvas.addEventListener('mouseout', mouseoutHandler);
                    
                    // Update stored handlers
                    mouseHandlers.set(canvas, {
                        mousemove: mousemoveHandler,
                        mouseout: mouseoutHandler
                    });
                }
                resizeTimeouts.delete(canvas);
            }, 200);
            resizeTimeouts.set(canvas, timeoutId);
        };
        
        window.addEventListener('resize', resizeHandler);
        resizeHandlers.set(canvas, resizeHandler);
    }
    
    // Attach refresh handler
    attachRefreshHandler(modalId, project, apiBase);
}

/**
 * Handle errors when fetching job analytics
 * @param {string} modalId - Modal element ID
 * @param {Error} error - Error object
 * @param {Object} project - Project object
 * @param {string} apiBase - Base URL for API
 */
function handleJobAnalyticsError(modalId, error, project, apiBase) {
    let title = 'Error Loading Analytics';
    let message;
    let showRefresh = false;
    
    if (error.status === HTTP_NOT_FOUND) {
        title = 'Analytics Not Available';
        message = error.message || 'Analytics have not been computed yet for this project.';
        showRefresh = true;
    } else if (error.status === HTTP_SERVICE_UNAVAILABLE) {
        title = 'Feature Not Available';
        message = error.message || 'Job analytics feature is not enabled or available.';
        showRefresh = false;
    } else {
        message = error.message || 'Failed to fetch analytics data. Please try again.';
        showRefresh = true;
    }
    
    setModalContent(modalId, `
        <div class="modal-error">
            <div class="modal-error-title">${escapeHtml(title)}</div>
            <div class="modal-error-message">${escapeHtml(message)}</div>
        </div>
        ${showRefresh ? `
            <div class="modal-error-actions">
                ${renderRefreshButton(project.id, apiBase, '🔄 Compute Analytics')}
            </div>
        ` : ''}
    `);
    
    if (showRefresh) {
        attachRefreshHandler(modalId, project, apiBase);
    }
}

/**
 * Render refresh button HTML
 * @param {number} projectId - Project ID
 * @param {string} apiBase - Base URL for API
 * @param {string} label - Button label
 * @returns {string} - Button HTML
 */
function renderRefreshButton(projectId, apiBase, label) {
    return `
        <button class="chart-refresh-btn" data-project-id="${projectId}" data-action="refresh">
            ${escapeHtml(label)}
        </button>
    `;
}

/**
 * Cleanup function to be called when modal closes
 * Removes resize handlers and clears timeouts
 */
export function cleanupJobPerformanceModal() {
    // Clean up all resize handlers
    const canvas = document.getElementById('jobPerformanceChart');
    if (canvas) {
        const resizeHandler = resizeHandlers.get(canvas);
        if (resizeHandler) {
            window.removeEventListener('resize', resizeHandler);
            resizeHandlers.delete(canvas);
        }
        const resizeTimeout = resizeTimeouts.get(canvas);
        if (resizeTimeout) {
            clearTimeout(resizeTimeout);
            resizeTimeouts.delete(canvas);
        }
        
        // Clean up mouse handlers
        const handlers = mouseHandlers.get(canvas);
        if (handlers) {
            canvas.removeEventListener('mousemove', handlers.mousemove);
            canvas.removeEventListener('mouseout', handlers.mouseout);
            mouseHandlers.delete(canvas);
        }
    }
    
    // Hide tooltip
    const tooltip = document.getElementById('chartTooltip');
    if (tooltip) {
        tooltip.style.display = 'none';
    }
    
    // Clean up error timeouts
    const modal = document.getElementById('jobPerformanceModal');
    if (modal) {
        const errorTimeout = errorTimeouts.get(modal);
        if (errorTimeout) {
            clearTimeout(errorTimeout);
            errorTimeouts.delete(modal);
        }
        
        // Clean up refresh button handlers
        const refreshBtn = modal.querySelector('[data-action="refresh"]');
        if (refreshBtn) {
            const refreshHandler = refreshButtonHandlers.get(refreshBtn);
            if (refreshHandler) {
                refreshBtn.removeEventListener('click', refreshHandler);
                refreshButtonHandlers.delete(refreshBtn);
            }
        }
    }
}

/**
 * Attach toggle event handlers for chart visibility controls
 * @param {string} modalId - Modal element ID
 * @param {Object} analytics - Analytics data
 * @param {Object} project - Project object
 * @param {string} apiBase - Base URL for API
 */
function attachToggleHandlers(modalId, analytics, project, apiBase) {
    const modal = document.getElementById(modalId);
    if (!modal) return;
    
    const toggleAvg = modal.querySelector('#toggleAvg');
    const toggleP95 = modal.querySelector('#toggleP95');
    const toggleP99 = modal.querySelector('#toggleP99');
    
    const handleToggle = (metric) => {
        // Toggle visibility state
        const newVisibility = toggleMetric(metric);
        
        // Update legend items
        const legendItems = modal.querySelectorAll('.legend-item[data-metric]');
        legendItems.forEach(item => {
            const itemMetric = item.getAttribute('data-metric');
            if (itemMetric && newVisibility.hasOwnProperty(itemMetric)) {
                if (newVisibility[itemMetric]) {
                    item.classList.remove('is-hidden');
                } else {
                    item.classList.add('is-hidden');
                }
            }
        });
        
        // Re-render chart
        const canvas = document.getElementById('jobPerformanceChart');
        if (canvas && analytics.data) {
            renderJobPerformanceChart(canvas, analytics.data, {
                window_days: analytics.window_days || 7,
                visibility: newVisibility
            });
        }
    };
    
    if (toggleAvg) {
        toggleAvg.addEventListener('change', () => handleToggle('avg'));
    }
    if (toggleP95) {
        toggleP95.addEventListener('change', () => handleToggle('p95'));
    }
    if (toggleP99) {
        toggleP99.addEventListener('change', () => handleToggle('p99'));
    }
}

/**
 * Attach click handler for refresh button
 * @param {string} modalId - Modal element ID
 * @param {Object} project - Project object
 * @param {string} apiBase - Base URL for API
 */
function attachRefreshHandler(modalId, project, apiBase) {
    const modal = document.getElementById(modalId);
    if (!modal) return;
    
    const refreshBtn = modal.querySelector('[data-action="refresh"]');
    if (!refreshBtn) return;
    
    // Remove old handler if exists
    const oldHandler = refreshButtonHandlers.get(refreshBtn);
    if (oldHandler) {
        refreshBtn.removeEventListener('click', oldHandler);
    }
    
    // Clear any existing error timeout
    const oldTimeoutId = errorTimeouts.get(modal);
    if (oldTimeoutId) {
        clearTimeout(oldTimeoutId);
        errorTimeouts.delete(modal);
    }
    
    // Define the handler
    const handler = async () => {
        // Disable button during refresh
        refreshBtn.disabled = true;
        refreshBtn.textContent = '⏳ Computing...';
        
        try {
            const result = await refreshJobAnalytics(apiBase, project.id);
            
            // Re-render with new data
            if (result.analytics) {
                renderJobAnalytics(modalId, result.analytics, project, apiBase);
            } else {
                // Fetch fresh data
                const analytics = await fetchJobAnalytics(apiBase, project.id);
                renderJobAnalytics(modalId, analytics, project, apiBase);
            }
        } catch (error) {
            console.error('Error refreshing analytics:', error);
            
            // Show error but keep existing content
            const modalBody = modal.querySelector('.modal-body');
            if (modalBody) {
                const errorDiv = document.createElement('div');
                errorDiv.className = 'modal-error embedded-error';
                
                let errorMessage = 'Failed to refresh analytics. Please try again.';
                
                if (error.status === HTTP_CONFLICT) {
                    errorMessage = 'A refresh is already in progress. Please wait...';
                } else if (error.status === HTTP_INTERNAL_SERVER_ERROR) {
                    errorMessage = 'Refresh failed. The server may be unable to compute analytics.';
                } else if (error.message) {
                    errorMessage = error.message;
                }
                
                errorDiv.innerHTML = `
                    <div class="modal-error-title">Refresh Failed</div>
                    <div class="modal-error-message">${escapeHtml(errorMessage)}</div>
                `;
                
                // Insert at top of modal body
                modalBody.insertBefore(errorDiv, modalBody.firstChild);
                
                // Re-enable button
                refreshBtn.disabled = false;
                refreshBtn.textContent = '🔄 Retry';
                
                // Remove error after 5 seconds - store timeout ID
                const timeoutId = setTimeout(() => {
                    errorDiv.remove();
                    errorTimeouts.delete(modal);
                }, 5000);
                errorTimeouts.set(modal, timeoutId);
            }
        }
    };
    
    // Add new handler and store reference
    refreshBtn.addEventListener('click', handler);
    refreshButtonHandlers.set(refreshBtn, handler);
}

/**
 * Format computed time as relative time
 * @param {string} timestamp - ISO timestamp
 * @returns {string} - Formatted time
 */
function formatComputedTime(timestamp) {
    if (!timestamp) return 'unknown';
    
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    
    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins} min ago`;
    
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
    
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
}

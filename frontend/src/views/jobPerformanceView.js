// Job Performance Modal View
// Pure JavaScript - no external dependencies

import { escapeHtml } from '../utils/formatters.js';
import { openModal, closeModal, setModalContent, setModalLoading, setModalError } from '../utils/modal.js';
import { fetchJobAnalytics, refreshJobAnalytics } from '../api/apiClient.js';
import { renderJobPerformanceChart } from '../utils/chart.js';

/**
 * Open the job performance modal for a specific project
 * @param {Object} project - Project object with id, name, etc.
 * @param {string} apiBase - Base URL for API
 */
export async function openJobPerformanceModal(project, apiBase) {
    const modalId = 'jobPerformanceModal';
    
    // Update modal title with project name
    const modal = document.getElementById(modalId);
    if (!modal) {
        console.error('Job performance modal not found in DOM');
        return;
    }
    
    const modalTitle = modal.querySelector('.modal-title');
    if (modalTitle) {
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
    
    // Render chart container with data
    const content = `
        <div class="chart-container">
            <div class="chart-header">
                <div class="chart-title">7-Day Job Performance Trend</div>
                ${renderRefreshButton(project.id, apiBase, '🔄 Refresh')}
            </div>
            <div class="chart-canvas-wrapper">
                <canvas id="jobPerformanceChart"></canvas>
            </div>
            <div class="chart-legend">
                <div class="legend-item">
                    <div class="legend-color legend-color--avg"></div>
                    <span>Average Duration</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color legend-color--p95"></div>
                    <span>P95 Duration</span>
                </div>
                <div class="legend-item">
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
            <strong>Window:</strong> ${analytics.window_days || 7} days | 
            <strong>Pipelines:</strong> ${analytics.data.length} | 
            <strong>Computed:</strong> ${formatComputedTime(analytics.computed_at)}
        </div>
    `;
    
    setModalContent(modalId, content);
    
    // Render chart on canvas
    const canvas = document.getElementById('jobPerformanceChart');
    if (canvas) {
        renderJobPerformanceChart(canvas, analytics.data);
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
    let message = 'An unexpected error occurred while loading job analytics.';
    let showRefresh = false;
    
    if (error.status === 404) {
        title = 'Analytics Not Available';
        message = error.message || 'Analytics have not been computed yet for this project.';
        showRefresh = true;
    } else if (error.status === 503) {
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
            <div style="margin-top: 1rem; text-align: center;">
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
    
    refreshBtn.addEventListener('click', async () => {
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
                errorDiv.className = 'modal-error';
                errorDiv.style.marginBottom = '1rem';
                
                let errorMessage = 'Failed to refresh analytics. Please try again.';
                
                if (error.status === 409) {
                    errorMessage = 'A refresh is already in progress. Please wait...';
                } else if (error.status === 500) {
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
                
                // Remove error after 5 seconds
                setTimeout(() => errorDiv.remove(), 5000);
            }
        }
    });
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

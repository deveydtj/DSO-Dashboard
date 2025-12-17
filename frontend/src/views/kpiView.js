// KPI view module - Summary KPI rendering
// Pure JavaScript - no external dependencies

import { updateMockBadge } from '../utils/dom.js';

/**
 * Format a decimal value as a percentage string
 * @param {number|null|undefined} value - Decimal value (e.g. 0.987)
 * @returns {string} - Formatted percentage string (e.g. "98.7%") or "--" if invalid
 */
export function formatSloPercentage(value) {
    if (value === null || value === undefined || typeof value !== 'number' || isNaN(value)) {
        return '--';
    }
    return (value * 100).toFixed(1) + '%';
}

/**
 * Render summary KPI values to the DOM
 * @param {Object} data - Summary data from API
 * @param {number} data.total_repositories - Total number of repositories
 * @param {number} data.successful_pipelines - Number of successful pipelines
 * @param {number} data.failed_pipelines - Number of failed pipelines
 * @param {number} data.running_pipelines - Number of running pipelines
 * @param {number} [data.pipeline_slo_target_default_branch_success_rate] - SLO target (0-1)
 * @param {number} [data.pipeline_slo_observed_default_branch_success_rate] - Observed rate (0-1)
 * @param {boolean} [data.is_mock] - Whether mock data is being used
 */
export function renderSummaryKpis(data) {
    const totalRepos = document.getElementById('totalRepos');
    const successPipelines = document.getElementById('successPipelines');
    const failedPipelines = document.getElementById('failedPipelines');
    const runningPipelines = document.getElementById('runningPipelines');

    if (totalRepos) totalRepos.textContent = data.total_repositories || 0;
    if (successPipelines) successPipelines.textContent = data.successful_pipelines || 0;
    if (failedPipelines) failedPipelines.textContent = data.failed_pipelines || 0;
    if (runningPipelines) runningPipelines.textContent = data.running_pipelines || 0;

    // Render SLO KPI values and show/hide SLO tile based on data presence
    renderSloKpis(data);

    // Update mock data badge visibility
    updateMockBadge(data.is_mock);
}

/**
 * Render SLO-specific KPI values and show/hide the SLO tile
 * @param {Object} data - Summary data containing SLO fields
 */
export function renderSloKpis(data) {
    const sloCard = document.querySelector('.kpi-card-slo');
    const sloTarget = document.getElementById('pipelineSloTarget');
    const sloObserved = document.getElementById('pipelineSloObserved');

    // Extract SLO values with fallback to null
    const targetValue = data.pipeline_slo_target_default_branch_success_rate ?? null;
    const observedValue = data.pipeline_slo_observed_default_branch_success_rate ?? null;

    // Check if SLO data is present (enabled in backend)
    const sloEnabled = targetValue !== null && observedValue !== null;

    // Show or hide the SLO tile
    if (sloCard) {
        if (sloEnabled) {
            sloCard.style.display = '';  // Show (use default display)
        } else {
            sloCard.style.display = 'none';  // Hide
            return;  // Don't update values if hidden
        }
    }

    // Update target and observed displays
    if (sloTarget) {
        sloTarget.textContent = formatSloPercentage(targetValue);
    }
    if (sloObserved) {
        sloObserved.textContent = formatSloPercentage(observedValue);
    }
}

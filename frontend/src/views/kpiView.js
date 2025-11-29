// KPI view module - Summary KPI rendering
// Pure JavaScript - no external dependencies

import { updateMockBadge } from '../utils/dom.js';

/**
 * Render summary KPI values to the DOM
 * @param {Object} data - Summary data from API
 * @param {number} data.total_repositories - Total number of repositories
 * @param {number} data.successful_pipelines - Number of successful pipelines
 * @param {number} data.failed_pipelines - Number of failed pipelines
 * @param {number} data.running_pipelines - Number of running pipelines
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

    // Update mock data badge visibility
    updateMockBadge(data.is_mock);
}

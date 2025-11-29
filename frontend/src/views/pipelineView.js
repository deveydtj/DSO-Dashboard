// Pipeline view module - Pipeline table rendering
// Pure JavaScript - no external dependencies

import { escapeHtml, formatDate, formatDuration } from '../utils/formatters.js';
import { normalizeStatus } from '../utils/status.js';

/**
 * Create HTML for a single pipeline table row
 * @param {Object} pipeline - Pipeline data
 * @returns {string} - HTML string for the table row
 */
export function createPipelineRow(pipeline) {
    const status = pipeline.status || 'unknown';
    const normalizedStatus = normalizeStatus(status);
    const duration = pipeline.duration != null
        ? formatDuration(pipeline.duration) 
        : '--';
    const createdAt = pipeline.created_at 
        ? formatDate(pipeline.created_at) 
        : '--';
    const fullTimestamp = pipeline.created_at || '';

    return `
        <tr class="row-status-${normalizedStatus}">
            <td>
                <span class="pipeline-status ${normalizedStatus}" title="Raw status: ${escapeHtml(status)}">${escapeHtml(status)}</span>
            </td>
            <td>${escapeHtml(pipeline.project_name)}</td>
            <td>${escapeHtml(pipeline.ref || '--')}</td>
            <td>
                <span class="commit-sha">${escapeHtml(pipeline.sha || '--')}</span>
            </td>
            <td>${duration}</td>
            <td title="${escapeHtml(fullTimestamp)}">${createdAt}</td>
            <td>
                ${pipeline.web_url 
                    ? `<a href="${pipeline.web_url}" target="_blank" rel="noopener noreferrer" class="pipeline-link">View →</a>` 
                    : '--'}
            </td>
        </tr>
    `;
}

/**
 * Render pipelines table to the DOM
 * @param {Array} pipelines - Array of pipeline objects
 */
export function renderPipelines(pipelines) {
    const tbody = document.getElementById('pipelineTableBody');
    if (!tbody) return;

    if (pipelines.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="loading">No pipelines found</td></tr>';
        return;
    }

    tbody.innerHTML = pipelines.map(pipeline => createPipelineRow(pipeline)).join('');
}

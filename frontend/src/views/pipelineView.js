// Pipeline view module - Pipeline table rendering
// Pure JavaScript - no external dependencies

import { escapeHtml, formatDate, formatDuration } from '../utils/formatters.js';
import { normalizeStatus } from '../utils/status.js';

/**
 * Determine if failing jobs emphasis should be shown
 * Only show for failing jobs on default branch (DSO priority)
 * @param {boolean} hasFailingJobs - Whether project has failing jobs
 * @param {boolean} isDefaultBranch - Whether pipeline is on default branch
 * @returns {boolean} - True if failing jobs emphasis should be shown
 */
function shouldShowFailingJobsEmphasis(hasFailingJobs, isDefaultBranch) {
    return hasFailingJobs && isDefaultBranch;
}

/**
 * Build CSS class list for pipeline row based on DSO emphasis requirements
 * @param {string} normalizedStatus - Normalized pipeline status
 * @param {boolean} isDefaultBranch - Whether pipeline is on default branch
 * @param {boolean} hasRunnerIssues - Whether project has runner issues
 * @param {boolean} hasFailingJobs - Whether project has failing jobs
 * @returns {string} - Space-separated CSS class names
 */
function buildRowClasses(normalizedStatus, isDefaultBranch, hasRunnerIssues, hasFailingJobs) {
    const classes = [`row-status-${normalizedStatus}`];
    
    // Add default-branch class for emphasis
    if (isDefaultBranch) {
        classes.push('row-default-branch');
    }
    
    // Add runner-issue class for urgent infrastructure problems
    if (hasRunnerIssues) {
        classes.push('row-runner-issue');
    }
    
    // Add failing-jobs class for job failures on default branch
    if (shouldShowFailingJobsEmphasis(hasFailingJobs, isDefaultBranch)) {
        classes.push('row-failing-jobs');
    }
    
    return classes.join(' ');
}

/**
 * Create badge HTML for runner issues or job failures
 * @param {boolean} hasRunnerIssues - Whether project has runner issues
 * @param {boolean} hasFailingJobs - Whether project has failing jobs
 * @param {boolean} isDefaultBranch - Whether pipeline is on default branch
 * @returns {string} - HTML string for badges (empty if no issues)
 */
function createIssueBadges(hasRunnerIssues, hasFailingJobs, isDefaultBranch) {
    const badges = [];
    
    if (hasRunnerIssues) {
        badges.push('<span class="pipeline-issue-badge runner-issue" title="Project has runner/infrastructure issues on default branch" aria-label="Runner issue">⚙️</span>');
    }
    
    if (shouldShowFailingJobsEmphasis(hasFailingJobs, isDefaultBranch)) {
        badges.push('<span class="pipeline-issue-badge failing-jobs" title="Project has failing jobs on default branch" aria-label="Failing jobs">⚠️</span>');
    }
    
    return badges.join(' ');
}

/**
 * Create failure domain badge for pipeline classification
 * Shows classification of pipeline failures: infra vs unknown vs code
 * @param {string|null} failureDomain - Failure domain: 'infra', 'code', 'unknown', 'unclassified', or null
 * @param {boolean|null} classificationAttempted - Whether classification was attempted
 * @returns {string} - HTML string for badge (empty if no badge needed)
 */
export function createFailureDomainBadge(failureDomain, classificationAttempted) {
    // No badge for non-failing pipelines or unclassified failures
    if (!failureDomain || failureDomain === 'unclassified') {
        return '';
    }
    
    // Infrastructure failure - show "Infra" badge
    if (failureDomain === 'infra') {
        return '<span class="failure-domain-badge failure-domain-badge--infra" title="Infrastructure failure detected" aria-label="Infrastructure failure">Infra</span>';
    }
    
    // Unknown failure with verification - show "Unknown (verified)" badge
    if (failureDomain === 'unknown' && classificationAttempted === true) {
        return '<span class="failure-domain-badge failure-domain-badge--unknown-verified" title="Unknown failure cause (classification attempted and verified)" aria-label="Unknown verified failure">Unknown (verified)</span>';
    }
    
    // Code failure - show "Code" badge with subdued styling
    if (failureDomain === 'code') {
        return '<span class="failure-domain-badge failure-domain-badge--code" title="Application code failure detected" aria-label="Code failure">Code</span>';
    }
    
    // Default: no badge for other cases
    return '';
}

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
    
    // DSO emphasis flags from backend
    const isDefaultBranch = pipeline.is_default_branch === true;
    const hasRunnerIssues = pipeline.has_runner_issues === true;
    const hasFailingJobs = pipeline.has_failing_jobs === true;
    
    // Build row classes for styling
    const rowClasses = buildRowClasses(normalizedStatus, isDefaultBranch, hasRunnerIssues, hasFailingJobs);
    
    // Create issue badges if applicable
    const issueBadges = createIssueBadges(hasRunnerIssues, hasFailingJobs, isDefaultBranch);
    
    // Create failure domain badge for failing pipelines
    const failureDomainBadge = createFailureDomainBadge(
        pipeline.failure_domain || null,
        pipeline.classification_attempted || null
    );
    
    // Project name styling: bold for default branch
    const projectNameClass = isDefaultBranch ? 'pipeline-project-name default-branch' : 'pipeline-project-name';
    
    // Branch/ref styling: bold for default branch
    const refClass = isDefaultBranch ? 'pipeline-ref default-branch' : 'pipeline-ref';

    return `
        <tr class="${rowClasses}">
            <td>
                <span class="pipeline-status ${normalizedStatus}" title="Raw status: ${escapeHtml(status)}">${escapeHtml(status)}</span>
                ${issueBadges}
                ${failureDomainBadge}
            </td>
            <td><span class="${projectNameClass}">${escapeHtml(pipeline.project_name)}</span></td>
            <td><span class="${refClass}">${escapeHtml(pipeline.ref || '--')}</span></td>
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

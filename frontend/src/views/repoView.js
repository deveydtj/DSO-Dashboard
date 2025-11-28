// Repository view module - Repository card rendering
// Pure JavaScript - no external dependencies

import { escapeHtml, formatDate, formatDuration } from '../utils/formatters.js';
import { normalizeStatus } from '../utils/status.js';

/**
 * Get a stable unique key for a repository
 * @param {Object} repo - Repository object
 * @returns {string} - Stable key for the repository
 */
export function getRepoKey(repo) {
    // Prefer id (most stable), fallback to path_with_namespace, then name
    if (repo.id != null) {
        return String(repo.id);
    }
    if (repo.path_with_namespace) {
        return repo.path_with_namespace;
    }
    return repo.name || 'unknown';
}

/**
 * Create HTML for a single repository card
 * @param {Object} repo - Repository data
 * @param {string} [extraClasses=''] - Additional CSS classes (e.g., for attention animations)
 * @returns {string} - HTML string for the repo card
 */
export function createRepoCard(repo, extraClasses = '') {
    const description = repo.description || 'No description available';
    const pipelineStatus = repo.last_pipeline_status || null;
    const normalizedStatus = normalizeStatus(pipelineStatus);
    const statusClass = pipelineStatus ? `status-${normalizedStatus}` : 'status-none';
    
    // Pipeline info section
    let pipelineInfo = '';
    if (pipelineStatus) {
        const ref = repo.last_pipeline_ref || 'unknown';
        const duration = repo.last_pipeline_duration != null 
            ? formatDuration(repo.last_pipeline_duration) 
            : '--';
        const updatedAt = repo.last_pipeline_updated_at 
            ? formatDate(repo.last_pipeline_updated_at) 
            : 'unknown';
        
        pipelineInfo = `
            <div class="repo-pipeline">
                <div class="pipeline-status-chip ${normalizedStatus}" title="Status: ${escapeHtml(pipelineStatus)}">
                    <span class="status-dot"></span>
                    <span>${escapeHtml(pipelineStatus)}</span>
                </div>
                <div class="pipeline-details">
                    <span class="pipeline-ref">${escapeHtml(ref)}</span>
                    <span class="pipeline-duration">${duration}</span>
                    <span class="pipeline-time">updated ${updatedAt}</span>
                </div>
            </div>
        `;
    }
    
    // Success rate section
    let successRateSection = '';
    if (repo.recent_success_rate != null) {
        const successPercent = Math.round(repo.recent_success_rate * 100);
        successRateSection = `
            <div class="repo-success-rate" title="Recent success rate across all branches (excludes skipped/manual/canceled pipelines)">
                <div class="success-rate-label">
                    <span>Recent Success Rate</span>
                    <span class="success-rate-value">${successPercent}%</span>
                </div>
                <div class="success-rate-bar">
                    <div class="success-rate-fill" style="width: ${successPercent}%"></div>
                </div>
            </div>
        `;
    }

    // Combine status class with any extra attention classes
    const cardClasses = `repo-card ${statusClass}${extraClasses}`;

    return `
        <div class="${cardClasses}">
            <div class="repo-header">
                <div>
                    <h3 class="repo-name">${escapeHtml(repo.name)}</h3>
                </div>
                <span class="repo-visibility">${escapeHtml(repo.visibility)}</span>
            </div>
            <p class="repo-description">${escapeHtml(description)}</p>
            ${pipelineInfo}
            ${successRateSection}
            ${repo.web_url ? `<a href="${repo.web_url}" target="_blank" rel="noopener noreferrer" class="repo-link">View on GitLab →</a>` : ''}
        </div>
    `;
}

/**
 * Sort repositories by priority:
 * (1) consecutive default-branch failures
 * (2) recent all-branch success rate
 * (3) last pipeline status
 * (4) name alphabetically
 * @param {Array} repos - Array of repository objects
 * @returns {Array} - Sorted array of repositories
 */
function sortRepositories(repos) {
    return [...repos].sort((a, b) => {
        // First priority: consecutive_default_branch_failures DESC
        const failuresA = a.consecutive_default_branch_failures || 0;
        const failuresB = b.consecutive_default_branch_failures || 0;
        if (failuresB !== failuresA) {
            return failuresB - failuresA;
        }

        // Second priority: recent_success_rate (lower is worse, so sort ascending)
        // Repos with no success rate data (null/undefined) sort after those with data
        const successA = typeof a.recent_success_rate === 'number' ? a.recent_success_rate : null;
        const successB = typeof b.recent_success_rate === 'number' ? b.recent_success_rate : null;
        if (successA !== null && successB !== null) {
            // Both have numeric values - lower success rate comes first
            if (successA !== successB) {
                return successA - successB;
            }
        } else if (successA !== null && successB === null) {
            // A has data, B doesn't - A comes first
            return -1;
        } else if (successA === null && successB !== null) {
            // B has data, A doesn't - B comes first
            return 1;
        }
        // Both null or equal - fall through to next priority

        // Third priority: failed/running pipelines first (using normalized status)
        const normalizedStatusA = normalizeStatus(a.last_pipeline_status);
        const normalizedStatusB = normalizeStatus(b.last_pipeline_status);
        
        const statusPriorityMap = {
            'failed': 0,
            'running': 1,
            'pending': 2,
            'manual': 3,
            'success': 4,
            'canceled': 5,
            'skipped': 6,
            'other': 7
        };
        
        const priorityA = statusPriorityMap[normalizedStatusA] ?? 7;
        const priorityB = statusPriorityMap[normalizedStatusB] ?? 7;
        if (priorityA !== priorityB) {
            return priorityA - priorityB;
        }

        // Fourth priority: alphabetical by name
        const nameA = (a.name || '').toLowerCase();
        const nameB = (b.name || '').toLowerCase();
        return nameA.localeCompare(nameB);
    });
}

/**
 * Render repositories to the DOM
 * @param {Array} repos - Array of repository objects
 * @param {Map} previousState - Map of previous repo states { status, index }
 * @returns {Map} - Updated state map for next render cycle
 */
export function renderRepositories(repos, previousState) {
    const container = document.getElementById('repoGrid');
    if (!container) return previousState;

    if (repos.length === 0) {
        container.innerHTML = '<div class="loading">No repositories found</div>';
        return new Map();
    }

    // Grab previous state for change detection
    const prevState = previousState;
    const nextState = new Map();

    // Sort repositories
    const sortedRepos = sortRepositories(repos);

    // Generate cards with attention classes based on state changes
    const cardsHtml = sortedRepos.map((repo, currentIndex) => {
        const key = getRepoKey(repo);
        const normalizedStatus = normalizeStatus(repo.last_pipeline_status);
        const prev = prevState.get(key);

        // Determine if status degraded (any status -> failed is considered degradation)
        const hasDegradedStatus = prev && normalizedStatus === 'failed' && prev.status !== 'failed';

        // Determine if position changed
        const hasMoved = prev && prev.index !== currentIndex;

        // Build extra CSS classes - prefer degradation over movement
        let attentionClass = '';
        if (hasDegradedStatus) {
            attentionClass = ' repo-status-degraded';
        } else if (hasMoved) {
            attentionClass = ' repo-moved';
        }

        // Store new state for next refresh
        nextState.set(key, { status: normalizedStatus, index: currentIndex });

        return createRepoCard(repo, attentionClass);
    }).join('');

    container.innerHTML = cardsHtml;

    // Return updated state for subsequent refreshes
    return nextState;
}

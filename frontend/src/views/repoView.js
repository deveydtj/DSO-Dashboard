// Repository view module - Repository card rendering
// Pure JavaScript - no external dependencies

import { escapeHtml, formatDate, formatDuration } from '../utils/formatters.js';
import { normalizeStatus } from '../utils/status.js';

/**
 * DSO Status priority levels for repo card status determination.
 * Reflects what DSO members actually care about:
 * - Default-branch health
 * - Runner issues
 * - Failing jobs
 * NOT noisy dev/feature branch flakiness.
 */
const DSO_STATUS = {
    RUNNER_ISSUE: 'runner-issue',   // High-priority: infrastructure problem
    FAILING: 'failing',             // Default branch has consecutive failures
    WARNING: 'warning',             // Default branch has some failures
    DEGRADED: 'degraded',           // Default branch success rate below threshold
    HEALTHY: 'healthy',             // Default branch is healthy
    UNKNOWN: 'unknown'              // No data available
};

// Thresholds for DSO status determination
const DSO_THRESHOLDS = {
    HEALTHY_MIN_RATE: 0.9,   // 90%+ success rate = healthy
    WARNING_MIN_RATE: 0.7    // 70-89% = degraded, below 70% = warning
};

/**
 * Determine the DSO-focused status for a repository.
 * Priority order:
 * 1. has_runner_issues → high-priority error (runner-issue)
 * 2. consecutive_default_branch_failures > 0 → failing
 * 3. has_failing_jobs on default branch → warning
 * 4. Otherwise use default-branch success rate for healthy/warning/degraded
 * 
 * @param {Object} repo - Repository data with DSO fields
 * @returns {string} - DSO status (runner-issue, failing, warning, degraded, healthy, unknown)
 */
export function getDsoStatus(repo) {
    // Priority 1: Runner issues are high-priority errors
    if (repo.has_runner_issues) {
        return DSO_STATUS.RUNNER_ISSUE;
    }
    
    // Priority 2: Consecutive default-branch failures indicate broken state
    const consecutiveFailures = repo.consecutive_default_branch_failures || 0;
    if (consecutiveFailures > 0) {
        return DSO_STATUS.FAILING;
    }
    
    // Priority 3: Has failing jobs on default branch (but not consecutive)
    if (repo.has_failing_jobs) {
        return DSO_STATUS.WARNING;
    }
    
    // Priority 4: Use default-branch success rate
    // Note: recent_success_rate is now default-branch rate (see backend)
    const successRate = repo.recent_success_rate;
    if (successRate == null) {
        return DSO_STATUS.UNKNOWN;
    }
    
    if (successRate >= DSO_THRESHOLDS.HEALTHY_MIN_RATE) {
        return DSO_STATUS.HEALTHY;
    } else if (successRate >= DSO_THRESHOLDS.WARNING_MIN_RATE) {
        return DSO_STATUS.DEGRADED;
    } else {
        return DSO_STATUS.WARNING;
    }
}

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
 * Uses DSO-focused status for card styling based on:
 * - Runner issues (high priority)
 * - Default branch failures
 * - Default branch success rate
 * 
 * @param {Object} repo - Repository data
 * @param {string} [extraClasses=''] - Additional CSS classes (e.g., for attention animations)
 * @returns {string} - HTML string for the repo card
 */
export function createRepoCard(repo, extraClasses = '') {
    const description = repo.description || 'No description available';
    const pipelineStatus = repo.last_pipeline_status || null;
    const normalizedStatus = normalizeStatus(pipelineStatus);
    
    // Get DSO-focused status for card styling
    const dsoStatus = getDsoStatus(repo);
    const statusClass = `status-${dsoStatus}`;
    
    // Generate DSO indicator badges
    let dsoIndicators = '';
    
    // Runner issue badge (high priority)
    if (repo.has_runner_issues) {
        dsoIndicators += '<span class="dso-badge dso-badge-runner" title="Runner infrastructure issue detected">⚠️ Runner Issue</span>';
    }
    
    // Consecutive failures badge
    const consecutiveFailures = repo.consecutive_default_branch_failures || 0;
    if (consecutiveFailures > 0) {
        dsoIndicators += `<span class="dso-badge dso-badge-failing" title="${consecutiveFailures} consecutive failure(s) on default branch">🔴 ${consecutiveFailures} Consecutive Failure${consecutiveFailures > 1 ? 's' : ''}</span>`;
    }
    
    // Failing jobs indicator (if not already showing consecutive failures)
    if (repo.has_failing_jobs && consecutiveFailures === 0) {
        const failingCount = repo.failing_jobs_count || 0;
        if (failingCount > 0) {
            dsoIndicators += `<span class="dso-badge dso-badge-warning" title="${failingCount} failed pipeline(s) on default branch">⚠️ ${failingCount} Failed</span>`;
        }
    }
    
    // Wrap indicators if any
    const indicatorsHtml = dsoIndicators ? `<div class="dso-indicators">${dsoIndicators}</div>` : '';
    
    // Pipeline info section (shows last pipeline regardless of branch)
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
    
    // Success rate section - now shows default-branch rate as primary
    let successRateSection = '';
    if (repo.recent_success_rate != null) {
        const successPercent = Math.round(repo.recent_success_rate * 100);
        
        // Determine bar color class based on success rate
        let barColorClass = '';
        if (successPercent >= 90) {
            barColorClass = 'rate-healthy';
        } else if (successPercent >= 70) {
            barColorClass = 'rate-degraded';
        } else {
            barColorClass = 'rate-warning';
        }
        
        successRateSection = `
            <div class="repo-success-rate" title="Default branch success rate (excludes skipped/manual/canceled pipelines)">
                <div class="success-rate-label">
                    <span>Default Branch</span>
                    <span class="success-rate-value">${successPercent}%</span>
                </div>
                <div class="success-rate-bar">
                    <div class="success-rate-fill ${barColorClass}" style="width: ${successPercent}%"></div>
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
            ${indicatorsHtml}
            ${pipelineInfo}
            ${successRateSection}
            ${repo.web_url ? `<a href="${repo.web_url}" target="_blank" rel="noopener noreferrer" class="repo-link">View on GitLab →</a>` : ''}
        </div>
    `;
}

/**
 * Sort repositories by DSO priority:
 * (1) runner issues (highest priority - infrastructure problem)
 * (2) consecutive default-branch failures
 * (3) has failing jobs
 * (4) recent default-branch success rate (lower is worse)
 * (5) last pipeline status
 * (6) name alphabetically
 * @param {Array} repos - Array of repository objects
 * @returns {Array} - Sorted array of repositories
 */
function sortRepositories(repos) {
    return [...repos].sort((a, b) => {
        // First priority: runner issues are infrastructure problems - highest priority
        const runnerA = a.has_runner_issues ? 1 : 0;
        const runnerB = b.has_runner_issues ? 1 : 0;
        if (runnerB !== runnerA) {
            return runnerB - runnerA;
        }
        
        // Second priority: consecutive_default_branch_failures DESC
        const failuresA = a.consecutive_default_branch_failures || 0;
        const failuresB = b.consecutive_default_branch_failures || 0;
        if (failuresB !== failuresA) {
            return failuresB - failuresA;
        }
        
        // Third priority: has_failing_jobs (repos with failures come first)
        const hasFailingA = a.has_failing_jobs ? 1 : 0;
        const hasFailingB = b.has_failing_jobs ? 1 : 0;
        if (hasFailingB !== hasFailingA) {
            return hasFailingB - hasFailingA;
        }

        // Fourth priority: recent_success_rate (lower is worse, so sort ascending)
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

        // Fifth priority: failed/running pipelines first (using normalized status)
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

        // Sixth priority: alphabetical by name
        const nameA = (a.name || '').toLowerCase();
        const nameB = (b.name || '').toLowerCase();
        return nameA.localeCompare(nameB);
    });
}

/**
 * Render repositories to the DOM
 * Uses DSO status for degradation detection (e.g., healthy → failing triggers animation)
 * 
 * @param {Array} repos - Array of repository objects
 * @param {Map} previousState - Map of previous repo states { dsoStatus, index }
 * @returns {Map} - Updated state map for next render cycle
 */
export function renderRepositories(repos, previousState) {
    const container = document.getElementById('repoGrid');
    if (!container) return new Map();

    if (repos.length === 0) {
        container.innerHTML = '<div class="loading">No repositories found</div>';
        return new Map();
    }

    // Grab previous state for change detection
    const prevState = previousState;
    const nextState = new Map();

    // Sort repositories by DSO priority
    const sortedRepos = sortRepositories(repos);

    // DSO status degradation priority (higher number = worse status)
    const dsoStatusPriority = {
        'healthy': 0,
        'unknown': 1,
        'degraded': 2,
        'warning': 3,
        'failing': 4,
        'runner-issue': 5
    };

    // Generate cards with attention classes based on state changes
    const cardsHtml = sortedRepos.map((repo, currentIndex) => {
        const key = getRepoKey(repo);
        const dsoStatus = getDsoStatus(repo);
        const prev = prevState.get(key);

        // Determine if DSO status degraded (any status -> worse status is considered degradation)
        const prevPriority = prev ? (dsoStatusPriority[prev.dsoStatus] ?? 0) : 0;
        const currentPriority = dsoStatusPriority[dsoStatus] ?? 0;
        const hasDegradedStatus = prev && currentPriority > prevPriority;

        // Determine if position changed
        const hasMoved = prev && prev.index !== currentIndex;

        // Build extra CSS classes - prefer degradation over movement
        let attentionClass = '';
        if (hasDegradedStatus) {
            attentionClass = ' repo-status-degraded';
        } else if (hasMoved) {
            attentionClass = ' repo-moved';
        }

        // Store new state for next refresh (use dsoStatus instead of normalizedStatus)
        nextState.set(key, { dsoStatus: dsoStatus, index: currentIndex });

        return createRepoCard(repo, attentionClass);
    }).join('');

    container.innerHTML = cardsHtml;

    // Return updated state for subsequent refreshes
    return nextState;
}

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
 * Get success rate color class based on DSO thresholds
 * @param {number} successRate - Success rate as decimal (0-1)
 * @returns {string} - CSS class for the color (rate-healthy, rate-degraded, rate-warning)
 */
function getSuccessRateColorClass(successRate) {
    if (successRate >= DSO_THRESHOLDS.HEALTHY_MIN_RATE) {
        return 'rate-healthy';
    } else if (successRate >= DSO_THRESHOLDS.WARNING_MIN_RATE) {
        return 'rate-degraded';
    }
    return 'rate-warning';
}

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
    // The backend's recent_success_rate field now reflects default-branch rate
    // (set by enrich_projects_with_pipelines in gitlab_client.py)
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
 * Compute the remaining error budget percentage for a repo.
 * Formula: If observed >= target, budget = 100%. Otherwise, budget = max(0, 100 * (1 - (target - observed) / (1 - target)))
 * 
 * @param {number|null} observedRate - Repo's recent success rate (0-1)
 * @param {number} targetRate - SLO target success rate (0-1), defaults to 0.99
 * @returns {number|null} - Remaining budget percentage (0-100) or null if observedRate is null
 */
export function computeErrorBudgetRemaining(observedRate, targetRate = 0.99) {
    if (observedRate === null || observedRate === undefined) {
        return null;
    }
    // If observed rate meets or exceeds target, budget is 100%
    if (observedRate >= targetRate) {
        return 100;
    }
    // Error budget = 1 - target (the allowed error margin)
    // Consumed = target - observed
    // Remaining % = max(0, 100 * (1 - consumed / errorBudget))
    const errorBudget = 1 - targetRate;
    if (errorBudget <= 0) {
        // Edge case: target is 100%, any failure exhausts budget
        return 0;
    }
    const consumed = targetRate - observedRate;
    const remainingPct = Math.max(0, Math.min(100, 100 * (1 - consumed / errorBudget)));
    return remainingPct;
}

/**
 * Error budget color thresholds matching the KPI SLO bar
 * These constants define when the budget bar changes color:
 * - >= HEALTHY_MIN (50%): Green - comfortable remaining budget
 * - >= WARNING_MIN (20%): Yellow - budget getting tight
 * - < WARNING_MIN: Red - budget nearly or fully exhausted
 */
const ERROR_BUDGET_THRESHOLDS = {
    HEALTHY_MIN: 50,    // >= 50% remaining = green (budget-healthy)
    WARNING_MIN: 20     // >= 20% remaining = yellow (budget-warning), < 20% = red (budget-critical)
};

/**
 * Get the CSS class for error budget bar color based on remaining percentage.
 * @param {number} remaining - Remaining budget percentage (0-100)
 * @returns {string} - CSS class name
 */
function getErrorBudgetColorClass(remaining) {
    if (remaining >= ERROR_BUDGET_THRESHOLDS.HEALTHY_MIN) {
        return 'budget-healthy';
    } else if (remaining >= ERROR_BUDGET_THRESHOLDS.WARNING_MIN) {
        return 'budget-warning';
    }
    return 'budget-critical';
}

/**
 * Generate sparkline HTML for a history array of success rates.
 * Normalizes success rates (0-1) into 5 height buckets.
 * Returns empty string if history has fewer than 2 numeric entries.
 * 
 * @param {Array<number>|null} history - Array of success rate values (0-1)
 * @returns {string} - Sparkline HTML or empty string
 */
export function createRepoSparkline(history) {
    // Return empty if no history or fewer than 2 numeric entries
    if (!Array.isArray(history)) return '';
    
    const numericValues = history.filter(v => typeof v === 'number' && Number.isFinite(v));
    if (numericValues.length < 2) return '';
    
    // Normalize each value to 1-5 based on success rate buckets:
    // h1: 0-20%, h2: 20-40%, h3: 40-60%, h4: 60-80%, h5: 80-100%
    const bars = numericValues.map(val => {
        // Clamp value to 0-1 range
        const clamped = Math.max(0, Math.min(1, val));
        // Convert to height bucket (1-5)
        const bucket = Math.min(5, Math.max(1, Math.ceil(clamped * 5)));
        return `<span class="sparkline-bar sparkline-bar--h${bucket}"></span>`;
    }).join('');
    
    return `<div class="sparkline sparkline--repo" aria-label="Recent default-branch success trend">${bars}</div>`;
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
 * @param {Object} [sloConfig=null] - Optional SLO configuration
 * @param {number} [sloConfig.defaultBranchSuccessTarget] - SLO target for default branch success rate (0-1)
 * @param {Array<number>|null} [history=null] - Optional history array of success rates for sparkline
 * @returns {string} - HTML string for the repo card
 */
export function createRepoCard(repo, extraClasses = '', sloConfig = null, history = null) {
    const description = repo.description || '';
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
        dsoIndicators += `<span class="dso-badge dso-badge-failing" title="${escapeHtml(String(consecutiveFailures))} consecutive failure(s) on default branch">🔴 ${escapeHtml(String(consecutiveFailures))} Consecutive Failure${consecutiveFailures > 1 ? 's' : ''}</span>`;
    }
    
    // Failing jobs indicator (if not already showing consecutive failures)
    if (repo.has_failing_jobs && consecutiveFailures === 0) {
        const failingCount = repo.failing_jobs_count || 0;
        if (failingCount > 0) {
            dsoIndicators += `<span class="dso-badge dso-badge-warning" title="${escapeHtml(String(failingCount))} failed pipeline(s) on default branch">⚠️ ${escapeHtml(String(failingCount))} Failed</span>`;
        }
    }
    
    // Wrap indicators if any
    const indicatorsHtml = dsoIndicators ? `<div class="dso-indicators" role="status" aria-label="Repository health indicators">${dsoIndicators}</div>` : '';
    
    // Pipeline info section - only show chip if last pipeline is on default branch
    let pipelineInfo = '';
    const isDefaultBranchPipeline = pipelineStatus && 
        repo.last_pipeline_ref && 
        repo.default_branch && 
        repo.last_pipeline_ref === repo.default_branch;
    
    if (isDefaultBranchPipeline) {
        const ref = repo.last_pipeline_ref;
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
    } else if (pipelineStatus) {
        // Last pipeline is not on default branch - show fallback
        pipelineInfo = `
            <div class="repo-pipeline repo-pipeline-fallback">
                <span class="pipeline-fallback-text">No recent default-branch pipelines</span>
            </div>
        `;
    }
    
    // Success rate section - now shows default-branch rate as primary
    let successRateSection = '';
    if (repo.recent_success_rate != null) {
        const successPercent = Math.min(100, Math.max(0, Math.round(repo.recent_success_rate * 100)));
        
        // Determine bar color class based on success rate using shared threshold logic
        const barColorClass = getSuccessRateColorClass(repo.recent_success_rate);
        
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

    // Error budget section - shows remaining error budget based on SLO target
    let errorBudgetSection = '';
    
    // Sanitize sloTarget: ensure it's a valid number between 0 and 1, fallback to 0.99 if invalid
    let sloTargetRaw = sloConfig?.defaultBranchSuccessTarget;
    let sloTargetNum = Number(sloTargetRaw);
    if (isNaN(sloTargetNum) || sloTargetNum <= 0 || sloTargetNum > 1) {
        sloTargetNum = 0.99;
    }
    const errorBudgetRemaining = computeErrorBudgetRemaining(repo.recent_success_rate, sloTargetNum);
    
    if (errorBudgetRemaining !== null) {
        // Value is already clamped and finite by computeErrorBudgetRemaining; just round
        const safeRemainingPct = Math.round(errorBudgetRemaining);
        const budgetColorClass = getErrorBudgetColorClass(errorBudgetRemaining);
        const sloTargetPercent = Math.round(sloTargetNum * 100);
        
        errorBudgetSection = `
            <div class="repo-error-budget" title="Error budget remaining based on SLO target of ${sloTargetPercent}%">
                <span class="repo-error-budget-label">Error budget: ${safeRemainingPct}% remaining</span>
                <div class="repo-error-budget-bar-container" role="progressbar" aria-valuenow="${safeRemainingPct}" aria-valuemin="0" aria-valuemax="100" aria-label="Error budget remaining: ${safeRemainingPct}%">
                    <div class="repo-error-budget-bar ${budgetColorClass}" data-remaining="${safeRemainingPct}" style="width: ${safeRemainingPct}%"></div>
                </div>
            </div>
        `;
    } else {
        errorBudgetSection = `
            <div class="repo-error-budget">
                <span class="repo-error-budget-label">Error budget: N/A</span>
            </div>
        `;
    }

    // Generate sparkline for success rate trend (placed near success rate display)
    const sparklineHtml = createRepoSparkline(history);

    // Combine status class with any extra attention classes
    const cardClasses = `repo-card ${statusClass}${extraClasses}`;

    // Only display description if repo has one
    const descriptionHtml = description ? `<p class="repo-description">${escapeHtml(description)}</p>` : '';

    return `
        <div class="${cardClasses}">
            <div class="repo-header">
                <div>
                    <h3 class="repo-name">${escapeHtml(repo.name)}</h3>
                </div>
                <span class="repo-visibility">${escapeHtml(repo.visibility)}</span>
            </div>
            ${descriptionHtml}
            ${indicatorsHtml}
            ${pipelineInfo}
            ${successRateSection}
            ${sparklineHtml}
            ${errorBudgetSection}
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
 * @param {Object} [sloConfig=null] - Optional SLO configuration to pass to createRepoCard
 * @param {number} [sloConfig.defaultBranchSuccessTarget] - SLO target for default branch success rate (0-1)
 * @param {Map} [historyMap=undefined] - Optional Map of repo key to history array (success rates)
 * @returns {Map} - Updated state map for next render cycle
 */
export function renderRepositories(repos, previousState, sloConfig = null, historyMap = undefined) {
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

        // Get history for this repo (if available)
        const history = historyMap?.get(key) ?? null;

        return createRepoCard(repo, attentionClass, sloConfig, history);
    }).join('');

    container.innerHTML = cardsHtml;

    // Return updated state for subsequent refreshes
    return nextState;
}

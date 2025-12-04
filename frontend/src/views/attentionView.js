// Attention strip view module - "Things That Need Attention" rendering
// Pure JavaScript - no external dependencies

import { normalizeServiceStatus } from '../utils/status.js';

// Default SLO target when summary doesn't provide one
const DEFAULT_SLO_TARGET = 0.9;

// Severity priority for sorting (lower = higher priority)
const SEVERITY_PRIORITY = {
    critical: 0,
    high: 1,
    medium: 2,
    low: 3
};

// Maximum number of items to display
const MAX_ATTENTION_ITEMS = 8;

/**
 * Build attention items from repositories that need attention.
 * @param {Array} repos - Repository list
 * @param {number} sloTarget - SLO target for success rate
 * @returns {Array} - Array of attention items for repositories
 */
function buildRepoAttentionItems(repos, sloTarget) {
    const items = [];
    const seenIds = new Set();

    for (const repo of repos) {
        // Use path_with_namespace or id as stable identifier
        const repoId = repo.path_with_namespace || repo.id;
        if (!repoId || seenIds.has(repoId)) continue;

        // Check for runner issues - critical severity
        if (repo.has_runner_issues === true) {
            seenIds.add(repoId);
            items.push({
                type: 'repo',
                id: repoId,
                name: repo.name || repoId,
                reason: 'Runner issue',
                severity: 'critical'
            });
            continue; // Only one item per repo, highest severity wins
        }

        // Check for consecutive default branch failures - high severity
        // Use defensive check for null/undefined
        if ((repo.consecutive_default_branch_failures || 0) > 0) {
            seenIds.add(repoId);
            const count = repo.consecutive_default_branch_failures || 0;
            items.push({
                type: 'repo',
                id: repoId,
                name: repo.name || repoId,
                reason: `Default branch failing ${count} time${count > 1 ? 's' : ''} in a row`,
                severity: 'high'
            });
            continue;
        }

        // Check for low success rate (below SLO target) - medium severity
        if (repo.recent_success_rate != null && repo.recent_success_rate < sloTarget) {
            seenIds.add(repoId);
            const pct = Math.round(repo.recent_success_rate * 100);
            items.push({
                type: 'repo',
                id: repoId,
                name: repo.name || repoId,
                reason: `Success rate ${pct}% below target`,
                severity: 'medium'
            });
        }
    }

    return items;
}

/**
 * Build attention items from services that need attention.
 * @param {Array} services - Service list
 * @returns {Array} - Array of attention items for services
 */
function buildServiceAttentionItems(services) {
    const items = [];
    const seenIds = new Set();

    for (const service of services) {
        const serviceId = service.id || service.name || service.url;
        if (!serviceId || seenIds.has(serviceId)) continue;

        const status = normalizeServiceStatus(service.status);

        // Check for offline/unhealthy services - critical severity
        if (status !== 'UP') {
            seenIds.add(serviceId);
            items.push({
                type: 'service',
                id: serviceId,
                name: service.name || serviceId,
                reason: status === 'DOWN' ? 'Service offline' : 'Service status unknown',
                severity: 'critical'
            });
            continue;
        }

        // Check for latency warning - medium severity
        if (service.latency_trend === 'warning') {
            seenIds.add(serviceId);
            items.push({
                type: 'service',
                id: serviceId,
                name: service.name || serviceId,
                reason: 'Latency degradation',
                severity: 'medium'
            });
        }
    }

    return items;
}

/**
 * Build attention items from pipelines that need attention.
 * Only includes the most recent pipeline on default branch with issues.
 * @param {Array} pipelines - Pipeline list (should be safe array)
 * @param {Array} repos - Repository list (should be safe array, used to determine default branches)
 * @returns {Array} - Array of attention items for pipelines
 */
function buildPipelineAttentionItems(pipelines, repos) {
    // Ensure arrays are safe (this function is called from buildAttentionItems which already ensures safety)
    const safePipelines = pipelines || [];
    const safeRepos = repos || [];

    // Build a map of project_id to default_branch
    const defaultBranches = new Map();
    for (const repo of safeRepos) {
        if (repo.id && repo.default_branch) {
            defaultBranches.set(repo.id, repo.default_branch);
        }
    }

    // Find pipelines on default branch with issues
    const pipelineIssues = [];
    for (const pipeline of safePipelines) {
        const defaultBranch = defaultBranches.get(pipeline.project_id);
        const isDefaultBranch = defaultBranch && pipeline.ref === defaultBranch;

        if (!isDefaultBranch) continue;

        // Check for runner issues or failing jobs
        // Note: has_runner_issues and has_failing_jobs are project-level flags copied to pipelines,
        // not pipeline-specific indicators. This flags pipelines from projects with known issues.
        if (pipeline.has_runner_issues === true || pipeline.has_failing_jobs === true) {
            pipelineIssues.push({
                pipeline,
                reason: pipeline.has_runner_issues ? 'Runner issue' : 'Failing jobs',
                severity: pipeline.has_runner_issues ? 'critical' : 'high'
            });
        }
    }

    // Sort by created_at descending and take only the most recent
    if (pipelineIssues.length === 0) return [];

    pipelineIssues.sort((a, b) => {
        const dateA = new Date(a.pipeline.created_at || 0);
        const dateB = new Date(b.pipeline.created_at || 0);
        return dateB - dateA;
    });

    const most = pipelineIssues[0];
    return [{
        type: 'pipeline',
        id: most.pipeline.id,
        name: most.pipeline.project_name || `Pipeline #${most.pipeline.id}`,
        reason: most.reason,
        severity: most.severity
    }];
}

/**
 * Build attention items from all data sources.
 * @param {Object} params - Data to analyze for attention items
 * @param {Object|null} params.summary - Summary data from API
 * @param {Array} params.repos - Repository list
 * @param {Array} params.services - Service list
 * @param {Array} params.pipelines - Pipeline list
 * @returns {Array} - Array of attention items with type, id, name, reason, severity
 */
export function buildAttentionItems({ summary, repos, services, pipelines }) {
    const safeRepos = repos || [];
    const safeServices = services || [];
    const safePipelines = pipelines || [];

    // Get SLO target from summary or use default
    const sloTarget = summary?.pipeline_slo_target_default_branch_success_rate ?? DEFAULT_SLO_TARGET;

    // Build items from each source
    const repoItems = buildRepoAttentionItems(safeRepos, sloTarget);
    const serviceItems = buildServiceAttentionItems(safeServices);
    const pipelineItems = buildPipelineAttentionItems(safePipelines, safeRepos);

    // Combine all items
    const allItems = [...repoItems, ...serviceItems, ...pipelineItems];

    // Sort by severity (critical first), then by name
    // Unknown severities go to end (priority 999)
    allItems.sort((a, b) => {
        const severityA = SEVERITY_PRIORITY[a.severity] ?? 999;
        const severityB = SEVERITY_PRIORITY[b.severity] ?? 999;
        const severityDiff = severityA - severityB;
        if (severityDiff !== 0) return severityDiff;
        return (a.name || '').localeCompare(b.name || '');
    });

    // Truncate to maximum items
    return allItems.slice(0, MAX_ATTENTION_ITEMS);
}

/**
 * Get type icon for attention item
 * @param {string} type - Item type (repo, service, pipeline)
 * @returns {string} - Emoji icon
 */
function getTypeIcon(type) {
    switch (type) {
        case 'repo': return '📦';
        case 'service': return '⚙️';  // Single-codepoint emoji for cross-platform consistency
        case 'pipeline': return '🔧';
        default: return '⚠️';
    }
}

/**
 * Render the attention strip based on current data.
 * Shows an "all clear" message when no items need attention.
 * Shows a horizontal list of chips/pills when items exist.
 * @param {Object} params - Data to analyze for attention items
 * @param {Object|null} params.summary - Summary data from API
 * @param {Array} params.repos - Repository list
 * @param {Array} params.services - Service list
 * @param {Array} params.pipelines - Pipeline list
 */
export function renderAttentionStrip({ summary, repos, services, pipelines }) {
    const strip = document.getElementById('attentionStrip');
    if (!strip) {
        return;
    }

    // Ensure arrays are never null/undefined
    const safeRepos = repos || [];
    const safeServices = services || [];
    const safePipelines = pipelines || [];

    // Build attention items
    const items = buildAttentionItems({
        summary,
        repos: safeRepos,
        services: safeServices,
        pipelines: safePipelines
    });

    // Clear previous content
    strip.innerHTML = '';

    if (items.length === 0) {
        // Show "all clear" message
        strip.classList.add('attention-strip--empty');
        const clearMessage = document.createElement('span');
        clearMessage.className = 'attention-clear-message';
        clearMessage.textContent = '✓ All clear – nothing needs attention right now';
        strip.appendChild(clearMessage);
    } else {
        // Show attention items as pills/chips
        strip.classList.remove('attention-strip--empty');
        items.forEach(item => {
            const chip = document.createElement('div');
            // Build CSS classes: attention-item attention-item--TYPE attention-item--SEVERITY
            const classes = [
                'attention-item',
                `attention-item--${item.type}`,
                `attention-item--${item.severity}`
            ];
            chip.className = classes.join(' ');
            
            // Build pill content using createElement for better maintainability
            // and automatic escaping via textContent
            const iconSpan = document.createElement('span');
            iconSpan.className = 'attention-item-icon';
            iconSpan.textContent = getTypeIcon(item.type);

            const nameSpan = document.createElement('span');
            nameSpan.className = 'attention-item-name';
            nameSpan.textContent = item.name;

            const reasonSpan = document.createElement('span');
            reasonSpan.className = 'attention-item-reason';
            reasonSpan.textContent = item.reason;

            chip.appendChild(iconSpan);
            chip.appendChild(nameSpan);
            chip.appendChild(reasonSpan);
            
            strip.appendChild(chip);
        });
    }
}

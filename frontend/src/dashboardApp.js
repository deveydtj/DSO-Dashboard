// GitLab Dashboard Frontend Application
// Pure JavaScript - no external dependencies
// ES Module - DashboardApp class

// Import utility modules
import { escapeHtml, formatDate, formatDuration } from './utils/formatters.js';
import { normalizeStatus, normalizeServiceStatus } from './utils/status.js';
import {
    showError,
    updateStatusIndicator,
    updateLastUpdated,
    showPartialStaleWarning,
    showAllStaleWarning,
    updateMockBadge
} from './utils/dom.js';
import {
    fetchWithTimeout,
    fetchSummary,
    fetchRepos,
    fetchPipelines,
    fetchServices,
    checkBackendHealth
} from './api/apiClient.js';

export class DashboardApp {
    constructor() {
        this.apiBase = window.location.origin;
        this.refreshInterval = 60000; // 60 seconds
        this.fetchTimeout = 8000; // 8 seconds timeout for API requests
        this.updateTimer = null;
        this.cachedData = {
            summary: null,
            repos: null,
            pipelines: null,
            services: null
        };
        // Track per-repo state between refreshes for animation detection
        // Stores { status: normalizedStatus, index: sortedPosition } per repo key
        this.repoState = new Map();
        this.init();
    }

    /**
     * Get a stable unique key for a repository
     * @param {Object} repo - Repository object
     * @returns {string} - Stable key for the repository
     */
    getRepoKey(repo) {
        // Prefer id (most stable), fallback to path_with_namespace, then name
        if (repo.id != null) {
            return String(repo.id);
        }
        if (repo.path_with_namespace) {
            return repo.path_with_namespace;
        }
        return repo.name || 'unknown';
    }

    init() {
        console.log('🚀 Initializing GitLab DSO Dashboard...');
        this.checkTVMode();
        this.checkDensityMode();
        this.setupTVToggle();
        this.setupDensityToggle();
        this.setupWallboardPreset();
        this.checkHealth();
        this.loadAllData();
        this.startAutoRefresh();
    }

    checkTVMode() {
        // Check for ?tv=1 URL parameter
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('tv') === '1') {
            document.body.classList.add('tv');
            console.log('📺 TV mode enabled');
        }
    }

    checkDensityMode() {
        // Check for ?density=compact URL parameter
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('density') === 'compact') {
            document.body.classList.add('compact');
            console.log('📏 Compact mode enabled');
        }
    }

    setupTVToggle() {
        const toggle = document.getElementById('tvToggle');
        if (!toggle) return;

        // Read current mode from body class
        const isTVMode = document.body.classList.contains('tv');
        
        // Set toggle UI state
        if (isTVMode) {
            toggle.classList.add('active');
        }

        // Add click handler
        toggle.addEventListener('click', () => {
            const isCurrentlyTV = document.body.classList.contains('tv');
            
            if (isCurrentlyTV) {
                // Disable TV mode
                document.body.classList.remove('tv');
                toggle.classList.remove('active');
                console.log('📺 TV mode disabled');
                
                // Remove tv parameter from URL
                const url = new URL(window.location);
                url.searchParams.delete('tv');
                window.history.replaceState({}, '', url);
            } else {
                // Enable TV mode
                document.body.classList.add('tv');
                toggle.classList.add('active');
                console.log('📺 TV mode enabled');
                
                // Add tv=1 parameter to URL
                const url = new URL(window.location);
                url.searchParams.set('tv', '1');
                window.history.replaceState({}, '', url);
            }
            
            // Update wallboard button state
            this.updateWallboardButtonState();
        });
    }

    setupDensityToggle() {
        const toggle = document.getElementById('densityToggle');
        if (!toggle) return;

        // Read current mode from body class
        const isCompactMode = document.body.classList.contains('compact');
        
        // Set toggle UI state
        if (isCompactMode) {
            toggle.classList.add('active');
        }

        // Add click handler
        toggle.addEventListener('click', () => {
            const isCurrentlyCompact = document.body.classList.contains('compact');
            
            if (isCurrentlyCompact) {
                // Disable compact mode
                document.body.classList.remove('compact');
                toggle.classList.remove('active');
                console.log('📏 Compact mode disabled');
                
                // Remove density parameter from URL
                const url = new URL(window.location);
                url.searchParams.delete('density');
                window.history.replaceState({}, '', url);
            } else {
                // Enable compact mode
                document.body.classList.add('compact');
                toggle.classList.add('active');
                console.log('📏 Compact mode enabled');
                
                // Add density=compact parameter to URL (preserving other params like tv)
                const url = new URL(window.location);
                url.searchParams.set('density', 'compact');
                window.history.replaceState({}, '', url);
            }
            
            // Update wallboard button state
            this.updateWallboardButtonState();
        });
    }

    updateWallboardButtonState() {
        const button = document.getElementById('wallboardPreset');
        if (!button) return;

        const isTVMode = document.body.classList.contains('tv');
        const isCompactMode = document.body.classList.contains('compact');
        const isBothEnabled = isTVMode && isCompactMode;

        // Update button active state based on whether both modes are enabled
        if (isBothEnabled) {
            button.classList.add('active');
        } else {
            button.classList.remove('active');
        }
    }

    setupWallboardPreset() {
        const button = document.getElementById('wallboardPreset');
        if (!button) return;

        // Set initial button state
        this.updateWallboardButtonState();

        // Add click handler
        button.addEventListener('click', () => {
            const isCurrentlyTVMode = document.body.classList.contains('tv');
            const isCurrentlyCompactMode = document.body.classList.contains('compact');
            const isBothEnabled = isCurrentlyTVMode && isCurrentlyCompactMode;
            
            if (isBothEnabled) {
                // Disable wallboard mode (turn off both TV and Compact)
                document.body.classList.remove('tv');
                document.body.classList.remove('compact');
                
                // Also update individual toggle buttons
                const tvToggle = document.getElementById('tvToggle');
                const densityToggle = document.getElementById('densityToggle');
                if (tvToggle) tvToggle.classList.remove('active');
                if (densityToggle) densityToggle.classList.remove('active');
                
                console.log('🖥️ Wallboard mode disabled');
                
                // Remove both parameters from URL
                const url = new URL(window.location);
                url.searchParams.delete('tv');
                url.searchParams.delete('density');
                window.history.replaceState({}, '', url);
            } else {
                // Enable wallboard mode (turn on both TV and Compact)
                document.body.classList.add('tv');
                document.body.classList.add('compact');
                
                // Also update individual toggle buttons
                const tvToggle = document.getElementById('tvToggle');
                const densityToggle = document.getElementById('densityToggle');
                if (tvToggle) tvToggle.classList.add('active');
                if (densityToggle) densityToggle.classList.add('active');
                
                console.log('🖥️ Wallboard mode enabled');
                
                // Add both parameters to URL
                const url = new URL(window.location);
                url.searchParams.set('tv', '1');
                url.searchParams.set('density', 'compact');
                window.history.replaceState({}, '', url);
            }
            
            // Update wallboard button state
            this.updateWallboardButtonState();
        });
    }

    async checkHealth() {
        try {
            const data = await checkBackendHealth(this.apiBase, this.fetchTimeout);
            updateStatusIndicator(true, this.cachedData);
            console.log('✅ Backend health check passed', data);
        } catch (error) {
            console.error('❌ Backend health check failed', error);
            updateStatusIndicator(false, this.cachedData);
        }
    }

    async loadAllData() {
        console.log('📊 Loading dashboard data...');
        // Load endpoints concurrently using Promise.allSettled
        // This fetches in parallel while handling individual failures gracefully
        const [summaryResult, reposResult, pipelinesResult, servicesResult] = await Promise.allSettled([
            this.loadSummary(),
            this.loadRepositories(),
            this.loadPipelines(),
            this.loadServices()
        ]);
        
        // Extract success status from each result
        const summarySuccess = summaryResult.status === 'fulfilled' && summaryResult.value === true;
        const reposSuccess = reposResult.status === 'fulfilled' && reposResult.value === true;
        const pipelinesSuccess = pipelinesResult.status === 'fulfilled' && pipelinesResult.value === true;
        const servicesSuccess = servicesResult.status === 'fulfilled' && servicesResult.value === true;
        
        const anySuccess = summarySuccess || reposSuccess || pipelinesSuccess || servicesSuccess;
        const anyFailure = !summarySuccess || !reposSuccess || !pipelinesSuccess || !servicesSuccess;
        
        // Update timestamp and status based on results
        if (anySuccess && !anyFailure) {
            // All endpoints succeeded - show fresh data
            updateLastUpdated();
        } else if (anySuccess && anyFailure) {
            // Partial success - show warning about mixed data
            updateLastUpdated();
            showPartialStaleWarning();
        } else if (!anySuccess) {
            // All endpoints failed - show stale data warning even if health check passed
            showAllStaleWarning(this.cachedData);
        }
    }

    async loadSummary() {
        try {
            const data = await fetchSummary(this.apiBase, this.fetchTimeout);
            this.cachedData.summary = data;
            this.updateSummaryKPIs(data);
            console.log('✅ Summary data loaded', data);
            return true;
        } catch (error) {
            console.error('❌ Error loading summary:', error);
            // Try to use cached data
            if (this.cachedData.summary) {
                console.log('📦 Using cached summary data');
                this.updateSummaryKPIs(this.cachedData.summary);
            } else {
                showError('Failed to load summary data');
            }
            return false;
        }
    }

    updateSummaryKPIs(data) {
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

    async loadRepositories() {
        try {
            const data = await fetchRepos(this.apiBase, this.fetchTimeout);
            this.cachedData.repos = data.repositories;
            this.renderRepositories(data.repositories || []);
            console.log(`✅ Loaded ${data.repositories?.length || 0} repositories`);
            return true;
        } catch (error) {
            console.error('❌ Error loading repositories:', error);
            // Try to use cached data
            if (this.cachedData.repos) {
                console.log('📦 Using cached repositories data');
                this.renderRepositories(this.cachedData.repos);
            } else {
                showError('Failed to load repositories', 'repoGrid');
            }
            return false;
        }
    }

    renderRepositories(repos) {
        const container = document.getElementById('repoGrid');
        if (!container) return;

        if (repos.length === 0) {
            container.innerHTML = '<div class="loading">No repositories found</div>';
            return;
        }

        // Grab previous state for change detection
        const prevState = this.repoState;
        const nextState = new Map();

        // Sort repositories by: (1) default-branch consecutive failures, (2) recent all-branch success rate,
        // (3) last pipeline status, (4) name alphabetically
        const sortedRepos = [...repos].sort((a, b) => {
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

        // Generate cards with attention classes based on state changes
        const cardsHtml = sortedRepos.map((repo, currentIndex) => {
            const key = this.getRepoKey(repo);
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

            return this.createRepoCard(repo, attentionClass);
        }).join('');

        container.innerHTML = cardsHtml;

        // Update instance state for subsequent refreshes
        this.repoState = nextState;
    }

    createRepoCard(repo, extraClasses = '') {
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

    async loadPipelines() {
        try {
            const data = await fetchPipelines(this.apiBase, this.fetchTimeout);
            this.cachedData.pipelines = data.pipelines;
            this.renderPipelines(data.pipelines || []);
            console.log(`✅ Loaded ${data.pipelines?.length || 0} pipelines`);
            return true;
        } catch (error) {
            console.error('❌ Error loading pipelines:', error);
            // Try to use cached data
            if (this.cachedData.pipelines) {
                console.log('📦 Using cached pipelines data');
                this.renderPipelines(this.cachedData.pipelines);
            } else {
                showError('Failed to load pipelines', 'pipelineTableBody');
            }
            return false;
        }
    }

    renderPipelines(pipelines) {
        const tbody = document.getElementById('pipelineTableBody');
        if (!tbody) return;

        if (pipelines.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="loading">No pipelines found</td></tr>';
            return;
        }

        tbody.innerHTML = pipelines.map(pipeline => this.createPipelineRow(pipeline)).join('');
    }

    createPipelineRow(pipeline) {
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

    async loadServices() {
        try {
            const data = await fetchServices(this.apiBase, this.fetchTimeout);
            this.cachedData.services = data.services;
            this.renderServices(data.services || []);
            console.log(`✅ Loaded ${data.services?.length || 0} services`);
            return true;
        } catch (error) {
            console.error('❌ Error loading services:', error);
            // Try to use cached data
            if (this.cachedData.services) {
                console.log('📦 Using cached services data');
                this.renderServices(this.cachedData.services);
            } else {
                showError('Failed to load services', 'servicesGrid');
            }
            return false;
        }
    }

    renderServices(services) {
        const container = document.getElementById('servicesGrid');
        if (!container) return;

        if (services.length === 0) {
            container.innerHTML = '<div class="services-empty">No services configured</div>';
            return;
        }

        container.innerHTML = services.map(service => this.createServiceCard(service)).join('');
    }

    createServiceCard(service) {
        const name = service.name || service.id || service.url || 'Unknown Service';
        const status = normalizeServiceStatus(service.status);
        const statusClass = `service-status-${status.toLowerCase()}`;
        
        // Latency display
        const latency = service.latency_ms != null 
            ? `${Math.round(service.latency_ms)}ms`
            : '--';
        
        // Last checked display
        const lastChecked = service.last_checked 
            ? formatDate(service.last_checked)
            : '--';
        
        // HTTP status display (optional)
        const httpStatus = service.http_status 
            ? `HTTP ${service.http_status}`
            : '';
        
        // Error message (optional)
        const errorHtml = service.error 
            ? `<div class="service-error">${escapeHtml(service.error)}</div>`
            : '';
        
        // Optional link to open service URL
        const linkHtml = service.url 
            ? `<a href="${escapeHtml(service.url)}" target="_blank" rel="noopener noreferrer" class="service-link" title="Open ${escapeHtml(name)}">Open →</a>`
            : '';

        return `
            <div class="service-card ${statusClass}">
                <div class="service-header">
                    <h3 class="service-name">${escapeHtml(name)}</h3>
                    <span class="service-status-chip ${status.toLowerCase()}">
                        <span class="status-dot"></span>
                        <span>${escapeHtml(status)}</span>
                    </span>
                </div>
                <div class="service-metrics">
                    <div class="service-metric">
                        <span class="metric-label">Latency</span>
                        <span class="metric-value">${latency}</span>
                    </div>
                    <div class="service-metric">
                        <span class="metric-label">Last Check</span>
                        <span class="metric-value">${lastChecked}</span>
                    </div>
                    ${httpStatus ? `
                    <div class="service-metric">
                        <span class="metric-label">Status</span>
                        <span class="metric-value">${httpStatus}</span>
                    </div>
                    ` : ''}
                </div>
                ${errorHtml}
                ${linkHtml}
            </div>
        `;
    }

    startAutoRefresh() {
        console.log(`⏱️ Auto-refresh enabled (every ${this.refreshInterval / 1000}s)`);
        
        // Clear existing timer if any
        if (this.updateTimer) {
            clearInterval(this.updateTimer);
        }

        // Set up new timer
        this.updateTimer = setInterval(() => {
            console.log('🔄 Auto-refreshing data...');
            this.checkHealth();  // Re-check health status
            this.loadAllData();
        }, this.refreshInterval);
    }
}

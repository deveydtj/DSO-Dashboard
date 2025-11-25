// GitLab Dashboard Frontend Application
// Pure JavaScript - no external dependencies

/**
 * Fetch with timeout support using AbortController
 * @param {string} url - The URL to fetch
 * @param {number} timeoutMs - Timeout in milliseconds (default: 8000ms)
 * @returns {Promise<Response>} - Fetch response
 * @throws {Error} - Throws on timeout or fetch errors
 */
async function fetchWithTimeout(url, timeoutMs = 8000) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
    
    try {
        const response = await fetch(url, { signal: controller.signal });
        clearTimeout(timeoutId);
        return response;
    } catch (error) {
        clearTimeout(timeoutId);
        // AbortController throws an AbortError when signal is aborted
        if (error.name === 'AbortError') {
            throw new Error(`Request timeout after ${timeoutMs}ms`);
        }
        throw error;
    }
}

class DashboardApp {
    constructor() {
        this.apiBase = window.location.origin;
        this.refreshInterval = 60000; // 60 seconds
        this.fetchTimeout = 8000; // 8 seconds timeout for API requests
        this.updateTimer = null;
        this.cachedData = {
            summary: null,
            repos: null,
            pipelines: null
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
            const response = await fetchWithTimeout(`${this.apiBase}/api/health`, this.fetchTimeout);
            
            // Check if response is successful (status 200-299)
            if (!response.ok) {
                console.error(`❌ Backend health check failed: HTTP ${response.status}`);
                this.updateStatusIndicator(false);
                return;
            }
            
            const data = await response.json();
            this.updateStatusIndicator(true);
            console.log('✅ Backend health check passed', data);
        } catch (error) {
            console.error('❌ Backend health check failed', error);
            this.updateStatusIndicator(false);
        }
    }

    updateStatusIndicator(isOnline) {
        const indicator = document.getElementById('statusIndicator');
        const lastUpdated = document.getElementById('lastUpdated');
        if (indicator) {
            indicator.className = `status-indicator ${isOnline ? 'online' : 'offline'}`;
        }
        // Show stale data notice when offline
        if (!isOnline && lastUpdated) {
            const hasCache = this.cachedData.summary || this.cachedData.repos || this.cachedData.pipelines;
            if (hasCache) {
                lastUpdated.textContent = '⚠️ Showing cached data (backend offline)';
            }
        } else if (isOnline && lastUpdated) {
            // Clear any partial stale warning when back online
            // (will be updated by loadAllData if needed)
        }
    }

    async loadAllData() {
        console.log('📊 Loading dashboard data...');
        // Load endpoints concurrently using Promise.allSettled
        // This fetches in parallel while handling individual failures gracefully
        const [summaryResult, reposResult, pipelinesResult] = await Promise.allSettled([
            this.loadSummary(),
            this.loadRepositories(),
            this.loadPipelines()
        ]);
        
        // Extract success status from each result
        const summarySuccess = summaryResult.status === 'fulfilled' && summaryResult.value === true;
        const reposSuccess = reposResult.status === 'fulfilled' && reposResult.value === true;
        const pipelinesSuccess = pipelinesResult.status === 'fulfilled' && pipelinesResult.value === true;
        
        const anySuccess = summarySuccess || reposSuccess || pipelinesSuccess;
        const anyFailure = !summarySuccess || !reposSuccess || !pipelinesSuccess;
        
        // Update timestamp and status based on results
        if (anySuccess && !anyFailure) {
            // All endpoints succeeded - show fresh data
            this.updateLastUpdated();
        } else if (anySuccess && anyFailure) {
            // Partial success - show warning about mixed data
            this.updateLastUpdated();
            this.showPartialStaleWarning();
        } else if (!anySuccess) {
            // All endpoints failed - show stale data warning even if health check passed
            this.showAllStaleWarning();
        }
    }

    async loadSummary() {
        try {
            const response = await fetchWithTimeout(`${this.apiBase}/api/summary`, this.fetchTimeout);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
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
                this.showError('Failed to load summary data');
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
        this.updateMockBadge(data.is_mock);
    }

    updateMockBadge(isMock) {
        const badge = document.getElementById('mockBadge');
        if (badge) {
            if (isMock === true) {
                badge.style.display = 'inline-flex';
            } else {
                badge.style.display = 'none';
            }
        }
    }

    async loadRepositories() {
        try {
            const response = await fetchWithTimeout(`${this.apiBase}/api/repos`, this.fetchTimeout);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
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
                this.showError('Failed to load repositories', 'repoGrid');
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
            const normalizedStatusA = this.normalizeStatus(a.last_pipeline_status);
            const normalizedStatusB = this.normalizeStatus(b.last_pipeline_status);
            
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
            const normalizedStatus = this.normalizeStatus(repo.last_pipeline_status);
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
        const normalizedStatus = this.normalizeStatus(pipelineStatus);
        const statusClass = pipelineStatus ? `status-${normalizedStatus}` : 'status-none';
        
        // Pipeline info section
        let pipelineInfo = '';
        if (pipelineStatus) {
            const ref = repo.last_pipeline_ref || 'unknown';
            const duration = repo.last_pipeline_duration != null 
                ? this.formatDuration(repo.last_pipeline_duration) 
                : '--';
            const updatedAt = repo.last_pipeline_updated_at 
                ? this.formatDate(repo.last_pipeline_updated_at) 
                : 'unknown';
            
            pipelineInfo = `
                <div class="repo-pipeline">
                    <div class="pipeline-status-chip ${normalizedStatus}" title="Status: ${this.escapeHtml(pipelineStatus)}">
                        <span class="status-dot"></span>
                        <span>${this.escapeHtml(pipelineStatus)}</span>
                    </div>
                    <div class="pipeline-details">
                        <span class="pipeline-ref">${this.escapeHtml(ref)}</span>
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
                        <h3 class="repo-name">${this.escapeHtml(repo.name)}</h3>
                    </div>
                    <span class="repo-visibility">${this.escapeHtml(repo.visibility)}</span>
                </div>
                <p class="repo-description">${this.escapeHtml(description)}</p>
                ${pipelineInfo}
                ${successRateSection}
                ${repo.web_url ? `<a href="${repo.web_url}" target="_blank" rel="noopener noreferrer" class="repo-link">View on GitLab →</a>` : ''}
            </div>
        `;
    }

    async loadPipelines() {
        try {
            const response = await fetchWithTimeout(`${this.apiBase}/api/pipelines`, this.fetchTimeout);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
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
                this.showError('Failed to load pipelines', 'pipelineTableBody');
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
        const normalizedStatus = this.normalizeStatus(status);
        const duration = pipeline.duration != null
            ? this.formatDuration(pipeline.duration) 
            : '--';
        const createdAt = pipeline.created_at 
            ? this.formatDate(pipeline.created_at) 
            : '--';
        const fullTimestamp = pipeline.created_at || '';

        return `
            <tr class="row-status-${normalizedStatus}">
                <td>
                    <span class="pipeline-status ${normalizedStatus}" title="Raw status: ${this.escapeHtml(status)}">${this.escapeHtml(status)}</span>
                </td>
                <td>${this.escapeHtml(pipeline.project_name)}</td>
                <td>${this.escapeHtml(pipeline.ref || '--')}</td>
                <td>
                    <span class="commit-sha">${this.escapeHtml(pipeline.sha || '--')}</span>
                </td>
                <td>${duration}</td>
                <td title="${this.escapeHtml(fullTimestamp)}">${createdAt}</td>
                <td>
                    ${pipeline.web_url 
                        ? `<a href="${pipeline.web_url}" target="_blank" rel="noopener noreferrer" class="pipeline-link">View →</a>` 
                        : '--'}
                </td>
            </tr>
        `;
    }

    updateLastUpdated() {
        const element = document.getElementById('lastUpdated');
        if (element) {
            const now = new Date();
            element.textContent = `Last updated: ${now.toLocaleTimeString()}`;
        }
    }

    showPartialStaleWarning() {
        const element = document.getElementById('lastUpdated');
        if (element) {
            const now = new Date();
            element.textContent = `⚠️ Partially stale (updated: ${now.toLocaleTimeString()})`;
        }
    }

    showAllStaleWarning() {
        const element = document.getElementById('lastUpdated');
        const indicator = document.getElementById('statusIndicator');
        if (element) {
            const hasCache = this.cachedData.summary || this.cachedData.repos || this.cachedData.pipelines;
            if (hasCache) {
                element.textContent = '⚠️ All data stale (using cache)';
            } else {
                element.textContent = '❌ Failed to load data';
            }
        }
        // Update indicator to offline when all endpoints fail
        if (indicator) {
            indicator.className = 'status-indicator offline';
        }
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

    showError(message, containerId = null) {
        const errorHtml = `<div class="error">⚠️ ${message}</div>`;
        
        if (containerId) {
            const container = document.getElementById(containerId);
            if (container) {
                container.innerHTML = errorHtml;
            }
        } else {
            console.error(message);
        }
    }

    formatDate(dateString) {
        try {
            const date = new Date(dateString);
            const now = new Date();
            const diffMs = now - date;
            const diffMins = Math.floor(diffMs / 60000);
            const diffHours = Math.floor(diffMs / 3600000);
            const diffDays = Math.floor(diffMs / 86400000);

            if (diffMins < 1) return 'Just now';
            if (diffMins < 60) return `${diffMins}m ago`;
            if (diffHours < 24) return `${diffHours}h ago`;
            if (diffDays < 7) return `${diffDays}d ago`;
            
            return date.toLocaleDateString();
        } catch (error) {
            return dateString;
        }
    }

    formatDuration(seconds) {
        if (seconds == null || seconds < 0) return '--';
        
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        
        if (mins === 0) return `${secs}s`;
        return `${mins}m ${secs}s`;
    }

    escapeHtml(text) {
        if (!text) return '';
        
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return String(text).replace(/[&<>"']/g, char => map[char]);
    }

    normalizeStatus(rawStatus) {
        // Normalize GitLab pipeline status to a safe whitelist for CSS classes
        // Handles null/undefined/empty, case differences, and underscores
        
        if (!rawStatus) return 'other';
        
        // Normalize: lowercase and replace underscores/dashes with spaces for matching
        const normalized = String(rawStatus).toLowerCase().replace(/[_-]/g, ' ').trim();
        
        // Map GitLab statuses to our whitelist
        const statusMap = {
            // Success states
            'success': 'success',
            'passed': 'success',
            
            // Failed states
            'failed': 'failed',
            'failure': 'failed',
            
            // Running states
            'running': 'running',
            'in progress': 'running',
            
            // Pending/waiting states
            'pending': 'pending',
            'created': 'pending',
            'scheduled': 'pending',
            'preparing': 'pending',
            'waiting for resource': 'pending',
            'waiting for callback': 'pending',
            
            // Canceled states
            'canceled': 'canceled',
            'cancelled': 'canceled',
            
            // Skipped states
            'skipped': 'skipped',
            
            // Manual intervention needed
            'manual': 'manual'
        };
        
        // Return mapped status or 'other' for unknown statuses
        return statusMap[normalized] || 'other';
    }
}

// Sanity check function to verify escapeHtml is properly applied
function verifySanitization() {
    // Create a temporary instance to test escapeHtml
    const testApp = { 
        escapeHtml: DashboardApp.prototype.escapeHtml 
    };
    
    // Test cases for XSS prevention
    const tests = [
        { input: '<script>alert("xss")</script>', expected: '&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;' },
        { input: '<img src=x onerror=alert(1)>', expected: '&lt;img src=x onerror=alert(1)&gt;' },
        { input: 'normal text', expected: 'normal text' },
        { input: "It's a test & more", expected: 'It&#039;s a test &amp; more' }
    ];
    
    let passed = 0;
    let failed = 0;
    
    tests.forEach((test, index) => {
        const result = testApp.escapeHtml(test.input);
        if (result === test.expected) {
            passed++;
        } else {
            failed++;
            console.error(`❌ Test ${index + 1} failed:`, { input: test.input, expected: test.expected, got: result });
        }
    });
    
    console.log(`✅ Sanitization check: ${passed}/${tests.length} tests passed`);
    
    if (failed > 0) {
        console.error(`⚠️ WARNING: ${failed} sanitization tests failed!`);
        return false;
    }
    
    return true;
}

// Initialize the dashboard when DOM is ready
function initializeDashboard() {
    verifySanitization(); // Run sanity check on startup
    window.dashboardApp = new DashboardApp();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeDashboard);
} else {
    initializeDashboard();
}

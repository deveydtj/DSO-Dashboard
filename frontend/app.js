// GitLab Dashboard Frontend Application
// Pure JavaScript - no external dependencies

class DashboardApp {
    constructor() {
        this.apiBase = window.location.origin;
        this.refreshInterval = 60000; // 60 seconds
        this.updateTimer = null;
        this.cachedData = {
            summary: null,
            repos: null,
            pipelines: null
        };
        this.init();
    }

    init() {
        console.log('🚀 Initializing GitLab DSO Dashboard...');
        this.checkTVMode();
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

    async checkHealth() {
        try {
            const response = await fetch(`${this.apiBase}/api/health`);
            
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
                lastUpdated.innerHTML = '⚠️ Showing cached data (backend offline)';
            }
        } else if (isOnline && lastUpdated) {
            // Clear any partial stale warning when back online
            // (will be updated by loadAllData if needed)
        }
    }

    async loadAllData() {
        console.log('📊 Loading dashboard data...');
        // Load each endpoint independently instead of Promise.all
        // This ensures that if one fails, others can still succeed
        const summarySuccess = await this.loadSummary();
        const reposSuccess = await this.loadRepositories();
        const pipelinesSuccess = await this.loadPipelines();
        
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
        }
        // If all failed (no success), keep the cached-data warning from updateStatusIndicator
    }

    async loadSummary() {
        try {
            const response = await fetch(`${this.apiBase}/api/summary`);
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
    }

    async loadRepositories() {
        try {
            const response = await fetch(`${this.apiBase}/api/repos`);
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

        // Sort repositories: failing repos first
        const sortedRepos = [...repos].sort((a, b) => {
            // First priority: consecutive_default_branch_failures DESC
            const failuresA = a.consecutive_default_branch_failures || 0;
            const failuresB = b.consecutive_default_branch_failures || 0;
            if (failuresB !== failuresA) {
                return failuresB - failuresA;
            }

            // Second priority: failed/running pipelines first
            const statusPriorityMap = {
                'failed': 0,
                'running': 1,
                'pending': 2,
                'success': 3,
                'canceled': 4,
                'cancelled': 4,
                'skipped': 5,
                null: 6,
                undefined: 6
            };
            const priorityA = statusPriorityMap[a.last_pipeline_status] ?? 6;
            const priorityB = statusPriorityMap[b.last_pipeline_status] ?? 6;
            if (priorityA !== priorityB) {
                return priorityA - priorityB;
            }

            // Third priority: alphabetical by name
            const nameA = (a.name || '').toLowerCase();
            const nameB = (b.name || '').toLowerCase();
            return nameA.localeCompare(nameB);
        });

        container.innerHTML = sortedRepos.map(repo => this.createRepoCard(repo)).join('');
    }

    createRepoCard(repo) {
        const description = repo.description || 'No description available';
        const pipelineStatus = repo.last_pipeline_status || null;
        const statusClass = pipelineStatus ? `status-${pipelineStatus}` : 'status-none';
        
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
                    <div class="pipeline-status-chip ${this.escapeHtml(pipelineStatus)}">
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
                <div class="repo-success-rate">
                    <div class="success-rate-label">
                        <span>Success Rate</span>
                        <span class="success-rate-value">${successPercent}%</span>
                    </div>
                    <div class="success-rate-bar">
                        <div class="success-rate-fill" style="width: ${successPercent}%"></div>
                    </div>
                </div>
            `;
        }

        return `
            <div class="repo-card ${statusClass}">
                <div class="repo-header">
                    <div>
                        <h3 class="repo-name">${this.escapeHtml(repo.name)}</h3>
                    </div>
                    <span class="repo-visibility">${repo.visibility}</span>
                </div>
                <p class="repo-description">${this.escapeHtml(description)}</p>
                ${pipelineInfo}
                ${successRateSection}
                <div class="repo-stats">
                    <div class="repo-stat">
                        <span>⭐</span>
                        <span>${repo.star_count || 0}</span>
                    </div>
                    <div class="repo-stat">
                        <span>🔱</span>
                        <span>${repo.forks_count || 0}</span>
                    </div>
                    <div class="repo-stat">
                        <span>🐛</span>
                        <span>${repo.open_issues_count || 0}</span>
                    </div>
                </div>
                ${repo.web_url ? `<a href="${repo.web_url}" target="_blank" class="repo-link">View on GitLab →</a>` : ''}
            </div>
        `;
    }

    async loadPipelines() {
        try {
            const response = await fetch(`${this.apiBase}/api/pipelines`);
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
        const duration = pipeline.duration != null
            ? this.formatDuration(pipeline.duration) 
            : '--';
        const createdAt = pipeline.created_at 
            ? this.formatDate(pipeline.created_at) 
            : '--';
        const fullTimestamp = pipeline.created_at || '';

        return `
            <tr class="row-status-${status}">
                <td>
                    <span class="pipeline-status ${status}">${status}</span>
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
                        ? `<a href="${pipeline.web_url}" target="_blank" class="pipeline-link">View →</a>` 
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
            element.innerHTML = `⚠️ Partially stale (updated: ${now.toLocaleTimeString()})`;
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
}

// Initialize the dashboard when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.dashboardApp = new DashboardApp();
    });
} else {
    window.dashboardApp = new DashboardApp();
}

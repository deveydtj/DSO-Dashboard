// GitLab Dashboard Frontend Application
// Pure JavaScript - no external dependencies

class DashboardApp {
    constructor() {
        this.apiBase = window.location.origin;
        this.refreshInterval = 60000; // 60 seconds
        this.updateTimer = null;
        this.init();
    }

    init() {
        console.log('🚀 Initializing GitLab DSO Dashboard...');
        this.checkHealth();
        this.loadAllData();
        this.startAutoRefresh();
    }

    async checkHealth() {
        try {
            const response = await fetch(`${this.apiBase}/api/health`);
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
        if (indicator) {
            indicator.className = `status-indicator ${isOnline ? 'online' : 'offline'}`;
        }
    }

    async loadAllData() {
        console.log('📊 Loading dashboard data...');
        await Promise.all([
            this.loadSummary(),
            this.loadRepositories(),
            this.loadPipelines()
        ]);
        this.updateLastUpdated();
    }

    async loadSummary() {
        try {
            const response = await fetch(`${this.apiBase}/api/summary`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            this.updateSummaryKPIs(data);
            console.log('✅ Summary data loaded', data);
        } catch (error) {
            console.error('❌ Error loading summary:', error);
            this.showError('Failed to load summary data');
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
            this.renderRepositories(data.repositories || []);
            console.log(`✅ Loaded ${data.repositories?.length || 0} repositories`);
        } catch (error) {
            console.error('❌ Error loading repositories:', error);
            this.showError('Failed to load repositories', 'repoGrid');
        }
    }

    renderRepositories(repos) {
        const container = document.getElementById('repoGrid');
        if (!container) return;

        if (repos.length === 0) {
            container.innerHTML = '<div class="loading">No repositories found</div>';
            return;
        }

        container.innerHTML = repos.map(repo => this.createRepoCard(repo)).join('');
    }

    createRepoCard(repo) {
        const description = repo.description || 'No description available';
        const lastActivity = repo.last_activity_at 
            ? this.formatDate(repo.last_activity_at) 
            : 'Unknown';

        return `
            <div class="repo-card">
                <div class="repo-header">
                    <div>
                        <h3 class="repo-name">${this.escapeHtml(repo.name)}</h3>
                    </div>
                    <span class="repo-visibility">${repo.visibility}</span>
                </div>
                <p class="repo-description">${this.escapeHtml(description)}</p>
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
            this.renderPipelines(data.pipelines || []);
            console.log(`✅ Loaded ${data.pipelines?.length || 0} pipelines`);
        } catch (error) {
            console.error('❌ Error loading pipelines:', error);
            this.showError('Failed to load pipelines', 'pipelineTableBody');
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
        const duration = pipeline.duration 
            ? this.formatDuration(pipeline.duration) 
            : '--';
        const createdAt = pipeline.created_at 
            ? this.formatDate(pipeline.created_at) 
            : '--';

        return `
            <tr>
                <td>
                    <span class="pipeline-status ${status}">${status}</span>
                </td>
                <td>${this.escapeHtml(pipeline.project_name)}</td>
                <td>${this.escapeHtml(pipeline.ref || '--')}</td>
                <td>
                    <span class="commit-sha">${this.escapeHtml(pipeline.sha || '--')}</span>
                </td>
                <td>${duration}</td>
                <td>${createdAt}</td>
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

    startAutoRefresh() {
        console.log(`⏱️ Auto-refresh enabled (every ${this.refreshInterval / 1000}s)`);
        
        // Clear existing timer if any
        if (this.updateTimer) {
            clearInterval(this.updateTimer);
        }

        // Set up new timer
        this.updateTimer = setInterval(() => {
            console.log('🔄 Auto-refreshing data...');
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
        if (!seconds || seconds < 0) return '--';
        
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        
        if (mins === 0) return `${secs}s`;
        return `${mins}m ${secs}s`;
    }

    escapeHtml(text) {
        if (!text) return '';
        
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
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

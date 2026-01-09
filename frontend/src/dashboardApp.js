// GitLab Dashboard Frontend Application
// Pure JavaScript - no external dependencies
// ES Module - DashboardApp class

// Import utility modules
import {
    showError,
    updateStatusIndicator,
    updateLastUpdated,
    showPartialStaleWarning,
    showAllStaleWarning
} from './utils/dom.js';
import {
    fetchSummary,
    fetchRepos,
    fetchPipelines,
    fetchServices,
    checkBackendHealth
} from './api/apiClient.js';

// Import view modules
import { initHeaderToggles } from './views/headerView.js';
import { renderSummaryKpis } from './views/kpiView.js';
import { renderRepositories, getRepoKey, attachRepoCardHandlers } from './views/repoView.js';
import { renderPipelines } from './views/pipelineView.js';
import { renderServices } from './views/serviceView.js';
import { renderAttentionStrip } from './views/attentionView.js';
import { openJobPerformanceModal } from './views/jobPerformanceView.js';

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
        // History buffers for trend sparklines
        this.repoHistory = new Map();     // key → array of recent success rates
        this.serviceHistory = new Map();  // key → array of recent latencies
        this.historyWindow = 20;          // number of points to retain per item
        this.init();
    }

    init() {
        console.log('🚀 Initializing DSO Dashboard...');
        // Initialize header toggles (TV, Compact, Wallboard)
        initHeaderToggles();
        this.checkHealth();
        this.loadAllData();
        this.startAutoRefresh();
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

        // Render attention strip after all other sections have been rendered
        renderAttentionStrip({
            summary: this.cachedData.summary,
            repos: this.cachedData.repos || [],
            pipelines: this.cachedData.pipelines || [],
            services: this.cachedData.services || []
        });
    }

    async loadSummary() {
        try {
            const data = await fetchSummary(this.apiBase, this.fetchTimeout);
            this.cachedData.summary = data;
            // Use view module to render KPIs
            renderSummaryKpis(data);
            console.log('✅ Summary data loaded', data);
            return true;
        } catch (error) {
            console.error('❌ Error loading summary:', error);
            // Try to use cached data
            if (this.cachedData.summary) {
                console.log('📦 Using cached summary data');
                renderSummaryKpis(this.cachedData.summary);
            } else {
                showError('Failed to load summary data');
            }
            return false;
        }
    }

    async loadRepositories() {
        try {
            const data = await fetchRepos(this.apiBase, this.fetchTimeout);
            this.cachedData.repos = data.repositories;
            // Update history buffers for trend sparklines
            this._updateRepoHistory(data.repositories || []);
            // Render repos and track state for attention animations (status degradation, position changes)
            this.repoState = renderRepositories(data.repositories || [], this.repoState);
            // Attach event handlers for job performance buttons
            attachRepoCardHandlers(this.apiBase, openJobPerformanceModal);
            console.log(`✅ Loaded ${data.repositories?.length || 0} repositories`);
            return true;
        } catch (error) {
            console.error('❌ Error loading repositories:', error);
            // Try to use cached data
            if (this.cachedData.repos) {
                console.log('📦 Using cached repositories data');
                this.repoState = renderRepositories(this.cachedData.repos, this.repoState);
                // Attach event handlers for cached data too
                attachRepoCardHandlers(this.apiBase, openJobPerformanceModal);
            } else {
                showError('Failed to load repositories', 'repoGrid');
            }
            return false;
        }
    }

    async loadPipelines() {
        try {
            const data = await fetchPipelines(this.apiBase, this.fetchTimeout);
            this.cachedData.pipelines = data.pipelines;
            // Use view module to render pipelines
            renderPipelines(data.pipelines || []);
            console.log(`✅ Loaded ${data.pipelines?.length || 0} pipelines`);
            return true;
        } catch (error) {
            console.error('❌ Error loading pipelines:', error);
            // Try to use cached data
            if (this.cachedData.pipelines) {
                console.log('📦 Using cached pipelines data');
                renderPipelines(this.cachedData.pipelines);
            } else {
                showError('Failed to load pipelines', 'pipelineTableBody');
            }
            return false;
        }
    }

    async loadServices() {
        try {
            const data = await fetchServices(this.apiBase, this.fetchTimeout);
            this.cachedData.services = data.services;
            // Update history buffers for trend sparklines
            this._updateServiceHistory(data.services || []);
            // Use view module to render services
            renderServices(data.services || [], this.serviceHistory);
            console.log(`✅ Loaded ${data.services?.length || 0} services`);
            return true;
        } catch (error) {
            console.error('❌ Error loading services:', error);
            // Try to use cached data
            if (this.cachedData.services) {
                console.log('📦 Using cached services data');
                renderServices(this.cachedData.services, this.serviceHistory);
            } else {
                showError('Failed to load services', 'servicesGrid');
            }
            return false;
        }
    }

    /**
     * Get a stable unique key for a repository
     * Delegates to getRepoKey from repoView.js for consistency
     * @param {Object} repo - Repository object
     * @returns {string} - Stable key for the repository
     */
    _getRepoKey(repo) {
        return getRepoKey(repo);
    }

    /**
     * Update repository history buffers with latest success rates
     * @param {Array} repos - Array of repository objects
     */
    _updateRepoHistory(repos) {
        for (const repo of repos) {
            const key = this._getRepoKey(repo);
            const successRate = repo.recent_success_rate;

            // Skip if success rate is null, undefined, or not a number
            if (successRate == null || typeof successRate !== 'number' || !Number.isFinite(successRate)) {
                continue;
            }

            // Get or create history array for this repo
            if (!this.repoHistory.has(key)) {
                this.repoHistory.set(key, []);
            }
            const history = this.repoHistory.get(key);

            // Append new value
            history.push(successRate);

            // Trim to historyWindow
            if (history.length > this.historyWindow) {
                history.splice(0, history.length - this.historyWindow);
            }
        }
    }

    /**
     * Get a stable unique key for a service
     * @param {Object} service - Service object
     * @returns {string} - Stable key for the service
     */
    _getServiceKey(service) {
        // Prefer id, fallback to name, then url
        if (service.id != null) {
            return String(service.id);
        }
        if (service.name) {
            return service.name;
        }
        return service.url || 'unknown';
    }

    /**
     * Update service history buffers with latest latency values
     * Prefers server-provided latency_samples_ms when available for persistence
     * across browser refreshes. Falls back to client-side tracking otherwise.
     * @param {Array} services - Array of service objects
     */
    _updateServiceHistory(services) {
        for (const service of services) {
            const key = this._getServiceKey(service);
            
            // Prefer server-provided samples if available
            // This enables sparklines to persist across browser refreshes
            if (service.latency_samples_ms && Array.isArray(service.latency_samples_ms)) {
                // Use server-provided samples directly
                // Filter to ensure all values are valid numbers
                const validSamples = service.latency_samples_ms.filter(
                    v => typeof v === 'number' && Number.isFinite(v) && v >= 0
                );
                if (validSamples.length > 0) {
                    this.serviceHistory.set(key, validSamples);
                    continue;
                }
            }
            
            // Fallback: client-side tracking (original behavior)
            const latency = service.latency_ms;

            // Skip if latency is null, undefined, or not a number
            if (latency == null || typeof latency !== 'number' || !Number.isFinite(latency)) {
                continue;
            }

            // Get or create history array for this service
            if (!this.serviceHistory.has(key)) {
                this.serviceHistory.set(key, []);
            }
            const history = this.serviceHistory.get(key);

            // Append new value
            history.push(latency);

            // Trim to historyWindow
            if (history.length > this.historyWindow) {
                history.splice(0, history.length - this.historyWindow);
            }
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
}

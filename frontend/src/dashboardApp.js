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
import { renderRepositories } from './views/repoView.js';
import { renderPipelines } from './views/pipelineView.js';
import { renderServices } from './views/serviceView.js';

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

    init() {
        console.log('🚀 Initializing GitLab DSO Dashboard...');
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
            // Render repos and track state for attention animations (status degradation, position changes)
            this.repoState = renderRepositories(data.repositories || [], this.repoState);
            console.log(`✅ Loaded ${data.repositories?.length || 0} repositories`);
            return true;
        } catch (error) {
            console.error('❌ Error loading repositories:', error);
            // Try to use cached data
            if (this.cachedData.repos) {
                console.log('📦 Using cached repositories data');
                this.repoState = renderRepositories(this.cachedData.repos, this.repoState);
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
            // Use view module to render services
            renderServices(data.services || []);
            console.log(`✅ Loaded ${data.services?.length || 0} services`);
            return true;
        } catch (error) {
            console.error('❌ Error loading services:', error);
            // Try to use cached data
            if (this.cachedData.services) {
                console.log('📦 Using cached services data');
                renderServices(this.cachedData.services);
            } else {
                showError('Failed to load services', 'servicesGrid');
            }
            return false;
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

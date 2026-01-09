// API client for GitLab Dashboard
// Pure JavaScript - no external dependencies

/**
 * Default timeout for API requests (8 seconds)
 */
export const DEFAULT_TIMEOUT = 8000;

/**
 * Fetch with timeout support using AbortController
 * @param {string} url - The URL to fetch
 * @param {number} timeoutMs - Timeout in milliseconds (default: 8000ms)
 * @param {Object} options - Fetch options (method, headers, body, etc.)
 * @returns {Promise<Response>} - Fetch response
 * @throws {Error} - Throws on timeout or fetch errors
 */
export async function fetchWithTimeout(url, timeoutMs = DEFAULT_TIMEOUT, options = {}) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
    
    try {
        const response = await fetch(url, { 
            ...options,
            signal: controller.signal 
        });
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

/**
 * Fetch summary statistics from the API
 * @param {string} apiBase - Base URL for API (e.g., window.location.origin)
 * @param {number} [timeoutMs] - Optional timeout in milliseconds
 * @returns {Promise<Object>} - Summary data
 * @throws {Error} - Throws on network or HTTP errors
 */
export async function fetchSummary(apiBase, timeoutMs = DEFAULT_TIMEOUT) {
    const response = await fetchWithTimeout(`${apiBase}/api/summary`, timeoutMs);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
}

/**
 * Fetch repositories from the API
 * @param {string} apiBase - Base URL for API (e.g., window.location.origin)
 * @param {number} [timeoutMs] - Optional timeout in milliseconds
 * @returns {Promise<Object>} - Repository data with repositories array
 * @throws {Error} - Throws on network or HTTP errors
 */
export async function fetchRepos(apiBase, timeoutMs = DEFAULT_TIMEOUT) {
    const response = await fetchWithTimeout(`${apiBase}/api/repos`, timeoutMs);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
}

/**
 * Fetch pipelines from the API
 * @param {string} apiBase - Base URL for API (e.g., window.location.origin)
 * @param {number} [timeoutMs] - Optional timeout in milliseconds
 * @param {boolean} [dsoOnly=false] - Optional flag to filter DSO-relevant pipelines only
 * @returns {Promise<Object>} - Pipeline data with pipelines array
 * @throws {Error} - Throws on network or HTTP errors
 */
export async function fetchPipelines(apiBase, timeoutMs = DEFAULT_TIMEOUT, dsoOnly = false) {
    const url = dsoOnly 
        ? `${apiBase}/api/pipelines?dso_only=true`
        : `${apiBase}/api/pipelines?dso_only=false`;
    const response = await fetchWithTimeout(url, timeoutMs);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
}

/**
 * Fetch services from the API
 * @param {string} apiBase - Base URL for API (e.g., window.location.origin)
 * @param {number} [timeoutMs] - Optional timeout in milliseconds
 * @returns {Promise<Object>} - Services data with services array
 * @throws {Error} - Throws on network or HTTP errors
 */
export async function fetchServices(apiBase, timeoutMs = DEFAULT_TIMEOUT) {
    const response = await fetchWithTimeout(`${apiBase}/api/services`, timeoutMs);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
}

/**
 * Check backend health status
 * @param {string} apiBase - Base URL for API (e.g., window.location.origin)
 * @param {number} [timeoutMs] - Optional timeout in milliseconds
 * @returns {Promise<Object>} - Health check data
 * @throws {Error} - Throws on network or HTTP errors
 */
export async function checkBackendHealth(apiBase, timeoutMs = DEFAULT_TIMEOUT) {
    const response = await fetchWithTimeout(`${apiBase}/api/health`, timeoutMs);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
}

/**
 * Fetch job performance analytics for a specific project
 * @param {string} apiBase - Base URL for API (e.g., window.location.origin)
 * @param {number|string} projectId - GitLab project ID
 * @param {number} [timeoutMs] - Optional timeout in milliseconds
 * @returns {Promise<Object>} - Job analytics data with 7-day trend
 * @throws {Error} - Throws on network or HTTP errors
 */
export async function fetchJobAnalytics(apiBase, projectId, timeoutMs = DEFAULT_TIMEOUT) {
    const response = await fetchWithTimeout(`${apiBase}/api/job-analytics/${projectId}`, timeoutMs);
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const error = new Error(errorData.message || `HTTP ${response.status}`);
        error.status = response.status;
        error.data = errorData;
        throw error;
    }
    return response.json();
}

/**
 * Trigger a manual refresh of job analytics for a specific project
 * @param {string} apiBase - Base URL for API (e.g., window.location.origin)
 * @param {number|string} projectId - GitLab project ID
 * @param {number} [timeoutMs] - Optional timeout in milliseconds (default: 30 seconds).
 *                                This should be sufficient for most job analytics computations.
 *                                Increase if backend processing typically takes longer.
 * @returns {Promise<Object>} - Refresh result with updated analytics
 * @throws {Error} - Throws on network or HTTP errors
 */
export async function refreshJobAnalytics(apiBase, projectId, timeoutMs = 30000) {
    const response = await fetchWithTimeout(
        `${apiBase}/api/job-analytics/${projectId}/refresh`, 
        timeoutMs,
        { method: 'POST' }
    );
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const error = new Error(errorData.message || `HTTP ${response.status}`);
        error.status = response.status;
        error.data = errorData;
        throw error;
    }
    return response.json();
}

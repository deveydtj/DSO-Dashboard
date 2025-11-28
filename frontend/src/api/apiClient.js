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
 * @returns {Promise<Response>} - Fetch response
 * @throws {Error} - Throws on timeout or fetch errors
 */
export async function fetchWithTimeout(url, timeoutMs = DEFAULT_TIMEOUT) {
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
 * @returns {Promise<Object>} - Pipeline data with pipelines array
 * @throws {Error} - Throws on network or HTTP errors
 */
export async function fetchPipelines(apiBase, timeoutMs = DEFAULT_TIMEOUT) {
    const response = await fetchWithTimeout(`${apiBase}/api/pipelines`, timeoutMs);
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

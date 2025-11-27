// GitLab Dashboard Frontend - Main Entrypoint
// Pure JavaScript ES Module - no external dependencies

import { DashboardApp } from './dashboardApp.js';

/**
 * Sanity check function to verify escapeHtml is properly applied
 * @returns {boolean} - true if all tests pass, false otherwise
 */
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

/**
 * Initialize the dashboard when DOM is ready
 */
function initializeDashboard() {
    verifySanitization(); // Run sanity check on startup
    window.dashboardApp = new DashboardApp();
}

// Initialize the dashboard when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeDashboard);
} else {
    initializeDashboard();
}

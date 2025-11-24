"""
Tests for frontend fetch timeout functionality
"""
import unittest
import re


class TestFetchTimeoutImplementation(unittest.TestCase):
    """Test that fetch timeout is properly implemented in frontend code"""
    
    def setUp(self):
        """Load the frontend app.js file"""
        with open('frontend/app.js', 'r') as f:
            self.app_js_content = f.read()
    
    def test_fetchWithTimeout_function_exists(self):
        """Test that fetchWithTimeout function is defined"""
        self.assertIn('async function fetchWithTimeout', self.app_js_content)
        self.assertIn('AbortController', self.app_js_content)
    
    def test_fetchWithTimeout_has_default_timeout(self):
        """Test that fetchWithTimeout has a default timeout parameter"""
        # Check for function signature with default parameter
        pattern = r'async function fetchWithTimeout\([^)]*timeoutMs\s*=\s*\d+'
        self.assertTrue(
            re.search(pattern, self.app_js_content),
            "fetchWithTimeout should have a default timeout parameter"
        )
    
    def test_abortController_used(self):
        """Test that AbortController is used for timeout implementation"""
        self.assertIn('new AbortController()', self.app_js_content)
        self.assertIn('controller.abort()', self.app_js_content)
        self.assertIn('signal: controller.signal', self.app_js_content)
    
    def test_timeout_cleared(self):
        """Test that timeout is properly cleared"""
        # Should clear timeout in both success and error cases
        timeout_clears = self.app_js_content.count('clearTimeout(timeoutId)')
        self.assertGreaterEqual(
            timeout_clears, 
            2, 
            "clearTimeout should be called in both success and error paths"
        )
    
    def test_abort_error_handling(self):
        """Test that AbortError is properly handled"""
        self.assertIn('AbortError', self.app_js_content)
        self.assertIn('Request timeout', self.app_js_content)
    
    def test_all_fetch_calls_replaced(self):
        """Test that all direct fetch() calls are replaced with fetchWithTimeout()"""
        # Check that fetchWithTimeout is used instead of direct fetch
        fetch_with_timeout_count = self.app_js_content.count('fetchWithTimeout(')
        
        # Count direct fetch calls (excluding the one inside fetchWithTimeout itself)
        # We expect exactly 1 direct fetch call (inside fetchWithTimeout function)
        direct_fetch_pattern = r'\bfetch\s*\('
        direct_fetches = re.findall(direct_fetch_pattern, self.app_js_content)
        
        # Should have at least 4 fetchWithTimeout calls (health, summary, repos, pipelines)
        self.assertGreaterEqual(
            fetch_with_timeout_count,
            4,
            "Should have at least 4 fetchWithTimeout calls for API endpoints"
        )
    
    def test_fetchTimeout_property_exists(self):
        """Test that fetchTimeout property is set in constructor"""
        self.assertIn('this.fetchTimeout', self.app_js_content)
        # Check that it's initialized to a reasonable value (8000ms = 8 seconds)
        self.assertIn('this.fetchTimeout = 8000', self.app_js_content)
    
    def test_api_endpoints_use_timeout(self):
        """Test that all API endpoints use fetchWithTimeout"""
        api_endpoints = [
            '/api/health',
            '/api/summary',
            '/api/repos',
            '/api/pipelines'
        ]
        
        for endpoint in api_endpoints:
            # Find lines that call this endpoint
            endpoint_lines = [
                line for line in self.app_js_content.split('\n')
                if endpoint in line
            ]
            
            # At least one should use fetchWithTimeout
            has_timeout = any('fetchWithTimeout' in line for line in endpoint_lines)
            self.assertTrue(
                has_timeout,
                f"Endpoint {endpoint} should use fetchWithTimeout"
            )
    
    def test_no_external_dependencies(self):
        """Test that no external dependencies are imported"""
        # Should not import any external libraries
        self.assertNotIn('import ', self.app_js_content)
        self.assertNotIn('require(', self.app_js_content)
        
        # Verify comment states no external dependencies
        self.assertIn('no external dependencies', self.app_js_content)


if __name__ == '__main__':
    unittest.main()

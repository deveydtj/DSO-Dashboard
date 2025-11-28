"""
Tests for frontend fetch timeout functionality
"""
import unittest
import re
import os


class TestFetchTimeoutImplementation(unittest.TestCase):
    """Test that fetch timeout is properly implemented in frontend code"""
    
    def setUp(self):
        """Load frontend files (ES modules)"""
        # Compute path relative to this test file's location
        test_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(test_dir))
        
        # Load the dashboardApp.js file
        dashboard_path = os.path.join(project_root, 'frontend', 'src', 'dashboardApp.js')
        with open(dashboard_path, 'r') as f:
            self.app_js_content = f.read()
        
        # Load the apiClient.js file (where fetchWithTimeout now lives)
        api_client_path = os.path.join(project_root, 'frontend', 'src', 'api', 'apiClient.js')
        with open(api_client_path, 'r') as f:
            self.api_client_content = f.read()
        
        # Combined content for some tests
        self.all_frontend_content = self.app_js_content + self.api_client_content
    
    def test_fetchWithTimeout_function_exists(self):
        """Test that fetchWithTimeout function is defined in apiClient.js"""
        self.assertIn('async function fetchWithTimeout', self.api_client_content)
        self.assertIn('AbortController', self.api_client_content)
    
    def test_fetchWithTimeout_has_default_timeout(self):
        """Test that fetchWithTimeout has a default timeout parameter"""
        # Check for function signature with default parameter in apiClient.js
        # Matches either a numeric literal (8000) or a constant name (DEFAULT_TIMEOUT)
        pattern = r'async function fetchWithTimeout\([^)]*timeoutMs\s*=\s*\w+'
        self.assertTrue(
            re.search(pattern, self.api_client_content),
            "fetchWithTimeout should have a default timeout parameter"
        )
    
    def test_abortController_used(self):
        """Test that AbortController is used for timeout implementation"""
        self.assertIn('new AbortController()', self.api_client_content)
        self.assertIn('controller.abort()', self.api_client_content)
        self.assertIn('signal: controller.signal', self.api_client_content)
    
    def test_timeout_cleared(self):
        """Test that timeout is properly cleared"""
        # Should clear timeout in both success and error cases in apiClient.js
        timeout_clears = self.api_client_content.count('clearTimeout(timeoutId)')
        self.assertGreaterEqual(
            timeout_clears, 
            2, 
            "clearTimeout should be called in both success and error paths"
        )
    
    def test_abort_error_handling(self):
        """Test that AbortError is properly handled"""
        self.assertIn('AbortError', self.api_client_content)
        self.assertIn('Request timeout', self.api_client_content)
    
    def test_api_client_functions_exist(self):
        """Test that API client functions are defined"""
        # Check for all expected API functions
        api_functions = [
            'fetchSummary',
            'fetchRepos',
            'fetchPipelines',
            'fetchServices',
            'checkBackendHealth'
        ]
        for func_name in api_functions:
            self.assertIn(
                f'export async function {func_name}',
                self.api_client_content,
                f"{func_name} should be exported from apiClient.js"
            )
    
    def test_dashboardApp_imports_api_client(self):
        """Test that DashboardApp imports from apiClient.js"""
        # Check for import from apiClient module
        self.assertIn("from './api/apiClient.js'", self.app_js_content)
        # Check that at least one API function is imported
        self.assertTrue(
            'fetchSummary' in self.app_js_content or 
            'fetchRepos' in self.app_js_content or
            'fetchPipelines' in self.app_js_content,
            "DashboardApp should import API functions from apiClient.js"
        )
    
    def test_dashboardApp_uses_api_functions(self):
        """Test that DashboardApp uses the imported API functions"""
        # Check that the app uses API functions
        api_calls = [
            'fetchSummary(',
            'fetchRepos(',
            'fetchPipelines(',
            'fetchServices(',
            'checkBackendHealth('
        ]
        for api_call in api_calls:
            self.assertIn(
                api_call,
                self.app_js_content,
                f"DashboardApp should use {api_call.rstrip('(')}"
            )
    
    def test_no_direct_fetch_in_dashboardApp(self):
        """Test that DashboardApp doesn't make direct fetch() calls"""
        # Count direct fetch calls in dashboardApp.js
        # There should be no direct fetch() calls since we use the API client
        direct_fetch_pattern = r'(?<!fetchWith)\bfetch\s*\('
        direct_fetches = re.findall(direct_fetch_pattern, self.app_js_content)
        self.assertEqual(
            len(direct_fetches),
            0,
            f"DashboardApp should not have direct fetch() calls, found {len(direct_fetches)}"
        )
    
    def test_single_fetch_in_api_client(self):
        """Test that only one fetch exists in apiClient.js (inside fetchWithTimeout)"""
        # Count fetch calls in apiClient.js
        # We expect exactly 1 direct fetch call (inside fetchWithTimeout function)
        direct_fetch_pattern = r'\bfetch\s*\('
        direct_fetches = re.findall(direct_fetch_pattern, self.api_client_content)
        self.assertEqual(
            len(direct_fetches),
            1,
            f"Should have exactly 1 direct fetch() call in apiClient.js, found {len(direct_fetches)}"
        )
    
    def test_fetchTimeout_property_exists(self):
        """Test that fetchTimeout property is set in constructor"""
        self.assertIn('this.fetchTimeout', self.app_js_content)
        # Check that it's initialized to a reasonable value (8000ms = 8 seconds)
        self.assertIn('this.fetchTimeout = 8000', self.app_js_content)
    
    def test_api_endpoints_defined_in_client(self):
        """Test that all API endpoints are defined in apiClient.js"""
        api_endpoints = [
            '/api/health',
            '/api/summary',
            '/api/repos',
            '/api/pipelines',
            '/api/services'
        ]
        
        for endpoint in api_endpoints:
            self.assertIn(
                endpoint,
                self.api_client_content,
                f"Endpoint {endpoint} should be defined in apiClient.js"
            )
    
    def test_no_external_dependencies(self):
        """Test that no external dependencies are imported (ES modules only use local imports)"""
        # Should not import any external libraries (only local ES module imports are allowed)
        # ES module imports from './file.js' are local and acceptable
        for content in [self.app_js_content, self.api_client_content]:
            import_lines = [line for line in content.split('\n') if line.strip().startswith('import ')]
            for import_line in import_lines:
                # Check that all imports are from local files (start with './' or '../')
                # Extract the module path from the import statement
                if 'from' in import_line:
                    # Find the quoted path
                    match = re.search(r"from\s+['\"]([^'\"]+)['\"]", import_line)
                    if match:
                        module_path = match.group(1)
                        self.assertTrue(
                            module_path.startswith('./') or module_path.startswith('../'),
                            f"Import must be from local file (start with './' or '../'), got: {module_path}"
                        )
            
            self.assertNotIn('require(', content)
        
        # Verify comment states no external dependencies
        self.assertIn('no external dependencies', self.app_js_content)
        self.assertIn('no external dependencies', self.api_client_content)


if __name__ == '__main__':
    unittest.main()

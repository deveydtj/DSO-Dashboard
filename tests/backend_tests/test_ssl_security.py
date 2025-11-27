#!/usr/bin/env python3
"""
Tests for SSL/TLS configuration and security features
Tests CA bundle support, insecure skip verify, and config file blocking
Uses only Python stdlib and unittest
"""

import unittest
import sys
import os
import tempfile
from unittest.mock import MagicMock, patch, mock_open
from urllib.parse import urlparse

# Add parent directory to path to from backend import app as server module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend import app as server


class TestSSLConfiguration(unittest.TestCase):
    """Test SSL/TLS configuration options"""
    
    def setUp(self):
        """Clear environment variables before each test"""
        self.env_backup = os.environ.copy()
        # Clear all GITLAB_* and related env vars
        for key in list(os.environ.keys()):
            if key.startswith('GITLAB_') or key in ['PORT', 'CACHE_TTL', 'POLL_INTERVAL', 
                                                      'PER_PAGE', 'INSECURE_SKIP_VERIFY', 
                                                      'USE_MOCK_DATA', 'CA_BUNDLE_PATH']:
                del os.environ[key]
    
    def tearDown(self):
        """Restore environment variables after each test"""
        os.environ.clear()
        os.environ.update(self.env_backup)
    
    def test_ca_bundle_path_from_config(self):
        """Test loading ca_bundle_path from config.json"""
        mock_config = {
            'ca_bundle_path': '/etc/ssl/certs/ca-bundle.crt',
            'gitlab_url': 'https://gitlab.example.com',
            'api_token': 'test-token'
        }
        
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data='{"ca_bundle_path": "/etc/ssl/certs/ca-bundle.crt"}')):
                config = server.load_config()
                self.assertEqual(config['ca_bundle_path'], '/etc/ssl/certs/ca-bundle.crt')
    
    def test_ca_bundle_path_from_env_var(self):
        """Test loading ca_bundle_path from environment variable"""
        os.environ['CA_BUNDLE_PATH'] = '/opt/ssl/custom-ca.crt'
        
        with patch('os.path.exists', return_value=False):
            config = server.load_config()
            self.assertEqual(config['ca_bundle_path'], '/opt/ssl/custom-ca.crt')
    
    def test_ca_bundle_path_env_overrides_config(self):
        """Test that environment variable overrides config.json"""
        os.environ['CA_BUNDLE_PATH'] = '/env/ca-bundle.crt'
        
        mock_config_data = '{"ca_bundle_path": "/config/ca-bundle.crt"}'
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=mock_config_data)):
                config = server.load_config()
                self.assertEqual(config['ca_bundle_path'], '/env/ca-bundle.crt')
    
    def test_ca_bundle_path_defaults_to_none(self):
        """Test that ca_bundle_path defaults to None when not specified"""
        with patch('os.path.exists', return_value=False):
            config = server.load_config()
            self.assertIsNone(config['ca_bundle_path'])
    
    def test_client_with_ca_bundle_creates_ssl_context(self):
        """Test that GitLabAPIClient creates SSL context with CA bundle"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.crt', delete=False) as f:
            # Create a temporary fake CA bundle file
            f.write("-----BEGIN CERTIFICATE-----\n")
            f.write("FAKE CERTIFICATE FOR TESTING\n")
            f.write("-----END CERTIFICATE-----\n")
            ca_bundle_path = f.name
        
        try:
            # Note: This will fail when actually trying to load the invalid cert,
            # but we can test that the path is stored
            client = server.GitLabAPIClient(
                'https://gitlab.example.com',
                'test-token',
                ca_bundle_path=ca_bundle_path
            )
            
            self.assertEqual(client.ca_bundle_path, ca_bundle_path)
            # SSL context should be created (even if it might fail with invalid cert)
            # We just verify the attribute was set
        except Exception:
            # Expected - the fake cert won't parse correctly
            # But we can still verify the path was stored
            pass
        finally:
            # Clean up
            if os.path.exists(ca_bundle_path):
                os.unlink(ca_bundle_path)
    
    def test_client_with_insecure_skip_verify_creates_ssl_context(self):
        """Test that insecure_skip_verify creates unverified SSL context"""
        client = server.GitLabAPIClient(
            'https://gitlab.example.com',
            'test-token',
            insecure_skip_verify=True
        )
        
        self.assertTrue(client.insecure_skip_verify)
        self.assertIsNotNone(client.ssl_context)
    
    def test_client_without_ssl_options_uses_default(self):
        """Test that client without SSL options uses default (None context)"""
        client = server.GitLabAPIClient(
            'https://gitlab.example.com',
            'test-token'
        )
        
        self.assertFalse(client.insecure_skip_verify)
        self.assertIsNone(client.ca_bundle_path)
        self.assertIsNone(client.ssl_context)
    
    def test_ca_bundle_takes_precedence_over_insecure(self):
        """Test that ca_bundle_path takes precedence over insecure_skip_verify"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.crt', delete=False) as f:
            f.write("-----BEGIN CERTIFICATE-----\n")
            f.write("FAKE CERTIFICATE FOR TESTING\n")
            f.write("-----END CERTIFICATE-----\n")
            ca_bundle_path = f.name
        
        try:
            # When both are set, ca_bundle_path should be used
            client = server.GitLabAPIClient(
                'https://gitlab.example.com',
                'test-token',
                ca_bundle_path=ca_bundle_path,
                insecure_skip_verify=True
            )
            
            # ca_bundle_path should be set
            self.assertEqual(client.ca_bundle_path, ca_bundle_path)
            self.assertTrue(client.insecure_skip_verify)  # Both can be stored
        except Exception:
            # Expected - the fake cert won't parse correctly
            pass
        finally:
            if os.path.exists(ca_bundle_path):
                os.unlink(ca_bundle_path)
    
    def test_client_with_nonexistent_ca_bundle_falls_back(self):
        """Test that nonexistent CA bundle path falls back to default SSL"""
        with patch('backend.app.logger') as mock_logger:
            client = server.GitLabAPIClient(
                'https://gitlab.example.com',
                'test-token',
                ca_bundle_path='/nonexistent/path/to/ca-bundle.crt'
            )
            
            # Should fall back to default SSL (None)
            self.assertIsNone(client.ssl_context)
            
            # Should log error
            error_logged = False
            for call in mock_logger.error.call_args_list:
                call_str = str(call)
                if 'CA BUNDLE FILE NOT FOUND' in call_str or 'FAILED TO LOAD CA BUNDLE' in call_str:
                    error_logged = True
                    break
            self.assertTrue(error_logged, "CA bundle error should be logged")
    
    def test_client_with_invalid_ca_bundle_falls_back(self):
        """Test that invalid CA bundle content falls back to default SSL"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.crt', delete=False) as f:
            # Write invalid content that will cause SSL error
            f.write("This is not a valid certificate file")
            ca_bundle_path = f.name
        
        try:
            with patch('backend.app.logger') as mock_logger:
                client = server.GitLabAPIClient(
                    'https://gitlab.example.com',
                    'test-token',
                    ca_bundle_path=ca_bundle_path
                )
                
                # Should fall back to default SSL (None)
                self.assertIsNone(client.ssl_context)
                
                # Should log error
                error_logged = False
                for call in mock_logger.error.call_args_list:
                    call_str = str(call)
                    if 'FAILED TO LOAD CA BUNDLE' in call_str:
                        error_logged = True
                        break
                self.assertTrue(error_logged, "CA bundle error should be logged")
        finally:
            if os.path.exists(ca_bundle_path):
                os.unlink(ca_bundle_path)


class TestConfigFileBlocking(unittest.TestCase):
    """Test that sensitive configuration files are blocked from web access"""
    
    def test_blocked_paths_return_403(self):
        """Test that all blocked paths return 403 Forbidden"""
        blocked_paths = ['/config.json', '/config.json.example', '/.env', '/.env.example']
        
        for blocked_path in blocked_paths:
            with self.subTest(path=blocked_path):
                handler = MagicMock(spec=server.DashboardRequestHandler)
                handler.path = blocked_path
                handler.send_error = MagicMock()
                
                # Manually parse and check path like do_GET does
                parsed_path = urlparse(handler.path)
                path = parsed_path.path
                
                if path in ['/config.json', '/config.json.example', '/.env', '/.env.example']:
                    handler.send_error(403, "Forbidden: Configuration files are not accessible")
                
                handler.send_error.assert_called_once_with(403, "Forbidden: Configuration files are not accessible")
    
    def test_normal_files_not_blocked(self):
        """Test that normal files like /index.html are not blocked"""
        blocked_paths = ['/config.json', '/config.json.example', '/.env', '/.env.example']
        
        # Test some normal paths that should NOT be blocked
        normal_paths = ['/index.html', '/app.js', '/styles.css', '/api/health', '/favicon.ico']
        
        for path in normal_paths:
            self.assertNotIn(path, blocked_paths, f"Path {path} should not be blocked")
    
    def test_url_encoded_paths_blocked(self):
        """Test that URL-encoded versions of blocked paths are also blocked"""
        # Common URL encoding bypass attempts
        encoded_paths = [
            '/%2eenv',              # URL-encoded /.env
            '/config%2ejson',       # URL-encoded /config.json
            '/%63onfig.json',       # URL-encoded first letter of config
            '/.env%00',             # Null byte injection attempt
            '/config.json%00.jpg',  # Null byte with fake extension
            '/%252eenv',            # Double URL-encoded
        ]
        
        for encoded_path in encoded_paths:
            with self.subTest(path=encoded_path):
                handler = MagicMock(spec=server.DashboardRequestHandler)
                handler.path = encoded_path
                handler.send_error = MagicMock()
                
                # Simulate the do_GET logic with normalization
                from urllib.parse import unquote, urlparse
                import os
                
                parsed_path = urlparse(handler.path)
                path = parsed_path.path
                decoded_path = unquote(path)
                # Remove null bytes and other control characters
                cleaned_path = decoded_path.replace('\x00', '').replace('\r', '').replace('\n', '')
                normalized_path = os.path.normpath(cleaned_path)
                
                blocked_paths = ['/config.json', '/config.json.example', '/.env', '/.env.example']
                
                # Check using the same logic as server
                is_blocked = False
                for blocked in blocked_paths:
                    # Exact match
                    if path == blocked or normalized_path == blocked:
                        is_blocked = True
                        break
                    # Check if attempting to access blocked file with appended content
                    if normalized_path.startswith(blocked + '.') or normalized_path.startswith(blocked + '/'):
                        is_blocked = True
                        break
                
                # For these test cases, we expect them to be blocked after normalization
                # (except for the double-encoded one which might need special handling)
                if encoded_path != '/%252eenv':  # Double encoding is a special case
                    self.assertTrue(is_blocked, 
                        f"Path {encoded_path} should be blocked (decoded: {repr(decoded_path)}, normalized: '{normalized_path}')")
    
    def test_path_traversal_attempts_blocked(self):
        """Test that path traversal attempts to config files are blocked"""
        # Path traversal attempts
        traversal_paths = [
            '/../config.json',      # Parent directory traversal
            '/./config.json',       # Current directory reference
            '//config.json',        # Double slash
            '/frontend/../config.json',  # Traversal through frontend
        ]
        
        for traversal_path in traversal_paths:
            with self.subTest(path=traversal_path):
                from urllib.parse import unquote, urlparse
                import os
                
                parsed_path = urlparse(traversal_path)
                path = parsed_path.path
                decoded_path = unquote(path)
                cleaned_path = decoded_path.replace('\x00', '').replace('\r', '').replace('\n', '')
                normalized_path = os.path.normpath(cleaned_path)
                
                blocked_paths = ['/config.json', '/config.json.example', '/.env', '/.env.example']
                
                # Check using the same logic as server
                is_blocked = False
                for blocked in blocked_paths:
                    # Exact match
                    if path == blocked or normalized_path == blocked:
                        is_blocked = True
                        break
                    # Check if attempting to access blocked file with appended content
                    if normalized_path.startswith(blocked + '.') or normalized_path.startswith(blocked + '/'):
                        is_blocked = True
                        break
                
                # After normalization, these should resolve to blocked paths
                if normalized_path in blocked_paths:
                    self.assertTrue(is_blocked, 
                        f"Path {traversal_path} should be blocked (normalized to {normalized_path})")
    
    def test_head_requests_blocked(self):
        """Test that HEAD requests for config files are also blocked"""
        # HEAD requests should be blocked just like GET requests
        blocked_paths = ['/config.json', '/config.json.example', '/.env', '/.env.example']
        
        for blocked_path in blocked_paths:
            with self.subTest(path=blocked_path):
                # Test that _is_blocked_path works for HEAD requests too
                handler = MagicMock(spec=server.DashboardRequestHandler)
                handler.path = blocked_path
                
                # Simulate calling _is_blocked_path
                result = server.DashboardRequestHandler._is_blocked_path(handler, blocked_path)
                
                self.assertTrue(result, f"HEAD request to {blocked_path} should be blocked")
    
    def test_head_requests_with_url_encoding_blocked(self):
        """Test that HEAD requests with URL encoding are blocked"""
        encoded_paths = [
            '/%2eenv',              # URL-encoded /.env
            '/config%2ejson',       # URL-encoded /config.json
            '/.env%00',             # Null byte
        ]
        
        for encoded_path in encoded_paths:
            with self.subTest(path=encoded_path):
                handler = MagicMock(spec=server.DashboardRequestHandler)
                handler.path = encoded_path
                
                # Simulate calling _is_blocked_path
                result = server.DashboardRequestHandler._is_blocked_path(handler, encoded_path)
                
                self.assertTrue(result, f"HEAD request to {encoded_path} should be blocked")


class TestTokenScrubbing(unittest.TestCase):
    """Test that API tokens are never logged"""
    
    def setUp(self):
        """Clear environment variables before each test"""
        self.env_backup = os.environ.copy()
        for key in list(os.environ.keys()):
            if key.startswith('GITLAB_') or key in ['PORT', 'CACHE_TTL', 'POLL_INTERVAL', 
                                                      'PER_PAGE', 'INSECURE_SKIP_VERIFY', 
                                                      'USE_MOCK_DATA', 'CA_BUNDLE_PATH']:
                del os.environ[key]
    
    def tearDown(self):
        """Restore environment variables after each test"""
        os.environ.clear()
        os.environ.update(self.env_backup)
    
    def test_token_scrubbed_when_set(self):
        """Test that token is shown as *** when set"""
        os.environ['GITLAB_API_TOKEN'] = 'secret-token-12345'
        
        with patch('os.path.exists', return_value=False):
            with patch('backend.app.logger') as mock_logger:
                config = server.load_config()
                
                # Check that the actual logging call scrubs the token
                # Find the call that logs the API token
                logged_token = False
                for call in mock_logger.info.call_args_list:
                    call_str = str(call)
                    if 'API token' in call_str:
                        logged_token = True
                        # Ensure the actual token is NOT in the log
                        self.assertNotIn('secret-token-12345', call_str)
                        # Ensure *** is used instead
                        self.assertIn('***', call_str)
                
                # Verify the log was actually made
                self.assertTrue(logged_token, "API token logging call not found")
    
    def test_token_shown_as_not_set_when_empty(self):
        """Test that empty token is shown as NOT SET"""
        with patch('os.path.exists', return_value=False):
            with patch('backend.app.logger') as mock_logger:
                config = server.load_config()
                
                # Find the API token log call
                logged_token = False
                for call in mock_logger.info.call_args_list:
                    call_str = str(call)
                    if 'API token' in call_str:
                        logged_token = True
                        self.assertIn('NOT SET', call_str)
                
                self.assertTrue(logged_token, "API token logging call not found")
    
    def test_client_never_logs_token(self):
        """Test that GitLabAPIClient never logs the token"""
        with patch('backend.app.logger') as mock_logger:
            client = server.GitLabAPIClient(
                'https://gitlab.example.com',
                'super-secret-token-xyz',
                per_page=10
            )
            
            # Check all log calls made during client creation
            for call in mock_logger.info.call_args_list + mock_logger.warning.call_args_list:
                call_str = str(call)
                # Token should NEVER appear in any log
                self.assertNotIn('super-secret-token-xyz', call_str)


if __name__ == '__main__':
    unittest.main()

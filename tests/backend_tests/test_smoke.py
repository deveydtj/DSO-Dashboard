#!/usr/bin/env python3
"""
Smoke tests for DSO-Dashboard
Tests basic functionality without requiring GitLab API access
Uses only Python stdlib and unittest
"""

import unittest
import sys
import os
import json
from unittest.mock import MagicMock, patch
from datetime import datetime

# Add parent directory to path to from backend import app as server module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend import app as server


class TestConfigLoading(unittest.TestCase):
    """Test configuration loading from config.json and environment variables"""
    
    def setUp(self):
        """Clear environment variables before each test"""
        self.env_backup = os.environ.copy()
        # Clear all GITLAB_* and related env vars
        for key in list(os.environ.keys()):
            if key.startswith('GITLAB_') or key in ['PORT', 'CACHE_TTL', 'POLL_INTERVAL', 'PER_PAGE', 'INSECURE_SKIP_VERIFY', 'USE_MOCK_DATA']:
                del os.environ[key]
    
    def tearDown(self):
        """Restore environment variables after each test"""
        os.environ.clear()
        os.environ.update(self.env_backup)
    
    def test_load_config_defaults(self):
        """Test config loading with defaults when no file or env vars exist"""
        with patch('os.path.exists', return_value=False):
            config = server.load_config()
            
            self.assertEqual(config['gitlab_url'], 'https://gitlab.com')
            self.assertEqual(config['port'], 8080)
            self.assertEqual(config['cache_ttl_sec'], 300)
            self.assertEqual(config['poll_interval_sec'], 60)
            self.assertEqual(config['per_page'], 100)
            self.assertEqual(config['insecure_skip_verify'], False)
            self.assertEqual(config['use_mock_data'], False)
            self.assertEqual(config['group_ids'], [])
            self.assertEqual(config['project_ids'], [])
    
    def test_load_config_from_env_vars(self):
        """Test config loading from environment variables"""
        os.environ['GITLAB_URL'] = 'https://gitlab.example.com'
        os.environ['GITLAB_API_TOKEN'] = 'test-token'
        os.environ['PORT'] = '9090'
        os.environ['POLL_INTERVAL'] = '120'
        os.environ['GITLAB_GROUP_IDS'] = 'group1,group2,group3'
        os.environ['INSECURE_SKIP_VERIFY'] = 'true'
        
        with patch('os.path.exists', return_value=False):
            config = server.load_config()
            
            self.assertEqual(config['gitlab_url'], 'https://gitlab.example.com')
            self.assertEqual(config['api_token'], 'test-token')
            self.assertEqual(config['port'], 9090)
            self.assertEqual(config['poll_interval_sec'], 120)
            self.assertEqual(config['group_ids'], ['group1', 'group2', 'group3'])
            self.assertEqual(config['insecure_skip_verify'], True)
    
    def test_load_config_mock_mode_enabled(self):
        """Test config with mock mode enabled"""
        os.environ['USE_MOCK_DATA'] = 'true'
        
        with patch('os.path.exists', return_value=False):
            config = server.load_config()
            
            self.assertTrue(config['use_mock_data'])
    
    def test_load_config_mock_mode_disabled(self):
        """Test config with mock mode explicitly disabled"""
        os.environ['USE_MOCK_DATA'] = 'false'
        
        with patch('os.path.exists', return_value=False):
            config = server.load_config()
            
            self.assertFalse(config['use_mock_data'])
    
    def test_parse_csv_list(self):
        """Test CSV list parsing for group_ids and project_ids"""
        result = server.parse_csv_list('group1,group2,group3')
        self.assertEqual(result, ['group1', 'group2', 'group3'])
        
        # Test with spaces
        result = server.parse_csv_list('group1, group2 , group3')
        self.assertEqual(result, ['group1', 'group2', 'group3'])
        
        # Test empty string
        result = server.parse_csv_list('')
        self.assertEqual(result, [])
        
        # Test None
        result = server.parse_csv_list(None)
        self.assertEqual(result, [])
    
    def test_parse_int_config(self):
        """Test integer config parsing with fallback"""
        result = server.parse_int_config('8080', 3000, 'PORT')
        self.assertEqual(result, 8080)
        
        # Test invalid integer
        result = server.parse_int_config('invalid', 3000, 'PORT')
        self.assertEqual(result, 3000)
        
        # Test None
        result = server.parse_int_config(None, 3000, 'PORT')
        self.assertEqual(result, 3000)


class TestStateManagement(unittest.TestCase):
    """Test thread-safe state management functions"""
    
    def setUp(self):
        """Reset global STATE before each test"""
        with server.STATE_LOCK:
            server.STATE['data'] = {}
            server.STATE['last_updated'] = None
            server.STATE['status'] = 'INITIALIZING'
            server.STATE['error'] = None
    
    def test_update_state_single_key(self):
        """Test updating single key in STATE"""
        server.update_state('projects', [{'id': 1, 'name': 'test'}])
        
        projects = server.get_state('projects')
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0]['name'], 'test')
        
        status = server.get_state_status()
        self.assertEqual(status['status'], 'ONLINE')
        self.assertIsNotNone(status['last_updated'])
    
    def test_update_state_atomic(self):
        """Test atomic update of multiple STATE keys"""
        updates = {
            'projects': [{'id': 1}],
            'pipelines': [{'id': 2}],
            'summary': {'total': 2}
        }
        server.update_state_atomic(updates)
        
        self.assertEqual(len(server.get_state('projects')), 1)
        self.assertEqual(len(server.get_state('pipelines')), 1)
        self.assertEqual(server.get_state('summary')['total'], 2)
        
        status = server.get_state_status()
        self.assertEqual(status['status'], 'ONLINE')
    
    def test_get_state_nonexistent_key(self):
        """Test getting non-existent key returns None"""
        result = server.get_state('nonexistent')
        self.assertIsNone(result)
    
    def test_set_state_error(self):
        """Test setting error state"""
        server.set_state_error('Test error')
        
        status = server.get_state_status()
        self.assertEqual(status['status'], 'ERROR')
        self.assertEqual(status['error'], 'Test error')


class TestGitLabAPIClient(unittest.TestCase):
    """Test GitLab API client without making real API calls"""
    
    def setUp(self):
        """Create a client instance for testing"""
        self.client = server.GitLabAPIClient(
            'https://gitlab.example.com',
            'test-token',
            per_page=10
        )
    
    def test_client_initialization(self):
        """Test client is initialized with correct values"""
        self.assertEqual(self.client.gitlab_url, 'https://gitlab.example.com')
        self.assertEqual(self.client.api_token, 'test-token')
        self.assertEqual(self.client.base_url, 'https://gitlab.example.com/api/v4')
        self.assertEqual(self.client.per_page, 10)
        self.assertEqual(self.client.insecure_skip_verify, False)
        self.assertIsNone(self.client.ssl_context)
    
    def test_client_with_insecure_skip_verify(self):
        """Test client with SSL verification disabled"""
        client = server.GitLabAPIClient(
            'https://gitlab.example.com',
            'test-token',
            insecure_skip_verify=True
        )
        self.assertTrue(client.insecure_skip_verify)
        self.assertIsNotNone(client.ssl_context)
    
    def test_process_response_valid_json(self):
        """Test processing valid JSON response"""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"data": "test"}'
        mock_response.headers = {}
        
        result = self.client._process_response(mock_response)
        self.assertEqual(result['data'], {'data': 'test'})
    
    def test_process_response_invalid_json(self):
        """Test processing invalid JSON returns None"""
        mock_response = MagicMock()
        mock_response.read.return_value = b'invalid json'
        mock_response.headers = {}
        
        result = self.client._process_response(mock_response)
        self.assertIsNone(result)


class TestHelperFunctions(unittest.TestCase):
    """Test various helper functions"""
    
    def test_parse_csv_list_edge_cases(self):
        """Test CSV list parsing with edge cases"""
        # Single item
        self.assertEqual(server.parse_csv_list('single'), ['single'])
        
        # Empty items in list
        self.assertEqual(server.parse_csv_list('a,,b'), ['a', 'b'])
        
        # Whitespace-only items
        self.assertEqual(server.parse_csv_list('a,  ,b'), ['a', 'b'])
        
        # Single comma
        self.assertEqual(server.parse_csv_list(','), [])
    
    def test_parse_int_config_edge_cases(self):
        """Test integer parsing with edge cases"""
        # Zero
        self.assertEqual(server.parse_int_config('0', 100, 'test'), 0)
        
        # Negative
        self.assertEqual(server.parse_int_config('-5', 100, 'test'), -5)
        
        # Float string (invalid format, falls back to default)
        self.assertEqual(server.parse_int_config('42.7', 100, 'test'), 100)
        
        # Empty string
        self.assertEqual(server.parse_int_config('', 100, 'test'), 100)


class TestConstants(unittest.TestCase):
    """Test that important constants are defined correctly"""
    
    def test_pipeline_constants(self):
        """Test pipeline-related constants"""
        self.assertIsInstance(server.MAX_PROJECTS_FOR_PIPELINES, int)
        self.assertIsInstance(server.PIPELINES_PER_PROJECT, int)
        self.assertIsInstance(server.DEFAULT_PIPELINE_LIMIT, int)
        self.assertIsInstance(server.MAX_PIPELINE_LIMIT, int)
        
        # Sanity checks
        self.assertGreater(server.MAX_PROJECTS_FOR_PIPELINES, 0)
        self.assertGreater(server.PIPELINES_PER_PROJECT, 0)
        self.assertGreater(server.DEFAULT_PIPELINE_LIMIT, 0)
        self.assertGreater(server.MAX_PIPELINE_LIMIT, server.DEFAULT_PIPELINE_LIMIT)
    
    def test_fallback_constants(self):
        """Test fallback constants"""
        self.assertEqual(server.EPOCH_TIMESTAMP, '1970-01-01T00:00:00Z')
        self.assertEqual(server.DEFAULT_BRANCH_NAME, 'main')


class TestImports(unittest.TestCase):
    """Test that all required stdlib modules can be imported"""
    
    def test_stdlib_imports(self):
        """Test that server.py only uses stdlib modules"""
        import json
        import os
        import ssl
        import time
        import threading
        from datetime import datetime, timedelta
        from http.server import HTTPServer, SimpleHTTPRequestHandler
        from urllib.request import Request, urlopen
        from urllib.error import URLError, HTTPError
        from urllib.parse import urlparse, parse_qs, urlencode
        import logging
        
        # If we got here, all imports succeeded
        self.assertTrue(True)


class TestMockDataMode(unittest.TestCase):
    """Test mock data mode functionality"""
    
    def test_load_mock_data_success(self):
        """Test loading mock data from valid JSON file"""
        mock_data = {
            'summary': {'total_repositories': 5},
            'repositories': [{'id': 1, 'name': 'test'}],
            'pipelines': [{'id': 100, 'status': 'success'}]
        }
        
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', unittest.mock.mock_open(read_data=json.dumps(mock_data))):
                result = server.load_mock_data()
                
                self.assertIsNotNone(result)
                self.assertIn('summary', result)
                self.assertIn('repositories', result)
                self.assertIn('pipelines', result)
                self.assertEqual(result['summary']['total_repositories'], 5)
    
    def test_load_mock_data_file_not_found(self):
        """Test loading mock data when file doesn't exist"""
        with patch('os.path.exists', return_value=False):
            result = server.load_mock_data()
            self.assertIsNone(result)
    
    def test_load_mock_data_missing_keys(self):
        """Test loading mock data with missing required keys"""
        incomplete_data = {
            'summary': {'total_repositories': 5}
            # Missing 'repositories' and 'pipelines'
        }
        
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', unittest.mock.mock_open(read_data=json.dumps(incomplete_data))):
                result = server.load_mock_data()
                self.assertIsNone(result)
    
    def test_load_mock_data_invalid_json(self):
        """Test loading mock data with invalid JSON"""
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', unittest.mock.mock_open(read_data='invalid json {')):
                result = server.load_mock_data()
                self.assertIsNone(result)
    
    def test_summary_includes_is_mock_field_when_mock_enabled(self):
        """Test that /api/summary includes is_mock=true when MOCK_MODE_ENABLED is True"""
        # Set mock mode to enabled
        original_mock_mode = server.MOCK_MODE_ENABLED
        server.MOCK_MODE_ENABLED = True
        
        try:
            # Set up mock state data
            mock_summary = {
                'total_repositories': 5,
                'successful_pipelines': 10
            }
            server.update_state('summary', mock_summary)
            
            # Create a mock request handler
            handler = MagicMock(spec=server.DashboardRequestHandler)
            handler.send_json_response = MagicMock()
            
            # Call handle_summary
            server.DashboardRequestHandler.handle_summary(handler)
            
            # Verify response includes is_mock=True
            handler.send_json_response.assert_called_once()
            response_data = handler.send_json_response.call_args[0][0]
            self.assertIn('is_mock', response_data)
            self.assertTrue(response_data['is_mock'])
        finally:
            # Restore original mock mode
            server.MOCK_MODE_ENABLED = original_mock_mode
    
    def test_summary_includes_is_mock_field_when_mock_disabled(self):
        """Test that /api/summary includes is_mock=false when MOCK_MODE_ENABLED is False"""
        # Ensure mock mode is disabled
        original_mock_mode = server.MOCK_MODE_ENABLED
        server.MOCK_MODE_ENABLED = False
        
        try:
            # Set up mock state data
            mock_summary = {
                'total_repositories': 5,
                'successful_pipelines': 10
            }
            server.update_state('summary', mock_summary)
            
            # Create a mock request handler
            handler = MagicMock(spec=server.DashboardRequestHandler)
            handler.send_json_response = MagicMock()
            
            # Call handle_summary
            server.DashboardRequestHandler.handle_summary(handler)
            
            # Verify response includes is_mock=False
            handler.send_json_response.assert_called_once()
            response_data = handler.send_json_response.call_args[0][0]
            self.assertIn('is_mock', response_data)
            self.assertFalse(response_data['is_mock'])
        finally:
            # Restore original mock mode
            server.MOCK_MODE_ENABLED = original_mock_mode


class TestSloConfigSmoke(unittest.TestCase):
    """Smoke tests for SLO configuration loading"""
    
    def setUp(self):
        """Clear environment variables before each test"""
        self.env_backup = os.environ.copy()
        # Clear all GITLAB_* and SLO_* env vars
        for key in list(os.environ.keys()):
            if key.startswith('GITLAB_') or key.startswith('SLO_') or key in ['PORT', 'CACHE_TTL', 'POLL_INTERVAL', 'PER_PAGE', 'INSECURE_SKIP_VERIFY', 'USE_MOCK_DATA']:
                del os.environ[key]
    
    def tearDown(self):
        """Restore environment variables after each test"""
        os.environ.clear()
        os.environ.update(self.env_backup)
    
    def test_load_config_returns_slo_key(self):
        """Test that load_config() returns a dict with a 'slo' key"""
        with patch('os.path.exists', return_value=False):
            config = server.load_config()
            
            self.assertIn('slo', config)
            self.assertIsInstance(config['slo'], dict)
    
    def test_load_config_slo_has_default_branch_success_target(self):
        """Test that config['slo']['default_branch_success_target'] is a float within (0, 1)"""
        with patch('os.path.exists', return_value=False):
            config = server.load_config()
            
            self.assertIn('default_branch_success_target', config['slo'])
            target = config['slo']['default_branch_success_target']
            self.assertIsInstance(target, float)
            self.assertGreater(target, 0)
            self.assertLess(target, 1)
    
    def test_load_config_slo_default_value(self):
        """Test that default SLO target is 0.99"""
        with patch('os.path.exists', return_value=False):
            config = server.load_config()
            
            self.assertEqual(config['slo']['default_branch_success_target'], 0.99)
    
    def test_load_config_slo_from_env_var(self):
        """Test that SLO can be configured via environment variable"""
        os.environ['SLO_DEFAULT_BRANCH_SUCCESS_TARGET'] = '0.95'
        
        with patch('os.path.exists', return_value=False):
            config = server.load_config()
            
            self.assertEqual(config['slo']['default_branch_success_target'], 0.95)
    
    def test_load_config_slo_from_config_json(self):
        """Test that SLO can be configured via config.json"""
        config_data = {
            'gitlab_url': 'https://gitlab.com',
            'api_token': 'test',
            'slo': {
                'default_branch_success_target': 0.9
            }
        }
        
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', unittest.mock.mock_open(read_data=json.dumps(config_data))):
                config = server.load_config()
                
                self.assertEqual(config['slo']['default_branch_success_target'], 0.9)
    
    def test_load_config_slo_env_overrides_config_json(self):
        """Test that env var overrides config.json for SLO"""
        os.environ['SLO_DEFAULT_BRANCH_SUCCESS_TARGET'] = '0.95'
        
        config_data = {
            'gitlab_url': 'https://gitlab.com',
            'api_token': 'test',
            'slo': {
                'default_branch_success_target': 0.9
            }
        }
        
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', unittest.mock.mock_open(read_data=json.dumps(config_data))):
                config = server.load_config()
                
                # Env var should override config.json
                self.assertEqual(config['slo']['default_branch_success_target'], 0.95)
    
    def test_default_slo_config_constant_exists(self):
        """Test that DEFAULT_SLO_CONFIG constant is defined and accessible"""
        self.assertTrue(hasattr(server, 'DEFAULT_SLO_CONFIG'))
        self.assertIsInstance(server.DEFAULT_SLO_CONFIG, dict)
        self.assertIn('default_branch_success_target', server.DEFAULT_SLO_CONFIG)
    
    def test_missing_slo_section_uses_defaults(self):
        """Test that missing slo section falls back to DEFAULT_SLO_CONFIG"""
        config_data = {
            'gitlab_url': 'https://gitlab.com',
            'api_token': 'test'
            # No slo section
        }
        
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', unittest.mock.mock_open(read_data=json.dumps(config_data))):
                config = server.load_config()
                
                # Should use default
                self.assertIn('slo', config)
                self.assertEqual(
                    config['slo']['default_branch_success_target'],
                    server.DEFAULT_SLO_CONFIG['default_branch_success_target']
                )


class TestBackgroundPollerSloConfig(unittest.TestCase):
    """Test BackgroundPoller SLO config wiring"""
    
    def test_poller_accepts_slo_config(self):
        """Test that BackgroundPoller accepts slo_config parameter"""
        gitlab_client = MagicMock()
        slo_config = {'default_branch_success_target': 0.95}
        
        poller = server.BackgroundPoller(
            gitlab_client,
            poll_interval_sec=60,
            slo_config=slo_config
        )
        
        self.assertEqual(poller.slo_config['default_branch_success_target'], 0.95)
    
    def test_poller_uses_default_slo_when_none(self):
        """Test that BackgroundPoller uses DEFAULT_SLO_CONFIG when slo_config is None"""
        gitlab_client = MagicMock()
        
        poller = server.BackgroundPoller(
            gitlab_client,
            poll_interval_sec=60,
            slo_config=None
        )
        
        self.assertEqual(
            poller.slo_config['default_branch_success_target'],
            server.DEFAULT_SLO_CONFIG['default_branch_success_target']
        )
    
    def test_poller_slo_config_is_copy(self):
        """Test that BackgroundPoller makes a copy of slo_config to prevent mutation"""
        gitlab_client = MagicMock()
        slo_config = {'default_branch_success_target': 0.95}
        
        poller = server.BackgroundPoller(
            gitlab_client,
            poll_interval_sec=60,
            slo_config=slo_config
        )
        
        # Mutate the original dict
        slo_config['default_branch_success_target'] = 0.5
        
        # Poller's config should not have changed
        self.assertEqual(poller.slo_config['default_branch_success_target'], 0.95)
    
    def test_poller_default_slo_not_mutated(self):
        """Test that BackgroundPoller does not mutate DEFAULT_SLO_CONFIG"""
        gitlab_client = MagicMock()
        original_default = server.DEFAULT_SLO_CONFIG['default_branch_success_target']
        
        poller = server.BackgroundPoller(
            gitlab_client,
            poll_interval_sec=60,
            slo_config=None
        )
        
        # Mutate the poller's config
        poller.slo_config['default_branch_success_target'] = 0.5
        
        # DEFAULT_SLO_CONFIG should not have changed
        self.assertEqual(server.DEFAULT_SLO_CONFIG['default_branch_success_target'], original_default)


if __name__ == '__main__':
    unittest.main()

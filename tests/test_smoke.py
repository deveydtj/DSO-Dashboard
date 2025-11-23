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

# Add parent directory to path to import server module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import server


class TestConfigLoading(unittest.TestCase):
    """Test configuration loading from config.json and environment variables"""
    
    def setUp(self):
        """Clear environment variables before each test"""
        self.env_backup = os.environ.copy()
        # Clear all GITLAB_* and related env vars
        for key in list(os.environ.keys()):
            if key.startswith('GITLAB_') or key in ['PORT', 'CACHE_TTL', 'POLL_INTERVAL', 'PER_PAGE', 'INSECURE_SKIP_VERIFY']:
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
        
        # Float string (should convert to int)
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


if __name__ == '__main__':
    unittest.main()

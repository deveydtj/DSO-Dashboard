#!/usr/bin/env python3
"""
Tests for logging and observability features in DSO-Dashboard
Tests log level configuration, timing logs, poll_id, and HTTP access logging
Uses only Python stdlib and unittest
"""

import unittest
import sys
import os
import logging
from unittest.mock import MagicMock, patch, call
from io import StringIO

# Add parent directory to path to from backend import app as server module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend import app as server


class TestLogLevelConfiguration(unittest.TestCase):
    """Test LOG_LEVEL configuration via environment variable and config.json"""
    
    def setUp(self):
        """Clear environment variables before each test"""
        self.env_backup = os.environ.copy()
        # Clear all GITLAB_* and related env vars
        for key in list(os.environ.keys()):
            if key.startswith('GITLAB_') or key in ['PORT', 'CACHE_TTL', 'POLL_INTERVAL', 'PER_PAGE', 
                                                      'INSECURE_SKIP_VERIFY', 'USE_MOCK_DATA', 'LOG_LEVEL']:
                del os.environ[key]
    
    def tearDown(self):
        """Restore environment variables after each test"""
        os.environ.clear()
        os.environ.update(self.env_backup)
    
    def test_get_log_level_default(self):
        """Test get_log_level returns INFO by default"""
        if 'LOG_LEVEL' in os.environ:
            del os.environ['LOG_LEVEL']
        level = server.get_log_level()
        self.assertEqual(level, logging.INFO)
    
    def test_get_log_level_debug(self):
        """Test get_log_level returns DEBUG when LOG_LEVEL=DEBUG"""
        os.environ['LOG_LEVEL'] = 'DEBUG'
        level = server.get_log_level()
        self.assertEqual(level, logging.DEBUG)
    
    def test_get_log_level_warning(self):
        """Test get_log_level returns WARNING when LOG_LEVEL=WARNING"""
        os.environ['LOG_LEVEL'] = 'WARNING'
        level = server.get_log_level()
        self.assertEqual(level, logging.WARNING)
    
    def test_get_log_level_error(self):
        """Test get_log_level returns ERROR when LOG_LEVEL=ERROR"""
        os.environ['LOG_LEVEL'] = 'ERROR'
        level = server.get_log_level()
        self.assertEqual(level, logging.ERROR)
    
    def test_get_log_level_critical(self):
        """Test get_log_level returns CRITICAL when LOG_LEVEL=CRITICAL"""
        os.environ['LOG_LEVEL'] = 'CRITICAL'
        level = server.get_log_level()
        self.assertEqual(level, logging.CRITICAL)
    
    def test_get_log_level_case_insensitive(self):
        """Test LOG_LEVEL is case-insensitive"""
        os.environ['LOG_LEVEL'] = 'debug'
        level = server.get_log_level()
        self.assertEqual(level, logging.DEBUG)
        
        os.environ['LOG_LEVEL'] = 'DeBuG'
        level = server.get_log_level()
        self.assertEqual(level, logging.DEBUG)
    
    def test_get_log_level_invalid_falls_back_to_info(self):
        """Test invalid LOG_LEVEL falls back to INFO"""
        os.environ['LOG_LEVEL'] = 'INVALID'
        level = server.get_log_level()
        self.assertEqual(level, logging.INFO)
    
    def test_load_config_includes_log_level(self):
        """Test load_config includes log_level in returned config"""
        with patch('os.path.exists', return_value=False):
            config = server.load_config()
            
            self.assertIn('log_level', config)
            self.assertEqual(config['log_level'], 'INFO')
    
    def test_load_config_log_level_from_env(self):
        """Test load_config picks up LOG_LEVEL from environment"""
        os.environ['LOG_LEVEL'] = 'DEBUG'
        
        with patch('os.path.exists', return_value=False):
            config = server.load_config()
            
            self.assertEqual(config['log_level'], 'DEBUG')
    
    def test_load_config_invalid_log_level_falls_back_to_info(self):
        """Test load_config falls back to INFO for invalid LOG_LEVEL"""
        os.environ['LOG_LEVEL'] = 'INVALID_LEVEL'
        
        with patch('os.path.exists', return_value=False):
            config = server.load_config()
            
            self.assertEqual(config['log_level'], 'INFO')
    
    def test_valid_log_levels_constant(self):
        """Test VALID_LOG_LEVELS contains expected values"""
        expected = ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
        self.assertEqual(server.VALID_LOG_LEVELS, expected)


class TestPollCounter(unittest.TestCase):
    """Test poll_id generation in BackgroundPoller"""
    
    def test_poll_counter_initializes_to_zero(self):
        """Test poll_counter starts at 0"""
        client = MagicMock()
        poller = server.BackgroundPoller(client, 60)
        self.assertEqual(poller.poll_counter, 0)
    
    def test_generate_poll_id_increments_counter(self):
        """Test _generate_poll_id increments poll_counter"""
        client = MagicMock()
        poller = server.BackgroundPoller(client, 60)
        
        poll_id1 = poller._generate_poll_id()
        poll_id2 = poller._generate_poll_id()
        poll_id3 = poller._generate_poll_id()
        
        self.assertEqual(poll_id1, 'poll-1')
        self.assertEqual(poll_id2, 'poll-2')
        self.assertEqual(poll_id3, 'poll-3')
    
    def test_poll_counter_persists_across_calls(self):
        """Test poll_counter persists across multiple poll cycles"""
        client = MagicMock()
        poller = server.BackgroundPoller(client, 60)
        
        # Simulate multiple poll cycles
        for i in range(1, 6):
            poll_id = poller._generate_poll_id()
            self.assertEqual(poll_id, f'poll-{i}')
        
        self.assertEqual(poller.poll_counter, 5)


class TestSetStateErrorWithPollId(unittest.TestCase):
    """Test set_state_error accepts poll_id for logging context"""
    
    def setUp(self):
        """Reset global STATE before each test"""
        with server.STATE_LOCK:
            server.STATE['data'] = {}
            server.STATE['last_updated'] = None
            server.STATE['status'] = 'INITIALIZING'
            server.STATE['error'] = None
    
    def test_set_state_error_without_poll_id(self):
        """Test set_state_error works without poll_id"""
        server.set_state_error('Test error')
        
        status = server.get_state_status()
        self.assertEqual(status['status'], 'ERROR')
        self.assertEqual(status['error'], 'Test error')
    
    def test_set_state_error_with_poll_id(self):
        """Test set_state_error works with poll_id"""
        server.set_state_error('Test error', poll_id='poll-42')
        
        status = server.get_state_status()
        self.assertEqual(status['status'], 'ERROR')
        self.assertEqual(status['error'], 'Test error')


class TestGitLabAPIClientTiming(unittest.TestCase):
    """Test timing instrumentation in GitLabAPIClient"""
    
    def setUp(self):
        """Create a client instance for testing"""
        self.client = server.GitLabAPIClient(
            'https://gitlab.example.com',
            'test-token',
            per_page=10
        )
    
    def test_mask_url_returns_url(self):
        """Test _mask_url returns the URL (no token in query string)"""
        url = 'https://gitlab.example.com/api/v4/projects?per_page=10'
        masked = self.client._mask_url(url)
        self.assertEqual(masked, url)


class TestHTTPAccessLogging(unittest.TestCase):
    """Test enhanced HTTP access logging in DashboardRequestHandler"""
    
    def test_log_message_api_tag(self):
        """Test log_message includes 'api' tag for API requests"""
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.path = '/api/health'
        handler.command = 'GET'
        handler.address_string = MagicMock(return_value='127.0.0.1')
        
        # Create a log capture
        with patch.object(server.logger, 'info') as mock_log:
            server.DashboardRequestHandler.log_message(handler, '200 OK')
            
            # Check the log was called with api tag
            mock_log.assert_called_once()
            log_message = mock_log.call_args[0][0]
            self.assertIn('[api]', log_message)
            self.assertIn('GET', log_message)
            self.assertIn('/api/health', log_message)
    
    def test_log_message_static_tag(self):
        """Test log_message includes 'static' tag for non-API requests"""
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.path = '/index.html'
        handler.command = 'GET'
        handler.address_string = MagicMock(return_value='127.0.0.1')
        
        with patch.object(server.logger, 'info') as mock_log:
            server.DashboardRequestHandler.log_message(handler, '200 OK')
            
            mock_log.assert_called_once()
            log_message = mock_log.call_args[0][0]
            self.assertIn('[static]', log_message)
            self.assertIn('GET', log_message)
            self.assertIn('/index.html', log_message)
    
    def test_log_message_with_query_params(self):
        """Test log_message correctly identifies API paths with query params"""
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.path = '/api/pipelines?limit=10&status=failed'
        handler.command = 'GET'
        handler.address_string = MagicMock(return_value='127.0.0.1')
        
        with patch.object(server.logger, 'info') as mock_log:
            server.DashboardRequestHandler.log_message(handler, '200 OK')
            
            mock_log.assert_called_once()
            log_message = mock_log.call_args[0][0]
            self.assertIn('[api]', log_message)


if __name__ == '__main__':
    unittest.main()

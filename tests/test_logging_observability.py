#!/usr/bin/env python3
"""
Tests for logging and observability improvements (PR 1)
- LOG_LEVEL configuration
- GitLab API timing logs
- Poll cycle identifiers
- HTTP access logging with route type
"""

import unittest
import sys
import os
import logging
from unittest.mock import MagicMock, patch
from io import StringIO

# Add parent directory to path to import server module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import server


class TestLogLevelConfiguration(unittest.TestCase):
    """Test LOG_LEVEL environment variable configuration"""
    
    def setUp(self):
        """Clear LOG_LEVEL env var before each test"""
        self.env_backup = os.environ.copy()
        if 'LOG_LEVEL' in os.environ:
            del os.environ['LOG_LEVEL']
    
    def tearDown(self):
        """Restore environment after each test"""
        os.environ.clear()
        os.environ.update(self.env_backup)
    
    def test_get_log_level_default(self):
        """Test that default log level is INFO when LOG_LEVEL not set"""
        level, name = server.get_log_level()
        self.assertEqual(level, logging.INFO)
        self.assertEqual(name, 'INFO')
    
    def test_get_log_level_debug(self):
        """Test DEBUG log level"""
        os.environ['LOG_LEVEL'] = 'DEBUG'
        level, name = server.get_log_level()
        self.assertEqual(level, logging.DEBUG)
        self.assertEqual(name, 'DEBUG')
    
    def test_get_log_level_warning(self):
        """Test WARNING log level"""
        os.environ['LOG_LEVEL'] = 'WARNING'
        level, name = server.get_log_level()
        self.assertEqual(level, logging.WARNING)
        self.assertEqual(name, 'WARNING')
    
    def test_get_log_level_error(self):
        """Test ERROR log level"""
        os.environ['LOG_LEVEL'] = 'ERROR'
        level, name = server.get_log_level()
        self.assertEqual(level, logging.ERROR)
        self.assertEqual(name, 'ERROR')
    
    def test_get_log_level_critical(self):
        """Test CRITICAL log level"""
        os.environ['LOG_LEVEL'] = 'CRITICAL'
        level, name = server.get_log_level()
        self.assertEqual(level, logging.CRITICAL)
        self.assertEqual(name, 'CRITICAL')
    
    def test_get_log_level_lowercase(self):
        """Test that lowercase log level names work"""
        os.environ['LOG_LEVEL'] = 'debug'
        level, name = server.get_log_level()
        self.assertEqual(level, logging.DEBUG)
        self.assertEqual(name, 'DEBUG')
    
    def test_get_log_level_invalid_fallback(self):
        """Test that invalid log level falls back to INFO"""
        os.environ['LOG_LEVEL'] = 'INVALID'
        level, name = server.get_log_level()
        self.assertEqual(level, logging.INFO)
        self.assertEqual(name, 'INFO')
    
    def test_log_level_map_has_all_standard_levels(self):
        """Test that LOG_LEVEL_MAP contains all standard logging levels"""
        expected_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        for level_name in expected_levels:
            self.assertIn(level_name, server.LOG_LEVEL_MAP)


class TestPollCycleIdentifier(unittest.TestCase):
    """Test poll cycle identifier (poll_id) in BackgroundPoller"""
    
    def test_poll_counter_initialization(self):
        """Test that poll_counter starts at 0"""
        poller = server.BackgroundPoller(None, 60)
        self.assertEqual(poller.poll_counter, 0)
    
    def test_poll_counter_increments(self):
        """Test that poll_counter increments on each poll"""
        poller = server.BackgroundPoller(None, 60)
        
        # Mock the methods that poll_data calls
        with patch.object(poller, '_fetch_projects', return_value=None):
            poller.poll_data()
            self.assertEqual(poller.poll_counter, 1)
            
            poller.poll_data()
            self.assertEqual(poller.poll_counter, 2)
            
            poller.poll_data()
            self.assertEqual(poller.poll_counter, 3)


class TestSetStateErrorWithPollId(unittest.TestCase):
    """Test that set_state_error accepts poll_id for correlation"""
    
    def setUp(self):
        """Reset STATE before each test"""
        with server.STATE_LOCK:
            server.STATE['status'] = 'INITIALIZING'
            server.STATE['error'] = None
    
    def test_set_state_error_without_poll_id(self):
        """Test set_state_error works without poll_id"""
        server.set_state_error("Test error")
        status = server.get_state_status()
        self.assertEqual(status['status'], 'ERROR')
        self.assertEqual(status['error'], 'Test error')
    
    def test_set_state_error_with_poll_id(self):
        """Test set_state_error works with poll_id"""
        server.set_state_error("Test error", poll_id="poll-5")
        status = server.get_state_status()
        self.assertEqual(status['status'], 'ERROR')
        self.assertEqual(status['error'], 'Test error')


class TestHTTPAccessLogging(unittest.TestCase):
    """Test improved HTTP access logging with route type"""
    
    def test_log_message_includes_route_type_api(self):
        """Test that API routes are tagged as 'api'"""
        # Create a mock handler
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.path = '/api/summary?foo=bar'
        handler.command = 'GET'
        handler.address_string = MagicMock(return_value='127.0.0.1')
        handler.log_date_time_string = MagicMock(return_value='24/Nov/2025:12:00:00')
        
        # Capture log output
        with patch.object(server.logger, 'info') as mock_log:
            server.DashboardRequestHandler.log_message(handler, 'test message')
            
            # Check that log was called with route_type
            mock_log.assert_called_once()
            log_message = mock_log.call_args[0][0]
            self.assertIn('[api]', log_message)
            self.assertIn('GET', log_message)
            self.assertIn('/api/summary', log_message)
    
    def test_log_message_includes_route_type_static(self):
        """Test that static routes are tagged as 'static'"""
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.path = '/index.html'
        handler.command = 'GET'
        handler.address_string = MagicMock(return_value='127.0.0.1')
        handler.log_date_time_string = MagicMock(return_value='24/Nov/2025:12:00:00')
        
        with patch.object(server.logger, 'info') as mock_log:
            server.DashboardRequestHandler.log_message(handler, 'test message')
            
            mock_log.assert_called_once()
            log_message = mock_log.call_args[0][0]
            self.assertIn('[static]', log_message)
            self.assertIn('GET', log_message)


if __name__ == '__main__':
    unittest.main()

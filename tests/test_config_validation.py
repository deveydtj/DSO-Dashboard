#!/usr/bin/env python3
"""
Tests for configuration validation functionality
Tests validate_config() function and fail-fast startup behavior
Uses only Python stdlib and unittest
"""

import unittest
import sys
import os
from unittest.mock import patch, MagicMock
import logging

# Add parent directory to path to import server module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import server


class TestValidateConfigApiToken(unittest.TestCase):
    """Test API token validation in validate_config"""
    
    def test_missing_api_token_when_mock_disabled_fails(self):
        """Test that missing API token fails validation when mock mode is off"""
        config = {
            'use_mock_data': False,
            'api_token': '',
            'poll_interval_sec': 60,
            'cache_ttl_sec': 300,
            'per_page': 100
        }
        
        result = server.validate_config(config)
        self.assertFalse(result)
    
    def test_none_api_token_when_mock_disabled_fails(self):
        """Test that None API token fails validation when mock mode is off"""
        config = {
            'use_mock_data': False,
            'api_token': None,
            'poll_interval_sec': 60,
            'cache_ttl_sec': 300,
            'per_page': 100
        }
        
        result = server.validate_config(config)
        self.assertFalse(result)
    
    def test_valid_api_token_passes(self):
        """Test that a valid API token passes validation"""
        config = {
            'use_mock_data': False,
            'api_token': 'glpat-test-token-123',
            'poll_interval_sec': 60,
            'cache_ttl_sec': 300,
            'per_page': 100
        }
        
        result = server.validate_config(config)
        self.assertTrue(result)
    
    def test_missing_api_token_skipped_when_mock_enabled(self):
        """Test that missing API token is OK when mock mode is on"""
        config = {
            'use_mock_data': True,
            'api_token': '',
            'poll_interval_sec': 60,
            'cache_ttl_sec': 300,
            'per_page': 100
        }
        
        result = server.validate_config(config)
        self.assertTrue(result)


class TestValidateConfigPollInterval(unittest.TestCase):
    """Test poll_interval_sec validation in validate_config"""
    
    def test_zero_poll_interval_fails(self):
        """Test that poll_interval_sec of 0 fails validation"""
        config = {
            'use_mock_data': True,
            'api_token': '',
            'poll_interval_sec': 0,
            'cache_ttl_sec': 300,
            'per_page': 100
        }
        
        result = server.validate_config(config)
        self.assertFalse(result)
    
    def test_negative_poll_interval_fails(self):
        """Test that negative poll_interval_sec fails validation"""
        config = {
            'use_mock_data': True,
            'api_token': '',
            'poll_interval_sec': -10,
            'cache_ttl_sec': 300,
            'per_page': 100
        }
        
        result = server.validate_config(config)
        self.assertFalse(result)
    
    def test_none_poll_interval_fails(self):
        """Test that None poll_interval_sec fails validation"""
        config = {
            'use_mock_data': True,
            'api_token': '',
            'poll_interval_sec': None,
            'cache_ttl_sec': 300,
            'per_page': 100
        }
        
        result = server.validate_config(config)
        self.assertFalse(result)
    
    def test_valid_poll_interval_passes(self):
        """Test that valid poll_interval_sec passes validation"""
        config = {
            'use_mock_data': True,
            'api_token': '',
            'poll_interval_sec': 60,
            'cache_ttl_sec': 300,
            'per_page': 100
        }
        
        result = server.validate_config(config)
        self.assertTrue(result)
    
    def test_small_poll_interval_warns(self):
        """Test that poll_interval_sec < 5 logs a warning but still passes"""
        config = {
            'use_mock_data': True,
            'api_token': '',
            'poll_interval_sec': 3,
            'cache_ttl_sec': 300,
            'per_page': 100
        }
        
        with patch.object(server.logger, 'warning') as mock_warning:
            result = server.validate_config(config)
            self.assertTrue(result)
            # Check that a warning was logged about short interval
            mock_warning.assert_called()
            warning_message = str(mock_warning.call_args)
            self.assertIn('poll_interval_sec', warning_message)


class TestValidateConfigCacheTtl(unittest.TestCase):
    """Test cache_ttl_sec validation in validate_config"""
    
    def test_negative_cache_ttl_fails(self):
        """Test that negative cache_ttl_sec fails validation"""
        config = {
            'use_mock_data': True,
            'api_token': '',
            'poll_interval_sec': 60,
            'cache_ttl_sec': -1,
            'per_page': 100
        }
        
        result = server.validate_config(config)
        self.assertFalse(result)
    
    def test_none_cache_ttl_fails(self):
        """Test that None cache_ttl_sec fails validation"""
        config = {
            'use_mock_data': True,
            'api_token': '',
            'poll_interval_sec': 60,
            'cache_ttl_sec': None,
            'per_page': 100
        }
        
        result = server.validate_config(config)
        self.assertFalse(result)
    
    def test_zero_cache_ttl_passes(self):
        """Test that cache_ttl_sec of 0 passes validation (disables caching)"""
        config = {
            'use_mock_data': True,
            'api_token': '',
            'poll_interval_sec': 60,
            'cache_ttl_sec': 0,
            'per_page': 100
        }
        
        result = server.validate_config(config)
        self.assertTrue(result)
    
    def test_valid_cache_ttl_passes(self):
        """Test that valid cache_ttl_sec passes validation"""
        config = {
            'use_mock_data': True,
            'api_token': '',
            'poll_interval_sec': 60,
            'cache_ttl_sec': 300,
            'per_page': 100
        }
        
        result = server.validate_config(config)
        self.assertTrue(result)


class TestValidateConfigPerPage(unittest.TestCase):
    """Test per_page validation in validate_config"""
    
    def test_zero_per_page_fails(self):
        """Test that per_page of 0 fails validation"""
        config = {
            'use_mock_data': True,
            'api_token': '',
            'poll_interval_sec': 60,
            'cache_ttl_sec': 300,
            'per_page': 0
        }
        
        result = server.validate_config(config)
        self.assertFalse(result)
    
    def test_negative_per_page_fails(self):
        """Test that negative per_page fails validation"""
        config = {
            'use_mock_data': True,
            'api_token': '',
            'poll_interval_sec': 60,
            'cache_ttl_sec': 300,
            'per_page': -10
        }
        
        result = server.validate_config(config)
        self.assertFalse(result)
    
    def test_none_per_page_fails(self):
        """Test that None per_page fails validation"""
        config = {
            'use_mock_data': True,
            'api_token': '',
            'poll_interval_sec': 60,
            'cache_ttl_sec': 300,
            'per_page': None
        }
        
        result = server.validate_config(config)
        self.assertFalse(result)
    
    def test_valid_per_page_passes(self):
        """Test that valid per_page passes validation"""
        config = {
            'use_mock_data': True,
            'api_token': '',
            'poll_interval_sec': 60,
            'cache_ttl_sec': 300,
            'per_page': 100
        }
        
        result = server.validate_config(config)
        self.assertTrue(result)


class TestValidateConfigMultipleErrors(unittest.TestCase):
    """Test that all errors are reported when multiple validations fail"""
    
    def test_multiple_validation_errors(self):
        """Test that validation fails when multiple fields are invalid"""
        config = {
            'use_mock_data': False,
            'api_token': '',
            'poll_interval_sec': -1,
            'cache_ttl_sec': -5,
            'per_page': 0
        }
        
        result = server.validate_config(config)
        self.assertFalse(result)
    
    def test_logs_all_errors(self):
        """Test that all validation errors are logged"""
        config = {
            'use_mock_data': False,
            'api_token': '',
            'poll_interval_sec': -1,
            'cache_ttl_sec': -5,
            'per_page': 0
        }
        
        with patch.object(server.logger, 'error') as mock_error:
            server.validate_config(config)
            # Should log at least 4 errors:
            # - api_token
            # - poll_interval_sec
            # - cache_ttl_sec
            # - per_page
            # Plus the "validation failed" message
            self.assertGreaterEqual(mock_error.call_count, 5)


class TestValidateConfigLogging(unittest.TestCase):
    """Test that validate_config logs appropriate messages"""
    
    def test_logs_success_on_valid_config(self):
        """Test that a success message is logged when config is valid"""
        config = {
            'use_mock_data': True,
            'api_token': '',
            'poll_interval_sec': 60,
            'cache_ttl_sec': 300,
            'per_page': 100
        }
        
        with patch.object(server.logger, 'info') as mock_info:
            server.validate_config(config)
            # Should log "Configuration validation passed"
            mock_info.assert_called()
            info_calls = [str(call) for call in mock_info.call_args_list]
            self.assertTrue(any('validation passed' in call for call in info_calls))
    
    def test_logs_failure_on_invalid_config(self):
        """Test that a failure message is logged when config is invalid"""
        config = {
            'use_mock_data': False,
            'api_token': '',
            'poll_interval_sec': 60,
            'cache_ttl_sec': 300,
            'per_page': 100
        }
        
        with patch.object(server.logger, 'error') as mock_error:
            server.validate_config(config)
            # Should log "Configuration validation failed"
            mock_error.assert_called()
            error_calls = [str(call) for call in mock_error.call_args_list]
            self.assertTrue(any('validation failed' in call for call in error_calls))


class TestMainWithValidation(unittest.TestCase):
    """Test main() integration with validate_config"""
    
    def test_main_exits_with_nonzero_on_invalid_config(self):
        """Test that main() returns nonzero exit code when validation fails"""
        with patch.object(server, 'load_config') as mock_load:
            mock_load.return_value = {
                'use_mock_data': False,
                'api_token': '',
                'poll_interval_sec': 60,
                'cache_ttl_sec': 300,
                'per_page': 100,
                'mock_scenario': ''
            }
            
            result = server.main()
            self.assertEqual(result, 1)
    
    def test_main_continues_on_valid_config(self):
        """Test that main() continues past validation when config is valid"""
        mock_data = {
            'summary': {'total_repositories': 0},
            'repositories': [],
            'pipelines': []
        }
        
        with patch.object(server, 'load_config') as mock_load:
            mock_load.return_value = {
                'use_mock_data': True,
                'api_token': '',
                'poll_interval_sec': 60,
                'cache_ttl_sec': 300,
                'per_page': 100,
                'mock_scenario': '',
                'port': 8080,
                'gitlab_url': 'https://gitlab.com',
                'insecure_skip_verify': False,
                'ca_bundle_path': None,
                'group_ids': [],
                'project_ids': []
            }
            
            with patch.object(server, 'load_mock_data') as mock_load_mock:
                mock_load_mock.return_value = mock_data
                
                with patch.object(server.DashboardServer, 'serve_forever') as mock_serve:
                    # Simulate KeyboardInterrupt to exit serve_forever
                    mock_serve.side_effect = KeyboardInterrupt()
                    
                    with patch.object(server.DashboardServer, 'shutdown'):
                        result = server.main()
                        # Should exit cleanly with 0
                        self.assertEqual(result, 0)


if __name__ == '__main__':
    unittest.main()

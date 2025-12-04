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

# Add parent directory to path to from backend import app as server module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend import app as server
from backend import config_loader


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
        
        # validate_config is in config_loader, so patch its logger
        with patch.object(config_loader.logger, 'warning') as mock_warning:
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
        
        # validate_config is in config_loader, so patch its logger
        with patch.object(config_loader.logger, 'error') as mock_error:
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
        
        # validate_config is in config_loader, so patch its logger
        with patch.object(config_loader.logger, 'info') as mock_info:
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
        
        # validate_config is in config_loader, so patch its logger
        with patch.object(config_loader.logger, 'error') as mock_error:
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

    def test_main_exits_with_nonzero_when_mock_data_missing(self):
        """Test that main() returns nonzero when mock data fails to load"""
        config = {
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

        with patch.object(server, 'load_config', return_value=config), \
                patch.object(server, 'load_mock_data', return_value=None), \
                patch.object(server, 'DashboardServer') as mock_server:
            result = server.main()

        self.assertEqual(result, 1)
        mock_server.assert_not_called()

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
                
                # Patch DashboardServer to avoid binding to real port
                mock_server = MagicMock()
                mock_server.serve_forever.side_effect = KeyboardInterrupt()
                
                with patch.object(server, 'DashboardServer', return_value=mock_server):
                    result = server.main()
                    # Should exit cleanly with 0
                    self.assertEqual(result, 0)


class TestValidateConfigSlo(unittest.TestCase):
    """Test SLO configuration validation in validate_config"""
    
    def _base_config(self):
        """Return a valid base config for testing"""
        return {
            'use_mock_data': True,
            'api_token': '',
            'poll_interval_sec': 60,
            'cache_ttl_sec': 300,
            'per_page': 100,
            'slo': {
                'default_branch_success_target': 0.99
            }
        }
    
    def test_valid_slo_config_passes(self):
        """Test that a valid SLO config passes validation"""
        config = self._base_config()
        result = server.validate_config(config)
        self.assertTrue(result)
    
    def test_missing_slo_section_uses_defaults(self):
        """Test that missing slo section uses DEFAULT_SLO_CONFIG defaults"""
        config = self._base_config()
        del config['slo']
        # validate_config should pass because load_config adds the defaults
        result = server.validate_config(config)
        # Missing slo is allowed - validate_config checks for dict type which None/missing passes
        self.assertTrue(result)
    
    def test_slo_target_at_lower_bound_fails(self):
        """Test that slo.default_branch_success_target of 0 fails validation"""
        config = self._base_config()
        config['slo']['default_branch_success_target'] = 0
        result = server.validate_config(config)
        self.assertFalse(result)
    
    def test_slo_target_at_upper_bound_fails(self):
        """Test that slo.default_branch_success_target of 1 fails validation"""
        config = self._base_config()
        config['slo']['default_branch_success_target'] = 1
        result = server.validate_config(config)
        self.assertFalse(result)
    
    def test_slo_target_negative_fails(self):
        """Test that negative slo.default_branch_success_target fails validation"""
        config = self._base_config()
        config['slo']['default_branch_success_target'] = -0.5
        result = server.validate_config(config)
        self.assertFalse(result)
    
    def test_slo_target_greater_than_one_fails(self):
        """Test that slo.default_branch_success_target > 1 fails validation"""
        config = self._base_config()
        config['slo']['default_branch_success_target'] = 1.5
        result = server.validate_config(config)
        self.assertFalse(result)
    
    def test_slo_target_non_numeric_fails(self):
        """Test that non-numeric slo.default_branch_success_target fails validation"""
        config = self._base_config()
        config['slo']['default_branch_success_target'] = 'invalid'
        result = server.validate_config(config)
        self.assertFalse(result)
    
    def test_slo_target_valid_values_pass(self):
        """Test that various valid SLO targets pass validation"""
        valid_targets = [0.01, 0.5, 0.9, 0.95, 0.99, 0.999, 0.9999]
        for target in valid_targets:
            with self.subTest(target=target):
                config = self._base_config()
                config['slo']['default_branch_success_target'] = target
                result = server.validate_config(config)
                self.assertTrue(result, f"Target {target} should be valid")
    
    def test_slo_not_dict_fails(self):
        """Test that non-dict slo config fails validation"""
        config = self._base_config()
        config['slo'] = 'invalid'
        result = server.validate_config(config)
        self.assertFalse(result)
    
    def test_slo_validation_logs_helpful_error(self):
        """Test that SLO validation logs a helpful error message"""
        config = self._base_config()
        config['slo']['default_branch_success_target'] = 1.5
        
        with patch.object(config_loader.logger, 'error') as mock_error:
            server.validate_config(config)
            # Check that helpful error was logged
            error_calls = [str(call) for call in mock_error.call_args_list]
            self.assertTrue(any('slo.default_branch_success_target' in call for call in error_calls))
            self.assertTrue(any('must be > 0 and < 1' in call for call in error_calls))
    
    def test_slo_target_invalid_string_fails_validation(self):
        """Test that invalid string SLO target from raw config fails validation (not silently defaulted)"""
        # This tests the fix for the issue where invalid strings like 'abc' were
        # silently converted to defaults by parse_float_config, bypassing validation
        config = self._base_config()
        config['slo']['default_branch_success_target'] = 'invalid_string'
        
        result = server.validate_config(config)
        self.assertFalse(result, "Invalid string SLO target should fail validation")
    
    def test_slo_target_invalid_string_logs_type_error(self):
        """Test that invalid string SLO target logs 'must be a number' error"""
        config = self._base_config()
        config['slo']['default_branch_success_target'] = 'abc'
        
        with patch.object(config_loader.logger, 'error') as mock_error:
            server.validate_config(config)
            error_calls = [str(call) for call in mock_error.call_args_list]
            # Should report type error, not silently accept as valid
            self.assertTrue(any('must be a number' in call for call in error_calls),
                           "Should log 'must be a number' error for string value")


if __name__ == '__main__':
    unittest.main()

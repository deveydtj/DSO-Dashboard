#!/usr/bin/env python3
"""
Tests for service latency configuration functionality
Tests loading and validation of service_latency config section
Uses only Python stdlib and unittest
"""

import unittest
import sys
import os
from unittest.mock import patch, MagicMock
import logging

# Add parent directory to path to import backend modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend import app as server
from backend import config_loader


class TestServiceLatencyConfigDefaults(unittest.TestCase):
    """Test that service_latency config section has sensible defaults"""
    
    def test_defaults_applied_when_section_missing(self):
        """Test that defaults are applied when service_latency section is missing"""
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(config_loader, 'PROJECT_ROOT', '/tmp'), \
             patch('os.path.exists', return_value=False):
            config = config_loader.load_config()
        
        self.assertIn('service_latency', config)
        self.assertEqual(config['service_latency']['enabled'], True)
        self.assertEqual(config['service_latency']['window_size'], 10)
        self.assertEqual(config['service_latency']['degradation_threshold_ratio'], 1.5)
    
    def test_defaults_applied_for_missing_keys(self):
        """Test that defaults are applied for individual missing keys"""
        mock_config = {
            'service_latency': {
                'enabled': False
            }
        }
        
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(config_loader, 'PROJECT_ROOT', '/tmp'), \
             patch('os.path.exists', return_value=True), \
             patch('builtins.open', unittest.mock.mock_open(read_data='{"service_latency": {"enabled": false}}')):
            config = config_loader.load_config()
        
        self.assertIn('service_latency', config)
        self.assertEqual(config['service_latency']['enabled'], False)
        # window_size and degradation_threshold_ratio should get defaults
        self.assertEqual(config['service_latency']['window_size'], 10)
        self.assertEqual(config['service_latency']['degradation_threshold_ratio'], 1.5)
    
    def test_config_json_values_loaded(self):
        """Test that service_latency values from config.json are loaded"""
        config_json = '{"service_latency": {"enabled": false, "window_size": 20, "degradation_threshold_ratio": 2.0}}'
        
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(config_loader, 'PROJECT_ROOT', '/tmp'), \
             patch('os.path.exists', return_value=True), \
             patch('builtins.open', unittest.mock.mock_open(read_data=config_json)):
            config = config_loader.load_config()
        
        self.assertEqual(config['service_latency']['enabled'], False)
        self.assertEqual(config['service_latency']['window_size'], 20)
        self.assertEqual(config['service_latency']['degradation_threshold_ratio'], 2.0)


class TestServiceLatencyConfigEnvVars(unittest.TestCase):
    """Test environment variable overrides for service_latency config"""
    
    def test_env_var_overrides_enabled(self):
        """Test that SERVICE_LATENCY_ENABLED env var overrides config"""
        with patch.dict(os.environ, {'SERVICE_LATENCY_ENABLED': 'false'}, clear=True), \
             patch.object(config_loader, 'PROJECT_ROOT', '/tmp'), \
             patch('os.path.exists', return_value=False):
            config = config_loader.load_config()
        
        self.assertEqual(config['service_latency']['enabled'], False)
    
    def test_env_var_overrides_window_size(self):
        """Test that SERVICE_LATENCY_WINDOW_SIZE env var overrides config"""
        with patch.dict(os.environ, {'SERVICE_LATENCY_WINDOW_SIZE': '25'}, clear=True), \
             patch.object(config_loader, 'PROJECT_ROOT', '/tmp'), \
             patch('os.path.exists', return_value=False):
            config = config_loader.load_config()
        
        self.assertEqual(config['service_latency']['window_size'], 25)
    
    def test_env_var_overrides_degradation_threshold_ratio(self):
        """Test that SERVICE_LATENCY_DEGRADATION_THRESHOLD_RATIO env var overrides config"""
        with patch.dict(os.environ, {'SERVICE_LATENCY_DEGRADATION_THRESHOLD_RATIO': '2.5'}, clear=True), \
             patch.object(config_loader, 'PROJECT_ROOT', '/tmp'), \
             patch('os.path.exists', return_value=False):
            config = config_loader.load_config()
        
        self.assertEqual(config['service_latency']['degradation_threshold_ratio'], 2.5)
    
    def test_env_vars_override_config_json(self):
        """Test that env vars take precedence over config.json values"""
        config_json = '{"service_latency": {"enabled": true, "window_size": 5, "degradation_threshold_ratio": 1.0}}'
        
        with patch.dict(os.environ, {
            'SERVICE_LATENCY_ENABLED': 'false',
            'SERVICE_LATENCY_WINDOW_SIZE': '50',
            'SERVICE_LATENCY_DEGRADATION_THRESHOLD_RATIO': '3.0'
        }, clear=True), \
             patch.object(config_loader, 'PROJECT_ROOT', '/tmp'), \
             patch('os.path.exists', return_value=True), \
             patch('builtins.open', unittest.mock.mock_open(read_data=config_json)):
            config = config_loader.load_config()
        
        self.assertEqual(config['service_latency']['enabled'], False)
        self.assertEqual(config['service_latency']['window_size'], 50)
        self.assertEqual(config['service_latency']['degradation_threshold_ratio'], 3.0)


class TestServiceLatencyConfigValidation(unittest.TestCase):
    """Test validation of service_latency config values"""
    
    def test_valid_config_passes(self):
        """Test that valid service_latency config passes validation"""
        config = {
            'use_mock_data': True,
            'api_token': '',
            'poll_interval_sec': 60,
            'cache_ttl_sec': 300,
            'per_page': 100,
            'service_latency': {
                'enabled': True,
                'window_size': 10,
                'degradation_threshold_ratio': 1.5
            }
        }
        
        result = config_loader.validate_config(config)
        self.assertTrue(result)
    
    def test_zero_window_size_fails(self):
        """Test that window_size of 0 fails validation"""
        config = {
            'use_mock_data': True,
            'api_token': '',
            'poll_interval_sec': 60,
            'cache_ttl_sec': 300,
            'per_page': 100,
            'service_latency': {
                'enabled': True,
                'window_size': 0,
                'degradation_threshold_ratio': 1.5
            }
        }
        
        result = config_loader.validate_config(config)
        self.assertFalse(result)
    
    def test_negative_window_size_fails(self):
        """Test that negative window_size fails validation"""
        config = {
            'use_mock_data': True,
            'api_token': '',
            'poll_interval_sec': 60,
            'cache_ttl_sec': 300,
            'per_page': 100,
            'service_latency': {
                'enabled': True,
                'window_size': -5,
                'degradation_threshold_ratio': 1.5
            }
        }
        
        result = config_loader.validate_config(config)
        self.assertFalse(result)
    
    def test_zero_threshold_ratio_fails(self):
        """Test that degradation_threshold_ratio of 0 fails validation"""
        config = {
            'use_mock_data': True,
            'api_token': '',
            'poll_interval_sec': 60,
            'cache_ttl_sec': 300,
            'per_page': 100,
            'service_latency': {
                'enabled': True,
                'window_size': 10,
                'degradation_threshold_ratio': 0
            }
        }
        
        result = config_loader.validate_config(config)
        self.assertFalse(result)
    
    def test_negative_threshold_ratio_fails(self):
        """Test that negative degradation_threshold_ratio fails validation"""
        config = {
            'use_mock_data': True,
            'api_token': '',
            'poll_interval_sec': 60,
            'cache_ttl_sec': 300,
            'per_page': 100,
            'service_latency': {
                'enabled': True,
                'window_size': 10,
                'degradation_threshold_ratio': -0.5
            }
        }
        
        result = config_loader.validate_config(config)
        self.assertFalse(result)
    
    def test_missing_service_latency_passes(self):
        """Test that missing service_latency section passes validation (uses defaults)"""
        config = {
            'use_mock_data': True,
            'api_token': '',
            'poll_interval_sec': 60,
            'cache_ttl_sec': 300,
            'per_page': 100
            # service_latency not present
        }
        
        result = config_loader.validate_config(config)
        self.assertTrue(result)
    
    def test_non_dict_service_latency_fails(self):
        """Test that non-dict service_latency fails validation"""
        config = {
            'use_mock_data': True,
            'api_token': '',
            'poll_interval_sec': 60,
            'cache_ttl_sec': 300,
            'per_page': 100,
            'service_latency': "not a dict"
        }
        
        result = config_loader.validate_config(config)
        self.assertFalse(result)


class TestBackgroundPollerServiceLatencyConfig(unittest.TestCase):
    """Test that BackgroundPoller receives and stores service_latency_config"""
    
    def test_poller_stores_service_latency_config(self):
        """Test that BackgroundPoller stores service_latency_config attribute"""
        mock_client = MagicMock()
        service_latency_config = {
            'enabled': True,
            'window_size': 15,
            'degradation_threshold_ratio': 2.0
        }
        
        poller = server.BackgroundPoller(
            mock_client,
            poll_interval_sec=60,
            service_latency_config=service_latency_config
        )
        
        self.assertEqual(poller.service_latency_config['enabled'], True)
        self.assertEqual(poller.service_latency_config['window_size'], 15)
        self.assertEqual(poller.service_latency_config['degradation_threshold_ratio'], 2.0)
    
    def test_poller_uses_default_when_config_none(self):
        """Test that BackgroundPoller uses defaults when service_latency_config is None"""
        mock_client = MagicMock()
        
        poller = server.BackgroundPoller(
            mock_client,
            poll_interval_sec=60,
            service_latency_config=None
        )
        
        self.assertEqual(poller.service_latency_config['enabled'], True)
        self.assertEqual(poller.service_latency_config['window_size'], 10)
        self.assertEqual(poller.service_latency_config['degradation_threshold_ratio'], 1.5)
    
    def test_poller_disabled_latency_tracking(self):
        """Test that poller respects enabled=False"""
        mock_client = MagicMock()
        service_latency_config = {
            'enabled': False,
            'window_size': 10,
            'degradation_threshold_ratio': 1.5
        }
        
        poller = server.BackgroundPoller(
            mock_client,
            poll_interval_sec=60,
            service_latency_config=service_latency_config
        )
        
        self.assertEqual(poller.service_latency_config['enabled'], False)


class TestParseFloatConfig(unittest.TestCase):
    """Test the parse_float_config helper function"""
    
    def test_valid_float_string(self):
        """Test parsing valid float from string"""
        result = config_loader.parse_float_config('1.5', 2.0, 'test')
        self.assertEqual(result, 1.5)
    
    def test_valid_float_value(self):
        """Test parsing already float value"""
        result = config_loader.parse_float_config(2.5, 1.0, 'test')
        self.assertEqual(result, 2.5)
    
    def test_valid_int_value(self):
        """Test parsing int value to float"""
        result = config_loader.parse_float_config(3, 1.0, 'test')
        self.assertEqual(result, 3.0)
    
    def test_invalid_string_returns_default(self):
        """Test that invalid string returns default"""
        result = config_loader.parse_float_config('invalid', 2.0, 'test')
        self.assertEqual(result, 2.0)
    
    def test_none_returns_default(self):
        """Test that None returns default"""
        result = config_loader.parse_float_config(None, 2.0, 'test')
        self.assertEqual(result, 2.0)


class TestParseBoolConfig(unittest.TestCase):
    """Test the parse_bool_config helper function"""
    
    def test_true_string_values(self):
        """Test parsing various true string values"""
        for value in ['true', 'True', 'TRUE', '1', 'yes', 'Yes', 'YES']:
            result = config_loader.parse_bool_config(value, False, 'test')
            self.assertTrue(result, f"Expected True for value: {value}")
    
    def test_false_string_values(self):
        """Test parsing various false string values"""
        for value in ['false', 'False', 'FALSE', '0', 'no', 'No', 'NO', '']:
            result = config_loader.parse_bool_config(value, True, 'test')
            self.assertFalse(result, f"Expected False for value: {value}")
    
    def test_bool_value(self):
        """Test that bool values are passed through"""
        self.assertTrue(config_loader.parse_bool_config(True, False, 'test'))
        self.assertFalse(config_loader.parse_bool_config(False, True, 'test'))
    
    def test_none_returns_default(self):
        """Test that None returns default"""
        self.assertTrue(config_loader.parse_bool_config(None, True, 'test'))
        self.assertFalse(config_loader.parse_bool_config(None, False, 'test'))


class TestDefaultServiceLatencyConfigConstant(unittest.TestCase):
    """Test the DEFAULT_SERVICE_LATENCY_CONFIG constant"""
    
    def test_constant_has_expected_keys(self):
        """Test that DEFAULT_SERVICE_LATENCY_CONFIG has all expected keys"""
        self.assertIn('enabled', config_loader.DEFAULT_SERVICE_LATENCY_CONFIG)
        self.assertIn('window_size', config_loader.DEFAULT_SERVICE_LATENCY_CONFIG)
        self.assertIn('degradation_threshold_ratio', config_loader.DEFAULT_SERVICE_LATENCY_CONFIG)
    
    def test_constant_has_expected_values(self):
        """Test that DEFAULT_SERVICE_LATENCY_CONFIG has expected default values"""
        self.assertEqual(config_loader.DEFAULT_SERVICE_LATENCY_CONFIG['enabled'], True)
        self.assertEqual(config_loader.DEFAULT_SERVICE_LATENCY_CONFIG['window_size'], 10)
        self.assertEqual(config_loader.DEFAULT_SERVICE_LATENCY_CONFIG['degradation_threshold_ratio'], 1.5)


if __name__ == '__main__':
    unittest.main()

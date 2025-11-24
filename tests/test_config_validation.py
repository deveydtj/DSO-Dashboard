#!/usr/bin/env python3
"""
Tests for configuration validation (PR 2)
- validate_config() function
- Fail-fast startup behavior
- Configuration error messages
"""

import unittest
import sys
import os
from unittest.mock import patch

# Add parent directory to path to import server module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import server


class TestValidateConfig(unittest.TestCase):
    """Test the validate_config() function"""
    
    def test_valid_config_in_mock_mode(self):
        """Test that validation passes in mock mode without API token"""
        config = {
            'use_mock_data': True,
            'api_token': '',
            'poll_interval_sec': 60,
            'cache_ttl_sec': 300,
            'per_page': 100
        }
        self.assertTrue(server.validate_config(config))
    
    def test_valid_config_with_token(self):
        """Test that validation passes with valid token in non-mock mode"""
        config = {
            'use_mock_data': False,
            'api_token': 'my-api-token',
            'poll_interval_sec': 60,
            'cache_ttl_sec': 300,
            'per_page': 100
        }
        self.assertTrue(server.validate_config(config))
    
    def test_invalid_missing_token_non_mock(self):
        """Test that validation fails without token in non-mock mode"""
        config = {
            'use_mock_data': False,
            'api_token': '',
            'poll_interval_sec': 60,
            'cache_ttl_sec': 300,
            'per_page': 100
        }
        self.assertFalse(server.validate_config(config))
    
    def test_invalid_poll_interval_too_low(self):
        """Test that validation fails when poll_interval_sec < MIN_POLL_INTERVAL_SEC"""
        config = {
            'use_mock_data': True,
            'api_token': '',
            'poll_interval_sec': 2,  # Below minimum of 5
            'cache_ttl_sec': 300,
            'per_page': 100
        }
        self.assertFalse(server.validate_config(config))
    
    def test_poll_interval_at_minimum(self):
        """Test that validation passes when poll_interval_sec == MIN_POLL_INTERVAL_SEC"""
        config = {
            'use_mock_data': True,
            'api_token': '',
            'poll_interval_sec': 5,  # Exactly at minimum
            'cache_ttl_sec': 300,
            'per_page': 100
        }
        self.assertTrue(server.validate_config(config))
    
    def test_invalid_per_page_zero(self):
        """Test that validation fails when per_page is 0"""
        config = {
            'use_mock_data': True,
            'api_token': '',
            'poll_interval_sec': 60,
            'cache_ttl_sec': 300,
            'per_page': 0
        }
        self.assertFalse(server.validate_config(config))
    
    def test_invalid_per_page_negative(self):
        """Test that validation fails when per_page is negative"""
        config = {
            'use_mock_data': True,
            'api_token': '',
            'poll_interval_sec': 60,
            'cache_ttl_sec': 300,
            'per_page': -10
        }
        self.assertFalse(server.validate_config(config))
    
    def test_cache_ttl_zero_valid(self):
        """Test that cache_ttl_sec = 0 is valid (clamped, not failed)"""
        config = {
            'use_mock_data': True,
            'api_token': '',
            'poll_interval_sec': 60,
            'cache_ttl_sec': 0,
            'per_page': 100
        }
        # Should pass - 0 is valid for cache TTL
        self.assertTrue(server.validate_config(config))
    
    def test_cache_ttl_negative_clamped(self):
        """Test that negative cache_ttl_sec is clamped to 0"""
        config = {
            'use_mock_data': True,
            'api_token': '',
            'poll_interval_sec': 60,
            'cache_ttl_sec': -100,
            'per_page': 100
        }
        # Validation should still pass (clamping is warning, not error)
        result = server.validate_config(config)
        self.assertTrue(result)
        # Check that value was clamped
        self.assertEqual(config['cache_ttl_sec'], 0)


class TestMinPollIntervalConstant(unittest.TestCase):
    """Test that MIN_POLL_INTERVAL_SEC constant is defined"""
    
    def test_min_poll_interval_defined(self):
        """Test MIN_POLL_INTERVAL_SEC is a reasonable value"""
        self.assertTrue(hasattr(server, 'MIN_POLL_INTERVAL_SEC'))
        self.assertIsInstance(server.MIN_POLL_INTERVAL_SEC, int)
        self.assertGreaterEqual(server.MIN_POLL_INTERVAL_SEC, 1)


if __name__ == '__main__':
    unittest.main()

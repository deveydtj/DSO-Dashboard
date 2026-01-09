#!/usr/bin/env python3
"""
Tests for pipeline failure classification configuration
Tests config parsing, validation, and env var overrides
Uses only Python stdlib and unittest
"""

import unittest
import sys
import os
from unittest.mock import patch

# Add parent directory to path to import backend module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend import app as server
from backend import config_loader


class TestPipelineFailureClassificationConfigDefaults(unittest.TestCase):
    """Test that defaults are correctly applied"""
    
    def test_default_config_structure(self):
        """Test DEFAULT_PIPELINE_FAILURE_CLASSIFICATION_CONFIG structure"""
        config = config_loader.DEFAULT_PIPELINE_FAILURE_CLASSIFICATION_CONFIG
        
        self.assertIn('enabled', config)
        self.assertIn('max_job_calls_per_poll', config)
        self.assertIsInstance(config['enabled'], bool)
        self.assertIsInstance(config['max_job_calls_per_poll'], int)
    
    def test_default_enabled_is_true(self):
        """Test that classification is enabled by default"""
        config = config_loader.DEFAULT_PIPELINE_FAILURE_CLASSIFICATION_CONFIG
        self.assertTrue(config['enabled'])
    
    def test_default_budget_is_reasonable(self):
        """Test that default budget is safe and reasonable"""
        config = config_loader.DEFAULT_PIPELINE_FAILURE_CLASSIFICATION_CONFIG
        budget = config['max_job_calls_per_poll']
        
        # Budget should be positive
        self.assertGreater(budget, 0)
        # Budget should be conservative (not too high to avoid rate limiting)
        self.assertLessEqual(budget, 100)


class TestPipelineFailureClassificationConfigLoading(unittest.TestCase):
    """Test config loading from config.json"""
    
    def test_missing_section_uses_defaults(self):
        """Test that missing pipeline_failure_classification section uses defaults"""
        with patch.object(config_loader, 'os') as mock_os:
            mock_os.path.exists.return_value = False
            mock_os.path.join = os.path.join
            mock_os.path.dirname = os.path.dirname
            mock_os.path.abspath = os.path.abspath
            mock_os.environ = {}
            
            config = config_loader.load_config()
            
            self.assertIn('pipeline_failure_classification', config)
            pfc = config['pipeline_failure_classification']
            self.assertEqual(pfc['enabled'], config_loader.DEFAULT_PIPELINE_FAILURE_CLASSIFICATION_CONFIG['enabled'])
            self.assertEqual(pfc['max_job_calls_per_poll'], config_loader.DEFAULT_PIPELINE_FAILURE_CLASSIFICATION_CONFIG['max_job_calls_per_poll'])
    
    def test_partial_section_fills_missing_with_defaults(self):
        """Test that partial section is filled with defaults for missing keys"""
        mock_config_json = {
            'gitlab_url': 'https://gitlab.com',
            'api_token': 'test',
            'pipeline_failure_classification': {
                'enabled': False
                # max_job_calls_per_poll is missing
            }
        }
        
        with patch.object(config_loader, 'os') as mock_os:
            mock_os.path.exists.return_value = True
            mock_os.path.join = os.path.join
            mock_os.path.dirname = os.path.dirname
            mock_os.path.abspath = os.path.abspath
            mock_os.environ = {}
            
            with patch('builtins.open', create=True) as mock_open:
                import json
                mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(mock_config_json)
                
                config = config_loader.load_config()
                
                pfc = config['pipeline_failure_classification']
                self.assertEqual(pfc['enabled'], False)  # From config
                self.assertEqual(pfc['max_job_calls_per_poll'], config_loader.DEFAULT_PIPELINE_FAILURE_CLASSIFICATION_CONFIG['max_job_calls_per_poll'])  # Default


class TestPipelineFailureClassificationConfigEnvVars(unittest.TestCase):
    """Test environment variable overrides"""
    
    def test_env_var_enabled_override(self):
        """Test PIPELINE_FAILURE_CLASSIFICATION_ENABLED env var override"""
        mock_config_json = {
            'gitlab_url': 'https://gitlab.com',
            'api_token': 'test',
            'pipeline_failure_classification': {
                'enabled': True,
                'max_job_calls_per_poll': 20
            }
        }
        
        with patch.object(config_loader, 'os') as mock_os:
            mock_os.path.exists.return_value = True
            mock_os.path.join = os.path.join
            mock_os.path.dirname = os.path.dirname
            mock_os.path.abspath = os.path.abspath
            mock_os.environ = {
                'PIPELINE_FAILURE_CLASSIFICATION_ENABLED': 'false'
            }
            
            with patch('builtins.open', create=True) as mock_open:
                import json
                mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(mock_config_json)
                
                config = config_loader.load_config()
                
                # Env var should override config.json
                self.assertEqual(config['pipeline_failure_classification']['enabled'], False)
    
    def test_env_var_max_job_calls_override(self):
        """Test PIPELINE_FAILURE_CLASSIFICATION_MAX_JOB_CALLS_PER_POLL env var override"""
        mock_config_json = {
            'gitlab_url': 'https://gitlab.com',
            'api_token': 'test',
            'pipeline_failure_classification': {
                'enabled': True,
                'max_job_calls_per_poll': 20
            }
        }
        
        with patch.object(config_loader, 'os') as mock_os:
            mock_os.path.exists.return_value = True
            mock_os.path.join = os.path.join
            mock_os.path.dirname = os.path.dirname
            mock_os.path.abspath = os.path.abspath
            mock_os.environ = {
                'PIPELINE_FAILURE_CLASSIFICATION_MAX_JOB_CALLS_PER_POLL': '50'
            }
            
            with patch('builtins.open', create=True) as mock_open:
                import json
                mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(mock_config_json)
                
                config = config_loader.load_config()
                
                # Env var should override config.json
                self.assertEqual(config['pipeline_failure_classification']['max_job_calls_per_poll'], 50)
    
    def test_invalid_env_var_uses_default(self):
        """Test that invalid env var falls back to default"""
        with patch.object(config_loader, 'os') as mock_os:
            mock_os.path.exists.return_value = False
            mock_os.path.join = os.path.join
            mock_os.path.dirname = os.path.dirname
            mock_os.path.abspath = os.path.abspath
            mock_os.environ = {
                'PIPELINE_FAILURE_CLASSIFICATION_MAX_JOB_CALLS_PER_POLL': 'invalid'
            }
            
            with patch.object(config_loader.logger, 'warning'):
                config = config_loader.load_config()
                
                # Should use default when env var is invalid
                self.assertEqual(
                    config['pipeline_failure_classification']['max_job_calls_per_poll'],
                    config_loader.DEFAULT_PIPELINE_FAILURE_CLASSIFICATION_CONFIG['max_job_calls_per_poll']
                )


class TestPipelineFailureClassificationConfigLogging(unittest.TestCase):
    """Test that config is logged at startup"""
    
    def test_config_logged_at_startup(self):
        """Test that pipeline_failure_classification config is logged"""
        with patch.object(config_loader, 'os') as mock_os:
            mock_os.path.exists.return_value = False
            mock_os.path.join = os.path.join
            mock_os.path.dirname = os.path.dirname
            mock_os.path.abspath = os.path.abspath
            mock_os.environ = {}
            
            with patch.object(config_loader.logger, 'info') as mock_info:
                config = config_loader.load_config()
                
                # Check that a log message was made about pipeline_failure_classification
                info_calls = [str(call) for call in mock_info.call_args_list]
                has_pfc_log = any('Pipeline failure classification' in call for call in info_calls)
                self.assertTrue(has_pfc_log, "Config should log pipeline_failure_classification settings")


class TestPipelineFailureClassificationConfigTypeSafety(unittest.TestCase):
    """Test type safety and defensive coding"""
    
    def test_non_dict_config_uses_defaults(self):
        """Test that non-dict pipeline_failure_classification section uses defaults"""
        mock_config_json = {
            'gitlab_url': 'https://gitlab.com',
            'api_token': 'test',
            'pipeline_failure_classification': 'invalid'  # Not a dict
        }
        
        with patch.object(config_loader, 'os') as mock_os:
            mock_os.path.exists.return_value = True
            mock_os.path.join = os.path.join
            mock_os.path.dirname = os.path.dirname
            mock_os.path.abspath = os.path.abspath
            mock_os.environ = {}
            
            with patch('builtins.open', create=True) as mock_open:
                import json
                mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(mock_config_json)
                
                with patch.object(config_loader.logger, 'warning'):
                    config = config_loader.load_config()
                    
                    # Should use defaults when config is invalid
                    pfc = config['pipeline_failure_classification']
                    self.assertEqual(pfc['enabled'], config_loader.DEFAULT_PIPELINE_FAILURE_CLASSIFICATION_CONFIG['enabled'])
                    self.assertEqual(pfc['max_job_calls_per_poll'], config_loader.DEFAULT_PIPELINE_FAILURE_CLASSIFICATION_CONFIG['max_job_calls_per_poll'])


if __name__ == '__main__':
    unittest.main()

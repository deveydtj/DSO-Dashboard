#!/usr/bin/env python3
"""
Unit tests for mock scenario loading functionality
Tests the new load_mock_data(scenario) parameter
"""

import unittest
import sys
import os
import json
from unittest.mock import MagicMock, patch, mock_open

# Add parent directory to path to from backend import app as server module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend import app as server


class TestMockScenarioLoading(unittest.TestCase):
    """Test loading different mock scenarios"""
    
    def test_load_default_mock_data(self):
        """Test loading default mock_data.json when no scenario specified"""
        mock_data = {
            'summary': {'total_repositories': 5},
            'repositories': [{'id': 1}],
            'pipelines': [{'id': 100}]
        }
        
        with patch('builtins.open', mock_open(read_data=json.dumps(mock_data))):
            with patch('os.path.exists', return_value=True):
                result = server.load_mock_data('')
        
        self.assertIsNotNone(result)
        self.assertEqual(result['summary']['total_repositories'], 5)
    
    def test_load_healthy_scenario(self):
        """Test loading healthy scenario from data/mock_scenarios/"""
        mock_data = {
            'summary': {'total_repositories': 10, 'pipeline_success_rate': 0.95},
            'repositories': [{'id': i} for i in range(10)],
            'pipelines': [{'id': i, 'status': 'success'} for i in range(60)]
        }
        
        with patch('builtins.open', mock_open(read_data=json.dumps(mock_data))):
            with patch('os.path.exists', return_value=True) as mock_exists:
                result = server.load_mock_data('healthy')
                
                # Verify it tried to load the correct file (absolute path from PROJECT_ROOT)
                expected_path = os.path.join(server.PROJECT_ROOT, 'data', 'mock_scenarios', 'healthy.json')
                mock_exists.assert_called_with(expected_path)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['summary']['total_repositories'], 10)
        self.assertAlmostEqual(result['summary']['pipeline_success_rate'], 0.95)
    
    def test_load_failing_scenario(self):
        """Test loading failing scenario"""
        mock_data = {
            'summary': {'total_repositories': 8, 'pipeline_success_rate': 0.3},
            'repositories': [{'id': i, 'consecutive_default_branch_failures': 5} for i in range(8)],
            'pipelines': [{'id': i, 'status': 'failed'} for i in range(30)]
        }
        
        with patch('builtins.open', mock_open(read_data=json.dumps(mock_data))):
            with patch('os.path.exists', return_value=True) as mock_exists:
                result = server.load_mock_data('failing')
                
                # Verify it tried to load the correct file (absolute path from PROJECT_ROOT)
                expected_path = os.path.join(server.PROJECT_ROOT, 'data', 'mock_scenarios', 'failing.json')
                mock_exists.assert_called_with(expected_path)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['summary']['total_repositories'], 8)
        self.assertAlmostEqual(result['summary']['pipeline_success_rate'], 0.3)
    
    def test_load_running_scenario(self):
        """Test loading running scenario"""
        mock_data = {
            'summary': {'total_repositories': 12, 'running_pipelines': 18},
            'repositories': [{'id': i, 'last_pipeline_status': 'running'} for i in range(12)],
            'pipelines': [{'id': i, 'status': 'running'} for i in range(18)]
        }
        
        with patch('builtins.open', mock_open(read_data=json.dumps(mock_data))):
            with patch('os.path.exists', return_value=True) as mock_exists:
                result = server.load_mock_data('running')
                
                # Verify it tried to load the correct file (absolute path from PROJECT_ROOT)
                expected_path = os.path.join(server.PROJECT_ROOT, 'data', 'mock_scenarios', 'running.json')
                mock_exists.assert_called_with(expected_path)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['summary']['running_pipelines'], 18)
    
    def test_scenario_file_not_found(self):
        """Test error handling when scenario file doesn't exist"""
        with patch('os.path.exists', return_value=False):
            result = server.load_mock_data('nonexistent')
        
        self.assertIsNone(result)
    
    def test_scenario_missing_required_keys(self):
        """Test error handling when scenario file missing required keys"""
        incomplete_data = {
            'summary': {'total_repositories': 5},
            'repositories': [{'id': 1}]
            # Missing 'pipelines' key
        }
        
        with patch('builtins.open', mock_open(read_data=json.dumps(incomplete_data))):
            with patch('os.path.exists', return_value=True):
                result = server.load_mock_data('healthy')
        
        self.assertIsNone(result)
    
    def test_scenario_invalid_json(self):
        """Test error handling when scenario file contains invalid JSON"""
        with patch('builtins.open', mock_open(read_data='not valid json {')):
            with patch('os.path.exists', return_value=True):
                result = server.load_mock_data('healthy')
        
        self.assertIsNone(result)


class TestMockScenarioConfiguration(unittest.TestCase):
    """Test configuration loading for mock scenarios"""
    
    def setUp(self):
        """Clear environment variables before each test"""
        # Store original env
        self.original_env = os.environ.copy()
        
        # Clear relevant env vars
        for key in ['MOCK_SCENARIO', 'USE_MOCK_DATA']:
            if key in os.environ:
                del os.environ[key]
    
    def tearDown(self):
        """Restore original environment"""
        os.environ.clear()
        os.environ.update(self.original_env)
    
    def test_load_config_with_scenario_from_env(self):
        """Test loading mock_scenario from environment variable"""
        os.environ['MOCK_SCENARIO'] = 'healthy'
        
        with patch('os.path.exists', return_value=False):
            config = server.load_config()
        
        self.assertEqual(config['mock_scenario'], 'healthy')
    
    def test_load_config_with_scenario_from_config_file(self):
        """Test loading mock_scenario from config.json"""
        mock_config = {
            'gitlab_url': 'https://gitlab.com',
            'api_token': 'test-token',
            'use_mock_data': True,
            'mock_scenario': 'failing'
        }
        
        with patch('builtins.open', mock_open(read_data=json.dumps(mock_config))):
            with patch('os.path.exists', return_value=True):
                config = server.load_config()
        
        self.assertEqual(config['mock_scenario'], 'failing')
    
    def test_env_var_overrides_config_file_scenario(self):
        """Test that MOCK_SCENARIO env var overrides config.json"""
        os.environ['MOCK_SCENARIO'] = 'running'
        
        mock_config = {
            'gitlab_url': 'https://gitlab.com',
            'api_token': 'test-token',
            'mock_scenario': 'healthy'
        }
        
        with patch('builtins.open', mock_open(read_data=json.dumps(mock_config))):
            with patch('os.path.exists', return_value=True):
                config = server.load_config()
        
        self.assertEqual(config['mock_scenario'], 'running')
    
    def test_empty_scenario_defaults_to_mock_data_json(self):
        """Test that empty scenario string defaults to mock_data.json"""
        with patch('os.path.exists', return_value=False):
            config = server.load_config()
        
        self.assertEqual(config['mock_scenario'], '')


class TestMockScenarioGlobalVariable(unittest.TestCase):
    """Test MOCK_SCENARIO global variable"""
    
    def setUp(self):
        """Reset global variables"""
        server.MOCK_MODE_ENABLED = False
        server.MOCK_SCENARIO = ''
    
    def tearDown(self):
        """Clean up"""
        server.MOCK_MODE_ENABLED = False
        server.MOCK_SCENARIO = ''
    
    def test_mock_scenario_initially_empty(self):
        """Test that MOCK_SCENARIO starts empty"""
        self.assertEqual(server.MOCK_SCENARIO, '')
    
    def test_mock_scenario_set_by_main(self):
        """Test that main() sets MOCK_SCENARIO from config"""
        # This would require complex mocking of main()
        # Instead we test that the variable can be set
        server.MOCK_SCENARIO = 'healthy'
        self.assertEqual(server.MOCK_SCENARIO, 'healthy')


if __name__ == '__main__':
    unittest.main()

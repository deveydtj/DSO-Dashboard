#!/usr/bin/env python3
"""
Tests for pipeline duration hydration functionality
"""

import unittest
import sys
import os
from unittest.mock import MagicMock, patch

# Add parent directory to path to import backend modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend import app as server
from backend.gitlab_client import GitLabAPIClient
from backend.config_loader import DEFAULT_DURATION_HYDRATION_CONFIG


class TestGetPipelineMethod(unittest.TestCase):
    """Test GitLabAPIClient.get_pipeline method"""
    
    def test_get_pipeline_success(self):
        """Test get_pipeline returns pipeline detail data"""
        client = GitLabAPIClient('https://gitlab.com', 'test-token')
        
        mock_response = {
            'data': {
                'id': 123,
                'project_id': 456,
                'status': 'success',
                'duration': 300,
                'ref': 'main'
            }
        }
        
        with patch.object(client, 'gitlab_request', return_value=mock_response) as mock_request:
            result = client.get_pipeline(456, 123)
            
            mock_request.assert_called_once_with('projects/456/pipelines/123')
            self.assertEqual(result['id'], 123)
            self.assertEqual(result['duration'], 300)
    
    def test_get_pipeline_api_error(self):
        """Test get_pipeline returns None on API error"""
        client = GitLabAPIClient('https://gitlab.com', 'test-token')
        
        with patch.object(client, 'gitlab_request', return_value=None) as mock_request:
            result = client.get_pipeline(456, 123)
            
            mock_request.assert_called_once()
            self.assertIsNone(result)
    
    def test_get_pipeline_empty_response(self):
        """Test get_pipeline returns None when data is missing"""
        client = GitLabAPIClient('https://gitlab.com', 'test-token')
        
        with patch.object(client, 'gitlab_request', return_value={'data': None}):
            result = client.get_pipeline(456, 123)
            self.assertIsNone(result)


class TestDurationHydrationConfig(unittest.TestCase):
    """Test duration hydration configuration loading"""
    
    def test_default_config_values(self):
        """Test default duration hydration config values"""
        self.assertEqual(DEFAULT_DURATION_HYDRATION_CONFIG['global_cap'], 200)
        self.assertEqual(DEFAULT_DURATION_HYDRATION_CONFIG['per_project_cap'], 2)
    
    @patch.dict(os.environ, {
        'DURATION_HYDRATION_GLOBAL_CAP': '100',
        'DURATION_HYDRATION_PER_PROJECT_CAP': '5',
        'USE_MOCK_DATA': 'true'  # Required to skip API token validation
    }, clear=False)
    def test_env_vars_override_config(self):
        """Test environment variables override config.json values"""
        from backend.config_loader import load_config
        
        config = load_config()
        
        self.assertEqual(config['duration_hydration']['global_cap'], 100)
        self.assertEqual(config['duration_hydration']['per_project_cap'], 5)


class TestHydratePipelineDurations(unittest.TestCase):
    """Test BackgroundPoller._hydrate_pipeline_durations method"""
    
    def setUp(self):
        """Create a poller with mocked GitLab client"""
        self.mock_client = MagicMock(spec=GitLabAPIClient)
        self.poller = server.BackgroundPoller(
            gitlab_client=self.mock_client,
            poll_interval_sec=60,
            duration_hydration_config={'global_cap': 10, 'per_project_cap': 2}
        )
    
    def test_hydrates_pipelines_without_duration(self):
        """Test that pipelines without duration get hydrated"""
        # Pipeline with no duration
        all_pipelines = [
            {'id': 1, 'project_id': 100, 'ref': 'main', 'status': 'success', 'duration': None},
            {'id': 2, 'project_id': 100, 'ref': 'main', 'status': 'success', 'duration': 120}  # Already has duration
        ]
        per_project = {100: all_pipelines}
        projects = [{'id': 100, 'default_branch': 'main'}]
        
        # Mock get_pipeline to return duration
        self.mock_client.get_pipeline.return_value = {'id': 1, 'duration': 300}
        
        stats = self.poller._hydrate_pipeline_durations(all_pipelines, per_project, projects, 'test-poll')
        
        # Should have called get_pipeline for the pipeline without duration
        self.mock_client.get_pipeline.assert_called_once_with(100, 1)
        
        # Pipeline should now have duration
        self.assertEqual(all_pipelines[0]['duration'], 300)
        
        # Pipeline with existing duration should be unchanged
        self.assertEqual(all_pipelines[1]['duration'], 120)
        
        # Stats should reflect one hydrated
        self.assertEqual(stats['hydrated'], 1)
        self.assertEqual(stats['skipped_error'], 0)
    
    def test_respects_global_cap(self):
        """Test that hydration respects global cap"""
        # Create more pipelines than global_cap (10)
        all_pipelines = [
            {'id': i, 'project_id': 100, 'ref': 'main', 'status': 'success', 'duration': None, 'created_at': f'2024-01-01T{i:02d}:00:00'}
            for i in range(15)
        ]
        per_project = {100: all_pipelines}
        projects = [{'id': 100, 'default_branch': 'main'}]
        
        self.mock_client.get_pipeline.return_value = {'id': 1, 'duration': 300}
        
        self.poller._hydrate_pipeline_durations(all_pipelines, per_project, projects, 'test-poll')
        
        # Should not have called get_pipeline more than global_cap times
        self.assertLessEqual(self.mock_client.get_pipeline.call_count, 10)
    
    def test_skips_pipelines_with_existing_duration(self):
        """Test that pipelines with duration are not hydrated"""
        all_pipelines = [
            {'id': 1, 'project_id': 100, 'ref': 'main', 'status': 'success', 'duration': 120}
        ]
        per_project = {100: all_pipelines}
        projects = [{'id': 100, 'default_branch': 'main'}]
        
        stats = self.poller._hydrate_pipeline_durations(all_pipelines, per_project, projects, 'test-poll')
        
        # Should not call get_pipeline at all
        self.mock_client.get_pipeline.assert_not_called()
        
        # Stats should show no hydration
        self.assertEqual(stats['hydrated'], 0)
    
    def test_handles_api_errors_gracefully(self):
        """Test that API errors don't break hydration"""
        all_pipelines = [
            {'id': 1, 'project_id': 100, 'ref': 'main', 'status': 'success', 'duration': None},
            {'id': 2, 'project_id': 100, 'ref': 'main', 'status': 'success', 'duration': None}
        ]
        per_project = {100: all_pipelines}
        projects = [{'id': 100, 'default_branch': 'main'}]
        
        # Mock get_pipeline: return None for pipeline 1, success for pipeline 2
        def mock_get_pipeline(project_id, pipeline_id):
            if pipeline_id == 1:
                return None  # Simulate error
            return {'id': pipeline_id, 'duration': 200}
        
        self.mock_client.get_pipeline.side_effect = mock_get_pipeline
        
        stats = self.poller._hydrate_pipeline_durations(all_pipelines, per_project, projects, 'test-poll')
        
        # Pipeline 1 should still have no duration (error)
        self.assertIsNone(all_pipelines[0]['duration'])
        
        # Pipeline 2 should have duration
        self.assertEqual(all_pipelines[1]['duration'], 200)
        
        # Stats should reflect one error and one success
        self.assertEqual(stats['hydrated'], 1)
        self.assertEqual(stats['skipped_error'], 1)
    
    def test_hydrates_default_branch_pipelines_for_tiles(self):
        """Test that default branch pipelines are prioritized for hydration"""
        all_pipelines = [
            {'id': 1, 'project_id': 100, 'ref': 'feature/test', 'status': 'success', 'duration': None, 'created_at': '2024-01-01T02:00:00'},
            {'id': 2, 'project_id': 100, 'ref': 'main', 'status': 'success', 'duration': None, 'created_at': '2024-01-01T01:00:00'}
        ]
        per_project = {100: all_pipelines}
        projects = [{'id': 100, 'default_branch': 'main'}]
        
        self.mock_client.get_pipeline.return_value = {'id': 2, 'duration': 300}
        
        self.poller._hydrate_pipeline_durations(all_pipelines, per_project, projects, 'test-poll')
        
        # Should have hydrated the default branch pipeline
        # Both pipelines are in the "all_pipelines" list so both could be hydrated
        # But default branch pipelines get priority for per-project cap
        calls = [call[0] for call in self.mock_client.get_pipeline.call_args_list]
        # At least the main branch pipeline (id=2) should be hydrated
        self.assertTrue(any(call == (100, 2) for call in calls))
    
    def test_handles_empty_pipelines(self):
        """Test that empty pipeline list is handled gracefully"""
        stats = self.poller._hydrate_pipeline_durations([], {}, [], 'test-poll')
        
        self.mock_client.get_pipeline.assert_not_called()
        self.assertEqual(stats['hydrated'], 0)
        self.assertEqual(stats['skipped_error'], 0)


class TestBackgroundPollerWithHydration(unittest.TestCase):
    """Test BackgroundPoller integration with duration hydration"""
    
    def test_poller_accepts_duration_hydration_config(self):
        """Test BackgroundPoller initializes with duration_hydration_config"""
        mock_client = MagicMock(spec=GitLabAPIClient)
        config = {'global_cap': 50, 'per_project_cap': 1}
        
        poller = server.BackgroundPoller(
            gitlab_client=mock_client,
            poll_interval_sec=60,
            duration_hydration_config=config
        )
        
        self.assertEqual(poller.duration_hydration_config['global_cap'], 50)
        self.assertEqual(poller.duration_hydration_config['per_project_cap'], 1)
    
    def test_poller_uses_defaults_when_config_not_provided(self):
        """Test BackgroundPoller uses defaults when config is None"""
        mock_client = MagicMock(spec=GitLabAPIClient)
        
        poller = server.BackgroundPoller(
            gitlab_client=mock_client,
            poll_interval_sec=60,
            duration_hydration_config=None
        )
        
        self.assertEqual(poller.duration_hydration_config['global_cap'], DEFAULT_DURATION_HYDRATION_CONFIG['global_cap'])
        self.assertEqual(poller.duration_hydration_config['per_project_cap'], DEFAULT_DURATION_HYDRATION_CONFIG['per_project_cap'])


if __name__ == '__main__':
    unittest.main()

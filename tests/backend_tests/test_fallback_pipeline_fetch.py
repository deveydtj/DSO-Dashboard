"""Integration tests for default-branch pipeline fallback fetch logic in BackgroundPoller."""
import unittest
from unittest.mock import MagicMock, call
from backend.app import BackgroundPoller
from backend.gitlab_client import GitLabAPIClient


class TestDefaultBranchPipelineFallbackFetch(unittest.TestCase):
    """Test the fallback fetch logic in _fetch_pipelines when default-branch pipelines are missing."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock GitLab client
        self.mock_client = MagicMock(spec=GitLabAPIClient)
        
        # Create a BackgroundPoller instance with mock client
        self.poller = BackgroundPoller(
            gitlab_client=self.mock_client,
            poll_interval_sec=60,
            group_ids=[123],  # Use a configured scope to trigger the specific code path
            project_ids=None,
            external_services=[],
            service_latency_config=None,
            slo_config=None,
            duration_hydration_config=None
        )

    def test_fallback_fetch_when_only_feature_branches(self):
        """
        Test that fallback fetch is triggered when initial fetch returns only feature branch pipelines.
        
        Scenario:
        - Initial fetch returns 10 feature branch pipelines
        - No default-branch pipeline in initial fetch
        - Fallback fetch should be triggered with ref='main'
        - Fallback returns 1 default-branch pipeline
        - Pipeline should be added to per_project_pipelines and all_pipelines
        """
        projects = [
            {
                'id': 456,
                'name': 'feature-heavy-project',
                'path_with_namespace': 'org/feature-heavy-project',
                'default_branch': 'main'
            }
        ]
        
        # Initial fetch returns only feature branch pipelines
        feature_pipelines = [
            {
                'id': i,
                'status': 'success',
                'ref': f'feature/branch-{i}',
                'created_at': f'2024-01-20T10:{50-i:02d}:00.000Z'
            }
            for i in range(10)
        ]
        
        # Fallback fetch returns default-branch pipeline
        default_branch_pipeline = [
            {
                'id': 100,
                'status': 'failed',
                'ref': 'main',
                'created_at': '2024-01-20T10:30:00.000Z',
                'updated_at': '2024-01-20T10:35:00.000Z',
                'duration': 200
            }
        ]
        
        # Mock get_projects to return our test project
        self.poller.gitlab_client.get_projects.return_value = projects
        
        # Mock get_pipelines to return different results based on parameters
        def mock_get_pipelines(project_id, per_page=None, ref=None):
            if ref == 'main':
                # Fallback fetch with ref filter
                return default_branch_pipeline
            else:
                # Initial fetch without ref filter
                return feature_pipelines
        
        self.poller.gitlab_client.get_pipelines.side_effect = mock_get_pipelines
        
        # Call _fetch_pipelines
        result = self.poller._fetch_pipelines(projects, poll_id='test-1')
        
        # Verify get_pipelines was called twice: once for initial fetch, once for fallback
        self.assertEqual(self.poller.gitlab_client.get_pipelines.call_count, 2)
        
        # Verify first call was without ref filter
        first_call = self.poller.gitlab_client.get_pipelines.call_args_list[0]
        self.assertEqual(first_call, call(456, per_page=10))
        
        # Verify second call was with ref='main' and per_page=PIPELINES_PER_PROJECT
        second_call = self.poller.gitlab_client.get_pipelines.call_args_list[1]
        self.assertEqual(second_call, call(456, per_page=10, ref='main'))
        
        # Verify result contains both feature pipelines and default-branch pipeline
        self.assertIsNotNone(result)
        all_pipelines = result['all_pipelines']
        per_project = result['per_project']
        
        # Should have 11 pipelines total (10 feature + 1 default-branch)
        self.assertEqual(len(all_pipelines), 11)
        
        # Should have 11 pipelines in per-project dict
        self.assertEqual(len(per_project[456]), 11)
        
        # Verify default-branch pipeline was added with correct project info
        default_pipeline_in_result = [p for p in all_pipelines if p['ref'] == 'main']
        self.assertEqual(len(default_pipeline_in_result), 1)
        self.assertEqual(default_pipeline_in_result[0]['project_name'], 'feature-heavy-project')
        self.assertEqual(default_pipeline_in_result[0]['project_id'], 456)

    def test_no_fallback_when_default_branch_in_initial_fetch(self):
        """
        Test that fallback fetch is NOT triggered when default-branch pipeline is in initial fetch.
        
        Scenario:
        - Initial fetch returns 9 feature pipelines + 1 default-branch pipeline
        - Default-branch pipeline is already present
        - No fallback fetch should be triggered
        """
        projects = [
            {
                'id': 789,
                'name': 'balanced-project',
                'path_with_namespace': 'org/balanced-project',
                'default_branch': 'main'
            }
        ]
        
        # Initial fetch includes default-branch pipeline
        mixed_pipelines = [
            # 9 feature branch pipelines
            *[
                {
                    'id': i,
                    'status': 'success',
                    'ref': f'feature/branch-{i}',
                    'created_at': f'2024-01-20T10:{50-i:02d}:00.000Z'
                }
                for i in range(9)
            ],
            # 1 default-branch pipeline
            {
                'id': 100,
                'status': 'success',
                'ref': 'main',
                'created_at': '2024-01-20T10:40:00.000Z'
            }
        ]
        
        self.poller.gitlab_client.get_projects.return_value = projects
        self.poller.gitlab_client.get_pipelines.return_value = mixed_pipelines
        
        # Call _fetch_pipelines
        result = self.poller._fetch_pipelines(projects, poll_id='test-2')
        
        # Verify get_pipelines was called only once (no fallback)
        self.assertEqual(self.poller.gitlab_client.get_pipelines.call_count, 1)
        
        # Verify the call was without ref filter
        self.poller.gitlab_client.get_pipelines.assert_called_once_with(789, per_page=10)
        
        # Verify result contains all 10 pipelines
        self.assertIsNotNone(result)
        self.assertEqual(len(result['all_pipelines']), 10)
        self.assertEqual(len(result['per_project'][789]), 10)

    def test_fallback_handles_api_error_gracefully(self):
        """
        Test that API errors in fallback fetch are handled gracefully without failing entire poll.
        
        Scenario:
        - Initial fetch returns only feature pipelines
        - Fallback fetch returns None (API error)
        - Should log warning but not fail the entire poll
        - Should return feature pipelines successfully
        """
        projects = [
            {
                'id': 111,
                'name': 'error-project',
                'path_with_namespace': 'org/error-project',
                'default_branch': 'main'
            }
        ]
        
        feature_pipelines = [
            {
                'id': i,
                'status': 'success',
                'ref': f'feature/branch-{i}',
                'created_at': f'2024-01-20T10:{50-i:02d}:00.000Z'
            }
            for i in range(5)
        ]
        
        self.poller.gitlab_client.get_projects.return_value = projects
        
        # Mock to return feature pipelines initially, then None for fallback
        def mock_get_pipelines(project_id, per_page=None, ref=None):
            if ref == 'main':
                return None  # API error on fallback
            else:
                return feature_pipelines
        
        self.poller.gitlab_client.get_pipelines.side_effect = mock_get_pipelines
        
        # Call _fetch_pipelines - should not raise exception
        result = self.poller._fetch_pipelines(projects, poll_id='test-3')
        
        # Verify both calls were made
        self.assertEqual(self.poller.gitlab_client.get_pipelines.call_count, 2)
        
        # Verify result is successful despite fallback error
        self.assertIsNotNone(result)
        
        # Should have only feature pipelines (fallback failed)
        self.assertEqual(len(result['all_pipelines']), 5)
        self.assertEqual(len(result['per_project'][111]), 5)

    def test_fallback_with_empty_result(self):
        """
        Test that empty fallback result (no pipelines on default branch) is handled correctly.
        
        Scenario:
        - Initial fetch returns only feature pipelines
        - Fallback fetch returns empty list (no default-branch pipelines exist)
        - Should not fail, just return feature pipelines
        """
        projects = [
            {
                'id': 222,
                'name': 'no-default-pipeline-project',
                'path_with_namespace': 'org/no-default-pipeline-project',
                'default_branch': 'main'
            }
        ]
        
        feature_pipelines = [
            {
                'id': i,
                'status': 'success',
                'ref': f'feature/branch-{i}',
                'created_at': f'2024-01-20T10:{50-i:02d}:00.000Z'
            }
            for i in range(3)
        ]
        
        self.poller.gitlab_client.get_projects.return_value = projects
        
        # Mock to return feature pipelines initially, then empty list for fallback
        def mock_get_pipelines(project_id, per_page=None, ref=None):
            if ref == 'main':
                return []  # No default-branch pipelines
            else:
                return feature_pipelines
        
        self.poller.gitlab_client.get_pipelines.side_effect = mock_get_pipelines
        
        # Call _fetch_pipelines
        result = self.poller._fetch_pipelines(projects, poll_id='test-4')
        
        # Verify both calls were made
        self.assertEqual(self.poller.gitlab_client.get_pipelines.call_count, 2)
        
        # Verify result contains only feature pipelines
        self.assertIsNotNone(result)
        self.assertEqual(len(result['all_pipelines']), 3)
        self.assertEqual(len(result['per_project'][222]), 3)

    def test_fallback_with_runner_failure(self):
        """
        Test the exact scenario from the issue: runner failure on default branch.
        
        Scenario:
        - Initial fetch returns feature pipelines
        - Fallback fetch returns failed pipeline with runner_system_failure
        - Should add the failed pipeline to collections
        """
        projects = [
            {
                'id': 333,
                'name': 'runner-issue-project',
                'path_with_namespace': 'org/runner-issue-project',
                'default_branch': 'main'
            }
        ]
        
        feature_pipelines = [
            {
                'id': i,
                'status': 'success',
                'ref': f'feature/branch-{i}',
                'created_at': f'2024-01-20T11:{55-i:02d}:00.000Z'
            }
            for i in range(10)
        ]
        
        runner_failure_pipeline = [
            {
                'id': 999,
                'status': 'failed',
                'ref': 'main',
                'failure_reason': 'runner_system_failure',
                'created_at': '2024-01-20T11:45:00.000Z',
                'updated_at': '2024-01-20T11:50:00.000Z',
                'duration': 50
            }
        ]
        
        self.poller.gitlab_client.get_projects.return_value = projects
        
        def mock_get_pipelines(project_id, per_page=None, ref=None):
            if ref == 'main':
                return runner_failure_pipeline
            else:
                return feature_pipelines
        
        self.poller.gitlab_client.get_pipelines.side_effect = mock_get_pipelines
        
        # Call _fetch_pipelines
        result = self.poller._fetch_pipelines(projects, poll_id='test-5')
        
        # Verify fallback was triggered
        self.assertEqual(self.poller.gitlab_client.get_pipelines.call_count, 2)
        
        # Verify runner failure pipeline is in results
        self.assertIsNotNone(result)
        all_pipelines = result['all_pipelines']
        
        # Should have 11 pipelines (10 feature + 1 failed main)
        self.assertEqual(len(all_pipelines), 11)
        
        # Find the failed pipeline
        failed_pipeline = [p for p in all_pipelines if p['ref'] == 'main']
        self.assertEqual(len(failed_pipeline), 1)
        self.assertEqual(failed_pipeline[0]['status'], 'failed')
        self.assertEqual(failed_pipeline[0]['failure_reason'], 'runner_system_failure')
        self.assertEqual(failed_pipeline[0]['project_name'], 'runner-issue-project')


if __name__ == '__main__':
    unittest.main()

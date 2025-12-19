"""Tests for sparkline rendering with multiple default-branch pipelines.

This test validates the fix for the issue where repo default-branch sparklines
often render only 1 bar due to insufficient default-branch pipeline fetch.
"""
import unittest
from unittest.mock import MagicMock
from backend.app import BackgroundPoller
from backend.gitlab_client import GitLabAPIClient, PIPELINES_PER_PROJECT


class TestSparklineMultiplePipelines(unittest.TestCase):
    """Test that sparklines get multiple default-branch pipelines when available."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock GitLab client
        self.mock_client = MagicMock(spec=GitLabAPIClient)
        self.mock_client.resolve_merge_request_refs = MagicMock()  # No-op for these tests
        
        # Create poller with mock client
        self.poller = BackgroundPoller(
            gitlab_client=self.mock_client,
            poll_interval_sec=60,
            group_ids=None,
            project_ids=[123]  # Configured scope
        )

    def test_fetches_multiple_default_branch_pipelines_when_missing_from_general(self):
        """
        When feature branches dominate the general pipeline list and no default-branch
        pipeline is present, the targeted fetch should request PIPELINES_PER_PROJECT
        default-branch pipelines, not just 1.
        """
        # Mock project with feature-heavy activity
        project = {
            'id': 123,
            'name': 'feature-heavy-project',
            'path_with_namespace': 'org/feature-heavy',
            'default_branch': 'main'
        }
        
        # General fetch returns 10 feature branch pipelines (no main)
        feature_pipelines = [
            {
                'id': 1000 + i,
                'status': 'success',
                'ref': f'feature/branch-{i}',
                'created_at': f'2024-01-20T12:{50-i:02d}:00.000Z'
            }
            for i in range(PIPELINES_PER_PROJECT)
        ]
        
        # Targeted default-branch fetch should return multiple pipelines
        default_branch_pipelines = [
            {
                'id': 2000 + i,
                'status': 'success' if i % 2 == 0 else 'failed',
                'ref': 'main',
                'created_at': f'2024-01-20T11:{50-i:02d}:00.000Z'
            }
            for i in range(PIPELINES_PER_PROJECT)
        ]
        
        # Mock get_pipelines to return different results based on ref parameter
        def mock_get_pipelines(project_id, per_page=None, ref=None):
            if ref == 'main':
                # Should be called with per_page=PIPELINES_PER_PROJECT
                self.assertEqual(per_page, PIPELINES_PER_PROJECT,
                    f"Expected targeted default-branch fetch to use per_page={PIPELINES_PER_PROJECT}, got {per_page}")
                return list(default_branch_pipelines)  # Return copy
            else:
                # General fetch (no ref filter)
                return list(feature_pipelines)  # Return copy
        
        self.mock_client.get_pipelines = mock_get_pipelines
        
        # Call the method under test
        pipeline_data = self.poller._fetch_pipelines([project], poll_id='test-1')
        
        # Verify pipeline_data structure
        self.assertIsNotNone(pipeline_data)
        self.assertIn('all_pipelines', pipeline_data)
        self.assertIn('per_project', pipeline_data)
        
        # Verify per-project pipelines contain both general and default-branch pipelines
        per_project = pipeline_data['per_project']
        self.assertIn(123, per_project)
        project_pipelines = per_project[123]
        
        # Should have feature pipelines + default-branch pipelines
        self.assertEqual(len(project_pipelines), PIPELINES_PER_PROJECT * 2,
            f"Expected {PIPELINES_PER_PROJECT * 2} pipelines (10 feature + 10 default-branch)")

    def test_deduplicates_pipelines_when_overlap_occurs(self):
        """
        When the GitLab API returns duplicate pipeline IDs (rare API anomaly),
        they should be deduplicated.
        """
        project = {
            'id': 456,
            'name': 'overlap-project',
            'path_with_namespace': 'org/overlap',
            'default_branch': 'main'
        }
        
        # Simulate API returning duplicate IDs in general fetch (API anomaly)
        # Pipeline ID 3500 appears twice with different timestamps
        general_pipelines = [
            # First occurrence of ID 3500
            {
                'id': 3500,
                'status': 'success',
                'ref': 'feature/branch-1',
                'created_at': '2024-01-20T13:55:00.000Z'
            },
            # Other pipelines
            {
                'id': 3001,
                'status': 'success',
                'ref': 'feature/branch-2',
                'created_at': '2024-01-20T13:54:00.000Z'
            },
            {
                'id': 3002,
                'status': 'success',
                'ref': 'main',  # Has default-branch pipeline, so no targeted fetch
                'created_at': '2024-01-20T13:53:00.000Z'
            },
            # Second occurrence of ID 3500 (duplicate)
            {
                'id': 3500,
                'status': 'failed',
                'ref': 'feature/branch-3',
                'created_at': '2024-01-20T13:52:00.000Z'
            },
        ]
        
        self.mock_client.get_pipelines = MagicMock(return_value=list(general_pipelines))
        
        # Call the method
        pipeline_data = self.poller._fetch_pipelines([project], poll_id='test-2')
        
        # Verify deduplication in per-project pipelines
        per_project = pipeline_data['per_project']
        self.assertIn(456, per_project)
        project_pipelines = per_project[456]
        
        # Check for duplicate IDs - should only have unique IDs
        pipeline_ids = [p.get('id') for p in project_pipelines]
        unique_ids = set(pipeline_ids)
        
        self.assertEqual(len(pipeline_ids), len(unique_ids),
            f"Found duplicate pipeline IDs: {len(pipeline_ids)} total, {len(unique_ids)} unique")
        
        # Should have 3 unique pipelines (3500, 3001, 3002)
        self.assertEqual(len(unique_ids), 3,
            f"Expected 3 unique pipelines after deduplication, got {len(unique_ids)}")
        
        # Verify ID 3500 appears only once
        count_3500 = sum(1 for pid in pipeline_ids if pid == 3500)
        self.assertEqual(count_3500, 1,
            f"Pipeline ID 3500 should appear only once, found {count_3500} times")
        
        # Verify global all_pipelines also has no duplicates
        all_pipelines = pipeline_data['all_pipelines']
        all_pipeline_ids = [p.get('id') for p in all_pipelines]
        all_unique_ids = set(all_pipeline_ids)
        
        self.assertEqual(len(all_pipeline_ids), len(all_unique_ids),
            f"Found duplicate pipeline IDs in all_pipelines: {len(all_pipeline_ids)} total, {len(all_unique_ids)} unique")

    def test_sparkline_data_includes_multiple_statuses(self):
        """
        After enrichment, the recent_default_branch_pipelines list should contain
        multiple status entries when multiple default-branch pipelines are available.
        """
        from backend.gitlab_client import enrich_projects_with_pipelines
        
        project = {
            'id': 789,
            'name': 'sparkline-project',
            'default_branch': 'main'
        }
        
        # Simulate fetched pipelines: mix of feature and default-branch
        # 5 feature pipelines + 5 default-branch pipelines
        pipelines = [
            # Feature pipelines (newer)
            *[{
                'id': 5000 + i,
                'status': 'success',
                'ref': f'feature/branch-{i}',
                'created_at': f'2024-01-20T14:{55-i:02d}:00.000Z'
            } for i in range(5)],
            # Default-branch pipelines (older, mixed success/failed)
            {
                'id': 6000,
                'status': 'failed',
                'ref': 'main',
                'created_at': '2024-01-20T14:49:00.000Z'
            },
            {
                'id': 6001,
                'status': 'success',
                'ref': 'main',
                'created_at': '2024-01-20T14:48:00.000Z'
            },
            {
                'id': 6002,
                'status': 'failed',
                'ref': 'main',
                'created_at': '2024-01-20T14:47:00.000Z'
            },
            {
                'id': 6003,
                'status': 'success',
                'ref': 'main',
                'created_at': '2024-01-20T14:46:00.000Z'
            },
            {
                'id': 6004,
                'status': 'success',
                'ref': 'main',
                'created_at': '2024-01-20T14:45:00.000Z'
            }
        ]
        
        per_project_pipelines = {789: pipelines}
        
        # Enrich the project
        enriched = enrich_projects_with_pipelines([project], per_project_pipelines)
        
        self.assertEqual(len(enriched), 1)
        enriched_project = enriched[0]
        
        # Verify recent_default_branch_pipelines contains multiple entries
        default_branch_statuses = enriched_project.get('recent_default_branch_pipelines', [])
        
        self.assertGreater(len(default_branch_statuses), 1,
            "Sparkline data should contain more than 1 status entry")
        
        # Should have 5 default-branch pipeline statuses (matching our 5 main pipelines)
        self.assertEqual(len(default_branch_statuses), 5,
            f"Expected 5 default-branch statuses, got {len(default_branch_statuses)}")
        
        # Verify the statuses match our expectations (failed, success, failed, success, success)
        expected_statuses = ['failed', 'success', 'failed', 'success', 'success']
        self.assertEqual(default_branch_statuses, expected_statuses,
            f"Sparkline statuses don't match expected: {default_branch_statuses} vs {expected_statuses}")

    def test_ignores_skipped_manual_canceled_in_sparkline(self):
        """
        Verify that skipped/manual/canceled pipelines are excluded from the
        recent_default_branch_pipelines list (sparkline data).
        """
        from backend.gitlab_client import enrich_projects_with_pipelines
        
        project = {
            'id': 999,
            'name': 'filtered-project',
            'default_branch': 'main'
        }
        
        # Mix of meaningful and ignored statuses on default branch
        pipelines = [
            {'id': 7000, 'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T15:50:00.000Z'},
            {'id': 7001, 'status': 'skipped', 'ref': 'main', 'created_at': '2024-01-20T15:49:00.000Z'},  # IGNORED
            {'id': 7002, 'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T15:48:00.000Z'},
            {'id': 7003, 'status': 'manual', 'ref': 'main', 'created_at': '2024-01-20T15:47:00.000Z'},   # IGNORED
            {'id': 7004, 'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T15:46:00.000Z'},
            {'id': 7005, 'status': 'canceled', 'ref': 'main', 'created_at': '2024-01-20T15:45:00.000Z'}, # IGNORED
            {'id': 7006, 'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T15:44:00.000Z'},
        ]
        
        per_project_pipelines = {999: pipelines}
        
        # Enrich the project
        enriched = enrich_projects_with_pipelines([project], per_project_pipelines)
        enriched_project = enriched[0]
        
        # Verify sparkline excludes ignored statuses
        default_branch_statuses = enriched_project.get('recent_default_branch_pipelines', [])
        
        # Should only have meaningful statuses (success, failed, success, success)
        expected_statuses = ['success', 'failed', 'success', 'success']
        self.assertEqual(default_branch_statuses, expected_statuses,
            f"Sparkline should exclude skipped/manual/canceled: {default_branch_statuses}")
        
        # Verify count
        self.assertEqual(len(default_branch_statuses), 4,
            f"Expected 4 meaningful statuses (excluded 3 ignored), got {len(default_branch_statuses)}")


if __name__ == '__main__':
    unittest.main()

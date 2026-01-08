"""Integration test to verify sparkline guarantee of 10 meaningful default-branch statuses.

This test validates the complete end-to-end flow from fetch to enrichment to ensure
that repositories get up to 10 meaningful default-branch pipeline statuses for sparklines.
"""
import unittest
from unittest.mock import MagicMock
from backend.app import BackgroundPoller
from backend.gitlab_client import (
    GitLabAPIClient, 
    enrich_projects_with_pipelines,
    TARGET_MEANINGFUL_DEFAULT_BRANCH_STATUSES,
    DEFAULT_BRANCH_FETCH_LIMIT,
)


class TestSparklineGuarantee(unittest.TestCase):
    """End-to-end integration test for sparkline guarantee."""

    def test_guarantees_10_meaningful_statuses_with_ignored_statuses_mixed_in(self):
        """
        Full integration test: Verify that when a project has many default-branch
        pipelines with some ignored statuses (skipped/manual/canceled), the sparkline
        still gets exactly TARGET_MEANINGFUL_DEFAULT_BRANCH_STATUSES (10) meaningful statuses.
        
        Scenario:
        - Project has 20 default-branch pipelines
        - 10 are meaningful (success/failed)
        - 10 are ignored (skipped/manual/canceled)
        - Backend fetches 20 (DEFAULT_BRANCH_FETCH_LIMIT)
        - Enrichment filters to get 10 meaningful statuses for sparkline
        """
        # Mock GitLab client
        mock_client = MagicMock(spec=GitLabAPIClient)
        mock_client.resolve_merge_request_refs = MagicMock()  # No-op
        
        # Create poller
        poller = BackgroundPoller(
            gitlab_client=mock_client,
            poll_interval_sec=60,
            project_ids=[999]  # Configured scope
        )
        
        # Test project
        project = {
            'id': 999,
            'name': 'rich-history-project',
            'path_with_namespace': 'org/rich-history-project',
            'default_branch': 'main'
        }
        
        # General fetch: 10 feature branch pipelines (no main)
        feature_pipelines = [
            {
                'id': 5000 + i,
                'status': 'success',
                'ref': f'feature/branch-{i}',
                'created_at': f'2024-01-20T16:{59-i:02d}:00.000Z'
            }
            for i in range(10)
        ]
        
        # Default-branch fetch: 20 pipelines alternating between meaningful and ignored
        # Pattern: meaningful, meaningful, ignored, meaningful, meaningful, ignored, ...
        # This gives us exactly 13-14 meaningful out of 20 (enough to get 10)
        default_branch_pipelines = []
        meaningful_count = 0
        for i in range(20):
            if i % 3 == 2:  # Every 3rd is ignored
                status = 'skipped' if i % 6 == 2 else 'manual'
            else:
                status = 'success' if meaningful_count % 3 < 2 else 'failed'
                meaningful_count += 1
            
            default_branch_pipelines.append({
                'id': 6000 + i,
                'status': status,
                'ref': 'main',
                'created_at': f'2024-01-20T15:{59-i:02d}:00.000Z'
            })
        
        # Mock get_pipelines
        def mock_get_pipelines(project_id, per_page=None, ref=None):
            if ref == 'main':
                # Should be called with DEFAULT_BRANCH_FETCH_LIMIT
                self.assertEqual(per_page, DEFAULT_BRANCH_FETCH_LIMIT)
                return list(default_branch_pipelines)
            else:
                return list(feature_pipelines)
        
        mock_client.get_pipelines = mock_get_pipelines
        
        # Fetch pipelines
        pipeline_data = poller._fetch_pipelines([project], poll_id='test-guarantee')
        
        # Verify fetch happened
        self.assertIsNotNone(pipeline_data)
        
        # Enrich projects
        enriched = enrich_projects_with_pipelines(
            [project], 
            pipeline_data['per_project'],
            poll_id='test-guarantee'
        )
        
        # Verify enrichment
        self.assertEqual(len(enriched), 1)
        enriched_project = enriched[0]
        
        # Get sparkline data
        sparkline_statuses = enriched_project.get('recent_default_branch_pipelines', [])
        
        # CRITICAL ASSERTION: Should have exactly 10 meaningful statuses
        self.assertEqual(len(sparkline_statuses), TARGET_MEANINGFUL_DEFAULT_BRANCH_STATUSES,
            f"Expected {TARGET_MEANINGFUL_DEFAULT_BRANCH_STATUSES} meaningful statuses, got {len(sparkline_statuses)}")
        
        # Verify no ignored statuses in sparkline
        ignored_statuses = {'skipped', 'manual', 'canceled', 'cancelled'}
        for status in sparkline_statuses:
            self.assertNotIn(status, ignored_statuses,
                f"Sparkline should not contain ignored status: {status}")
        
        # Verify statuses are meaningful (success or failed)
        valid_statuses = {'success', 'failed', 'running', 'pending'}
        for status in sparkline_statuses:
            self.assertIn(status, valid_statuses,
                f"Sparkline status should be meaningful: {status}")

    def test_returns_fewer_than_10_when_insufficient_meaningful_pipelines(self):
        """
        Verify that when a project has fewer than 10 meaningful default-branch pipelines,
        the sparkline returns whatever is available (not padded to 10).
        
        Scenario:
        - Project has 20 default-branch pipelines total
        - Only 5 are meaningful (success/failed)
        - 15 are ignored (skipped/manual/canceled)
        - Should return 5 in sparkline, not 10
        """
        # Mock GitLab client
        mock_client = MagicMock(spec=GitLabAPIClient)
        mock_client.resolve_merge_request_refs = MagicMock()
        
        # Create poller
        poller = BackgroundPoller(
            gitlab_client=mock_client,
            poll_interval_sec=60,
            project_ids=[888]
        )
        
        # Test project
        project = {
            'id': 888,
            'name': 'sparse-history-project',
            'path_with_namespace': 'org/sparse-history-project',
            'default_branch': 'main'
        }
        
        # General fetch: feature pipelines
        feature_pipelines = [
            {
                'id': 4000 + i,
                'status': 'success',
                'ref': f'feature/branch-{i}',
                'created_at': f'2024-01-20T16:{59-i:02d}:00.000Z'
            }
            for i in range(5)
        ]
        
        # Default-branch fetch: 5 meaningful + 15 ignored = 20 total
        default_branch_pipelines = [
            # 5 meaningful pipelines
            *[{
                'id': 7000 + i,
                'status': 'success' if i % 2 == 0 else 'failed',
                'ref': 'main',
                'created_at': f'2024-01-20T15:{59-i:02d}:00.000Z'
            } for i in range(5)],
            # 15 ignored pipelines
            *[{
                'id': 7100 + i,
                'status': 'skipped',
                'ref': 'main',
                'created_at': f'2024-01-20T14:{59-i:02d}:00.000Z'
            } for i in range(15)]
        ]
        
        # Mock get_pipelines
        def mock_get_pipelines(project_id, per_page=None, ref=None):
            if ref == 'main':
                return list(default_branch_pipelines)
            else:
                return list(feature_pipelines)
        
        mock_client.get_pipelines = mock_get_pipelines
        
        # Fetch and enrich
        pipeline_data = poller._fetch_pipelines([project], poll_id='test-sparse')
        enriched = enrich_projects_with_pipelines([project], pipeline_data['per_project'])
        
        # Verify sparkline has only 5 statuses (not padded to 10)
        sparkline_statuses = enriched[0].get('recent_default_branch_pipelines', [])
        self.assertEqual(len(sparkline_statuses), 5,
            f"Expected 5 meaningful statuses (not padded to 10), got {len(sparkline_statuses)}")
        
        # Verify all are meaningful
        for status in sparkline_statuses:
            self.assertIn(status, {'success', 'failed', 'running', 'pending'},
                f"All sparkline statuses should be meaningful: {status}")


if __name__ == '__main__':
    unittest.main()

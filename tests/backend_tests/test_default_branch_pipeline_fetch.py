"""Tests for default branch pipeline fetching when feature branches dominate recent pipelines."""
import unittest
from unittest.mock import MagicMock, patch
from backend.gitlab_client import enrich_projects_with_pipelines


class TestDefaultBranchPipelineFetch(unittest.TestCase):
    """Test that default-branch pipeline data is available even when feature branches dominate."""

    def test_enrichment_with_only_feature_branch_pipelines(self):
        """
        Scenario: Last 10 pipelines are all from feature branches.
        In this case, last_default_branch_pipeline_status should be None
        because no default-branch pipeline exists in the provided data.
        """
        projects = [
            {
                'id': 123,
                'name': 'feature-heavy-project',
                'default_branch': 'main'
            }
        ]
        
        # Simulate 10 recent pipelines, all on feature branches
        feature_pipelines = [
            {
                'id': i,
                'status': 'success',
                'ref': f'feature/branch-{i}',
                'created_at': f'2024-01-20T10:{50-i:02d}:00.000Z'
            }
            for i in range(10)
        ]
        
        per_project_pipelines = {
            123: feature_pipelines
        }
        
        enriched = enrich_projects_with_pipelines(projects, per_project_pipelines)
        
        self.assertEqual(len(enriched), 1)
        project = enriched[0]
        
        # Should have last_pipeline_* from the most recent feature branch pipeline
        self.assertEqual(project['last_pipeline_status'], 'success')
        self.assertEqual(project['last_pipeline_ref'], 'feature/branch-0')
        
        # Should NOT have default-branch pipeline data (all nulls)
        self.assertIsNone(project['last_default_branch_pipeline_status'])
        self.assertIsNone(project['last_default_branch_pipeline_ref'])
        self.assertIsNone(project['last_default_branch_pipeline_duration'])
        self.assertIsNone(project['last_default_branch_pipeline_updated_at'])
        
        # Success rate should be None (no default-branch data)
        self.assertIsNone(project['recent_success_rate'])
        self.assertIsNone(project['recent_success_rate_default_branch'])
        
        # No consecutive failures (no default-branch pipelines)
        self.assertEqual(project['consecutive_default_branch_failures'], 0)
        self.assertFalse(project['has_failing_jobs'])
        self.assertFalse(project['has_runner_issues'])

    def test_enrichment_with_mixed_pipelines_including_default_branch(self):
        """
        Scenario: 8 feature branch pipelines + 2 default branch pipelines.
        The default-branch data should be properly extracted and set.
        """
        projects = [
            {
                'id': 456,
                'name': 'mixed-project',
                'default_branch': 'main'
            }
        ]
        
        # Simulate 10 pipelines: newest 8 are feature branches, 
        # then 2 older ones on main (one failed, one success)
        mixed_pipelines = [
            # 8 recent feature branch pipelines (newest first)
            *[
                {
                    'id': i,
                    'status': 'success',
                    'ref': f'feature/branch-{i}',
                    'duration': 100 + i,
                    'created_at': f'2024-01-20T10:{50-i:02d}:00.000Z'
                }
                for i in range(8)
            ],
            # 1 failed default-branch pipeline (9th in list)
            {
                'id': 100,
                'status': 'failed',
                'ref': 'main',
                'duration': 200,
                'created_at': '2024-01-20T10:42:00.000Z',
                'updated_at': '2024-01-20T10:45:00.000Z'
            },
            # 1 successful default-branch pipeline (10th in list, oldest)
            {
                'id': 101,
                'status': 'success',
                'ref': 'main',
                'duration': 150,
                'created_at': '2024-01-20T10:40:00.000Z',
                'updated_at': '2024-01-20T10:43:00.000Z'
            }
        ]
        
        per_project_pipelines = {
            456: mixed_pipelines
        }
        
        enriched = enrich_projects_with_pipelines(projects, per_project_pipelines)
        
        self.assertEqual(len(enriched), 1)
        project = enriched[0]
        
        # last_pipeline_* should be from the most recent overall (feature branch)
        self.assertEqual(project['last_pipeline_status'], 'success')
        self.assertEqual(project['last_pipeline_ref'], 'feature/branch-0')
        
        # last_default_branch_pipeline_* should be from the most recent main branch pipeline (failed)
        self.assertEqual(project['last_default_branch_pipeline_status'], 'failed')
        self.assertEqual(project['last_default_branch_pipeline_ref'], 'main')
        self.assertEqual(project['last_default_branch_pipeline_duration'], 200)
        self.assertEqual(project['last_default_branch_pipeline_updated_at'], '2024-01-20T10:45:00.000Z')
        
        # Success rate based on default-branch only (1 failed, 1 success = 50%)
        self.assertEqual(project['recent_success_rate_default_branch'], 0.5)
        self.assertEqual(project['recent_success_rate'], 0.5)  # Backward compatible field
        
        # All-branches success rate (8 success + 1 failed + 1 success = 90%)
        self.assertEqual(project['recent_success_rate_all_branches'], 0.9)
        
        # Consecutive failures on default branch (most recent is failed = 1)
        self.assertEqual(project['consecutive_default_branch_failures'], 1)
        self.assertTrue(project['has_failing_jobs'])
        self.assertEqual(project['failing_jobs_count'], 1)

    def test_enrichment_with_default_branch_runner_failure(self):
        """
        Scenario matching the issue: Runner failure on default branch,
        but surrounded by many feature branch pipelines.
        """
        projects = [
            {
                'id': 789,
                'name': 'runner-issue-project',
                'default_branch': 'main'
            }
        ]
        
        # Simulate: 5 feature pipelines, then 1 failed main with runner issue, then 4 more features
        pipelines_with_runner_issue = [
            # 5 recent feature branch pipelines
            *[
                {
                    'id': i,
                    'status': 'success',
                    'ref': f'feature/new-{i}',
                    'duration': 100 + i,
                    'created_at': f'2024-01-20T11:{55-i:02d}:00.000Z'
                }
                for i in range(5)
            ],
            # 1 failed main branch pipeline with runner issue (6th in list)
            {
                'id': 200,
                'status': 'failed',
                'ref': 'main',
                'failure_reason': 'runner_system_failure',  # Runner issue!
                'duration': 50,
                'created_at': '2024-01-20T11:49:00.000Z',
                'updated_at': '2024-01-20T11:50:00.000Z'
            },
            # 4 older feature branch pipelines
            *[
                {
                    'id': 100 + i,
                    'status': 'success',
                    'ref': f'feature/old-{i}',
                    'duration': 90 + i,
                    'created_at': f'2024-01-20T11:{45-i:02d}:00.000Z'
                }
                for i in range(4)
            ]
        ]
        
        per_project_pipelines = {
            789: pipelines_with_runner_issue
        }
        
        enriched = enrich_projects_with_pipelines(projects, per_project_pipelines)
        
        self.assertEqual(len(enriched), 1)
        project = enriched[0]
        
        # last_pipeline_* is from most recent overall (feature branch)
        self.assertEqual(project['last_pipeline_status'], 'success')
        self.assertEqual(project['last_pipeline_ref'], 'feature/new-0')
        
        # last_default_branch_pipeline_* should show the failed main pipeline
        self.assertEqual(project['last_default_branch_pipeline_status'], 'failed')
        self.assertEqual(project['last_default_branch_pipeline_ref'], 'main')
        self.assertEqual(project['last_default_branch_pipeline_duration'], 50)
        self.assertEqual(project['last_default_branch_pipeline_updated_at'], '2024-01-20T11:50:00.000Z')
        
        # Success rate on default branch: only 1 pipeline (failed) = 0%
        self.assertEqual(project['recent_success_rate_default_branch'], 0.0)
        
        # Should detect runner issue
        self.assertTrue(project['has_runner_issues'])
        
        # Should show failing jobs
        self.assertTrue(project['has_failing_jobs'])
        self.assertEqual(project['failing_jobs_count'], 1)
        
        # Consecutive failures = 1
        self.assertEqual(project['consecutive_default_branch_failures'], 1)


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python3
"""
Tests for DSO health fields: has_failing_jobs, failing_jobs_count, has_runner_issues

These fields are used by the DSO dashboard to provide quick visibility into CI health issues.
"""

import unittest
import sys
import os

# Add parent directory to path to import from backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend import app as server
from backend.gitlab_client import is_runner_related_failure


class TestIsRunnerRelatedFailureHelper(unittest.TestCase):
    """Test the is_runner_related_failure helper function directly"""
    
    def test_returns_true_for_stuck_status(self):
        """Test helper returns True for 'stuck' pipeline status"""
        pipeline = {'status': 'stuck', 'ref': 'main'}
        self.assertTrue(is_runner_related_failure(pipeline))
    
    def test_returns_true_for_runner_system_failure(self):
        """Test helper returns True for runner_system_failure reason"""
        pipeline = {'status': 'failed', 'failure_reason': 'runner_system_failure'}
        self.assertTrue(is_runner_related_failure(pipeline))
    
    def test_returns_true_for_stuck_or_timeout_failure(self):
        """Test helper returns True for stuck_or_timeout_failure reason"""
        pipeline = {'status': 'failed', 'failure_reason': 'stuck_or_timeout_failure'}
        self.assertTrue(is_runner_related_failure(pipeline))
    
    def test_returns_true_for_runner_unsupported(self):
        """Test helper returns True for runner_unsupported reason"""
        pipeline = {'status': 'failed', 'failure_reason': 'runner_unsupported'}
        self.assertTrue(is_runner_related_failure(pipeline))
    
    def test_returns_true_for_scheduler_failure(self):
        """Test helper returns True for scheduler_failure reason"""
        pipeline = {'status': 'failed', 'failure_reason': 'scheduler_failure'}
        self.assertTrue(is_runner_related_failure(pipeline))
    
    def test_returns_true_for_data_integrity_failure(self):
        """Test helper returns True for data_integrity_failure reason"""
        pipeline = {'status': 'failed', 'failure_reason': 'data_integrity_failure'}
        self.assertTrue(is_runner_related_failure(pipeline))
    
    def test_returns_true_for_unknown_failure(self):
        """Test helper returns True for unknown_failure reason (unclassified errors)"""
        pipeline = {'status': 'failed', 'failure_reason': 'unknown_failure'}
        self.assertTrue(is_runner_related_failure(pipeline))
    
    def test_returns_true_for_api_failure(self):
        """Test helper returns True for api_failure reason (GitLab API issues)"""
        pipeline = {'status': 'failed', 'failure_reason': 'api_failure'}
        self.assertTrue(is_runner_related_failure(pipeline))
    
    def test_returns_true_for_system_failure(self):
        """Test helper returns True for system_failure reason (pod/container failures)"""
        pipeline = {'status': 'failed', 'failure_reason': 'system_failure'}
        self.assertTrue(is_runner_related_failure(pipeline))
    
    def test_returns_true_for_pod_timeout_error(self):
        """Test helper returns True for pod timeout errors (GitHub issue scenario)
        
        This tests the specific error pattern reported by users:
        'Job failed (system failure): prepare environment: waiting for pod running: 
        timed out waiting for pod to start'
        """
        pipeline = {
            'status': 'failed', 
            'failure_reason': 'Job failed (system failure): prepare environment: waiting for pod running: timed out waiting for pod to start'
        }
        self.assertTrue(is_runner_related_failure(pipeline))
    
    def test_returns_true_for_out_of_memory_error(self):
        """Test helper returns True for out of memory errors
        
        Common scenarios:
        - 'fatal: Out of memory, malloc failed'
        - 'std::bad_alloc'
        - Container/runner memory exhaustion
        """
        pipeline = {'status': 'failed', 'failure_reason': 'fatal: Out of memory, malloc failed (tried to allocate 8192 bytes)'}
        self.assertTrue(is_runner_related_failure(pipeline))
    
    def test_returns_true_for_no_space_left_error(self):
        """Test helper returns True for disk space exhaustion errors
        
        Common scenarios:
        - 'write /var/lib/docker: no space left on device'
        - Docker builds filling up runner disk
        - Build artifacts exceeding available space
        """
        pipeline = {'status': 'failed', 'failure_reason': 'write /var/lib/docker: no space left on device'}
        self.assertTrue(is_runner_related_failure(pipeline))
    
    def test_returns_false_for_script_failure(self):
        """Test helper returns False for regular script_failure"""
        pipeline = {'status': 'failed', 'failure_reason': 'script_failure'}
        self.assertFalse(is_runner_related_failure(pipeline))
    
    def test_returns_false_for_no_failure_reason(self):
        """Test helper returns False when no failure_reason is present"""
        pipeline = {'status': 'failed'}
        self.assertFalse(is_runner_related_failure(pipeline))
    
    def test_returns_false_for_success_status(self):
        """Test helper returns False for success status"""
        pipeline = {'status': 'success'}
        self.assertFalse(is_runner_related_failure(pipeline))
    
    def test_case_insensitive_matching(self):
        """Test helper matches failure_reason case-insensitively"""
        pipeline = {'status': 'failed', 'failure_reason': 'RUNNER_SYSTEM_FAILURE'}
        self.assertTrue(is_runner_related_failure(pipeline))
    
    def test_partial_match_in_reason(self):
        """Test helper matches when reason is contained within failure_reason"""
        pipeline = {'status': 'failed', 'failure_reason': 'some_prefix_runner_system_failure_suffix'}
        self.assertTrue(is_runner_related_failure(pipeline))


class TestDSOHealthFieldsHasFailingJobs(unittest.TestCase):
    """Test has_failing_jobs field - true if recent default-branch pipelines contain failed jobs"""
    
    def test_has_failing_jobs_true_when_recent_failures(self):
        """Test has_failing_jobs is True when default branch has recent failures"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        pipelines = [
            {'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z'},
            {'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T09:00:00Z'},
        ]
        
        per_project_pipelines = {1: pipelines}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        self.assertTrue(enriched[0]['has_failing_jobs'])
    
    def test_has_failing_jobs_false_when_no_failures(self):
        """Test has_failing_jobs is False when all default branch pipelines succeed"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        pipelines = [
            {'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z'},
            {'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T09:00:00Z'},
        ]
        
        per_project_pipelines = {1: pipelines}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        self.assertFalse(enriched[0]['has_failing_jobs'])
    
    def test_has_failing_jobs_ignores_feature_branch_failures(self):
        """Test has_failing_jobs only considers default branch pipelines"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        # Feature branch has failures, but main branch is all success
        pipelines = [
            {'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z'},
            {'status': 'failed', 'ref': 'feature/new', 'created_at': '2024-01-20T09:30:00Z'},
            {'status': 'failed', 'ref': 'feature/new', 'created_at': '2024-01-20T09:00:00Z'},
        ]
        
        per_project_pipelines = {1: pipelines}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        # Should be False - only default branch matters
        self.assertFalse(enriched[0]['has_failing_jobs'])
    
    def test_has_failing_jobs_ignores_skipped_manual_canceled(self):
        """Test has_failing_jobs ignores skipped/manual/canceled statuses"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        # Only skipped, manual, and canceled statuses - no actual failures
        pipelines = [
            {'status': 'skipped', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z'},
            {'status': 'manual', 'ref': 'main', 'created_at': '2024-01-20T09:00:00Z'},
            {'status': 'canceled', 'ref': 'main', 'created_at': '2024-01-20T08:00:00Z'},
        ]
        
        per_project_pipelines = {1: pipelines}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        # Should be False - ignored statuses don't count as failures
        self.assertFalse(enriched[0]['has_failing_jobs'])
    
    def test_has_failing_jobs_false_when_no_pipelines(self):
        """Test has_failing_jobs is False when project has no pipelines"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        per_project_pipelines = {}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        self.assertFalse(enriched[0]['has_failing_jobs'])


class TestDSOHealthFieldsFailingJobsCount(unittest.TestCase):
    """Test failing_jobs_count field - count of failed pipelines on default branch"""
    
    def test_failing_jobs_count_correct_count(self):
        """Test failing_jobs_count correctly counts failed default-branch pipelines"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        # 3 failures on main branch
        pipelines = [
            {'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z'},
            {'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T09:30:00Z'},
            {'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T09:00:00Z'},
            {'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T08:00:00Z'},
            {'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T07:00:00Z'},
        ]
        
        per_project_pipelines = {1: pipelines}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        self.assertEqual(enriched[0]['failing_jobs_count'], 3)
    
    def test_failing_jobs_count_zero_when_no_failures(self):
        """Test failing_jobs_count is 0 when no failures"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        pipelines = [
            {'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z'},
            {'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T09:00:00Z'},
        ]
        
        per_project_pipelines = {1: pipelines}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        self.assertEqual(enriched[0]['failing_jobs_count'], 0)
    
    def test_failing_jobs_count_ignores_feature_branches(self):
        """Test failing_jobs_count only counts default branch failures"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        # 1 failure on main, 3 failures on feature branches
        pipelines = [
            {'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z'},
            {'status': 'failed', 'ref': 'feature/a', 'created_at': '2024-01-20T09:30:00Z'},
            {'status': 'failed', 'ref': 'feature/b', 'created_at': '2024-01-20T09:00:00Z'},
            {'status': 'failed', 'ref': 'feature/c', 'created_at': '2024-01-20T08:00:00Z'},
        ]
        
        per_project_pipelines = {1: pipelines}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        # Should only count main branch failure
        self.assertEqual(enriched[0]['failing_jobs_count'], 1)
    
    def test_failing_jobs_count_zero_when_no_pipelines(self):
        """Test failing_jobs_count is 0 when no pipelines exist"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        per_project_pipelines = {}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        self.assertEqual(enriched[0]['failing_jobs_count'], 0)


class TestDSOHealthFieldsHasRunnerIssues(unittest.TestCase):
    """Test has_runner_issues field - true if pipelines are failing due to runner problems"""
    
    def test_has_runner_issues_true_when_stuck_status(self):
        """Test has_runner_issues is True when pipeline has 'stuck' status"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        pipelines = [
            {'status': 'stuck', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z'},
            {'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T09:00:00Z'},
        ]
        
        per_project_pipelines = {1: pipelines}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        self.assertTrue(enriched[0]['has_runner_issues'])
    
    def test_has_runner_issues_true_when_runner_system_failure(self):
        """Test has_runner_issues is True when failure_reason indicates runner issue"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        pipelines = [
            {'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z', 
             'failure_reason': 'runner_system_failure'},
            {'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T09:00:00Z'},
        ]
        
        per_project_pipelines = {1: pipelines}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        self.assertTrue(enriched[0]['has_runner_issues'])
    
    def test_has_runner_issues_true_when_stuck_or_timeout_failure(self):
        """Test has_runner_issues is True when failure_reason is stuck_or_timeout_failure"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        pipelines = [
            {'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z',
             'failure_reason': 'stuck_or_timeout_failure'},
        ]
        
        per_project_pipelines = {1: pipelines}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        self.assertTrue(enriched[0]['has_runner_issues'])
    
    def test_has_runner_issues_true_when_runner_unsupported(self):
        """Test has_runner_issues is True when failure_reason is runner_unsupported"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        pipelines = [
            {'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z',
             'failure_reason': 'runner_unsupported'},
        ]
        
        per_project_pipelines = {1: pipelines}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        self.assertTrue(enriched[0]['has_runner_issues'])
    
    def test_has_runner_issues_true_when_scheduler_failure(self):
        """Test has_runner_issues is True when failure_reason is scheduler_failure"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        pipelines = [
            {'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z',
             'failure_reason': 'scheduler_failure'},
        ]
        
        per_project_pipelines = {1: pipelines}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        self.assertTrue(enriched[0]['has_runner_issues'])
    
    def test_has_runner_issues_false_when_regular_failure(self):
        """Test has_runner_issues is False when failure is not runner-related"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        # Regular failure with script_failure reason (not runner-related)
        pipelines = [
            {'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z',
             'failure_reason': 'script_failure'},
            {'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T09:00:00Z'},
        ]
        
        per_project_pipelines = {1: pipelines}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        self.assertFalse(enriched[0]['has_runner_issues'])
    
    def test_has_runner_issues_false_when_no_failure_reason(self):
        """Test has_runner_issues is False when pipeline has no failure_reason"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        # Regular failure without failure_reason field
        pipelines = [
            {'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z'},
            {'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T09:00:00Z'},
        ]
        
        per_project_pipelines = {1: pipelines}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        self.assertFalse(enriched[0]['has_runner_issues'])
    
    def test_has_runner_issues_false_when_no_pipelines(self):
        """Test has_runner_issues is False when no pipelines exist"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        per_project_pipelines = {}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        self.assertFalse(enriched[0]['has_runner_issues'])
    
    def test_has_runner_issues_ignores_feature_branches(self):
        """Test has_runner_issues only considers default branch pipelines"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        # Runner issue on feature branch, main is healthy
        pipelines = [
            {'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z'},
            {'status': 'stuck', 'ref': 'feature/new', 'created_at': '2024-01-20T09:30:00Z'},
        ]
        
        per_project_pipelines = {1: pipelines}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        # Should be False - only default branch matters
        self.assertFalse(enriched[0]['has_runner_issues'])
    
    def test_has_runner_issues_case_insensitive_failure_reason(self):
        """Test has_runner_issues matches failure_reason case-insensitively"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        # Mixed case failure_reason
        pipelines = [
            {'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z',
             'failure_reason': 'Runner_System_Failure'},
        ]
        
        per_project_pipelines = {1: pipelines}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        self.assertTrue(enriched[0]['has_runner_issues'])


class TestDSOHealthFieldsIntegration(unittest.TestCase):
    """Integration tests for all DSO health fields together"""
    
    def test_all_fields_present_in_enriched_project(self):
        """Test that all DSO health fields are present in enriched project"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        pipelines = [
            {'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z'},
        ]
        
        per_project_pipelines = {1: pipelines}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        # All DSO health fields should be present
        self.assertIn('has_failing_jobs', enriched[0])
        self.assertIn('failing_jobs_count', enriched[0])
        self.assertIn('has_runner_issues', enriched[0])
        self.assertIn('consecutive_default_branch_failures', enriched[0])
    
    def test_all_fields_present_when_no_pipelines(self):
        """Test that all DSO health fields are present even with no pipelines"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        per_project_pipelines = {}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        # All DSO health fields should be present with default values
        self.assertFalse(enriched[0]['has_failing_jobs'])
        self.assertEqual(enriched[0]['failing_jobs_count'], 0)
        self.assertFalse(enriched[0]['has_runner_issues'])
        self.assertEqual(enriched[0]['consecutive_default_branch_failures'], 0)
    
    def test_complex_scenario_multiple_issues(self):
        """Test complex scenario with failures and runner issues"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        # Reordered to have failed pipelines at the top for consecutive failure count
        pipelines = [
            {'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T12:00:00Z',
             'failure_reason': 'runner_system_failure'},
            {'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T11:00:00Z'},
            {'status': 'stuck', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z'},
            {'status': 'skipped', 'ref': 'main', 'created_at': '2024-01-20T09:00:00Z'},
            {'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T08:00:00Z'},
        ]
        
        per_project_pipelines = {1: pipelines}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        # Has failing jobs (2 failed pipelines)
        self.assertTrue(enriched[0]['has_failing_jobs'])
        # 2 failed pipelines
        self.assertEqual(enriched[0]['failing_jobs_count'], 2)
        # Has runner issues (runner_system_failure and stuck status)
        self.assertTrue(enriched[0]['has_runner_issues'])
        # Consecutive failures count (2 failed in a row before stuck breaks the streak)
        # Note: 'stuck' is not 'failed' so it breaks consecutive failure counting
        self.assertEqual(enriched[0]['consecutive_default_branch_failures'], 2)
    
    def test_only_stuck_pipelines_edge_case(self):
        """Test edge case: only 'stuck' pipelines with no 'failed' ones
        
        This documents the behavior where:
        - has_runner_issues = True (detects 'stuck' status as runner issue)
        - has_failing_jobs = False (only counts 'failed' status)
        - failing_jobs_count = 0 (only counts 'failed' status)
        
        This is intentional: 'stuck' indicates runner problems but is not a 'failed' job.
        """
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        # Only stuck pipelines - no 'failed' status
        pipelines = [
            {'status': 'stuck', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z'},
            {'status': 'stuck', 'ref': 'main', 'created_at': '2024-01-20T09:00:00Z'},
            {'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T08:00:00Z'},
        ]
        
        per_project_pipelines = {1: pipelines}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        # has_runner_issues is True because 'stuck' indicates runner problems
        self.assertTrue(enriched[0]['has_runner_issues'])
        # has_failing_jobs is False because only 'failed' status is counted
        self.assertFalse(enriched[0]['has_failing_jobs'])
        # failing_jobs_count is 0 because only 'failed' status is counted
        self.assertEqual(enriched[0]['failing_jobs_count'], 0)
    
    def test_fields_consistent_with_success_rate(self):
        """Test DSO health fields are consistent with success rate calculation"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        # 50% success rate scenario
        pipelines = [
            {'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z'},
            {'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T09:00:00Z'},
        ]
        
        per_project_pipelines = {1: pipelines}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        # Verify all fields
        self.assertEqual(enriched[0]['recent_success_rate'], 0.5)
        self.assertTrue(enriched[0]['has_failing_jobs'])
        self.assertEqual(enriched[0]['failing_jobs_count'], 1)
        self.assertFalse(enriched[0]['has_runner_issues'])


if __name__ == '__main__':
    unittest.main()

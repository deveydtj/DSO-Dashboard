#!/usr/bin/env python3
"""
Tests for consecutive failure counting on default branch
Tests that skipped/manual/canceled statuses are ignored when computing consecutive failures
"""

import unittest
import sys
import os

# Add parent directory to path to from backend import app as server module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend import app as server


class TestConsecutiveFailureLogic(unittest.TestCase):
    """Test consecutive failure counting with various pipeline statuses"""
    
    def test_consecutive_failures_ignores_skipped(self):
        """Test that skipped pipelines are ignored when counting consecutive failures"""
        # Create a mock project with default branch 'main'
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        # Create pipelines: failed, skipped, failed (all on main)
        # Expected: 2 consecutive failures (skipped is ignored)
        pipelines = [
            {'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z'},
            {'status': 'skipped', 'ref': 'main', 'created_at': '2024-01-20T09:00:00Z'},
            {'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T08:00:00Z'},
            {'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T07:00:00Z'},
        ]
        
        per_project_pipelines = {1: pipelines}
        
        # Call the enrichment function
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        # Verify consecutive failures count
        self.assertEqual(len(enriched), 1)
        self.assertEqual(enriched[0]['consecutive_default_branch_failures'], 2)
    
    def test_consecutive_failures_ignores_manual(self):
        """Test that manual pipelines are ignored when counting consecutive failures"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        # Create pipelines: failed, manual, failed, success
        # Expected: 2 consecutive failures (manual is ignored)
        pipelines = [
            {'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z'},
            {'status': 'manual', 'ref': 'main', 'created_at': '2024-01-20T09:00:00Z'},
            {'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T08:00:00Z'},
            {'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T07:00:00Z'},
        ]
        
        per_project_pipelines = {1: pipelines}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        self.assertEqual(enriched[0]['consecutive_default_branch_failures'], 2)
    
    def test_consecutive_failures_ignores_canceled(self):
        """Test that canceled pipelines are ignored when counting consecutive failures"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        # Create pipelines: failed, canceled, failed, success
        # Expected: 2 consecutive failures (canceled is ignored)
        pipelines = [
            {'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z'},
            {'status': 'canceled', 'ref': 'main', 'created_at': '2024-01-20T09:00:00Z'},
            {'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T08:00:00Z'},
            {'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T07:00:00Z'},
        ]
        
        per_project_pipelines = {1: pipelines}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        self.assertEqual(enriched[0]['consecutive_default_branch_failures'], 2)
    
    def test_consecutive_failures_ignores_cancelled_british_spelling(self):
        """Test that cancelled (British spelling) pipelines are ignored"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        pipelines = [
            {'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z'},
            {'status': 'cancelled', 'ref': 'main', 'created_at': '2024-01-20T09:00:00Z'},
            {'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T08:00:00Z'},
        ]
        
        per_project_pipelines = {1: pipelines}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        self.assertEqual(enriched[0]['consecutive_default_branch_failures'], 2)
    
    def test_consecutive_failures_stops_at_success(self):
        """Test that consecutive count stops at success status"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        # Create pipelines: failed, skipped, failed, success, failed (old)
        # Expected: 2 consecutive failures (stops at success)
        pipelines = [
            {'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T11:00:00Z'},
            {'status': 'skipped', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z'},
            {'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T09:00:00Z'},
            {'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T08:00:00Z'},
            {'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T07:00:00Z'},
        ]
        
        per_project_pipelines = {1: pipelines}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        self.assertEqual(enriched[0]['consecutive_default_branch_failures'], 2)
    
    def test_consecutive_failures_stops_at_running(self):
        """Test that consecutive count stops at running status"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        pipelines = [
            {'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z'},
            {'status': 'running', 'ref': 'main', 'created_at': '2024-01-20T09:00:00Z'},
            {'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T08:00:00Z'},
        ]
        
        per_project_pipelines = {1: pipelines}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        self.assertEqual(enriched[0]['consecutive_default_branch_failures'], 1)
    
    def test_consecutive_failures_only_counts_default_branch(self):
        """Test that only default branch pipelines are counted"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        # Mix of main and feature branch pipelines
        # Only main branch should count
        pipelines = [
            {'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z'},
            {'status': 'failed', 'ref': 'feature/new', 'created_at': '2024-01-20T09:30:00Z'},  # ignored
            {'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T09:00:00Z'},
            {'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T08:00:00Z'},
        ]
        
        per_project_pipelines = {1: pipelines}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        self.assertEqual(enriched[0]['consecutive_default_branch_failures'], 2)
    
    def test_consecutive_failures_complex_scenario(self):
        """Test complex scenario with multiple ignored statuses"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        # Scenario: failed, skipped, failed, manual, failed, canceled, success
        # Expected: 3 consecutive failures (all ignored statuses are skipped)
        pipelines = [
            {'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T13:00:00Z'},
            {'status': 'skipped', 'ref': 'main', 'created_at': '2024-01-20T12:00:00Z'},
            {'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T11:00:00Z'},
            {'status': 'manual', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z'},
            {'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T09:00:00Z'},
            {'status': 'canceled', 'ref': 'main', 'created_at': '2024-01-20T08:00:00Z'},
            {'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T07:00:00Z'},
        ]
        
        per_project_pipelines = {1: pipelines}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        self.assertEqual(enriched[0]['consecutive_default_branch_failures'], 3)
    
    def test_consecutive_failures_zero_when_no_failures(self):
        """Test that consecutive failures is 0 when latest is success"""
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
        
        self.assertEqual(enriched[0]['consecutive_default_branch_failures'], 0)
    
    def test_consecutive_failures_zero_when_no_pipelines(self):
        """Test that consecutive failures is 0 when no pipelines exist"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        per_project_pipelines = {}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        self.assertEqual(enriched[0]['consecutive_default_branch_failures'], 0)


class TestSuccessRateCalculation(unittest.TestCase):
    """Test that success rate uses ALL branches and excludes skipped/manual/canceled"""
    
    def test_success_rate_ignores_skipped_manual_canceled(self):
        """Test that success rate calculation ignores skipped/manual/canceled"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        # 2 success, 2 failed, 2 skipped, 1 manual = 50% success rate (2/4)
        pipelines = [
            {'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z'},
            {'status': 'skipped', 'ref': 'main', 'created_at': '2024-01-20T09:00:00Z'},
            {'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T08:00:00Z'},
            {'status': 'manual', 'ref': 'main', 'created_at': '2024-01-20T07:00:00Z'},
            {'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T06:00:00Z'},
            {'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T05:00:00Z'},
            {'status': 'skipped', 'ref': 'main', 'created_at': '2024-01-20T04:00:00Z'},
        ]
        
        per_project_pipelines = {1: pipelines}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        # Should be 2 successes / 4 meaningful pipelines = 0.5
        self.assertEqual(enriched[0]['recent_success_rate'], 0.5)
    
    def test_success_rate_none_when_only_ignored_statuses(self):
        """Test that success rate is None when all pipelines are skipped/manual/canceled"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        pipelines = [
            {'status': 'skipped', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z'},
            {'status': 'manual', 'ref': 'main', 'created_at': '2024-01-20T09:00:00Z'},
            {'status': 'canceled', 'ref': 'main', 'created_at': '2024-01-20T08:00:00Z'},
        ]
        
        per_project_pipelines = {1: pipelines}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        self.assertIsNone(enriched[0]['recent_success_rate'])
    
    def test_success_rate_default_branch_only(self):
        """Test that recent_success_rate is based on default branch only (DSO primary metric)"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        # Mix of main and feature branch pipelines
        # recent_success_rate should only count main branch (DSO primary metric)
        # recent_success_rate_all_branches should count all branches (legacy)
        pipelines = [
            {'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z'},
            {'status': 'failed', 'ref': 'feature/new', 'created_at': '2024-01-20T09:00:00Z'},
            {'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T08:00:00Z'},
        ]
        
        per_project_pipelines = {1: pipelines}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        # recent_success_rate (DSO primary) should be 1 success / 2 main pipelines = 0.5
        self.assertEqual(enriched[0]['recent_success_rate'], 0.5)
        self.assertEqual(enriched[0]['recent_success_rate_default_branch'], 0.5)
        
        # recent_success_rate_all_branches should be 1 success / 3 total = 0.333...
        self.assertAlmostEqual(enriched[0]['recent_success_rate_all_branches'], 1/3)
    
    def test_success_rate_all_branches_vs_default_branch(self):
        """Test difference between all-branches and default-branch success rates"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        # Default branch is healthy (all success), but feature branch has failures
        pipelines = [
            {'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z'},
            {'status': 'failed', 'ref': 'feature/broken', 'created_at': '2024-01-20T09:00:00Z'},
            {'status': 'failed', 'ref': 'feature/broken', 'created_at': '2024-01-20T08:00:00Z'},
            {'status': 'failed', 'ref': 'feature/broken', 'created_at': '2024-01-20T07:00:00Z'},
            {'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T06:00:00Z'},
        ]
        
        per_project_pipelines = {1: pipelines}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        # DSO primary metric (recent_success_rate) should be 2/2 = 1.0 (default branch only)
        self.assertEqual(enriched[0]['recent_success_rate'], 1.0)
        self.assertEqual(enriched[0]['recent_success_rate_default_branch'], 1.0)
        
        # Legacy/comprehensive metric should be 2/5 = 0.4 (all branches)
        self.assertEqual(enriched[0]['recent_success_rate_all_branches'], 0.4)
    
    def test_success_rate_respects_pipelines_per_project_limit(self):
        """Test that success rate uses only the first 10 pipelines (PIPELINES_PER_PROJECT)"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        # Create more pipelines than PIPELINES_PER_PROJECT (10)
        # First 10 are all failures, later ones are successes
        # Use different hours instead of days to avoid invalid date issues
        pipelines = []
        for i in range(15):
            status = 'failed' if i < 10 else 'success'
            pipelines.append({
                'status': status,
                'ref': 'main',
                'created_at': f'2024-01-20T{23-i:02d}:00:00Z'
            })
        
        per_project_pipelines = {1: pipelines}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        # Should only consider first 10 pipelines (all failed) = 0.0
        # Both default-branch and all-branches rates should be 0.0
        self.assertEqual(enriched[0]['recent_success_rate'], 0.0)
        self.assertEqual(enriched[0]['recent_success_rate_default_branch'], 0.0)
        self.assertEqual(enriched[0]['recent_success_rate_all_branches'], 0.0)
    
    def test_consecutive_failures_still_default_branch_only(self):
        """Test that both success rate and consecutive failures are default-branch-only"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        # Feature branch has many failures, but main branch is healthy
        pipelines = [
            {'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z'},
            {'status': 'failed', 'ref': 'feature/broken', 'created_at': '2024-01-20T09:00:00Z'},
            {'status': 'failed', 'ref': 'feature/broken', 'created_at': '2024-01-20T08:00:00Z'},
            {'status': 'failed', 'ref': 'feature/broken', 'created_at': '2024-01-20T07:00:00Z'},
        ]
        
        per_project_pipelines = {1: pipelines}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        # DSO primary metric: default branch only = 1 success / 1 main pipeline = 1.0
        self.assertEqual(enriched[0]['recent_success_rate'], 1.0)
        self.assertEqual(enriched[0]['recent_success_rate_default_branch'], 1.0)
        
        # Legacy/comprehensive: all branches = 1 success / 4 total = 0.25
        self.assertEqual(enriched[0]['recent_success_rate_all_branches'], 0.25)
        
        # Consecutive failures is 0 (main branch has success)
        self.assertEqual(enriched[0]['consecutive_default_branch_failures'], 0)
    
    def test_success_rate_default_branch_none_when_no_default_branch_pipelines(self):
        """Test that default-branch success rate is None when no default-branch pipelines exist"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        # Only feature branch pipelines, no main branch
        pipelines = [
            {'status': 'success', 'ref': 'feature/new', 'created_at': '2024-01-20T10:00:00Z'},
            {'status': 'failed', 'ref': 'feature/another', 'created_at': '2024-01-20T09:00:00Z'},
        ]
        
        per_project_pipelines = {1: pipelines}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        # Default-branch success rates should be None (no main branch pipelines)
        self.assertIsNone(enriched[0]['recent_success_rate'])
        self.assertIsNone(enriched[0]['recent_success_rate_default_branch'])
        
        # All-branches rate should still work: 1 success / 2 total = 0.5
        self.assertEqual(enriched[0]['recent_success_rate_all_branches'], 0.5)


if __name__ == '__main__':
    # Support both unittest and pytest discovery
    unittest.main()

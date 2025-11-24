#!/usr/bin/env python3
"""
Tests for consecutive failure counting on default branch
Tests that skipped/manual/canceled statuses are ignored when computing consecutive failures
"""

import unittest
import sys
import os

# Add parent directory to path to import server module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import server


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
    """Test that success rate also excludes skipped/manual/canceled"""
    
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
    
    def test_success_rate_only_counts_default_branch(self):
        """Test that success rate only considers default branch pipelines"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        pipelines = [
            {'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z'},
            {'status': 'failed', 'ref': 'feature/new', 'created_at': '2024-01-20T09:00:00Z'},  # ignored
            {'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T08:00:00Z'},
        ]
        
        per_project_pipelines = {1: pipelines}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        # Should be 1 success / 2 main branch pipelines = 0.5
        self.assertEqual(enriched[0]['recent_success_rate'], 0.5)


if __name__ == '__main__':
    # Support both unittest and pytest discovery
    unittest.main()

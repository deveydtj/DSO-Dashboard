#!/usr/bin/env python3
"""
Tests for SLO summary and error budget fields

These tests verify that the backend correctly computes:
- Default-branch pipeline success rate (observed)
- SLO target from configuration
- Error budget remaining percentage
"""

import unittest
import sys
import os

# Add parent directory to path to import from backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend import app as server
from backend.config_loader import DEFAULT_SLO_CONFIG


class TestSLOSummaryComputation(unittest.TestCase):
    """Test SLO metrics computation in BackgroundPoller._calculate_summary"""
    
    def test_all_successful_default_branch_pipelines(self):
        """Test Case 1: All successful default-branch pipelines -> 100% error budget remaining"""
        projects = [
            {'id': 1, 'name': 'project-a', 'default_branch': 'main', 'last_activity_at': '2024-01-01'},
            {'id': 2, 'name': 'project-b', 'default_branch': 'develop', 'last_activity_at': '2024-01-01'},
        ]
        
        pipelines = [
            {'project_id': 1, 'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z'},
            {'project_id': 1, 'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T09:00:00Z'},
            {'project_id': 2, 'status': 'success', 'ref': 'develop', 'created_at': '2024-01-20T10:00:00Z'},
            {'project_id': 2, 'status': 'success', 'ref': 'develop', 'created_at': '2024-01-20T09:00:00Z'},
        ]
        
        # Create poller with default SLO config
        poller = server.BackgroundPoller(None, 60, slo_config={'enabled': True, 'default_branch_success_target': 0.99})
        summary = poller._calculate_summary(projects, pipelines)
        
        # Verify SLO fields are present
        self.assertIn('pipeline_slo_target_default_branch_success_rate', summary)
        self.assertIn('pipeline_slo_observed_default_branch_success_rate', summary)
        self.assertIn('pipeline_slo_total_default_branch_pipelines', summary)
        self.assertIn('pipeline_error_budget_remaining_pct', summary)
        
        # All pipelines succeeded, so observed rate should be 1.0
        self.assertEqual(summary['pipeline_slo_observed_default_branch_success_rate'], 1.0)
        self.assertEqual(summary['pipeline_slo_total_default_branch_pipelines'], 4)
        self.assertEqual(summary['pipeline_slo_target_default_branch_success_rate'], 0.99)
        # 100% error budget remaining (no errors consumed any budget)
        self.assertEqual(summary['pipeline_error_budget_remaining_pct'], 100)
    
    def test_half_failing_default_branch_pipelines(self):
        """Test Case 2: Half failing pipelines with 99% SLO target -> significant budget consumed"""
        projects = [
            {'id': 1, 'name': 'project-a', 'default_branch': 'main', 'last_activity_at': '2024-01-01'},
        ]
        
        # 50% success rate on default branch
        pipelines = [
            {'project_id': 1, 'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z'},
            {'project_id': 1, 'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T09:00:00Z'},
        ]
        
        # With 99% target, error budget is 1% (0.01)
        # Observed rate is 50%, so errors consumed = 50% = 0.5
        # error_budget_spent_fraction = 0.5 / 0.01 = 50, clamped to 1.0
        # error_budget_remaining = 0%
        poller = server.BackgroundPoller(None, 60, slo_config={'enabled': True, 'default_branch_success_target': 0.99})
        summary = poller._calculate_summary(projects, pipelines)
        
        self.assertEqual(summary['pipeline_slo_observed_default_branch_success_rate'], 0.5)
        self.assertEqual(summary['pipeline_slo_total_default_branch_pipelines'], 2)
        # Error budget should be exhausted (way below target)
        self.assertEqual(summary['pipeline_error_budget_remaining_pct'], 0)
    
    def test_slightly_below_target(self):
        """Test observed rate slightly below target consumes partial budget"""
        projects = [
            {'id': 1, 'name': 'project-a', 'default_branch': 'main', 'last_activity_at': '2024-01-01'},
        ]
        
        # 90% success rate (9 success, 1 failure out of 10)
        pipelines = [
            {'project_id': 1, 'status': 'success', 'ref': 'main', 'created_at': f'2024-01-20T{i+10:02d}:00:00Z'}
            for i in range(9)
        ] + [
            {'project_id': 1, 'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T00:00:00Z'}
        ]
        
        # With 90% target (0.90), error budget is 10% (0.10)
        # Observed rate is 90%, error fraction = (1 - 0.9) / 0.1 = 1.0
        # So budget is exactly exhausted
        poller = server.BackgroundPoller(None, 60, slo_config={'enabled': True, 'default_branch_success_target': 0.90})
        summary = poller._calculate_summary(projects, pipelines)
        
        self.assertEqual(summary['pipeline_slo_observed_default_branch_success_rate'], 0.9)
        self.assertEqual(summary['pipeline_slo_total_default_branch_pipelines'], 10)
        # At exactly the target, budget is exactly 0
        self.assertEqual(summary['pipeline_error_budget_remaining_pct'], 0)
    
    def test_above_target_partial_budget_remaining(self):
        """Test observed rate above target keeps budget partially remaining"""
        projects = [
            {'id': 1, 'name': 'project-a', 'default_branch': 'main', 'last_activity_at': '2024-01-01'},
        ]
        
        # 95% success rate (19 success, 1 failure out of 20)
        pipelines = [
            {'project_id': 1, 'status': 'success', 'ref': 'main', 'created_at': f'2024-01-20T{i:02d}:00:00Z'}
            for i in range(19)
        ] + [
            {'project_id': 1, 'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T19:00:00Z'}
        ]
        
        # With 90% target (0.90), error budget is 10% (0.10)
        # Observed rate is 95%, error fraction = (1 - 0.95) / 0.1 = 0.5
        # So 50% of budget is spent, 50% remaining
        poller = server.BackgroundPoller(None, 60, slo_config={'enabled': True, 'default_branch_success_target': 0.90})
        summary = poller._calculate_summary(projects, pipelines)
        
        self.assertEqual(summary['pipeline_slo_observed_default_branch_success_rate'], 0.95)
        self.assertEqual(summary['pipeline_slo_total_default_branch_pipelines'], 20)
        # 50% of budget remaining
        self.assertEqual(summary['pipeline_error_budget_remaining_pct'], 50)
    
    def test_no_meaningful_default_branch_pipelines(self):
        """Test Case 3: No meaningful pipelines -> 100% error budget remaining"""
        projects = [
            {'id': 1, 'name': 'project-a', 'default_branch': 'main', 'last_activity_at': '2024-01-01'},
        ]
        
        # Only skipped/manual/canceled pipelines - no meaningful data
        pipelines = [
            {'project_id': 1, 'status': 'skipped', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z'},
            {'project_id': 1, 'status': 'manual', 'ref': 'main', 'created_at': '2024-01-20T09:00:00Z'},
            {'project_id': 1, 'status': 'canceled', 'ref': 'main', 'created_at': '2024-01-20T08:00:00Z'},
        ]
        
        poller = server.BackgroundPoller(None, 60, slo_config={'enabled': True, 'default_branch_success_target': 0.99})
        summary = poller._calculate_summary(projects, pipelines)
        
        # No meaningful pipelines -> observed rate treated as 1.0
        self.assertEqual(summary['pipeline_slo_observed_default_branch_success_rate'], 1.0)
        self.assertEqual(summary['pipeline_slo_total_default_branch_pipelines'], 0)
        # 100% error budget remaining
        self.assertEqual(summary['pipeline_error_budget_remaining_pct'], 100)
    
    def test_empty_projects_and_pipelines(self):
        """Test empty projects and pipelines -> 100% error budget remaining"""
        projects = []
        pipelines = []
        
        poller = server.BackgroundPoller(None, 60, slo_config={'enabled': True, 'default_branch_success_target': 0.99})
        summary = poller._calculate_summary(projects, pipelines)
        
        # No pipelines -> observed rate treated as 1.0
        self.assertEqual(summary['pipeline_slo_observed_default_branch_success_rate'], 1.0)
        self.assertEqual(summary['pipeline_slo_total_default_branch_pipelines'], 0)
        self.assertEqual(summary['pipeline_error_budget_remaining_pct'], 100)
    
    def test_ignores_feature_branch_pipelines(self):
        """Test that only default-branch pipelines are counted"""
        projects = [
            {'id': 1, 'name': 'project-a', 'default_branch': 'main', 'last_activity_at': '2024-01-01'},
        ]
        
        # Main branch all successful, feature branch all failing
        pipelines = [
            {'project_id': 1, 'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z'},
            {'project_id': 1, 'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T09:00:00Z'},
            {'project_id': 1, 'status': 'failed', 'ref': 'feature/new', 'created_at': '2024-01-20T08:00:00Z'},
            {'project_id': 1, 'status': 'failed', 'ref': 'feature/new', 'created_at': '2024-01-20T07:00:00Z'},
        ]
        
        poller = server.BackgroundPoller(None, 60, slo_config={'enabled': True, 'default_branch_success_target': 0.99})
        summary = poller._calculate_summary(projects, pipelines)
        
        # Only main branch counted -> 2 pipelines, 100% success
        self.assertEqual(summary['pipeline_slo_observed_default_branch_success_rate'], 1.0)
        self.assertEqual(summary['pipeline_slo_total_default_branch_pipelines'], 2)
        self.assertEqual(summary['pipeline_error_budget_remaining_pct'], 100)
    
    def test_ignores_pipelines_from_unknown_projects(self):
        """Test that pipelines from unknown project_ids are ignored"""
        projects = [
            {'id': 1, 'name': 'project-a', 'default_branch': 'main', 'last_activity_at': '2024-01-01'},
        ]
        
        pipelines = [
            {'project_id': 1, 'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z'},
            {'project_id': 999, 'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T09:00:00Z'},  # Unknown project
            {'project_id': None, 'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T08:00:00Z'},  # No project_id
        ]
        
        poller = server.BackgroundPoller(None, 60, slo_config={'enabled': True, 'default_branch_success_target': 0.99})
        summary = poller._calculate_summary(projects, pipelines)
        
        # Only project_id=1 counted
        self.assertEqual(summary['pipeline_slo_total_default_branch_pipelines'], 1)
        self.assertEqual(summary['pipeline_slo_observed_default_branch_success_rate'], 1.0)
    
    def test_uses_default_branch_name_fallback(self):
        """Test that DEFAULT_BRANCH_NAME is used when project has no default_branch"""
        projects = [
            {'id': 1, 'name': 'project-a', 'last_activity_at': '2024-01-01'},  # No default_branch field
        ]
        
        # Pipelines on 'main' (the default fallback)
        pipelines = [
            {'project_id': 1, 'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z'},
            {'project_id': 1, 'status': 'failed', 'ref': 'main', 'created_at': '2024-01-20T09:00:00Z'},
        ]
        
        poller = server.BackgroundPoller(None, 60, slo_config={'enabled': True, 'default_branch_success_target': 0.99})
        summary = poller._calculate_summary(projects, pipelines)
        
        # Should use 'main' as default branch
        self.assertEqual(summary['pipeline_slo_total_default_branch_pipelines'], 2)
        self.assertEqual(summary['pipeline_slo_observed_default_branch_success_rate'], 0.5)
    
    def test_uses_default_slo_config_fallback(self):
        """Test that DEFAULT_SLO_CONFIG is used when slo_config is missing target"""
        projects = [
            {'id': 1, 'name': 'project-a', 'default_branch': 'main', 'last_activity_at': '2024-01-01'},
        ]
        
        pipelines = [
            {'project_id': 1, 'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z'},
        ]
        
        # slo_config with enabled=True but missing target - should use DEFAULT_SLO_CONFIG target
        poller = server.BackgroundPoller(None, 60, slo_config={'enabled': True})
        summary = poller._calculate_summary(projects, pipelines)
        
        # Should use default target from DEFAULT_SLO_CONFIG
        self.assertEqual(
            summary['pipeline_slo_target_default_branch_success_rate'],
            DEFAULT_SLO_CONFIG['default_branch_success_target']
        )


class TestSLOSummaryEdgeCases(unittest.TestCase):
    """Edge case tests for SLO metrics computation"""
    
    def test_cancelled_british_spelling_ignored(self):
        """Test that 'cancelled' (British spelling) is also ignored"""
        projects = [
            {'id': 1, 'name': 'project-a', 'default_branch': 'main', 'last_activity_at': '2024-01-01'},
        ]
        
        pipelines = [
            {'project_id': 1, 'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z'},
            {'project_id': 1, 'status': 'cancelled', 'ref': 'main', 'created_at': '2024-01-20T09:00:00Z'},  # British
        ]
        
        poller = server.BackgroundPoller(None, 60, slo_config={'enabled': True, 'default_branch_success_target': 0.99})
        summary = poller._calculate_summary(projects, pipelines)
        
        # 'cancelled' should be ignored, only 1 meaningful pipeline
        self.assertEqual(summary['pipeline_slo_total_default_branch_pipelines'], 1)
        self.assertEqual(summary['pipeline_slo_observed_default_branch_success_rate'], 1.0)
    
    def test_error_budget_clamped_to_zero(self):
        """Test that error budget is clamped to 0% when severely exceeded"""
        projects = [
            {'id': 1, 'name': 'project-a', 'default_branch': 'main', 'last_activity_at': '2024-01-01'},
        ]
        
        # All pipelines failing
        pipelines = [
            {'project_id': 1, 'status': 'failed', 'ref': 'main', 'created_at': f'2024-01-20T{i:02d}:00:00Z'}
            for i in range(10)
        ]
        
        poller = server.BackgroundPoller(None, 60, slo_config={'enabled': True, 'default_branch_success_target': 0.99})
        summary = poller._calculate_summary(projects, pipelines)
        
        # 0% success rate -> way past budget
        self.assertEqual(summary['pipeline_slo_observed_default_branch_success_rate'], 0.0)
        self.assertEqual(summary['pipeline_error_budget_remaining_pct'], 0)
    
    def test_error_budget_clamped_to_hundred(self):
        """Test that error budget is clamped to 100% maximum"""
        projects = [
            {'id': 1, 'name': 'project-a', 'default_branch': 'main', 'last_activity_at': '2024-01-01'},
        ]
        
        # All pipelines succeeding
        pipelines = [
            {'project_id': 1, 'status': 'success', 'ref': 'main', 'created_at': f'2024-01-20T{i:02d}:00:00Z'}
            for i in range(10)
        ]
        
        poller = server.BackgroundPoller(None, 60, slo_config={'enabled': True, 'default_branch_success_target': 0.99})
        summary = poller._calculate_summary(projects, pipelines)
        
        # 100% success rate -> full budget remaining
        self.assertEqual(summary['pipeline_slo_observed_default_branch_success_rate'], 1.0)
        self.assertEqual(summary['pipeline_error_budget_remaining_pct'], 100)
    
    def test_multiple_projects_with_different_default_branches(self):
        """Test SLO computation across multiple projects with different default branches"""
        projects = [
            {'id': 1, 'name': 'project-a', 'default_branch': 'main', 'last_activity_at': '2024-01-01'},
            {'id': 2, 'name': 'project-b', 'default_branch': 'develop', 'last_activity_at': '2024-01-01'},
            {'id': 3, 'name': 'project-c', 'default_branch': 'master', 'last_activity_at': '2024-01-01'},
        ]
        
        pipelines = [
            # Project 1: 2 success on main
            {'project_id': 1, 'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z'},
            {'project_id': 1, 'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T09:00:00Z'},
            # Project 2: 1 success, 1 failure on develop
            {'project_id': 2, 'status': 'success', 'ref': 'develop', 'created_at': '2024-01-20T10:00:00Z'},
            {'project_id': 2, 'status': 'failed', 'ref': 'develop', 'created_at': '2024-01-20T09:00:00Z'},
            # Project 3: 2 failures on master
            {'project_id': 3, 'status': 'failed', 'ref': 'master', 'created_at': '2024-01-20T10:00:00Z'},
            {'project_id': 3, 'status': 'failed', 'ref': 'master', 'created_at': '2024-01-20T09:00:00Z'},
        ]
        
        poller = server.BackgroundPoller(None, 60, slo_config={'enabled': True, 'default_branch_success_target': 0.99})
        summary = poller._calculate_summary(projects, pipelines)
        
        # Total: 6 pipelines, 3 success, 3 failure -> 50% success rate
        self.assertEqual(summary['pipeline_slo_total_default_branch_pipelines'], 6)
        self.assertEqual(summary['pipeline_slo_observed_default_branch_success_rate'], 0.5)
    
    def test_running_pipelines_counted_as_non_success(self):
        """Test that running pipelines are counted but not as success"""
        projects = [
            {'id': 1, 'name': 'project-a', 'default_branch': 'main', 'last_activity_at': '2024-01-01'},
        ]
        
        pipelines = [
            {'project_id': 1, 'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z'},
            {'project_id': 1, 'status': 'running', 'ref': 'main', 'created_at': '2024-01-20T09:00:00Z'},
        ]
        
        poller = server.BackgroundPoller(None, 60, slo_config={'enabled': True, 'default_branch_success_target': 0.99})
        summary = poller._calculate_summary(projects, pipelines)
        
        # 2 total, 1 success -> 50% success rate
        self.assertEqual(summary['pipeline_slo_total_default_branch_pipelines'], 2)
        self.assertEqual(summary['pipeline_slo_observed_default_branch_success_rate'], 0.5)
    
    def test_pending_pipelines_counted_as_non_success(self):
        """Test that pending pipelines are counted but not as success"""
        projects = [
            {'id': 1, 'name': 'project-a', 'default_branch': 'main', 'last_activity_at': '2024-01-01'},
        ]
        
        pipelines = [
            {'project_id': 1, 'status': 'success', 'ref': 'main', 'created_at': '2024-01-20T10:00:00Z'},
            {'project_id': 1, 'status': 'pending', 'ref': 'main', 'created_at': '2024-01-20T09:00:00Z'},
        ]
        
        poller = server.BackgroundPoller(None, 60, slo_config={'enabled': True, 'default_branch_success_target': 0.99})
        summary = poller._calculate_summary(projects, pipelines)
        
        # 2 total, 1 success -> 50% success rate
        self.assertEqual(summary['pipeline_slo_total_default_branch_pipelines'], 2)
        self.assertEqual(summary['pipeline_slo_observed_default_branch_success_rate'], 0.5)


class TestSLOFieldsInDefaultSummary(unittest.TestCase):
    """Test that SLO fields are NOT present in DEFAULT_SUMMARY (they're only added when enabled)"""
    
    def test_default_summary_excludes_slo_fields(self):
        """Test DEFAULT_SUMMARY does NOT include SLO fields (only added when enabled)"""
        for key in server.SLO_FIELD_KEYS:
            self.assertNotIn(key, server.DEFAULT_SUMMARY, 
                           f"SLO key should not be in DEFAULT_SUMMARY (only added when enabled): {key}")
    
    def test_summary_includes_slo_when_enabled(self):
        """Test that SLO fields are added to summary when SLO is enabled"""
        projects = []
        pipelines = []
        
        # Create poller with SLO enabled
        poller = server.BackgroundPoller(None, 60, slo_config={'enabled': True, 'default_branch_success_target': 0.99})
        summary = poller._calculate_summary(projects, pipelines)
        
        # Verify SLO fields ARE present when enabled
        self.assertIn('pipeline_slo_target_default_branch_success_rate', summary)
        self.assertIn('pipeline_slo_observed_default_branch_success_rate', summary)
        self.assertIn('pipeline_slo_total_default_branch_pipelines', summary)
        self.assertIn('pipeline_error_budget_remaining_pct', summary)
        
        # Verify sensible defaults for empty state
        self.assertEqual(summary['pipeline_slo_target_default_branch_success_rate'], 0.99)
        self.assertEqual(summary['pipeline_slo_observed_default_branch_success_rate'], 1.0)
        self.assertEqual(summary['pipeline_slo_total_default_branch_pipelines'], 0)
        self.assertEqual(summary['pipeline_error_budget_remaining_pct'], 100)
    
    def test_summary_excludes_slo_when_disabled(self):
        """Test that SLO fields are NOT added to summary when SLO is disabled"""
        projects = []
        pipelines = []
        
        # Create poller with SLO disabled (default)
        poller = server.BackgroundPoller(None, 60, slo_config={'enabled': False, 'default_branch_success_target': 0.99})
        summary = poller._calculate_summary(projects, pipelines)
        
        # Verify SLO fields are NOT present when disabled
        self.assertNotIn('pipeline_slo_target_default_branch_success_rate', summary)
        self.assertNotIn('pipeline_slo_observed_default_branch_success_rate', summary)
        self.assertNotIn('pipeline_slo_total_default_branch_pipelines', summary)
        self.assertNotIn('pipeline_error_budget_remaining_pct', summary)


class TestFilterSloFieldsFunction(unittest.TestCase):
    """Test the filter_slo_fields_from_summary() function"""
    
    def test_filter_slo_fields_when_enabled(self):
        """Test that all fields including SLO are preserved when slo_enabled=True"""
        summary = {
            'total_repositories': 5,
            'total_pipelines': 10,
            'pipeline_slo_target_default_branch_success_rate': 0.99,
            'pipeline_slo_observed_default_branch_success_rate': 0.95,
            'pipeline_slo_total_default_branch_pipelines': 8,
            'pipeline_error_budget_remaining_pct': 60,
        }
        
        result = server.filter_slo_fields_from_summary(summary, slo_enabled=True)
        
        # All fields should be preserved
        self.assertIn('total_repositories', result)
        self.assertIn('total_pipelines', result)
        self.assertIn('pipeline_slo_target_default_branch_success_rate', result)
        self.assertIn('pipeline_slo_observed_default_branch_success_rate', result)
        self.assertIn('pipeline_slo_total_default_branch_pipelines', result)
        self.assertIn('pipeline_error_budget_remaining_pct', result)
        
        # Values should be unchanged
        self.assertEqual(result['total_repositories'], 5)
        self.assertEqual(result['pipeline_slo_target_default_branch_success_rate'], 0.99)
    
    def test_filter_slo_fields_when_disabled(self):
        """Test that SLO fields are removed but other fields remain when slo_enabled=False"""
        summary = {
            'total_repositories': 5,
            'total_pipelines': 10,
            'pipeline_success_rate': 0.8,
            'pipeline_slo_target_default_branch_success_rate': 0.99,
            'pipeline_slo_observed_default_branch_success_rate': 0.95,
            'pipeline_slo_total_default_branch_pipelines': 8,
            'pipeline_error_budget_remaining_pct': 60,
        }
        
        result = server.filter_slo_fields_from_summary(summary, slo_enabled=False)
        
        # Non-SLO fields should be preserved
        self.assertIn('total_repositories', result)
        self.assertIn('total_pipelines', result)
        self.assertIn('pipeline_success_rate', result)
        
        # SLO fields should be removed
        self.assertNotIn('pipeline_slo_target_default_branch_success_rate', result)
        self.assertNotIn('pipeline_slo_observed_default_branch_success_rate', result)
        self.assertNotIn('pipeline_slo_total_default_branch_pipelines', result)
        self.assertNotIn('pipeline_error_budget_remaining_pct', result)
        
        # Non-SLO values should be unchanged
        self.assertEqual(result['total_repositories'], 5)
        self.assertEqual(result['total_pipelines'], 10)
        self.assertEqual(result['pipeline_success_rate'], 0.8)
    
    def test_filter_slo_fields_with_missing_slo_fields(self):
        """Test that filtering works correctly when SLO fields are already absent"""
        summary = {
            'total_repositories': 5,
            'total_pipelines': 10,
        }
        
        result = server.filter_slo_fields_from_summary(summary, slo_enabled=False)
        
        # Non-SLO fields should be preserved
        self.assertIn('total_repositories', result)
        self.assertIn('total_pipelines', result)
        
        # Should not raise errors even though SLO fields aren't present
        self.assertEqual(result['total_repositories'], 5)
    
    def test_filter_slo_fields_preserves_all_slo_field_keys(self):
        """Test that all keys in SLO_FIELD_KEYS are handled correctly"""
        # Create summary with all SLO fields
        summary = {'base_field': 'value'}
        for key in server.SLO_FIELD_KEYS:
            summary[key] = f'test_value_{key}'
        
        result = server.filter_slo_fields_from_summary(summary, slo_enabled=False)
        
        # Base field should remain
        self.assertIn('base_field', result)
        
        # All SLO fields should be removed
        for key in server.SLO_FIELD_KEYS:
            self.assertNotIn(key, result, f"SLO field {key} should be removed when disabled")


if __name__ == '__main__':
    unittest.main()

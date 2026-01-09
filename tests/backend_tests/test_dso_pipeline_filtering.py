#!/usr/bin/env python3
"""
Tests for DSO-mode filtering in /api/pipelines endpoint

This test suite validates:
1. Default behavior (dso_only=false) returns all pipelines for backward compatibility
2. dso_only=true filters to DSO-relevant pipelines only
3. dso_only=false returns all pipelines (subject to other filters)
4. Verified unknown failures (unknown + classification_attempted=true) are included
5. Unclassified failures (unclassified or unknown without classification) are excluded
6. Code failures are excluded when dso_only=true
7. Infra failures are always included when dso_only=true
8. Non-failing pipelines are always included
9. Scope filtering (default_branch vs all) works correctly
"""

import unittest
import sys
import os
from unittest.mock import MagicMock

# Add parent directory to path to import backend.app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend import app as server


class TestDSOPipelineFiltering(unittest.TestCase):
    """Test DSO-mode filtering in /api/pipelines endpoint"""
    
    def setUp(self):
        """Set up STATE with pipelines having different failure domains"""
        # Create a comprehensive set of test pipelines covering all failure domains
        test_pipelines = [
            # Non-failing pipelines (should always be included)
            {'id': 1, 'status': 'success', 'project_name': 'proj1', 'project_id': 100, 'ref': 'main',
             'failure_domain': None, 'classification_attempted': None},
            {'id': 2, 'status': 'running', 'project_name': 'proj1', 'project_id': 100, 'ref': 'main',
             'failure_domain': None, 'classification_attempted': None},
            
            # Infra failures (should be included in DSO mode)
            {'id': 3, 'status': 'failed', 'project_name': 'proj1', 'project_id': 100, 'ref': 'main',
             'failure_domain': 'infra', 'failure_category': 'runner_timeout', 'classification_attempted': True},
            {'id': 4, 'status': 'failed', 'project_name': 'proj2', 'project_id': 101, 'ref': 'main',
             'failure_domain': 'infra', 'failure_category': 'pod_timeout', 'classification_attempted': True},
            
            # Code failures (should be excluded in DSO mode)
            {'id': 5, 'status': 'failed', 'project_name': 'proj1', 'project_id': 100, 'ref': 'feature-branch',
             'failure_domain': 'code', 'failure_category': 'script_failure', 'classification_attempted': True},
            {'id': 6, 'status': 'failed', 'project_name': 'proj2', 'project_id': 101, 'ref': 'main',
             'failure_domain': 'code', 'failure_category': 'test_failure', 'classification_attempted': True},
            
            # Verified unknown failures (classification attempted, should be included in DSO mode)
            {'id': 7, 'status': 'failed', 'project_name': 'proj1', 'project_id': 100, 'ref': 'main',
             'failure_domain': 'unknown', 'failure_category': 'generic_failure', 'classification_attempted': True},
            {'id': 8, 'status': 'failed', 'project_name': 'proj3', 'project_id': 102, 'ref': 'main',
             'failure_domain': 'unknown', 'failure_category': None, 'classification_attempted': True},
            
            # Unverified unknown failures (no classification, should be excluded in DSO mode)
            {'id': 9, 'status': 'failed', 'project_name': 'proj1', 'project_id': 100, 'ref': 'feature-branch',
             'failure_domain': 'unknown', 'failure_category': None, 'classification_attempted': False},
            
            # Unclassified failures (should be excluded in DSO mode)
            {'id': 10, 'status': 'failed', 'project_name': 'proj2', 'project_id': 101, 'ref': 'main',
             'failure_domain': 'unclassified', 'failure_category': None, 'classification_attempted': False},
            {'id': 11, 'status': 'failed', 'project_name': 'proj3', 'project_id': 102, 'ref': 'feature-branch',
             'failure_domain': 'unclassified', 'failure_category': None, 'classification_attempted': False},
        ]
        
        # Add required fields for all pipelines
        for pipeline in test_pipelines:
            pipeline.setdefault('project_path', f"group/{pipeline['project_name']}")
            pipeline.setdefault('created_at', '2024-01-01T12:00:00Z')
            pipeline.setdefault('sha', 'abc12345')
            pipeline.setdefault('web_url', f"https://gitlab.com/pipeline/{pipeline['id']}")
            pipeline.setdefault('is_merge_request', False)
        
        # Create projects with default branch info
        test_projects = [
            {'id': 100, 'name': 'proj1', 'path_with_namespace': 'group/proj1', 'default_branch': 'main'},
            {'id': 101, 'name': 'proj2', 'path_with_namespace': 'group/proj2', 'default_branch': 'main'},
            {'id': 102, 'name': 'proj3', 'path_with_namespace': 'group/proj3', 'default_branch': 'main'},
        ]
        
        server.update_state_atomic({
            'projects': test_projects,
            'pipelines': test_pipelines,
            'summary': dict(server.DEFAULT_SUMMARY)
        })
    
    def tearDown(self):
        """Clean up after tests"""
        pass
    
    def test_default_dso_only_filters_correctly(self):
        """Test default behavior (dso_only=false) returns all pipelines"""
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.path = '/api/pipelines'  # No query params, should default to dso_only=false
        handler.send_json_response = MagicMock()
        
        server.DashboardRequestHandler.handle_pipelines(handler)
        
        handler.send_json_response.assert_called_once()
        response = handler.send_json_response.call_args[0][0]
        
        # Verify response structure
        self.assertIn('pipelines', response)
        pipelines = response['pipelines']
        
        # Default behavior should return all 11 pipelines (no filtering)
        self.assertEqual(len(pipelines), 11, f"Expected 11 pipelines with default dso_only=false, got {len(pipelines)}")
    
    def test_dso_only_true_filters_correctly(self):
        """Test dso_only=true filters to DSO-relevant pipelines only"""
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.path = '/api/pipelines?dso_only=true'
        handler.send_json_response = MagicMock()
        
        server.DashboardRequestHandler.handle_pipelines(handler)
        
        handler.send_json_response.assert_called_once()
        response = handler.send_json_response.call_args[0][0]
        
        # Verify response structure
        self.assertIn('pipelines', response)
        pipelines = response['pipelines']
        pipeline_ids = [p['id'] for p in pipelines]
        
        # Should include: success (1), running (2), infra (3, 4), verified unknown (7, 8)
        # Should exclude: code (5, 6), unverified unknown (9), unclassified (10, 11)
        self.assertIn(1, pipeline_ids, "Success pipeline should be included")
        self.assertIn(2, pipeline_ids, "Running pipeline should be included")
        self.assertIn(3, pipeline_ids, "Infra failure should be included")
        self.assertIn(4, pipeline_ids, "Infra failure should be included")
        self.assertIn(7, pipeline_ids, "Verified unknown failure should be included")
        self.assertIn(8, pipeline_ids, "Verified unknown failure should be included")
        
        self.assertNotIn(5, pipeline_ids, "Code failure should be excluded")
        self.assertNotIn(6, pipeline_ids, "Code failure should be excluded")
        self.assertNotIn(9, pipeline_ids, "Unverified unknown failure should be excluded")
        self.assertNotIn(10, pipeline_ids, "Unclassified failure should be excluded")
        self.assertNotIn(11, pipeline_ids, "Unclassified failure should be excluded")
        
        # Total should be 6 (1 success + 1 running + 2 infra + 2 verified unknown)
        self.assertEqual(len(pipelines), 6, f"Expected 6 pipelines with dso_only=true, got {len(pipelines)}")
    
    def test_dso_only_false_returns_all_pipelines(self):
        """Test dso_only=false returns all pipelines (no DSO filtering)"""
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.path = '/api/pipelines?dso_only=false'
        handler.send_json_response = MagicMock()
        
        server.DashboardRequestHandler.handle_pipelines(handler)
        
        handler.send_json_response.assert_called_once()
        response = handler.send_json_response.call_args[0][0]
        pipelines = response['pipelines']
        
        # Should include all 11 test pipelines
        self.assertEqual(len(pipelines), 11, f"Expected 11 pipelines with dso_only=false, got {len(pipelines)}")
        
        # Verify all pipeline IDs are present
        pipeline_ids = [p['id'] for p in pipelines]
        for expected_id in range(1, 12):
            self.assertIn(expected_id, pipeline_ids, f"Pipeline {expected_id} should be included with dso_only=false")
    
    def test_dso_only_with_limit(self):
        """Test DSO filtering applies before limit"""
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.path = '/api/pipelines?dso_only=true&limit=3'
        handler.send_json_response = MagicMock()
        
        server.DashboardRequestHandler.handle_pipelines(handler)
        
        handler.send_json_response.assert_called_once()
        response = handler.send_json_response.call_args[0][0]
        pipelines = response['pipelines']
        
        # Should return first 3 pipelines after DSO filtering
        self.assertEqual(len(pipelines), 3, "Should limit to 3 pipelines")
        
        # Verify total_before_limit shows the full filtered count
        self.assertEqual(response['total_before_limit'], 6, "total_before_limit should show 6 (all DSO-filtered pipelines)")
    
    def test_verified_unknown_included_unclassified_excluded(self):
        """Test that verified unknowns are included but unclassified are excluded"""
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.path = '/api/pipelines?dso_only=true&status=failed'
        handler.send_json_response = MagicMock()
        
        server.DashboardRequestHandler.handle_pipelines(handler)
        
        handler.send_json_response.assert_called_once()
        response = handler.send_json_response.call_args[0][0]
        pipelines = response['pipelines']
        pipeline_ids = [p['id'] for p in pipelines]
        
        # Should include verified unknown (7, 8) and infra (3, 4)
        self.assertIn(7, pipeline_ids, "Verified unknown (classification_attempted=true) should be included")
        self.assertIn(8, pipeline_ids, "Verified unknown (classification_attempted=true) should be included")
        
        # Should exclude unverified unknown (9) and unclassified (10, 11)
        self.assertNotIn(9, pipeline_ids, "Unverified unknown (classification_attempted=false) should be excluded")
        self.assertNotIn(10, pipeline_ids, "Unclassified failure should be excluded")
        self.assertNotIn(11, pipeline_ids, "Unclassified failure should be excluded")
        
        # Should also exclude code failures (5, 6)
        self.assertNotIn(5, pipeline_ids, "Code failure should be excluded")
        self.assertNotIn(6, pipeline_ids, "Code failure should be excluded")
    
    def test_scope_default_branch_only(self):
        """Test scope=default_branch filters to default branch pipelines only"""
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.path = '/api/pipelines?scope=default_branch&dso_only=false'
        handler.send_json_response = MagicMock()
        
        server.DashboardRequestHandler.handle_pipelines(handler)
        
        handler.send_json_response.assert_called_once()
        response = handler.send_json_response.call_args[0][0]
        pipelines = response['pipelines']
        
        # All returned pipelines should be on default branch (main)
        for pipeline in pipelines:
            self.assertEqual(pipeline['ref'], 'main', "All pipelines should be on default branch with scope=default_branch")
        
        # Should exclude feature-branch pipelines (5, 9, 11)
        pipeline_ids = [p['id'] for p in pipelines]
        self.assertNotIn(5, pipeline_ids, "Feature branch pipeline should be excluded")
        self.assertNotIn(9, pipeline_ids, "Feature branch pipeline should be excluded")
        self.assertNotIn(11, pipeline_ids, "Feature branch pipeline should be excluded")
    
    def test_scope_all_includes_all_branches(self):
        """Test scope=all (default) includes all branch pipelines"""
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.path = '/api/pipelines?scope=all&dso_only=false'
        handler.send_json_response = MagicMock()
        
        server.DashboardRequestHandler.handle_pipelines(handler)
        
        handler.send_json_response.assert_called_once()
        response = handler.send_json_response.call_args[0][0]
        pipelines = response['pipelines']
        
        # Should include all 11 pipelines (both main and feature branches)
        self.assertEqual(len(pipelines), 11, "scope=all should include all branch pipelines")
        
        # Verify both main and feature-branch refs are present
        refs = {p['ref'] for p in pipelines}
        self.assertIn('main', refs, "Should include main branch pipelines")
        self.assertIn('feature-branch', refs, "Should include feature branch pipelines")
    
    def test_dso_only_with_user_filters(self):
        """Test DSO filtering combines correctly with user filters (status, project)"""
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.path = '/api/pipelines?dso_only=true&status=failed&project=proj1'
        handler.send_json_response = MagicMock()
        
        server.DashboardRequestHandler.handle_pipelines(handler)
        
        handler.send_json_response.assert_called_once()
        response = handler.send_json_response.call_args[0][0]
        pipelines = response['pipelines']
        pipeline_ids = [p['id'] for p in pipelines]
        
        # Should include only DSO-relevant, failed, proj1 pipelines
        # Expected: infra failure (3), verified unknown (7)
        self.assertIn(3, pipeline_ids, "proj1 infra failure should be included")
        self.assertIn(7, pipeline_ids, "proj1 verified unknown failure should be included")
        
        # Should exclude:
        # - proj1 code failure (5) - excluded by DSO filter
        # - proj2/proj3 pipelines - excluded by project filter
        # - success/running pipelines - excluded by status filter
        self.assertNotIn(5, pipeline_ids, "proj1 code failure should be excluded by DSO filter")
        self.assertEqual(len(pipelines), 2, f"Expected 2 pipelines (proj1 infra + verified unknown), got {len(pipelines)}")
    
    def test_dso_only_parameter_variations(self):
        """Test different boolean representations for dso_only parameter"""
        # Test various truthy values
        for dso_value in ['true', 'True', 'TRUE', '1', 'yes']:
            handler = MagicMock(spec=server.DashboardRequestHandler)
            handler.path = f'/api/pipelines?dso_only={dso_value}'
            handler.send_json_response = MagicMock()
            
            server.DashboardRequestHandler.handle_pipelines(handler)
            
            response = handler.send_json_response.call_args[0][0]
            pipelines = response['pipelines']
            
            # Should filter (6 pipelines expected)
            self.assertEqual(len(pipelines), 6, f"dso_only={dso_value} should filter to 6 pipelines")
        
        # Test various falsy values
        for dso_value in ['false', 'False', 'FALSE', '0', 'no']:
            handler = MagicMock(spec=server.DashboardRequestHandler)
            handler.path = f'/api/pipelines?dso_only={dso_value}'
            handler.send_json_response = MagicMock()
            
            server.DashboardRequestHandler.handle_pipelines(handler)
            
            response = handler.send_json_response.call_args[0][0]
            pipelines = response['pipelines']
            
            # Should not filter (11 pipelines expected)
            self.assertEqual(len(pipelines), 11, f"dso_only={dso_value} should not filter (11 pipelines)")
    
    def test_invalid_scope_parameter_returns_400(self):
        """Test invalid scope parameter returns 400 error"""
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.path = '/api/pipelines?scope=invalid&dso_only=false'
        handler.send_json_response = MagicMock()
        
        server.DashboardRequestHandler.handle_pipelines(handler)
        
        handler.send_json_response.assert_called_once()
        # Should be called with status=400
        call_args = handler.send_json_response.call_args
        response = call_args[0][0]
        status = call_args[1].get('status', 200) if len(call_args) > 1 else 200
        
        self.assertEqual(status, 400, "Invalid scope should return 400 status")
        self.assertIn('error', response, "Response should contain error message")
        self.assertIn('scope', response['error'].lower(), "Error message should mention 'scope'")
    
    def test_backward_compatibility_no_query_params(self):
        """Test backward compatibility: no query params returns all pipelines (dso_only=false default)"""
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.path = '/api/pipelines'  # No query params at all
        handler.send_json_response = MagicMock()
        
        server.DashboardRequestHandler.handle_pipelines(handler)
        
        handler.send_json_response.assert_called_once()
        response = handler.send_json_response.call_args[0][0]
        pipelines = response['pipelines']
        
        # Default behavior should NOT filter (dso_only=false by default for backward compatibility)
        # Should get all 11 pipelines
        self.assertEqual(len(pipelines), 11, "Default behavior should NOT apply DSO filtering for backward compatibility")


if __name__ == '__main__':
    unittest.main()

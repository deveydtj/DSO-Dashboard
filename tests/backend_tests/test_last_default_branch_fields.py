#!/usr/bin/env python3
"""
Tests for last_default_branch_* fields in enrich_projects_with_pipelines.

These fields provide explicit default-branch pipeline info so the UI can
reliably show default-branch-only chip even when last_pipeline_* is from
a non-default branch.
"""

import unittest
import sys
import os

# Add parent directory to path to import from backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend import app as server


class TestLastDefaultBranchPipelineFields(unittest.TestCase):
    """Test last_default_branch_pipeline_* fields are correctly populated"""
    
    def test_fields_populated_when_default_branch_pipeline_exists(self):
        """Test all last_default_branch_* fields are set when default branch has pipelines"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        pipelines = [
            {
                'status': 'success', 
                'ref': 'main', 
                'duration': 245,
                'updated_at': '2024-01-20T10:35:00Z',
                'created_at': '2024-01-20T10:00:00Z'
            },
        ]
        
        per_project_pipelines = {1: pipelines}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        self.assertEqual(enriched[0]['last_default_branch_pipeline_status'], 'success')
        self.assertEqual(enriched[0]['last_default_branch_pipeline_ref'], 'main')
        self.assertEqual(enriched[0]['last_default_branch_pipeline_duration'], 245)
        self.assertEqual(enriched[0]['last_default_branch_pipeline_updated_at'], '2024-01-20T10:35:00Z')
    
    def test_fields_null_when_no_default_branch_pipelines(self):
        """Test last_default_branch_* fields are null when only non-default branch pipelines exist"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        # Only feature branch pipelines, no main branch pipelines
        pipelines = [
            {
                'status': 'success', 
                'ref': 'feature/new', 
                'duration': 180,
                'updated_at': '2024-01-20T10:35:00Z',
                'created_at': '2024-01-20T10:00:00Z'
            },
            {
                'status': 'failed', 
                'ref': 'develop', 
                'duration': 120,
                'updated_at': '2024-01-20T09:35:00Z',
                'created_at': '2024-01-20T09:00:00Z'
            },
        ]
        
        per_project_pipelines = {1: pipelines}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        # last_default_branch_* fields should be null
        self.assertIsNone(enriched[0]['last_default_branch_pipeline_status'])
        self.assertIsNone(enriched[0]['last_default_branch_pipeline_ref'])
        self.assertIsNone(enriched[0]['last_default_branch_pipeline_duration'])
        self.assertIsNone(enriched[0]['last_default_branch_pipeline_updated_at'])
        
        # last_pipeline_* fields should still reflect the most recent overall pipeline
        self.assertEqual(enriched[0]['last_pipeline_status'], 'success')
        self.assertEqual(enriched[0]['last_pipeline_ref'], 'feature/new')
    
    def test_fields_null_when_no_pipelines(self):
        """Test last_default_branch_* fields are null when project has no pipelines"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        per_project_pipelines = {}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        self.assertIsNone(enriched[0]['last_default_branch_pipeline_status'])
        self.assertIsNone(enriched[0]['last_default_branch_pipeline_ref'])
        self.assertIsNone(enriched[0]['last_default_branch_pipeline_duration'])
        self.assertIsNone(enriched[0]['last_default_branch_pipeline_updated_at'])
    
    def test_fields_reflect_most_recent_default_branch_pipeline(self):
        """Test last_default_branch_* fields reflect the most recent default-branch pipeline"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        # Mix of pipelines - feature branch is most recent overall, but we want
        # the most recent default-branch pipeline info
        pipelines = [
            {
                'status': 'running', 
                'ref': 'feature/new', 
                'duration': None,
                'updated_at': '2024-01-20T12:00:00Z',
                'created_at': '2024-01-20T11:55:00Z'
            },
            {
                'status': 'failed', 
                'ref': 'main', 
                'duration': 300,
                'updated_at': '2024-01-20T11:00:00Z',
                'created_at': '2024-01-20T10:55:00Z'
            },
            {
                'status': 'success', 
                'ref': 'main', 
                'duration': 250,
                'updated_at': '2024-01-20T10:00:00Z',
                'created_at': '2024-01-20T09:55:00Z'
            },
        ]
        
        per_project_pipelines = {1: pipelines}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        # last_pipeline_* should reflect the most recent overall (feature branch)
        self.assertEqual(enriched[0]['last_pipeline_status'], 'running')
        self.assertEqual(enriched[0]['last_pipeline_ref'], 'feature/new')
        
        # last_default_branch_* should reflect the most recent default-branch pipeline
        self.assertEqual(enriched[0]['last_default_branch_pipeline_status'], 'failed')
        self.assertEqual(enriched[0]['last_default_branch_pipeline_ref'], 'main')
        self.assertEqual(enriched[0]['last_default_branch_pipeline_duration'], 300)
        self.assertEqual(enriched[0]['last_default_branch_pipeline_updated_at'], '2024-01-20T11:00:00Z')


class TestLastDefaultBranchFieldsWithDifferentBranches(unittest.TestCase):
    """Test last_default_branch_* fields with various default branch configurations"""
    
    def test_with_non_main_default_branch(self):
        """Test fields work correctly when default_branch is not 'main'"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'develop'  # Non-standard default branch
        }
        
        pipelines = [
            {
                'status': 'success', 
                'ref': 'main',  # This is NOT the default branch
                'duration': 100,
                'updated_at': '2024-01-20T12:00:00Z',
                'created_at': '2024-01-20T11:55:00Z'
            },
            {
                'status': 'failed', 
                'ref': 'develop',  # This IS the default branch
                'duration': 200,
                'updated_at': '2024-01-20T11:00:00Z',
                'created_at': '2024-01-20T10:55:00Z'
            },
        ]
        
        per_project_pipelines = {1: pipelines}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        # last_default_branch_* should use 'develop' pipelines
        self.assertEqual(enriched[0]['last_default_branch_pipeline_status'], 'failed')
        self.assertEqual(enriched[0]['last_default_branch_pipeline_ref'], 'develop')
        self.assertEqual(enriched[0]['last_default_branch_pipeline_duration'], 200)
    
    def test_with_missing_default_branch_uses_fallback(self):
        """Test that missing default_branch uses 'main' as fallback"""
        project = {
            'id': 1,
            'name': 'test-project'
            # No default_branch specified - should fallback to 'main'
        }
        
        pipelines = [
            {
                'status': 'success', 
                'ref': 'main', 
                'duration': 150,
                'updated_at': '2024-01-20T10:35:00Z',
                'created_at': '2024-01-20T10:00:00Z'
            },
        ]
        
        per_project_pipelines = {1: pipelines}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        # Should find 'main' branch pipeline using fallback default
        self.assertEqual(enriched[0]['last_default_branch_pipeline_status'], 'success')
        self.assertEqual(enriched[0]['last_default_branch_pipeline_ref'], 'main')


class TestLastDefaultBranchFieldsBackwardCompatibility(unittest.TestCase):
    """Test that last_pipeline_* fields remain unchanged for backward compatibility"""
    
    def test_last_pipeline_fields_unchanged(self):
        """Test last_pipeline_* fields are not affected by new fields"""
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main'
        }
        
        pipelines = [
            {
                'status': 'running', 
                'ref': 'feature/test', 
                'duration': None,
                'updated_at': '2024-01-20T12:00:00Z',
                'created_at': '2024-01-20T11:55:00Z'
            },
            {
                'status': 'success', 
                'ref': 'main', 
                'duration': 245,
                'updated_at': '2024-01-20T10:35:00Z',
                'created_at': '2024-01-20T10:00:00Z'
            },
        ]
        
        per_project_pipelines = {1: pipelines}
        
        poller = server.BackgroundPoller(None, 60)
        enriched = poller._enrich_projects_with_pipelines([project], per_project_pipelines)
        
        # last_pipeline_* should still reflect the most recent overall pipeline
        # (regardless of branch) for backward compatibility
        self.assertEqual(enriched[0]['last_pipeline_status'], 'running')
        self.assertEqual(enriched[0]['last_pipeline_ref'], 'feature/test')
        self.assertIsNone(enriched[0]['last_pipeline_duration'])
        self.assertEqual(enriched[0]['last_pipeline_updated_at'], '2024-01-20T12:00:00Z')
        
        # New fields should reflect default-branch pipeline
        self.assertEqual(enriched[0]['last_default_branch_pipeline_status'], 'success')
        self.assertEqual(enriched[0]['last_default_branch_pipeline_ref'], 'main')
        self.assertEqual(enriched[0]['last_default_branch_pipeline_duration'], 245)


class TestGetRepositoriesIncludesNewFields(unittest.TestCase):
    """Test that get_repositories includes the new last_default_branch_* fields"""
    
    def test_get_repositories_includes_all_new_fields(self):
        """Test get_repositories includes all last_default_branch_* fields"""
        from backend.gitlab_client import get_repositories
        
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main',
            'last_default_branch_pipeline_status': 'success',
            'last_default_branch_pipeline_ref': 'main',
            'last_default_branch_pipeline_duration': 245,
            'last_default_branch_pipeline_updated_at': '2024-01-20T10:35:00Z',
        }
        
        repos = get_repositories([project])
        
        self.assertEqual(len(repos), 1)
        self.assertEqual(repos[0]['last_default_branch_pipeline_status'], 'success')
        self.assertEqual(repos[0]['last_default_branch_pipeline_ref'], 'main')
        self.assertEqual(repos[0]['last_default_branch_pipeline_duration'], 245)
        self.assertEqual(repos[0]['last_default_branch_pipeline_updated_at'], '2024-01-20T10:35:00Z')
    
    def test_get_repositories_handles_null_new_fields(self):
        """Test get_repositories correctly handles null new fields"""
        from backend.gitlab_client import get_repositories
        
        project = {
            'id': 1,
            'name': 'test-project',
            'default_branch': 'main',
            # No last_default_branch_* fields - should be null in output
        }
        
        repos = get_repositories([project])
        
        self.assertEqual(len(repos), 1)
        self.assertIsNone(repos[0]['last_default_branch_pipeline_status'])
        self.assertIsNone(repos[0]['last_default_branch_pipeline_ref'])
        self.assertIsNone(repos[0]['last_default_branch_pipeline_duration'])
        self.assertIsNone(repos[0]['last_default_branch_pipeline_updated_at'])


if __name__ == '__main__':
    unittest.main()

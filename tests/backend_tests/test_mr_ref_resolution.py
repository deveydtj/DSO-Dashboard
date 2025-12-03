#!/usr/bin/env python3
"""
Tests for merge request ref resolution functionality

Tests BE-1: get_merge_request helper
Tests BE-2: resolve_merge_request_refs method
Tests BE-3: Integration into pipeline fetch flow
Tests BE-4: Logging and safety
"""

import unittest
import sys
import os
from unittest.mock import MagicMock, patch, call

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend.gitlab_client import GitLabAPIClient


class TestGetMergeRequest(unittest.TestCase):
    """Tests for BE-1: get_merge_request helper method"""
    
    def setUp(self):
        """Create a GitLab client instance for testing"""
        self.client = GitLabAPIClient(
            'https://gitlab.example.com',
            'test-token',
            per_page=10
        )
    
    def test_get_merge_request_success(self):
        """Test successful merge request fetch"""
        mock_mr_data = {
            'iid': 481,
            'title': 'Test MR',
            'source_branch': 'feature/foo',
            'target_branch': 'main'
        }
        
        with patch.object(self.client, 'gitlab_request') as mock_request:
            mock_request.return_value = {'data': mock_mr_data}
            
            result = self.client.get_merge_request(123, 481)
            
            self.assertEqual(result['source_branch'], 'feature/foo')
            self.assertEqual(result['iid'], 481)
            mock_request.assert_called_once_with('projects/123/merge_requests/481')
    
    def test_get_merge_request_api_error(self):
        """Test merge request fetch when API returns error"""
        with patch.object(self.client, 'gitlab_request') as mock_request:
            mock_request.return_value = None
            
            result = self.client.get_merge_request(123, 481)
            
            self.assertIsNone(result)
    
    def test_get_merge_request_empty_data(self):
        """Test merge request fetch when API returns empty data"""
        with patch.object(self.client, 'gitlab_request') as mock_request:
            mock_request.return_value = {'data': None}
            
            result = self.client.get_merge_request(123, 481)
            
            self.assertIsNone(result)


class TestResolveMergeRequestRefs(unittest.TestCase):
    """Tests for BE-2: resolve_merge_request_refs method"""
    
    def setUp(self):
        """Create a GitLab client instance for testing"""
        self.client = GitLabAPIClient(
            'https://gitlab.example.com',
            'test-token',
            per_page=10
        )
    
    def test_resolve_single_mr_ref(self):
        """Test resolving a single MR pipeline ref"""
        pipelines = [
            {
                'id': 1,
                'project_id': 123,
                'ref': 'refs/merge-requests/481/head',
                'status': 'success'
            }
        ]
        
        mock_mr = {'source_branch': 'feature/foo', 'iid': 481}
        
        with patch.object(self.client, 'get_merge_request') as mock_get_mr:
            mock_get_mr.return_value = mock_mr
            
            self.client.resolve_merge_request_refs(pipelines)
            
            # Verify pipeline was mutated correctly
            self.assertEqual(pipelines[0]['ref'], 'feature/foo')
            self.assertEqual(pipelines[0]['original_ref'], 'refs/merge-requests/481/head')
            self.assertEqual(pipelines[0]['merge_request_iid'], '481')
    
    def test_resolve_multiple_mr_refs_same_project(self):
        """Test resolving multiple MR refs in the same project"""
        pipelines = [
            {'id': 1, 'project_id': 123, 'ref': 'refs/merge-requests/481/head'},
            {'id': 2, 'project_id': 123, 'ref': 'refs/merge-requests/482/head'},
        ]
        
        def mock_get_mr(project_id, mr_iid):
            if mr_iid == '481':
                return {'source_branch': 'feature/foo'}
            elif mr_iid == '482':
                return {'source_branch': 'feature/bar'}
            return None
        
        with patch.object(self.client, 'get_merge_request', side_effect=mock_get_mr):
            self.client.resolve_merge_request_refs(pipelines)
            
            self.assertEqual(pipelines[0]['ref'], 'feature/foo')
            self.assertEqual(pipelines[1]['ref'], 'feature/bar')
    
    def test_resolve_mr_refs_different_projects(self):
        """Test resolving MR refs across different projects"""
        pipelines = [
            {'id': 1, 'project_id': 100, 'ref': 'refs/merge-requests/1/head'},
            {'id': 2, 'project_id': 200, 'ref': 'refs/merge-requests/2/head'},
        ]
        
        def mock_get_mr(project_id, mr_iid):
            if project_id == 100 and mr_iid == '1':
                return {'source_branch': 'branch-a'}
            elif project_id == 200 and mr_iid == '2':
                return {'source_branch': 'branch-b'}
            return None
        
        with patch.object(self.client, 'get_merge_request', side_effect=mock_get_mr):
            self.client.resolve_merge_request_refs(pipelines)
            
            self.assertEqual(pipelines[0]['ref'], 'branch-a')
            self.assertEqual(pipelines[1]['ref'], 'branch-b')
    
    def test_normal_refs_unchanged(self):
        """Test that normal (non-MR) refs are not modified"""
        pipelines = [
            {'id': 1, 'project_id': 123, 'ref': 'main', 'status': 'success'},
            {'id': 2, 'project_id': 123, 'ref': 'develop', 'status': 'running'},
            {'id': 3, 'project_id': 123, 'ref': 'feature/something', 'status': 'failed'},
        ]
        
        original_refs = [p['ref'] for p in pipelines]
        
        with patch.object(self.client, 'get_merge_request') as mock_get_mr:
            self.client.resolve_merge_request_refs(pipelines)
            
            # get_merge_request should never be called for normal refs
            mock_get_mr.assert_not_called()
            
            # All refs should remain unchanged
            for i, pipeline in enumerate(pipelines):
                self.assertEqual(pipeline['ref'], original_refs[i])
                self.assertNotIn('original_ref', pipeline)
                self.assertNotIn('merge_request_iid', pipeline)
    
    def test_mixed_mr_and_normal_refs(self):
        """Test handling mix of MR and normal refs"""
        pipelines = [
            {'id': 1, 'project_id': 123, 'ref': 'main'},
            {'id': 2, 'project_id': 123, 'ref': 'refs/merge-requests/100/head'},
            {'id': 3, 'project_id': 123, 'ref': 'develop'},
        ]
        
        with patch.object(self.client, 'get_merge_request') as mock_get_mr:
            mock_get_mr.return_value = {'source_branch': 'feature/test'}
            
            self.client.resolve_merge_request_refs(pipelines)
            
            # Only MR ref should be modified
            self.assertEqual(pipelines[0]['ref'], 'main')
            self.assertNotIn('original_ref', pipelines[0])
            
            self.assertEqual(pipelines[1]['ref'], 'feature/test')
            self.assertEqual(pipelines[1]['original_ref'], 'refs/merge-requests/100/head')
            self.assertEqual(pipelines[1]['merge_request_iid'], '100')
            
            self.assertEqual(pipelines[2]['ref'], 'develop')
            self.assertNotIn('original_ref', pipelines[2])
    
    def test_failed_mr_lookup_keeps_original_ref(self):
        """Test that failed MR lookups leave ref unchanged"""
        pipelines = [
            {'id': 1, 'project_id': 123, 'ref': 'refs/merge-requests/999/head'},
        ]
        
        with patch.object(self.client, 'get_merge_request') as mock_get_mr:
            mock_get_mr.return_value = None  # Simulate API failure
            
            self.client.resolve_merge_request_refs(pipelines)
            
            # Ref should remain unchanged
            self.assertEqual(pipelines[0]['ref'], 'refs/merge-requests/999/head')
            self.assertNotIn('original_ref', pipelines[0])
            self.assertNotIn('merge_request_iid', pipelines[0])
    
    def test_mr_without_source_branch(self):
        """Test handling MR response without source_branch field"""
        pipelines = [
            {'id': 1, 'project_id': 123, 'ref': 'refs/merge-requests/100/head'},
        ]
        
        with patch.object(self.client, 'get_merge_request') as mock_get_mr:
            mock_get_mr.return_value = {'iid': 100, 'title': 'No source branch'}
            
            self.client.resolve_merge_request_refs(pipelines)
            
            # Ref should remain unchanged when source_branch is missing
            self.assertEqual(pipelines[0]['ref'], 'refs/merge-requests/100/head')
    
    def test_empty_pipelines_list(self):
        """Test handling empty pipelines list"""
        pipelines = []
        
        with patch.object(self.client, 'get_merge_request') as mock_get_mr:
            # Should not raise any exception
            self.client.resolve_merge_request_refs(pipelines)
            mock_get_mr.assert_not_called()
    
    def test_none_ref_handling(self):
        """Test handling pipelines with None ref"""
        pipelines = [
            {'id': 1, 'project_id': 123, 'ref': None},
        ]
        
        with patch.object(self.client, 'get_merge_request') as mock_get_mr:
            # Should not raise any exception
            self.client.resolve_merge_request_refs(pipelines)
            mock_get_mr.assert_not_called()
    
    def test_exception_in_get_merge_request(self):
        """Test handling exceptions during MR lookup"""
        pipelines = [
            {'id': 1, 'project_id': 123, 'ref': 'refs/merge-requests/100/head'},
            {'id': 2, 'project_id': 123, 'ref': 'refs/merge-requests/101/head'},
        ]
        
        def mock_get_mr(project_id, mr_iid):
            if mr_iid == '100':
                raise Exception("Network error")
            return {'source_branch': 'feature/works'}
        
        with patch.object(self.client, 'get_merge_request', side_effect=mock_get_mr):
            # Should not raise, but first pipeline should be unchanged
            self.client.resolve_merge_request_refs(pipelines)
            
            # First pipeline should be unchanged due to exception
            self.assertEqual(pipelines[0]['ref'], 'refs/merge-requests/100/head')
            
            # Second pipeline should be resolved
            self.assertEqual(pipelines[1]['ref'], 'feature/works')
    
    def test_duplicate_mr_refs_same_iid(self):
        """Test handling multiple pipelines with the same MR ref"""
        pipelines = [
            {'id': 1, 'project_id': 123, 'ref': 'refs/merge-requests/100/head'},
            {'id': 2, 'project_id': 123, 'ref': 'refs/merge-requests/100/head'},
        ]
        
        with patch.object(self.client, 'get_merge_request') as mock_get_mr:
            mock_get_mr.return_value = {'source_branch': 'feature/shared'}
            
            self.client.resolve_merge_request_refs(pipelines)
            
            # Both pipelines should be resolved
            self.assertEqual(pipelines[0]['ref'], 'feature/shared')
            self.assertEqual(pipelines[1]['ref'], 'feature/shared')
            
            # Should only call get_merge_request once for the same MR
            mock_get_mr.assert_called_once_with(123, '100')
    
    def test_poll_id_in_logs(self):
        """Test that poll_id is included in log messages"""
        pipelines = [
            {'id': 1, 'project_id': 123, 'ref': 'refs/merge-requests/100/head'},
        ]
        
        with patch.object(self.client, 'get_merge_request') as mock_get_mr:
            mock_get_mr.return_value = {'source_branch': 'feature/test'}
            
            # Should not raise - logging should work with poll_id
            self.client.resolve_merge_request_refs(pipelines, poll_id='test-poll-123')
            
            self.assertEqual(pipelines[0]['ref'], 'feature/test')
    
    def test_missing_project_id(self):
        """Test handling pipeline without project_id"""
        pipelines = [
            {'id': 1, 'ref': 'refs/merge-requests/100/head'},  # No project_id
        ]
        
        with patch.object(self.client, 'get_merge_request') as mock_get_mr:
            self.client.resolve_merge_request_refs(pipelines)
            
            # Should not call get_merge_request without project_id
            mock_get_mr.assert_not_called()
            # Ref should remain unchanged
            self.assertEqual(pipelines[0]['ref'], 'refs/merge-requests/100/head')


class TestMRRefResolutionIntegration(unittest.TestCase):
    """Tests for BE-3: Integration into pipeline fetch flow"""
    
    def test_resolve_called_in_configured_scope_path(self):
        """Test that resolve_merge_request_refs is called in configured scope path"""
        from backend.app import BackgroundPoller
        
        mock_client = MagicMock()
        mock_client.get_pipelines.return_value = [
            {'id': 1, 'ref': 'refs/merge-requests/100/head'}
        ]
        mock_client.resolve_merge_request_refs = MagicMock()
        
        poller = BackgroundPoller(
            mock_client,
            poll_interval_sec=60,
            project_ids=['123']  # Configured scope
        )
        
        projects = [{'id': 123, 'name': 'test', 'path_with_namespace': 'group/test'}]
        result = poller._fetch_pipelines(projects, poll_id='test')
        
        self.assertIsNotNone(result)
        mock_client.resolve_merge_request_refs.assert_called_once()
    
    def test_resolve_called_in_fallback_path(self):
        """Test that resolve_merge_request_refs is called in fallback path"""
        from backend.app import BackgroundPoller
        
        mock_client = MagicMock()
        mock_client.get_all_pipelines.return_value = [
            {'id': 1, 'project_id': 123, 'ref': 'refs/merge-requests/100/head'}
        ]
        mock_client.resolve_merge_request_refs = MagicMock()
        
        poller = BackgroundPoller(
            mock_client,
            poll_interval_sec=60
            # No group_ids or project_ids = fallback path
        )
        
        projects = []  # Empty projects, fallback path will be used
        result = poller._fetch_pipelines(projects, poll_id='test')
        
        self.assertIsNotNone(result)
        mock_client.resolve_merge_request_refs.assert_called_once()
    
    def test_exception_in_resolve_does_not_break_fetch(self):
        """Test that exception in resolve_merge_request_refs doesn't break pipeline fetch"""
        from backend.app import BackgroundPoller
        
        mock_client = MagicMock()
        mock_client.get_pipelines.return_value = [
            {'id': 1, 'ref': 'refs/merge-requests/100/head'}
        ]
        mock_client.resolve_merge_request_refs.side_effect = Exception("Test exception")
        
        poller = BackgroundPoller(
            mock_client,
            poll_interval_sec=60,
            project_ids=['123']
        )
        
        projects = [{'id': 123, 'name': 'test', 'path_with_namespace': 'group/test'}]
        
        # Should not raise exception
        result = poller._fetch_pipelines(projects, poll_id='test')
        
        # Should still return pipelines even though resolve failed
        self.assertIsNotNone(result)
        self.assertEqual(len(result['all_pipelines']), 1)


class TestAPIResponseIncludesMRFields(unittest.TestCase):
    """Tests for BE-4: API response includes MR-specific fields"""
    
    def setUp(self):
        """Set up test fixtures"""
        from backend import app as server
        # Reset STATE for testing
        with server.STATE_LOCK:
            server.STATE['data'] = {
                'projects': [],
                'pipelines': [],
                'summary': {},
                'services': []
            }
            server.STATE['last_updated'] = None
            server.STATE['status'] = 'ONLINE'
            server.STATE['error'] = None
    
    def test_api_response_includes_mr_fields(self):
        """Test that /api/pipelines response includes original_ref and merge_request_iid"""
        from backend import app as server
        
        # Set up STATE with MR pipeline
        pipelines = [
            {
                'id': 1,
                'project_id': 123,
                'project_name': 'test',
                'ref': 'feature/foo',
                'original_ref': 'refs/merge-requests/481/head',
                'merge_request_iid': '481',
                'status': 'success'
            }
        ]
        server.update_state('pipelines', pipelines)
        
        # Create mock handler
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.path = '/api/pipelines'
        handler.send_json_response = MagicMock()
        
        # Call handle_pipelines
        server.DashboardRequestHandler.handle_pipelines(handler)
        
        # Verify response
        handler.send_json_response.assert_called_once()
        response = handler.send_json_response.call_args[0][0]
        
        pipeline = response['pipelines'][0]
        self.assertEqual(pipeline['ref'], 'feature/foo')
        self.assertEqual(pipeline['original_ref'], 'refs/merge-requests/481/head')
        self.assertEqual(pipeline['merge_request_iid'], '481')
    
    def test_api_response_excludes_mr_fields_for_normal_pipelines(self):
        """Test that normal pipelines don't have original_ref or merge_request_iid"""
        from backend import app as server
        
        # Set up STATE with normal pipeline (no MR fields)
        pipelines = [
            {
                'id': 1,
                'project_id': 123,
                'project_name': 'test',
                'ref': 'main',
                'status': 'success'
            }
        ]
        server.update_state('pipelines', pipelines)
        
        # Create mock handler
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.path = '/api/pipelines'
        handler.send_json_response = MagicMock()
        
        # Call handle_pipelines
        server.DashboardRequestHandler.handle_pipelines(handler)
        
        # Verify response
        handler.send_json_response.assert_called_once()
        response = handler.send_json_response.call_args[0][0]
        
        pipeline = response['pipelines'][0]
        self.assertEqual(pipeline['ref'], 'main')
        self.assertNotIn('original_ref', pipeline)
        self.assertNotIn('merge_request_iid', pipeline)


if __name__ == '__main__':
    unittest.main()

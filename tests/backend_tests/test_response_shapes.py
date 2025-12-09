#!/usr/bin/env python3
"""
Tests for API endpoint response shapes
Ensures endpoints always return correct JSON shapes even when STATE is empty or None
"""

import unittest
import sys
import os
import json
from unittest.mock import MagicMock, patch
from datetime import datetime

# Add parent directory to path to from backend import app as server module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend import app as server


class TestResponseShapes(unittest.TestCase):
    """Test that API endpoints always return correct JSON shapes"""
    
    def setUp(self):
        """Reset global STATE before each test"""
        with server.STATE_LOCK:
            server.STATE['data'] = {}
            server.STATE['last_updated'] = None
            server.STATE['status'] = 'INITIALIZING'
            server.STATE['error'] = None
    
    def test_summary_with_empty_state_initializing(self):
        """Test /api/summary returns proper shape when STATE is empty and INITIALIZING"""
        # STATE is empty (no data yet) and status is INITIALIZING
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.send_json_response = MagicMock()
        
        server.DashboardRequestHandler.handle_summary(handler)
        
        # Should have been called once
        handler.send_json_response.assert_called_once()
        response_data = handler.send_json_response.call_args[0][0]
        
        # Should return proper shape with zeros, not error shape
        self.assertIsInstance(response_data, dict)
        self.assertIn('total_repositories', response_data)
        self.assertIn('total_pipelines', response_data)
        self.assertIn('last_updated', response_data)
        self.assertIn('backend_status', response_data)
        self.assertEqual(response_data['total_repositories'], 0)
        self.assertEqual(response_data['backend_status'], 'INITIALIZING')
    
    def test_summary_with_empty_list_state(self):
        """Test /api/summary returns proper shape when STATE has empty lists"""
        # Set STATE with empty lists (valid empty state after successful poll)
        server.update_state_atomic({
            'projects': [],
            'pipelines': [],
            'summary': dict(server.DEFAULT_SUMMARY)  # Use copy of default summary
        })
        
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.send_json_response = MagicMock()
        
        server.DashboardRequestHandler.handle_summary(handler)
        
        handler.send_json_response.assert_called_once()
        response_data = handler.send_json_response.call_args[0][0]
        
        # Should return proper shape with zeros
        self.assertIn('total_repositories', response_data)
        self.assertIn('total_pipelines', response_data)
        self.assertIn('last_updated', response_data)
        self.assertEqual(response_data['total_repositories'], 0)
        self.assertEqual(response_data['total_pipelines'], 0)
    
    def test_repos_with_empty_state_initializing(self):
        """Test /api/repos returns proper shape when STATE is empty and INITIALIZING"""
        # STATE is empty (no data yet) and status is INITIALIZING
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.send_json_response = MagicMock()
        
        server.DashboardRequestHandler.handle_repos(handler)
        
        handler.send_json_response.assert_called_once()
        response_data = handler.send_json_response.call_args[0][0]
        
        # Should return proper shape with empty array, not error shape
        self.assertIsInstance(response_data, dict)
        self.assertIn('repositories', response_data)
        self.assertIn('total', response_data)
        self.assertIn('backend_status', response_data)
        self.assertIsInstance(response_data['repositories'], list)
        self.assertEqual(len(response_data['repositories']), 0)
        self.assertEqual(response_data['backend_status'], 'INITIALIZING')
    
    def test_repos_with_empty_list_state(self):
        """Test /api/repos returns proper shape when STATE has empty lists"""
        # Set STATE with empty list (valid empty state after successful poll)
        server.update_state_atomic({
            'projects': [],
            'pipelines': [],
            'summary': {'total_repositories': 0}
        })
        
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.send_json_response = MagicMock()
        
        server.DashboardRequestHandler.handle_repos(handler)
        
        handler.send_json_response.assert_called_once()
        response_data = handler.send_json_response.call_args[0][0]
        
        # Should return proper shape with empty array
        self.assertIn('repositories', response_data)
        self.assertIn('total', response_data)
        self.assertIn('last_updated', response_data)
        self.assertIsInstance(response_data['repositories'], list)
        self.assertEqual(len(response_data['repositories']), 0)
        self.assertEqual(response_data['total'], 0)
    
    def test_pipelines_with_empty_state_initializing(self):
        """Test /api/pipelines returns proper shape when STATE is empty and INITIALIZING"""
        # STATE is empty (no data yet) and status is INITIALIZING
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.send_json_response = MagicMock()
        handler.path = '/api/pipelines'  # Add path for query parsing
        
        server.DashboardRequestHandler.handle_pipelines(handler)
        
        handler.send_json_response.assert_called_once()
        response_data = handler.send_json_response.call_args[0][0]
        
        # Should return proper shape with empty array, not error shape
        self.assertIsInstance(response_data, dict)
        self.assertIn('pipelines', response_data)
        self.assertIn('total', response_data)
        self.assertIn('backend_status', response_data)
        self.assertIsInstance(response_data['pipelines'], list)
        self.assertEqual(len(response_data['pipelines']), 0)
        self.assertEqual(response_data['backend_status'], 'INITIALIZING')
    
    def test_pipelines_with_empty_list_state(self):
        """Test /api/pipelines returns proper shape when STATE has empty lists"""
        # Set STATE with empty lists (valid empty state after successful poll)
        server.update_state_atomic({
            'projects': [],
            'pipelines': [],
            'summary': {'total_pipelines': 0}
        })
        
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.send_json_response = MagicMock()
        handler.path = '/api/pipelines'  # Add path for query parsing
        
        server.DashboardRequestHandler.handle_pipelines(handler)
        
        handler.send_json_response.assert_called_once()
        response_data = handler.send_json_response.call_args[0][0]
        
        # Should return proper shape with empty array
        self.assertIn('pipelines', response_data)
        self.assertIn('total', response_data)
        self.assertIn('last_updated', response_data)
        self.assertIsInstance(response_data['pipelines'], list)
        self.assertEqual(len(response_data['pipelines']), 0)
        self.assertEqual(response_data['total'], 0)
    
    def test_summary_never_returns_bare_array(self):
        """Test /api/summary never returns a bare array"""
        # Test with various STATE configurations
        test_states = [
            {},  # Empty
            {'summary': None},  # None summary
            {'summary': {'total_repositories': 5}},  # Valid summary
        ]
        
        for state_data in test_states:
            with self.subTest(state=state_data):
                with server.STATE_LOCK:
                    server.STATE['data'] = state_data
                
                handler = MagicMock(spec=server.DashboardRequestHandler)
                handler.send_json_response = MagicMock()
                
                server.DashboardRequestHandler.handle_summary(handler)
                
                handler.send_json_response.assert_called_once()
                response_data = handler.send_json_response.call_args[0][0]
                
                # Response must be a dict, never a list
                self.assertIsInstance(response_data, dict)
                self.assertNotIsInstance(response_data, list)
    
    def test_repos_never_returns_bare_array(self):
        """Test /api/repos never returns a bare array"""
        # Test with various STATE configurations
        test_states = [
            {},  # Empty
            {'projects': None},  # None projects
            {'projects': []},  # Empty list
            {'projects': [{'id': 1, 'name': 'test'}]},  # Valid projects
        ]
        
        for state_data in test_states:
            with self.subTest(state=state_data):
                with server.STATE_LOCK:
                    server.STATE['data'] = state_data
                    server.STATE['status'] = 'ONLINE' if state_data.get('projects') is not None else 'INITIALIZING'
                
                handler = MagicMock(spec=server.DashboardRequestHandler)
                handler.send_json_response = MagicMock()
                
                server.DashboardRequestHandler.handle_repos(handler)
                
                handler.send_json_response.assert_called_once()
                response_data = handler.send_json_response.call_args[0][0]
                
                # Response must be a dict, never a list
                self.assertIsInstance(response_data, dict)
                self.assertNotIsInstance(response_data, list)
    
    def test_pipelines_never_returns_bare_array(self):
        """Test /api/pipelines never returns a bare array"""
        # Test with various STATE configurations
        test_states = [
            {},  # Empty
            {'pipelines': None},  # None pipelines
            {'pipelines': []},  # Empty list
            {'pipelines': [{'id': 1, 'status': 'success'}]},  # Valid pipelines
        ]
        
        for state_data in test_states:
            with self.subTest(state=state_data):
                with server.STATE_LOCK:
                    server.STATE['data'] = state_data
                    server.STATE['status'] = 'ONLINE' if state_data.get('pipelines') is not None else 'INITIALIZING'
                
                handler = MagicMock(spec=server.DashboardRequestHandler)
                handler.send_json_response = MagicMock()
                handler.path = '/api/pipelines'  # Add path for query parsing
                
                server.DashboardRequestHandler.handle_pipelines(handler)
                
                handler.send_json_response.assert_called_once()
                response_data = handler.send_json_response.call_args[0][0]
                
                # Response must be a dict, never a list
                self.assertIsInstance(response_data, dict)
                self.assertNotIsInstance(response_data, list)


class TestResponseShapeKeys(unittest.TestCase):
    """Test that API endpoint responses always have required keys"""
    
    def setUp(self):
        """Set up STATE with valid empty data"""
        server.update_state_atomic({
            'projects': [],
            'pipelines': [],
            'summary': dict(server.DEFAULT_SUMMARY)  # Use copy of default summary
        })
    
    def test_summary_has_all_required_keys(self):
        """Test /api/summary response has all required keys"""
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.send_json_response = MagicMock()
        
        server.DashboardRequestHandler.handle_summary(handler)
        
        response_data = handler.send_json_response.call_args[0][0]
        
        # Required keys according to problem statement and docs
        required_keys = [
            'total_repositories',
            'active_repositories',
            'total_pipelines',
            'successful_pipelines',
            'failed_pipelines',
            'running_pipelines',
            'pending_pipelines',
            'pipeline_success_rate',
            'last_updated',
        ]
        
        for key in required_keys:
            self.assertIn(key, response_data, f"Missing required key: {key}")
        
        # SLO fields are optional (only present when SLO is enabled in config)
        # If present, verify they have the expected types
        slo_keys = [
            'pipeline_slo_target_default_branch_success_rate',
            'pipeline_slo_observed_default_branch_success_rate',
            'pipeline_slo_total_default_branch_pipelines',
            'pipeline_error_budget_remaining_pct',
        ]
        
        # If any SLO key is present, all should be present
        slo_keys_present = [key for key in slo_keys if key in response_data]
        if slo_keys_present:
            # If some are present, all should be present
            for key in slo_keys:
                self.assertIn(key, response_data, 
                            f"SLO key {key} missing, but other SLO keys are present: {slo_keys_present}")
    
    def test_repos_has_all_required_keys(self):
        """Test /api/repos response has all required keys"""
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.send_json_response = MagicMock()
        
        server.DashboardRequestHandler.handle_repos(handler)
        
        response_data = handler.send_json_response.call_args[0][0]
        
        # Required keys according to problem statement
        required_keys = ['repositories', 'total', 'last_updated']
        
        for key in required_keys:
            self.assertIn(key, response_data, f"Missing required key: {key}")
        
        # Verify repositories is a list
        self.assertIsInstance(response_data['repositories'], list)
    
    def test_pipelines_has_all_required_keys(self):
        """Test /api/pipelines response has all required keys"""
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.send_json_response = MagicMock()
        handler.path = '/api/pipelines'
        
        server.DashboardRequestHandler.handle_pipelines(handler)
        
        response_data = handler.send_json_response.call_args[0][0]
        
        # Required keys according to problem statement
        required_keys = ['pipelines', 'total', 'last_updated']
        
        for key in required_keys:
            self.assertIn(key, response_data, f"Missing required key: {key}")
        
        # Verify pipelines is a list
        self.assertIsInstance(response_data['pipelines'], list)


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python3
"""
Unit tests for mock mode job analytics functionality
Tests loading and serving of job_analytics data in mock mode
"""

import unittest
import sys
import os
import json
import io
from unittest.mock import MagicMock, patch
from datetime import datetime
from http.server import HTTPServer

# Add parent directory to path to import backend module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend import app as server


class TestMockJobAnalyticsLoading(unittest.TestCase):
    """Test loading of job_analytics from mock data files"""
    
    def setUp(self):
        """Reset global STATE before each test"""
        with server.STATE_LOCK:
            server.STATE['data'] = {
                'projects': [],
                'pipelines': [],
                'summary': {},
                'services': [],
                'job_analytics': {}
            }
            server.STATE['last_updated'] = None
            server.STATE['job_analytics_last_updated'] = {}
            server.STATE['status'] = 'INITIALIZING'
            server.STATE['error'] = None
        
        server.MOCK_MODE_ENABLED = False
    
    def tearDown(self):
        """Clean up after each test"""
        server.MOCK_MODE_ENABLED = False
    
    def test_load_mock_data_with_job_analytics(self):
        """Test that job_analytics field is properly loaded from mock data"""
        mock_data = {
            'summary': {'total_repositories': 2},
            'repositories': [
                {'id': 10001, 'name': 'frontend-app'},
                {'id': 10002, 'name': 'backend-api'}
            ],
            'pipelines': [
                {'id': 50001, 'project_id': 10001, 'status': 'success'}
            ],
            'job_analytics': {
                '10001': {
                    'project_id': 10001,
                    'window_days': 7,
                    'computed_at': '2024-01-20T10:35:00Z',
                    'data': [
                        {
                            'pipeline_id': 50001,
                            'pipeline_ref': 'main',
                            'pipeline_status': 'success',
                            'created_at': '2024-01-20T10:30:00Z',
                            'is_default_branch': True,
                            'is_merge_request': False,
                            'avg_duration': 120.5,
                            'p95_duration': 180.2,
                            'p99_duration': 210.8,
                            'job_count': 12
                        }
                    ],
                    'staleness_seconds': 0,
                    'error': None
                }
            }
        }
        
        # Simulate loading job_analytics into STATE
        job_analytics_data = {}
        for project_id_str, analytics in mock_data['job_analytics'].items():
            try:
                project_id = int(project_id_str)
                job_analytics_data[project_id] = analytics
                with server.STATE_LOCK:
                    server.STATE['job_analytics_last_updated'][project_id] = datetime.now()
            except (ValueError, TypeError):
                pass
        
        server.update_state_atomic({
            'projects': mock_data['repositories'],
            'pipelines': mock_data['pipelines'],
            'summary': mock_data['summary'],
            'job_analytics': job_analytics_data
        })
        
        # Verify job_analytics was loaded correctly
        job_analytics = server.get_state('job_analytics')
        self.assertIsNotNone(job_analytics)
        self.assertIn(10001, job_analytics)
        self.assertEqual(job_analytics[10001]['project_id'], 10001)
        self.assertEqual(job_analytics[10001]['window_days'], 7)
        self.assertEqual(len(job_analytics[10001]['data']), 1)
        
        # Verify timestamp was set
        with server.STATE_LOCK:
            self.assertIn(10001, server.STATE['job_analytics_last_updated'])
    
    def test_load_mock_data_without_job_analytics(self):
        """Test that missing job_analytics field doesn't break loading"""
        mock_data = {
            'summary': {'total_repositories': 1},
            'repositories': [{'id': 10001, 'name': 'test-repo'}],
            'pipelines': []
            # No job_analytics field
        }
        
        server.update_state_atomic({
            'projects': mock_data['repositories'],
            'pipelines': mock_data['pipelines'],
            'summary': mock_data['summary']
        })
        
        # Verify STATE was updated successfully
        projects = server.get_state('projects')
        self.assertEqual(len(projects), 1)
        
        # job_analytics should be empty dict (from initialization)
        job_analytics = server.get_state('job_analytics')
        self.assertIsNotNone(job_analytics)
        self.assertEqual(len(job_analytics), 0)
    
    def test_job_analytics_key_conversion(self):
        """Test that string project_id keys are converted to integers"""
        mock_analytics = {
            '10001': {'project_id': 10001, 'data': []},
            '10002': {'project_id': 10002, 'data': []},
            '999': {'project_id': 999, 'data': []}
        }
        
        job_analytics_data = {}
        for project_id_str, analytics in mock_analytics.items():
            try:
                project_id = int(project_id_str)
                job_analytics_data[project_id] = analytics
            except (ValueError, TypeError):
                pass
        
        # All keys should be integers
        self.assertIn(10001, job_analytics_data)
        self.assertIn(10002, job_analytics_data)
        self.assertIn(999, job_analytics_data)
        self.assertNotIn('10001', job_analytics_data)
    
    def test_invalid_project_id_skipped(self):
        """Test that invalid project_id keys are skipped gracefully"""
        mock_analytics = {
            '10001': {'project_id': 10001, 'data': []},
            'invalid': {'project_id': 'invalid', 'data': []},
            'not_a_number': {'project_id': 0, 'data': []}
        }
        
        job_analytics_data = {}
        for project_id_str, analytics in mock_analytics.items():
            try:
                project_id = int(project_id_str)
                job_analytics_data[project_id] = analytics
            except (ValueError, TypeError):
                # Skip invalid keys
                pass
        
        # Only valid integer key should be present
        self.assertEqual(len(job_analytics_data), 1)
        self.assertIn(10001, job_analytics_data)
        self.assertNotIn('invalid', job_analytics_data)
        self.assertNotIn('not_a_number', job_analytics_data)


class TestMockJobAnalyticsEndpoint(unittest.TestCase):
    """Test GET /api/job-analytics/{project_id} endpoint in mock mode"""
    
    def setUp(self):
        """Create mock request handler and prepare STATE"""
        with server.STATE_LOCK:
            server.STATE['data'] = {
                'projects': [],
                'pipelines': [],
                'summary': {},
                'services': [],
                'job_analytics': {
                    10001: {
                        'project_id': 10001,
                        'window_days': 7,
                        'computed_at': '2024-01-20T10:35:00Z',
                        'data': [
                            {
                                'pipeline_id': 50001,
                                'pipeline_ref': 'main',
                                'pipeline_status': 'success',
                                'avg_duration': 120.5,
                                'p95_duration': 180.2,
                                'p99_duration': 210.8,
                                'job_count': 12
                            }
                        ],
                        'staleness_seconds': 0,
                        'error': None
                    }
                }
            }
            server.STATE['job_analytics_last_updated'] = {10001: datetime.now()}
            server.STATE['last_updated'] = datetime.now()
            server.STATE['status'] = 'ONLINE'
        
        server.MOCK_MODE_ENABLED = True
        
        # Create handler instance
        self.mock_request = MagicMock()
        self.mock_request.makefile = MagicMock(return_value=io.BytesIO(b''))
        self.mock_client_address = ('127.0.0.1', 12345)
        self.mock_server = MagicMock(spec=HTTPServer)
        self.mock_server.gitlab_client = None
        
        self.handler = server.DashboardRequestHandler(
            self.mock_request,
            self.mock_client_address,
            self.mock_server
        )
        
        # Mock response methods
        self.handler.send_response = MagicMock()
        self.handler.send_header = MagicMock()
        self.handler.end_headers = MagicMock()
        self.handler.wfile = MagicMock()
        self.handler.wfile.write = MagicMock()
    
    def tearDown(self):
        """Clean up"""
        server.MOCK_MODE_ENABLED = False
    
    def test_get_job_analytics_success(self):
        """Test successful GET of job analytics for a project"""
        self.handler.handle_job_analytics(10001)
        
        # Should return 200 OK
        self.handler.send_response.assert_called_once_with(200)
        
        # Check response content
        call_args = self.handler.wfile.write.call_args[0][0]
        response_data = json.loads(call_args.decode('utf-8'))
        
        # Verify analytics structure
        self.assertEqual(response_data['project_id'], 10001)
        self.assertEqual(response_data['window_days'], 7)
        self.assertIn('data', response_data)
        self.assertEqual(len(response_data['data']), 1)
        self.assertEqual(response_data['data'][0]['pipeline_id'], 50001)
        self.assertEqual(response_data['data'][0]['avg_duration'], 120.5)
        self.assertIn('staleness_seconds', response_data)
    
    def test_get_job_analytics_not_found(self):
        """Test GET for project without analytics returns 404"""
        self.handler.handle_job_analytics(99999)
        
        # Should return 404 Not Found
        self.handler.send_response.assert_called_once_with(404)
        
        # Check response content
        call_args = self.handler.wfile.write.call_args[0][0]
        response_data = json.loads(call_args.decode('utf-8'))
        
        self.assertIn('error', response_data)
        self.assertIn('Analytics not available', response_data['error'])


class TestMockReloadWithJobAnalytics(unittest.TestCase):
    """Test that POST /api/mock/reload includes job_analytics"""
    
    def setUp(self):
        """Create mock request handler"""
        with server.STATE_LOCK:
            server.STATE['data'] = {}
            server.STATE['last_updated'] = None
            server.STATE['job_analytics_last_updated'] = {}
            server.STATE['status'] = 'INITIALIZING'
        
        server.MOCK_MODE_ENABLED = True
        
        self.mock_request = MagicMock()
        self.mock_request.makefile = MagicMock(return_value=io.BytesIO(b''))
        self.mock_client_address = ('127.0.0.1', 12345)
        self.mock_server = MagicMock(spec=HTTPServer)
        self.mock_server.gitlab_client = None
        
        self.handler = server.DashboardRequestHandler(
            self.mock_request,
            self.mock_client_address,
            self.mock_server
        )
        
        self.handler.send_response = MagicMock()
        self.handler.send_header = MagicMock()
        self.handler.end_headers = MagicMock()
        self.handler.wfile = MagicMock()
        self.handler.wfile.write = MagicMock()
    
    def tearDown(self):
        """Clean up"""
        server.MOCK_MODE_ENABLED = False
    
    def test_mock_reload_includes_job_analytics(self):
        """Test that reload loads job_analytics from mock data"""
        mock_data = {
            'summary': {'total_repositories': 1},
            'repositories': [{'id': 10001, 'name': 'test-repo'}],
            'pipelines': [{'id': 50001, 'status': 'success'}],
            'job_analytics': {
                '10001': {
                    'project_id': 10001,
                    'window_days': 7,
                    'data': []
                },
                '10002': {
                    'project_id': 10002,
                    'window_days': 7,
                    'data': []
                }
            }
        }
        
        with patch('backend.app.load_mock_data', return_value=mock_data):
            self.handler.handle_mock_reload()
        
        # Should return 200 OK
        self.handler.send_response.assert_called_once_with(200)
        
        # Check response includes job_analytics count
        call_args = self.handler.wfile.write.call_args[0][0]
        response_data = json.loads(call_args.decode('utf-8'))
        
        self.assertTrue(response_data['reloaded'])
        self.assertIn('summary', response_data)
        self.assertIn('job_analytics', response_data['summary'])
        self.assertEqual(response_data['summary']['job_analytics'], 2)
        
        # Verify STATE was updated with job_analytics
        job_analytics = server.get_state('job_analytics')
        self.assertIsNotNone(job_analytics)
        self.assertEqual(len(job_analytics), 2)
        self.assertIn(10001, job_analytics)
        self.assertIn(10002, job_analytics)
    
    def test_mock_reload_without_job_analytics(self):
        """Test that reload works when job_analytics is missing"""
        mock_data = {
            'summary': {'total_repositories': 1},
            'repositories': [{'id': 10001, 'name': 'test-repo'}],
            'pipelines': []
            # No job_analytics
        }
        
        with patch('backend.app.load_mock_data', return_value=mock_data):
            self.handler.handle_mock_reload()
        
        # Should return 200 OK
        self.handler.send_response.assert_called_once_with(200)
        
        # Check response
        call_args = self.handler.wfile.write.call_args[0][0]
        response_data = json.loads(call_args.decode('utf-8'))
        
        self.assertTrue(response_data['reloaded'])
        self.assertIn('summary', response_data)
        # job_analytics count should be 0
        self.assertEqual(response_data['summary']['job_analytics'], 0)


if __name__ == '__main__':
    unittest.main()

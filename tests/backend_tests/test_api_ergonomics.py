#!/usr/bin/env python3
"""
Tests for API ergonomics, headers, and mock-mode metadata improvements
"""

import unittest
import sys
import os
import json
import io
from unittest.mock import MagicMock, patch
from datetime import datetime

# Add parent directory to path to from backend import app as server module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend import app as server


class TestSecurityHeaders(unittest.TestCase):
    """Test that send_json_response includes required security headers"""
    
    def setUp(self):
        """Set up a mock request handler"""
        self.handler = MagicMock(spec=server.DashboardRequestHandler)
        # Create a mock wfile to capture written bytes
        self.handler.wfile = io.BytesIO()
        
        # Track headers
        self.sent_headers = {}
        
        def mock_send_header(name, value):
            self.sent_headers[name] = value
        
        self.handler.send_header = mock_send_header
        self.handler.send_response = MagicMock()
        self.handler.end_headers = MagicMock()
        
    def test_send_json_response_includes_cache_control(self):
        """Test that send_json_response includes Cache-Control header"""
        # Call the actual method with our mock handler
        server.DashboardRequestHandler.send_json_response(self.handler, {'test': 'data'})
        
        self.assertIn('Cache-Control', self.sent_headers)
        self.assertEqual(self.sent_headers['Cache-Control'], 'no-store, max-age=0')
    
    def test_send_json_response_includes_content_type_options(self):
        """Test that send_json_response includes X-Content-Type-Options header"""
        server.DashboardRequestHandler.send_json_response(self.handler, {'test': 'data'})
        
        self.assertIn('X-Content-Type-Options', self.sent_headers)
        self.assertEqual(self.sent_headers['X-Content-Type-Options'], 'nosniff')
    
    def test_send_json_response_includes_cors_header(self):
        """Test that send_json_response includes Access-Control-Allow-Origin header"""
        server.DashboardRequestHandler.send_json_response(self.handler, {'test': 'data'})
        
        self.assertIn('Access-Control-Allow-Origin', self.sent_headers)
        self.assertEqual(self.sent_headers['Access-Control-Allow-Origin'], '*')
    
    def test_send_json_response_includes_content_type(self):
        """Test that send_json_response includes Content-Type header"""
        server.DashboardRequestHandler.send_json_response(self.handler, {'test': 'data'})
        
        self.assertIn('Content-Type', self.sent_headers)
        self.assertEqual(self.sent_headers['Content-Type'], 'application/json')


class TestIsMockFlag(unittest.TestCase):
    """Test that all API endpoints include is_mock flag"""
    
    def setUp(self):
        """Set up STATE with valid data before each test"""
        server.update_state_atomic({
            'projects': [{'id': 1, 'name': 'test-project'}],
            'pipelines': [{'id': 100, 'status': 'success', 'project_name': 'test'}],
            'summary': dict(server.DEFAULT_SUMMARY)
        })
        
    def tearDown(self):
        """Reset MOCK_MODE_ENABLED after each test"""
        server.MOCK_MODE_ENABLED = False
    
    def test_summary_includes_is_mock_when_enabled(self):
        """Test /api/summary includes is_mock=true when mock mode enabled"""
        server.MOCK_MODE_ENABLED = True
        
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.send_json_response = MagicMock()
        
        server.DashboardRequestHandler.handle_summary(handler)
        
        handler.send_json_response.assert_called_once()
        response_data = handler.send_json_response.call_args[0][0]
        self.assertIn('is_mock', response_data)
        self.assertTrue(response_data['is_mock'])
    
    def test_summary_includes_is_mock_when_disabled(self):
        """Test /api/summary includes is_mock=false when mock mode disabled"""
        server.MOCK_MODE_ENABLED = False
        
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.send_json_response = MagicMock()
        
        server.DashboardRequestHandler.handle_summary(handler)
        
        handler.send_json_response.assert_called_once()
        response_data = handler.send_json_response.call_args[0][0]
        self.assertIn('is_mock', response_data)
        self.assertFalse(response_data['is_mock'])
    
    def test_repos_includes_is_mock_when_enabled(self):
        """Test /api/repos includes is_mock=true when mock mode enabled"""
        server.MOCK_MODE_ENABLED = True
        
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.send_json_response = MagicMock()
        
        server.DashboardRequestHandler.handle_repos(handler)
        
        handler.send_json_response.assert_called_once()
        response_data = handler.send_json_response.call_args[0][0]
        self.assertIn('is_mock', response_data)
        self.assertTrue(response_data['is_mock'])
    
    def test_repos_includes_is_mock_when_disabled(self):
        """Test /api/repos includes is_mock=false when mock mode disabled"""
        server.MOCK_MODE_ENABLED = False
        
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.send_json_response = MagicMock()
        
        server.DashboardRequestHandler.handle_repos(handler)
        
        handler.send_json_response.assert_called_once()
        response_data = handler.send_json_response.call_args[0][0]
        self.assertIn('is_mock', response_data)
        self.assertFalse(response_data['is_mock'])
    
    def test_pipelines_includes_is_mock_when_enabled(self):
        """Test /api/pipelines includes is_mock=true when mock mode enabled"""
        server.MOCK_MODE_ENABLED = True
        
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.send_json_response = MagicMock()
        handler.path = '/api/pipelines'
        
        server.DashboardRequestHandler.handle_pipelines(handler)
        
        handler.send_json_response.assert_called_once()
        response_data = handler.send_json_response.call_args[0][0]
        self.assertIn('is_mock', response_data)
        self.assertTrue(response_data['is_mock'])
    
    def test_pipelines_includes_is_mock_when_disabled(self):
        """Test /api/pipelines includes is_mock=false when mock mode disabled"""
        server.MOCK_MODE_ENABLED = False
        
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.send_json_response = MagicMock()
        handler.path = '/api/pipelines'
        
        server.DashboardRequestHandler.handle_pipelines(handler)
        
        handler.send_json_response.assert_called_once()
        response_data = handler.send_json_response.call_args[0][0]
        self.assertIn('is_mock', response_data)
        self.assertFalse(response_data['is_mock'])
    
    def test_health_includes_is_mock_when_enabled(self):
        """Test /api/health includes is_mock=true when mock mode enabled"""
        server.MOCK_MODE_ENABLED = True
        
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.send_json_response = MagicMock()
        
        server.DashboardRequestHandler.handle_health(handler)
        
        handler.send_json_response.assert_called_once()
        response_data = handler.send_json_response.call_args[0][0]
        self.assertIn('is_mock', response_data)
        self.assertTrue(response_data['is_mock'])
    
    def test_health_includes_is_mock_when_disabled(self):
        """Test /api/health includes is_mock=false when mock mode disabled"""
        server.MOCK_MODE_ENABLED = False
        
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.send_json_response = MagicMock()
        
        server.DashboardRequestHandler.handle_health(handler)
        
        handler.send_json_response.assert_called_once()
        response_data = handler.send_json_response.call_args[0][0]
        self.assertIn('is_mock', response_data)
        self.assertFalse(response_data['is_mock'])


class TestPipelinesLimitValidation(unittest.TestCase):
    """Test /api/pipelines limit parameter validation"""
    
    def setUp(self):
        """Set up STATE with valid data before each test"""
        server.update_state_atomic({
            'projects': [],
            'pipelines': [{'id': i, 'status': 'success', 'project_name': 'test'} for i in range(100)],
            'summary': dict(server.DEFAULT_SUMMARY)
        })
    
    def _get_status_code(self, call_args):
        """Extract status code from mock call arguments
        
        Helper method to extract HTTP status code from send_json_response mock call.
        Handles both positional and keyword argument cases.
        """
        if 'status' in call_args[1]:
            return call_args[1]['status']
        elif len(call_args[0]) > 1:
            return call_args[0][1]
        return 200  # Default status
    
    def test_invalid_limit_returns_400(self):
        """Test that non-numeric limit returns 400 error with is_mock"""
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.send_json_response = MagicMock()
        handler.path = '/api/pipelines?limit=invalid'
        
        server.DashboardRequestHandler.handle_pipelines(handler)
        
        handler.send_json_response.assert_called_once()
        call_args = handler.send_json_response.call_args
        response_data = call_args[0][0]
        status_code = self._get_status_code(call_args)
        
        self.assertIn('error', response_data)
        self.assertIn('is_mock', response_data)
        self.assertEqual(status_code, 400)
    
    def test_zero_limit_returns_400(self):
        """Test that limit=0 returns 400 error with is_mock"""
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.send_json_response = MagicMock()
        handler.path = '/api/pipelines?limit=0'
        
        server.DashboardRequestHandler.handle_pipelines(handler)
        
        handler.send_json_response.assert_called_once()
        call_args = handler.send_json_response.call_args
        response_data = call_args[0][0]
        status_code = self._get_status_code(call_args)
        
        self.assertIn('error', response_data)
        self.assertIn('is_mock', response_data)
        self.assertEqual(status_code, 400)
    
    def test_negative_limit_returns_400(self):
        """Test that negative limit returns 400 error with is_mock"""
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.send_json_response = MagicMock()
        handler.path = '/api/pipelines?limit=-5'
        
        server.DashboardRequestHandler.handle_pipelines(handler)
        
        handler.send_json_response.assert_called_once()
        call_args = handler.send_json_response.call_args
        response_data = call_args[0][0]
        status_code = self._get_status_code(call_args)
        
        self.assertIn('error', response_data)
        self.assertIn('is_mock', response_data)
        self.assertEqual(status_code, 400)
    
    def test_float_limit_returns_400(self):
        """Test that float limit (like 5.5) returns 400 error with is_mock"""
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.send_json_response = MagicMock()
        handler.path = '/api/pipelines?limit=5.5'
        
        server.DashboardRequestHandler.handle_pipelines(handler)
        
        handler.send_json_response.assert_called_once()
        call_args = handler.send_json_response.call_args
        response_data = call_args[0][0]
        status_code = self._get_status_code(call_args)
        
        self.assertIn('error', response_data)
        self.assertIn('is_mock', response_data)
        self.assertEqual(status_code, 400)
    
    def test_limit_exceeds_max_returns_400(self):
        """Test that limit exceeding MAX_PIPELINE_LIMIT returns 400 error with is_mock"""
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.send_json_response = MagicMock()
        handler.path = f'/api/pipelines?limit={server.MAX_PIPELINE_LIMIT + 1}'
        
        server.DashboardRequestHandler.handle_pipelines(handler)
        
        handler.send_json_response.assert_called_once()
        call_args = handler.send_json_response.call_args
        response_data = call_args[0][0]
        status_code = self._get_status_code(call_args)
        
        self.assertIn('error', response_data)
        self.assertIn('is_mock', response_data)
        self.assertEqual(status_code, 400)
    
    def test_valid_limit_returns_200(self):
        """Test that valid limit returns 200 success"""
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.send_json_response = MagicMock()
        handler.path = '/api/pipelines?limit=10'
        
        server.DashboardRequestHandler.handle_pipelines(handler)
        
        handler.send_json_response.assert_called_once()
        call_args = handler.send_json_response.call_args
        response_data = call_args[0][0]
        status_code = self._get_status_code(call_args)
        
        self.assertEqual(status_code, 200)
        self.assertIn('pipelines', response_data)
        self.assertNotIn('error', response_data)
    
    def test_total_before_limit_maintained(self):
        """Test that total_before_limit is correctly returned"""
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.send_json_response = MagicMock()
        handler.path = '/api/pipelines?limit=10'
        
        server.DashboardRequestHandler.handle_pipelines(handler)
        
        handler.send_json_response.assert_called_once()
        response_data = handler.send_json_response.call_args[0][0]
        
        self.assertIn('total_before_limit', response_data)
        self.assertIn('total', response_data)
        # total_before_limit should be >= total
        self.assertGreaterEqual(response_data['total_before_limit'], response_data['total'])
        # total should be limited to 10
        self.assertLessEqual(response_data['total'], 10)


class TestCORSPreflight(unittest.TestCase):
    """Test CORS preflight OPTIONS support"""
    
    def test_do_options_exists(self):
        """Test that do_OPTIONS method exists"""
        self.assertTrue(hasattr(server.DashboardRequestHandler, 'do_OPTIONS'))
    
    def test_do_options_sends_cors_headers(self):
        """Test that do_OPTIONS sends proper CORS headers"""
        handler = MagicMock(spec=server.DashboardRequestHandler)
        
        # Track headers
        sent_headers = {}
        def mock_send_header(name, value):
            sent_headers[name] = value
        
        handler.send_header = mock_send_header
        handler.send_response = MagicMock()
        handler.end_headers = MagicMock()
        
        server.DashboardRequestHandler.do_OPTIONS(handler)
        
        # Check response was 200
        handler.send_response.assert_called_once_with(200)
        
        # Check CORS headers
        self.assertIn('Access-Control-Allow-Origin', sent_headers)
        self.assertEqual(sent_headers['Access-Control-Allow-Origin'], '*')
        
        self.assertIn('Access-Control-Allow-Methods', sent_headers)
        self.assertIn('GET', sent_headers['Access-Control-Allow-Methods'])
        self.assertIn('POST', sent_headers['Access-Control-Allow-Methods'])
        self.assertIn('OPTIONS', sent_headers['Access-Control-Allow-Methods'])
        
        self.assertIn('Access-Control-Allow-Headers', sent_headers)
        self.assertIn('Content-Type', sent_headers['Access-Control-Allow-Headers'])
        
        # Check end_headers was called
        handler.end_headers.assert_called_once()


class TestIsMockInErrorResponses(unittest.TestCase):
    """Test that is_mock is included even in error responses"""
    
    def tearDown(self):
        """Reset MOCK_MODE_ENABLED after each test"""
        server.MOCK_MODE_ENABLED = False
    
    def test_repos_error_includes_is_mock(self):
        """Test /api/repos error response includes is_mock"""
        server.MOCK_MODE_ENABLED = True
        
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.send_json_response = MagicMock()
        
        # Force an error by making get_state_snapshot raise an exception
        with patch.object(server, 'get_state_snapshot', side_effect=Exception('Test error')):
            server.DashboardRequestHandler.handle_repos(handler)
        
        handler.send_json_response.assert_called_once()
        response_data = handler.send_json_response.call_args[0][0]
        self.assertIn('is_mock', response_data)
        self.assertTrue(response_data['is_mock'])
    
    def test_pipelines_error_includes_is_mock(self):
        """Test /api/pipelines error response includes is_mock"""
        server.MOCK_MODE_ENABLED = True
        
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.send_json_response = MagicMock()
        handler.path = '/api/pipelines'
        
        # Force an error by making get_state_snapshot raise an exception
        with patch.object(server, 'get_state_snapshot', side_effect=Exception('Test error')):
            server.DashboardRequestHandler.handle_pipelines(handler)
        
        handler.send_json_response.assert_called_once()
        response_data = handler.send_json_response.call_args[0][0]
        self.assertIn('is_mock', response_data)
        self.assertTrue(response_data['is_mock'])
    
    def test_health_error_includes_is_mock(self):
        """Test /api/health error response includes is_mock"""
        server.MOCK_MODE_ENABLED = True
        
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.send_json_response = MagicMock()
        
        # Force an error by making get_state_snapshot raise an exception
        with patch.object(server, 'get_state_snapshot', side_effect=Exception('Test error')):
            server.DashboardRequestHandler.handle_health(handler)
        
        handler.send_json_response.assert_called_once()
        response_data = handler.send_json_response.call_args[0][0]
        self.assertIn('is_mock', response_data)
        self.assertTrue(response_data['is_mock'])
    
    def test_summary_error_includes_is_mock(self):
        """Test /api/summary error response includes is_mock"""
        server.MOCK_MODE_ENABLED = True
        
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.send_json_response = MagicMock()
        
        # Force an error by making get_state_snapshot raise an exception
        with patch.object(server, 'get_state_snapshot', side_effect=Exception('Test error')):
            server.DashboardRequestHandler.handle_summary(handler)
        
        handler.send_json_response.assert_called_once()
        response_data = handler.send_json_response.call_args[0][0]
        self.assertIn('is_mock', response_data)
        self.assertTrue(response_data['is_mock'])


if __name__ == '__main__':
    unittest.main()

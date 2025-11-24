#!/usr/bin/env python3
"""
Tests for API ergonomics, headers, and mock flags (PR 3)
- Cache-Control and X-Content-Type-Options headers
- is_mock field in all API responses
- CORS OPTIONS preflight support
"""

import unittest
import sys
import os
import json
from unittest.mock import MagicMock, patch
from io import BytesIO

# Add parent directory to path to import server module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import server


class TestSendJsonResponseHeaders(unittest.TestCase):
    """Test that send_json_response includes proper headers"""
    
    def test_cache_control_header(self):
        """Test that Cache-Control header is set to prevent caching"""
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.wfile = BytesIO()
        headers_sent = {}
        
        def track_header(name, value):
            headers_sent[name] = value
        
        handler.send_response = MagicMock()
        handler.send_header = track_header
        handler.end_headers = MagicMock()
        
        server.DashboardRequestHandler.send_json_response(handler, {'test': 'data'})
        
        self.assertIn('Cache-Control', headers_sent)
        self.assertEqual(headers_sent['Cache-Control'], 'no-store, max-age=0')
    
    def test_x_content_type_options_header(self):
        """Test that X-Content-Type-Options: nosniff is set"""
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.wfile = BytesIO()
        headers_sent = {}
        
        def track_header(name, value):
            headers_sent[name] = value
        
        handler.send_response = MagicMock()
        handler.send_header = track_header
        handler.end_headers = MagicMock()
        
        server.DashboardRequestHandler.send_json_response(handler, {'test': 'data'})
        
        self.assertIn('X-Content-Type-Options', headers_sent)
        self.assertEqual(headers_sent['X-Content-Type-Options'], 'nosniff')
    
    def test_content_type_header(self):
        """Test that Content-Type is application/json"""
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.wfile = BytesIO()
        headers_sent = {}
        
        def track_header(name, value):
            headers_sent[name] = value
        
        handler.send_response = MagicMock()
        handler.send_header = track_header
        handler.end_headers = MagicMock()
        
        server.DashboardRequestHandler.send_json_response(handler, {'test': 'data'})
        
        self.assertIn('Content-Type', headers_sent)
        self.assertEqual(headers_sent['Content-Type'], 'application/json')
    
    def test_cors_header(self):
        """Test that Access-Control-Allow-Origin is set"""
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.wfile = BytesIO()
        headers_sent = {}
        
        def track_header(name, value):
            headers_sent[name] = value
        
        handler.send_response = MagicMock()
        handler.send_header = track_header
        handler.end_headers = MagicMock()
        
        server.DashboardRequestHandler.send_json_response(handler, {'test': 'data'})
        
        self.assertIn('Access-Control-Allow-Origin', headers_sent)
        self.assertEqual(headers_sent['Access-Control-Allow-Origin'], '*')


class TestIsMockFlagInResponses(unittest.TestCase):
    """Test that is_mock flag is included in API responses"""
    
    def setUp(self):
        """Reset STATE and MOCK_MODE_ENABLED before each test"""
        with server.STATE_LOCK:
            server.STATE['data'] = {
                'projects': [],
                'pipelines': [],
                'summary': dict(server.DEFAULT_SUMMARY)
            }
            server.STATE['last_updated'] = None
            server.STATE['status'] = 'ONLINE'
            server.STATE['error'] = None
    
    def test_handle_repos_includes_is_mock(self):
        """Test that /api/repos response includes is_mock"""
        original_mock_mode = server.MOCK_MODE_ENABLED
        server.MOCK_MODE_ENABLED = True
        
        try:
            handler = MagicMock(spec=server.DashboardRequestHandler)
            handler.send_json_response = MagicMock()
            
            server.DashboardRequestHandler.handle_repos(handler)
            
            handler.send_json_response.assert_called_once()
            response_data = handler.send_json_response.call_args[0][0]
            self.assertIn('is_mock', response_data)
            self.assertTrue(response_data['is_mock'])
        finally:
            server.MOCK_MODE_ENABLED = original_mock_mode
    
    def test_handle_pipelines_includes_is_mock(self):
        """Test that /api/pipelines response includes is_mock"""
        original_mock_mode = server.MOCK_MODE_ENABLED
        server.MOCK_MODE_ENABLED = False
        
        try:
            handler = MagicMock(spec=server.DashboardRequestHandler)
            handler.path = '/api/pipelines'
            handler.send_json_response = MagicMock()
            
            server.DashboardRequestHandler.handle_pipelines(handler)
            
            handler.send_json_response.assert_called_once()
            response_data = handler.send_json_response.call_args[0][0]
            self.assertIn('is_mock', response_data)
            self.assertFalse(response_data['is_mock'])
        finally:
            server.MOCK_MODE_ENABLED = original_mock_mode
    
    def test_handle_health_includes_is_mock(self):
        """Test that /api/health response includes is_mock"""
        original_mock_mode = server.MOCK_MODE_ENABLED
        server.MOCK_MODE_ENABLED = True
        
        try:
            handler = MagicMock(spec=server.DashboardRequestHandler)
            handler.send_json_response = MagicMock()
            
            server.DashboardRequestHandler.handle_health(handler)
            
            handler.send_json_response.assert_called_once()
            response_data = handler.send_json_response.call_args[0][0]
            self.assertIn('is_mock', response_data)
            self.assertTrue(response_data['is_mock'])
        finally:
            server.MOCK_MODE_ENABLED = original_mock_mode


class TestCORSOptionsHandler(unittest.TestCase):
    """Test CORS OPTIONS preflight request handling"""
    
    def test_options_api_route_returns_cors_headers(self):
        """Test that OPTIONS on /api/* returns CORS headers"""
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.path = '/api/summary'
        headers_sent = {}
        
        def track_header(name, value):
            headers_sent[name] = value
        
        handler.send_response = MagicMock()
        handler.send_header = track_header
        handler.end_headers = MagicMock()
        
        server.DashboardRequestHandler.do_OPTIONS(handler)
        
        # Check response code
        handler.send_response.assert_called_once_with(204)
        
        # Check CORS headers
        self.assertIn('Access-Control-Allow-Origin', headers_sent)
        self.assertEqual(headers_sent['Access-Control-Allow-Origin'], '*')
        
        self.assertIn('Access-Control-Allow-Methods', headers_sent)
        self.assertIn('GET', headers_sent['Access-Control-Allow-Methods'])
        self.assertIn('POST', headers_sent['Access-Control-Allow-Methods'])
        self.assertIn('OPTIONS', headers_sent['Access-Control-Allow-Methods'])
        
        self.assertIn('Access-Control-Allow-Headers', headers_sent)
        self.assertIn('Content-Type', headers_sent['Access-Control-Allow-Headers'])
    
    def test_options_non_api_route_returns_minimal(self):
        """Test that OPTIONS on non-API paths returns minimal response"""
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.path = '/index.html'
        headers_sent = {}
        
        def track_header(name, value):
            headers_sent[name] = value
        
        handler.send_response = MagicMock()
        handler.send_header = track_header
        handler.end_headers = MagicMock()
        
        server.DashboardRequestHandler.do_OPTIONS(handler)
        
        # Check response code is 200 for non-API routes
        handler.send_response.assert_called_once_with(200)


class TestPipelinesLimitValidation(unittest.TestCase):
    """Test /api/pipelines limit parameter validation"""
    
    def setUp(self):
        """Reset STATE before each test"""
        with server.STATE_LOCK:
            server.STATE['data'] = {
                'projects': [],
                'pipelines': [],
                'summary': dict(server.DEFAULT_SUMMARY)
            }
            server.STATE['last_updated'] = None
            server.STATE['status'] = 'ONLINE'
    
    def test_limit_zero_returns_400(self):
        """Test that limit=0 returns 400 error"""
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.path = '/api/pipelines?limit=0'
        handler.send_json_response = MagicMock()
        
        server.DashboardRequestHandler.handle_pipelines(handler)
        
        handler.send_json_response.assert_called_once()
        call_args = handler.send_json_response.call_args
        self.assertEqual(call_args[1]['status'], 400)
        self.assertIn('error', call_args[0][0])
    
    def test_limit_negative_returns_400(self):
        """Test that negative limit returns 400 error"""
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.path = '/api/pipelines?limit=-5'
        handler.send_json_response = MagicMock()
        
        server.DashboardRequestHandler.handle_pipelines(handler)
        
        handler.send_json_response.assert_called_once()
        call_args = handler.send_json_response.call_args
        self.assertEqual(call_args[1]['status'], 400)
    
    def test_limit_non_integer_returns_400(self):
        """Test that non-integer limit returns 400 error"""
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.path = '/api/pipelines?limit=abc'
        handler.send_json_response = MagicMock()
        
        server.DashboardRequestHandler.handle_pipelines(handler)
        
        handler.send_json_response.assert_called_once()
        call_args = handler.send_json_response.call_args
        self.assertEqual(call_args[1]['status'], 400)


if __name__ == '__main__':
    unittest.main()

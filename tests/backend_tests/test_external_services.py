#!/usr/bin/env python3
"""
Tests for external service uptime monitoring
Tests configuration loading, validation, service checking, and API endpoint
"""

import unittest
import sys
import os
import json
from unittest.mock import MagicMock, patch, Mock, mock_open
from datetime import datetime
from urllib.error import URLError, HTTPError

# Add parent directory to path to from backend import app as server module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend import app as server
from backend import services as services_module


class TestExternalServicesStateInit(unittest.TestCase):
    """Test that global STATE includes services collection"""
    
    def setUp(self):
        """Reset global STATE before each test"""
        with server.STATE_LOCK:
            server.STATE['data'] = {
                'projects': [],
                'pipelines': [],
                'summary': dict(server.DEFAULT_SUMMARY),
                'services': []
            }
            server.STATE['last_updated'] = None
            server.STATE['services_last_updated'] = None
            server.STATE['status'] = 'INITIALIZING'
            server.STATE['error'] = None
    
    def test_state_has_services_key(self):
        """Test that STATE.data includes 'services' key"""
        with server.STATE_LOCK:
            self.assertIn('services', server.STATE['data'])
    
    def test_state_services_defaults_to_empty_list(self):
        """Test that services defaults to empty list"""
        with server.STATE_LOCK:
            self.assertEqual(server.STATE['data']['services'], [])
    
    def test_get_state_snapshot_includes_services(self):
        """Test that get_state_snapshot returns services"""
        server.update_state_atomic({
            'projects': [],
            'pipelines': [],
            'summary': {},
            'services': [{'id': 'test', 'status': 'UP'}]
        })
        
        snapshot = server.get_state_snapshot()
        self.assertIn('services', snapshot['data'])
        self.assertEqual(len(snapshot['data']['services']), 1)
        self.assertEqual(snapshot['data']['services'][0]['id'], 'test')


class TestExternalServicesConfig(unittest.TestCase):
    """Test external_services configuration loading and validation"""
    
    def setUp(self):
        """Clear environment variables before each test"""
        self.env_backup = os.environ.copy()
        # Clear relevant env vars
        for key in list(os.environ.keys()):
            if key.startswith('GITLAB_') or key in ['PORT', 'CACHE_TTL', 'POLL_INTERVAL', 'PER_PAGE', 'INSECURE_SKIP_VERIFY', 'USE_MOCK_DATA']:
                del os.environ[key]
    
    def tearDown(self):
        """Restore environment variables after each test"""
        os.environ.clear()
        os.environ.update(self.env_backup)
    
    def test_load_config_external_services_defaults_to_empty_list(self):
        """Test external_services defaults to empty list when not specified"""
        with patch('os.path.exists', return_value=False):
            config = server.load_config()
            self.assertEqual(config['external_services'], [])
    
    def test_load_config_external_services_from_config_json(self):
        """Test external_services loaded from config.json"""
        mock_config = {
            'external_services': [
                {'name': 'Artifactory', 'url': 'https://artifactory.example.com/health'}
            ]
        }
        
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=json.dumps(mock_config))):
                config = server.load_config()
                self.assertEqual(len(config['external_services']), 1)
                self.assertEqual(config['external_services'][0]['name'], 'Artifactory')
    
    def test_load_config_external_services_null_becomes_empty_list(self):
        """Test null external_services becomes empty list"""
        mock_config = {'external_services': None}
        
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=json.dumps(mock_config))):
                config = server.load_config()
                self.assertEqual(config['external_services'], [])
    
    def test_load_config_external_services_string_becomes_empty_list(self):
        """Test non-list external_services becomes empty list with warning"""
        mock_config = {'external_services': 'invalid'}
        
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=json.dumps(mock_config))):
                config = server.load_config()
                self.assertEqual(config['external_services'], [])


class TestExternalServicesValidation(unittest.TestCase):
    """Test external_services configuration validation"""
    
    def test_validate_config_valid_external_services(self):
        """Test validation passes for valid external_services"""
        config = {
            'use_mock_data': True,
            'poll_interval_sec': 60,
            'cache_ttl_sec': 300,
            'per_page': 100,
            'external_services': [
                {'name': 'Artifactory', 'url': 'https://artifactory.example.com/health'},
                {'id': 'jira', 'name': 'Jira', 'url': 'https://jira.example.com/status'}
            ]
        }
        
        result = server.validate_config(config)
        self.assertTrue(result)
    
    def test_validate_config_empty_external_services_valid(self):
        """Test validation passes for empty external_services"""
        config = {
            'use_mock_data': True,
            'poll_interval_sec': 60,
            'cache_ttl_sec': 300,
            'per_page': 100,
            'external_services': []
        }
        
        result = server.validate_config(config)
        self.assertTrue(result)
    
    def test_validate_config_external_service_not_dict_fails(self):
        """Test validation fails when external service is not a dict"""
        config = {
            'use_mock_data': True,
            'poll_interval_sec': 60,
            'cache_ttl_sec': 300,
            'per_page': 100,
            'external_services': [
                {'name': 'Valid', 'url': 'https://valid.example.com'},
                'invalid_string'
            ]
        }
        
        result = server.validate_config(config)
        self.assertFalse(result)
    
    def test_validate_config_external_service_missing_url_fails(self):
        """Test validation fails when external service missing url"""
        config = {
            'use_mock_data': True,
            'poll_interval_sec': 60,
            'cache_ttl_sec': 300,
            'per_page': 100,
            'external_services': [
                {'name': 'Missing URL'}
            ]
        }
        
        result = server.validate_config(config)
        self.assertFalse(result)
    
    def test_validate_config_external_service_empty_url_fails(self):
        """Test validation fails when external service has empty url"""
        config = {
            'use_mock_data': True,
            'poll_interval_sec': 60,
            'cache_ttl_sec': 300,
            'per_page': 100,
            'external_services': [
                {'name': 'Empty URL', 'url': ''}
            ]
        }
        
        result = server.validate_config(config)
        self.assertFalse(result)


class TestBackgroundPollerExternalServices(unittest.TestCase):
    """Test BackgroundPoller external services handling"""
    
    def test_poller_accepts_external_services(self):
        """Test BackgroundPoller accepts external_services parameter"""
        mock_client = MagicMock()
        services = [{'name': 'Test', 'url': 'https://test.example.com'}]
        
        poller = server.BackgroundPoller(
            mock_client,
            60,
            external_services=services
        )
        
        self.assertEqual(poller.external_services, services)
    
    def test_poller_external_services_defaults_to_empty(self):
        """Test BackgroundPoller external_services defaults to empty list"""
        mock_client = MagicMock()
        
        poller = server.BackgroundPoller(mock_client, 60)
        
        self.assertEqual(poller.external_services, [])
    
    def test_poller_external_services_none_becomes_empty(self):
        """Test BackgroundPoller handles None external_services"""
        mock_client = MagicMock()
        
        poller = server.BackgroundPoller(mock_client, 60, external_services=None)
        
        self.assertEqual(poller.external_services, [])
    
    def test_poller_external_services_non_list_becomes_empty(self):
        """Test BackgroundPoller handles non-list external_services"""
        mock_client = MagicMock()
        
        poller = server.BackgroundPoller(mock_client, 60, external_services="invalid")
        
        self.assertEqual(poller.external_services, [])


class TestExternalServiceChecks(unittest.TestCase):
    """Test _check_external_services method"""
    
    def setUp(self):
        """Create mock GitLab client and poller"""
        self.mock_client = MagicMock()
        self.mock_client.ssl_context = None
    
    def test_check_external_services_empty_list(self):
        """Test _check_external_services returns empty list when no services configured"""
        poller = server.BackgroundPoller(self.mock_client, 60, external_services=[])
        
        result = poller._check_external_services()
        
        self.assertEqual(result, [])
    
    def test_check_external_services_skips_invalid_config(self):
        """Test _check_external_services skips non-dict entries"""
        poller = server.BackgroundPoller(
            self.mock_client, 
            60, 
            external_services=['invalid', None, 123]
        )
        
        result = poller._check_external_services()
        
        self.assertEqual(result, [])
    
    def test_check_external_services_skips_missing_url(self):
        """Test _check_external_services skips entries without url"""
        poller = server.BackgroundPoller(
            self.mock_client, 
            60, 
            external_services=[{'name': 'No URL'}]
        )
        
        result = poller._check_external_services()
        
        self.assertEqual(result, [])
    
    def test_check_external_services_resolves_name(self):
        """Test _check_external_services uses name -> id -> url for name"""
        poller = server.BackgroundPoller(
            self.mock_client, 
            60, 
            external_services=[{'name': 'Test Service', 'url': 'https://test.example.com'}]
        )
        
        # Now _check_external_services delegates to services module, so patch at module level
        with patch.object(services_module, '_check_single_service') as mock_check:
            mock_check.return_value = {'id': 'test-service', 'name': 'Test Service', 'status': 'UP'}
            
            result = poller._check_external_services()
            
            # Check that _check_single_service was called with correct name
            mock_check.assert_called_once()
            call_kwargs = mock_check.call_args[1]
            self.assertEqual(call_kwargs['name'], 'Test Service')
    
    def test_check_external_services_generates_stable_id(self):
        """Test _check_external_services generates stable ID from name"""
        poller = server.BackgroundPoller(
            self.mock_client, 
            60, 
            external_services=[{'name': 'My Test Service', 'url': 'https://test.example.com'}]
        )
        
        with patch.object(services_module, '_check_single_service') as mock_check:
            mock_check.return_value = {'id': 'my-test-service', 'name': 'My Test Service', 'status': 'UP'}
            
            poller._check_external_services()
            
            # Check that _check_single_service was called with normalized ID
            call_kwargs = mock_check.call_args[1]
            self.assertEqual(call_kwargs['service_id'], 'my-test-service')
    
    def test_check_external_services_uses_explicit_id(self):
        """Test _check_external_services uses explicit id when provided"""
        poller = server.BackgroundPoller(
            self.mock_client, 
            60, 
            external_services=[{'id': 'custom-id', 'name': 'Service', 'url': 'https://test.example.com'}]
        )
        
        with patch.object(services_module, '_check_single_service') as mock_check:
            mock_check.return_value = {'id': 'custom-id', 'name': 'Service', 'status': 'UP'}
            
            poller._check_external_services()
            
            call_kwargs = mock_check.call_args[1]
            self.assertEqual(call_kwargs['service_id'], 'custom-id')
    
    def test_check_external_services_uses_default_timeout(self):
        """Test _check_external_services uses default timeout when not specified"""
        poller = server.BackgroundPoller(
            self.mock_client, 
            60, 
            external_services=[{'name': 'Service', 'url': 'https://test.example.com'}]
        )
        
        with patch.object(services_module, '_check_single_service') as mock_check:
            mock_check.return_value = {'id': 'service', 'name': 'Service', 'status': 'UP'}
            
            poller._check_external_services()
            
            call_kwargs = mock_check.call_args[1]
            self.assertEqual(call_kwargs['timeout'], server.DEFAULT_SERVICE_CHECK_TIMEOUT)
    
    def test_check_external_services_uses_custom_timeout(self):
        """Test _check_external_services uses custom timeout when specified"""
        poller = server.BackgroundPoller(
            self.mock_client, 
            60, 
            external_services=[{'name': 'Service', 'url': 'https://test.example.com', 'timeout': 5}]
        )
        
        with patch.object(services_module, '_check_single_service') as mock_check:
            mock_check.return_value = {'id': 'service', 'name': 'Service', 'status': 'UP'}
            
            poller._check_external_services()
            
            call_kwargs = mock_check.call_args[1]
            self.assertEqual(call_kwargs['timeout'], 5)


class TestSingleServiceCheck(unittest.TestCase):
    """Test _check_single_service function from services module"""
    
    def test_check_single_service_success(self):
        """Test _check_single_service returns UP for successful response"""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.close = MagicMock()
        
        with patch('backend.services.urlopen', return_value=mock_response):
            result = services_module._check_single_service(
                url='https://test.example.com',
                name='Test',
                service_id='test',
                timeout=10
            )
        
        self.assertEqual(result['status'], 'UP')
        self.assertEqual(result['http_status'], 200)
        self.assertEqual(result['id'], 'test')
        self.assertEqual(result['name'], 'Test')
        self.assertIsNotNone(result['latency_ms'])
        self.assertIsNone(result['error'])
    
    def test_check_single_service_redirect_is_up(self):
        """Test _check_single_service returns UP for redirect response"""
        mock_response = MagicMock()
        mock_response.status = 302
        mock_response.close = MagicMock()
        
        with patch('backend.services.urlopen', return_value=mock_response):
            result = services_module._check_single_service(
                url='https://test.example.com',
                name='Test',
                service_id='test',
                timeout=10
            )
        
        self.assertEqual(result['status'], 'UP')
        self.assertEqual(result['http_status'], 302)
    
    def test_check_single_service_500_is_down(self):
        """Test _check_single_service returns DOWN for 5xx response"""
        mock_error = HTTPError(
            url='https://test.example.com',
            code=500,
            msg='Internal Server Error',
            hdrs=None,
            fp=None
        )
        
        with patch('backend.services.urlopen', side_effect=mock_error):
            result = services_module._check_single_service(
                url='https://test.example.com',
                name='Test',
                service_id='test',
                timeout=10
            )
        
        self.assertEqual(result['status'], 'DOWN')
        self.assertEqual(result['http_status'], 500)
        self.assertIn('500', result['error'])
    
    def test_check_single_service_timeout_is_down(self):
        """Test _check_single_service returns DOWN for timeout"""
        mock_error = URLError('timed out')
        
        with patch('backend.services.urlopen', side_effect=mock_error):
            result = services_module._check_single_service(
                url='https://test.example.com',
                name='Test',
                service_id='test',
                timeout=10
            )
        
        self.assertEqual(result['status'], 'DOWN')
        self.assertIsNone(result['http_status'])
        self.assertIn('timed out', result['error'])
    
    def test_check_single_service_connection_refused_is_down(self):
        """Test _check_single_service returns DOWN for connection refused"""
        mock_error = URLError('Connection refused')
        
        with patch('backend.services.urlopen', side_effect=mock_error):
            result = services_module._check_single_service(
                url='https://test.example.com',
                name='Test',
                service_id='test',
                timeout=10
            )
        
        self.assertEqual(result['status'], 'DOWN')
        self.assertIn('Connection refused', result['error'])
    
    def test_check_single_service_includes_last_checked(self):
        """Test _check_single_service includes last_checked timestamp"""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.close = MagicMock()
        
        with patch('backend.services.urlopen', return_value=mock_response):
            result = services_module._check_single_service(
                url='https://test.example.com',
                name='Test',
                service_id='test',
                timeout=10
            )
        
        self.assertIn('last_checked', result)
        # Verify it's a valid ISO timestamp
        datetime.fromisoformat(result['last_checked'])


class TestServicesEndpoint(unittest.TestCase):
    """Test /api/services endpoint handler"""
    
    def setUp(self):
        """Reset global STATE before each test"""
        with server.STATE_LOCK:
            server.STATE['data'] = {
                'projects': [],
                'pipelines': [],
                'summary': dict(server.DEFAULT_SUMMARY),
                'services': []
            }
            server.STATE['last_updated'] = None
            server.STATE['services_last_updated'] = None
            server.STATE['status'] = 'INITIALIZING'
            server.STATE['error'] = None
    
    def test_handle_services_empty_state(self):
        """Test /api/services returns proper shape when services list is empty"""
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.send_json_response = MagicMock()
        
        server.DashboardRequestHandler.handle_services(handler)
        
        handler.send_json_response.assert_called_once()
        response_data = handler.send_json_response.call_args[0][0]
        
        self.assertIn('services', response_data)
        self.assertIn('total', response_data)
        self.assertIn('backend_status', response_data)
        self.assertIn('is_mock', response_data)
        self.assertEqual(response_data['services'], [])
        self.assertEqual(response_data['total'], 0)
    
    def test_handle_services_with_data(self):
        """Test /api/services returns services data"""
        # Set up STATE with services
        services = [
            {'id': 'artifactory', 'name': 'Artifactory', 'status': 'UP', 'latency_ms': 50},
            {'id': 'jira', 'name': 'Jira', 'status': 'DOWN', 'error': 'Timeout'}
        ]
        server.update_state_atomic({
            'projects': [],
            'pipelines': [],
            'summary': {},
            'services': services
        })
        
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.send_json_response = MagicMock()
        
        server.DashboardRequestHandler.handle_services(handler)
        
        response_data = handler.send_json_response.call_args[0][0]
        
        self.assertEqual(len(response_data['services']), 2)
        self.assertEqual(response_data['total'], 2)
        self.assertEqual(response_data['services'][0]['status'], 'UP')
        self.assertEqual(response_data['services'][1]['status'], 'DOWN')
    
    def test_handle_services_includes_last_updated(self):
        """Test /api/services includes last_updated timestamp"""
        server.update_state_atomic({
            'projects': [],
            'pipelines': [],
            'summary': {},
            'services': []
        })
        
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.send_json_response = MagicMock()
        
        server.DashboardRequestHandler.handle_services(handler)
        
        response_data = handler.send_json_response.call_args[0][0]
        
        self.assertIn('last_updated', response_data)
        self.assertIsNotNone(response_data['last_updated'])
    
    def test_handle_services_includes_backend_status(self):
        """Test /api/services includes backend_status"""
        server.update_state_atomic({
            'projects': [],
            'pipelines': [],
            'summary': {},
            'services': []
        })
        
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.send_json_response = MagicMock()
        
        server.DashboardRequestHandler.handle_services(handler)
        
        response_data = handler.send_json_response.call_args[0][0]
        
        self.assertEqual(response_data['backend_status'], 'ONLINE')
    
    def test_handle_services_error_returns_500(self):
        """Test /api/services returns 500 on error with proper shape"""
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.send_json_response = MagicMock()
        
        # Mock get_state_snapshot to raise exception
        with patch('backend.app.get_state_snapshot', side_effect=Exception('Test error')):
            server.DashboardRequestHandler.handle_services(handler)
        
        handler.send_json_response.assert_called_once()
        args, kwargs = handler.send_json_response.call_args
        response_data = args[0]
        status = kwargs.get('status', 200)
        
        self.assertEqual(status, 500)
        self.assertIn('services', response_data)
        self.assertEqual(response_data['services'], [])
        self.assertIn('error', response_data)


class TestServicesInMockMode(unittest.TestCase):
    """Test services handling in mock mode"""
    
    def setUp(self):
        """Reset state and backup mock mode flag"""
        self.original_mock_mode = server.MOCK_MODE_ENABLED
        self.original_mock_scenario = server.MOCK_SCENARIO
        
        with server.STATE_LOCK:
            server.STATE['data'] = {
                'projects': [],
                'pipelines': [],
                'summary': dict(server.DEFAULT_SUMMARY),
                'services': []
            }
            server.STATE['last_updated'] = None
            server.STATE['services_last_updated'] = None
            server.STATE['status'] = 'INITIALIZING'
            server.STATE['error'] = None
    
    def tearDown(self):
        """Restore mock mode flag"""
        server.MOCK_MODE_ENABLED = self.original_mock_mode
        server.MOCK_SCENARIO = self.original_mock_scenario
    
    def test_handle_services_includes_is_mock_when_enabled(self):
        """Test /api/services includes is_mock=true when mock mode enabled"""
        server.MOCK_MODE_ENABLED = True
        
        server.update_state_atomic({
            'projects': [],
            'pipelines': [],
            'summary': {},
            'services': []
        })
        
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.send_json_response = MagicMock()
        
        server.DashboardRequestHandler.handle_services(handler)
        
        response_data = handler.send_json_response.call_args[0][0]
        
        self.assertIn('is_mock', response_data)
        self.assertTrue(response_data['is_mock'])
    
    def test_handle_services_includes_is_mock_when_disabled(self):
        """Test /api/services includes is_mock=false when mock mode disabled"""
        server.MOCK_MODE_ENABLED = False
        
        server.update_state_atomic({
            'projects': [],
            'pipelines': [],
            'summary': {},
            'services': []
        })
        
        handler = MagicMock(spec=server.DashboardRequestHandler)
        handler.send_json_response = MagicMock()
        
        server.DashboardRequestHandler.handle_services(handler)
        
        response_data = handler.send_json_response.call_args[0][0]
        
        self.assertIn('is_mock', response_data)
        self.assertFalse(response_data['is_mock'])


class TestPollDataIncludesServices(unittest.TestCase):
    """Test that poll_data updates services in STATE"""
    
    def setUp(self):
        """Create mock GitLab client and poller"""
        self.mock_client = MagicMock()
        self.mock_client.ssl_context = None
        
        # Reset STATE
        with server.STATE_LOCK:
            server.STATE['data'] = {
                'projects': [],
                'pipelines': [],
                'summary': dict(server.DEFAULT_SUMMARY),
                'services': []
            }
            server.STATE['last_updated'] = None
            server.STATE['services_last_updated'] = None
            server.STATE['status'] = 'INITIALIZING'
            server.STATE['error'] = None
    
    def test_poll_data_updates_services_in_state(self):
        """Test poll_data includes services in atomic state update"""
        services_config = [{'name': 'Test', 'url': 'https://test.example.com'}]
        poller = server.BackgroundPoller(
            self.mock_client,
            60,
            external_services=services_config
        )
        
        # Mock the methods
        with patch.object(poller, '_fetch_projects', return_value=[]):
            with patch.object(poller, '_fetch_pipelines', return_value={'all_pipelines': [], 'per_project': {}}):
                with patch.object(poller, '_enrich_projects_with_pipelines', return_value=[]):
                    with patch.object(poller, '_calculate_summary', return_value={}):
                        with patch.object(poller, '_check_external_services', return_value=[
                            {'id': 'test', 'name': 'Test', 'status': 'UP'}
                        ]):
                            poller.poll_data('test-poll')
        
        # Verify services was updated in STATE
        snapshot = server.get_state_snapshot()
        self.assertIn('services', snapshot['data'])
        self.assertEqual(len(snapshot['data']['services']), 1)
        self.assertEqual(snapshot['data']['services'][0]['status'], 'UP')
    
    def test_poll_data_updates_services_when_gitlab_fails(self):
        """Test services are updated even when GitLab API fails
        
        External service checks should be decoupled from GitLab fetches,
        so service health continues to refresh during GitLab outages.
        """
        services_config = [{'name': 'Test', 'url': 'https://test.example.com'}]
        poller = server.BackgroundPoller(
            self.mock_client,
            60,
            external_services=services_config
        )
        
        # Mock GitLab fetches to fail
        with patch.object(poller, '_fetch_projects', return_value=None):  # GitLab failure
            with patch.object(poller, '_check_external_services', return_value=[
                {'id': 'test', 'name': 'Test', 'status': 'UP'}
            ]):
                poller.poll_data('test-poll')
        
        # Verify services was still updated despite GitLab failure
        snapshot = server.get_state_snapshot()
        self.assertIn('services', snapshot['data'])
        self.assertEqual(len(snapshot['data']['services']), 1)
        self.assertEqual(snapshot['data']['services'][0]['status'], 'UP')
        # But status should be ERROR due to GitLab failure
        self.assertEqual(snapshot['status'], 'ERROR')
    
    def test_poll_data_updates_services_when_pipeline_fetch_fails(self):
        """Test services are updated even when pipeline fetch fails
        
        External service checks should continue even when GitLab 
        pipeline API calls fail.
        """
        services_config = [{'name': 'Test', 'url': 'https://test.example.com'}]
        poller = server.BackgroundPoller(
            self.mock_client,
            60,
            external_services=services_config
        )
        
        # Mock projects success but pipelines fail
        with patch.object(poller, '_fetch_projects', return_value=[]):
            with patch.object(poller, '_fetch_pipelines', return_value=None):  # Pipeline failure
                with patch.object(poller, '_check_external_services', return_value=[
                    {'id': 'svc', 'name': 'Service', 'status': 'DOWN', 'error': 'Connection refused'}
                ]):
                    poller.poll_data('test-poll')
        
        # Verify services was still updated despite pipeline failure
        snapshot = server.get_state_snapshot()
        self.assertEqual(len(snapshot['data']['services']), 1)
        self.assertEqual(snapshot['data']['services'][0]['status'], 'DOWN')
        # But status should be ERROR due to pipeline failure
        self.assertEqual(snapshot['status'], 'ERROR')
    
    def test_services_timestamp_updates_during_gitlab_failure(self):
        """Test services_last_updated is set even when GitLab fails
        
        The /api/services endpoint needs a fresh timestamp to indicate
        when services were last checked, independent of GitLab state.
        """
        services_config = [{'name': 'Test', 'url': 'https://test.example.com'}]
        poller = server.BackgroundPoller(
            self.mock_client,
            60,
            external_services=services_config
        )
        
        # Verify services_last_updated is initially None
        snapshot_before = server.get_state_snapshot()
        self.assertIsNone(snapshot_before['services_last_updated'])
        
        # Mock GitLab fetches to fail
        with patch.object(poller, '_fetch_projects', return_value=None):  # GitLab failure
            with patch.object(poller, '_check_external_services', return_value=[
                {'id': 'test', 'name': 'Test', 'status': 'UP'}
            ]):
                poller.poll_data('test-poll')
        
        # Verify services_last_updated was set despite GitLab failure
        snapshot = server.get_state_snapshot()
        self.assertIsNotNone(snapshot['services_last_updated'])
        # last_updated (GitLab timestamp) should still be None since GitLab never succeeded
        self.assertIsNone(snapshot['last_updated'])
        # But services timestamp should be set
        self.assertIsInstance(snapshot['services_last_updated'], datetime)


if __name__ == '__main__':
    unittest.main()

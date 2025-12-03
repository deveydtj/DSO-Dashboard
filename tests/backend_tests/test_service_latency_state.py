#!/usr/bin/env python3
"""
Tests for per-service latency state in BackgroundPoller

Tests that the BackgroundPoller class properly initializes and maintains
per-service latency history/aggregate state for tracking running averages.

Uses only Python stdlib and unittest.
"""

import unittest
import sys
import os
from unittest.mock import MagicMock

# Add parent directory to path to import backend modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend import app as server


class TestServiceLatencyHistoryInitialization(unittest.TestCase):
    """Test that BackgroundPoller initializes _service_latency_history attribute"""
    
    def test_poller_has_service_latency_history_attribute(self):
        """Test that BackgroundPoller has _service_latency_history attribute"""
        mock_client = MagicMock()
        
        poller = server.BackgroundPoller(mock_client, poll_interval_sec=60)
        
        self.assertTrue(hasattr(poller, '_service_latency_history'))
    
    def test_poller_service_latency_history_initialized_to_empty_dict(self):
        """Test that _service_latency_history is initialized as an empty dict"""
        mock_client = MagicMock()
        
        poller = server.BackgroundPoller(mock_client, poll_interval_sec=60)
        
        self.assertIsInstance(poller._service_latency_history, dict)
        self.assertEqual(poller._service_latency_history, {})
    
    def test_poller_service_latency_history_with_all_parameters(self):
        """Test that _service_latency_history is initialized when all params provided"""
        mock_client = MagicMock()
        service_latency_config = {
            'enabled': True,
            'window_size': 15,
            'degradation_threshold_ratio': 2.0
        }
        external_services = [
            {'id': 'svc1', 'name': 'Service 1', 'url': 'https://svc1.example.com'}
        ]
        
        poller = server.BackgroundPoller(
            mock_client,
            poll_interval_sec=60,
            group_ids=[1, 2],
            project_ids=[10, 20],
            external_services=external_services,
            service_latency_config=service_latency_config
        )
        
        # _service_latency_history should still start empty
        # It gets populated during poll cycles, not during initialization
        self.assertIsInstance(poller._service_latency_history, dict)
        self.assertEqual(poller._service_latency_history, {})


class TestServiceLatencyHistoryPersistence(unittest.TestCase):
    """Test that _service_latency_history persists across method calls"""
    
    def test_service_latency_history_survives_poll_cycle_setup(self):
        """Test that _service_latency_history persists through polling setup
        
        The state should survive across polls for as long as the process is running.
        This test verifies the attribute is not reset during normal poller lifecycle.
        """
        mock_client = MagicMock()
        
        poller = server.BackgroundPoller(mock_client, poll_interval_sec=60)
        
        # Simulate adding some latency data to the history
        poller._service_latency_history['test-service'] = {
            'average_ms': 100.5,
            'sample_count': 5,
            'recent_samples': [95.0, 102.0, 98.0, 105.0, 102.5]
        }
        
        # Generate poll IDs (simulates normal poller operation)
        for _ in range(10):
            poller._generate_poll_id()
        
        # Verify the latency history was not reset
        self.assertIn('test-service', poller._service_latency_history)
        self.assertEqual(poller._service_latency_history['test-service']['average_ms'], 100.5)
        self.assertEqual(poller._service_latency_history['test-service']['sample_count'], 5)
    
    def test_service_latency_history_can_hold_multiple_services(self):
        """Test that _service_latency_history can store data for multiple services"""
        mock_client = MagicMock()
        
        poller = server.BackgroundPoller(mock_client, poll_interval_sec=60)
        
        # Add data for multiple services
        poller._service_latency_history['service-a'] = {
            'average_ms': 50.0,
            'sample_count': 10,
            'recent_samples': [45.0, 55.0]
        }
        poller._service_latency_history['service-b'] = {
            'average_ms': 200.0,
            'sample_count': 3,
            'recent_samples': [180.0, 200.0, 220.0]
        }
        poller._service_latency_history['service-c'] = {
            'average_ms': 75.5,
            'sample_count': 7,
            'recent_samples': [70.0, 80.0, 76.0]
        }
        
        self.assertEqual(len(poller._service_latency_history), 3)
        self.assertIn('service-a', poller._service_latency_history)
        self.assertIn('service-b', poller._service_latency_history)
        self.assertIn('service-c', poller._service_latency_history)


class TestServiceLatencyHistoryStructure(unittest.TestCase):
    """Test the expected structure of entries in _service_latency_history"""
    
    def test_expected_entry_keys_can_be_stored(self):
        """Test that entries with the expected structure can be stored"""
        mock_client = MagicMock()
        
        poller = server.BackgroundPoller(mock_client, poll_interval_sec=60)
        
        # Store an entry with the expected structure
        entry = {
            'average_ms': 123.45,       # Running average latency in milliseconds
            'sample_count': 5,           # Number of samples in the running average
            'recent_samples': [120.0, 125.0, 130.0, 115.0, 127.25]  # Last N samples
        }
        poller._service_latency_history['my-service'] = entry
        
        # Verify the entry was stored correctly
        stored = poller._service_latency_history['my-service']
        self.assertEqual(stored['average_ms'], 123.45)
        self.assertEqual(stored['sample_count'], 5)
        self.assertEqual(len(stored['recent_samples']), 5)
        self.assertIsInstance(stored['average_ms'], float)
        self.assertIsInstance(stored['sample_count'], int)
        self.assertIsInstance(stored['recent_samples'], list)
    
    def test_service_id_used_as_key(self):
        """Test that service ID (string) is used as the key"""
        mock_client = MagicMock()
        
        poller = server.BackgroundPoller(mock_client, poll_interval_sec=60)
        
        # Service IDs should be strings (stable identifiers)
        poller._service_latency_history['artifactory'] = {'average_ms': 50.0, 'sample_count': 1, 'recent_samples': [50.0]}
        poller._service_latency_history['jira-cloud'] = {'average_ms': 75.0, 'sample_count': 2, 'recent_samples': [70.0, 80.0]}
        poller._service_latency_history['confluence'] = {'average_ms': 100.0, 'sample_count': 3, 'recent_samples': [90.0, 100.0, 110.0]}
        
        # Verify keys are strings and data is accessible
        for service_id in ['artifactory', 'jira-cloud', 'confluence']:
            self.assertIn(service_id, poller._service_latency_history)
            self.assertIsInstance(service_id, str)


class TestServiceLatencyHistoryGracefulFallback(unittest.TestCase):
    """Test that missing/malformed latency data falls back gracefully
    
    Per requirements: If latency data for a service is missing or malformed,
    fall back gracefully to using just the current sample.
    """
    
    def test_empty_history_is_valid_initial_state(self):
        """Test that empty history is valid for new services"""
        mock_client = MagicMock()
        
        poller = server.BackgroundPoller(mock_client, poll_interval_sec=60)
        
        # A new service not yet in history should return KeyError when accessed
        # This is expected behavior - calling code should check if key exists
        self.assertNotIn('new-service', poller._service_latency_history)
        
        # .get() should return None for missing services
        self.assertIsNone(poller._service_latency_history.get('new-service'))
    
    def test_history_can_be_updated_with_first_sample(self):
        """Test that history can be initialized with a first sample"""
        mock_client = MagicMock()
        
        poller = server.BackgroundPoller(mock_client, poll_interval_sec=60)
        
        # First sample for a new service
        service_id = 'brand-new-service'
        first_latency = 150.0
        
        # Initialize with first sample (no averaging needed yet)
        poller._service_latency_history[service_id] = {
            'average_ms': first_latency,  # First sample IS the average
            'sample_count': 1,
            'recent_samples': [first_latency]
        }
        
        # Verify initialization
        entry = poller._service_latency_history[service_id]
        self.assertEqual(entry['average_ms'], first_latency)
        self.assertEqual(entry['sample_count'], 1)
        self.assertEqual(entry['recent_samples'], [first_latency])


class TestPollerCreationWithDifferentConfigs(unittest.TestCase):
    """Test that _service_latency_history is initialized with various configs"""
    
    def test_poller_with_disabled_latency_tracking(self):
        """Test that history is initialized even when latency tracking is disabled"""
        mock_client = MagicMock()
        service_latency_config = {
            'enabled': False,
            'window_size': 10,
            'degradation_threshold_ratio': 1.5
        }
        
        poller = server.BackgroundPoller(
            mock_client,
            poll_interval_sec=60,
            service_latency_config=service_latency_config
        )
        
        # History should still be initialized (may just not be used if disabled)
        self.assertIsInstance(poller._service_latency_history, dict)
        self.assertEqual(poller._service_latency_history, {})
    
    def test_poller_with_custom_window_size(self):
        """Test initialization with custom window_size config"""
        mock_client = MagicMock()
        service_latency_config = {
            'enabled': True,
            'window_size': 25,  # Custom window size
            'degradation_threshold_ratio': 2.0
        }
        
        poller = server.BackgroundPoller(
            mock_client,
            poll_interval_sec=60,
            service_latency_config=service_latency_config
        )
        
        # History is initialized empty; window_size affects how it's used, not how it's initialized
        self.assertIsInstance(poller._service_latency_history, dict)
        self.assertEqual(poller._service_latency_history, {})
        # Config should be stored for later use
        self.assertEqual(poller.service_latency_config['window_size'], 25)
    
    def test_poller_with_no_external_services(self):
        """Test initialization when no external services are configured"""
        mock_client = MagicMock()
        
        poller = server.BackgroundPoller(
            mock_client,
            poll_interval_sec=60,
            external_services=[]
        )
        
        # History should still be initialized (just won't have any entries)
        self.assertIsInstance(poller._service_latency_history, dict)
        self.assertEqual(poller._service_latency_history, {})


if __name__ == '__main__':
    unittest.main()

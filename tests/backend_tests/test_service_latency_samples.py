#!/usr/bin/env python3
"""
Tests for service latency_samples_ms field in BackgroundPoller

Tests that _annotate_services_with_latency_metrics() correctly includes
the latency_samples_ms field in service payloads for persistence across
browser refreshes.

Uses only Python stdlib and unittest.
"""

import unittest
import sys
import os
from unittest.mock import MagicMock

# Add parent directory to path to import backend modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend import app as server


class TestLatencySamplesIncluded(unittest.TestCase):
    """Test that latency_samples_ms field is included when latency monitoring is enabled"""
    
    def setUp(self):
        """Create a poller with latency monitoring enabled"""
        self.mock_client = MagicMock()
        self.service_latency_config = {
            'enabled': True,
            'window_size': 5,
            'degradation_threshold_ratio': 1.5
        }
        self.poller = server.BackgroundPoller(
            self.mock_client,
            poll_interval_sec=60,
            service_latency_config=self.service_latency_config
        )
    
    def test_first_sample_includes_one_element_array(self):
        """Test that first sample includes latency_samples_ms with one element"""
        services = [
            {'id': 'svc1', 'name': 'Service 1', 'status': 'UP', 'latency_ms': 100.0}
        ]
        
        result = self.poller._annotate_services_with_latency_metrics(services)
        
        self.assertIn('latency_samples_ms', result[0])
        self.assertIsInstance(result[0]['latency_samples_ms'], list)
        self.assertEqual(len(result[0]['latency_samples_ms']), 1)
        self.assertEqual(result[0]['latency_samples_ms'][0], 100.0)
    
    def test_samples_grow_over_time(self):
        """Test that latency_samples_ms grows with each poll"""
        services = [
            {'id': 'svc1', 'name': 'Service 1', 'status': 'UP', 'latency_ms': 100.0}
        ]
        
        # First sample
        self.poller._annotate_services_with_latency_metrics(services)
        self.assertEqual(len(services[0]['latency_samples_ms']), 1)
        
        # Second sample
        services[0]['latency_ms'] = 110.0
        self.poller._annotate_services_with_latency_metrics(services)
        self.assertEqual(len(services[0]['latency_samples_ms']), 2)
        self.assertEqual(services[0]['latency_samples_ms'], [100.0, 110.0])
        
        # Third sample
        services[0]['latency_ms'] = 120.0
        self.poller._annotate_services_with_latency_metrics(services)
        self.assertEqual(len(services[0]['latency_samples_ms']), 3)
        self.assertEqual(services[0]['latency_samples_ms'], [100.0, 110.0, 120.0])
    
    def test_samples_bounded_by_window_size(self):
        """Test that latency_samples_ms never exceeds window_size"""
        self.poller.service_latency_config['window_size'] = 3
        
        services = [
            {'id': 'svc1', 'name': 'Service 1', 'status': 'UP', 'latency_ms': 100.0}
        ]
        
        # Add 5 samples (more than window_size)
        for i in range(5):
            services[0]['latency_ms'] = 100.0 + (i * 10.0)
            self.poller._annotate_services_with_latency_metrics(services)
        
        # Should only have last 3 samples
        self.assertEqual(len(services[0]['latency_samples_ms']), 3)
        self.assertEqual(services[0]['latency_samples_ms'], [120.0, 130.0, 140.0])
    
    def test_samples_list_maintains_order(self):
        """Test that samples are in chronological order (oldest to newest)"""
        services = [
            {'id': 'svc1', 'name': 'Service 1', 'status': 'UP', 'latency_ms': 50.0}
        ]
        
        latencies = [50.0, 75.0, 100.0, 125.0, 150.0]
        for latency in latencies:
            services[0]['latency_ms'] = latency
            self.poller._annotate_services_with_latency_metrics(services)
        
        # All 5 samples should be in order (window_size is 5)
        self.assertEqual(services[0]['latency_samples_ms'], latencies)
    
    def test_samples_rounded_to_2_decimal_places(self):
        """Test that sample values are rounded to 2 decimal places"""
        services = [
            {'id': 'svc1', 'name': 'Service 1', 'status': 'UP', 'latency_ms': 33.333}
        ]
        
        self.poller._annotate_services_with_latency_metrics(services)
        
        # Should be rounded to 2 decimal places
        self.assertEqual(services[0]['latency_samples_ms'][0], 33.33)
    
    def test_multiple_services_have_independent_samples(self):
        """Test that each service has its own independent sample list"""
        services = [
            {'id': 'fast', 'name': 'Fast Service', 'status': 'UP', 'latency_ms': 50.0},
            {'id': 'slow', 'name': 'Slow Service', 'status': 'UP', 'latency_ms': 500.0}
        ]
        
        # First poll
        self.poller._annotate_services_with_latency_metrics(services)
        
        # Second poll with different latencies
        services[0]['latency_ms'] = 60.0
        services[1]['latency_ms'] = 450.0
        self.poller._annotate_services_with_latency_metrics(services)
        
        # Each should have its own samples
        self.assertEqual(services[0]['latency_samples_ms'], [50.0, 60.0])
        self.assertEqual(services[1]['latency_samples_ms'], [500.0, 450.0])


class TestLatencySamplesDisabled(unittest.TestCase):
    """Test that latency_samples_ms is not included when monitoring is disabled"""
    
    def setUp(self):
        """Create a poller with latency monitoring disabled"""
        self.mock_client = MagicMock()
        self.service_latency_config = {
            'enabled': False,
            'window_size': 10,
            'degradation_threshold_ratio': 1.5
        }
        self.poller = server.BackgroundPoller(
            self.mock_client,
            poll_interval_sec=60,
            service_latency_config=self.service_latency_config
        )
    
    def test_no_samples_field_when_disabled(self):
        """Test that latency_samples_ms is not added when monitoring is disabled"""
        services = [
            {'id': 'svc1', 'name': 'Service 1', 'status': 'UP', 'latency_ms': 100.0}
        ]
        
        result = self.poller._annotate_services_with_latency_metrics(services)
        
        self.assertNotIn('latency_samples_ms', result[0])
    
    def test_no_samples_field_after_multiple_polls_when_disabled(self):
        """Test that latency_samples_ms remains absent across multiple polls when disabled"""
        services = [
            {'id': 'svc1', 'name': 'Service 1', 'status': 'UP', 'latency_ms': 100.0}
        ]
        
        # Multiple polls
        for i in range(5):
            services[0]['latency_ms'] = 100.0 + (i * 10.0)
            self.poller._annotate_services_with_latency_metrics(services)
            self.assertNotIn('latency_samples_ms', services[0])


class TestLatencySamplesWithInvalidData(unittest.TestCase):
    """Test handling of services without valid latency data"""
    
    def setUp(self):
        """Create a poller with latency monitoring enabled"""
        self.mock_client = MagicMock()
        self.service_latency_config = {
            'enabled': True,
            'window_size': 10,
            'degradation_threshold_ratio': 1.5
        }
        self.poller = server.BackgroundPoller(
            self.mock_client,
            poll_interval_sec=60,
            service_latency_config=self.service_latency_config
        )
    
    def test_no_samples_for_none_latency(self):
        """Test that services with None latency don't get samples field"""
        services = [
            {'id': 'svc1', 'name': 'Service 1', 'status': 'DOWN', 'latency_ms': None}
        ]
        
        result = self.poller._annotate_services_with_latency_metrics(services)
        
        self.assertNotIn('latency_samples_ms', result[0])
    
    def test_no_samples_for_missing_latency(self):
        """Test that services without latency_ms field don't get samples field"""
        services = [
            {'id': 'svc1', 'name': 'Service 1', 'status': 'DOWN', 'error': 'timeout'}
        ]
        
        result = self.poller._annotate_services_with_latency_metrics(services)
        
        self.assertNotIn('latency_samples_ms', result[0])
    
    def test_no_samples_for_invalid_latency_type(self):
        """Test that services with non-numeric latency don't get samples field"""
        services = [
            {'id': 'svc1', 'name': 'Service 1', 'status': 'UP', 'latency_ms': 'invalid'}
        ]
        
        result = self.poller._annotate_services_with_latency_metrics(services)
        
        self.assertNotIn('latency_samples_ms', result[0])
    
    def test_no_samples_for_service_without_id(self):
        """Test that services without id don't get samples field"""
        services = [
            {'name': 'Service 1', 'status': 'UP', 'latency_ms': 100.0}
        ]
        
        result = self.poller._annotate_services_with_latency_metrics(services)
        
        self.assertNotIn('latency_samples_ms', result[0])
    
    def test_mixed_valid_invalid_services(self):
        """Test that only valid services get samples field in mixed list"""
        services = [
            {'id': 'valid', 'name': 'Valid', 'status': 'UP', 'latency_ms': 100.0},
            {'id': 'no-latency', 'name': 'No Latency', 'status': 'DOWN', 'latency_ms': None},
            {'id': 'another-valid', 'name': 'Another', 'status': 'UP', 'latency_ms': 200.0}
        ]
        
        result = self.poller._annotate_services_with_latency_metrics(services)
        
        # First and third should have samples
        self.assertIn('latency_samples_ms', result[0])
        self.assertIn('latency_samples_ms', result[2])
        
        # Second should not have samples
        self.assertNotIn('latency_samples_ms', result[1])


class TestLatencySamplesWindowSize(unittest.TestCase):
    """Test that window_size configuration is respected for samples"""
    
    def test_custom_window_size_respected(self):
        """Test that custom window_size limits sample list length"""
        mock_client = MagicMock()
        service_latency_config = {
            'enabled': True,
            'window_size': 7,  # Custom window size
            'degradation_threshold_ratio': 1.5
        }
        poller = server.BackgroundPoller(
            mock_client,
            poll_interval_sec=60,
            service_latency_config=service_latency_config
        )
        
        services = [
            {'id': 'svc1', 'name': 'Service 1', 'status': 'UP', 'latency_ms': 100.0}
        ]
        
        # Add 10 samples
        for i in range(10):
            services[0]['latency_ms'] = 100.0 + (i * 10.0)
            poller._annotate_services_with_latency_metrics(services)
        
        # Should only have last 7 samples
        self.assertEqual(len(services[0]['latency_samples_ms']), 7)
    
    def test_default_window_size_applied(self):
        """Test that default window_size (10) is used when not specified"""
        mock_client = MagicMock()
        service_latency_config = {
            'enabled': True,
            # window_size not specified, should use default (10)
            'degradation_threshold_ratio': 1.5
        }
        poller = server.BackgroundPoller(
            mock_client,
            poll_interval_sec=60,
            service_latency_config=service_latency_config
        )
        
        services = [
            {'id': 'svc1', 'name': 'Service 1', 'status': 'UP', 'latency_ms': 100.0}
        ]
        
        # Add 15 samples
        for i in range(15):
            services[0]['latency_ms'] = 100.0 + (i * 10.0)
            poller._annotate_services_with_latency_metrics(services)
        
        # Should only have last 10 samples (default window_size)
        self.assertEqual(len(services[0]['latency_samples_ms']), 10)


class TestLatencySamplesConsistency(unittest.TestCase):
    """Test that latency_samples_ms is consistent with average_latency_ms"""
    
    def setUp(self):
        """Create a poller with latency monitoring enabled"""
        self.mock_client = MagicMock()
        self.service_latency_config = {
            'enabled': True,
            'window_size': 5,
            'degradation_threshold_ratio': 1.5
        }
        self.poller = server.BackgroundPoller(
            self.mock_client,
            poll_interval_sec=60,
            service_latency_config=self.service_latency_config
        )
    
    def test_average_computed_from_samples(self):
        """Test that average_latency_ms is the average of latency_samples_ms"""
        services = [
            {'id': 'svc1', 'name': 'Service 1', 'status': 'UP', 'latency_ms': 100.0}
        ]
        
        # Add samples
        latencies = [100.0, 200.0, 150.0, 250.0, 175.0]
        for latency in latencies:
            services[0]['latency_ms'] = latency
            self.poller._annotate_services_with_latency_metrics(services)
        
        # Verify samples are present
        self.assertEqual(services[0]['latency_samples_ms'], latencies)
        
        # Verify average matches samples
        expected_avg = sum(latencies) / len(latencies)
        self.assertAlmostEqual(services[0]['average_latency_ms'], expected_avg, places=2)


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python3
"""
Tests for service latency annotation functionality

Tests the _annotate_services_with_latency_metrics() method on BackgroundPoller
that computes running average, ratio, and trend for each service.

Uses only Python stdlib and unittest.
"""

import unittest
import sys
import os
from unittest.mock import MagicMock

# Add parent directory to path to import backend modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend import app as server


class TestAnnotateServicesEnabled(unittest.TestCase):
    """Test latency annotation when monitoring is enabled"""
    
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
    
    def test_first_sample_sets_average_equal_to_current(self):
        """Test that first sample for a service sets average equal to current"""
        services = [
            {'id': 'svc1', 'name': 'Service 1', 'status': 'UP', 'latency_ms': 100.0}
        ]
        
        result = self.poller._annotate_services_with_latency_metrics(services)
        
        self.assertEqual(result[0]['average_latency_ms'], 100.0)
        self.assertEqual(result[0]['latency_ratio'], 1.0)
        self.assertEqual(result[0]['latency_trend'], 'normal')
    
    def test_running_average_computed_correctly(self):
        """Test that running average is computed from recent samples"""
        services = [
            {'id': 'svc1', 'name': 'Service 1', 'status': 'UP', 'latency_ms': 100.0}
        ]
        
        # First sample
        self.poller._annotate_services_with_latency_metrics(services)
        
        # Second sample
        services[0]['latency_ms'] = 200.0
        self.poller._annotate_services_with_latency_metrics(services)
        
        # Average should be (100 + 200) / 2 = 150
        self.assertEqual(services[0]['average_latency_ms'], 150.0)
    
    def test_latency_ratio_computed_correctly(self):
        """Test that latency ratio is current / average"""
        services = [
            {'id': 'svc1', 'name': 'Service 1', 'status': 'UP', 'latency_ms': 100.0}
        ]
        
        # First sample
        self.poller._annotate_services_with_latency_metrics(services)
        
        # Second sample - double the latency
        services[0]['latency_ms'] = 200.0
        self.poller._annotate_services_with_latency_metrics(services)
        
        # Average is 150, current is 200, ratio = 200/150 = 1.33
        self.assertAlmostEqual(services[0]['latency_ratio'], 1.33, places=2)
    
    def test_warning_trend_when_exceeds_threshold(self):
        """Test that trend is 'warning' when ratio exceeds threshold"""
        # Use lower threshold for easier testing
        self.poller.service_latency_config['degradation_threshold_ratio'] = 1.5
        
        services = [
            {'id': 'svc1', 'name': 'Service 1', 'status': 'UP', 'latency_ms': 100.0}
        ]
        
        # First sample
        self.poller._annotate_services_with_latency_metrics(services)
        
        # Second sample - 200% of first (ratio 2.0 > threshold 1.5)
        services[0]['latency_ms'] = 200.0
        self.poller._annotate_services_with_latency_metrics(services)
        
        # avg is 150, current is 200, ratio is 1.33 (below 1.5)
        self.assertEqual(services[0]['latency_trend'], 'normal')
        
        # Third sample - 450ms (avg becomes ~250, ratio = 450/250 = 1.8 > 1.5)
        services[0]['latency_ms'] = 450.0
        self.poller._annotate_services_with_latency_metrics(services)
        
        self.assertEqual(services[0]['latency_trend'], 'warning')
    
    def test_normal_trend_when_below_threshold(self):
        """Test that trend is 'normal' when ratio is below threshold"""
        services = [
            {'id': 'svc1', 'name': 'Service 1', 'status': 'UP', 'latency_ms': 100.0}
        ]
        
        # Build up some history
        for _ in range(5):
            self.poller._annotate_services_with_latency_metrics(services)
        
        # Similar latency should be 'normal'
        services[0]['latency_ms'] = 110.0  # 10% above average
        self.poller._annotate_services_with_latency_metrics(services)
        
        self.assertEqual(services[0]['latency_trend'], 'normal')
    
    def test_window_size_limits_samples(self):
        """Test that only window_size recent samples are used"""
        self.poller.service_latency_config['window_size'] = 3
        
        services = [
            {'id': 'svc1', 'name': 'Service 1', 'status': 'UP', 'latency_ms': 100.0}
        ]
        
        # Add 5 samples of 100ms
        for _ in range(5):
            services[0]['latency_ms'] = 100.0
            self.poller._annotate_services_with_latency_metrics(services)
        
        # Now add 3 samples of 200ms (should replace all 100s in window)
        for _ in range(3):
            services[0]['latency_ms'] = 200.0
            self.poller._annotate_services_with_latency_metrics(services)
        
        # Average should now be 200 (only last 3 samples used)
        self.assertEqual(services[0]['average_latency_ms'], 200.0)
    
    def test_multiple_services_tracked_independently(self):
        """Test that each service has independent latency tracking"""
        services = [
            {'id': 'fast-svc', 'name': 'Fast Service', 'status': 'UP', 'latency_ms': 50.0},
            {'id': 'slow-svc', 'name': 'Slow Service', 'status': 'UP', 'latency_ms': 500.0}
        ]
        
        self.poller._annotate_services_with_latency_metrics(services)
        
        self.assertEqual(services[0]['average_latency_ms'], 50.0)
        self.assertEqual(services[1]['average_latency_ms'], 500.0)
        
        # Update with different values
        services[0]['latency_ms'] = 100.0
        services[1]['latency_ms'] = 400.0
        self.poller._annotate_services_with_latency_metrics(services)
        
        self.assertEqual(services[0]['average_latency_ms'], 75.0)  # (50+100)/2
        self.assertEqual(services[1]['average_latency_ms'], 450.0)  # (500+400)/2
    
    def test_preserves_existing_fields(self):
        """Test that existing service fields are preserved"""
        services = [
            {
                'id': 'svc1',
                'name': 'Service 1',
                'url': 'https://example.com',
                'status': 'UP',
                'latency_ms': 100.0,
                'http_status': 200,
                'last_checked': '2024-01-01T00:00:00'
            }
        ]
        
        result = self.poller._annotate_services_with_latency_metrics(services)
        
        # Original fields preserved
        self.assertEqual(result[0]['id'], 'svc1')
        self.assertEqual(result[0]['name'], 'Service 1')
        self.assertEqual(result[0]['url'], 'https://example.com')
        self.assertEqual(result[0]['status'], 'UP')
        self.assertEqual(result[0]['latency_ms'], 100.0)
        self.assertEqual(result[0]['http_status'], 200)
        self.assertEqual(result[0]['last_checked'], '2024-01-01T00:00:00')
        
        # New fields added
        self.assertIn('average_latency_ms', result[0])
        self.assertIn('latency_ratio', result[0])
        self.assertIn('latency_trend', result[0])


class TestAnnotateServicesDisabled(unittest.TestCase):
    """Test latency annotation when monitoring is disabled"""
    
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
    
    def test_no_fields_added_when_disabled(self):
        """Test that no latency fields are added when disabled"""
        services = [
            {'id': 'svc1', 'name': 'Service 1', 'status': 'UP', 'latency_ms': 100.0}
        ]
        
        result = self.poller._annotate_services_with_latency_metrics(services)
        
        self.assertNotIn('average_latency_ms', result[0])
        self.assertNotIn('latency_ratio', result[0])
        self.assertNotIn('latency_trend', result[0])
    
    def test_history_not_updated_when_disabled(self):
        """Test that latency history is not updated when disabled"""
        services = [
            {'id': 'svc1', 'name': 'Service 1', 'status': 'UP', 'latency_ms': 100.0}
        ]
        
        self.poller._annotate_services_with_latency_metrics(services)
        
        # History should still be empty
        self.assertEqual(self.poller._service_latency_history, {})
    
    def test_preserves_existing_fields_when_disabled(self):
        """Test that existing fields are preserved when disabled"""
        services = [
            {'id': 'svc1', 'name': 'Service 1', 'status': 'UP', 'latency_ms': 100.0}
        ]
        
        result = self.poller._annotate_services_with_latency_metrics(services)
        
        self.assertEqual(result[0]['id'], 'svc1')
        self.assertEqual(result[0]['latency_ms'], 100.0)


class TestAnnotateServicesNoLatency(unittest.TestCase):
    """Test handling of services without latency data"""
    
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
    
    def test_skips_service_with_none_latency(self):
        """Test that services with None latency are skipped"""
        services = [
            {'id': 'svc1', 'name': 'Service 1', 'status': 'DOWN', 'latency_ms': None}
        ]
        
        result = self.poller._annotate_services_with_latency_metrics(services)
        
        self.assertNotIn('average_latency_ms', result[0])
        self.assertNotIn('latency_ratio', result[0])
        self.assertNotIn('latency_trend', result[0])
    
    def test_skips_service_with_missing_latency(self):
        """Test that services without latency_ms field are skipped"""
        services = [
            {'id': 'svc1', 'name': 'Service 1', 'status': 'DOWN', 'error': 'timeout'}
        ]
        
        result = self.poller._annotate_services_with_latency_metrics(services)
        
        self.assertNotIn('average_latency_ms', result[0])
    
    def test_skips_service_with_invalid_latency_type(self):
        """Test that services with non-numeric latency are skipped"""
        services = [
            {'id': 'svc1', 'name': 'Service 1', 'status': 'UP', 'latency_ms': 'invalid'}
        ]
        
        result = self.poller._annotate_services_with_latency_metrics(services)
        
        self.assertNotIn('average_latency_ms', result[0])
    
    def test_skips_service_without_id(self):
        """Test that services without id are skipped"""
        services = [
            {'name': 'Service 1', 'status': 'UP', 'latency_ms': 100.0}
        ]
        
        result = self.poller._annotate_services_with_latency_metrics(services)
        
        # Should not crash, but no annotation added
        self.assertNotIn('average_latency_ms', result[0])
    
    def test_handles_mixed_services(self):
        """Test handling of mix of valid and invalid services"""
        services = [
            {'id': 'valid', 'name': 'Valid', 'status': 'UP', 'latency_ms': 100.0},
            {'id': 'no-latency', 'name': 'No Latency', 'status': 'DOWN', 'latency_ms': None},
            {'id': 'another-valid', 'name': 'Another', 'status': 'UP', 'latency_ms': 200.0}
        ]
        
        result = self.poller._annotate_services_with_latency_metrics(services)
        
        # First and third should have annotation
        self.assertIn('average_latency_ms', result[0])
        self.assertIn('average_latency_ms', result[2])
        
        # Second should not have annotation
        self.assertNotIn('average_latency_ms', result[1])


class TestAnnotateServicesEmptyList(unittest.TestCase):
    """Test handling of empty services list"""
    
    def setUp(self):
        """Create a poller with latency monitoring enabled"""
        self.mock_client = MagicMock()
        self.poller = server.BackgroundPoller(
            self.mock_client,
            poll_interval_sec=60,
            service_latency_config={'enabled': True, 'window_size': 10, 'degradation_threshold_ratio': 1.5}
        )
    
    def test_empty_list_returns_empty_list(self):
        """Test that empty list is handled gracefully"""
        result = self.poller._annotate_services_with_latency_metrics([])
        
        self.assertEqual(result, [])
    
    def test_empty_list_does_not_crash(self):
        """Test that empty list does not cause exceptions"""
        # Should not raise any exceptions
        self.poller._annotate_services_with_latency_metrics([])


class TestLatencyValueRounding(unittest.TestCase):
    """Test that computed values are properly rounded"""
    
    def setUp(self):
        """Create a poller with latency monitoring enabled"""
        self.mock_client = MagicMock()
        self.poller = server.BackgroundPoller(
            self.mock_client,
            poll_interval_sec=60,
            service_latency_config={'enabled': True, 'window_size': 10, 'degradation_threshold_ratio': 1.5}
        )
    
    def test_average_rounded_to_2_decimal_places(self):
        """Test that average is rounded to 2 decimal places"""
        services = [
            {'id': 'svc1', 'name': 'Service 1', 'status': 'UP', 'latency_ms': 33.333}
        ]
        
        self.poller._annotate_services_with_latency_metrics(services)
        
        services[0]['latency_ms'] = 66.666
        self.poller._annotate_services_with_latency_metrics(services)
        
        # Average would be 49.9995, should round to 50.0
        self.assertEqual(services[0]['average_latency_ms'], 50.0)
    
    def test_ratio_rounded_to_2_decimal_places(self):
        """Test that ratio is rounded to 2 decimal places"""
        services = [
            {'id': 'svc1', 'name': 'Service 1', 'status': 'UP', 'latency_ms': 100.0}
        ]
        
        self.poller._annotate_services_with_latency_metrics(services)
        
        services[0]['latency_ms'] = 133.333
        self.poller._annotate_services_with_latency_metrics(services)
        
        # Ratio precision should be limited
        self.assertIsInstance(services[0]['latency_ratio'], float)
        # Check it's reasonably close (the exact value depends on rounding)
        self.assertAlmostEqual(services[0]['latency_ratio'], 1.14, places=1)


if __name__ == '__main__':
    unittest.main()

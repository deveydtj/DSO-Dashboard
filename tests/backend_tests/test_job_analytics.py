#!/usr/bin/env python3
"""
Tests for job performance analytics functionality

Tests cover:
- Job filtering (manual, skipped, missing duration)
- Percentile calculations (avg, p95, p99)
- MR pipeline identification
- Analytics computation
"""

import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta

# Import functions to test
from backend.gitlab_client import (
    is_merge_request_pipeline,
    filter_valid_jobs,
    calculate_percentiles,
    calculate_job_statistics,
    compute_job_analytics_for_project,
)


class TestMergeRequestPipelineIdentification(unittest.TestCase):
    """Test identification of merge request pipelines"""
    
    def test_merge_request_pipeline(self):
        """Test pipeline with merge_request_event source"""
        pipeline = {'source': 'merge_request_event'}
        self.assertTrue(is_merge_request_pipeline(pipeline))
    
    def test_push_pipeline(self):
        """Test regular push pipeline"""
        pipeline = {'source': 'push'}
        self.assertFalse(is_merge_request_pipeline(pipeline))
    
    def test_api_pipeline(self):
        """Test API-triggered pipeline"""
        pipeline = {'source': 'api'}
        self.assertFalse(is_merge_request_pipeline(pipeline))
    
    def test_missing_source(self):
        """Test pipeline without source field"""
        pipeline = {}
        self.assertFalse(is_merge_request_pipeline(pipeline))


class TestJobFiltering(unittest.TestCase):
    """Test filtering of jobs for analytics"""
    
    def test_filter_excludes_manual_jobs(self):
        """Manual jobs should be excluded"""
        jobs = [
            {'status': 'success', 'duration': 100.0},
            {'status': 'manual', 'duration': 50.0},
        ]
        result = filter_valid_jobs(jobs)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['status'], 'success')
    
    def test_filter_excludes_skipped_jobs(self):
        """Skipped jobs should be excluded"""
        jobs = [
            {'status': 'success', 'duration': 100.0},
            {'status': 'skipped', 'duration': 0},
        ]
        result = filter_valid_jobs(jobs)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['status'], 'success')
    
    def test_filter_excludes_jobs_without_duration(self):
        """Jobs without duration should be excluded"""
        jobs = [
            {'status': 'success', 'duration': 100.0},
            {'status': 'failed', 'duration': None},
            {'status': 'success', 'duration': 0},
        ]
        result = filter_valid_jobs(jobs)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['duration'], 100.0)
    
    def test_filter_includes_failed_jobs_with_duration(self):
        """Failed jobs with duration should be included"""
        jobs = [
            {'status': 'failed', 'duration': 45.2},
        ]
        result = filter_valid_jobs(jobs)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['status'], 'failed')
    
    def test_filter_empty_list(self):
        """Empty job list should return empty result"""
        result = filter_valid_jobs([])
        self.assertEqual(len(result), 0)


class TestPercentileCalculations(unittest.TestCase):
    """Test percentile calculation logic"""
    
    def test_percentiles_with_sufficient_data(self):
        """Test percentile calculation with sufficient data"""
        values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        result = calculate_percentiles(values, [50, 95, 99])
        
        # p50 should be around median (5.5)
        self.assertAlmostEqual(result[50], 5.5, places=1)
        # p95 should be near upper end
        self.assertGreater(result[95], 9.0)
        # p99 should be near maximum
        self.assertGreater(result[99], 9.5)
    
    def test_percentiles_with_two_values(self):
        """Test percentile calculation with minimum data"""
        values = [10, 20]
        result = calculate_percentiles(values, [50, 95])
        
        # p50 should be 15 (midpoint)
        self.assertEqual(result[50], 15.0)
        # p95 should be near 20
        self.assertGreater(result[95], 19.0)
    
    def test_percentiles_insufficient_data(self):
        """Test percentile calculation with insufficient data"""
        values = [10]
        result = calculate_percentiles(values, [50, 95, 99])
        
        # All percentiles should be None
        self.assertIsNone(result[50])
        self.assertIsNone(result[95])
        self.assertIsNone(result[99])
    
    def test_percentiles_empty_list(self):
        """Test percentile calculation with empty list"""
        result = calculate_percentiles([], [50, 95, 99])
        
        # All percentiles should be None
        self.assertIsNone(result[50])
        self.assertIsNone(result[95])
        self.assertIsNone(result[99])
    
    def test_percentiles_are_sorted_correctly(self):
        """Test percentile calculation with unsorted input"""
        values = [5, 1, 9, 3, 7]
        result = calculate_percentiles(values, [50])
        
        # p50 of [1,3,5,7,9] should be 5
        self.assertEqual(result[50], 5.0)


class TestJobStatistics(unittest.TestCase):
    """Test aggregate job statistics calculation"""
    
    def test_statistics_with_valid_jobs(self):
        """Test statistics calculation with valid jobs"""
        jobs = [
            {'status': 'success', 'duration': 100.0},
            {'status': 'success', 'duration': 200.0},
            {'status': 'failed', 'duration': 150.0},
        ]
        result = calculate_job_statistics(jobs)
        
        # Check average
        self.assertEqual(result['avg_duration'], 150.0)
        # Check job count
        self.assertEqual(result['job_count'], 3)
        # Check percentiles are not None
        self.assertIsNotNone(result['p95_duration'])
        self.assertIsNotNone(result['p99_duration'])
    
    def test_statistics_filters_invalid_jobs(self):
        """Test that statistics calculation filters invalid jobs"""
        jobs = [
            {'status': 'success', 'duration': 100.0},
            {'status': 'manual', 'duration': 999.0},  # Should be filtered
            {'status': 'skipped', 'duration': 999.0},  # Should be filtered
            {'status': 'failed', 'duration': None},  # Should be filtered
        ]
        result = calculate_job_statistics(jobs)
        
        # Only one valid job should be counted
        self.assertEqual(result['job_count'], 1)
        self.assertEqual(result['avg_duration'], 100.0)
        # Percentiles should be None (insufficient data)
        self.assertIsNone(result['p95_duration'])
        self.assertIsNone(result['p99_duration'])
    
    def test_statistics_with_no_valid_jobs(self):
        """Test statistics with no valid jobs"""
        jobs = [
            {'status': 'manual', 'duration': 100.0},
            {'status': 'skipped', 'duration': 200.0},
        ]
        result = calculate_job_statistics(jobs)
        
        self.assertEqual(result['job_count'], 0)
        self.assertIsNone(result['avg_duration'])
        self.assertIsNone(result['p95_duration'])
        self.assertIsNone(result['p99_duration'])
    
    def test_statistics_with_empty_list(self):
        """Test statistics with empty job list"""
        result = calculate_job_statistics([])
        
        self.assertEqual(result['job_count'], 0)
        self.assertIsNone(result['avg_duration'])
        self.assertIsNone(result['p95_duration'])
        self.assertIsNone(result['p99_duration'])


class TestComputeJobAnalytics(unittest.TestCase):
    """Test complete job analytics computation"""
    
    def test_compute_analytics_success(self):
        """Test successful analytics computation"""
        # Mock GitLab client
        mock_client = MagicMock()
        
        # Mock pipelines within 7-day window
        now = datetime.now(timezone.utc)
        mock_pipelines = [
            {
                'id': 1,
                'ref': 'main',
                'status': 'success',
                'created_at': (now - timedelta(days=1)).isoformat(),
                'source': 'push'
            },
            {
                'id': 2,
                'ref': 'feature-branch',
                'status': 'success',
                'created_at': (now - timedelta(days=2)).isoformat(),
                'source': 'merge_request_event'
            }
        ]
        mock_client.get_pipelines_with_time_filter.return_value = mock_pipelines
        
        # Mock jobs for each pipeline
        mock_jobs = [
            {'status': 'success', 'duration': 100.0},
            {'status': 'success', 'duration': 200.0},
        ]
        mock_client.get_pipeline_jobs.return_value = mock_jobs
        
        # Compute analytics
        result = compute_job_analytics_for_project(
            mock_client,
            project_id=123,
            project_name='test-project',
            default_branch='main',
            window_days=7,
            max_pipelines=100,
            max_job_calls=50
        )
        
        # Verify result structure
        self.assertIsNotNone(result)
        self.assertEqual(result['project_id'], 123)
        self.assertEqual(result['window_days'], 7)
        self.assertIsNotNone(result['computed_at'])
        self.assertEqual(result['staleness_seconds'], 0)
        self.assertIsNone(result['error'])
        
        # Verify data items
        self.assertEqual(len(result['data']), 2)
        
        # Check first pipeline (default branch)
        first_item = result['data'][0]
        self.assertEqual(first_item['pipeline_id'], 1)
        self.assertEqual(first_item['pipeline_ref'], 'main')
        self.assertTrue(first_item['is_default_branch'])
        self.assertFalse(first_item['is_merge_request'])
        self.assertIsNotNone(first_item['avg_duration'])
        
        # Check second pipeline (MR)
        second_item = result['data'][1]
        self.assertEqual(second_item['pipeline_id'], 2)
        self.assertFalse(second_item['is_default_branch'])
        self.assertTrue(second_item['is_merge_request'])
    
    def test_compute_analytics_api_error(self):
        """Test analytics computation with API error"""
        mock_client = MagicMock()
        mock_client.get_pipelines_with_time_filter.return_value = None  # API error
        
        result = compute_job_analytics_for_project(
            mock_client,
            project_id=123,
            project_name='test-project',
            default_branch='main'
        )
        
        # Should return error structure
        self.assertIsNotNone(result)
        self.assertEqual(result['project_id'], 123)
        self.assertEqual(len(result['data']), 0)
        self.assertIsNotNone(result['error'])
        self.assertIn('Failed to fetch pipelines', result['error'])
    
    def test_compute_analytics_respects_caps(self):
        """Test that analytics computation respects API call caps"""
        mock_client = MagicMock()
        
        # Mock many pipelines (more than max_job_calls)
        mock_pipelines = [
            {
                'id': i,
                'ref': 'main',
                'status': 'success',
                'created_at': datetime.now(timezone.utc).isoformat(),
                'source': 'push'
            }
            for i in range(100)
        ]
        mock_client.get_pipelines_with_time_filter.return_value = mock_pipelines
        mock_client.get_pipeline_jobs.return_value = [
            {'status': 'success', 'duration': 100.0}
        ]
        
        # Compute with low max_job_calls cap
        result = compute_job_analytics_for_project(
            mock_client,
            project_id=123,
            project_name='test-project',
            default_branch='main',
            max_job_calls=5  # Very low cap
        )
        
        # Should only process up to max_job_calls pipelines
        self.assertLessEqual(len(result['data']), 5)
        
        # Verify get_pipeline_jobs was not called more than max_job_calls times
        self.assertLessEqual(mock_client.get_pipeline_jobs.call_count, 5)


if __name__ == '__main__':
    unittest.main()

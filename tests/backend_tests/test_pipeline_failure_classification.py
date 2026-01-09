#!/usr/bin/env python3
"""
Tests for pipeline failure classification system

Tests the classify_pipeline_failure() function to ensure correct categorization
of pipeline failures into failure domains (infra/code/unknown/unclassified).
"""

import unittest
import sys
import os

# Add parent directory to path to import from backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend.gitlab_client import classify_pipeline_failure, is_merge_request_pipeline


class TestClassifyPipelineFailureMergeRequestInfra(unittest.TestCase):
    """Test MR pipeline classification with infrastructure failures"""
    
    def test_mr_pipeline_pod_timeout_yields_infra(self):
        """Test MR pipeline with pod_timeout yields failure_domain == 'infra'"""
        pipeline = {
            'id': 123,
            'status': 'failed',
            'source': 'merge_request_event'
        }
        jobs = [
            {'status': 'failed', 'failure_reason': 'waiting for pod running: timed out waiting for pod to start', 'id': 1, 'created_at': '2024-01-01T00:00:00Z'}
        ]
        
        result = classify_pipeline_failure(pipeline, jobs)
        
        self.assertEqual(result['failure_domain'], 'infra')
        self.assertEqual(result['failure_category'], 'pod_timeout')
        self.assertTrue(result['classification_attempted'])
    
    def test_mr_pipeline_oom_yields_infra(self):
        """Test MR pipeline with OOM yields failure_domain == 'infra'"""
        pipeline = {
            'id': 124,
            'status': 'failed',
            'source': 'merge_request_event'
        }
        jobs = [
            {'status': 'failed', 'failure_reason': 'fatal: out of memory', 'id': 2, 'created_at': '2024-01-01T00:00:00Z'}
        ]
        
        result = classify_pipeline_failure(pipeline, jobs)
        
        self.assertEqual(result['failure_domain'], 'infra')
        self.assertEqual(result['failure_category'], 'oom')
        self.assertTrue(result['classification_attempted'])
    
    def test_mr_pipeline_timeout_yields_infra(self):
        """Test MR pipeline with generic timeout yields failure_domain == 'infra'"""
        pipeline = {
            'id': 125,
            'status': 'failed',
            'source': 'merge_request_event'
        }
        jobs = [
            {'status': 'failed', 'failure_reason': 'Job execution timeout', 'id': 3, 'created_at': '2024-01-01T00:00:00Z'}
        ]
        
        result = classify_pipeline_failure(pipeline, jobs)
        
        self.assertEqual(result['failure_domain'], 'infra')
        self.assertEqual(result['failure_category'], 'timeout')
        self.assertTrue(result['classification_attempted'])
    
    def test_mr_pipeline_runner_system_yields_infra(self):
        """Test MR pipeline with runner_system failure yields failure_domain == 'infra'"""
        pipeline = {
            'id': 126,
            'status': 'failed',
            'source': 'merge_request_event'
        }
        jobs = [
            {'status': 'failed', 'failure_reason': 'runner_system_failure', 'id': 4, 'created_at': '2024-01-01T00:00:00Z'}
        ]
        
        result = classify_pipeline_failure(pipeline, jobs)
        
        self.assertEqual(result['failure_domain'], 'infra')
        self.assertEqual(result['failure_category'], 'runner_system')
        self.assertTrue(result['classification_attempted'])


class TestClassifyPipelineFailureScriptFailureCode(unittest.TestCase):
    """Test script failure classification yields code domain"""
    
    def test_script_failure_yields_code(self):
        """Test job script_failure yields failure_domain == 'code'"""
        pipeline = {
            'id': 127,
            'status': 'failed',
            'source': 'push'
        }
        jobs = [
            {'status': 'failed', 'failure_reason': 'script_failure', 'id': 5, 'created_at': '2024-01-01T00:00:00Z'}
        ]
        
        result = classify_pipeline_failure(pipeline, jobs)
        
        self.assertEqual(result['failure_domain'], 'code')
        self.assertEqual(result['failure_category'], 'script_failure')
        self.assertTrue(result['classification_attempted'])
    
    def test_script_failure_with_space_yields_code(self):
        """Test 'script failure' with space yields code domain"""
        pipeline = {
            'id': 128,
            'status': 'failed',
            'source': 'push'
        }
        jobs = [
            {'status': 'failed', 'failure_reason': 'Job failed (script failure): exit code 1', 'id': 6, 'created_at': '2024-01-01T00:00:00Z'}
        ]
        
        result = classify_pipeline_failure(pipeline, jobs)
        
        self.assertEqual(result['failure_domain'], 'code')
        self.assertEqual(result['failure_category'], 'script_failure')
        self.assertTrue(result['classification_attempted'])


class TestClassifyPipelineFailureJobFetchError(unittest.TestCase):
    """Test classification when job fetch fails"""
    
    def test_job_fetch_failure_yields_unclassified(self):
        """Test job fetch failure results in failure_domain == 'unclassified' and classification_attempted == false"""
        pipeline = {
            'id': 129,
            'status': 'failed',
            'source': 'push'
        }
        
        # None indicates API error (job fetch failure)
        result = classify_pipeline_failure(pipeline, None)
        
        self.assertEqual(result['failure_domain'], 'unclassified')
        self.assertIsNone(result['failure_category'])
        self.assertFalse(result['classification_attempted'])


class TestClassifyPipelineFailureUnknown(unittest.TestCase):
    """Test unknown classification"""
    
    def test_unknown_failure_reason_yields_unknown(self):
        """Test unrecognized failure_reason yields failure_domain == 'unknown'"""
        pipeline = {
            'id': 130,
            'status': 'failed',
            'source': 'push'
        }
        jobs = [
            {'status': 'failed', 'failure_reason': 'Something completely unexpected', 'id': 7, 'created_at': '2024-01-01T00:00:00Z'}
        ]
        
        result = classify_pipeline_failure(pipeline, jobs)
        
        self.assertEqual(result['failure_domain'], 'unknown')
        self.assertEqual(result['failure_category'], 'unknown')
        self.assertTrue(result['classification_attempted'])
    
    def test_no_failure_reason_yields_unknown(self):
        """Test missing failure_reason yields unknown domain"""
        pipeline = {
            'id': 131,
            'status': 'failed',
            'source': 'push'
        }
        jobs = [
            {'status': 'failed', 'id': 8, 'created_at': '2024-01-01T00:00:00Z'}
        ]
        
        result = classify_pipeline_failure(pipeline, jobs)
        
        self.assertEqual(result['failure_domain'], 'unknown')
        self.assertEqual(result['failure_category'], 'unknown')
        self.assertTrue(result['classification_attempted'])
    
    def test_empty_jobs_list_yields_unknown(self):
        """Test empty jobs list (no failed jobs) yields unknown domain"""
        pipeline = {
            'id': 132,
            'status': 'failed',
            'source': 'push'
        }
        
        result = classify_pipeline_failure(pipeline, [])
        
        self.assertEqual(result['failure_domain'], 'unknown')
        self.assertEqual(result['failure_category'], 'unknown')
        self.assertTrue(result['classification_attempted'])


class TestClassifyPipelineFailureChronologicalOrdering(unittest.TestCase):
    """Test that earliest failed job is classified (root cause)"""
    
    def test_earliest_failed_job_classified(self):
        """Test that the earliest failed job is classified as root cause"""
        pipeline = {
            'id': 133,
            'status': 'failed',
            'source': 'push'
        }
        # Jobs in reverse chronological order (newest first)
        # The earliest job has pod_timeout
        jobs = [
            {'status': 'failed', 'failure_reason': 'script_failure', 'id': 3, 'created_at': '2024-01-01T03:00:00Z'},
            {'status': 'failed', 'failure_reason': 'runner_system_failure', 'id': 2, 'created_at': '2024-01-01T02:00:00Z'},
            {'status': 'failed', 'failure_reason': 'waiting for pod: timed out', 'id': 1, 'created_at': '2024-01-01T01:00:00Z'},
        ]
        
        result = classify_pipeline_failure(pipeline, jobs)
        
        # Should classify the earliest failed job (pod_timeout)
        self.assertEqual(result['failure_domain'], 'infra')
        self.assertEqual(result['failure_category'], 'pod_timeout')
    
    def test_only_first_failure_matters(self):
        """Test that only the first chronological failure is considered"""
        pipeline = {
            'id': 134,
            'status': 'failed',
            'source': 'push'
        }
        # Mix of success and failures - first failure is script_failure
        jobs = [
            {'status': 'success', 'id': 4, 'created_at': '2024-01-01T04:00:00Z'},
            {'status': 'failed', 'failure_reason': 'out of memory', 'id': 3, 'created_at': '2024-01-01T03:00:00Z'},
            {'status': 'failed', 'failure_reason': 'script_failure', 'id': 2, 'created_at': '2024-01-01T02:00:00Z'},
            {'status': 'success', 'id': 1, 'created_at': '2024-01-01T01:00:00Z'},
        ]
        
        result = classify_pipeline_failure(pipeline, jobs)
        
        # Should classify the first chronological failure (script_failure)
        self.assertEqual(result['failure_domain'], 'code')
        self.assertEqual(result['failure_category'], 'script_failure')


class TestClassifyPipelineFailureResponseStructure(unittest.TestCase):
    """Test that response structure is always consistent"""
    
    def test_response_has_all_required_keys(self):
        """Test response always has failure_domain, failure_category, classification_attempted"""
        pipeline = {'id': 135, 'status': 'failed', 'source': 'push'}
        jobs = [{'status': 'failed', 'failure_reason': 'test', 'id': 1, 'created_at': '2024-01-01T00:00:00Z'}]
        
        result = classify_pipeline_failure(pipeline, jobs)
        
        self.assertIn('failure_domain', result)
        self.assertIn('failure_category', result)
        self.assertIn('classification_attempted', result)
        self.assertEqual(len(result), 3)  # Exactly 3 keys
    
    def test_failure_domain_is_always_string_or_none(self):
        """Test failure_domain is always a string"""
        test_cases = [
            ({'status': 'failed'}, [{'status': 'failed', 'failure_reason': 'pod timeout', 'id': 1, 'created_at': '2024-01-01T00:00:00Z'}]),
            ({'status': 'failed'}, None),
            ({'status': 'failed'}, []),
        ]
        
        for pipeline, jobs in test_cases:
            result = classify_pipeline_failure(pipeline, jobs)
            self.assertIsInstance(result['failure_domain'], str)
            self.assertGreater(len(result['failure_domain']), 0)
    
    def test_classification_attempted_is_always_bool(self):
        """Test classification_attempted is always a boolean"""
        test_cases = [
            ({'status': 'failed'}, [{'status': 'failed', 'failure_reason': 'test', 'id': 1, 'created_at': '2024-01-01T00:00:00Z'}]),
            ({'status': 'failed'}, None),
            ({'status': 'failed'}, []),
        ]
        
        for pipeline, jobs in test_cases:
            result = classify_pipeline_failure(pipeline, jobs)
            self.assertIsInstance(result['classification_attempted'], bool)


class TestIsMergeRequestPipeline(unittest.TestCase):
    """Test is_merge_request_pipeline helper function"""
    
    def test_merge_request_event_source(self):
        """Test pipeline with source == 'merge_request_event' is detected"""
        pipeline = {'source': 'merge_request_event'}
        self.assertTrue(is_merge_request_pipeline(pipeline))
    
    def test_push_source_not_mr(self):
        """Test pipeline with source == 'push' is not MR"""
        pipeline = {'source': 'push'}
        self.assertFalse(is_merge_request_pipeline(pipeline))
    
    def test_missing_source_not_mr(self):
        """Test pipeline without source field is not MR"""
        pipeline = {}
        self.assertFalse(is_merge_request_pipeline(pipeline))
    
    def test_empty_source_not_mr(self):
        """Test pipeline with empty source is not MR"""
        pipeline = {'source': ''}
        self.assertFalse(is_merge_request_pipeline(pipeline))
    
    def test_case_sensitive(self):
        """Test source matching is case-sensitive"""
        pipeline = {'source': 'MERGE_REQUEST_EVENT'}
        self.assertFalse(is_merge_request_pipeline(pipeline))


class TestClassifyPipelineFailureAllDomains(unittest.TestCase):
    """Test all possible failure domains"""
    
    def test_all_infra_categories_map_to_infra_domain(self):
        """Test that all infrastructure categories map to infra domain"""
        infra_categories = ['pod_timeout', 'oom', 'timeout', 'runner_system']
        
        for category in infra_categories:
            pipeline = {'id': 200, 'status': 'failed'}
            # Create job with corresponding failure_reason
            if category == 'pod_timeout':
                failure_reason = 'waiting for pod: timed out'
            elif category == 'oom':
                failure_reason = 'out of memory'
            elif category == 'timeout':
                failure_reason = 'execution timeout'
            elif category == 'runner_system':
                failure_reason = 'runner_system_failure'
            
            jobs = [{'status': 'failed', 'failure_reason': failure_reason, 'id': 1, 'created_at': '2024-01-01T00:00:00Z'}]
            
            result = classify_pipeline_failure(pipeline, jobs)
            
            self.assertEqual(result['failure_domain'], 'infra', 
                           f"Category {category} should map to infra domain")
            self.assertEqual(result['failure_category'], category)
    
    def test_code_domain(self):
        """Test code domain classification"""
        pipeline = {'id': 201, 'status': 'failed'}
        jobs = [{'status': 'failed', 'failure_reason': 'script_failure', 'id': 1, 'created_at': '2024-01-01T00:00:00Z'}]
        
        result = classify_pipeline_failure(pipeline, jobs)
        
        self.assertEqual(result['failure_domain'], 'code')
        self.assertEqual(result['failure_category'], 'script_failure')
    
    def test_unknown_domain(self):
        """Test unknown domain classification"""
        pipeline = {'id': 202, 'status': 'failed'}
        jobs = [{'status': 'failed', 'failure_reason': 'something weird', 'id': 1, 'created_at': '2024-01-01T00:00:00Z'}]
        
        result = classify_pipeline_failure(pipeline, jobs)
        
        self.assertEqual(result['failure_domain'], 'unknown')
        self.assertEqual(result['failure_category'], 'unknown')
    
    def test_unclassified_domain(self):
        """Test unclassified domain classification"""
        pipeline = {'id': 203, 'status': 'failed'}
        
        result = classify_pipeline_failure(pipeline, None)
        
        self.assertEqual(result['failure_domain'], 'unclassified')
        self.assertIsNone(result['failure_category'])
        self.assertFalse(result['classification_attempted'])


if __name__ == '__main__':
    unittest.main()

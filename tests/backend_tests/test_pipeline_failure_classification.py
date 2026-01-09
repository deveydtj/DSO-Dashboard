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
    
    def test_jobs_with_missing_created_at(self):
        """Test that jobs with missing or None created_at are handled gracefully"""
        pipeline = {
            'id': 135,
            'status': 'failed',
            'source': 'push'
        }
        # Jobs with missing/None created_at get empty string, which sorts BEFORE ISO timestamps
        # So jobs WITHOUT timestamps come first, then sorted by ID
        jobs = [
            {'status': 'failed', 'failure_reason': 'out of memory', 'id': 3},  # Missing created_at, ID 3
            {'status': 'failed', 'failure_reason': 'waiting for pod: timed out', 'id': 1, 'created_at': None},  # None created_at, ID 1 (will be first)
            {'status': 'failed', 'failure_reason': 'script_failure', 'id': 2, 'created_at': '2024-01-01T03:00:00Z'},  # Has timestamp
        ]
        
        result = classify_pipeline_failure(pipeline, jobs)
        
        # Should classify the job with smallest ID among those without timestamp (pod_timeout with ID 1)
        # Empty strings sort before ISO timestamps
        self.assertEqual(result['failure_domain'], 'infra')
        self.assertEqual(result['failure_category'], 'pod_timeout')
    
    def test_jobs_all_missing_created_at(self):
        """Test that jobs without any created_at timestamps are sorted by ID"""
        pipeline = {
            'id': 136,
            'status': 'failed',
            'source': 'push'
        }
        # All jobs missing created_at - should sort by ID (lowest first)
        jobs = [
            {'status': 'failed', 'failure_reason': 'script_failure', 'id': 3},
            {'status': 'failed', 'failure_reason': 'out of memory', 'id': 2},
            {'status': 'failed', 'failure_reason': 'waiting for pod: timed out', 'id': 1},
        ]
        
        result = classify_pipeline_failure(pipeline, jobs)
        
        # Should classify the job with lowest ID (pod_timeout with id=1)
        self.assertEqual(result['failure_domain'], 'infra')
        self.assertEqual(result['failure_category'], 'pod_timeout')


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


class TestClassifyFailingPipelinesIntegration(unittest.TestCase):
    """Integration tests for _classify_failing_pipelines method"""
    
    def test_budget_enforcement(self):
        """Test that budget cap limits API calls"""
        from unittest.mock import MagicMock
        import sys
        
        # Import BackgroundPoller
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
        from backend.app import BackgroundPoller
        from backend.gitlab_client import PIPELINE_FAILURE_CLASSIFICATION_MAX_JOB_CALLS_PER_POLL
        
        # Create mock GitLab client
        mock_client = MagicMock()
        mock_client.get_pipeline_jobs.return_value = [
            {'status': 'failed', 'failure_reason': 'script_failure', 'id': 1, 'created_at': '2024-01-01T00:00:00Z'}
        ]
        
        # Create poller with mock client
        poller = BackgroundPoller(mock_client, 60)
        
        # Create more failing pipelines than budget allows
        num_pipelines = PIPELINE_FAILURE_CLASSIFICATION_MAX_JOB_CALLS_PER_POLL + 10
        pipelines = []
        for i in range(num_pipelines):
            pipelines.append({
                'id': i,
                'project_id': 100 + i,
                'status': 'failed',
                'ref': 'main',
                'source': 'push'
            })
        
        projects = [{'id': 100 + i, 'default_branch': 'main'} for i in range(num_pipelines)]
        
        # Classify pipelines
        poller._classify_failing_pipelines(pipelines, projects, poll_id='test')
        
        # Should only call get_pipeline_jobs up to budget
        self.assertEqual(mock_client.get_pipeline_jobs.call_count, PIPELINE_FAILURE_CLASSIFICATION_MAX_JOB_CALLS_PER_POLL)
        
        # All pipelines should have is_merge_request field
        for pipeline in pipelines:
            self.assertIn('is_merge_request', pipeline)
        
        # Pipelines are sorted by priority, then by descending ID (newer first)
        # Since all are priority 1 (default branch), highest IDs are classified first
        # So pipelines with IDs from (num_pipelines-1) down to (num_pipelines-BUDGET) should be classified
        budget = PIPELINE_FAILURE_CLASSIFICATION_MAX_JOB_CALLS_PER_POLL
        first_unclassified_id = num_pipelines - budget
        
        # Pipelines with high IDs (>= num_pipelines - budget) should be classified
        for i in range(first_unclassified_id, num_pipelines):
            self.assertIsNotNone(pipelines[i].get('failure_domain'))
            self.assertEqual(pipelines[i]['failure_domain'], 'code')
            self.assertIsNotNone(pipelines[i].get('failure_category'))
            self.assertIsNotNone(pipelines[i].get('classification_attempted'))
        
        # Pipelines with low IDs (< num_pipelines - budget) should not be classified
        for i in range(0, first_unclassified_id):
            self.assertNotIn('failure_domain', pipelines[i])
    
    def test_prioritization_default_branch_first(self):
        """Test that default branch pipelines are prioritized over MR and other refs"""
        from unittest.mock import MagicMock, patch
        import sys
        
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
        from backend.app import BackgroundPoller
        
        mock_client = MagicMock()
        mock_client.get_pipeline_jobs.return_value = [
            {'status': 'failed', 'failure_reason': 'script_failure', 'id': 1, 'created_at': '2024-01-01T00:00:00Z'}
        ]
        
        # Create poller with budget limited to 1
        poller = BackgroundPoller(
            mock_client, 
            60,
            pipeline_failure_classification_config={'enabled': True, 'max_job_calls_per_poll': 1}
        )
        
        # Create pipelines with different ref types
        pipelines = [
            {'id': 1, 'project_id': 101, 'status': 'failed', 'ref': 'feature/test', 'source': 'push'},  # Other ref (priority 3)
            {'id': 2, 'project_id': 102, 'status': 'failed', 'ref': 'main', 'source': 'push'},  # Default branch (priority 1)
            {'id': 3, 'project_id': 103, 'status': 'failed', 'ref': 'mr-branch', 'source': 'merge_request_event'},  # MR (priority 2)
        ]
        
        projects = [
            {'id': 101, 'default_branch': 'main'},
            {'id': 102, 'default_branch': 'main'},
            {'id': 103, 'default_branch': 'main'}
        ]
        
        poller._classify_failing_pipelines(pipelines, projects, poll_id='test')
        
        # Only one pipeline should be classified
        self.assertEqual(mock_client.get_pipeline_jobs.call_count, 1)
        
        # Default branch pipeline (id=2, index 1) should be classified first
        self.assertIsNotNone(pipelines[1].get('failure_domain'))
        self.assertEqual(pipelines[1]['failure_domain'], 'code')
        
        # Other pipelines should not be classified (no failure_domain set)
        self.assertIsNone(pipelines[0].get('failure_domain'))
        self.assertIsNone(pipelines[2].get('failure_domain'))
    
    def test_non_failing_pipelines_get_null_fields(self):
        """Test that non-failing pipelines get None for classification fields"""
        from unittest.mock import MagicMock
        import sys
        
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
        from backend.app import BackgroundPoller
        
        mock_client = MagicMock()
        poller = BackgroundPoller(mock_client, 60)
        
        # Create mix of failing and non-failing pipelines
        pipelines = [
            {'id': 1, 'project_id': 101, 'status': 'success', 'ref': 'main', 'source': 'push'},
            {'id': 2, 'project_id': 102, 'status': 'running', 'ref': 'main', 'source': 'push'},
            {'id': 3, 'project_id': 103, 'status': 'pending', 'ref': 'main', 'source': 'push'},
        ]
        
        projects = [{'id': 101, 'default_branch': 'main'}]
        
        poller._classify_failing_pipelines(pipelines, projects, poll_id='test')
        
        # Non-failing pipelines should have null classification fields
        for pipeline in pipelines:
            self.assertIsNone(pipeline.get('failure_domain'))
            self.assertIsNone(pipeline.get('failure_category'))
            self.assertIsNone(pipeline.get('classification_attempted'))
            # But is_merge_request should be set for all
            self.assertFalse(pipeline.get('is_merge_request'))
        
        # No API calls should be made for non-failing pipelines
        mock_client.get_pipeline_jobs.assert_not_called()
    
    def test_exception_handling_sets_unclassified(self):
        """Test that exceptions during job fetching set unclassified fields"""
        from unittest.mock import MagicMock
        import sys
        
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
        from backend.app import BackgroundPoller
        
        mock_client = MagicMock()
        # Simulate API error
        mock_client.get_pipeline_jobs.side_effect = Exception("API Error")
        
        poller = BackgroundPoller(mock_client, 60)
        
        pipelines = [
            {'id': 1, 'project_id': 101, 'status': 'failed', 'ref': 'main', 'source': 'push'}
        ]
        
        projects = [{'id': 101, 'default_branch': 'main'}]
        
        poller._classify_failing_pipelines(pipelines, projects, poll_id='test')
        
        # Pipeline should have unclassified fields
        self.assertEqual(pipelines[0]['failure_domain'], 'unclassified')
        self.assertIsNone(pipelines[0]['failure_category'])
        self.assertFalse(pipelines[0]['classification_attempted'])
    
    def test_is_merge_request_added_to_all_pipelines(self):
        """Test that is_merge_request field is added to all pipelines regardless of status"""
        from unittest.mock import MagicMock
        import sys
        
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
        from backend.app import BackgroundPoller
        
        mock_client = MagicMock()
        poller = BackgroundPoller(mock_client, 60)
        
        pipelines = [
            {'id': 1, 'project_id': 101, 'status': 'success', 'ref': 'main', 'source': 'push'},
            {'id': 2, 'project_id': 102, 'status': 'failed', 'ref': 'mr-branch', 'source': 'merge_request_event'},
            {'id': 3, 'project_id': 103, 'status': 'running', 'ref': 'feature', 'source': 'push'},
        ]
        
        projects = [{'id': 101, 'default_branch': 'main'}]
        
        poller._classify_failing_pipelines(pipelines, projects, poll_id='test')
        
        # All pipelines should have is_merge_request field
        self.assertFalse(pipelines[0]['is_merge_request'])  # Push to main
        self.assertTrue(pipelines[1]['is_merge_request'])   # MR pipeline
        self.assertFalse(pipelines[2]['is_merge_request'])  # Push to feature


if __name__ == '__main__':
    unittest.main()

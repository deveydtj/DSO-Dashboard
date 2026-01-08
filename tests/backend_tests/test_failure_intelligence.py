#!/usr/bin/env python3
"""
Tests for failure intelligence classification system

Tests the classify_job_failure() function and enrich_projects_with_failure_intelligence()
to ensure correct categorization of job failures, including the critical pod-start timeout
pattern from the GitHub issue.
"""

import unittest
import sys
import os

# Add parent directory to path to import from backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend.gitlab_client import classify_job_failure


class TestClassifyJobFailurePodTimeout(unittest.TestCase):
    """Test classification of pod-start timeout failures (GitHub issue requirement)"""
    
    def test_pod_start_timeout_exact_pattern(self):
        """Test the exact pod-start timeout pattern from GitHub issue"""
        job = {
            'status': 'failed',
            'failure_reason': 'prepare environment: waiting for pod running: timed out waiting for pod to start'
        }
        
        result = classify_job_failure(job)
        
        self.assertEqual(result['category'], 'pod_timeout')
        self.assertEqual(result['label'], 'Pod start timeout')
        self.assertIsNotNone(result['snippet'])
        self.assertIn('waiting for pod', result['snippet'])
    
    def test_pod_start_timeout_with_system_failure_prefix(self):
        """Test pod timeout with system failure prefix (common pattern)"""
        job = {
            'status': 'failed',
            'failure_reason': 'Job failed (system failure): prepare environment: waiting for pod running: timed out waiting for pod to start'
        }
        
        result = classify_job_failure(job)
        
        self.assertEqual(result['category'], 'pod_timeout')
        self.assertEqual(result['label'], 'Pod start timeout')
    
    def test_pod_timeout_broader_pattern(self):
        """Test broader pod timeout pattern"""
        job = {
            'status': 'failed',
            'failure_reason': 'pod timeout: container failed to start'
        }
        
        result = classify_job_failure(job)
        
        self.assertEqual(result['category'], 'pod_timeout')
        self.assertEqual(result['label'], 'Pod timeout')
    
    def test_pod_timeout_case_insensitive(self):
        """Test pod timeout detection is case-insensitive"""
        job = {
            'status': 'failed',
            'failure_reason': 'WAITING FOR POD RUNNING: TIMED OUT'
        }
        
        result = classify_job_failure(job)
        
        self.assertEqual(result['category'], 'pod_timeout')


class TestClassifyJobFailureOOM(unittest.TestCase):
    """Test OOM (out of memory) classification"""
    
    def test_oom_explicit_pattern(self):
        """Test explicit 'out of memory' pattern"""
        job = {
            'status': 'failed',
            'failure_reason': 'fatal: Out of memory, malloc failed (tried to allocate 8192 bytes)'
        }
        
        result = classify_job_failure(job)
        
        self.assertEqual(result['category'], 'oom')
        self.assertEqual(result['label'], 'Out of memory')
    
    def test_oom_abbreviation(self):
        """Test OOM abbreviation"""
        job = {
            'status': 'failed',
            'failure_reason': 'Container killed due to OOM'
        }
        
        result = classify_job_failure(job)
        
        self.assertEqual(result['category'], 'oom')
        self.assertEqual(result['label'], 'Out of memory')
    
    def test_no_oom_false_positive_for_java(self):
        """Test that Java OutOfMemoryError (no space) is NOT classified as OOM
        
        This verifies we don't have false positives for application-level OOM
        that doesn't match our explicit pattern.
        """
        job = {
            'status': 'failed',
            'failure_reason': 'java.lang.OutOfMemoryError: Java heap space'
        }
        
        result = classify_job_failure(job)
        
        # Should fall through to unknown since 'OutOfMemoryError' doesn't contain 'out of memory' or 'oom'
        self.assertEqual(result['category'], 'unknown')


class TestClassifyJobFailureTimeout(unittest.TestCase):
    """Test generic timeout classification"""
    
    def test_generic_timeout(self):
        """Test generic timeout (not pod-specific)"""
        job = {
            'status': 'failed',
            'failure_reason': 'Job execution timeout'
        }
        
        result = classify_job_failure(job)
        
        self.assertEqual(result['category'], 'timeout')
        self.assertEqual(result['label'], 'Timeout')
    
    def test_timed_out_pattern(self):
        """Test 'timed out' pattern (not pod-specific)"""
        job = {
            'status': 'failed',
            'failure_reason': 'Operation timed out after 300 seconds'
        }
        
        result = classify_job_failure(job)
        
        self.assertEqual(result['category'], 'timeout')


class TestClassifyJobFailureRunnerSystem(unittest.TestCase):
    """Test runner/system failure classification"""
    
    def test_runner_system_failure(self):
        """Test runner_system_failure enum value"""
        job = {
            'status': 'failed',
            'failure_reason': 'runner_system_failure'
        }
        
        result = classify_job_failure(job)
        
        self.assertEqual(result['category'], 'runner_system')
        self.assertEqual(result['label'], 'Runner system failure')
    
    def test_system_failure_with_space(self):
        """Test 'system failure' with space (message format)"""
        job = {
            'status': 'failed',
            'failure_reason': 'Job failed (system failure): infrastructure error'
        }
        
        result = classify_job_failure(job)
        
        self.assertEqual(result['category'], 'runner_system')
    
    def test_stuck_or_timeout_failure(self):
        """Test stuck_or_timeout_failure"""
        job = {
            'status': 'failed',
            'failure_reason': 'stuck_or_timeout_failure'
        }
        
        result = classify_job_failure(job)
        
        self.assertEqual(result['category'], 'runner_system')
    
    def test_api_failure(self):
        """Test api_failure"""
        job = {
            'status': 'failed',
            'failure_reason': 'api_failure'
        }
        
        result = classify_job_failure(job)
        
        self.assertEqual(result['category'], 'runner_system')


class TestClassifyJobFailureScriptFailure(unittest.TestCase):
    """Test script failure classification"""
    
    def test_script_failure(self):
        """Test script_failure enum value"""
        job = {
            'status': 'failed',
            'failure_reason': 'script_failure'
        }
        
        result = classify_job_failure(job)
        
        self.assertEqual(result['category'], 'script_failure')
        self.assertEqual(result['label'], 'Script failure')
    
    def test_script_failure_with_space(self):
        """Test 'script failure' with space"""
        job = {
            'status': 'failed',
            'failure_reason': 'Job failed (script failure): exit code 1'
        }
        
        result = classify_job_failure(job)
        
        self.assertEqual(result['category'], 'script_failure')


class TestClassifyJobFailureUnknown(unittest.TestCase):
    """Test unknown/fallback classification"""
    
    def test_unknown_no_failure_reason(self):
        """Test fallback to unknown when no failure_reason"""
        job = {
            'status': 'failed'
        }
        
        result = classify_job_failure(job)
        
        self.assertEqual(result['category'], 'unknown')
        self.assertEqual(result['label'], 'Unknown')
        self.assertIsNone(result['snippet'])
    
    def test_unknown_empty_failure_reason(self):
        """Test fallback to unknown when failure_reason is empty"""
        job = {
            'status': 'failed',
            'failure_reason': ''
        }
        
        result = classify_job_failure(job)
        
        self.assertEqual(result['category'], 'unknown')
        self.assertIsNone(result['snippet'])
    
    def test_unknown_unrecognized_pattern(self):
        """Test fallback to unknown for unrecognized patterns"""
        job = {
            'status': 'failed',
            'failure_reason': 'Something completely unexpected happened'
        }
        
        result = classify_job_failure(job)
        
        self.assertEqual(result['category'], 'unknown')
        self.assertEqual(result['label'], 'Unknown')
        self.assertIsNotNone(result['snippet'])
        self.assertIn('unexpected', result['snippet'])


class TestClassifyJobFailureSnippet(unittest.TestCase):
    """Test snippet generation and truncation"""
    
    def test_snippet_bounded_to_100_chars(self):
        """Test snippet is truncated to 100 chars"""
        long_reason = 'a' * 150  # 150 characters
        job = {
            'status': 'failed',
            'failure_reason': long_reason
        }
        
        result = classify_job_failure(job)
        
        self.assertIsNotNone(result['snippet'])
        self.assertLessEqual(len(result['snippet']), 100)
        self.assertTrue(result['snippet'].endswith('...'))
    
    def test_snippet_not_truncated_when_short(self):
        """Test snippet is not truncated when under 100 chars"""
        short_reason = 'script_failure'
        job = {
            'status': 'failed',
            'failure_reason': short_reason
        }
        
        result = classify_job_failure(job)
        
        self.assertEqual(result['snippet'], short_reason)
        self.assertFalse(result['snippet'].endswith('...'))
    
    def test_snippet_exactly_100_chars(self):
        """Test snippet handling when exactly 100 chars"""
        exact_reason = 'a' * 100
        job = {
            'status': 'failed',
            'failure_reason': exact_reason
        }
        
        result = classify_job_failure(job)
        
        self.assertEqual(result['snippet'], exact_reason)
        self.assertEqual(len(result['snippet']), 100)


class TestClassifyJobFailurePatternPriority(unittest.TestCase):
    """Test that more specific patterns take precedence over generic ones"""
    
    def test_pod_timeout_takes_precedence_over_generic_timeout(self):
        """Test pod timeout is detected before generic timeout"""
        job = {
            'status': 'failed',
            'failure_reason': 'waiting for pod running: timeout occurred'
        }
        
        result = classify_job_failure(job)
        
        # Should match pod_timeout, not generic timeout
        self.assertEqual(result['category'], 'pod_timeout')
        self.assertNotEqual(result['category'], 'timeout')
    
    def test_runner_system_not_confused_with_oom(self):
        """Test runner system failure is not confused with OOM"""
        job = {
            'status': 'failed',
            'failure_reason': 'runner_system_failure'
        }
        
        result = classify_job_failure(job)
        
        self.assertEqual(result['category'], 'runner_system')
        self.assertNotEqual(result['category'], 'oom')


class TestClassifyJobFailureEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions"""
    
    def test_failure_reason_is_none(self):
        """Test when failure_reason is explicitly None"""
        job = {
            'status': 'failed',
            'failure_reason': None
        }
        
        result = classify_job_failure(job)
        
        self.assertEqual(result['category'], 'unknown')
        self.assertIsNone(result['snippet'])
    
    def test_empty_job_dict(self):
        """Test with empty job dict"""
        job = {}
        
        result = classify_job_failure(job)
        
        self.assertEqual(result['category'], 'unknown')
        self.assertIsNone(result['snippet'])
    
    def test_multiple_patterns_in_reason(self):
        """Test when multiple patterns present (should match first/most specific)"""
        job = {
            'status': 'failed',
            'failure_reason': 'waiting for pod running timed out - out of memory'
        }
        
        result = classify_job_failure(job)
        
        # Should match pod_timeout (more specific, checked first)
        self.assertEqual(result['category'], 'pod_timeout')


class TestClassifyJobFailureResponseStructure(unittest.TestCase):
    """Test that response structure is always consistent"""
    
    def test_response_has_all_keys(self):
        """Test response always has category, label, snippet keys"""
        job = {'status': 'failed', 'failure_reason': 'test'}
        
        result = classify_job_failure(job)
        
        self.assertIn('category', result)
        self.assertIn('label', result)
        self.assertIn('snippet', result)
        self.assertEqual(len(result), 3)  # Exactly 3 keys
    
    def test_category_is_always_string(self):
        """Test category is always a string"""
        test_cases = [
            {'failure_reason': 'pod timeout'},
            {'failure_reason': 'out of memory'},
            {'failure_reason': 'script_failure'},
            {'failure_reason': ''},
            {}
        ]
        
        for job in test_cases:
            job['status'] = 'failed'
            result = classify_job_failure(job)
            self.assertIsInstance(result['category'], str)
            self.assertGreater(len(result['category']), 0)
    
    def test_label_is_always_string(self):
        """Test label is always a string"""
        test_cases = [
            {'failure_reason': 'pod timeout'},
            {'failure_reason': ''},
            {}
        ]
        
        for job in test_cases:
            job['status'] = 'failed'
            result = classify_job_failure(job)
            self.assertIsInstance(result['label'], str)
            self.assertGreater(len(result['label']), 0)
    
    def test_snippet_is_string_or_none(self):
        """Test snippet is either string or None (never empty string)"""
        test_cases = [
            {'failure_reason': 'pod timeout'},
            {'failure_reason': ''},
            {}
        ]
        
        for job in test_cases:
            job['status'] = 'failed'
            result = classify_job_failure(job)
            self.assertTrue(
                result['snippet'] is None or 
                (isinstance(result['snippet'], str) and len(result['snippet']) > 0)
            )


if __name__ == '__main__':
    unittest.main()

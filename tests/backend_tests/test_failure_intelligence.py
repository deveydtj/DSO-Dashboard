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
        
        This verifies the specificity of our OOM pattern matching by ensuring
        that messages like Java OutOfMemoryError, which don't match our explicit
        'out of memory' or 'oom' patterns, are not treated as OOM failures.
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


class TestEnrichProjectsWithFailureIntelligence(unittest.TestCase):
    """Test enrich_projects_with_failure_intelligence() function"""
    
    def test_projects_without_issues_get_none_fields(self):
        """Test that projects without failing jobs or runner issues get None fields"""
        from backend.gitlab_client import enrich_projects_with_failure_intelligence
        from unittest.mock import MagicMock
        
        # Mock GitLab client (should not be called)
        mock_client = MagicMock()
        
        projects = [
            {
                'id': 1,
                'name': 'healthy-project',
                'default_branch': 'main',
                'has_failing_jobs': False,
                'has_runner_issues': False
            }
        ]
        
        per_project_pipelines = {
            1: [{'status': 'success', 'ref': 'main', 'id': 100}]
        }
        
        result = enrich_projects_with_failure_intelligence(
            mock_client, projects, per_project_pipelines
        )
        
        # Should not have called API
        mock_client.get_pipeline_jobs.assert_not_called()
        
        # Check result
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], 1)
        self.assertIsNone(result[0]['failure_category'])
        self.assertIsNone(result[0]['failure_label'])
        self.assertIsNone(result[0]['failure_snippet'])
    
    def test_budget_cap_is_enforced(self):
        """Test that budget cap limits API calls"""
        from backend.gitlab_client import enrich_projects_with_failure_intelligence, JOB_DETAIL_HYDRATION_BUDGET
        from unittest.mock import MagicMock
        
        # Create more candidates than budget allows
        num_projects = JOB_DETAIL_HYDRATION_BUDGET + 5
        
        mock_client = MagicMock()
        mock_client.get_pipeline_jobs.return_value = [
            {'status': 'failed', 'failure_reason': 'script_failure', 'id': 1, 'created_at': '2024-01-01T00:00:00Z'}
        ]
        
        projects = []
        per_project_pipelines = {}
        for i in range(num_projects):
            projects.append({
                'id': i,
                'name': f'project-{i}',
                'default_branch': 'main',
                'has_failing_jobs': True,
                'has_runner_issues': False
            })
            per_project_pipelines[i] = [
                {'status': 'failed', 'ref': 'main', 'id': 100 + i}
            ]
        
        result = enrich_projects_with_failure_intelligence(
            mock_client, projects, per_project_pipelines
        )
        
        # Should only call API up to budget cap
        self.assertEqual(mock_client.get_pipeline_jobs.call_count, JOB_DETAIL_HYDRATION_BUDGET)
        
        # All projects should have the fields (some None, some populated)
        self.assertEqual(len(result), num_projects)
        for project in result:
            self.assertIn('failure_category', project)
            self.assertIn('failure_label', project)
            self.assertIn('failure_snippet', project)
    
    def test_prioritization_runner_issues_first(self):
        """Test that projects with runner issues are prioritized"""
        from backend.gitlab_client import enrich_projects_with_failure_intelligence
        from unittest.mock import MagicMock
        
        mock_client = MagicMock()
        mock_client.get_pipeline_jobs.return_value = [
            {'status': 'failed', 'failure_reason': 'runner_system_failure', 'id': 1, 'created_at': '2024-01-01T00:00:00Z'}
        ]
        
        # Create 3 projects: 1 with runner issues, 2 with just failing jobs
        # Set budget to 1 to force prioritization
        projects = [
            {
                'id': 1,
                'name': 'just-failing',
                'default_branch': 'main',
                'has_failing_jobs': True,
                'has_runner_issues': False
            },
            {
                'id': 2,
                'name': 'has-runner-issues',
                'default_branch': 'main',
                'has_failing_jobs': True,
                'has_runner_issues': True
            },
            {
                'id': 3,
                'name': 'also-just-failing',
                'default_branch': 'main',
                'has_failing_jobs': True,
                'has_runner_issues': False
            }
        ]
        
        per_project_pipelines = {
            1: [{'status': 'failed', 'ref': 'main', 'id': 101}],
            2: [{'status': 'failed', 'ref': 'main', 'id': 102}],
            3: [{'status': 'failed', 'ref': 'main', 'id': 103}]
        }
        
        # Temporarily reduce budget to test prioritization
        gc = sys.modules["backend.gitlab_client"]
        original_budget = gc.JOB_DETAIL_HYDRATION_BUDGET
        gc.JOB_DETAIL_HYDRATION_BUDGET = 1
        
        try:
            result = enrich_projects_with_failure_intelligence(
                mock_client, projects, per_project_pipelines
            )
            
            # Should have called API once
            self.assertEqual(mock_client.get_pipeline_jobs.call_count, 1)
            
            # Project with runner issues should be hydrated
            project_2 = [p for p in result if p['id'] == 2][0]
            self.assertEqual(project_2['failure_category'], 'runner_system')
            
            # Others should have None
            project_1 = [p for p in result if p['id'] == 1][0]
            self.assertIsNone(project_1['failure_category'])
            
        finally:
            # Restore budget
            gc.JOB_DETAIL_HYDRATION_BUDGET = original_budget
    
    def test_api_errors_handled_gracefully(self):
        """Test that API errors don't crash the enrichment"""
        from backend.gitlab_client import enrich_projects_with_failure_intelligence
        from unittest.mock import MagicMock
        
        mock_client = MagicMock()
        mock_client.get_pipeline_jobs.return_value = None  # API error
        
        projects = [
            {
                'id': 1,
                'name': 'failing-project',
                'default_branch': 'main',
                'has_failing_jobs': True,
                'has_runner_issues': False
            }
        ]
        
        per_project_pipelines = {
            1: [{'status': 'failed', 'ref': 'main', 'id': 100}]
        }
        
        # Should not raise exception
        result = enrich_projects_with_failure_intelligence(
            mock_client, projects, per_project_pipelines
        )
        
        # Should have None fields
        self.assertEqual(len(result), 1)
        self.assertIsNone(result[0]['failure_category'])
        self.assertIsNone(result[0]['failure_label'])
        self.assertIsNone(result[0]['failure_snippet'])
    
    def test_chronological_job_sorting(self):
        """Test that earliest failed job is classified (root cause)"""
        from backend.gitlab_client import enrich_projects_with_failure_intelligence
        from unittest.mock import MagicMock
        
        mock_client = MagicMock()
        # Return jobs in reverse chronological order (newest first)
        # The earliest job has pod_timeout, later ones have different failures
        mock_client.get_pipeline_jobs.return_value = [
            {'status': 'failed', 'failure_reason': 'script_failure', 'id': 3, 'created_at': '2024-01-01T03:00:00Z'},
            {'status': 'failed', 'failure_reason': 'runner_system_failure', 'id': 2, 'created_at': '2024-01-01T02:00:00Z'},
            {'status': 'failed', 'failure_reason': 'waiting for pod running: timed out', 'id': 1, 'created_at': '2024-01-01T01:00:00Z'},
        ]
        
        projects = [
            {
                'id': 1,
                'name': 'failing-project',
                'default_branch': 'main',
                'has_failing_jobs': True,
                'has_runner_issues': False
            }
        ]
        
        per_project_pipelines = {
            1: [{'status': 'failed', 'ref': 'main', 'id': 100}]
        }
        
        result = enrich_projects_with_failure_intelligence(
            mock_client, projects, per_project_pipelines
        )
        
        # Should classify the earliest failed job (pod_timeout)
        self.assertEqual(result[0]['failure_category'], 'pod_timeout')
    
    def test_does_not_mutate_input_projects(self):
        """Test that input projects list is not mutated"""
        from backend.gitlab_client import enrich_projects_with_failure_intelligence
        from unittest.mock import MagicMock
        
        mock_client = MagicMock()
        mock_client.get_pipeline_jobs.return_value = [
            {'status': 'failed', 'failure_reason': 'script_failure', 'id': 1, 'created_at': '2024-01-01T00:00:00Z'}
        ]
        
        projects = [
            {
                'id': 1,
                'name': 'failing-project',
                'default_branch': 'main',
                'has_failing_jobs': True,
                'has_runner_issues': False
            }
        ]
        
        per_project_pipelines = {
            1: [{'status': 'failed', 'ref': 'main', 'id': 100}]
        }
        
        # Store original state
        original_project = projects[0].copy()
        
        result = enrich_projects_with_failure_intelligence(
            mock_client, projects, per_project_pipelines
        )
        
        # Input should not have new fields
        self.assertNotIn('failure_category', projects[0])
        self.assertNotIn('failure_label', projects[0])
        self.assertNotIn('failure_snippet', projects[0])
        
        # Result should have new fields
        self.assertIn('failure_category', result[0])
        self.assertIn('failure_label', result[0])
        self.assertIn('failure_snippet', result[0])
        
        # Input should be unchanged (except for object identity)
        for key in original_project:
            self.assertEqual(projects[0][key], original_project[key])
    
    def test_empty_projects_list(self):
        """Test that empty projects list returns empty list"""
        from backend.gitlab_client import enrich_projects_with_failure_intelligence
        from unittest.mock import MagicMock
        
        mock_client = MagicMock()
        
        result = enrich_projects_with_failure_intelligence(
            mock_client, [], {}
        )
        
        self.assertEqual(result, [])
        mock_client.get_pipeline_jobs.assert_not_called()
    
    def test_only_default_branch_pipelines_analyzed(self):
        """Test that only default-branch pipelines trigger job fetching"""
        from backend.gitlab_client import enrich_projects_with_failure_intelligence
        from unittest.mock import MagicMock
        
        mock_client = MagicMock()
        
        projects = [
            {
                'id': 1,
                'name': 'project',
                'default_branch': 'main',
                'has_failing_jobs': True,
                'has_runner_issues': False
            }
        ]
        
        # Only feature branch pipeline is failing
        per_project_pipelines = {
            1: [
                {'status': 'failed', 'ref': 'feature/test', 'id': 101},
                {'status': 'success', 'ref': 'main', 'id': 100}
            ]
        }
        
        result = enrich_projects_with_failure_intelligence(
            mock_client, projects, per_project_pipelines
        )
        
        # Should not call API (no failed default-branch pipeline)
        mock_client.get_pipeline_jobs.assert_not_called()
        
        # Should have None fields
        self.assertIsNone(result[0]['failure_category'])


if __name__ == '__main__':
    unittest.main()

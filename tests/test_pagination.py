#!/usr/bin/env python3
"""
Tests for GitLab API pagination functionality
"""

import unittest
import sys
import os
from unittest.mock import MagicMock, patch, call

# Add parent directory to path to import server module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import server


class TestPaginationHelpers(unittest.TestCase):
    """Test pagination helper functions"""
    
    def setUp(self):
        """Create a client instance for testing"""
        self.client = server.GitLabAPIClient(
            'https://gitlab.example.com',
            'test-token',
            per_page=10
        )
    
    def test_parse_link_header_with_next(self):
        """Test parsing Link header with rel="next" """
        link_header = '<https://gitlab.com/api/v4/projects?page=2&per_page=10>; rel="next", <https://gitlab.com/api/v4/projects?page=10&per_page=10>; rel="last"'
        result = self.client._parse_link_header(link_header)
        self.assertEqual(result, '2')
    
    def test_parse_link_header_no_next(self):
        """Test parsing Link header without rel="next" (last page)"""
        link_header = '<https://gitlab.com/api/v4/projects?page=1&per_page=10>; rel="first", <https://gitlab.com/api/v4/projects?page=1&per_page=10>; rel="last"'
        result = self.client._parse_link_header(link_header)
        self.assertIsNone(result)
    
    def test_parse_link_header_empty(self):
        """Test parsing empty Link header"""
        result = self.client._parse_link_header(None)
        self.assertIsNone(result)
        result = self.client._parse_link_header('')
        self.assertIsNone(result)
    
    def test_parse_link_header_single_quotes(self):
        """Test parsing Link header with single quotes"""
        link_header = "<https://gitlab.com/api/v4/projects?page=3&per_page=10>; rel='next'"
        result = self.client._parse_link_header(link_header)
        self.assertEqual(result, '3')
    
    def test_gitlab_get_all_pages_alias(self):
        """Test that gitlab_get_all_pages is a working alias"""
        with patch.object(self.client, '_make_request') as mock_request:
            mock_request.return_value = {
                'data': [{'id': 1}],
                'next_page': None,
                'total_pages': '1',
                'total': '1'
            }
            
            result = self.client.gitlab_get_all_pages('projects', {'membership': 'true'})
            
            self.assertIsNotNone(result)
            self.assertEqual(len(result), 1)
            mock_request.assert_called_once()
    
    def test_make_paginated_request_single_page(self):
        """Test pagination with single page of results"""
        # Mock _make_request to return single page
        with patch.object(self.client, '_make_request') as mock_request:
            mock_request.return_value = {
                'data': [{'id': 1}, {'id': 2}],
                'next_page': None,
                'total_pages': '1',
                'total': '2'
            }
            
            result = self.client._make_paginated_request('projects')
            
            self.assertIsNotNone(result)
            self.assertEqual(len(result), 2)
            mock_request.assert_called_once()
    
    def test_make_paginated_request_multiple_pages(self):
        """Test pagination across multiple pages"""
        # Mock _make_request to return multiple pages
        with patch.object(self.client, '_make_request') as mock_request:
            # Page 1 has next_page
            mock_request.side_effect = [
                {
                    'data': [{'id': 1}, {'id': 2}],
                    'next_page': '2',
                    'total_pages': '3',
                    'total': '6'
                },
                {
                    'data': [{'id': 3}, {'id': 4}],
                    'next_page': '3',
                    'total_pages': '3',
                    'total': '6'
                },
                {
                    'data': [{'id': 5}, {'id': 6}],
                    'next_page': None,
                    'total_pages': '3',
                    'total': '6'
                }
            ]
            
            result = self.client._make_paginated_request('projects')
            
            self.assertIsNotNone(result)
            self.assertEqual(len(result), 6)
            self.assertEqual(mock_request.call_count, 3)
    
    def test_make_paginated_request_empty_results(self):
        """Test pagination with empty results"""
        with patch.object(self.client, '_make_request') as mock_request:
            mock_request.return_value = {
                'data': [],
                'next_page': None,
                'total_pages': '0',
                'total': '0'
            }
            
            result = self.client._make_paginated_request('projects')
            
            self.assertIsNotNone(result)
            self.assertEqual(len(result), 0)
    
    def test_make_paginated_request_api_error(self):
        """Test pagination handles API errors"""
        with patch.object(self.client, '_make_request') as mock_request:
            mock_request.return_value = None  # API error
            
            result = self.client._make_paginated_request('projects')
            
            self.assertIsNone(result)
    
    def test_make_paginated_request_max_pages_limit(self):
        """Test pagination respects max_pages limit"""
        with patch.object(self.client, '_make_request') as mock_request:
            # Mock infinite pagination (always has next_page)
            mock_request.return_value = {
                'data': [{'id': 1}],
                'next_page': '999',
                'total_pages': '1000',
                'total': '1000'
            }
            
            result = self.client._make_paginated_request('projects', max_pages=2)
            
            self.assertIsNotNone(result)
            self.assertEqual(len(result), 2)  # 2 pages * 1 item each
            self.assertEqual(mock_request.call_count, 2)
    
    def test_make_paginated_request_uses_per_page(self):
        """Test pagination uses configured per_page parameter"""
        with patch.object(self.client, '_make_request') as mock_request:
            mock_request.return_value = {
                'data': [{'id': 1}],
                'next_page': None,
                'total_pages': '1',
                'total': '1'
            }
            
            self.client._make_paginated_request('projects')
            
            # Check that per_page was set in params
            call_args = mock_request.call_args
            self.assertEqual(call_args[0][1]['per_page'], 10)


class TestGetProjectsPagination(unittest.TestCase):
    """Test get_projects() pagination behavior"""
    
    def setUp(self):
        """Create a client instance for testing"""
        self.client = server.GitLabAPIClient(
            'https://gitlab.example.com',
            'test-token',
            per_page=100
        )
    
    def test_get_projects_without_per_page_uses_pagination(self):
        """Test get_projects() without per_page uses full pagination"""
        with patch.object(self.client, '_make_paginated_request') as mock_paginated:
            mock_paginated.return_value = [{'id': 1}]
            
            result = self.client.get_projects()
            
            mock_paginated.assert_called_once_with('projects', {'membership': 'true'})
            self.assertEqual(result, [{'id': 1}])
    
    def test_get_projects_with_per_page_single_request(self):
        """Test get_projects(per_page=X) uses single page request for backward compatibility"""
        with patch.object(self.client, '_make_request') as mock_request:
            mock_request.return_value = {
                'data': [{'id': 1}],
                'next_page': '2',
                'total_pages': '5',
                'total': '500'
            }
            
            result = self.client.get_projects(per_page=20)
            
            # Should only make one request (not paginated)
            mock_request.assert_called_once()
            self.assertEqual(result, [{'id': 1}])


class TestGetGroupProjectsPagination(unittest.TestCase):
    """Test get_group_projects() pagination behavior"""
    
    def setUp(self):
        """Create a client instance for testing"""
        self.client = server.GitLabAPIClient(
            'https://gitlab.example.com',
            'test-token',
            per_page=100
        )
    
    def test_get_group_projects_uses_pagination(self):
        """Test get_group_projects() uses full pagination"""
        with patch.object(self.client, '_make_paginated_request') as mock_paginated:
            mock_paginated.return_value = [{'id': 1}, {'id': 2}]
            
            result = self.client.get_group_projects('my-group')
            
            mock_paginated.assert_called_once_with('groups/my-group/projects')
            self.assertEqual(len(result), 2)
    
    def test_get_group_projects_handles_large_groups(self):
        """Test get_group_projects() can handle groups with >100 projects"""
        with patch.object(self.client, '_make_request') as mock_request:
            # Simulate a large group with 250 projects across 3 pages
            mock_request.side_effect = [
                {
                    'data': [{'id': i} for i in range(1, 101)],  # 100 items
                    'next_page': '2',
                    'total_pages': '3',
                    'total': '250'
                },
                {
                    'data': [{'id': i} for i in range(101, 201)],  # 100 items
                    'next_page': '3',
                    'total_pages': '3',
                    'total': '250'
                },
                {
                    'data': [{'id': i} for i in range(201, 251)],  # 50 items
                    'next_page': None,
                    'total_pages': '3',
                    'total': '250'
                }
            ]
            
            result = self.client.get_group_projects('large-group')
            
            self.assertIsNotNone(result)
            self.assertEqual(len(result), 250)
            # Verify we got all items in order
            self.assertEqual(result[0]['id'], 1)
            self.assertEqual(result[99]['id'], 100)
            self.assertEqual(result[100]['id'], 101)
            self.assertEqual(result[249]['id'], 250)


class TestGetPipelinesPagination(unittest.TestCase):
    """Test get_pipelines() pagination behavior"""
    
    def setUp(self):
        """Create a client instance for testing"""
        self.client = server.GitLabAPIClient(
            'https://gitlab.example.com',
            'test-token',
            per_page=100
        )
    
    def test_get_pipelines_without_per_page_uses_pagination(self):
        """Test get_pipelines() without per_page uses full pagination"""
        with patch.object(self.client, '_make_paginated_request') as mock_paginated:
            mock_paginated.return_value = [{'id': 1}]
            
            result = self.client.get_pipelines(123)
            
            mock_paginated.assert_called_once_with('projects/123/pipelines')
            self.assertEqual(result, [{'id': 1}])
    
    def test_get_pipelines_with_per_page_single_request(self):
        """Test get_pipelines(per_page=X) uses single page request for backward compatibility"""
        with patch.object(self.client, '_make_request') as mock_request:
            mock_request.return_value = {
                'data': [{'id': 1}],
                'next_page': '2',
                'total_pages': '10',
                'total': '1000'
            }
            
            result = self.client.get_pipelines(123, per_page=10)
            
            # Should only make one request (not paginated)
            mock_request.assert_called_once()
            self.assertEqual(result, [{'id': 1}])
    
    def test_get_pipelines_handles_projects_with_many_pipelines(self):
        """Test get_pipelines() can handle projects with >100 pipelines"""
        with patch.object(self.client, '_make_request') as mock_request:
            # Simulate a project with 150 pipelines across 2 pages
            mock_request.side_effect = [
                {
                    'data': [{'id': i} for i in range(1, 101)],  # 100 items
                    'next_page': '2',
                    'total_pages': '2',
                    'total': '150'
                },
                {
                    'data': [{'id': i} for i in range(101, 151)],  # 50 items
                    'next_page': None,
                    'total_pages': '2',
                    'total': '150'
                }
            ]
            
            result = self.client.get_pipelines(123)
            
            self.assertIsNotNone(result)
            self.assertEqual(len(result), 150)
            self.assertEqual(result[0]['id'], 1)
            self.assertEqual(result[149]['id'], 150)


class TestPaginationLogging(unittest.TestCase):
    """Test pagination logging doesn't leak secrets"""
    
    def setUp(self):
        """Create a client instance for testing"""
        self.client = server.GitLabAPIClient(
            'https://gitlab.example.com',
            'secret-token-12345',
            per_page=10
        )
    
    def test_pagination_logs_no_secrets(self):
        """Test pagination logging doesn't include API tokens"""
        with patch.object(self.client, '_make_request') as mock_request:
            mock_request.return_value = {
                'data': [{'id': 1}],
                'next_page': None,
                'total_pages': '1',
                'total': '1'
            }
            
            # Capture log output
            with patch('server.logger') as mock_logger:
                self.client._make_paginated_request('projects')
                
                # Check all log calls don't contain the token
                for call_obj in mock_logger.info.call_args_list:
                    log_message = str(call_obj)
                    self.assertNotIn('secret-token-12345', log_message)
                    self.assertNotIn(self.client.api_token, log_message)
    
    def test_request_logging_redacts_token(self):
        """Test that request logging redacts API token"""
        # The token should never appear in logs
        # This is handled by not logging the headers
        with patch.object(self.client, '_make_request') as mock_request:
            mock_request.return_value = {
                'data': [{'id': 1}],
                'next_page': None,
                'total_pages': '1',
                'total': '1'
            }
            
            with patch('server.logger') as mock_logger:
                self.client.get_projects()
                
                # Verify no log contains the actual token
                all_logs = []
                for method in [mock_logger.debug, mock_logger.info, mock_logger.warning, mock_logger.error]:
                    all_logs.extend([str(c) for c in method.call_args_list])
                
                for log in all_logs:
                    self.assertNotIn('secret-token-12345', log)


class TestPerPageConfiguration(unittest.TestCase):
    """Test per_page configuration from config/env"""
    
    def test_per_page_from_config(self):
        """Test per_page can be set from config"""
        client = server.GitLabAPIClient(
            'https://gitlab.example.com',
            'test-token',
            per_page=50
        )
        self.assertEqual(client.per_page, 50)
    
    def test_per_page_default(self):
        """Test default per_page value"""
        client = server.GitLabAPIClient(
            'https://gitlab.example.com',
            'test-token'
        )
        self.assertEqual(client.per_page, 100)
    
    def test_per_page_used_in_pagination(self):
        """Test per_page is used in paginated requests"""
        client = server.GitLabAPIClient(
            'https://gitlab.example.com',
            'test-token',
            per_page=25
        )
        
        with patch.object(client, '_make_request') as mock_request:
            mock_request.return_value = {
                'data': [{'id': 1}],
                'next_page': None,
                'total_pages': '1',
                'total': '1'
            }
            
            client._make_paginated_request('projects')
            
            # Check that per_page=25 was used
            call_args = mock_request.call_args
            self.assertEqual(call_args[0][1]['per_page'], 25)


if __name__ == '__main__':
    unittest.main()

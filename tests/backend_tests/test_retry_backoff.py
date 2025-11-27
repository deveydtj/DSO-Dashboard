#!/usr/bin/env python3
"""
Tests for retry/backoff and rate-limiting logic (BE-3)
Tests the gitlab_request() method that handles:
- 429 rate-limiting with Retry-After header
- 429 rate-limiting with exponential backoff
- 5xx server errors with exponential backoff
- Timeout and connection errors with retry
- Max retries exceeded
"""

import unittest
import sys
import os
import time
from unittest.mock import MagicMock, patch, call
from urllib.error import HTTPError, URLError

# Add parent directory to path to from backend import app as server module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend import app as server


class TestRateLimitHandling(unittest.TestCase):
    """Test 429 rate-limiting with Retry-After header"""
    
    def setUp(self):
        """Create a client instance for testing"""
        self.client = server.GitLabAPIClient(
            'https://gitlab.example.com',
            'test-token',
            max_retries=3,
            initial_retry_delay=1.0
        )
    
    def test_429_with_retry_after_header(self):
        """Test 429 rate-limiting respects Retry-After header"""
        # Create mock 429 error with Retry-After header
        mock_error = HTTPError(
            url='https://gitlab.example.com/api/v4/projects',
            code=429,
            msg='Too Many Requests',
            hdrs={'Retry-After': '2'},
            fp=None
        )
        
        # Mock urlopen to raise 429 once, then succeed
        with patch('backend.app.urlopen') as mock_urlopen:
            # First call raises 429
            mock_success_response = MagicMock()
            mock_success_response.read.return_value = b'{"data": "success"}'
            mock_success_response.headers = {}
            mock_success_response.__enter__ = MagicMock(return_value=mock_success_response)
            mock_success_response.__exit__ = MagicMock(return_value=False)
            
            mock_urlopen.side_effect = [mock_error, mock_success_response]
            
            # Mock time.sleep to avoid actual delays
            with patch('time.sleep') as mock_sleep:
                result = self.client.gitlab_request('projects')
                
                # Should have slept for 2 seconds (from Retry-After header)
                mock_sleep.assert_called_once_with(2)
                
                # Should have succeeded on retry
                self.assertIsNotNone(result)
                self.assertEqual(result['data'], {'data': 'success'})
    
    def test_429_with_exponential_backoff(self):
        """Test 429 rate-limiting uses exponential backoff when Retry-After is missing"""
        # Create mock 429 error without Retry-After header
        mock_error = HTTPError(
            url='https://gitlab.example.com/api/v4/projects',
            code=429,
            msg='Too Many Requests',
            hdrs={},
            fp=None
        )
        
        with patch('backend.app.urlopen') as mock_urlopen:
            # First call raises 429, second succeeds
            mock_success_response = MagicMock()
            mock_success_response.read.return_value = b'{"data": "success"}'
            mock_success_response.headers = {}
            mock_success_response.__enter__ = MagicMock(return_value=mock_success_response)
            mock_success_response.__exit__ = MagicMock(return_value=False)
            
            mock_urlopen.side_effect = [mock_error, mock_success_response]
            
            with patch('time.sleep') as mock_sleep:
                result = self.client.gitlab_request('projects')
                
                # Should have used exponential backoff: 1.0 * (2^0) = 1.0
                mock_sleep.assert_called_once_with(1.0)
                
                self.assertIsNotNone(result)
    
    def test_429_max_retries_exceeded(self):
        """Test 429 returns None after max retries exceeded"""
        mock_error = HTTPError(
            url='https://gitlab.example.com/api/v4/projects',
            code=429,
            msg='Too Many Requests',
            hdrs={},
            fp=None
        )
        
        with patch('backend.app.urlopen') as mock_urlopen:
            # Always raise 429
            mock_urlopen.side_effect = mock_error
            
            with patch('time.sleep') as mock_sleep:
                result = self.client.gitlab_request('projects')
                
                # Should return None after max retries
                self.assertIsNone(result)
                
                # For 429: sleep happens BEFORE checking retry_count < max_retries
                # Sequence: fail, sleep(1s), check(0<3)✓, retry 1, fail, sleep(2s), check(1<3)✓, retry 2, 
                #          fail, sleep(4s), check(2<3)✓, retry 3, fail, sleep(8s), check(3<3)✗, return None
                # Total: 4 sleep calls
                self.assertEqual(mock_sleep.call_count, 4)
                expected_calls = [call(1.0), call(2.0), call(4.0), call(8.0)]
                mock_sleep.assert_has_calls(expected_calls)
    
    def test_429_invalid_retry_after_header(self):
        """Test 429 with invalid Retry-After falls back to exponential backoff"""
        mock_error = HTTPError(
            url='https://gitlab.example.com/api/v4/projects',
            code=429,
            msg='Too Many Requests',
            hdrs={'Retry-After': 'invalid'},
            fp=None
        )
        
        with patch('backend.app.urlopen') as mock_urlopen:
            mock_success_response = MagicMock()
            mock_success_response.read.return_value = b'{"data": "success"}'
            mock_success_response.headers = {}
            mock_success_response.__enter__ = MagicMock(return_value=mock_success_response)
            mock_success_response.__exit__ = MagicMock(return_value=False)
            
            mock_urlopen.side_effect = [mock_error, mock_success_response]
            
            with patch('time.sleep') as mock_sleep:
                result = self.client.gitlab_request('projects')
                
                # Should fall back to exponential backoff
                mock_sleep.assert_called_once_with(1.0)
                self.assertIsNotNone(result)


class TestServerErrorRetry(unittest.TestCase):
    """Test 5xx server error retry with exponential backoff"""
    
    def setUp(self):
        """Create a client instance for testing"""
        self.client = server.GitLabAPIClient(
            'https://gitlab.example.com',
            'test-token',
            max_retries=3,
            initial_retry_delay=1.0
        )
    
    def test_500_error_retry_with_exponential_backoff(self):
        """Test 500 server error retries with exponential backoff"""
        mock_error = HTTPError(
            url='https://gitlab.example.com/api/v4/projects',
            code=500,
            msg='Internal Server Error',
            hdrs={},
            fp=None
        )
        
        with patch('backend.app.urlopen') as mock_urlopen:
            # Fail twice with 500, then succeed
            mock_success_response = MagicMock()
            mock_success_response.read.return_value = b'{"data": "success"}'
            mock_success_response.headers = {}
            mock_success_response.__enter__ = MagicMock(return_value=mock_success_response)
            mock_success_response.__exit__ = MagicMock(return_value=False)
            
            mock_urlopen.side_effect = [mock_error, mock_error, mock_success_response]
            
            with patch('time.sleep') as mock_sleep:
                result = self.client.gitlab_request('projects')
                
                # Should have used exponential backoff: 1s, 2s
                expected_calls = [call(1.0), call(2.0)]
                mock_sleep.assert_has_calls(expected_calls)
                self.assertEqual(mock_sleep.call_count, 2)
                
                self.assertIsNotNone(result)
    
    def test_503_error_retry(self):
        """Test 503 service unavailable retries"""
        mock_error = HTTPError(
            url='https://gitlab.example.com/api/v4/projects',
            code=503,
            msg='Service Unavailable',
            hdrs={},
            fp=None
        )
        
        with patch('backend.app.urlopen') as mock_urlopen:
            mock_success_response = MagicMock()
            mock_success_response.read.return_value = b'{"data": "success"}'
            mock_success_response.headers = {}
            mock_success_response.__enter__ = MagicMock(return_value=mock_success_response)
            mock_success_response.__exit__ = MagicMock(return_value=False)
            
            mock_urlopen.side_effect = [mock_error, mock_success_response]
            
            with patch('time.sleep') as mock_sleep:
                result = self.client.gitlab_request('projects')
                
                # Should retry and succeed
                mock_sleep.assert_called_once_with(1.0)
                self.assertIsNotNone(result)
    
    def test_5xx_max_retries_exceeded(self):
        """Test 5xx returns None after max retries"""
        mock_error = HTTPError(
            url='https://gitlab.example.com/api/v4/projects',
            code=502,
            msg='Bad Gateway',
            hdrs={},
            fp=None
        )
        
        with patch('backend.app.urlopen') as mock_urlopen:
            # Always fail with 502
            mock_urlopen.side_effect = mock_error
            
            with patch('time.sleep') as mock_sleep:
                result = self.client.gitlab_request('projects')
                
                # Should return None
                self.assertIsNone(result)
                
                # For 5xx: check retry_count < max_retries BEFORE sleeping
                # Sequence: fail, check(0<3)✓, sleep(1s), retry 1, fail, check(1<3)✓, sleep(2s), retry 2,
                #          fail, check(2<3)✓, sleep(4s), retry 3, fail, check(3<3)✗, return None
                # Total: 3 sleep calls
                self.assertEqual(mock_sleep.call_count, 3)
                expected_calls = [call(1.0), call(2.0), call(4.0)]
                mock_sleep.assert_has_calls(expected_calls)


class TestTimeoutAndConnectionErrorRetry(unittest.TestCase):
    """Test timeout and connection error retry"""
    
    def setUp(self):
        """Create a client instance for testing"""
        self.client = server.GitLabAPIClient(
            'https://gitlab.example.com',
            'test-token',
            max_retries=3,
            initial_retry_delay=1.0
        )
    
    def test_timeout_error_retry(self):
        """Test timeout error retries with exponential backoff"""
        mock_error = URLError('timed out')
        
        with patch('backend.app.urlopen') as mock_urlopen:
            mock_success_response = MagicMock()
            mock_success_response.read.return_value = b'{"data": "success"}'
            mock_success_response.headers = {}
            mock_success_response.__enter__ = MagicMock(return_value=mock_success_response)
            mock_success_response.__exit__ = MagicMock(return_value=False)
            
            mock_urlopen.side_effect = [mock_error, mock_success_response]
            
            with patch('time.sleep') as mock_sleep:
                result = self.client.gitlab_request('projects')
                
                # Should retry and succeed
                mock_sleep.assert_called_once_with(1.0)
                self.assertIsNotNone(result)
    
    def test_connection_error_retry(self):
        """Test connection error retries"""
        mock_error = URLError('Connection refused')
        
        with patch('backend.app.urlopen') as mock_urlopen:
            mock_success_response = MagicMock()
            mock_success_response.read.return_value = b'{"data": "success"}'
            mock_success_response.headers = {}
            mock_success_response.__enter__ = MagicMock(return_value=mock_success_response)
            mock_success_response.__exit__ = MagicMock(return_value=False)
            
            mock_urlopen.side_effect = [mock_error, mock_success_response]
            
            with patch('time.sleep') as mock_sleep:
                result = self.client.gitlab_request('projects')
                
                # Should retry and succeed
                mock_sleep.assert_called_once_with(1.0)
                self.assertIsNotNone(result)
    
    def test_connection_error_max_retries_exceeded(self):
        """Test connection error returns None after max retries"""
        mock_error = URLError('Connection reset by peer')
        
        with patch('backend.app.urlopen') as mock_urlopen:
            # Always fail
            mock_urlopen.side_effect = mock_error
            
            with patch('time.sleep') as mock_sleep:
                result = self.client.gitlab_request('projects')
                
                # Should return None
                self.assertIsNone(result)
                
                # For URLError: check retry_count < max_retries BEFORE sleeping
                # Same logic as 5xx errors - sleep happens inside the retry condition
                # Total: 3 sleep calls for max_retries=3
                self.assertEqual(mock_sleep.call_count, 3)


class TestNonRetryableErrors(unittest.TestCase):
    """Test that non-retryable errors (4xx except 429) don't retry"""
    
    def setUp(self):
        """Create a client instance for testing"""
        self.client = server.GitLabAPIClient(
            'https://gitlab.example.com',
            'test-token',
            max_retries=3,
            initial_retry_delay=1.0
        )
    
    def test_401_unauthorized_no_retry(self):
        """Test 401 unauthorized doesn't retry"""
        mock_error = HTTPError(
            url='https://gitlab.example.com/api/v4/projects',
            code=401,
            msg='Unauthorized',
            hdrs={},
            fp=None
        )
        
        with patch('backend.app.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = mock_error
            
            with patch('time.sleep') as mock_sleep:
                result = self.client.gitlab_request('projects')
                
                # Should not retry
                mock_sleep.assert_not_called()
                
                # Should return None immediately
                self.assertIsNone(result)
    
    def test_404_not_found_no_retry(self):
        """Test 404 not found doesn't retry"""
        mock_error = HTTPError(
            url='https://gitlab.example.com/api/v4/projects',
            code=404,
            msg='Not Found',
            hdrs={},
            fp=None
        )
        
        with patch('backend.app.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = mock_error
            
            with patch('time.sleep') as mock_sleep:
                result = self.client.gitlab_request('projects')
                
                # Should not retry
                mock_sleep.assert_not_called()
                self.assertIsNone(result)


class TestExponentialBackoffFormula(unittest.TestCase):
    """Test exponential backoff formula is correct"""
    
    def test_backoff_sequence(self):
        """Test exponential backoff sequence: 1s, 2s, 4s, 8s, ..."""
        client = server.GitLabAPIClient(
            'https://gitlab.example.com',
            'test-token',
            max_retries=5,
            initial_retry_delay=1.0
        )
        
        # Simulate multiple retries and check backoff times
        mock_error = HTTPError(
            url='https://gitlab.example.com/api/v4/projects',
            code=503,
            msg='Service Unavailable',
            hdrs={},
            fp=None
        )
        
        with patch('backend.app.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = mock_error
            
            with patch('time.sleep') as mock_sleep:
                result = client.gitlab_request('projects')
                
                # Should have exponential backoff: 1, 2, 4, 8, 16
                expected_calls = [call(1.0), call(2.0), call(4.0), call(8.0), call(16.0)]
                mock_sleep.assert_has_calls(expected_calls)
                self.assertEqual(mock_sleep.call_count, 5)
    
    def test_custom_initial_delay(self):
        """Test exponential backoff with custom initial delay"""
        client = server.GitLabAPIClient(
            'https://gitlab.example.com',
            'test-token',
            max_retries=3,
            initial_retry_delay=2.0
        )
        
        mock_error = HTTPError(
            url='https://gitlab.example.com/api/v4/projects',
            code=503,
            msg='Service Unavailable',
            hdrs={},
            fp=None
        )
        
        with patch('backend.app.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = mock_error
            
            with patch('time.sleep') as mock_sleep:
                result = client.gitlab_request('projects')
                
                # Should have exponential backoff starting at 2.0: 2, 4, 8
                expected_calls = [call(2.0), call(4.0), call(8.0)]
                mock_sleep.assert_has_calls(expected_calls)


class TestRetryLogic(unittest.TestCase):
    """Test retry logic works correctly across different scenarios"""
    
    def test_success_on_first_try(self):
        """Test successful request on first try doesn't retry"""
        client = server.GitLabAPIClient(
            'https://gitlab.example.com',
            'test-token',
            max_retries=3,
            initial_retry_delay=1.0
        )
        
        with patch('backend.app.urlopen') as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = b'{"data": "success"}'
            mock_response.headers = {}
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            
            mock_urlopen.return_value = mock_response
            
            with patch('time.sleep') as mock_sleep:
                result = client.gitlab_request('projects')
                
                # Should not sleep on successful first try
                mock_sleep.assert_not_called()
                
                # Should return result
                self.assertIsNotNone(result)
                self.assertEqual(result['data'], {'data': 'success'})
    
    def test_mixed_errors_with_eventual_success(self):
        """Test mixed errors (429, 503, timeout) with eventual success"""
        client = server.GitLabAPIClient(
            'https://gitlab.example.com',
            'test-token',
            max_retries=5,
            initial_retry_delay=1.0
        )
        
        mock_429 = HTTPError(
            url='https://gitlab.example.com/api/v4/projects',
            code=429,
            msg='Too Many Requests',
            hdrs={'Retry-After': '1'},
            fp=None
        )
        
        mock_503 = HTTPError(
            url='https://gitlab.example.com/api/v4/projects',
            code=503,
            msg='Service Unavailable',
            hdrs={},
            fp=None
        )
        
        mock_timeout = URLError('timed out')
        
        with patch('backend.app.urlopen') as mock_urlopen:
            mock_success = MagicMock()
            mock_success.read.return_value = b'{"data": "success"}'
            mock_success.headers = {}
            mock_success.__enter__ = MagicMock(return_value=mock_success)
            mock_success.__exit__ = MagicMock(return_value=False)
            
            # Fail with different errors, then succeed
            mock_urlopen.side_effect = [mock_429, mock_503, mock_timeout, mock_success]
            
            with patch('time.sleep') as mock_sleep:
                result = client.gitlab_request('projects')
                
                # Should have retried and eventually succeeded
                self.assertIsNotNone(result)
                
                # Should have slept 3 times (once for each error)
                self.assertEqual(mock_sleep.call_count, 3)


if __name__ == '__main__':
    unittest.main()

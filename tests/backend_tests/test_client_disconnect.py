#!/usr/bin/env python3
"""
Tests for handling client disconnect errors during JSON response writes
"""

import unittest
import sys
import os
import io
from unittest.mock import MagicMock, patch

# Add parent directory to path to import backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend import app as server


class TestClientDisconnectHandling(unittest.TestCase):
    """Test that send_json_response handles client disconnects gracefully"""
    
    def setUp(self):
        """Set up a mock request handler"""
        self.handler = MagicMock(spec=server.DashboardRequestHandler)
        self.handler.send_response = MagicMock()
        self.handler.send_header = MagicMock()
        self.handler.end_headers = MagicMock()
        
    def test_normal_response_succeeds(self):
        """Test that normal response writing still works"""
        # Create a mock wfile that accepts writes
        self.handler.wfile = io.BytesIO()
        
        # Call send_json_response
        server.DashboardRequestHandler.send_json_response(
            self.handler, 
            {'status': 'ok', 'message': 'test'}
        )
        
        # Verify data was written
        written_data = self.handler.wfile.getvalue()
        self.assertGreater(len(written_data), 0)
        self.assertIn(b'status', written_data)
        self.assertIn(b'ok', written_data)
    
    def test_connection_aborted_error_handled(self):
        """Test that ConnectionAbortedError is caught and logged"""
        # Create a mock wfile that raises ConnectionAbortedError
        mock_wfile = MagicMock()
        mock_wfile.write.side_effect = ConnectionAbortedError("Client closed connection")
        self.handler.wfile = mock_wfile
        
        # Call send_json_response - should not raise
        with patch.object(server.logger, 'debug') as mock_log:
            server.DashboardRequestHandler.send_json_response(
                self.handler,
                {'test': 'data'}
            )
            
            # Verify debug log was called (not warning or error)
            mock_log.assert_called_once()
            log_message = mock_log.call_args[0][0]
            self.assertIn('Client disconnected', log_message)
            self.assertIn('ConnectionAbortedError', log_message)
    
    def test_connection_reset_error_handled(self):
        """Test that ConnectionResetError is caught and logged"""
        # Create a mock wfile that raises ConnectionResetError
        mock_wfile = MagicMock()
        mock_wfile.write.side_effect = ConnectionResetError("Connection reset by peer")
        self.handler.wfile = mock_wfile
        
        # Call send_json_response - should not raise
        with patch.object(server.logger, 'debug') as mock_log:
            server.DashboardRequestHandler.send_json_response(
                self.handler,
                {'test': 'data'}
            )
            
            # Verify debug log was called
            mock_log.assert_called_once()
            log_message = mock_log.call_args[0][0]
            self.assertIn('Client disconnected', log_message)
            self.assertIn('ConnectionResetError', log_message)
    
    def test_broken_pipe_error_handled(self):
        """Test that BrokenPipeError is caught and logged"""
        # Create a mock wfile that raises BrokenPipeError
        mock_wfile = MagicMock()
        mock_wfile.write.side_effect = BrokenPipeError("Broken pipe")
        self.handler.wfile = mock_wfile
        
        # Call send_json_response - should not raise
        with patch.object(server.logger, 'debug') as mock_log:
            server.DashboardRequestHandler.send_json_response(
                self.handler,
                {'test': 'data'}
            )
            
            # Verify debug log was called
            mock_log.assert_called_once()
            log_message = mock_log.call_args[0][0]
            self.assertIn('Client disconnected', log_message)
            self.assertIn('BrokenPipeError', log_message)
    
    def test_unexpected_write_error_handled(self):
        """Test that unexpected write errors are caught and logged at warning level"""
        # Create a mock wfile that raises an unexpected error
        mock_wfile = MagicMock()
        mock_wfile.write.side_effect = IOError("Unexpected IO error")
        self.handler.wfile = mock_wfile
        
        # Call send_json_response - should not raise
        with patch.object(server.logger, 'warning') as mock_log:
            server.DashboardRequestHandler.send_json_response(
                self.handler,
                {'test': 'data'}
            )
            
            # Verify warning log was called (not debug)
            mock_log.assert_called_once()
            log_message = mock_log.call_args[0][0]
            self.assertIn('Error writing JSON response', log_message)
    
    def test_headers_sent_before_disconnect(self):
        """Test that headers are sent even if write fails"""
        # Create a mock wfile that raises error on write
        mock_wfile = MagicMock()
        mock_wfile.write.side_effect = ConnectionAbortedError("Client closed")
        self.handler.wfile = mock_wfile
        
        # Call send_json_response
        with patch.object(server.logger, 'debug'):
            server.DashboardRequestHandler.send_json_response(
                self.handler,
                {'test': 'data'},
                status=200
            )
        
        # Verify send_response and headers were called before the write
        self.handler.send_response.assert_called_once_with(200)
        self.handler.send_header.assert_called()
        self.handler.end_headers.assert_called_once()


if __name__ == '__main__':
    unittest.main()

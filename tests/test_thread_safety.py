#!/usr/bin/env python3
"""
Tests for thread-safe STATE management to prevent torn reads
"""

import unittest
from unittest.mock import MagicMock, patch
import threading
import time
from datetime import datetime
import sys
import os

# Add parent directory to path so we can import server
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import server


class TestThreadSafeStateSnapshot(unittest.TestCase):
    """Test that get_state_snapshot provides atomic snapshots"""
    
    def setUp(self):
        """Reset STATE before each test"""
        with server.STATE_LOCK:
            server.STATE['data'] = {
                'projects': [],
                'pipelines': [],
                'summary': dict(server.DEFAULT_SUMMARY)
            }
            server.STATE['last_updated'] = None
            server.STATE['status'] = 'INITIALIZING'
            server.STATE['error'] = None
    
    def test_get_state_snapshot_returns_consistent_data(self):
        """Test that snapshot captures all data atomically"""
        # Set up some test data
        test_projects = [{'id': 1, 'name': 'test-project'}]
        test_pipelines = [{'id': 101, 'status': 'success'}]
        test_summary = {'total_repositories': 1, 'total_pipelines': 1}
        
        server.update_state_atomic({
            'projects': test_projects,
            'pipelines': test_pipelines,
            'summary': test_summary
        })
        
        # Get snapshot
        snapshot = server.get_state_snapshot()
        
        # Verify all data is present
        self.assertIn('data', snapshot)
        self.assertIn('last_updated', snapshot)
        self.assertIn('status', snapshot)
        self.assertIn('error', snapshot)
        
        # Verify data contents
        self.assertEqual(snapshot['data']['projects'], test_projects)
        self.assertEqual(snapshot['data']['pipelines'], test_pipelines)
        self.assertEqual(snapshot['data']['summary'], test_summary)
        self.assertEqual(snapshot['status'], 'ONLINE')
        self.assertIsInstance(snapshot['last_updated'], datetime)
    
    def test_snapshot_is_consistent_during_concurrent_updates(self):
        """Test that snapshot is never torn between updates"""
        iterations = 100
        torn_reads = []
        
        def writer_thread():
            """Continuously update STATE with matching data"""
            for i in range(iterations):
                # Each iteration, write matching values
                server.update_state_atomic({
                    'projects': [{'id': i}],
                    'pipelines': [{'id': i}],
                    'summary': {'counter': i}
                })
                time.sleep(0.001)  # Small delay
        
        def reader_thread():
            """Continuously read snapshots and check consistency"""
            for _ in range(iterations):
                snapshot = server.get_state_snapshot()
                projects = snapshot['data'].get('projects', [])
                pipelines = snapshot['data'].get('pipelines', [])
                summary = snapshot['data'].get('summary', {})
                
                # If data exists, verify it's internally consistent
                if projects and pipelines and summary:
                    project_id = projects[0].get('id')
                    pipeline_id = pipelines[0].get('id')
                    counter = summary.get('counter')
                    
                    # All three should match (same update iteration)
                    if project_id != pipeline_id or project_id != counter:
                        torn_reads.append({
                            'project_id': project_id,
                            'pipeline_id': pipeline_id,
                            'counter': counter
                        })
                
                time.sleep(0.001)  # Small delay
        
        # Start writer and multiple reader threads
        writer = threading.Thread(target=writer_thread)
        readers = [threading.Thread(target=reader_thread) for _ in range(3)]
        
        writer.start()
        for reader in readers:
            reader.start()
        
        # Wait for all threads to complete
        writer.join()
        for reader in readers:
            reader.join()
        
        # Assert no torn reads occurred
        self.assertEqual(len(torn_reads), 0, 
                        f"Found {len(torn_reads)} torn reads: {torn_reads[:5]}")
    
    def test_multiple_get_state_calls_can_produce_torn_reads(self):
        """Demonstrate that multiple get_state() calls can be inconsistent
        
        This test shows why we need get_state_snapshot() - multiple separate
        calls to get_state() can see different versions of the data.
        """
        inconsistencies = []
        iterations = 50
        
        def writer_thread():
            """Update STATE with incrementing values"""
            for i in range(iterations):
                server.update_state_atomic({
                    'projects': [{'version': i}],
                    'pipelines': [{'version': i}]
                })
                time.sleep(0.001)
        
        def reader_thread_separate_calls():
            """Read using separate get_state() calls"""
            for _ in range(iterations):
                # Two separate lock acquisitions - can see torn state
                projects = server.get_state('projects')
                pipelines = server.get_state('pipelines')
                
                if projects and pipelines:
                    proj_ver = projects[0].get('version')
                    pipe_ver = pipelines[0].get('version')
                    
                    if proj_ver != pipe_ver:
                        inconsistencies.append({
                            'proj_version': proj_ver,
                            'pipe_version': pipe_ver
                        })
                
                time.sleep(0.001)
        
        # Start threads
        writer = threading.Thread(target=writer_thread)
        readers = [threading.Thread(target=reader_thread_separate_calls) for _ in range(3)]
        
        writer.start()
        for reader in readers:
            reader.start()
        
        writer.join()
        for reader in readers:
            reader.join()
        
        # We expect this test might find inconsistencies (demonstrating the problem)
        # But it's not guaranteed due to timing, so we don't assert
        if inconsistencies:
            print(f"\nNote: Found {len(inconsistencies)} torn reads with separate get_state() calls")
            print(f"This demonstrates why atomic snapshots are needed.")
    
    def test_update_state_atomic_updates_all_fields_together(self):
        """Test that update_state_atomic updates all fields with single timestamp"""
        before_time = datetime.now()
        
        server.update_state_atomic({
            'projects': [{'id': 1}],
            'pipelines': [{'id': 2}],
            'summary': {'total': 3}
        })
        
        after_time = datetime.now()
        
        # Get snapshot to verify
        snapshot = server.get_state_snapshot()
        
        # All data should be present
        self.assertEqual(len(snapshot['data']['projects']), 1)
        self.assertEqual(len(snapshot['data']['pipelines']), 1)
        self.assertIsNotNone(snapshot['data']['summary'])
        
        # Should have a single timestamp
        self.assertIsNotNone(snapshot['last_updated'])
        self.assertGreaterEqual(snapshot['last_updated'], before_time)
        self.assertLessEqual(snapshot['last_updated'], after_time)
        
        # Status should be updated
        self.assertEqual(snapshot['status'], 'ONLINE')
        self.assertIsNone(snapshot['error'])


class TestHandlersUseAtomicSnapshots(unittest.TestCase):
    """Test that request handlers use atomic snapshots"""
    
    def setUp(self):
        """Reset STATE before each test"""
        with server.STATE_LOCK:
            server.STATE['data'] = {
                'projects': [{'id': 1, 'name': 'test'}],
                'pipelines': [{'id': 101, 'status': 'success', 'project_id': 1}],
                'summary': {
                    'total_repositories': 1,
                    'total_pipelines': 1,
                    'successful_pipelines': 1,
                    'failed_pipelines': 0,
                    'running_pipelines': 0,
                    'pending_pipelines': 0,
                    'pipeline_success_rate': 1.0,
                    'pipeline_statuses': {'success': 1}
                }
            }
            server.STATE['last_updated'] = datetime.now()
            server.STATE['status'] = 'ONLINE'
            server.STATE['error'] = None
    
    def test_handlers_call_get_state_snapshot(self):
        """Verify handlers use get_state_snapshot for atomic reads"""
        # Test that the handler methods call get_state_snapshot
        # We'll check this by examining the code pattern
        
        # Read handler code to verify pattern
        import inspect
        
        # Check handle_summary uses get_state_snapshot
        handle_summary_src = inspect.getsource(server.DashboardRequestHandler.handle_summary)
        self.assertIn('get_state_snapshot()', handle_summary_src, 
                     "handle_summary should use get_state_snapshot()")
        
        # Check handle_repos uses get_state_snapshot
        handle_repos_src = inspect.getsource(server.DashboardRequestHandler.handle_repos)
        self.assertIn('get_state_snapshot()', handle_repos_src,
                     "handle_repos should use get_state_snapshot()")
        
        # Check handle_pipelines uses get_state_snapshot
        handle_pipelines_src = inspect.getsource(server.DashboardRequestHandler.handle_pipelines)
        self.assertIn('get_state_snapshot()', handle_pipelines_src,
                     "handle_pipelines should use get_state_snapshot()")
        
        # Check handle_health uses get_state_snapshot
        handle_health_src = inspect.getsource(server.DashboardRequestHandler.handle_health)
        self.assertIn('get_state_snapshot()', handle_health_src,
                     "handle_health should use get_state_snapshot()")
    
    def test_handlers_do_not_use_multiple_get_state_calls(self):
        """Verify handlers don't use multiple get_state() calls that could cause torn reads"""
        import inspect
        
        # Check that handlers don't have the old pattern of multiple get_state calls
        handlers = [
            server.DashboardRequestHandler.handle_summary,
            server.DashboardRequestHandler.handle_repos,
            server.DashboardRequestHandler.handle_pipelines,
            server.DashboardRequestHandler.handle_health
        ]
        
        for handler in handlers:
            handler_src = inspect.getsource(handler)
            handler_name = handler.__name__
            
            # Count occurrences of get_state( and get_state_status(
            # These should not appear together (causing torn reads)
            get_state_count = handler_src.count('get_state(')
            get_state_status_count = handler_src.count('get_state_status(')
            
            # If both appear, that's the old pattern (torn reads possible)
            if get_state_count > 0 and get_state_status_count > 0:
                self.fail(f"{handler_name} uses both get_state() and get_state_status() "
                         f"which can cause torn reads. Should use get_state_snapshot() instead.")
            
            # New pattern should use get_state_snapshot, not separate calls
            if get_state_count > 0 or get_state_status_count > 0:
                # If they're using the old functions, they should only use get_state_snapshot
                self.assertIn('get_state_snapshot()', handler_src,
                             f"{handler_name} should use get_state_snapshot() for atomic reads")


class TestBackgroundPollerAtomicSwap(unittest.TestCase):
    """Test that BackgroundPoller builds data locally then swaps atomically"""
    
    def test_poller_uses_update_state_atomic(self):
        """Verify BackgroundPoller.poll_data uses update_state_atomic for swap"""
        import inspect
        
        # Check that poll_data calls update_state_atomic (not individual update_state)
        poll_data_src = inspect.getsource(server.BackgroundPoller.poll_data)
        
        # Should call update_state_atomic
        self.assertIn('update_state_atomic', poll_data_src,
                     "poll_data should use update_state_atomic for atomic STATE swap")
        
        # Should pass all three keys at once
        self.assertIn("'projects'", poll_data_src)
        self.assertIn("'pipelines'", poll_data_src)
        self.assertIn("'summary'", poll_data_src)
    
    def test_poller_builds_data_before_updating_state(self):
        """Verify poll_data builds all data locally before STATE update"""
        import inspect
        
        poll_data_src = inspect.getsource(server.BackgroundPoller.poll_data)
        
        # Find positions of key operations
        fetch_projects_pos = poll_data_src.find('_fetch_projects(')
        fetch_pipelines_pos = poll_data_src.find('_fetch_pipelines(')
        enrich_pos = poll_data_src.find('_enrich_projects_with_pipelines(')
        calculate_pos = poll_data_src.find('_calculate_summary(')
        update_pos = poll_data_src.find('update_state_atomic(')
        
        # All operations should be present
        self.assertGreater(fetch_projects_pos, 0, "Should fetch projects")
        self.assertGreater(fetch_pipelines_pos, 0, "Should fetch pipelines")
        self.assertGreater(enrich_pos, 0, "Should enrich projects")
        self.assertGreater(calculate_pos, 0, "Should calculate summary")
        self.assertGreater(update_pos, 0, "Should update state atomically")
        
        # update_state_atomic should come AFTER all data processing
        self.assertGreater(update_pos, fetch_projects_pos,
                          "STATE update should come after fetching projects")
        self.assertGreater(update_pos, fetch_pipelines_pos,
                          "STATE update should come after fetching pipelines")
        self.assertGreater(update_pos, enrich_pos,
                          "STATE update should come after enrichment")
        self.assertGreater(update_pos, calculate_pos,
                          "STATE update should come after summary calculation")


if __name__ == '__main__':
    unittest.main()

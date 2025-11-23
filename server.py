#!/usr/bin/env python3
"""
GitLab Dashboard Backend Server
Python 3.10 stdlib-only implementation using http.server and urllib
"""

import json
import os
import ssl
import time
import threading
from datetime import datetime, timedelta
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import urlparse, parse_qs, urlencode
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Pipeline fetching configuration constants
MAX_PROJECTS_FOR_PIPELINES = 20  # Max projects to fetch pipelines from
PIPELINES_PER_PROJECT = 10       # Pipelines to fetch per project
MAX_TOTAL_PIPELINES = 50         # Max total pipelines to return

# API query parameter constants
DEFAULT_PIPELINE_LIMIT = 50      # Default limit for /api/pipelines endpoint
MAX_PIPELINE_LIMIT = 1000        # Maximum limit for /api/pipelines endpoint

# Timestamp fallback constants
EPOCH_TIMESTAMP = '1970-01-01T00:00:00Z'  # Fallback for missing timestamps

# Default branch constant
DEFAULT_BRANCH_NAME = 'main'     # Default branch name fallback


class GitLabAPIClient:
    """GitLab API client using urllib with retry, rate limiting, and pagination support"""
    
    def __init__(self, gitlab_url, api_token, per_page=100, insecure_skip_verify=False, 
                 max_retries=3, initial_retry_delay=1.0):
        self.gitlab_url = gitlab_url.rstrip('/')
        self.api_token = api_token
        self.base_url = f"{self.gitlab_url}/api/v4"
        self.per_page = per_page
        self.insecure_skip_verify = insecure_skip_verify
        self.max_retries = max_retries
        self.initial_retry_delay = initial_retry_delay
        
        # Create SSL context for self-signed certificates
        if self.insecure_skip_verify:
            # Use public API for better stability
            self.ssl_context = ssl.create_default_context()
            self.ssl_context.check_hostname = False
            self.ssl_context.verify_mode = ssl.CERT_NONE
            logger.warning("=" * 70)
            logger.warning("SSL VERIFICATION DISABLED - SECURITY RISK")
            logger.warning("Using unverified SSL context for self-signed certificates")
            logger.warning("Only use this setting on trusted internal networks")
            logger.warning("=" * 70)
        else:
            self.ssl_context = None
    
    def _make_request(self, endpoint, params=None, retry_count=0):
        """Make a request to GitLab API with retry and rate limiting"""
        url = f"{self.base_url}/{endpoint}"
        
        if params:
            query_string = urlencode(params)
            url = f"{url}?{query_string}"
        
        headers = {
            'PRIVATE-TOKEN': self.api_token,
            'Content-Type': 'application/json'
        }
        
        try:
            request = Request(url, headers=headers)
            
            # Open with SSL context if configured
            if self.ssl_context:
                with urlopen(request, timeout=30, context=self.ssl_context) as response:
                    return self._process_response(response)
            else:
                with urlopen(request, timeout=30) as response:
                    return self._process_response(response)
                    
        except HTTPError as e:
            # Handle rate limiting (429)
            if e.code == 429:
                retry_after = e.headers.get('Retry-After')
                if retry_after:
                    try:
                        wait_time = int(retry_after)
                    except (ValueError, TypeError):
                        # If Retry-After is not a valid integer, use exponential backoff
                        wait_time = self.initial_retry_delay * (2 ** retry_count)
                        logger.warning(f"Invalid Retry-After header: {retry_after}. Using exponential backoff: {wait_time}s")
                    else:
                        logger.warning(f"Rate limited (429). Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                else:
                    # Exponential backoff
                    wait_time = self.initial_retry_delay * (2 ** retry_count)
                    logger.warning(f"Rate limited (429). Using exponential backoff: {wait_time}s")
                    time.sleep(wait_time)
                
                if retry_count < self.max_retries:
                    return self._make_request(endpoint, params, retry_count + 1)
                else:
                    logger.error(f"Max retries exceeded for rate limiting on {url}")
                    return None
            
            # Handle server errors (5xx) with retry
            elif 500 <= e.code < 600:
                if retry_count < self.max_retries:
                    wait_time = self.initial_retry_delay * (2 ** retry_count)
                    logger.warning(f"Server error {e.code}. Retrying in {wait_time}s... (attempt {retry_count + 1}/{self.max_retries})")
                    time.sleep(wait_time)
                    return self._make_request(endpoint, params, retry_count + 1)
                else:
                    logger.error(f"HTTP Error {e.code}: {e.reason} for {url} after {self.max_retries} retries")
                    return None
            else:
                logger.error(f"HTTP Error {e.code}: {e.reason} for {url}")
                return None
                
        except URLError as e:
            # Handle timeout and connection errors with retry
            if retry_count < self.max_retries:
                wait_time = self.initial_retry_delay * (2 ** retry_count)
                logger.warning(f"URL Error: {e.reason}. Retrying in {wait_time}s... (attempt {retry_count + 1}/{self.max_retries})")
                time.sleep(wait_time)
                return self._make_request(endpoint, params, retry_count + 1)
            else:
                logger.error(f"URL Error: {e.reason} for {url} after {self.max_retries} retries")
                return None
                
        except Exception as e:
            logger.error(f"Error making request to {url}: {e}")
            return None
    
    def _process_response(self, response):
        """Process HTTP response and extract data and headers"""
        try:
            data = response.read().decode('utf-8')
            parsed_data = json.loads(data)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            return None
        except Exception as e:
            logger.error(f"Error processing response: {e}")
            return None
        
        # Extract pagination info from headers
        headers = response.headers
        return {
            'data': parsed_data,
            'next_page': headers.get('X-Next-Page'),
            'total_pages': headers.get('X-Total-Pages'),
            'total': headers.get('X-Total')
        }
    
    def _make_paginated_request(self, endpoint, params=None, max_pages=None):
        """Make paginated requests, following X-Next-Page until exhausted"""
        if params is None:
            params = {}
        
        # Set per_page in params
        params['per_page'] = self.per_page
        
        all_items = []
        page = 1
        
        while True:
            params['page'] = page
            logger.debug(f"Fetching {endpoint} page {page}")
            
            result = self._make_request(endpoint, params)
            if result is None:
                logger.error(f"Failed to fetch {endpoint} page {page}")
                return None
            
            data = result.get('data')
            if not data:
                break
            
            all_items.extend(data)
            logger.info(f"Fetched page {page} of {endpoint}: {len(data)} items (total so far: {len(all_items)})")
            
            # Check if there's a next page
            next_page = result.get('next_page')
            if not next_page:
                break
            
            # Check if we've hit max pages limit
            if max_pages and page >= max_pages:
                logger.info(f"Reached max pages limit ({max_pages}) for {endpoint}")
                break
            
            page += 1
        
        logger.info(f"Completed fetching {endpoint}: {len(all_items)} total items across {page} pages")
        return all_items
    
    def get_projects(self, per_page=None):
        """Get list of projects with pagination support"""
        if per_page:
            # For backward compatibility, use single page request
            result = self._make_request('projects', {'per_page': per_page, 'membership': 'true'})
            if result is None:
                return None
            return result.get('data', None)
        else:
            # Full pagination for all projects
            return self._make_paginated_request('projects', {'membership': 'true'})
    
    def get_group_projects(self, group_id):
        """Get all projects in a group with pagination"""
        return self._make_paginated_request(f'groups/{group_id}/projects')
    
    def get_project(self, project_id):
        """Get single project details"""
        result = self._make_request(f'projects/{project_id}')
        if result is None:
            return None
        return result.get('data', None)
    
    def get_pipelines(self, project_id, per_page=None):
        """Get pipelines for a project with pagination"""
        if per_page:
            # For backward compatibility, use single page request
            result = self._make_request(f'projects/{project_id}/pipelines', {'per_page': per_page})
            if result is None:
                return None
            return result.get('data', None)
        else:
            # Full pagination for all pipelines
            return self._make_paginated_request(f'projects/{project_id}/pipelines')
    
    def get_all_pipelines(self, per_page=20):
        """Get recent pipelines across all projects
        
        Note: To optimize API calls, we fetch from a limited number of projects.
        We retrieve pipelines from up to 10 projects, requesting enough per project
        to meet the per_page requirement.
        """
        # Always fetch from a reasonable number of projects (5-10) for good distribution
        # Scale based on request size but maintain reasonable bounds
        num_projects = min(10, max(5, per_page // 5))
        projects = self.get_projects(per_page=num_projects)
        if projects is None:
            return None  # Propagate API failure
        if not projects:
            return []  # No projects available (valid empty state)
        
        # Calculate how many pipelines to fetch per project
        # Fetch extra to account for projects with fewer pipelines
        # Protected from division by zero since we've confirmed projects is not empty
        pipelines_per_project = max(5, (per_page // len(projects)) + 2)
        
        all_pipelines = []
        for project in projects:
            pipelines = self.get_pipelines(project['id'], per_page=pipelines_per_project)
            if pipelines is None:
                # Propagate API failure from per-project pipeline fetch
                return None
            if pipelines:
                for pipeline in pipelines:
                    pipeline['project_name'] = project['name']
                    pipeline['project_id'] = project['id']
                    pipeline['project_path'] = project.get('path_with_namespace', '')
                    all_pipelines.append(pipeline)
        
        # Sort by created_at descending
        all_pipelines.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        return all_pipelines[:per_page]


class DataCache:
    """Thread-safe in-memory cache with TTL"""
    
    def __init__(self, ttl_seconds=300):
        self.cache = {}
        self.ttl = ttl_seconds
        self.lock = threading.Lock()
    
    def get(self, key):
        """Get value from cache if not expired"""
        with self.lock:
            if key in self.cache:
                value, timestamp = self.cache[key]
                if datetime.now() - timestamp < timedelta(seconds=self.ttl):
                    logger.debug(f"Cache hit: {key}")
                    return value
                else:
                    logger.debug(f"Cache expired: {key}")
                    del self.cache[key]
            return None
    
    def set(self, key, value):
        """Set value in cache"""
        with self.lock:
            self.cache[key] = (value, datetime.now())
            logger.debug(f"Cache set: {key}")
    
    def clear(self):
        """Clear all cache"""
        with self.lock:
            self.cache.clear()
            logger.info("Cache cleared")


# Global STATE for thread-safe data access
STATE = {
    'data': {},
    'last_updated': None,
    'status': 'INITIALIZING',
    'error': None
}
STATE_LOCK = threading.Lock()


def update_state(key, value):
    """Thread-safe update of global STATE (single key)
    
    Note: For atomic updates of multiple keys, use update_state_atomic() instead
    """
    with STATE_LOCK:
        STATE['data'][key] = value
        STATE['last_updated'] = datetime.now()
        STATE['status'] = 'ONLINE'
        STATE['error'] = None


def update_state_atomic(updates):
    """Thread-safe atomic update of multiple STATE keys with single timestamp
    
    Args:
        updates: dict mapping keys to values (e.g., {'projects': [...], 'pipelines': [...]})
    """
    with STATE_LOCK:
        for key, value in updates.items():
            STATE['data'][key] = value
        STATE['last_updated'] = datetime.now()
        STATE['status'] = 'ONLINE'
        STATE['error'] = None


def get_state(key):
    """Thread-safe read of global STATE"""
    with STATE_LOCK:
        return STATE['data'].get(key)


def get_state_status():
    """Thread-safe read of STATE status"""
    with STATE_LOCK:
        return {
            'status': STATE['status'],
            'last_updated': STATE['last_updated'],
            'error': STATE['error']
        }


def set_state_error(error):
    """Thread-safe update of STATE error"""
    with STATE_LOCK:
        STATE['status'] = 'ERROR'
        STATE['error'] = str(error)


class BackgroundPoller(threading.Thread):
    """Background thread that polls GitLab API and updates global STATE"""
    
    def __init__(self, gitlab_client, poll_interval_sec, group_ids=None, project_ids=None):
        super().__init__(daemon=True)
        self.gitlab_client = gitlab_client
        self.poll_interval = poll_interval_sec
        self.group_ids = group_ids or []
        self.project_ids = project_ids or []
        self.running = True
        self.stop_event = threading.Event()
        
    def run(self):
        """Main polling loop"""
        logger.info("Background poller started")
        
        while self.running:
            try:
                self.poll_data()
            except Exception as e:
                logger.error(f"Error in background poller: {e}")
                set_state_error(e)
            
            # Sleep for poll interval with interruptible wait
            logger.debug(f"Sleeping for {self.poll_interval}s before next poll")
            if self.stop_event.wait(timeout=self.poll_interval):
                # Event was set, exit loop
                break
    
    def poll_data(self):
        """Poll GitLab API and update STATE"""
        logger.info("Starting data poll...")
        
        # Fetch projects and pipelines FIRST (don't update STATE yet)
        projects = self._fetch_projects()
        if projects is None:
            logger.error("Failed to fetch projects - API error")
            # Set error state so health endpoint reflects the failure
            set_state_error("Failed to fetch data from GitLab API")
            logger.error("Data poll completed with failures - state marked as ERROR")
            return
        
        # Fetch pipelines (pass projects to respect configured scope)
        pipelines = self._fetch_pipelines(projects)
        if pipelines is None:
            logger.error("Failed to fetch pipelines - API error")
            # Set error state so health endpoint reflects the failure
            set_state_error("Failed to fetch data from GitLab API")
            logger.error("Data poll completed with failures - state marked as ERROR")
            return
        
        # Enrich projects with pipeline health data
        enriched_projects = self._enrich_projects_with_pipelines(projects, pipelines)
        
        # Both fetches succeeded - calculate summary and update STATE atomically
        summary = self._calculate_summary(enriched_projects, pipelines)
        
        # Update all keys atomically with single timestamp and status
        update_state_atomic({
            'projects': enriched_projects,
            'pipelines': pipelines,
            'summary': summary
        })
        
        logger.info(f"Updated STATE atomically: {len(enriched_projects)} projects, {len(pipelines)} pipelines")
        logger.info("Data poll completed successfully")
    
    def _fetch_projects(self):
        """Fetch projects from configured sources
        
        Returns:
            list: List of projects (may be empty if no projects found)
            None: Only if API error occurred and NO projects were fetched
        """
        all_projects = []
        api_errors = 0
        
        # Fetch from specific project IDs if configured
        if self.project_ids:
            logger.info(f"Fetching {len(self.project_ids)} specific projects")
            for project_id in self.project_ids:
                project = self.gitlab_client.get_project(project_id)
                if project is None:
                    # API error occurred
                    api_errors += 1
                    logger.warning(f"Failed to fetch project {project_id}")
                else:
                    # Non-None means successful API call, add the project
                    all_projects.append(project)
        
        # Fetch from groups if configured
        if self.group_ids:
            logger.info(f"Fetching projects from {len(self.group_ids)} groups")
            for group_id in self.group_ids:
                logger.info(f"Fetching projects for group {group_id}")
                group_projects = self.gitlab_client.get_group_projects(group_id)
                if group_projects is None:
                    # API error occurred
                    api_errors += 1
                    logger.warning(f"Failed to fetch projects for group {group_id}")
                elif group_projects:
                    # Non-empty list, extend our results
                    all_projects.extend(group_projects)
                    logger.info(f"Added {len(group_projects)} projects from group {group_id}")
                else:
                    # Empty list - group has no projects
                    logger.info(f"Group {group_id} has no projects")
        
        # If no specific sources configured, fetch all accessible projects
        if not self.project_ids and not self.group_ids:
            logger.info("Fetching all accessible projects")
            projects = self.gitlab_client.get_projects()
            if projects is None:
                # API error occurred
                api_errors += 1
                logger.error("Failed to fetch all accessible projects")
            elif projects:
                # Non-empty list, use it as our results
                all_projects = projects
        
        # Deduplicate projects by ID (project may appear in multiple groups)
        if all_projects:
            seen_ids = set()
            unique_projects = []
            duplicates = 0
            for project in all_projects:
                project_id = project.get('id')
                if project_id not in seen_ids:
                    seen_ids.add(project_id)
                    unique_projects.append(project)
                else:
                    duplicates += 1
            
            if duplicates > 0:
                logger.info(f"Deduplicated {duplicates} duplicate projects (found in multiple groups/sources)")
            
            all_projects = unique_projects
        
        # Handle partial failures
        if api_errors > 0:
            if all_projects:
                logger.warning(f"Partial project fetch: {api_errors} sources failed, but got {len(all_projects)} projects from others")
            else:
                logger.error("All project fetches failed")
                return None
        
        if not all_projects:
            logger.info("No projects found (this may be expected for configured groups/IDs)")
        
        return all_projects
    
    def _fetch_pipelines(self, projects):
        """Fetch pipelines for configured projects
        
        Args:
            projects: List of project dicts from _fetch_projects(). 
                     None means API error occurred.
                     Empty list means no projects found in configured scope.
        
        Returns:
            list: List of pipelines (may be empty if no pipelines found)
            None: Only if API error occurred
        """
        # Check if we have a configured scope (group_ids or project_ids set)
        has_configured_scope = bool(self.group_ids or self.project_ids)
        
        # If we have a configured scope, only fetch from those projects
        if has_configured_scope:
            # projects is None means API error
            if projects is None:
                logger.error("Cannot fetch pipelines: project fetch failed")
                return None
            
            # projects is empty list means configured scope has no projects
            if not projects:
                logger.info("No projects in configured scope, returning empty pipelines")
                return []
            
            logger.info(f"Fetching pipelines for {len(projects)} configured projects")
            all_pipelines = []
            api_errors = 0
            
            # Limit to reasonable number of projects to avoid too many API calls
            projects_to_check = projects[:MAX_PROJECTS_FOR_PIPELINES]
            
            for project in projects_to_check:
                project_id = project.get('id')
                project_name = project.get('name', f'Project {project_id}')
                project_path = project.get('path_with_namespace', '')
                
                # Fetch recent pipelines for this project
                pipelines = self.gitlab_client.get_pipelines(project_id, per_page=PIPELINES_PER_PROJECT)
                
                if pipelines is None:
                    # API error occurred
                    logger.warning(f"Failed to fetch pipelines for project {project_name} (ID: {project_id})")
                    api_errors += 1
                elif pipelines:
                    # Add project info to each pipeline
                    for pipeline in pipelines:
                        pipeline['project_name'] = project_name
                        pipeline['project_id'] = project_id
                        pipeline['project_path'] = project_path
                        all_pipelines.append(pipeline)
            
            # Handle partial failures
            if api_errors > 0:
                if all_pipelines:
                    logger.warning(f"Partial pipeline fetch: {api_errors} projects failed, but got {len(all_pipelines)} pipelines from others")
                else:
                    logger.error("All pipeline fetches failed")
                    return None
            
            # Sort by created_at descending and limit to max
            # ISO 8601 string sorting works correctly; empty values sort to bottom
            all_pipelines.sort(key=lambda x: x.get('created_at') or '', reverse=True)
            result = all_pipelines[:MAX_TOTAL_PIPELINES]
            
            if not result:
                logger.info("No pipelines found in configured projects")
            
            return result
        else:
            # No scope configured: fallback to arbitrary membership sample
            logger.info("No scope configured, using membership sample for pipelines")
            pipelines = self.gitlab_client.get_all_pipelines(per_page=MAX_TOTAL_PIPELINES)
            
            # Return None for API errors, empty list is valid
            if pipelines is None:
                return None
            
            if not pipelines:
                logger.info("No pipelines found")
            
            return pipelines
    
    def _enrich_projects_with_pipelines(self, projects, pipelines):
        """Enrich project data with pipeline health metrics
        
        Args:
            projects: List of project dicts
            pipelines: List of all pipeline dicts (with project_id attached)
        
        Returns:
            List of enriched project dicts with pipeline health data
        """
        if not projects:
            return []
        
        # Build a map of project_id -> list of pipelines for that project
        project_pipelines = {}
        for pipeline in pipelines:
            project_id = pipeline.get('project_id')
            if project_id:
                if project_id not in project_pipelines:
                    project_pipelines[project_id] = []
                project_pipelines[project_id].append(pipeline)
        
        # Sort pipelines by created_at for each project (newest first)
        # ISO 8601 timestamps sort correctly lexicographically
        for project_id in project_pipelines:
            project_pipelines[project_id].sort(
                key=lambda p: p.get('created_at') or EPOCH_TIMESTAMP, 
                reverse=True
            )
        
        # Enrich each project with pipeline data
        enriched_projects = []
        for project in projects:
            project_id = project.get('id')
            enriched = dict(project)  # Create a copy
            
            # Get pipelines for this project
            pipelines_for_project = project_pipelines.get(project_id, [])
            
            if pipelines_for_project:
                # Last pipeline info
                last_pipeline = pipelines_for_project[0]
                enriched['last_pipeline_status'] = last_pipeline.get('status')
                enriched['last_pipeline_ref'] = last_pipeline.get('ref')
                enriched['last_pipeline_duration'] = last_pipeline.get('duration')
                enriched['last_pipeline_updated_at'] = last_pipeline.get('updated_at')
                
                # Calculate recent success rate (last 10 pipelines)
                recent_pipelines = pipelines_for_project[:10]
                success_count = sum(1 for p in recent_pipelines if p.get('status') == 'success')
                enriched['recent_success_rate'] = success_count / len(recent_pipelines)
                
                # Calculate consecutive failures on default branch
                default_branch = project.get('default_branch', DEFAULT_BRANCH_NAME)
                consecutive_failures = 0
                for pipeline in pipelines_for_project:
                    if pipeline.get('ref') == default_branch:
                        if pipeline.get('status') == 'failed':
                            consecutive_failures += 1
                        else:
                            # Stop counting at first non-failure
                            break
                enriched['consecutive_default_branch_failures'] = consecutive_failures
            else:
                # No pipelines for this project
                enriched['last_pipeline_status'] = None
                enriched['last_pipeline_ref'] = None
                enriched['last_pipeline_duration'] = None
                enriched['last_pipeline_updated_at'] = None
                enriched['recent_success_rate'] = None
                enriched['consecutive_default_branch_failures'] = 0
            
            enriched_projects.append(enriched)
        
        return enriched_projects
    
    def _calculate_summary(self, projects, pipelines):
        """Calculate summary statistics
        
        Note: This should only be called when both projects and pipelines
        were successfully fetched (not None). The caller is responsible for
        ensuring valid data.
        
        Returns summary dict without timestamp (caller adds it from STATE).
        """
        # Use empty lists if None (should not happen in normal flow)
        if projects is None:
            logger.warning("_calculate_summary called with None projects - using empty list")
            projects = []
        if pipelines is None:
            logger.warning("_calculate_summary called with None pipelines - using empty list")
            pipelines = []
        
        total_repos = len(projects)
        active_repos = len([p for p in projects if p.get('last_activity_at')])
        
        # Pipeline statistics
        pipeline_statuses = {}
        for pipeline in pipelines:
            status = pipeline.get('status', 'unknown')
            pipeline_statuses[status] = pipeline_statuses.get(status, 0) + 1
        
        # Calculate success rate
        total_pipelines = len(pipelines)
        successful_pipelines = pipeline_statuses.get('success', 0)
        pipeline_success_rate = successful_pipelines / total_pipelines if total_pipelines > 0 else 0.0
        
        return {
            'total_repositories': total_repos,
            'active_repositories': active_repos,
            'total_pipelines': total_pipelines,
            'successful_pipelines': successful_pipelines,
            'failed_pipelines': pipeline_statuses.get('failed', 0),
            'running_pipelines': pipeline_statuses.get('running', 0),
            'pending_pipelines': pipeline_statuses.get('pending', 0),
            'pipeline_success_rate': pipeline_success_rate,
            'pipeline_statuses': pipeline_statuses
        }
    
    def stop(self):
        """Stop the polling thread"""
        logger.info("Stopping background poller")
        self.running = False
        self.stop_event.set()  # Wake up the thread if it's sleeping


class DashboardRequestHandler(SimpleHTTPRequestHandler):
    """Custom HTTP request handler for the dashboard"""
    
    def __init__(self, *args, **kwargs):
        # Set the directory to serve static files from
        super().__init__(*args, directory='frontend', **kwargs)
    
    def do_GET(self):
        """Handle GET requests"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        # API endpoints
        if path == '/api/summary':
            self.handle_summary()
        elif path == '/api/repos':
            self.handle_repos()
        elif path == '/api/pipelines':
            self.handle_pipelines()
        elif path == '/api/health':
            self.handle_health()
        else:
            # Serve static files
            super().do_GET()
    
    def handle_summary(self):
        """Handle /api/summary endpoint"""
        try:
            summary = get_state('summary')
            status_info = get_state_status()
            
            if summary is None:
                # If no data yet, return initializing or error status
                if status_info['status'] == 'INITIALIZING':
                    self.send_json_response({
                        'status': 'initializing',
                        'message': 'Dashboard is initializing, please wait...'
                    }, status=503)
                else:
                    # Summary is None means API error during polling
                    self.send_json_response({'error': 'Failed to fetch data from GitLab API'}, status=502)
                return
            
            # Check if backend is in ERROR state (stale data)
            if status_info['status'] == 'ERROR':
                last_updated = status_info['last_updated'].isoformat() if isinstance(status_info['last_updated'], datetime) else str(status_info['last_updated']) if status_info['last_updated'] else None
                self.send_json_response({
                    'error': 'Backend is currently in ERROR state - GitLab API unavailable',
                    'last_successful_poll': last_updated,
                    'status': 'ERROR'
                }, status=503)
                return
            
            # Add timestamp from STATE to summary
            response = dict(summary)
            last_updated_iso = status_info['last_updated'].isoformat() if isinstance(status_info['last_updated'], datetime) else str(status_info['last_updated']) if status_info['last_updated'] else None
            response['last_updated'] = last_updated_iso
            response['last_updated_iso'] = last_updated_iso  # Explicit field as requested in requirements
            
            self.send_json_response(response)
            
        except Exception as e:
            logger.error(f"Error in handle_summary: {e}")
            self.send_json_response({'error': str(e)}, status=500)
    
    def handle_repos(self):
        """Handle /api/repos endpoint"""
        try:
            projects = get_state('projects')
            status_info = get_state_status()
            
            if projects is None:
                if status_info['status'] == 'INITIALIZING':
                    self.send_json_response({
                        'status': 'initializing',
                        'message': 'Dashboard is initializing, please wait...'
                    }, status=503)
                else:
                    # Projects is None means API error, not empty results
                    self.send_json_response({'error': 'Failed to fetch projects from GitLab API'}, status=502)
                return
            
            # Check if backend is in ERROR state (stale data)
            if status_info['status'] == 'ERROR':
                last_updated = status_info['last_updated'].isoformat() if isinstance(status_info['last_updated'], datetime) else str(status_info['last_updated']) if status_info['last_updated'] else None
                self.send_json_response({
                    'error': 'Backend is currently in ERROR state - GitLab API unavailable',
                    'last_successful_poll': last_updated,
                    'status': 'ERROR'
                }, status=503)
                return
            
            # Format repository data (projects can be empty list, which is valid)
            repos = []
            for project in projects:
                repo = {
                    'id': project.get('id'),
                    'name': project.get('name'),
                    'path_with_namespace': project.get('path_with_namespace'),
                    'description': project.get('description', ''),
                    'web_url': project.get('web_url'),
                    'last_activity_at': project.get('last_activity_at'),
                    'star_count': project.get('star_count', 0),
                    'forks_count': project.get('forks_count', 0),
                    'open_issues_count': project.get('open_issues_count', 0),
                    'default_branch': project.get('default_branch', 'main'),
                    'visibility': project.get('visibility', 'private'),
                    # Pipeline health metrics
                    'last_pipeline_status': project.get('last_pipeline_status'),
                    'last_pipeline_ref': project.get('last_pipeline_ref'),
                    'last_pipeline_duration': project.get('last_pipeline_duration'),
                    'last_pipeline_updated_at': project.get('last_pipeline_updated_at'),
                    'recent_success_rate': project.get('recent_success_rate'),
                    'consecutive_default_branch_failures': project.get('consecutive_default_branch_failures', 0)
                }
                repos.append(repo)
            
            response = {
                'repositories': repos,
                'total': len(repos),
                'last_updated': status_info['last_updated'].isoformat() if isinstance(status_info['last_updated'], datetime) else str(status_info['last_updated']) if status_info['last_updated'] else None
            }
            
            self.send_json_response(response)
            
        except Exception as e:
            logger.error(f"Error in handle_repos: {e}")
            self.send_json_response({'error': str(e)}, status=500)
    
    def handle_pipelines(self):
        """Handle /api/pipelines endpoint"""
        try:
            pipelines = get_state('pipelines')
            projects = get_state('projects')
            status_info = get_state_status()
            
            if pipelines is None:
                if status_info['status'] == 'INITIALIZING':
                    self.send_json_response({
                        'status': 'initializing',
                        'message': 'Dashboard is initializing, please wait...'
                    }, status=503)
                else:
                    # Pipelines is None means API error, not empty results
                    self.send_json_response({'error': 'Failed to fetch pipelines from GitLab API'}, status=502)
                return
            
            # Check if backend is in ERROR state (stale data)
            if status_info['status'] == 'ERROR':
                last_updated = status_info['last_updated'].isoformat() if isinstance(status_info['last_updated'], datetime) else str(status_info['last_updated']) if status_info['last_updated'] else None
                self.send_json_response({
                    'error': 'Backend is currently in ERROR state - GitLab API unavailable',
                    'last_successful_poll': last_updated,
                    'status': 'ERROR'
                }, status=503)
                return
            
            # Parse query parameters
            parsed_path = urlparse(self.path)
            query_params = parse_qs(parsed_path.query)
            
            # Get query parameter values (parse_qs returns lists)
            try:
                limit = int(query_params.get('limit', [str(DEFAULT_PIPELINE_LIMIT)])[0])
                if limit < 1:
                    raise ValueError("limit must be a positive integer (>= 1)")
                if limit > MAX_PIPELINE_LIMIT:
                    raise ValueError(f"limit must not exceed {MAX_PIPELINE_LIMIT}")
            except (ValueError, IndexError) as e:
                logger.error(f"Invalid limit parameter: {e}")
                self.send_json_response({'error': f'Invalid limit parameter: {str(e)}'}, status=400)
                return
            
            # Get optional filter parameters
            status_filter = query_params.get('status', [None])[0] if query_params.get('status') else None
            ref_filter = query_params.get('ref', [None])[0] if query_params.get('ref') else None
            project_filter = query_params.get('project', [None])[0] if query_params.get('project') else None
            
            # Build project_id to path_with_namespace map
            project_path_map = {}
            if projects:
                for project in projects:
                    project_id = project.get('id')
                    path_with_namespace = project.get('path_with_namespace', '')
                    if project_id:
                        project_path_map[project_id] = path_with_namespace
            
            # Format and filter pipeline data
            filtered_pipelines = []
            for pipeline in pipelines:
                # Apply filters
                if status_filter and pipeline.get('status') != status_filter:
                    continue
                if ref_filter and pipeline.get('ref') != ref_filter:
                    continue
                
                project_name = pipeline.get('project_name', 'Unknown')
                project_id = pipeline.get('project_id')
                project_path = project_path_map.get(project_id, '')
                
                # Apply project filter (substring match on name or path)
                if project_filter:
                    project_filter_lower = project_filter.lower()
                    if (project_filter_lower not in project_name.lower() and 
                        project_filter_lower not in project_path.lower()):
                        continue
                
                formatted = {
                    'id': pipeline.get('id'),
                    'project_id': project_id,
                    'project_name': project_name,
                    'project_path': project_path,
                    'status': pipeline.get('status'),
                    'ref': pipeline.get('ref'),
                    'sha': (pipeline.get('sha') or '')[:8],  # Short SHA (safe slicing)
                    'web_url': pipeline.get('web_url'),
                    'created_at': pipeline.get('created_at'),
                    'updated_at': pipeline.get('updated_at'),
                    'duration': pipeline.get('duration')
                }
                filtered_pipelines.append(formatted)
            
            # Apply limit
            limited_pipelines = filtered_pipelines[:limit]
            
            response = {
                'pipelines': limited_pipelines,
                'total': len(limited_pipelines),
                'total_before_limit': len(filtered_pipelines),  # For pagination context
                'last_updated': status_info['last_updated'].isoformat() if isinstance(status_info['last_updated'], datetime) else str(status_info['last_updated']) if status_info['last_updated'] else None
            }
            
            self.send_json_response(response)
            
        except Exception as e:
            logger.error(f"Error in handle_pipelines: {e}")
            self.send_json_response({'error': str(e)}, status=500)
    
    def handle_health(self):
        """Handle /api/health endpoint"""
        try:
            status_info = get_state_status()
            
            # Safe handling of last_updated
            last_poll = None
            if status_info['last_updated']:
                if isinstance(status_info['last_updated'], datetime):
                    last_poll = status_info['last_updated'].isoformat()
                else:
                    last_poll = str(status_info['last_updated'])
            
            # Determine health status
            # ONLINE = healthy (working connection to GitLab)
            # INITIALIZING = not ready (no successful GitLab connection yet)
            # ERROR = unhealthy (GitLab connection failed)
            is_healthy = status_info['status'] == 'ONLINE'
            
            health = {
                'status': 'healthy' if is_healthy else 'unhealthy',
                'backend_status': status_info['status'],
                'timestamp': datetime.now().isoformat(),
                'last_poll': last_poll,
                'error': status_info['error']
            }
            
            # Return 200 OK only for ONLINE (proven GitLab connectivity)
            # Return 503 for INITIALIZING (not ready) and ERROR (failed)
            status_code = 200 if is_healthy else 503
            self.send_json_response(health, status=status_code)
            
        except Exception as e:
            logger.error(f"Error in handle_health: {e}")
            health = {
                'status': 'unhealthy',
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }
            self.send_json_response(health, status=503)
    
    def send_json_response(self, data, status=200):
        """Send JSON response"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode('utf-8'))
    
    def log_message(self, format, *args):
        """Override to use logger"""
        logger.info("%s - - [%s] %s" % (
            self.address_string(),
            self.log_date_time_string(),
            format % args
        ))


class DashboardServer(HTTPServer):
    """Custom HTTP server with GitLab client"""
    
    def __init__(self, server_address, RequestHandlerClass, gitlab_client):
        super().__init__(server_address, RequestHandlerClass)
        self.gitlab_client = gitlab_client


def parse_int_config(value, default, name):
    """Parse integer configuration value with error handling"""
    try:
        return int(value)
    except (ValueError, TypeError):
        logger.warning(f"Invalid {name} value: {value}. Using default: {default}")
        return default


def parse_csv_list(value):
    """Parse comma-separated list from environment variable"""
    if not value:
        return []
    return [item.strip() for item in value.split(',') if item.strip()]


def load_config():
    """Load configuration from config.json or environment variables"""
    config = {}
    config_source = "environment variables"
    
    # Try to load from config.json first
    config_file = 'config.json'
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            config_source = "config.json"
            logger.info(f"Configuration loaded from {config_file}")
        except Exception as e:
            logger.warning(f"Failed to load {config_file}: {e}. Falling back to environment variables.")
            config = {}
    
    # Environment variables take precedence over config.json
    config['gitlab_url'] = os.environ.get('GITLAB_URL', config.get('gitlab_url', 'https://gitlab.com'))
    config['api_token'] = os.environ.get('GITLAB_API_TOKEN', config.get('api_token', ''))
    
    # For group_ids and project_ids, check if env var is explicitly set (even if empty)
    # to allow overriding config.json with empty scope
    if 'GITLAB_GROUP_IDS' in os.environ:
        config['group_ids'] = parse_csv_list(os.environ['GITLAB_GROUP_IDS'])
    else:
        config['group_ids'] = config.get('group_ids', [])
    
    if 'GITLAB_PROJECT_IDS' in os.environ:
        config['project_ids'] = parse_csv_list(os.environ['GITLAB_PROJECT_IDS'])
    else:
        config['project_ids'] = config.get('project_ids', [])
    
    config['port'] = parse_int_config(os.environ.get('PORT'), config.get('port', 8080), 'PORT')
    config['cache_ttl_sec'] = parse_int_config(os.environ.get('CACHE_TTL'), config.get('cache_ttl_sec', 300), 'CACHE_TTL')
    config['poll_interval_sec'] = parse_int_config(os.environ.get('POLL_INTERVAL'), config.get('poll_interval_sec', 60), 'POLL_INTERVAL')
    config['per_page'] = parse_int_config(os.environ.get('PER_PAGE'), config.get('per_page', 100), 'PER_PAGE')
    
    # For insecure_skip_verify, check if env var is explicitly set to allow overriding
    if 'INSECURE_SKIP_VERIFY' in os.environ:
        config['insecure_skip_verify'] = os.environ['INSECURE_SKIP_VERIFY'].lower() in ['true', '1', 'yes']
    else:
        config['insecure_skip_verify'] = config.get('insecure_skip_verify', False)
    
    # Ensure lists are clean (filter config.json values that might have empty strings or numeric IDs)
    if isinstance(config['group_ids'], list):
        config['group_ids'] = [str(gid).strip() for gid in config['group_ids'] if gid and str(gid).strip()]
    if isinstance(config['project_ids'], list):
        config['project_ids'] = [str(pid).strip() for pid in config['project_ids'] if pid and str(pid).strip()]
    
    # Validate required fields
    if not config['api_token']:
        logger.warning("GITLAB_API_TOKEN not set. API requests will fail.")
        logger.warning("Set GITLAB_API_TOKEN environment variable or add 'api_token' to config.json")
    
    # Log configuration (without secrets)
    logger.info(f"Configuration loaded from: {config_source}")
    logger.info(f"  GitLab URL: {config['gitlab_url']}")
    logger.info(f"  Port: {config['port']}")
    logger.info(f"  Poll interval: {config['poll_interval_sec']}s")
    logger.info(f"  Cache TTL: {config['cache_ttl_sec']}s")
    logger.info(f"  Per page: {config['per_page']}")
    logger.info(f"  Group IDs: {config['group_ids'] if config['group_ids'] else 'None (using all accessible projects)'}")
    logger.info(f"  Project IDs: {config['project_ids'] if config['project_ids'] else 'None'}")
    logger.info(f"  Insecure skip verify: {config['insecure_skip_verify']}")
    logger.info(f"  API token: {'***' if config['api_token'] else 'NOT SET'}")
    
    return config


def main():
    """Main entry point"""
    logger.info("Starting GitLab Dashboard Server...")
    
    # Load configuration
    config = load_config()
    
    # Initialize GitLab client
    gitlab_client = GitLabAPIClient(
        config['gitlab_url'], 
        config['api_token'],
        per_page=config['per_page'],
        insecure_skip_verify=config['insecure_skip_verify']
    )
    
    # Start background poller
    poller = BackgroundPoller(
        gitlab_client,
        config['poll_interval_sec'],
        group_ids=config['group_ids'],
        project_ids=config['project_ids']
    )
    poller.start()
    logger.info(f"Background poller started (interval: {config['poll_interval_sec']}s)")
    
    # Create server
    server_address = ('', config['port'])
    httpd = DashboardServer(server_address, DashboardRequestHandler, gitlab_client)
    
    logger.info(f"Server running at http://localhost:{config['port']}/")
    logger.info("Press Ctrl+C to stop the server")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("\nShutting down server...")
        poller.stop()
        poller.join(timeout=5)  # Wait for poller thread to finish
        if poller.is_alive():
            logger.warning("Poller thread did not stop cleanly")
        httpd.shutdown()
        logger.info("Server stopped.")


if __name__ == '__main__':
    main()

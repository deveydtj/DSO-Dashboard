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
from urllib.parse import urlparse, parse_qs, urlencode, unquote
import logging

# Valid log level names (case-insensitive)
VALID_LOG_LEVELS = ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')


def get_log_level():
    """Get log level from environment variable LOG_LEVEL
    
    Returns:
        int: Logging level constant (e.g., logging.INFO)
        
    Environment Variables:
        LOG_LEVEL: One of DEBUG, INFO, WARNING, ERROR, CRITICAL (case-insensitive)
                   Defaults to INFO if not set or invalid
    """
    level_str = os.environ.get('LOG_LEVEL', 'INFO').upper()
    if level_str not in VALID_LOG_LEVELS:
        # Fall back to INFO for invalid values
        return logging.INFO
    return getattr(logging, level_str)


def configure_logging():
    """Configure logging with level from environment
    
    Returns:
        str: The configured log level name (e.g., 'INFO')
    """
    level = get_log_level()
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLevelName(level)


# Configure logging at module load (can be reconfigured in main())
_configured_level = configure_logging()
logger = logging.getLogger(__name__)

# Pipeline fetching configuration constants
MAX_PROJECTS_FOR_PIPELINES = 20  # Max projects to fetch pipelines from
PIPELINES_PER_PROJECT = 10       # Pipelines to fetch per project
MAX_TOTAL_PIPELINES = 50         # Default max for /api/pipelines response (deprecated in storage)

# API query parameter constants
DEFAULT_PIPELINE_LIMIT = 50      # Default limit for /api/pipelines endpoint
MAX_PIPELINE_LIMIT = 1000        # Maximum limit for /api/pipelines endpoint

# Timestamp fallback constants
EPOCH_TIMESTAMP = '1970-01-01T00:00:00Z'  # Fallback for missing timestamps

# Default branch constant
DEFAULT_BRANCH_NAME = 'main'     # Default branch name fallback

# Pipeline statuses to ignore when calculating consecutive failures and success rates
# These statuses represent pipelines that didn't actually test the code
IGNORED_PIPELINE_STATUSES = ('skipped', 'manual', 'canceled', 'cancelled')

# Default summary structure for empty/error states
DEFAULT_SUMMARY = {
    'total_repositories': 0,
    'active_repositories': 0,
    'total_pipelines': 0,
    'successful_pipelines': 0,
    'failed_pipelines': 0,
    'running_pipelines': 0,
    'pending_pipelines': 0,
    'pipeline_success_rate': 0.0,
    'pipeline_statuses': {}
}


class GitLabAPIClient:
    """GitLab API client using urllib with retry, rate limiting, and pagination support"""
    
    def __init__(self, gitlab_url, api_token, per_page=100, insecure_skip_verify=False, 
                 max_retries=3, initial_retry_delay=1.0, ca_bundle_path=None):
        self.gitlab_url = gitlab_url.rstrip('/')
        self.api_token = api_token
        self.base_url = f"{self.gitlab_url}/api/v4"
        self.per_page = per_page
        self.insecure_skip_verify = insecure_skip_verify
        self.ca_bundle_path = ca_bundle_path
        self.max_retries = max_retries
        self.initial_retry_delay = initial_retry_delay
        
        # Create SSL context based on configuration
        if self.ca_bundle_path:
            # Use custom CA bundle (preferred for internal GitLab)
            try:
                logger.info("=" * 70)
                logger.info("USING CUSTOM CA BUNDLE")
                logger.info(f"CA bundle path: {self.ca_bundle_path}")
                logger.info("=" * 70)
                self.ssl_context = ssl.create_default_context(cafile=self.ca_bundle_path)
            except FileNotFoundError:
                logger.error("=" * 70)
                logger.error(f"CA BUNDLE FILE NOT FOUND: {self.ca_bundle_path}")
                logger.error("Falling back to default SSL verification")
                logger.error("=" * 70)
                self.ssl_context = None
            except (ssl.SSLError, OSError, IOError) as e:
                logger.error("=" * 70)
                logger.error(f"FAILED TO LOAD CA BUNDLE: {self.ca_bundle_path}")
                logger.error(f"Error: {e}")
                logger.error("Falling back to default SSL verification")
                logger.error("=" * 70)
                self.ssl_context = None
        elif self.insecure_skip_verify:
            # Disable SSL verification (use only on trusted networks)
            self.ssl_context = ssl.create_default_context()
            self.ssl_context.check_hostname = False
            self.ssl_context.verify_mode = ssl.CERT_NONE
            logger.warning("=" * 70)
            logger.warning("SSL VERIFICATION DISABLED - SECURITY RISK")
            logger.warning("Using unverified SSL context for self-signed certificates")
            logger.warning("Only use this setting on trusted internal networks")
            logger.warning("=" * 70)
        else:
            # Use default SSL verification
            self.ssl_context = None
    
    def _mask_url(self, url):
        """Return URL for logging
        
        Currently returns URL unchanged since the API token is sent in headers,
        not in the URL query string. This helper is provided for consistency
        and potential future use if masking becomes necessary.
        """
        return url
    
    def gitlab_request(self, endpoint, params=None, retry_count=0):
        """Make a request to GitLab API with retry and rate limiting
        
        This is the central retry/backoff handler for all GitLab API calls.
        Handles:
        - Exponential backoff for transient errors (5xx, timeouts, connection resets)
        - Rate limiting (429) with Retry-After header support
        - Max retry attempts (default: 3)
        
        Args:
            endpoint: GitLab API endpoint path (e.g., 'projects', 'projects/123/pipelines')
            params: Optional query parameters dict
            retry_count: Current retry attempt (internal use)
        
        Returns:
            dict: Response with 'data', 'next_page', 'total_pages', 'total' keys
            None: If API error occurred after all retries
        """
        url = f"{self.base_url}/{endpoint}"
        
        if params:
            query_string = urlencode(params)
            url = f"{url}?{query_string}"
        
        headers = {
            'PRIVATE-TOKEN': self.api_token,
            'Content-Type': 'application/json'
        }
        
        # Record start time for timing
        start_time = time.monotonic()
        masked_url = self._mask_url(url)
        
        try:
            request = Request(url, headers=headers)
            
            # Open with SSL context if configured
            if self.ssl_context:
                with urlopen(request, timeout=30, context=self.ssl_context) as response:
                    result = self._process_response(response)
                    elapsed_ms = (time.monotonic() - start_time) * 1000
                    logger.debug(f"GET {endpoint} -> {response.status} in {elapsed_ms:.1f}ms url={masked_url}")
                    return result
            else:
                with urlopen(request, timeout=30) as response:
                    result = self._process_response(response)
                    elapsed_ms = (time.monotonic() - start_time) * 1000
                    logger.debug(f"GET {endpoint} -> {response.status} in {elapsed_ms:.1f}ms url={masked_url}")
                    return result
                    
        except HTTPError as e:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            
            # Handle rate limiting (429)
            if e.code == 429:
                retry_after = e.headers.get('Retry-After')
                if retry_after:
                    try:
                        wait_time = int(retry_after)
                    except (ValueError, TypeError):
                        # If Retry-After is not a valid integer, use exponential backoff
                        wait_time = self.initial_retry_delay * (2 ** retry_count)
                        logger.warning(f"GET {endpoint} -> 429 in {elapsed_ms:.1f}ms - Invalid Retry-After: {retry_after}. Using exponential backoff: {wait_time}s")
                    else:
                        logger.warning(f"GET {endpoint} -> 429 in {elapsed_ms:.1f}ms - Rate limited. Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                else:
                    # Exponential backoff
                    wait_time = self.initial_retry_delay * (2 ** retry_count)
                    logger.warning(f"GET {endpoint} -> 429 in {elapsed_ms:.1f}ms - Rate limited. Using exponential backoff: {wait_time}s")
                    time.sleep(wait_time)
                
                if retry_count < self.max_retries:
                    return self.gitlab_request(endpoint, params, retry_count + 1)
                else:
                    logger.error(f"GET {endpoint} -> 429 - Max retries exceeded in {elapsed_ms:.1f}ms url={masked_url}")
                    return None
            
            # Handle server errors (5xx) with retry
            elif 500 <= e.code < 600:
                if retry_count < self.max_retries:
                    wait_time = self.initial_retry_delay * (2 ** retry_count)
                    logger.warning(f"GET {endpoint} -> {e.code} in {elapsed_ms:.1f}ms - Retrying in {wait_time}s (attempt {retry_count + 1}/{self.max_retries})")
                    time.sleep(wait_time)
                    return self.gitlab_request(endpoint, params, retry_count + 1)
                else:
                    logger.error(f"GET {endpoint} -> {e.code} {e.reason} in {elapsed_ms:.1f}ms after {self.max_retries} retries url={masked_url}")
                    return None
            else:
                logger.error(f"GET {endpoint} -> {e.code} {e.reason} in {elapsed_ms:.1f}ms url={masked_url}")
                return None
                
        except URLError as e:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            # Handle timeout and connection errors with retry
            if retry_count < self.max_retries:
                wait_time = self.initial_retry_delay * (2 ** retry_count)
                logger.warning(f"GET {endpoint} -> URLError in {elapsed_ms:.1f}ms: {e.reason}. Retrying in {wait_time}s (attempt {retry_count + 1}/{self.max_retries})")
                time.sleep(wait_time)
                return self.gitlab_request(endpoint, params, retry_count + 1)
            else:
                logger.error(f"GET {endpoint} -> URLError in {elapsed_ms:.1f}ms: {e.reason} after {self.max_retries} retries url={masked_url}")
                return None
                
        except Exception as e:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            logger.error(f"GET {endpoint} -> Error in {elapsed_ms:.1f}ms: {e} url={masked_url}")
            return None
    
    def _parse_link_header(self, link_header):
        """Parse RFC 5988 Link header to extract next page URL
        
        Example Link header:
        <https://gitlab.com/api/v4/projects?page=2>; rel="next", <https://gitlab.com/api/v4/projects?page=5>; rel="last"
        
        Returns:
            str: Next page number or None
        """
        if not link_header:
            return None
        
        # Parse Link header for rel="next"
        for link in link_header.split(','):
            link = link.strip()
            # Check for rel="next" or rel='next' (case-insensitive, handle whitespace)
            if 'rel' in link.lower():
                # Split by semicolon to separate URL from rel parameter
                parts = link.split(';')
                if len(parts) < 2:
                    continue
                
                # Check if this is the "next" link
                rel_part = parts[1].strip().lower()
                if 'next' not in rel_part:
                    continue
                
                # Extract URL from <URL>
                url_part = parts[0].strip()
                if not url_part.startswith('<'):
                    continue
                
                # Find the first '>' to handle URLs with query params
                end_bracket = url_part.find('>')
                if end_bracket == -1:
                    continue
                
                url = url_part[1:end_bracket]
                
                # Extract page number from URL query params
                try:
                    parsed = urlparse(url)
                    query_params = parse_qs(parsed.query)
                    if 'page' in query_params and query_params['page']:
                        page_value = query_params['page'][0]
                        # Validate that page is numeric
                        if page_value.isdigit():
                            return page_value
                except Exception as e:
                    logger.debug(f"Failed to parse Link header URL: {e}")
                    continue
        
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
        
        # GitLab provides pagination via X-Next-Page header (preferred) or Link header (RFC 5988)
        next_page = headers.get('X-Next-Page')
        if not next_page:
            # Fallback to parsing Link header
            next_page = self._parse_link_header(headers.get('Link'))
        
        return {
            'data': parsed_data,
            'next_page': next_page,
            'total_pages': headers.get('X-Total-Pages'),
            'total': headers.get('X-Total')
        }
    
    def _make_paginated_request(self, endpoint, params=None, max_pages=None):
        """Make paginated requests, following X-Next-Page/Link headers until exhausted
        
        This is the core pagination helper that fetches all pages of results from a GitLab API endpoint.
        It automatically handles:
        - X-Next-Page header (GitLab's preferred pagination method)
        - Link header with rel="next" (RFC 5988 standard)
        - Exponential backoff and retry logic (via gitlab_request)
        - Rate limiting (429 responses)
        
        Args:
            endpoint: GitLab API endpoint path (e.g., 'projects', 'groups/123/projects')
            params: Optional query parameters dict (e.g., {'membership': 'true'})
            max_pages: Optional maximum number of pages to fetch (None = unlimited)
        
        Returns:
            list: All items collected across all pages
            None: If API error occurred on any page
        
        Logging:
            - INFO: Page fetch progress (no secrets logged)
            - ERROR: API failures
        """
        if params is None:
            params = {}
        
        # Set per_page in params
        params['per_page'] = self.per_page
        
        all_items = []
        page = 1
        
        while True:
            params['page'] = page
            logger.debug(f"Fetching {endpoint} page {page}")
            
            result = self.gitlab_request(endpoint, params)
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
    
    def gitlab_get_all_pages(self, endpoint, params=None):
        """Public helper: Get all pages of results from a GitLab API endpoint
        
        This is a convenience wrapper around _make_paginated_request that provides
        a clear, public interface for fetching all pages of data. It reads X-Next-Page
        and Link headers to iterate through all pages until exhausted.
        
        Args:
            endpoint: GitLab API endpoint path (e.g., 'projects', 'groups/123/projects')
            params: Optional query parameters dict
        
        Returns:
            list: All items collected across all pages
            None: If API error occurred
        
        Example:
            # Fetch all projects
            projects = client.gitlab_get_all_pages('projects', {'membership': 'true'})
            
            # Fetch all group projects
            projects = client.gitlab_get_all_pages('groups/123/projects')
        """
        return self._make_paginated_request(endpoint, params)
    
    def get_projects(self, per_page=None):
        """Get list of projects with pagination support"""
        if per_page:
            # For backward compatibility, use single page request
            result = self.gitlab_request('projects', {'per_page': per_page, 'membership': 'true'})
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
        result = self.gitlab_request(f'projects/{project_id}')
        if result is None:
            return None
        return result.get('data', None)
    
    def get_pipelines(self, project_id, per_page=None):
        """Get pipelines for a project with pagination"""
        if per_page:
            # For backward compatibility, use single page request
            result = self.gitlab_request(f'projects/{project_id}/pipelines', {'per_page': per_page})
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
# Initialize with empty structures to ensure endpoints always have valid shapes
STATE = {
    'data': {
        'projects': [],
        'pipelines': [],
        'summary': dict(DEFAULT_SUMMARY)  # Use copy of default summary
    },
    'last_updated': None,
    'status': 'INITIALIZING',
    'error': None
}
STATE_LOCK = threading.Lock()

# Global flag to track if server is running in mock mode
MOCK_MODE_ENABLED = False

# Global variable to track which mock scenario is being used
MOCK_SCENARIO = ''


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


def get_state_snapshot():
    """Thread-safe atomic snapshot of entire STATE
    
    Returns a consistent snapshot of all STATE data under a single lock acquisition.
    This prevents torn reads where data could change between multiple get_state() calls.
    
    Returns:
        dict: Complete snapshot with 'data', 'last_updated', 'status', 'error' keys
              The 'data' dict contains references to the actual lists/dicts (shallow copy)
              which is safe since we rebuild these on each update
    """
    with STATE_LOCK:
        return {
            'data': dict(STATE['data']),  # Shallow copy of data dict
            'last_updated': STATE['last_updated'],
            'status': STATE['status'],
            'error': STATE['error']
        }


def set_state_error(error, poll_id=None):
    """Thread-safe update of STATE error
    
    Args:
        error: Error message or exception
        poll_id: Optional poll cycle identifier for logging context
    """
    with STATE_LOCK:
        STATE['status'] = 'ERROR'
        STATE['error'] = str(error)
    if poll_id:
        logger.error(f"[poll_id={poll_id}] State set to ERROR: {error}")


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
        self.poll_counter = 0
        
    def _generate_poll_id(self):
        """Generate a unique poll cycle identifier"""
        self.poll_counter += 1
        return f"poll-{self.poll_counter}"
        
    def run(self):
        """Main polling loop"""
        logger.info("Background poller started")
        
        while self.running:
            # Generate poll_id before entering try block so errors preserve the same ID
            poll_id = self._generate_poll_id()
            try:
                self.poll_data(poll_id)
            except Exception as e:
                logger.error(f"[poll_id={poll_id}] Error in background poller: {e}")
                set_state_error(e, poll_id=poll_id)
            
            # Sleep for poll interval with interruptible wait
            logger.debug(f"Sleeping for {self.poll_interval}s before next poll")
            if self.stop_event.wait(timeout=self.poll_interval):
                # Event was set, exit loop
                break
    
    def poll_data(self, poll_id):
        """Poll GitLab API and update STATE
        
        Args:
            poll_id: Poll cycle identifier for logging context
        """
        logger.info(f"[poll_id={poll_id}] Starting data poll...")
        
        # Fetch projects and pipelines FIRST (don't update STATE yet)
        projects = self._fetch_projects(poll_id)
        if projects is None:
            logger.error(f"[poll_id={poll_id}] Failed to fetch projects - API error")
            # Set error state so health endpoint reflects the failure
            set_state_error("Failed to fetch data from GitLab API", poll_id=poll_id)
            logger.error(f"[poll_id={poll_id}] Data poll completed with failures - state marked as ERROR")
            return
        
        # Fetch pipelines (pass projects to respect configured scope)
        # Returns dict with 'all_pipelines' (for /api/pipelines) and 'per_project' (for enrichment)
        pipeline_data = self._fetch_pipelines(projects, poll_id)
        if pipeline_data is None:
            logger.error(f"[poll_id={poll_id}] Failed to fetch pipelines - API error")
            # Set error state so health endpoint reflects the failure
            set_state_error("Failed to fetch data from GitLab API", poll_id=poll_id)
            logger.error(f"[poll_id={poll_id}] Data poll completed with failures - state marked as ERROR")
            return
        
        # Enrich projects with per-project pipeline health data
        enriched_projects = self._enrich_projects_with_pipelines(projects, pipeline_data['per_project'], poll_id)
        
        # Both fetches succeeded - calculate summary and update STATE atomically
        summary = self._calculate_summary(enriched_projects, pipeline_data['all_pipelines'])
        
        # Update all keys atomically with single timestamp and status
        update_state_atomic({
            'projects': enriched_projects,
            'pipelines': pipeline_data['all_pipelines'],
            'summary': summary
        })
        
        logger.info(f"[poll_id={poll_id}] Updated STATE atomically: {len(enriched_projects)} projects, {len(pipeline_data['all_pipelines'])} pipelines")
        logger.info(f"[poll_id={poll_id}] Data poll completed successfully")
    
    def _fetch_projects(self, poll_id=None):
        """Fetch projects from configured sources
        
        Args:
            poll_id: Poll cycle identifier for logging context
        
        Returns:
            list: List of projects (may be empty if no projects found)
            None: Only if API error occurred and NO projects were fetched
        """
        all_projects = []
        api_errors = 0
        log_prefix = f"[poll_id={poll_id}] " if poll_id else ""
        
        # Fetch from specific project IDs if configured
        if self.project_ids:
            logger.info(f"{log_prefix}Fetching {len(self.project_ids)} specific projects")
            for project_id in self.project_ids:
                project = self.gitlab_client.get_project(project_id)
                if project is None:
                    # API error occurred
                    api_errors += 1
                    logger.warning(f"{log_prefix}Failed to fetch project {project_id}")
                else:
                    # Non-None means successful API call, add the project
                    all_projects.append(project)
        
        # Fetch from groups if configured
        if self.group_ids:
            logger.info(f"{log_prefix}Fetching projects from {len(self.group_ids)} groups")
            for group_id in self.group_ids:
                logger.info(f"{log_prefix}Fetching projects for group {group_id}")
                group_projects = self.gitlab_client.get_group_projects(group_id)
                if group_projects is None:
                    # API error occurred
                    api_errors += 1
                    logger.warning(f"{log_prefix}Failed to fetch projects for group {group_id}")
                elif group_projects:
                    # Non-empty list, extend our results
                    all_projects.extend(group_projects)
                    logger.info(f"{log_prefix}Added {len(group_projects)} projects from group {group_id}")
                else:
                    # Empty list - group has no projects
                    logger.info(f"{log_prefix}Group {group_id} has no projects")
        
        # If no specific sources configured, fetch all accessible projects
        if not self.project_ids and not self.group_ids:
            logger.info(f"{log_prefix}Fetching all accessible projects")
            projects = self.gitlab_client.get_projects()
            if projects is None:
                # API error occurred
                api_errors += 1
                logger.error(f"{log_prefix}Failed to fetch all accessible projects")
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
                logger.info(f"{log_prefix}Deduplicated {duplicates} duplicate projects (found in multiple groups/sources)")
            
            all_projects = unique_projects
        
        # Handle partial failures
        if api_errors > 0:
            if all_projects:
                logger.warning(f"{log_prefix}Partial project fetch: {api_errors} sources failed, but got {len(all_projects)} projects from others")
            else:
                logger.error(f"{log_prefix}All project fetches failed")
                return None
        
        if not all_projects:
            logger.info(f"{log_prefix}No projects found (this may be expected for configured groups/IDs)")
        
        return all_projects
    
    def _fetch_pipelines(self, projects, poll_id=None):
        """Fetch pipelines for configured projects
        
        Args:
            projects: List of project dicts from _fetch_projects(). 
                     None means API error occurred.
                     Empty list means no projects found in configured scope.
            poll_id: Poll cycle identifier for logging context
        
        Returns:
            dict: {
                'all_pipelines': List sorted and limited for /api/pipelines endpoint,
                'per_project': Dict mapping project_id -> list of pipelines for enrichment
            }
            None: Only if API error occurred
        """
        log_prefix = f"[poll_id={poll_id}] " if poll_id else ""
        
        # Check if we have a configured scope (group_ids or project_ids set)
        has_configured_scope = bool(self.group_ids or self.project_ids)
        
        # If we have a configured scope, only fetch from those projects
        if has_configured_scope:
            # projects is None means API error
            if projects is None:
                logger.error(f"{log_prefix}Cannot fetch pipelines: project fetch failed")
                return None
            
            # projects is empty list means configured scope has no projects
            if not projects:
                logger.info(f"{log_prefix}No projects in configured scope, returning empty pipelines")
                return {'all_pipelines': [], 'per_project': {}}
            
            logger.info(f"{log_prefix}Fetching pipelines for {len(projects)} configured projects")
            all_pipelines = []
            per_project_pipelines = {}
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
                    logger.warning(f"{log_prefix}Failed to fetch pipelines for project {project_name} (ID: {project_id})")
                    api_errors += 1
                elif pipelines:
                    # Store per-project pipelines for enrichment (before global limit)
                    per_project_pipelines[project_id] = []
                    
                    # Add project info to each pipeline
                    for pipeline in pipelines:
                        pipeline['project_name'] = project_name
                        pipeline['project_id'] = project_id
                        pipeline['project_path'] = project_path
                        all_pipelines.append(pipeline)
                        # Also store in per-project dict
                        per_project_pipelines[project_id].append(pipeline)
            
            # Handle partial failures
            if api_errors > 0:
                if all_pipelines:
                    logger.warning(f"{log_prefix}Partial pipeline fetch: {api_errors} projects failed, but got {len(all_pipelines)} pipelines from others")
                else:
                    logger.error(f"{log_prefix}All pipeline fetches failed")
                    return None
            
            # Sort by created_at descending for /api/pipelines
            # ISO 8601 string sorting works correctly; empty values sort to bottom
            all_pipelines.sort(key=lambda x: x.get('created_at') or '', reverse=True)
            
            # Store all pipelines in STATE (up to what we fetched) to support filtering
            # The limit will be applied at the API response level in handle_pipelines
            if not all_pipelines:
                logger.info(f"{log_prefix}No pipelines found in configured projects")
            
            return {
                'all_pipelines': all_pipelines,  # Store all fetched pipelines
                'per_project': per_project_pipelines
            }
        else:
            # No scope configured: fallback to arbitrary membership sample
            # Fetch enough pipelines to support filtering and higher limits
            logger.info(f"{log_prefix}No scope configured, using membership sample for pipelines")
            pipelines = self.gitlab_client.get_all_pipelines(per_page=MAX_PROJECTS_FOR_PIPELINES * PIPELINES_PER_PROJECT)
            
            # Return None for API errors, empty list is valid
            if pipelines is None:
                return None
            
            if not pipelines:
                logger.info(f"{log_prefix}No pipelines found")
            
            # Build per-project map from the fetched pipelines
            per_project_pipelines = {}
            for pipeline in pipelines:
                project_id = pipeline.get('project_id')
                if project_id:
                    if project_id not in per_project_pipelines:
                        per_project_pipelines[project_id] = []
                    per_project_pipelines[project_id].append(pipeline)
            
            return {
                'all_pipelines': pipelines,
                'per_project': per_project_pipelines
            }
    
    def _enrich_projects_with_pipelines(self, projects, per_project_pipelines, poll_id=None):
        """Enrich project data with pipeline health metrics
        
        Args:
            projects: List of project dicts
            per_project_pipelines: Dict mapping project_id -> list of pipelines for that project
            poll_id: Poll cycle identifier for logging context
        
        Returns:
            List of enriched project dicts with pipeline health data
        """
        log_prefix = f"[poll_id={poll_id}] " if poll_id else ""
        
        if not projects:
            logger.debug(f"{log_prefix}No projects to enrich")
            return []
        
        # Sort pipelines by created_at for each project (newest first)
        # ISO 8601 timestamps sort correctly lexicographically
        for project_id in per_project_pipelines:
            per_project_pipelines[project_id].sort(
                key=lambda p: p.get('created_at') or EPOCH_TIMESTAMP, 
                reverse=True
            )
        
        # Enrich each project with pipeline data
        enriched_projects = []
        for project in projects:
            project_id = project.get('id')
            enriched = dict(project)  # Create a copy
            
            # Get pipelines for this project
            pipelines_for_project = per_project_pipelines.get(project_id, [])
            
            if pipelines_for_project:
                # Last pipeline info
                last_pipeline = pipelines_for_project[0]
                enriched['last_pipeline_status'] = last_pipeline.get('status')
                enriched['last_pipeline_ref'] = last_pipeline.get('ref')
                enriched['last_pipeline_duration'] = last_pipeline.get('duration')
                enriched['last_pipeline_updated_at'] = last_pipeline.get('updated_at')
                
                # Calculate recent success rate (last 10 pipelines on default branch only)
                default_branch = project.get('default_branch', DEFAULT_BRANCH_NAME)
                default_branch_pipelines = [
                    p for p in pipelines_for_project 
                    if p.get('ref') == default_branch
                ]
                
                if default_branch_pipelines:
                    # Calculate success rate on default branch, excluding skipped/manual/canceled
                    recent_default_pipelines = default_branch_pipelines[:10]
                    # Filter out statuses that should be ignored
                    meaningful_pipelines = [
                        p for p in recent_default_pipelines 
                        if p.get('status') not in IGNORED_PIPELINE_STATUSES
                    ]
                    if meaningful_pipelines:
                        success_count = sum(1 for p in meaningful_pipelines if p.get('status') == 'success')
                        enriched['recent_success_rate'] = success_count / len(meaningful_pipelines)
                    else:
                        # No meaningful pipelines (all were skipped/manual/canceled)
                        enriched['recent_success_rate'] = None
                else:
                    # No default branch pipelines found
                    enriched['recent_success_rate'] = None
                
                # Calculate consecutive failures on default branch
                # Ignore skipped/manual/canceled statuses when counting consecutive failures
                consecutive_failures = 0
                for pipeline in default_branch_pipelines:
                    status = pipeline.get('status')
                    if status == 'failed':
                        consecutive_failures += 1
                    elif status in IGNORED_PIPELINE_STATUSES:
                        # Ignore these statuses - they don't break the consecutive failure count
                        continue
                    else:
                        # Stop counting at first actual success/running/pending
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
        
        logger.debug(f"{log_prefix}Enriched {len(enriched_projects)} projects with pipeline data")
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
    
    def _is_blocked_path(self, path):
        """Check if a path should be blocked for security reasons
        
        Args:
            path: The request path to check
            
        Returns:
            True if the path should be blocked, False otherwise
        """
        # Normalize path to prevent bypass via URL encoding (security)
        # URL-decode, remove null bytes, and normalize the path before checking
        decoded_path = unquote(path)
        # Remove null bytes and other control characters that could be used for bypass
        cleaned_path = decoded_path.replace('\x00', '').replace('\r', '').replace('\n', '')
        normalized_path = os.path.normpath(cleaned_path)
        
        # Block access to configuration files (security)
        # Check both the original path and normalized path to catch encoding tricks
        # Also check if normalized path is attempting to access blocked files with trailing content
        blocked_paths = ['/config.json', '/config.json.example', '/.env', '/.env.example']
        
        for blocked in blocked_paths:
            # Exact match
            if path == blocked or normalized_path == blocked:
                return True
            # Check if attempting to access blocked file with appended content (e.g., /config.json.anything)
            if normalized_path.startswith(blocked + '.') or normalized_path.startswith(blocked + '/'):
                return True
        
        return False
    
    def do_GET(self):
        """Handle GET requests"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        # Block access to configuration files (security)
        if self._is_blocked_path(path):
            self.send_error(403, "Forbidden: Configuration files are not accessible")
            return
        
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
    
    def do_HEAD(self):
        """Handle HEAD requests"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        # Block access to configuration files (security)
        if self._is_blocked_path(path):
            self.send_error(403, "Forbidden: Configuration files are not accessible")
            return
        
        # For non-blocked paths, delegate to parent class
        super().do_HEAD()
    
    def do_POST(self):
        """Handle POST requests"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        # API endpoints
        if path == '/api/mock/reload':
            self.handle_mock_reload()
        else:
            # Unsupported POST endpoint
            self.send_json_response({'error': 'Endpoint not found'}, status=404)
    
    def do_OPTIONS(self):
        """Handle OPTIONS requests for CORS preflight"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Max-Age', '86400')  # Cache preflight for 24 hours
        self.end_headers()
    
    def handle_summary(self):
        """Handle /api/summary endpoint
        
        Always returns proper JSON shape even when data is empty or initializing.
        Uses atomic snapshot from in-memory STATE to prevent torn reads.
        """
        try:
            # Get atomic snapshot of STATE (single lock acquisition)
            snapshot = get_state_snapshot()
            summary = snapshot['data'].get('summary')
            
            # Build response with proper shape (never None, always has required keys)
            # If summary is None, use empty defaults (should not happen with new initialization)
            if summary is None:
                summary = dict(DEFAULT_SUMMARY)  # Use copy of default summary
            
            response = dict(summary)
            
            # Add timestamp from snapshot
            last_updated_iso = snapshot['last_updated'].isoformat() if isinstance(snapshot['last_updated'], datetime) else str(snapshot['last_updated']) if snapshot['last_updated'] else None
            response['last_updated'] = last_updated_iso
            response['last_updated_iso'] = last_updated_iso  # Explicit field as requested in requirements
            
            # Add backend status for frontend to detect stale/initializing data
            response['backend_status'] = snapshot['status']
            response['is_mock'] = MOCK_MODE_ENABLED  # Indicate if data is from mock source
            
            self.send_json_response(response)
            
        except Exception as e:
            logger.error(f"Error in handle_summary: {e}")
            # Even on error, return proper shape with zeros
            response = dict(DEFAULT_SUMMARY)  # Use copy of default summary
            response.update({
                'last_updated': None,
                'backend_status': 'ERROR',
                'is_mock': MOCK_MODE_ENABLED,
                'error': str(e)
            })
            self.send_json_response(response, status=500)
    
    def handle_repos(self):
        """Handle /api/repos endpoint
        
        Always returns proper JSON shape even when data is empty or initializing.
        Uses atomic snapshot from in-memory STATE to prevent torn reads.
        """
        try:
            # Get atomic snapshot of STATE (single lock acquisition)
            snapshot = get_state_snapshot()
            projects = snapshot['data'].get('projects')
            
            # Ensure projects is never None (use empty list if None)
            # This should not happen with new initialization, but defensive coding
            if projects is None:
                projects = []
            
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
                'last_updated': snapshot['last_updated'].isoformat() if isinstance(snapshot['last_updated'], datetime) else str(snapshot['last_updated']) if snapshot['last_updated'] else None,
                'backend_status': snapshot['status'],  # Add status for frontend to detect stale data
                'is_mock': MOCK_MODE_ENABLED  # Indicate if data is from mock source
            }
            
            self.send_json_response(response)
            
        except Exception as e:
            logger.error(f"Error in handle_repos: {e}")
            # Even on error, return proper shape with empty array
            self.send_json_response({
                'repositories': [],
                'total': 0,
                'last_updated': None,
                'backend_status': 'ERROR',
                'is_mock': MOCK_MODE_ENABLED,
                'error': str(e)
            }, status=500)
    
    def handle_pipelines(self):
        """Handle /api/pipelines endpoint
        
        Always returns proper JSON shape even when data is empty or initializing.
        Uses atomic snapshot from in-memory STATE to prevent torn reads.
        """
        try:
            # Get atomic snapshot of STATE (single lock acquisition)
            snapshot = get_state_snapshot()
            pipelines = snapshot['data'].get('pipelines')
            projects = snapshot['data'].get('projects')
            
            # Ensure pipelines is never None (use empty list if None)
            # This should not happen with new initialization, but defensive coding
            if pipelines is None:
                pipelines = []
            
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
                self.send_json_response({'error': f'Invalid limit parameter: {str(e)}', 'is_mock': MOCK_MODE_ENABLED}, status=400)
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
                'last_updated': snapshot['last_updated'].isoformat() if isinstance(snapshot['last_updated'], datetime) else str(snapshot['last_updated']) if snapshot['last_updated'] else None,
                'backend_status': snapshot['status'],  # Add status for frontend to detect stale data
                'is_mock': MOCK_MODE_ENABLED  # Indicate if data is from mock source
            }
            
            self.send_json_response(response)
            
        except Exception as e:
            logger.error(f"Error in handle_pipelines: {e}")
            # Even on error, return proper shape with empty array
            self.send_json_response({
                'pipelines': [],
                'total': 0,
                'total_before_limit': 0,
                'last_updated': None,
                'backend_status': 'ERROR',
                'is_mock': MOCK_MODE_ENABLED,
                'error': str(e)
            }, status=500)
    
    def handle_health(self):
        """Handle /api/health endpoint"""
        try:
            # Get atomic snapshot of STATE (single lock acquisition)
            snapshot = get_state_snapshot()
            
            # Safe handling of last_updated
            last_poll = None
            if snapshot['last_updated']:
                if isinstance(snapshot['last_updated'], datetime):
                    last_poll = snapshot['last_updated'].isoformat()
                else:
                    last_poll = str(snapshot['last_updated'])
            
            # Determine health status
            # ONLINE = healthy (working connection to GitLab)
            # INITIALIZING = not ready (no successful GitLab connection yet)
            # ERROR = unhealthy (GitLab connection failed)
            is_healthy = snapshot['status'] == 'ONLINE'
            
            health = {
                'status': 'healthy' if is_healthy else 'unhealthy',
                'backend_status': snapshot['status'],
                'timestamp': datetime.now().isoformat(),
                'last_poll': last_poll,
                'error': snapshot['error'],
                'is_mock': MOCK_MODE_ENABLED  # Indicate if data is from mock source
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
                'error': str(e),
                'is_mock': MOCK_MODE_ENABLED
            }
            self.send_json_response(health, status=503)
    
    def handle_mock_reload(self):
        """Handle /api/mock/reload endpoint (POST only)
        
        Re-reads mock data file and atomically replaces STATE contents.
        Only works when server is running in mock mode.
        Reloads from the same scenario that was initially configured.
        
        This endpoint is intentionally restricted to mock mode only because:
        1. In production (non-mock mode), STATE is populated by the background poller
           which fetches data from the real GitLab API. Allowing arbitrary state
           replacement would bypass normal data flow and could cause inconsistencies.
        2. Mock mode is designed for CI, testing, and demos - environments where
           hot-reloading test data is useful.
        3. This prevents accidental misuse where someone might try to "reload" data
           when connected to a real GitLab instance.
        """
        try:
            # Guardrail: This endpoint only works in mock mode.
            # See docstring above for rationale on why this is intentionally restricted.
            if not MOCK_MODE_ENABLED:
                self.send_json_response({
                    'error': 'Mock reload endpoint only available in mock mode',
                    'hint': 'Set USE_MOCK_DATA=true or use_mock_data: true in config.json',
                    'is_mock': False
                }, status=400)
                return
            
            # Re-load mock data from file (using the configured scenario)
            mock_data = load_mock_data(MOCK_SCENARIO)
            if mock_data is None:
                self.send_json_response({
                    'error': f'Failed to load mock data file',
                    'is_mock': True,
                    'scenario': MOCK_SCENARIO if MOCK_SCENARIO else 'default (mock_data.json)',
                    'details': 'Check server logs for details'
                }, status=500)
                return
            
            # Atomically update STATE with new mock data
            update_state_atomic({
                'projects': mock_data['repositories'],
                'pipelines': mock_data['pipelines'],
                'summary': mock_data['summary']
            })
            
            # Get the timestamp that was just set (using atomic snapshot)
            snapshot = get_state_snapshot()
            timestamp_iso = snapshot['last_updated'].isoformat() if isinstance(snapshot['last_updated'], datetime) else str(snapshot['last_updated'])
            
            logger.info("Mock data reloaded successfully via API")
            logger.info(f"  Repositories: {len(mock_data['repositories'])}")
            logger.info(f"  Pipelines: {len(mock_data['pipelines'])}")
            
            self.send_json_response({
                'reloaded': True,
                'is_mock': True,
                'backend_status': snapshot['status'],
                'last_updated': timestamp_iso,
                'timestamp': timestamp_iso,  # Keep for backward compatibility
                'scenario': MOCK_SCENARIO if MOCK_SCENARIO else 'default',
                'summary': {
                    'repositories': len(mock_data['repositories']),
                    'pipelines': len(mock_data['pipelines'])
                }
            })
            
        except Exception as e:
            logger.error(f"Error in handle_mock_reload: {e}")
            self.send_json_response({
                'error': str(e),
                'reloaded': False,
                'is_mock': MOCK_MODE_ENABLED
            }, status=500)
    
    def send_json_response(self, data, status=200):
        """Send JSON response with security headers"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-store, max-age=0')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode('utf-8'))
    
    def log_message(self, format, *args):
        """Override to use logger with enhanced context
        
        Adds method, path, and request type tag (api/static) for easy filtering.
        """
        # Determine request type tag based on path
        path = self.path.split('?')[0] if hasattr(self, 'path') else ''
        request_type = 'api' if path.startswith('/api/') else 'static'
        method = getattr(self, 'command', 'UNKNOWN')
        
        # Format: [type] METHOD /path - status - client
        logger.info("[%s] %s %s - %s - %s" % (
            request_type,
            method,
            self.path if hasattr(self, 'path') else '',
            format % args,
            self.address_string()
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
    
    # Log level configuration (environment variable takes precedence)
    # LOG_LEVEL env var is handled by get_log_level(), but we also support config.json
    if 'LOG_LEVEL' in os.environ:
        config['log_level'] = os.environ['LOG_LEVEL'].upper()
    elif 'log_level' in config:
        config['log_level'] = str(config['log_level']).upper()
    else:
        config['log_level'] = 'INFO'
    
    # Validate and set the log level
    if config['log_level'] not in VALID_LOG_LEVELS:
        logger.warning(f"Invalid LOG_LEVEL '{config['log_level']}'. Using default: INFO")
        config['log_level'] = 'INFO'
    
    # Reconfigure logging with the resolved level
    log_level = getattr(logging, config['log_level'])
    logging.getLogger().setLevel(log_level)
    logger.setLevel(log_level)
    
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
    
    # SSL/TLS Configuration
    # CA bundle path (preferred for custom/internal CA certificates)
    config['ca_bundle_path'] = os.environ.get('CA_BUNDLE_PATH', config.get('ca_bundle_path', None))
    
    # For insecure_skip_verify, check if env var is explicitly set to allow overriding
    if 'INSECURE_SKIP_VERIFY' in os.environ:
        config['insecure_skip_verify'] = os.environ['INSECURE_SKIP_VERIFY'].lower() in ['true', '1', 'yes']
    else:
        config['insecure_skip_verify'] = config.get('insecure_skip_verify', False)
    
    # For use_mock_data, check if env var is explicitly set to allow overriding
    if 'USE_MOCK_DATA' in os.environ:
        config['use_mock_data'] = os.environ['USE_MOCK_DATA'].lower() in ['true', '1', 'yes']
    else:
        config['use_mock_data'] = config.get('use_mock_data', False)
    
    # Mock scenario selection - which mock file to load
    config['mock_scenario'] = os.environ.get('MOCK_SCENARIO', config.get('mock_scenario', ''))
    
    # Ensure lists are clean (filter config.json values that might have empty strings or numeric IDs)
    if isinstance(config['group_ids'], list):
        config['group_ids'] = [str(gid).strip() for gid in config['group_ids'] if gid and str(gid).strip()]
    if isinstance(config['project_ids'], list):
        config['project_ids'] = [str(pid).strip() for pid in config['project_ids'] if pid and str(pid).strip()]
    
    # Log configuration (without secrets)
    logger.info(f"Configuration loaded from: {config_source}")
    logger.info(f"  Log level: {config['log_level']}")
    logger.info(f"  GitLab URL: {config['gitlab_url']}")
    logger.info(f"  Port: {config['port']}")
    logger.info(f"  Poll interval: {config['poll_interval_sec']}s")
    logger.info(f"  Cache TTL: {config['cache_ttl_sec']}s")
    logger.info(f"  Per page: {config['per_page']}")
    logger.info(f"  Group IDs: {config['group_ids'] if config['group_ids'] else 'None (using all accessible projects)'}")
    logger.info(f"  Project IDs: {config['project_ids'] if config['project_ids'] else 'None'}")
    logger.info(f"  CA bundle path: {config['ca_bundle_path'] if config['ca_bundle_path'] else 'None (using system default)'}")
    logger.info(f"  Insecure skip verify: {config['insecure_skip_verify']}")
    logger.info(f"  Use mock data: {config['use_mock_data']}")
    if config['use_mock_data']:
        logger.info(f"  Mock scenario: {config['mock_scenario'] if config['mock_scenario'] else 'default (mock_data.json)'}")
    logger.info(f"  API token: {'***' if config['api_token'] else 'NOT SET'}")
    
    return config


def validate_config(config):
    """Validate configuration values and fail-fast if invalid
    
    Validates:
    - API token must be provided if mock mode is disabled
    - poll_interval_sec must be a positive integer (≥5 recommended)
    - cache_ttl_sec must not be negative
    - per_page must be positive
    
    Args:
        config: Configuration dict from load_config()
    
    Returns:
        bool: True if configuration is valid, False otherwise
    
    Side effects:
        Logs error messages describing which key is invalid and how to fix it
    """
    is_valid = True
    
    # Skip API token validation if mock mode is enabled
    if not config.get('use_mock_data', False):
        # API token is required in non-mock mode
        if not config.get('api_token'):
            logger.error("Configuration error: 'api_token' is required when mock mode is disabled")
            logger.error("  Fix: Set GITLAB_API_TOKEN environment variable or add 'api_token' to config.json")
            is_valid = False
    
    # Validate poll_interval_sec is a positive integer
    poll_interval = config.get('poll_interval_sec')
    if poll_interval is None or not isinstance(poll_interval, int) or poll_interval <= 0:
        logger.error(f"Configuration error: 'poll_interval_sec' must be a positive integer, got: {poll_interval}")
        logger.error("  Fix: Set POLL_INTERVAL environment variable or 'poll_interval_sec' in config.json to a positive integer")
        is_valid = False
    elif poll_interval < 5:
        logger.warning(f"Configuration warning: 'poll_interval_sec' is {poll_interval}s, which is very short. Recommend ≥5s to avoid rate limiting.")
    
    # Validate cache_ttl_sec is not negative
    cache_ttl = config.get('cache_ttl_sec')
    if cache_ttl is None or not isinstance(cache_ttl, int) or cache_ttl < 0:
        logger.error(f"Configuration error: 'cache_ttl_sec' must be a non-negative integer, got: {cache_ttl}")
        logger.error("  Fix: Set CACHE_TTL environment variable or 'cache_ttl_sec' in config.json to 0 or a positive integer")
        is_valid = False
    
    # Validate per_page is positive
    per_page = config.get('per_page')
    if per_page is None or not isinstance(per_page, int) or per_page <= 0:
        logger.error(f"Configuration error: 'per_page' must be a positive integer, got: {per_page}")
        logger.error("  Fix: Set PER_PAGE environment variable or 'per_page' in config.json to a positive integer (1-100)")
        is_valid = False
    
    # Log validation result
    if is_valid:
        logger.info("Configuration validation passed")
    else:
        logger.error("Configuration validation failed - see errors above")
    
    return is_valid


def load_mock_data(scenario=''):
    """Load mock data from mock_data.json file or a specific scenario file
    
    Args:
        scenario: Optional scenario name (e.g., 'healthy', 'failing', 'running').
                  If provided, loads from data/mock_scenarios/{scenario}.json
                  If empty, loads from mock_data.json in root directory.
    
    Returns:
        dict: Mock data with 'summary', 'repositories', and 'pipelines' keys
        None: If file not found or JSON parsing fails
    """
    if scenario:
        # Load from scenario file in data/mock_scenarios/
        mock_data_file = f'data/mock_scenarios/{scenario}.json'
    else:
        # Load from default mock_data.json
        mock_data_file = 'mock_data.json'
    
    if not os.path.exists(mock_data_file):
        logger.error(f"Mock data file not found: {mock_data_file}")
        if scenario:
            logger.error(f"Available scenarios: healthy, failing, running")
            logger.error(f"Check that the file exists in data/mock_scenarios/ directory")
        return None
    
    try:
        with open(mock_data_file, 'r') as f:
            data = json.load(f)
        
        # Validate required keys
        required_keys = ['summary', 'repositories', 'pipelines']
        for key in required_keys:
            if key not in data:
                logger.error(f"Mock data file missing required key: {key}")
                return None
        
        logger.info(f"Successfully loaded mock data from {mock_data_file}")
        logger.info(f"  Repositories: {len(data['repositories'])}")
        logger.info(f"  Pipelines: {len(data['pipelines'])}")
        
        return data
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse mock data JSON: {e}")
        return None
    except Exception as e:
        logger.error(f"Error loading mock data: {e}")
        return None


def main():
    """Main entry point"""
    global MOCK_MODE_ENABLED, MOCK_SCENARIO
    
    logger.info("Starting GitLab Dashboard Server...")
    
    # Load configuration
    config = load_config()
    
    # Validate configuration (fail-fast on invalid config)
    if not validate_config(config):
        logger.error("Server startup aborted due to configuration errors")
        return 1
    
    # Check if mock mode is enabled
    if config['use_mock_data']:
        MOCK_MODE_ENABLED = True
        MOCK_SCENARIO = config['mock_scenario']
        
        # Determine the resolved file path for the mock data
        if MOCK_SCENARIO:
            mock_file_path = f'data/mock_scenarios/{MOCK_SCENARIO}.json'
        else:
            mock_file_path = 'mock_data.json'
        # Resolve to absolute path for clarity in logs
        resolved_mock_path = os.path.abspath(mock_file_path)
        
        # Log a clear banner about mock mode
        logger.info("=" * 70)
        logger.info("MOCK DATA MODE ENABLED")
        logger.info("=" * 70)
        logger.info(f"  Scenario: {MOCK_SCENARIO if MOCK_SCENARIO else 'default'}")
        logger.info(f"  File: {mock_file_path}")
        logger.info(f"  Resolved path: {resolved_mock_path}")
        logger.info("  GitLab polling: DISABLED")
        logger.info("  Use POST /api/mock/reload to hot-reload mock data")
        logger.info("=" * 70)
        
        # Load mock data with scenario
        mock_data = load_mock_data(MOCK_SCENARIO)
        if mock_data is None:
            logger.error("Failed to load mock data. Exiting.")
            return
        
        # Initialize STATE with mock data
        update_state_atomic({
            'projects': mock_data['repositories'],
            'pipelines': mock_data['pipelines'],
            'summary': mock_data['summary']
        })
        logger.info("Mock data loaded into STATE successfully")
        
        # No GitLab client or poller in mock mode
        gitlab_client = None
        poller = None
        
    else:
        # Normal mode: Initialize GitLab client and poller
        gitlab_client = GitLabAPIClient(
            config['gitlab_url'], 
            config['api_token'],
            per_page=config['per_page'],
            insecure_skip_verify=config['insecure_skip_verify'],
            ca_bundle_path=config.get('ca_bundle_path')
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
        if poller:
            poller.stop()
            poller.join(timeout=5)  # Wait for poller thread to finish
            if poller.is_alive():
                logger.warning("Poller thread did not stop cleanly")
        httpd.shutdown()
        logger.info("Server stopped.")
    
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main() or 0)

#!/usr/bin/env python3
"""
GitLab API Client Module for DSO-Dashboard

Handles all GitLab API interactions including:
- API requests with retry and rate limiting
- Pagination handling
- Project and pipeline data fetching

This module uses only Python standard library (no pip dependencies).
"""

import json
import logging
import re
import ssl
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

# Pipeline fetching configuration constants
MAX_PROJECTS_FOR_PIPELINES = 20  # Max projects to fetch pipelines from
PIPELINES_PER_PROJECT = 10       # Pipelines to fetch per project

# Pipeline statuses to ignore when calculating consecutive failures and success rates
# These statuses represent pipelines that didn't actually test the code
IGNORED_PIPELINE_STATUSES = ('skipped', 'manual', 'canceled', 'cancelled')

# Timestamp fallback constants
EPOCH_TIMESTAMP = '1970-01-01T00:00:00Z'  # Fallback for missing timestamps

# Default branch constant
DEFAULT_BRANCH_NAME = 'main'     # Default branch name fallback

# Runner issue detection constants
# These statuses indicate runner-related problems (pipeline level)
RUNNER_ISSUE_STATUSES = ('stuck',)

# These failure_reason values indicate runner-related problems (from GitLab API)
RUNNER_ISSUE_FAILURE_REASONS = (
    'runner_system_failure',
    'stuck_or_timeout_failure',
    'runner_unsupported',
    'scheduler_failure',
    'data_integrity_failure',
)


def is_runner_related_failure(pipeline):
    """Check if a pipeline failure is related to runner/infrastructure issues
    
    This helper function encapsulates the detection logic for runner-related
    failures to improve readability and testability.
    
    Detection methods:
    1. Pipeline status is 'stuck' (runner not picking up jobs)
    2. Pipeline failure_reason contains runner-related keywords
       (e.g., 'runner_system_failure', 'stuck_or_timeout_failure')
    
    Args:
        pipeline: Pipeline dict from GitLab API
        
    Returns:
        bool: True if the pipeline failure is runner-related
    """
    # Check for stuck status
    if pipeline.get('status') in RUNNER_ISSUE_STATUSES:
        return True
    
    # Check failure_reason if available (GitLab API may include this field)
    failure_reason = pipeline.get('failure_reason', '')
    if failure_reason:
        failure_reason_lower = failure_reason.lower()
        return any(reason in failure_reason_lower for reason in RUNNER_ISSUE_FAILURE_REASONS)
    
    return False


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
    
    def get_merge_request(self, project_id, mr_iid):
        """Get a single merge request by project ID and MR IID
        
        Args:
            project_id: GitLab project ID
            mr_iid: Merge request internal ID (IID) within the project
        
        Returns:
            dict: Merge request data from GitLab API, or None on error
        """
        result = self.gitlab_request(f'projects/{project_id}/merge_requests/{mr_iid}')
        if result is None:
            logger.warning(f"Failed to fetch merge request {mr_iid} for project {project_id}")
            return None
        return result.get('data', None)
    
    def resolve_merge_request_refs(self, pipelines, poll_id=None):
        """Resolve merge request pipeline refs to their source branch names
        
        For pipelines with refs like `refs/merge-requests/<iid>/head`, this method
        fetches the corresponding merge request to get the actual source branch name.
        
        Args:
            pipelines: List of pipeline dicts (will be mutated in place)
            poll_id: Optional poll cycle identifier for logging context
        
        Returns:
            None (mutates pipelines in place)
        
        Side effects:
            For MR pipelines, modifies each pipeline dict:
            - Sets `original_ref` to the raw MR ref (e.g., `refs/merge-requests/481/head`)
            - Sets `merge_request_iid` to the MR IID as a string (e.g., "481")
            - Replaces `ref` with the MR's `source_branch` (e.g., `feature/foo`)
        """
        log_prefix = f"[poll_id={poll_id}] " if poll_id else ""
        
        if not pipelines:
            return
        
        # Pattern to match MR refs: refs/merge-requests/<iid>/head
        mr_ref_pattern = re.compile(r'^refs/merge-requests/(\d+)/head$')
        
        # Group MR refs by project_id for batch lookup
        # Structure: {project_id: {mr_iid: [pipeline_indices...]}}
        mr_refs_by_project = {}
        
        for idx, pipeline in enumerate(pipelines):
            ref = pipeline.get('ref') or ''  # Handle None refs
            match = mr_ref_pattern.match(ref)
            if match:
                mr_iid = match.group(1)
                project_id = pipeline.get('project_id')
                if project_id:
                    if project_id not in mr_refs_by_project:
                        mr_refs_by_project[project_id] = {}
                    if mr_iid not in mr_refs_by_project[project_id]:
                        mr_refs_by_project[project_id][mr_iid] = []
                    mr_refs_by_project[project_id][mr_iid].append(idx)
        
        # Count total MR refs discovered (number of pipeline indices across all projects)
        total_mr_refs = sum(
            len(indices)
            for project_iids in mr_refs_by_project.values()
            for indices in project_iids.values()
        )
        
        if total_mr_refs == 0:
            logger.debug(f"{log_prefix}No merge request refs to resolve")
            return
        
        logger.info(f"{log_prefix}MR ref resolution: discovered {total_mr_refs} MR pipeline(s) across {len(mr_refs_by_project)} project(s)")
        
        # Build mapping: (project_id, mr_iid) -> source_branch
        mr_source_branches = {}
        successful_lookups = 0
        failed_lookups = 0
        
        for project_id, mr_iids in mr_refs_by_project.items():
            for mr_iid in mr_iids.keys():
                try:
                    mr_data = self.get_merge_request(project_id, mr_iid)
                    if mr_data and 'source_branch' in mr_data:
                        mr_source_branches[(project_id, mr_iid)] = mr_data['source_branch']
                        successful_lookups += 1
                    else:
                        failed_lookups += 1
                        logger.warning(f"{log_prefix}MR {mr_iid} in project {project_id}: no source_branch found")
                except Exception as e:
                    failed_lookups += 1
                    logger.warning(f"{log_prefix}Failed to fetch MR {mr_iid} for project {project_id}: {e}")
        
        # Apply the resolved branch names to pipelines
        resolved_count = 0
        for project_id, mr_iids in mr_refs_by_project.items():
            for mr_iid, pipeline_indices in mr_iids.items():
                source_branch = mr_source_branches.get((project_id, mr_iid))
                if source_branch:
                    for idx in pipeline_indices:
                        pipeline = pipelines[idx]
                        # Store original ref for debugging
                        pipeline['original_ref'] = pipeline['ref']
                        # Store the MR IID
                        pipeline['merge_request_iid'] = mr_iid
                        # Replace ref with source branch
                        pipeline['ref'] = source_branch
                        resolved_count += 1
        
        logger.info(f"{log_prefix}MR ref resolution complete: {resolved_count} resolved, {failed_lookups} failed")


def get_summary(projects, pipelines):
    """Calculate summary statistics from projects and pipelines
    
    Note: This should only be called when both projects and pipelines
    were successfully fetched (not None). The caller is responsible for
    ensuring valid data.
    
    Metrics distinction:
    - Repo-level `recent_success_rate` is based on recent pipelines on the DEFAULT branch only (DSO primary).
    - Repo-level `recent_success_rate_all_branches` is based on all branches (legacy/comprehensive).
    - Summary-level `pipeline_success_rate` is based on ALL fetched pipelines.
    
    Args:
        projects: List of project dicts (may be empty but not None)
        pipelines: List of pipeline dicts (may be empty but not None)
    
    Returns:
        dict: Summary dict without timestamp (caller adds it from STATE)
    """
    # Use empty lists if None (should not happen in normal flow)
    if projects is None:
        logger.warning("get_summary called with None projects - using empty list")
        projects = []
    if pipelines is None:
        logger.warning("get_summary called with None pipelines - using empty list")
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


def get_repositories(projects):
    """Format repository data for API response
    
    Args:
        projects: List of project dicts from GitLab API (may be empty but not None)
        
    Returns:
        list: List of formatted repository dicts for API response
        
    Pipeline health metrics included:
        - recent_success_rate: Default-branch success rate (backward compatible, DSO primary)
        - recent_success_rate_default_branch: Default-branch success rate (explicit naming)
        - recent_success_rate_all_branches: All-branches success rate (comprehensive/legacy)
    
    Last default-branch pipeline fields:
        - last_default_branch_pipeline_status: Status of most recent default-branch pipeline
        - last_default_branch_pipeline_ref: Ref of most recent default-branch pipeline
        - last_default_branch_pipeline_duration: Duration of most recent default-branch pipeline
        - last_default_branch_pipeline_updated_at: Updated timestamp of most recent default-branch pipeline
    
    DSO health fields included (for dashboard tiles):
        - has_failing_jobs: Whether recent default-branch pipelines contain any with 'failed' status (excludes skipped/manual/canceled)
        - failing_jobs_count: Count of pipelines with 'failed' status on default branch (excludes skipped/manual/canceled)
        - has_runner_issues: Whether failures are runner-related
    """
    if projects is None:
        projects = []
    
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
            # Pipeline health metrics (any branch - kept for backward compatibility)
            'last_pipeline_status': project.get('last_pipeline_status'),
            'last_pipeline_ref': project.get('last_pipeline_ref'),
            'last_pipeline_duration': project.get('last_pipeline_duration'),
            'last_pipeline_updated_at': project.get('last_pipeline_updated_at'),
            # Last default-branch pipeline fields (explicit default-branch-only):
            # These fields allow frontend to reliably display default-branch pipeline info
            # even when the most recent overall pipeline is from a non-default branch.
            'last_default_branch_pipeline_status': project.get('last_default_branch_pipeline_status'),
            'last_default_branch_pipeline_ref': project.get('last_default_branch_pipeline_ref'),
            'last_default_branch_pipeline_duration': project.get('last_default_branch_pipeline_duration'),
            'last_default_branch_pipeline_updated_at': project.get('last_default_branch_pipeline_updated_at'),
            # Success rate metrics:
            # - recent_success_rate: Backward compatible, points to default-branch rate (DSO primary)
            # - recent_success_rate_default_branch: Explicit default-branch rate for DSO consumption
            # - recent_success_rate_all_branches: Comprehensive rate including all branches (legacy)
            'recent_success_rate': project.get('recent_success_rate'),
            'recent_success_rate_default_branch': project.get('recent_success_rate_default_branch'),
            'recent_success_rate_all_branches': project.get('recent_success_rate_all_branches'),
            'consecutive_default_branch_failures': project.get('consecutive_default_branch_failures', 0),
            # DSO health fields (for dashboard tiles):
            # - has_failing_jobs: True if recent default-branch pipelines contain failed jobs
            # - failing_jobs_count: Count of failed pipelines on default branch
            # - has_runner_issues: True if pipelines are failing due to runner problems
            'has_failing_jobs': project.get('has_failing_jobs', False),
            'failing_jobs_count': project.get('failing_jobs_count', 0),
            'has_runner_issues': project.get('has_runner_issues', False)
        }
        repos.append(repo)
    
    return repos


def get_pipelines(pipelines, projects=None, limit=50, status_filter=None, ref_filter=None, project_filter=None):
    """Format and filter pipeline data for API response
    
    Args:
        pipelines: List of pipeline dicts (may be empty but not None)
        projects: Optional list of project dicts for path lookup
        limit: Maximum number of pipelines to return
        status_filter: Optional status to filter by
        ref_filter: Optional ref to filter by
        project_filter: Optional project name/path to filter by (substring match)
        
    Returns:
        dict: Dict with 'pipelines', 'total', and 'total_before_limit' keys
    """
    if pipelines is None:
        pipelines = []
    
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
    
    return {
        'pipelines': limited_pipelines,
        'total': len(limited_pipelines),
        'total_before_limit': len(filtered_pipelines)
    }


def enrich_projects_with_pipelines(projects, per_project_pipelines, poll_id=None):
    """Enrich project data with pipeline health metrics
    
    This function computes two distinct success rate metrics:
    
    1. recent_success_rate_default_branch (DSO primary metric):
       Based only on pipelines targeting the project's default branch.
       This is the primary metric for DSO consumption as it reflects
       the health of the main development branch.
    
    2. recent_success_rate_all_branches (legacy/comprehensive metric):
       Based on all branches. Allows noisy feature branches to drag
       a repo's health down, giving a more complete (but noisier) picture.
    
    The field `recent_success_rate` is provided for backward compatibility
    and points to the default-branch rate (the DSO primary metric).
    
    DSO Health Fields (for dashboard tiles):
        - has_failing_jobs (bool): True if recent default-branch pipelines contain any with 'failed' status (excludes skipped/manual/canceled).
          Used for DSO dashboard to highlight repos with failing CI.
        - failing_jobs_count (int): Count of pipelines with 'failed' status on default branch (excludes skipped/manual/canceled).
          Used for DSO dashboard to show severity of failures.
        - has_runner_issues (bool): True if pipelines are failing due to runner problems.
          Detected via pipeline status 'stuck' or failure_reason containing runner-related errors.
          Used for DSO dashboard to distinguish infrastructure issues from code issues.
    
    Args:
        projects: List of project dicts
        per_project_pipelines: Dict mapping project_id -> list of pipelines for that project
        poll_id: Poll cycle identifier for logging context
    
    Returns:
        List of enriched project dicts with pipeline health data including:
        - recent_success_rate: Default-branch success rate (for backward compatibility)
        - recent_success_rate_default_branch: Default-branch success rate (DSO primary)
        - recent_success_rate_all_branches: All-branches success rate (legacy/comprehensive)
        - has_failing_jobs: Whether recent default-branch pipelines have failures (DSO health)
        - failing_jobs_count: Count of failed default-branch pipelines (DSO health)
        - has_runner_issues: Whether failures are runner-related (DSO health)
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
            
            # Get the default branch name for this project
            default_branch = project.get('default_branch', DEFAULT_BRANCH_NAME)
            
            # ---------------------------------------------------------------
            # SUCCESS RATE CALCULATION: ALL BRANCHES (legacy/comprehensive)
            # ---------------------------------------------------------------
            # Calculate recent success rate using the last N pipelines across ALL branches
            # (excluding skipped/manual/canceled). This allows noisy feature branches
            # to drag a repo's health down, giving a more complete picture.
            recent_pipelines = pipelines_for_project[:PIPELINES_PER_PROJECT]
            # Filter out statuses that should be ignored
            meaningful_pipelines_all = [
                p for p in recent_pipelines 
                if p.get('status') not in IGNORED_PIPELINE_STATUSES
            ]
            if meaningful_pipelines_all:
                success_count_all = sum(1 for p in meaningful_pipelines_all if p.get('status') == 'success')
                enriched['recent_success_rate_all_branches'] = success_count_all / len(meaningful_pipelines_all)
            else:
                # No meaningful pipelines (all were skipped/manual/canceled)
                enriched['recent_success_rate_all_branches'] = None
            
            # ---------------------------------------------------------------
            # SUCCESS RATE CALCULATION: DEFAULT BRANCH ONLY (DSO primary metric)
            # ---------------------------------------------------------------
            # Calculate success rate using only pipelines on the default branch.
            # This metric is what DSO cares about - the health of the main branch.
            default_branch_pipelines = [
                p for p in pipelines_for_project 
                if p.get('ref') == default_branch
            ]
            
            # ---------------------------------------------------------------
            # LAST DEFAULT-BRANCH PIPELINE FIELDS
            # ---------------------------------------------------------------
            # Provide explicit fields for the most recent default-branch pipeline.
            # This allows the frontend to reliably show default-branch-only chip
            # even when last_pipeline_* is from a non-default branch.
            if default_branch_pipelines:
                last_default_branch_pipeline = default_branch_pipelines[0]
                enriched['last_default_branch_pipeline_status'] = last_default_branch_pipeline.get('status')
                enriched['last_default_branch_pipeline_ref'] = last_default_branch_pipeline.get('ref')
                enriched['last_default_branch_pipeline_duration'] = last_default_branch_pipeline.get('duration')
                enriched['last_default_branch_pipeline_updated_at'] = last_default_branch_pipeline.get('updated_at')
            else:
                # No default-branch pipeline found in the current window
                enriched['last_default_branch_pipeline_status'] = None
                enriched['last_default_branch_pipeline_ref'] = None
                enriched['last_default_branch_pipeline_duration'] = None
                enriched['last_default_branch_pipeline_updated_at'] = None
            
            # Limit to the same window size as all-branches for consistency
            recent_default_branch_pipelines = default_branch_pipelines[:PIPELINES_PER_PROJECT]
            # Filter out statuses that should be ignored
            meaningful_pipelines_default = [
                p for p in recent_default_branch_pipelines 
                if p.get('status') not in IGNORED_PIPELINE_STATUSES
            ]
            if meaningful_pipelines_default:
                success_count_default = sum(1 for p in meaningful_pipelines_default if p.get('status') == 'success')
                enriched['recent_success_rate_default_branch'] = success_count_default / len(meaningful_pipelines_default)
            else:
                # No meaningful default-branch pipelines in the fetched window
                enriched['recent_success_rate_default_branch'] = None
            
            # ---------------------------------------------------------------
            # BACKWARD COMPATIBILITY: recent_success_rate points to default-branch rate
            # ---------------------------------------------------------------
            # For DSO consumption, use the default-branch rate as the primary metric.
            # This aligns with the issue requirement to base repo success rate on default branch.
            enriched['recent_success_rate'] = enriched['recent_success_rate_default_branch']
            
            # ---------------------------------------------------------------
            # CONSECUTIVE FAILURES: DEFAULT BRANCH ONLY
            # ---------------------------------------------------------------
            # Calculate consecutive failures on DEFAULT BRANCH ONLY
            # This metric intentionally ignores other branches, providing a pure signal
            # for the health of the main development branch.
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
            
            # ---------------------------------------------------------------
            # DSO HEALTH FIELDS: FAILING JOBS AND RUNNER ISSUES
            # ---------------------------------------------------------------
            # These fields are used for DSO dashboard tiles to provide quick visibility
            # into CI health issues at a glance.
            
            # failing_jobs_count: Count of pipelines with 'failed' status on default branch
            # (among meaningful pipelines, excluding skipped/manual/canceled).
            # Uses generator expression for memory efficiency.
            # Used for: DSO dashboard showing count/severity of failing jobs.
            failing_jobs_count = sum(
                1 for p in meaningful_pipelines_default 
                if p.get('status') == 'failed'
            )
            enriched['failing_jobs_count'] = failing_jobs_count
            
            # has_failing_jobs: Derived from failing_jobs_count.
            # True if any meaningful recent default-branch pipeline has 'failed' status (excludes skipped/manual/canceled).
            # Used for: DSO dashboard "failing jobs" indicator tile.
            enriched['has_failing_jobs'] = failing_jobs_count > 0
            
            # has_runner_issues: True if pipelines are failing due to runner-related problems.
            # Uses the is_runner_related_failure helper for encapsulated detection logic.
            # Used for: DSO dashboard to distinguish infrastructure issues from code issues.
            enriched['has_runner_issues'] = any(
                is_runner_related_failure(p) for p in meaningful_pipelines_default
            )
        else:
            # No pipelines for this project
            enriched['last_pipeline_status'] = None
            enriched['last_pipeline_ref'] = None
            enriched['last_pipeline_duration'] = None
            enriched['last_pipeline_updated_at'] = None
            # Last default-branch pipeline fields - null when no pipelines
            enriched['last_default_branch_pipeline_status'] = None
            enriched['last_default_branch_pipeline_ref'] = None
            enriched['last_default_branch_pipeline_duration'] = None
            enriched['last_default_branch_pipeline_updated_at'] = None
            enriched['recent_success_rate'] = None
            enriched['recent_success_rate_all_branches'] = None
            enriched['recent_success_rate_default_branch'] = None
            enriched['consecutive_default_branch_failures'] = 0
            # DSO health fields - no pipelines means no failures or runner issues
            enriched['has_failing_jobs'] = False
            enriched['failing_jobs_count'] = 0
            enriched['has_runner_issues'] = False
        
        enriched_projects.append(enriched)
    
    logger.debug(f"{log_prefix}Enriched {len(enriched_projects)} projects with pipeline data")
    return enriched_projects

#!/usr/bin/env python3
"""
GitLab Dashboard Backend Server
Python 3.10 stdlib-only implementation using http.server and urllib

This is the main entry point for the DSO-Dashboard backend server.
It imports functionality from modular components:
- config_loader: Configuration loading from config.json and environment variables
- gitlab_client: GitLab API client and data processing functions
- services: External service health checks
"""

import json
import os
import sys
import threading
from datetime import datetime, timedelta
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote
import logging

# Add parent directory to path to allow direct execution (python3 backend/app.py)
# This is needed because when running directly, Python doesn't see the backend package
_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

# Import from modular components
from backend.config_loader import (
    configure_logging,
    load_config,
    load_mock_data,
    validate_config,
    PROJECT_ROOT,
)
from backend.gitlab_client import (
    GitLabAPIClient,
    enrich_projects_with_pipelines,
    get_summary,
    MAX_PROJECTS_FOR_PIPELINES,
    PIPELINES_PER_PROJECT,
    IGNORED_PIPELINE_STATUSES,
)
from backend.services import (
    get_service_statuses,
)

# Re-export symbols for backward compatibility with tests
# These are used in tests that import from backend.app (as 'server')
from backend.config_loader import (
    get_log_level,
    parse_csv_list,
    parse_int_config,
    parse_float_config,
    parse_bool_config,
    DEFAULT_SERVICE_LATENCY_CONFIG,
    DEFAULT_SLO_CONFIG,
    VALID_LOG_LEVELS,
)
from backend.services import DEFAULT_SERVICE_CHECK_TIMEOUT
from backend.gitlab_client import EPOCH_TIMESTAMP, DEFAULT_BRANCH_NAME

# Configure logging at module load (can be reconfigured in main())
_configured_level = configure_logging()
logger = logging.getLogger(__name__)

# API query parameter constants
DEFAULT_PIPELINE_LIMIT = 50      # Default limit for /api/pipelines endpoint
MAX_PIPELINE_LIMIT = 1000        # Maximum limit for /api/pipelines endpoint

# Deprecated constant kept for backward compatibility
MAX_TOTAL_PIPELINES = 50         # Default max for /api/pipelines response (deprecated in storage)

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
    'pipeline_statuses': {},
    # SLO fields for default-branch pipeline success
    'pipeline_slo_target_default_branch_success_rate': DEFAULT_SLO_CONFIG['default_branch_success_target'],
    'pipeline_slo_observed_default_branch_success_rate': 1.0,  # 100% when no pipelines
    'pipeline_slo_total_default_branch_pipelines': 0,
    'pipeline_error_budget_remaining_pct': 100,  # 100% remaining when no pipelines
}


# Note: GitLabAPIClient is now imported from backend.gitlab_client


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
        'summary': dict(DEFAULT_SUMMARY),  # Use copy of default summary
        'services': []  # External service health checks
    },
    'last_updated': None,
    'services_last_updated': None,  # Separate timestamp for external services
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
        now = datetime.now()
        STATE['last_updated'] = now
        # Also update services_last_updated when services are included
        if 'services' in updates:
            STATE['services_last_updated'] = now
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
        dict: Complete snapshot with 'data', 'last_updated', 'services_last_updated', 
              'status', 'error' keys. The 'data' dict contains references to the actual 
              lists/dicts (shallow copy) which is safe since we rebuild these on each update
    """
    with STATE_LOCK:
        return {
            'data': dict(STATE['data']),  # Shallow copy of data dict
            'last_updated': STATE['last_updated'],
            'services_last_updated': STATE['services_last_updated'],
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


def update_services_only(services):
    """Thread-safe update of services in STATE without changing status
    
    Updates only the services collection, preserving existing status/error.
    Used when external service checks succeed but GitLab API fails.
    Also updates services_last_updated so clients know when services were last checked.
    
    Args:
        services: List of service health check results
    """
    with STATE_LOCK:
        STATE['data']['services'] = services
        STATE['services_last_updated'] = datetime.now()
        # Don't change status or error - GitLab failure sets those


class BackgroundPoller(threading.Thread):
    """Background thread that polls GitLab API and updates global STATE
    
    Attributes:
        gitlab_client: GitLabAPIClient instance for API calls
        poll_interval: Seconds between poll cycles
        group_ids: List of GitLab group IDs to fetch projects from
        project_ids: List of specific GitLab project IDs to fetch
        external_services: List of external service configs for health checks
        service_latency_config: Configuration for service latency monitoring
            - enabled (bool): Whether latency tracking is enabled
            - window_size (int): Number of samples for running average
            - degradation_threshold_ratio (float): Warn if current > ratio × average
        slo_config: SLO (Service Level Objective) configuration
            - default_branch_success_target (float): Target success rate for default branch (0-1)
        _service_latency_history: Internal dict tracking per-service latency state.
            Keyed by service ID (string). Each entry contains:
            - average_ms (float): Running average latency in milliseconds
            - sample_count (int): Number of samples contributing to the average
            - recent_samples (list): Fixed-size list of most recent latency samples (ms)
            State persists across polls for the lifetime of the process.
    """
    
    def __init__(self, gitlab_client, poll_interval_sec, group_ids=None, project_ids=None,
                 external_services=None, service_latency_config=None, slo_config=None):
        super().__init__(daemon=True)
        self.gitlab_client = gitlab_client
        self.poll_interval = poll_interval_sec
        self.group_ids = group_ids or []
        self.project_ids = project_ids or []
        self.external_services = external_services if isinstance(external_services, list) else []
        # Service latency monitoring configuration
        # Provides settings for computing running average and degradation warnings
        # Use shallow copy to prevent mutation of the module-level constant
        self.service_latency_config = dict(service_latency_config) if service_latency_config else dict(DEFAULT_SERVICE_LATENCY_CONFIG)
        # SLO configuration for default-branch pipeline success rate target
        # Use shallow copy to prevent mutation of the module-level constant
        self.slo_config = dict(slo_config) if slo_config else dict(DEFAULT_SLO_CONFIG)
        self.running = True
        self.stop_event = threading.Event()
        self.poll_counter = 0
        
        # Per-service latency history for computing running averages and degradation detection
        # This state survives across polls for the lifetime of the poller process.
        # Structure per service ID:
        #   {
        #       'average_ms': <float>,       # Running average latency in milliseconds
        #       'sample_count': <int>,       # Number of samples in the running average
        #       'recent_samples': [<float>]  # Last N latency samples (bounded by window_size)
        #   }
        # If latency data is missing or malformed for a service, the current sample is used
        # alone without updating the historical state.
        self._service_latency_history = {}
        
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
        
        External service checks are decoupled from GitLab fetches - they run
        regardless of GitLab API success/failure so that service health 
        continues to refresh even during GitLab outages.
        
        Args:
            poll_id: Poll cycle identifier for logging context
        """
        logger.info(f"[poll_id={poll_id}] Starting data poll...")
        
        # Check external services FIRST - independent of GitLab
        # This ensures service health is always updated, even during GitLab outages
        services = self._check_external_services(poll_id)
        
        # Annotate services with latency metrics (running average, trend)
        # This must happen before any update to STATE
        services = self._annotate_services_with_latency_metrics(services, poll_id)
        
        # Fetch projects and pipelines
        projects = self._fetch_projects(poll_id)
        if projects is None:
            logger.error(f"[poll_id={poll_id}] Failed to fetch projects - API error")
            # Update services even though GitLab failed
            update_services_only(services)
            # Set error state so health endpoint reflects the GitLab failure
            set_state_error("Failed to fetch data from GitLab API", poll_id=poll_id)
            logger.error(f"[poll_id={poll_id}] Data poll completed with failures - state marked as ERROR (services still updated)")
            return
        
        # Fetch pipelines (pass projects to respect configured scope)
        # Returns dict with 'all_pipelines' (for /api/pipelines) and 'per_project' (for enrichment)
        pipeline_data = self._fetch_pipelines(projects, poll_id)
        if pipeline_data is None:
            logger.error(f"[poll_id={poll_id}] Failed to fetch pipelines - API error")
            # Update services even though GitLab failed
            update_services_only(services)
            # Set error state so health endpoint reflects the GitLab failure
            set_state_error("Failed to fetch data from GitLab API", poll_id=poll_id)
            logger.error(f"[poll_id={poll_id}] Data poll completed with failures - state marked as ERROR (services still updated)")
            return
        
        # Enrich projects with per-project pipeline health data
        enriched_projects = self._enrich_projects_with_pipelines(projects, pipeline_data['per_project'], poll_id)
        
        # Both fetches succeeded - calculate summary and update STATE atomically
        summary = self._calculate_summary(enriched_projects, pipeline_data['all_pipelines'])
        
        # Update all keys atomically with single timestamp and status
        update_state_atomic({
            'projects': enriched_projects,
            'pipelines': pipeline_data['all_pipelines'],
            'summary': summary,
            'services': services
        })
        
        logger.info(f"[poll_id={poll_id}] Updated STATE atomically: {len(enriched_projects)} projects, {len(pipeline_data['all_pipelines'])} pipelines, {len(services)} services")
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
            
            # Resolve merge request refs to their source branch names
            # This must happen before sorting so resolved refs are used in sorted results
            try:
                self.gitlab_client.resolve_merge_request_refs(all_pipelines, poll_id=poll_id)
            except Exception as e:
                logger.warning(f"{log_prefix}MR ref resolution failed, continuing with unmodified refs: {e}")
            
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
            
            # Resolve merge request refs to their source branch names
            # This must happen before building the per-project map
            try:
                self.gitlab_client.resolve_merge_request_refs(pipelines, poll_id=poll_id)
            except Exception as e:
                logger.warning(f"{log_prefix}MR ref resolution failed, continuing with unmodified refs: {e}")
            
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
        
        Delegates to the gitlab_client module's enrich_projects_with_pipelines function.
        """
        return enrich_projects_with_pipelines(projects, per_project_pipelines, poll_id)
    
    def _calculate_summary(self, projects, pipelines):
        """Calculate summary statistics
        
        Delegates to the gitlab_client module's get_summary function,
        then adds SLO metrics based on default-branch pipeline success.
        """
        summary = get_summary(projects, pipelines)
        
        # Compute and add SLO metrics for default-branch pipelines
        slo_metrics = self._compute_default_branch_slo(projects, pipelines)
        summary.update(slo_metrics)
        
        return summary
    
    def _compute_default_branch_slo(self, projects, pipelines):
        """Compute SLO metrics for default-branch pipelines
        
        Calculates success rate and error budget usage for pipelines
        targeting the default branch of each project.
        
        Args:
            projects: List of project dicts
            pipelines: List of pipeline dicts
        
        Returns:
            dict: SLO metrics with keys:
                - pipeline_slo_target_default_branch_success_rate (float)
                - pipeline_slo_observed_default_branch_success_rate (float)
                - pipeline_slo_total_default_branch_pipelines (int)
                - pipeline_error_budget_remaining_pct (int)
        """
        # Get target from SLO config
        target_rate = self.slo_config.get(
            'default_branch_success_target', 
            DEFAULT_SLO_CONFIG['default_branch_success_target']
        )
        
        # Build project_id -> default_branch map
        project_default_branches = {}
        for project in (projects or []):
            project_id = project.get('id')
            if project_id is not None:
                default_branch = project.get('default_branch', DEFAULT_BRANCH_NAME)
                project_default_branches[project_id] = default_branch
        
        # Filter pipelines to default-branch only, excluding ignored statuses
        total_default_branch = 0
        successful_default_branch = 0
        
        for pipeline in (pipelines or []):
            project_id = pipeline.get('project_id')
            
            # Skip pipelines without project_id or not in our projects
            if project_id is None or project_id not in project_default_branches:
                continue
            
            default_branch = project_default_branches[project_id]
            pipeline_ref = pipeline.get('ref')
            
            # Skip pipelines not on default branch
            if pipeline_ref != default_branch:
                continue
            
            # Skip ignored statuses (skipped, manual, canceled)
            status = pipeline.get('status')
            if status in IGNORED_PIPELINE_STATUSES:
                continue
            
            # Count meaningful default-branch pipelines
            total_default_branch += 1
            if status == 'success':
                successful_default_branch += 1
        
        # Compute observed success rate
        # If no meaningful pipelines, treat as 100% success (no error budget consumed)
        if total_default_branch > 0:
            observed_success_rate = successful_default_branch / total_default_branch
        else:
            observed_success_rate = 1.0
        
        # Compute error budget
        # error_budget_total = 1 - target_rate (with minimum to avoid div by zero)
        error_budget_total = max(1e-9, 1.0 - target_rate)
        
        # error_budget_spent_fraction = how much of the budget is consumed
        # (1 - observed_rate) / error_budget_total, clamped to [0, 1]
        error_budget_spent_fraction = max(0.0, min(1.0, 
            (1.0 - observed_success_rate) / error_budget_total
        ))
        
        # error_budget_remaining_pct = percentage of budget remaining
        error_budget_remaining_pct = round((1.0 - error_budget_spent_fraction) * 100)
        # Clamp to [0, 100]
        error_budget_remaining_pct = max(0, min(100, error_budget_remaining_pct))
        
        return {
            'pipeline_slo_target_default_branch_success_rate': target_rate,
            'pipeline_slo_observed_default_branch_success_rate': observed_success_rate,
            'pipeline_slo_total_default_branch_pipelines': total_default_branch,
            'pipeline_error_budget_remaining_pct': error_budget_remaining_pct,
        }
    
    def _check_external_services(self, poll_id=None):
        """Check health of configured external services
        
        Delegates to the services module's get_service_statuses function.
        """
        # Get SSL context from GitLab client if available
        ssl_context = None
        if self.gitlab_client:
            ssl_context = self.gitlab_client.ssl_context
        
        return get_service_statuses(
            self.external_services,
            ssl_context=ssl_context,
            poll_id=poll_id
        )
    
    def _annotate_services_with_latency_metrics(self, services, poll_id=None):
        """Annotate services with running average latency and trend
        
        Updates per-service latency state and adds computed metrics to each 
        service dict when latency monitoring is enabled.
        
        Args:
            services: List of service dicts from get_service_statuses()
            poll_id: Poll cycle identifier for logging context
        
        Returns:
            list: The same services list, with added latency metrics fields
                  when monitoring is enabled. Existing fields are preserved.
        
        Added fields (when enabled and latency_ms is available):
            - average_latency_ms: Running average latency in milliseconds
            - latency_ratio: current latency / average (if average > 0)
            - latency_trend: "normal" or "warning" based on degradation threshold
        """
        log_prefix = f"[poll_id={poll_id}] " if poll_id else ""
        
        # Check if latency monitoring is enabled
        if not self.service_latency_config.get('enabled', True):
            logger.debug(f"{log_prefix}Service latency monitoring disabled, skipping annotation")
            return services
        
        window_size = self.service_latency_config.get('window_size', 10)
        threshold_ratio = self.service_latency_config.get('degradation_threshold_ratio', 1.5)
        
        for service in services:
            service_id = service.get('id')
            if not service_id:
                continue
            
            latency_ms = service.get('latency_ms')
            
            # Skip services without valid latency (timeout, error, or None)
            if latency_ms is None or not isinstance(latency_ms, (int, float)):
                logger.debug(f"{log_prefix}Service {service_id}: no valid latency, skipping annotation")
                continue
            
            # Get or initialize per-service latency history
            if service_id not in self._service_latency_history:
                # First sample for this service
                self._service_latency_history[service_id] = {
                    'average_ms': latency_ms,
                    'sample_count': 1,
                    'recent_samples': [latency_ms]
                }
                # For first sample, average equals current, ratio is 1.0, trend is normal
                service['average_latency_ms'] = round(latency_ms, 2)
                service['latency_ratio'] = 1.0
                service['latency_trend'] = 'normal'
                continue
            
            history = self._service_latency_history[service_id]
            
            # Update recent_samples (bounded by window_size)
            recent_samples = history.get('recent_samples', [])
            recent_samples.append(latency_ms)
            if len(recent_samples) > window_size:
                recent_samples = recent_samples[-window_size:]
            
            # Compute running average from recent samples
            sample_count = len(recent_samples)
            average_ms = sum(recent_samples) / sample_count if sample_count > 0 else latency_ms
            
            # Store updated history
            self._service_latency_history[service_id] = {
                'average_ms': average_ms,
                'sample_count': sample_count,
                'recent_samples': recent_samples
            }
            
            # Compute latency ratio (current / average)
            if average_ms > 0:
                latency_ratio = latency_ms / average_ms
            else:
                latency_ratio = 1.0
            
            # Determine latency trend
            previous_trend = service.get('latency_trend')
            if latency_ratio > threshold_ratio:
                latency_trend = 'warning'
                # Log at debug level when transitioning into warning
                if previous_trend != 'warning':
                    logger.debug(
                        f"{log_prefix}Service {service_id} latency degraded: "
                        f"{latency_ms:.1f}ms vs avg {average_ms:.1f}ms "
                        f"(ratio {latency_ratio:.2f} > threshold {threshold_ratio})"
                    )
            else:
                latency_trend = 'normal'
            
            # Add computed fields to service dict
            service['average_latency_ms'] = round(average_ms, 2)
            service['latency_ratio'] = round(latency_ratio, 2)
            service['latency_trend'] = latency_trend
        
        return services
    
    def stop(self):
        """Stop the polling thread"""
        logger.info("Stopping background poller")
        self.running = False
        self.stop_event.set()  # Wake up the thread if it's sleeping


class DashboardRequestHandler(SimpleHTTPRequestHandler):
    """Custom HTTP request handler for the dashboard"""
    
    # Explicit MIME type mappings for JavaScript files
    # This fixes the "MIME type text/plain" error on systems where mimetypes.guess_type()
    # doesn't return the correct MIME type for .js files (e.g., some Windows/macOS configs)
    # The browser's strict MIME type checking requires application/javascript for ES modules
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        '.js': 'application/javascript',
        '.mjs': 'application/javascript',
        '.css': 'text/css',
        '.html': 'text/html',
        '.json': 'application/json',
    }
    
    def __init__(self, *args, **kwargs):
        # Set the directory to serve static files from (relative to project root)
        frontend_dir = os.path.join(PROJECT_ROOT, 'frontend')
        super().__init__(*args, directory=frontend_dir, **kwargs)
    
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
        elif path == '/api/services':
            self.handle_services()
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
                    'consecutive_default_branch_failures': project.get('consecutive_default_branch_failures', 0),
                    # DSO health fields (for dashboard tiles):
                    # - has_failing_jobs: True if recent default-branch pipelines contain any with 'failed' status (excludes skipped/manual/canceled)
                    # - failing_jobs_count: Count of pipelines with 'failed' status on default branch (excludes skipped/manual/canceled)
                    # - has_runner_issues: True if pipelines are failing due to runner problems
                    'has_failing_jobs': project.get('has_failing_jobs', False),
                    'failing_jobs_count': project.get('failing_jobs_count', 0),
                    'has_runner_issues': project.get('has_runner_issues', False)
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
            
            # Build project_id to metadata map for enriching pipelines
            project_metadata_map = {}
            if projects:
                for project in projects:
                    project_id = project.get('id')
                    if project_id:
                        project_metadata_map[project_id] = {
                            'path_with_namespace': project.get('path_with_namespace', ''),
                            'default_branch': project.get('default_branch', DEFAULT_BRANCH_NAME),
                            'has_runner_issues': project.get('has_runner_issues', False),
                            'has_failing_jobs': project.get('has_failing_jobs', False),
                        }
            
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
                project_metadata = project_metadata_map.get(project_id, {})
                project_path = project_metadata.get('path_with_namespace', '')
                default_branch = project_metadata.get('default_branch', DEFAULT_BRANCH_NAME)
                pipeline_ref = pipeline.get('ref', '')
                is_default_branch = (pipeline_ref == default_branch)
                
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
                    'duration': pipeline.get('duration'),
                    # DSO emphasis fields for highlighting default-branch and infra issues
                    'is_default_branch': is_default_branch,
                    'has_runner_issues': project_metadata.get('has_runner_issues', False),
                    'has_failing_jobs': project_metadata.get('has_failing_jobs', False),
                }
                # Add MR-specific fields only if present (for merge request pipelines)
                if 'original_ref' in pipeline:
                    formatted['original_ref'] = pipeline['original_ref']
                if 'merge_request_iid' in pipeline:
                    formatted['merge_request_iid'] = pipeline['merge_request_iid']
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
    
    def handle_services(self):
        """Handle /api/services endpoint
        
        Returns the current health status of configured external services.
        Always returns proper JSON shape even when data is empty or initializing.
        Uses atomic snapshot from in-memory STATE to prevent torn reads.
        """
        try:
            # Get atomic snapshot of STATE (single lock acquisition)
            snapshot = get_state_snapshot()
            services = snapshot['data'].get('services')
            
            # Ensure services is never None (use empty list if None)
            if services is None:
                services = []
            
            # Use services-specific timestamp (falls back to main timestamp if not set)
            services_ts = snapshot['services_last_updated'] or snapshot['last_updated']
            
            response = {
                'services': services,
                'total': len(services),
                'last_updated': services_ts.isoformat() if isinstance(services_ts, datetime) else str(services_ts) if services_ts else None,
                'backend_status': snapshot['status'],
                'is_mock': MOCK_MODE_ENABLED
            }
            
            self.send_json_response(response)
            
        except Exception as e:
            logger.error(f"Error in handle_services: {e}")
            # Even on error, return proper shape with empty array
            self.send_json_response({
                'services': [],
                'total': 0,
                'last_updated': None,
                'backend_status': 'ERROR',
                'is_mock': MOCK_MODE_ENABLED,
                'error': str(e)
            }, status=500)
    
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
            # Use services from mock data if present, otherwise empty list
            services = mock_data.get('services', [])
            update_state_atomic({
                'projects': mock_data['repositories'],
                'pipelines': mock_data['pipelines'],
                'summary': mock_data['summary'],
                'services': services
            })
            
            # Get the timestamp that was just set (using atomic snapshot)
            snapshot = get_state_snapshot()
            timestamp_iso = snapshot['last_updated'].isoformat() if isinstance(snapshot['last_updated'], datetime) else str(snapshot['last_updated'])
            
            logger.info("Mock data reloaded successfully via API")
            logger.info(f"  Repositories: {len(mock_data['repositories'])}")
            logger.info(f"  Pipelines: {len(mock_data['pipelines'])}")
            logger.info(f"  Services: {len(services)}")
            
            self.send_json_response({
                'reloaded': True,
                'is_mock': True,
                'backend_status': snapshot['status'],
                'last_updated': timestamp_iso,
                'timestamp': timestamp_iso,  # Deprecated: use last_updated (kept for backward compatibility)
                'scenario': MOCK_SCENARIO if MOCK_SCENARIO else 'default',
                'summary': {
                    'repositories': len(mock_data['repositories']),
                    'pipelines': len(mock_data['pipelines']),
                    'services': len(services)
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


# Note: parse_int_config, parse_csv_list, load_config, validate_config, and load_mock_data
# are now imported from backend.config_loader


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
            mock_file_path = os.path.join(PROJECT_ROOT, 'data', 'mock_scenarios', f'{MOCK_SCENARIO}.json')
        else:
            mock_file_path = os.path.join(PROJECT_ROOT, 'mock_data.json')
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
            return 1
        
        # Initialize STATE with mock data
        # Use services from mock data if present, otherwise empty list
        services = mock_data.get('services', [])
        update_state_atomic({
            'projects': mock_data['repositories'],
            'pipelines': mock_data['pipelines'],
            'summary': mock_data['summary'],
            'services': services
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
            project_ids=config['project_ids'],
            external_services=config.get('external_services', []),
            service_latency_config=config.get('service_latency'),
            slo_config=config.get('slo')
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

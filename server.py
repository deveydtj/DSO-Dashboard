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
            self.ssl_context = ssl._create_unverified_context()
            logger.warning("SSL verification disabled - using unverified SSL context")
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
                    wait_time = int(retry_after)
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
        data = response.read().decode('utf-8')
        parsed_data = json.loads(data)
        
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
            
            data = result['data']
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
            return result['data'] if result else None
        else:
            # Full pagination for all projects
            return self._make_paginated_request('projects', {'membership': 'true'})
    
    def get_group_projects(self, group_id):
        """Get all projects in a group with pagination"""
        return self._make_paginated_request(f'groups/{group_id}/projects')
    
    def get_project(self, project_id):
        """Get single project details"""
        result = self._make_request(f'projects/{project_id}')
        return result['data'] if result else None
    
    def get_pipelines(self, project_id, per_page=None):
        """Get pipelines for a project with pagination"""
        if per_page:
            # For backward compatibility, use single page request
            result = self._make_request(f'projects/{project_id}/pipelines', {'per_page': per_page})
            return result['data'] if result else None
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
    """Thread-safe update of global STATE"""
    with STATE_LOCK:
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
        
    def run(self):
        """Main polling loop"""
        logger.info("Background poller started")
        
        while self.running:
            try:
                self.poll_data()
            except Exception as e:
                logger.error(f"Error in background poller: {e}")
                set_state_error(e)
            
            # Sleep for poll interval
            logger.debug(f"Sleeping for {self.poll_interval}s before next poll")
            time.sleep(self.poll_interval)
    
    def poll_data(self):
        """Poll GitLab API and update STATE"""
        logger.info("Starting data poll...")
        
        # Fetch projects
        projects = self._fetch_projects()
        if projects is not None:
            update_state('projects', projects)
            logger.info(f"Updated projects in STATE: {len(projects)} projects")
        
        # Fetch pipelines
        pipelines = self._fetch_pipelines()
        if pipelines is not None:
            update_state('pipelines', pipelines)
            logger.info(f"Updated pipelines in STATE: {len(pipelines)} pipelines")
        
        # Calculate summary
        summary = self._calculate_summary(projects, pipelines)
        update_state('summary', summary)
        logger.info("Updated summary in STATE")
        
        logger.info("Data poll completed successfully")
    
    def _fetch_projects(self):
        """Fetch projects from configured sources"""
        all_projects = []
        
        # Fetch from specific project IDs if configured
        if self.project_ids:
            logger.info(f"Fetching {len(self.project_ids)} specific projects")
            for project_id in self.project_ids:
                project = self.gitlab_client.get_project(project_id)
                if project:
                    all_projects.append(project)
        
        # Fetch from groups if configured
        if self.group_ids:
            logger.info(f"Fetching projects from {len(self.group_ids)} groups")
            for group_id in self.group_ids:
                logger.info(f"Fetching projects for group {group_id}")
                group_projects = self.gitlab_client.get_group_projects(group_id)
                if group_projects:
                    all_projects.extend(group_projects)
                    logger.info(f"Added {len(group_projects)} projects from group {group_id}")
        
        # If no specific sources configured, fetch all accessible projects
        if not self.project_ids and not self.group_ids:
            logger.info("Fetching all accessible projects")
            projects = self.gitlab_client.get_projects()
            if projects:
                all_projects = projects
        
        return all_projects if all_projects else None
    
    def _fetch_pipelines(self):
        """Fetch pipelines across projects"""
        return self.gitlab_client.get_all_pipelines(per_page=50)
    
    def _calculate_summary(self, projects, pipelines):
        """Calculate summary statistics"""
        if projects is None:
            projects = []
        if pipelines is None:
            pipelines = []
        
        total_repos = len(projects)
        active_repos = len([p for p in projects if p.get('last_activity_at')])
        
        # Pipeline statistics
        pipeline_statuses = {}
        for pipeline in pipelines:
            status = pipeline.get('status', 'unknown')
            pipeline_statuses[status] = pipeline_statuses.get(status, 0) + 1
        
        return {
            'total_repositories': total_repos,
            'active_repositories': active_repos,
            'total_pipelines': len(pipelines),
            'successful_pipelines': pipeline_statuses.get('success', 0),
            'failed_pipelines': pipeline_statuses.get('failed', 0),
            'running_pipelines': pipeline_statuses.get('running', 0),
            'pipeline_statuses': pipeline_statuses,
            'last_updated': datetime.now().isoformat()
        }
    
    def stop(self):
        """Stop the polling thread"""
        logger.info("Stopping background poller")
        self.running = False


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
            
            if summary is None:
                # If no data yet, return initializing status
                status_info = get_state_status()
                if status_info['status'] == 'INITIALIZING':
                    self.send_json_response({
                        'status': 'initializing',
                        'message': 'Dashboard is initializing, please wait...'
                    }, status=503)
                else:
                    self.send_json_response({'error': 'No summary data available'}, status=500)
                return
            
            self.send_json_response(summary)
            
        except Exception as e:
            logger.error(f"Error in handle_summary: {e}")
            self.send_json_response({'error': str(e)}, status=500)
    
    def handle_repos(self):
        """Handle /api/repos endpoint"""
        try:
            projects = get_state('projects')
            
            if projects is None:
                status_info = get_state_status()
                if status_info['status'] == 'INITIALIZING':
                    self.send_json_response({
                        'status': 'initializing',
                        'message': 'Dashboard is initializing, please wait...'
                    }, status=503)
                else:
                    self.send_json_response({'error': 'No projects data available'}, status=500)
                return
            
            # Format repository data
            repos = []
            for project in projects:
                repo = {
                    'id': project.get('id'),
                    'name': project.get('name'),
                    'description': project.get('description', ''),
                    'web_url': project.get('web_url'),
                    'last_activity_at': project.get('last_activity_at'),
                    'star_count': project.get('star_count', 0),
                    'forks_count': project.get('forks_count', 0),
                    'open_issues_count': project.get('open_issues_count', 0),
                    'default_branch': project.get('default_branch', 'main'),
                    'visibility': project.get('visibility', 'private')
                }
                repos.append(repo)
            
            response = {
                'repositories': repos,
                'total': len(repos),
                'last_updated': datetime.now().isoformat()
            }
            
            self.send_json_response(response)
            
        except Exception as e:
            logger.error(f"Error in handle_repos: {e}")
            self.send_json_response({'error': str(e)}, status=500)
    
    def handle_pipelines(self):
        """Handle /api/pipelines endpoint"""
        try:
            pipelines = get_state('pipelines')
            
            if pipelines is None:
                status_info = get_state_status()
                if status_info['status'] == 'INITIALIZING':
                    self.send_json_response({
                        'status': 'initializing',
                        'message': 'Dashboard is initializing, please wait...'
                    }, status=503)
                else:
                    self.send_json_response({'error': 'No pipelines data available'}, status=500)
                return
            
            # Format pipeline data
            formatted_pipelines = []
            for pipeline in pipelines:
                formatted = {
                    'id': pipeline.get('id'),
                    'project_id': pipeline.get('project_id'),
                    'project_name': pipeline.get('project_name', 'Unknown'),
                    'status': pipeline.get('status'),
                    'ref': pipeline.get('ref'),
                    'sha': pipeline.get('sha', '')[:8],  # Short SHA
                    'web_url': pipeline.get('web_url'),
                    'created_at': pipeline.get('created_at'),
                    'updated_at': pipeline.get('updated_at'),
                    'duration': pipeline.get('duration')
                }
                formatted_pipelines.append(formatted)
            
            response = {
                'pipelines': formatted_pipelines,
                'total': len(formatted_pipelines),
                'last_updated': datetime.now().isoformat()
            }
            
            self.send_json_response(response)
            
        except Exception as e:
            logger.error(f"Error in handle_pipelines: {e}")
            self.send_json_response({'error': str(e)}, status=500)
    
    def handle_health(self):
        """Handle /api/health endpoint"""
        try:
            status_info = get_state_status()
            
            health = {
                'status': 'healthy' if status_info['status'] in ['ONLINE', 'INITIALIZING'] else 'unhealthy',
                'backend_status': status_info['status'],
                'timestamp': datetime.now().isoformat(),
                'last_poll': status_info['last_updated'].isoformat() if status_info['last_updated'] else None,
                'error': status_info['error']
            }
            
            # Return 200 OK for ONLINE and INITIALIZING (system is working)
            # Return 503 only for ERROR state
            status_code = 200 if status_info['status'] in ['ONLINE', 'INITIALIZING'] else 503
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
    
    # Load from environment variables (with fallback to config.json values)
    config.setdefault('gitlab_url', os.environ.get('GITLAB_URL', config.get('gitlab_url', 'https://gitlab.com')))
    config.setdefault('api_token', os.environ.get('GITLAB_API_TOKEN', config.get('api_token', '')))
    config.setdefault('group_ids', os.environ.get('GITLAB_GROUP_IDS', '').split(',') if os.environ.get('GITLAB_GROUP_IDS') else config.get('group_ids', []))
    config.setdefault('project_ids', os.environ.get('GITLAB_PROJECT_IDS', '').split(',') if os.environ.get('GITLAB_PROJECT_IDS') else config.get('project_ids', []))
    config.setdefault('port', int(os.environ.get('PORT', config.get('port', 8080))))
    config.setdefault('cache_ttl_sec', int(os.environ.get('CACHE_TTL', config.get('cache_ttl_sec', 300))))
    config.setdefault('poll_interval_sec', int(os.environ.get('POLL_INTERVAL', config.get('poll_interval_sec', 60))))
    config.setdefault('per_page', int(os.environ.get('PER_PAGE', config.get('per_page', 100))))
    config.setdefault('insecure_skip_verify', os.environ.get('INSECURE_SKIP_VERIFY', '').lower() in ['true', '1', 'yes'] or config.get('insecure_skip_verify', False))
    
    # Filter out empty strings from group_ids and project_ids
    config['group_ids'] = [gid.strip() for gid in config['group_ids'] if gid.strip()]
    config['project_ids'] = [pid.strip() for pid in config['project_ids'] if pid.strip()]
    
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
        httpd.shutdown()
        logger.info("Server stopped.")


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
GitLab Dashboard Backend Server
Python 3.10 stdlib-only implementation using http.server and urllib
"""

import json
import os
import sys
import time
import threading
from datetime import datetime, timedelta
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import urlparse, parse_qs
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GitLabAPIClient:
    """GitLab API client using urllib"""
    
    def __init__(self, gitlab_url, api_token):
        self.gitlab_url = gitlab_url.rstrip('/')
        self.api_token = api_token
        self.base_url = f"{self.gitlab_url}/api/v4"
        
    def _make_request(self, endpoint, params=None):
        """Make a request to GitLab API"""
        url = f"{self.base_url}/{endpoint}"
        
        if params:
            query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
            url = f"{url}?{query_string}"
        
        headers = {
            'PRIVATE-TOKEN': self.api_token,
            'Content-Type': 'application/json'
        }
        
        try:
            request = Request(url, headers=headers)
            with urlopen(request, timeout=10) as response:
                data = response.read().decode('utf-8')
                return json.loads(data)
        except HTTPError as e:
            logger.error(f"HTTP Error {e.code}: {e.reason} for {url}")
            return None
        except URLError as e:
            logger.error(f"URL Error: {e.reason} for {url}")
            return None
        except Exception as e:
            logger.error(f"Error making request to {url}: {e}")
            return None
    
    def get_projects(self, per_page=20):
        """Get list of projects"""
        return self._make_request('projects', {'per_page': per_page, 'membership': 'true'})
    
    def get_project(self, project_id):
        """Get single project details"""
        return self._make_request(f'projects/{project_id}')
    
    def get_pipelines(self, project_id, per_page=10):
        """Get pipelines for a project"""
        return self._make_request(f'projects/{project_id}/pipelines', {'per_page': per_page})
    
    def get_all_pipelines(self, per_page=20):
        """Get recent pipelines across all projects"""
        projects = self.get_projects(per_page=10)
        if not projects:
            return []
        
        all_pipelines = []
        for project in projects[:5]:  # Limit to first 5 projects
            pipelines = self.get_pipelines(project['id'], per_page=5)
            if pipelines:
                for pipeline in pipelines:
                    pipeline['project_name'] = project['name']
                    pipeline['project_id'] = project['id']
                    all_pipelines.append(pipeline)
        
        # Sort by created_at descending
        all_pipelines.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        return all_pipelines[:per_page]


class DataCache:
    """Simple in-memory cache with TTL"""
    
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
        cache_key = 'summary'
        cached_data = self.server.cache.get(cache_key)
        
        if cached_data:
            self.send_json_response(cached_data)
            return
        
        try:
            projects = self.server.gitlab_client.get_projects(per_page=100)
            pipelines = self.server.gitlab_client.get_all_pipelines(per_page=50)
            
            if projects is None:
                projects = []
            if pipelines is None:
                pipelines = []
            
            # Calculate summary statistics
            total_repos = len(projects)
            active_repos = len([p for p in projects if p.get('last_activity_at')])
            
            # Pipeline statistics
            pipeline_statuses = {}
            for pipeline in pipelines:
                status = pipeline.get('status', 'unknown')
                pipeline_statuses[status] = pipeline_statuses.get(status, 0) + 1
            
            summary = {
                'total_repositories': total_repos,
                'active_repositories': active_repos,
                'total_pipelines': len(pipelines),
                'successful_pipelines': pipeline_statuses.get('success', 0),
                'failed_pipelines': pipeline_statuses.get('failed', 0),
                'running_pipelines': pipeline_statuses.get('running', 0),
                'pipeline_statuses': pipeline_statuses,
                'last_updated': datetime.now().isoformat()
            }
            
            self.server.cache.set(cache_key, summary)
            self.send_json_response(summary)
            
        except Exception as e:
            logger.error(f"Error in handle_summary: {e}")
            self.send_json_response({'error': str(e)}, status=500)
    
    def handle_repos(self):
        """Handle /api/repos endpoint"""
        cache_key = 'repos'
        cached_data = self.server.cache.get(cache_key)
        
        if cached_data:
            self.send_json_response(cached_data)
            return
        
        try:
            projects = self.server.gitlab_client.get_projects(per_page=20)
            
            if projects is None:
                projects = []
            
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
            
            self.server.cache.set(cache_key, response)
            self.send_json_response(response)
            
        except Exception as e:
            logger.error(f"Error in handle_repos: {e}")
            self.send_json_response({'error': str(e)}, status=500)
    
    def handle_pipelines(self):
        """Handle /api/pipelines endpoint"""
        cache_key = 'pipelines'
        cached_data = self.server.cache.get(cache_key)
        
        if cached_data:
            self.send_json_response(cached_data)
            return
        
        try:
            pipelines = self.server.gitlab_client.get_all_pipelines(per_page=30)
            
            if pipelines is None:
                pipelines = []
            
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
            
            self.server.cache.set(cache_key, response)
            self.send_json_response(response)
            
        except Exception as e:
            logger.error(f"Error in handle_pipelines: {e}")
            self.send_json_response({'error': str(e)}, status=500)
    
    def handle_health(self):
        """Handle /api/health endpoint"""
        health = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'cache_entries': len(self.server.cache.cache)
        }
        self.send_json_response(health)
    
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
    """Custom HTTP server with GitLab client and cache"""
    
    def __init__(self, server_address, RequestHandlerClass, gitlab_client, cache):
        super().__init__(server_address, RequestHandlerClass)
        self.gitlab_client = gitlab_client
        self.cache = cache


def load_config():
    """Load configuration from environment variables"""
    config = {
        'gitlab_url': os.environ.get('GITLAB_URL', 'https://gitlab.com'),
        'api_token': os.environ.get('GITLAB_API_TOKEN', ''),
        'port': int(os.environ.get('PORT', '8080')),
        'cache_ttl': int(os.environ.get('CACHE_TTL', '300'))  # 5 minutes default
    }
    
    if not config['api_token']:
        logger.warning("GITLAB_API_TOKEN not set. API requests will fail.")
        logger.warning("Set GITLAB_API_TOKEN environment variable to enable GitLab API access.")
    
    return config


def main():
    """Main entry point"""
    logger.info("Starting GitLab Dashboard Server...")
    
    # Load configuration
    config = load_config()
    logger.info(f"Configuration loaded:")
    logger.info(f"  GitLab URL: {config['gitlab_url']}")
    logger.info(f"  Port: {config['port']}")
    logger.info(f"  Cache TTL: {config['cache_ttl']} seconds")
    
    # Initialize GitLab client and cache
    gitlab_client = GitLabAPIClient(config['gitlab_url'], config['api_token'])
    cache = DataCache(ttl_seconds=config['cache_ttl'])
    
    # Create server
    server_address = ('', config['port'])
    httpd = DashboardServer(server_address, DashboardRequestHandler, gitlab_client, cache)
    
    logger.info(f"Server running at http://localhost:{config['port']}/")
    logger.info("Press Ctrl+C to stop the server")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("\nShutting down server...")
        httpd.shutdown()
        logger.info("Server stopped.")


if __name__ == '__main__':
    main()

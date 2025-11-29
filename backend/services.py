#!/usr/bin/env python3
"""
External Services Health Check Module for DSO-Dashboard

Handles health checks for external services (Artifactory, Confluence, Jira, etc.).
Used by the /api/services endpoint to provide service status monitoring.

This module uses only Python standard library (no pip dependencies).
"""

import logging
import time
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

# Default timeout for external service checks (seconds)
DEFAULT_SERVICE_CHECK_TIMEOUT = 10


def get_service_statuses(external_services, ssl_context=None, poll_id=None):
    """Check health of configured external services
    
    For each configured external service:
    - Makes a HEAD request (fallback to GET if needed)
    - Classifies the result as UP or DOWN
    - Captures latency, status code, and any error message
    
    Args:
        external_services: List of service configuration dicts. Each dict should have:
            - url (required): Service URL to check
            - name (optional): Human-readable service name
            - id (optional): Stable service identifier
            - timeout (optional): Request timeout in seconds
        ssl_context: Optional SSL context for HTTPS requests
        poll_id: Poll cycle identifier for logging context
    
    Returns:
        list: List of dicts with service health data, each containing:
            - id: Stable service identifier
            - name: Human-readable service name
            - url: Service URL
            - status: 'UP' or 'DOWN'
            - latency_ms: Response time in milliseconds
            - last_checked: ISO timestamp of check
            - http_status: HTTP status code (if applicable)
            - error: Error message (if any)
    """
    log_prefix = f"[poll_id={poll_id}] " if poll_id else ""
    
    if not external_services:
        logger.debug(f"{log_prefix}No external services configured")
        return []
    
    results = []
    
    for service_config in external_services:
        # Skip invalid entries
        if not isinstance(service_config, dict):
            logger.warning(f"{log_prefix}Skipping invalid service config (not a dict): {service_config}")
            continue
        
        url = service_config.get('url')
        if not url:
            logger.warning(f"{log_prefix}Skipping service config with missing URL: {service_config}")
            continue
        
        # Resolve human-readable name (prefer name, then id, then url)
        name = service_config.get('name') or service_config.get('id') or url
        
        # Generate stable service ID
        service_id = service_config.get('id')
        if not service_id:
            # Normalize name to create a stable ID
            service_id = name.lower().replace(' ', '-').replace('/', '-')
        
        # Get timeout (use default if not provided)
        timeout = service_config.get('timeout', DEFAULT_SERVICE_CHECK_TIMEOUT)
        try:
            timeout = int(timeout)
            if timeout <= 0:
                timeout = DEFAULT_SERVICE_CHECK_TIMEOUT
        except (ValueError, TypeError):
            timeout = DEFAULT_SERVICE_CHECK_TIMEOUT
        
        # Check the service
        result = _check_single_service(
            url=url,
            name=name,
            service_id=service_id,
            timeout=timeout,
            ssl_context=ssl_context,
            poll_id=poll_id
        )
        results.append(result)
    
    # Log summary
    up_count = sum(1 for r in results if r.get('status') == 'UP')
    down_count = len(results) - up_count
    logger.info(f"{log_prefix}Checked {len(results)} external services: {up_count} UP, {down_count} DOWN")
    
    return results


def _check_single_service(url, name, service_id, timeout, ssl_context=None, poll_id=None):
    """Check health of a single external service
    
    Performs a HEAD request first, falling back to GET if HEAD is not allowed.
    
    Args:
        url: Service URL to check
        name: Human-readable service name
        service_id: Stable service identifier
        timeout: Request timeout in seconds
        ssl_context: Optional SSL context for HTTPS requests
        poll_id: Poll cycle identifier for logging context
    
    Returns:
        dict: Service health data with id, name, url, status, latency_ms, 
              last_checked, http_status, and error fields
    """
    log_prefix = f"[poll_id={poll_id}] " if poll_id else ""
    
    result = {
        'id': service_id,
        'name': name,
        'url': url,
        'status': 'DOWN',
        'latency_ms': None,
        'last_checked': datetime.now().isoformat(),
        'http_status': None,
        'error': None
    }
    
    start_time = time.monotonic()
    
    try:
        # Try HEAD request first (lighter weight)
        request = Request(url, method='HEAD')
        request.add_header('User-Agent', 'DSO-Dashboard-ServiceCheck/1.0')
        
        try:
            if ssl_context:
                response = urlopen(request, timeout=timeout, context=ssl_context)
            else:
                response = urlopen(request, timeout=timeout)
            
            elapsed_ms = (time.monotonic() - start_time) * 1000
            http_status = response.status
            response.close()
            
        except HTTPError as e:
            # HEAD might return 405 Method Not Allowed, try GET
            if e.code == 405:
                logger.debug(f"{log_prefix}HEAD not allowed for {name}, trying GET")
                start_time = time.monotonic()  # Reset timer for GET
                request = Request(url)
                request.add_header('User-Agent', 'DSO-Dashboard-ServiceCheck/1.0')
                
                if ssl_context:
                    response = urlopen(request, timeout=timeout, context=ssl_context)
                else:
                    response = urlopen(request, timeout=timeout)
                
                elapsed_ms = (time.monotonic() - start_time) * 1000
                http_status = response.status
                response.close()
            else:
                # Other HTTP errors
                elapsed_ms = (time.monotonic() - start_time) * 1000
                http_status = e.code
                
                # 2xx and 3xx are considered UP
                if 200 <= http_status < 400:
                    result['status'] = 'UP'
                else:
                    result['error'] = f"HTTP {http_status}: {e.reason}"
                
                result['latency_ms'] = round(elapsed_ms, 2)
                result['http_status'] = http_status
                logger.debug(f"{log_prefix}Service {name}: HTTP {http_status} in {elapsed_ms:.1f}ms")
                return result
        
        # Successful response (2xx or 3xx)
        result['latency_ms'] = round(elapsed_ms, 2)
        result['http_status'] = http_status
        
        if 200 <= http_status < 400:
            result['status'] = 'UP'
        else:
            result['status'] = 'DOWN'
            result['error'] = f"HTTP {http_status}"
        
        logger.debug(f"{log_prefix}Service {name}: {result['status']} HTTP {http_status} in {elapsed_ms:.1f}ms")
        
    except HTTPError as e:
        elapsed_ms = (time.monotonic() - start_time) * 1000
        result['latency_ms'] = round(elapsed_ms, 2)
        result['http_status'] = e.code
        result['error'] = f"HTTP {e.code}: {e.reason}"
        
        # 2xx and 3xx are considered UP
        if 200 <= e.code < 400:
            result['status'] = 'UP'
        
        logger.debug(f"{log_prefix}Service {name}: DOWN HTTP {e.code} in {elapsed_ms:.1f}ms")
        
    except URLError as e:
        elapsed_ms = (time.monotonic() - start_time) * 1000
        result['latency_ms'] = round(elapsed_ms, 2)
        result['error'] = str(e.reason)
        logger.debug(f"{log_prefix}Service {name}: DOWN URLError {e.reason} in {elapsed_ms:.1f}ms")
        
    except Exception as e:
        elapsed_ms = (time.monotonic() - start_time) * 1000
        result['latency_ms'] = round(elapsed_ms, 2)
        result['error'] = str(e)
        logger.debug(f"{log_prefix}Service {name}: DOWN Error {e} in {elapsed_ms:.1f}ms")
    
    return result

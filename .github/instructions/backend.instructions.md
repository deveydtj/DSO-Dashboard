---
applyTo:
  - "backend/app.py"
  - "backend/*.py"
  - "*.py"
---

# Backend Instructions (Python Standard Library Only)

## Absolute Rule: Stdlib Only

**NEVER suggest or add external dependencies.** This backend must remain pure Python standard library.

### Prohibited Libraries
- ❌ `requests` - Use `urllib.request` instead
- ❌ `Flask`, `FastAPI`, `Django` - Use `http.server` instead
- ❌ `aiohttp`, `httpx` - Use `urllib.request` instead
- ❌ `pytest` - Use `unittest` instead
- ❌ Any pip-installable package

### Allowed Libraries (stdlib only)
- ✅ `http.server` - HTTP server
- ✅ `urllib.request`, `urllib.parse` - HTTP client and URL utilities
- ✅ `json` - JSON parsing
- ✅ `threading` - Background polling
- ✅ `ssl` - TLS/SSL support
- ✅ `logging` - Structured logging
- ✅ `datetime`, `time` - Time handling
- ✅ `os`, `sys` - System utilities
- ✅ `unittest`, `unittest.mock` - Testing

## Architecture Overview

### Component Structure
```
┌─────────────────────────────────────────┐
│   GitLab API                            │
└────────────┬────────────────────────────┘
             │ HTTP requests (urllib)
             ↓
┌─────────────────────────────────────────┐
│   BackgroundPoller (Thread)             │
│   - Polls GitLab API every N seconds    │
│   - Retries with exponential backoff    │
│   - Handles rate limiting (429)         │
└────────────┬────────────────────────────┘
             │ Updates (thread-safe)
             ↓
┌─────────────────────────────────────────┐
│   Global STATE (dict + Lock)            │
│   - projects, pipelines, summary        │
│   - last_updated, status, error         │
└────────────┬────────────────────────────┘
             │ Reads (thread-safe)
             ↓
┌─────────────────────────────────────────┐
│   DashboardRequestHandler               │
│   - Serves JSON API endpoints           │
│   - Serves static frontend files        │
└─────────────────────────────────────────┘
```

### Threading Model
- **Main Thread**: HTTP server request handler (reads STATE)
- **Background Thread**: Poller that updates STATE periodically
- **Thread Safety**: All STATE access protected by `STATE_LOCK`

## Code Quality Expectations

### Reliability
- **Graceful Degradation**: Return cached data if API fails temporarily
- **Retry Logic**: Use exponential backoff for transient errors (5xx, timeouts)
- **Rate Limiting**: Honor GitLab's `Retry-After` header on 429 responses
- **Error Handling**: Catch specific exceptions, log meaningfully
- **Atomic Updates**: Use `update_state_atomic()` when updating multiple STATE keys

### Logging Best Practices
- **Info level**: Normal operations (polling completed, server started)
- **Warning level**: Recoverable issues (retry, partial data)
- **Error level**: Failures that impact functionality
- **Never log secrets**: Redact API tokens in logs (use `'***'` placeholder)
- **Structured messages**: Include context (project ID, endpoint, etc.)

Example:
```python
logger.info(f"Fetched {len(projects)} projects in {duration:.2f}s")
logger.warning(f"Rate limited (429). Retrying in {wait_time}s...")
logger.error(f"Failed to fetch project {project_id}: {error}")
# Never: logger.info(f"Token: {api_token}")
```

### Security Expectations

#### Never Log Sensitive Data
```python
# ❌ BAD
logger.info(f"Using token: {api_token}")

# ✅ GOOD
logger.info(f"API token: {'***' if api_token else 'NOT SET'}")
```

#### TLS Verification Default
```python
# Default behavior: verify certificates
if self.insecure_skip_verify:
    # Only disable with explicit user consent
    logger.warning("=" * 70)
    logger.warning("SSL VERIFICATION DISABLED - SECURITY RISK")
    logger.warning("Only use on trusted internal networks")
    logger.warning("=" * 70)
    self.ssl_context = ssl.create_default_context()
    self.ssl_context.check_hostname = False
    self.ssl_context.verify_mode = ssl.CERT_NONE
else:
    # Default: verify certificates
    self.ssl_context = None  # Use default verification
```

#### Input Validation
```python
# Validate and sanitize user inputs
try:
    limit = int(query_params.get('limit', ['50'])[0])
    if limit < 1 or limit > MAX_LIMIT:
        raise ValueError(f"limit must be 1-{MAX_LIMIT}")
except (ValueError, IndexError) as e:
    self.send_json_response({'error': str(e)}, status=400)
    return
```

## Code Style

### Function Design
- **Small functions**: Each function should do one thing well
- **Testable**: Easy to test in isolation
- **Pure when possible**: Minimize side effects

```python
# ✅ GOOD: Small, focused, testable
def parse_int_config(value, default, name):
    """Parse integer configuration with fallback"""
    try:
        return int(value)
    except (ValueError, TypeError):
        logger.warning(f"Invalid {name}: {value}. Using default: {default}")
        return default

# ❌ BAD: Too complex, hard to test
def load_and_validate_all_config():
    # 100 lines of mixed concerns...
```

### Type Hints (Optional)
Type hints are acceptable but **don't add mypy or type-checking tools**:

```python
def get_projects(self, per_page: int = None) -> list[dict] | None:
    """Get list of projects with pagination support"""
    # Implementation...
```

### Docstrings
```python
def _make_paginated_request(self, endpoint, params=None, max_pages=None):
    """Make paginated requests following X-Next-Page until exhausted
    
    Args:
        endpoint: API endpoint path (e.g., 'projects')
        params: Optional query parameters dict
        max_pages: Optional maximum pages to fetch
        
    Returns:
        list: All items across pages, or None if API error
    """
```

### Error Handling Patterns
```python
# Pattern 1: Retry transient errors
for attempt in range(max_retries):
    try:
        return self._fetch_data()
    except TimeoutError:
        if attempt < max_retries - 1:
            wait_time = initial_delay * (2 ** attempt)
            logger.warning(f"Timeout. Retry {attempt+1}/{max_retries} in {wait_time}s")
            time.sleep(wait_time)
        else:
            logger.error(f"Failed after {max_retries} retries")
            return None

# Pattern 2: Return None for API errors, empty list for valid empty results
projects = self.gitlab_client.get_projects()
if projects is None:
    # API error occurred
    logger.error("Failed to fetch projects")
    return None
elif not projects:
    # Valid empty result
    logger.info("No projects found")
    return []
```

## Testing Guidelines

### Use stdlib unittest
```python
import unittest
from unittest.mock import MagicMock, patch

class TestGitLabClient(unittest.TestCase):
    def setUp(self):
        self.client = GitLabAPIClient('https://gitlab.com', 'token')
    
    def test_get_projects_success(self):
        with patch.object(self.client, '_make_request') as mock:
            mock.return_value = {'data': [{'id': 1}]}
            result = self.client.get_projects(per_page=10)
            self.assertEqual(len(result), 1)
    
    def test_get_projects_api_error(self):
        with patch.object(self.client, '_make_request') as mock:
            mock.return_value = None
            result = self.client.get_projects()
            self.assertIsNone(result)
```

### Test Coverage Areas
- Configuration loading (env vars override config.json)
- API client (retry logic, pagination, error handling)
- State management (thread-safety, atomic updates)
- Request handlers (response format, status codes)
- Edge cases (empty results, None vs [], timeouts)

## Common Patterns

### Making HTTP Requests with urllib
```python
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

headers = {'PRIVATE-TOKEN': self.api_token}
request = Request(url, headers=headers)

try:
    with urlopen(request, timeout=30) as response:
        data = response.read().decode('utf-8')
        return json.loads(data)
except HTTPError as e:
    if e.code == 429:
        # Handle rate limiting
        retry_after = e.headers.get('Retry-After')
        # ...
    logger.error(f"HTTP Error {e.code}: {e.reason}")
except URLError as e:
    logger.error(f"URL Error: {e.reason}")
```

### Thread-Safe State Updates
```python
# Single key update
def update_state(key, value):
    with STATE_LOCK:
        STATE['data'][key] = value
        STATE['last_updated'] = datetime.now()
        STATE['status'] = 'ONLINE'

# Atomic multi-key update (preferred for consistency)
def update_state_atomic(updates):
    with STATE_LOCK:
        for key, value in updates.items():
            STATE['data'][key] = value
        STATE['last_updated'] = datetime.now()
        STATE['status'] = 'ONLINE'
```

### Serving JSON Responses
```python
def send_json_response(self, data, status=200):
    self.send_response(status)
    self.send_header('Content-Type', 'application/json')
    self.send_header('Access-Control-Allow-Origin', '*')
    self.end_headers()
    self.wfile.write(json.dumps(data, indent=2).encode('utf-8'))
```

## What NOT to Do

### ❌ Don't Add Dependencies
```python
# ❌ BAD
import requests  # External dependency
response = requests.get(url)

# ✅ GOOD
from urllib.request import Request, urlopen
request = Request(url)
with urlopen(request) as response:
    data = response.read()
```

### ❌ Don't Block the Request Handler
```python
# ❌ BAD: Blocking API call in request handler
def handle_repos(self):
    repos = self.server.gitlab_client.get_projects()  # Blocks!
    self.send_json_response(repos)

# ✅ GOOD: Read from cached state
def handle_repos(self):
    repos = get_state('projects')  # Fast, non-blocking
    self.send_json_response(repos)
```

### ❌ Don't Introduce Race Conditions
```python
# ❌ BAD: Non-atomic read-modify-write
projects = STATE['data']['projects']
projects.append(new_project)
STATE['data']['projects'] = projects

# ✅ GOOD: Atomic update with lock
with STATE_LOCK:
    STATE['data']['projects'].append(new_project)
```

## Performance Considerations

### Pagination
- Use `per_page=100` for better API efficiency
- Respect GitLab's `X-Next-Page` header
- Log pagination progress for visibility

### Caching
- Background poller updates cache periodically
- Request handlers serve from cache (fast, non-blocking)
- Cache invalidation happens on successful poll

### Rate Limiting
- Honor `Retry-After` header on 429 responses
- Use exponential backoff for retries
- Limit concurrent API requests (sequential in poller)

## Deployment Considerations

### Environment Variables
All config should support environment variable override:
```python
config['api_token'] = os.environ.get('GITLAB_API_TOKEN', config.get('api_token', ''))
```

### Graceful Shutdown
```python
try:
    httpd.serve_forever()
except KeyboardInterrupt:
    logger.info("Shutting down...")
    poller.stop()
    poller.join(timeout=5)
    httpd.shutdown()
```

### Health Checks
- `/api/health` should reflect actual backend state
- Return 503 during INITIALIZING or ERROR states
- Return 200 only when ONLINE and data is available

## Questions to Ask Before Adding Features

1. Can this be done with stdlib only? (Usually yes!)
2. Does this maintain backward compatibility?
3. Is the API response format consistent with existing endpoints?
4. Does this handle errors gracefully?
5. Is logging appropriate (informative but not noisy)?
6. Are secrets protected from logs?
7. Is the code testable with unittest?
8. Does it work with both config.json and environment variables?

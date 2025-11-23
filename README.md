# GitLab DSO Dashboard

A production-ready, zero-dependency dashboard for monitoring GitLab repositories and CI/CD pipelines. Built with **Python standard library only** (no pip dependencies) and **vanilla JavaScript** (no frameworks).

> **For Copilot Agents:** See [AGENTS.md](AGENTS.md) for workflow guidance and [.github/copilot-instructions.md](.github/copilot-instructions.md) for complete coding constraints.

## Table of Contents

- [What This Is](#what-this-is)
- [Architecture Overview](#architecture-overview)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [API Endpoints](#api-endpoints)
- [Frontend Features](#frontend-features)
- [Development](#development)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

## What This Is

DSO-Dashboard is a lightweight, portable GitLab monitoring dashboard designed for DevSecOps teams. It provides real-time visibility into repository health and CI/CD pipeline status with a modern dark neomorphic UI.

### Key Characteristics

- **Zero External Dependencies**: Pure Python stdlib backend + vanilla JS frontend
- **Easy Deployment**: Single Python file, no installation required
- **GitLab Native**: Connects directly to GitLab API (SaaS or self-hosted)
- **Real-time Updates**: Background polling with auto-refresh UI
- **Production Ready**: Thread-safe, retry logic, rate limiting, graceful degradation

### Use Cases

- **DevOps Dashboards**: Monitor CI/CD health across multiple projects/groups
- **TV Displays**: Kiosk mode for team dashboards (`?tv=true`)
- **Self-Hosted GitLab**: Works with internal GitLab instances (including self-signed certs)
- **Quick Insights**: Get repository and pipeline metrics without navigating GitLab UI

## Architecture Overview

### High-Level Flow

```
┌─────────────────┐
│   GitLab API    │
│  (SaaS/Self-   │
│    Hosted)      │
└────────┬────────┘
         │ HTTP/HTTPS (urllib)
         ↓
┌─────────────────────────────────────┐
│   Background Poller Thread          │
│   - Polls every N seconds           │
│   - Retries with exponential backoff│
│   - Handles rate limiting (429)     │
│   - Full pagination support         │
└────────┬────────────────────────────┘
         │ Thread-safe updates
         ↓
┌─────────────────────────────────────┐
│   Global STATE (in-memory)          │
│   - projects: [...enriched data]    │
│   - pipelines: [...recent runs]     │
│   - summary: {...statistics}        │
│   - last_updated, status, error     │
└────────┬────────────────────────────┘
         │ Fast, non-blocking reads
         ↓
┌─────────────────────────────────────┐
│   HTTP Request Handler              │
│   - Serves JSON API endpoints       │
│   - Serves static frontend files    │
└────────┬────────────────────────────┘
         │ HTTP Responses
         ↓
┌─────────────────────────────────────┐
│   Browser (Frontend)                │
│   - Fetches data every 60s          │
│   - Renders dark neomorphic UI      │
│   - TV mode support                 │
└─────────────────────────────────────┘
```

### Component Details

#### Backend (`server.py`)
- **`GitLabAPIClient`**: Handles all GitLab API communication
  - Retry logic with exponential backoff
  - Rate limiting (429 response handling)
  - Full pagination support
  - SSL/TLS support (including self-signed certs)
- **`BackgroundPoller`**: Daemon thread that polls GitLab periodically
  - Fetches projects and pipelines
  - Enriches data with pipeline health metrics
  - Updates global STATE atomically
- **`DashboardRequestHandler`**: HTTP request handler
  - Serves API endpoints (`/api/*`)
  - Serves static frontend files (`/`)
  - Thread-safe STATE reads
- **Global STATE**: Thread-safe in-memory cache
  - Protected by `threading.Lock`
  - Single source of truth for UI data

#### Frontend (`frontend/`)
- **`index.html`**: Semantic HTML5 structure
- **`app.js`**: Vanilla JavaScript (ES6+)
  - Fetches data from API endpoints
  - Renders dynamic content (cards, tables, stats)
  - Auto-refresh every 60 seconds
  - XSS prevention (`escapeHtml()`)
- **`styles.css`**: Dark neomorphic theme
  - CSS custom properties (variables)
  - Responsive grid layout
  - Soft shadows for depth effect

## Quick Start

### Prerequisites

- **Python 3.10 or higher**
- **GitLab API access** (SaaS or self-hosted)
- **Personal Access Token** with `read_api` scope

### Installation (3 Steps)

```bash
# 1. Clone the repository
git clone https://github.com/deveydtj/DSO-Dashboard.git
cd DSO-Dashboard

# 2. Configure (choose ONE option)

# Option A: config.json file
cp config.json.example config.json
nano config.json  # Add your GitLab URL and API token

# Option B: Environment variables
export GITLAB_URL="https://gitlab.com"
export GITLAB_API_TOKEN="your_token_here"

# 3. Run the server
python3 server.py
```

Open your browser to **`http://localhost:8080`**

That's it! No pip install, no npm install, no build step.

### Creating a GitLab API Token

1. Log in to GitLab
2. Go to **User Settings** → **Access Tokens**
3. Create a new token with:
   - **Name**: `DSO-Dashboard`
   - **Scopes**: `read_api` (only this scope needed)
   - **Expiration**: Set as needed
4. Copy the token and add it to `config.json` or `GITLAB_API_TOKEN` environment variable

## Configuration

### Configuration Methods

DSO-Dashboard supports two configuration methods that can be used together. **Environment variables override config.json values**.

| Priority | Method | Use Case |
|----------|--------|----------|
| 1 (highest) | Environment Variables | Docker, CI/CD, temporary overrides |
| 2 | config.json | Local development, persistent settings |

### Configuration Options

| config.json field | Environment Variable | Description | Default |
|-------------------|---------------------|-------------|---------|
| `gitlab_url` | `GITLAB_URL` | GitLab instance URL | `https://gitlab.com` |
| `api_token` | `GITLAB_API_TOKEN` | GitLab Personal Access Token (required) | - |
| `group_ids` | `GITLAB_GROUP_IDS` | Comma-separated group IDs to monitor | All accessible projects |
| `project_ids` | `GITLAB_PROJECT_IDS` | Comma-separated project IDs to monitor | - |
| `poll_interval_sec` | `POLL_INTERVAL` | Background polling interval (seconds) | `60` |
| `cache_ttl_sec` | `CACHE_TTL` | Cache TTL (deprecated, kept for compatibility) | `300` |
| `per_page` | `PER_PAGE` | API pagination size | `100` |
| `insecure_skip_verify` | `INSECURE_SKIP_VERIFY` | Skip SSL verification (self-signed certs) | `false` |
| `use_mock_data` | `USE_MOCK_DATA` | Use mock data instead of GitLab API | `false` |
| `mock_scenario` | `MOCK_SCENARIO` | Mock scenario name: `healthy`, `failing`, or `running` | `` (uses `mock_data.json`) |
| `port` (N/A in json) | `PORT` | Server port | `8080` |

### Configuration Examples

**Example 1: Monitor specific groups**
```json
{
  "gitlab_url": "https://gitlab.example.com",
  "api_token": "glpat-xxxxxxxxxxxxx",
  "group_ids": ["my-team", "infrastructure"],
  "poll_interval_sec": 60
}
```

**Example 2: Monitor specific projects**
```json
{
  "gitlab_url": "https://gitlab.com",
  "api_token": "glpat-xxxxxxxxxxxxx",
  "project_ids": ["12345", "67890"],
  "poll_interval_sec": 30
}
```

**Example 3: Self-signed certificates (use with caution)**
```json
{
  "gitlab_url": "https://internal-gitlab.corp",
  "api_token": "glpat-xxxxxxxxxxxxx",
  "insecure_skip_verify": true
}
```

**Example 4: Environment variable override**
```bash
# Start with config.json but override URL temporarily
export GITLAB_URL="https://staging-gitlab.example.com"
python3 server.py
```

### Mock Data Mode

Mock data mode allows the dashboard to run without GitLab API access. This is useful for:
- **Development**: Test the UI without a GitLab instance
- **Demos**: Show the dashboard functionality without credentials
- **Testing**: Validate frontend changes with predictable data
- **Offline Mode**: Run the dashboard when GitLab is unavailable

#### Enabling Mock Mode

**Option 1: Environment Variable**
```bash
export USE_MOCK_DATA=true
python3 server.py
```

**Option 2: config.json**
```json
{
  "use_mock_data": true
}
```

When mock mode is enabled:
- Server loads data from `mock_data.json` at startup (or a scenario file if specified)
- GitLab API polling is **disabled** (no network calls)
- `/api/health` returns `ONLINE` status
- All API endpoints serve data from the mock file

#### Mock Scenarios

DSO-Dashboard includes pre-built mock scenarios for testing different edge cases:

| Scenario | File | Description | Use Case |
|----------|------|-------------|----------|
| **Default** | `mock_data.json` | Mixed status with moderate activity | General development |
| **healthy** | `data/mock_scenarios/healthy.json` | Mostly successful pipelines (80% success rate) | Demo healthy CI/CD state |
| **failing** | `data/mock_scenarios/failing.json` | Multiple repos with consecutive failures (23% success rate) | Test failure handling, alerts |
| **running** | `data/mock_scenarios/running.json` | Many running and pending pipelines (50% in progress) | Test active build visualization |

**Switching Scenarios:**

```bash
# Use the healthy scenario
export USE_MOCK_DATA=true
export MOCK_SCENARIO=healthy
python3 server.py

# Use the failing scenario
export USE_MOCK_DATA=true
export MOCK_SCENARIO=failing
python3 server.py

# Use the running scenario
export USE_MOCK_DATA=true
export MOCK_SCENARIO=running
python3 server.py

# Use default mock_data.json (no scenario specified)
export USE_MOCK_DATA=true
python3 server.py
```

**Or via config.json:**
```json
{
  "use_mock_data": true,
  "mock_scenario": "healthy"
}
```

**Scenario Details:**

- **healthy**: 10 repositories, 10 pipelines, 80% success rate, minimal failures
- **failing**: 10 repositories, 22 pipelines, multiple with 3-10 consecutive failures on main branch, 23% success rate
- **running**: 12 repositories, 24 pipelines, 12 running + 10 pending (high activity)

#### Mock Data File Structure

The `mock_data.json` file contains sample data matching the API response format:

```json
{
  "summary": {
    "total_repositories": 8,
    "active_repositories": 7,
    "total_pipelines": 45,
    "successful_pipelines": 38,
    "failed_pipelines": 4,
    "running_pipelines": 2,
    "pending_pipelines": 1,
    "pipeline_success_rate": 0.8444,
    "pipeline_statuses": { ... }
  },
  "repositories": [
    {
      "id": 10001,
      "name": "frontend-app",
      "path_with_namespace": "demo-group/frontend-app",
      "description": "Modern React frontend application",
      "web_url": "https://gitlab.com/...",
      "last_pipeline_status": "success",
      "recent_success_rate": 0.9,
      ...
    }
  ],
  "pipelines": [
    {
      "id": 50001,
      "project_id": 10001,
      "project_name": "frontend-app",
      "status": "success",
      "ref": "main",
      "sha": "a1b2c3d4",
      ...
    }
  ]
}
```

**Required Keys:**
- `summary`: Overall statistics matching `/api/summary` response
- `repositories`: Array of repository objects matching `/api/repos` response
- `pipelines`: Array of pipeline objects matching `/api/pipelines` response

You can customize `mock_data.json` to test different scenarios, or use the pre-built scenarios in `data/mock_scenarios/`.

#### Hot-Reloading Mock Data

When running in mock mode, you can reload the mock data file without restarting the server. This is useful for:
- **Rapid iteration**: Test UI changes with different data sets
- **Demo scenarios**: Switch between different mock data snapshots
- **Testing edge cases**: Quickly test how the UI handles various data states

**Reload Mock Data:**
```bash
# Edit the mock file (mock_data.json or scenario file) with your changes, then reload:
curl -X POST http://localhost:8080/api/mock/reload

# Example response:
# {
#   "reloaded": true,
#   "timestamp": "2024-01-15T12:00:00.000000",
#   "scenario": "healthy",
#   "summary": {
#     "repositories": 10,
#     "pipelines": 60
#   }
# }
```

**Important Notes:**
- Hot-reload only works when `USE_MOCK_DATA=true` (mock mode enabled)
- The endpoint reloads from the same file that was initially configured (e.g., if you started with `MOCK_SCENARIO=healthy`, it reloads `data/mock_scenarios/healthy.json`)
- To switch scenarios, you need to restart the server with a different `MOCK_SCENARIO` value
- If you call the endpoint when not in mock mode, you'll get a `400 Bad Request` error
- The dashboard will reflect the new data on the next auto-refresh (within 60 seconds) or when you manually refresh the page
- Invalid JSON in the mock file will return a `500 Internal Server Error` with details in the response

## API Endpoints

The backend provides RESTful JSON API endpoints that the frontend consumes.

### GET `/api/health`

Health check endpoint for monitoring and load balancers.

**Response (200 OK - Healthy):**
```json
{
  "status": "healthy",
  "backend_status": "ONLINE",
  "timestamp": "2024-01-15T12:00:00.000000",
  "last_poll": "2024-01-15T11:59:30.000000",
  "error": null
}
```

**Response (503 Service Unavailable - Unhealthy):**
```json
{
  "status": "unhealthy",
  "backend_status": "ERROR",
  "timestamp": "2024-01-15T12:00:00.000000",
  "last_poll": "2024-01-15T11:50:00.000000",
  "error": "Failed to fetch data from GitLab API"
}
```

**Backend Status Values:**
- `INITIALIZING`: First poll in progress, no data yet
- `ONLINE`: Healthy, data is current
- `ERROR`: GitLab API unreachable or failing

### GET `/api/summary`

Overall statistics and KPIs.

**Response:**
```json
{
  "total_repositories": 42,
  "active_repositories": 38,
  "total_pipelines": 150,
  "successful_pipelines": 135,
  "failed_pipelines": 10,
  "running_pipelines": 3,
  "pending_pipelines": 2,
  "pipeline_success_rate": 0.90,
  "pipeline_statuses": {
    "success": 135,
    "failed": 10,
    "running": 3,
    "pending": 2
  },
  "last_updated": "2024-01-15T12:00:00.000000",
  "last_updated_iso": "2024-01-15T12:00:00.000000"
}
```

### GET `/api/repos`

List of repositories with enriched pipeline health data.

**Response:**
```json
{
  "repositories": [
    {
      "id": 12345,
      "name": "my-awesome-project",
      "path_with_namespace": "my-group/my-awesome-project",
      "description": "An awesome project",
      "web_url": "https://gitlab.com/my-group/my-awesome-project",
      "last_activity_at": "2024-01-15T11:30:00.000Z",
      "star_count": 15,
      "forks_count": 3,
      "open_issues_count": 8,
      "default_branch": "main",
      "visibility": "private",
      "last_pipeline_status": "success",
      "last_pipeline_ref": "main",
      "last_pipeline_duration": 245,
      "last_pipeline_updated_at": "2024-01-15T11:25:00.000Z",
      "recent_success_rate": 0.85,
      "consecutive_default_branch_failures": 0
    }
  ],
  "total": 42,
  "last_updated": "2024-01-15T12:00:00.000000"
}
```

**Pipeline Health Fields:**
- `last_pipeline_status`: Most recent pipeline status (any branch)
- `last_pipeline_ref`: Branch of most recent pipeline
- `last_pipeline_duration`: Duration in seconds
- `recent_success_rate`: Success rate of last 10 pipelines on default branch
- `consecutive_default_branch_failures`: Count of consecutive failures on default branch

### GET `/api/pipelines`

Recent pipeline runs across all monitored projects.

**Query Parameters:**
- `limit` (optional): Max pipelines to return (default: 50, max: 1000)
- `status` (optional): Filter by status (`success`, `failed`, `running`, `pending`)
- `ref` (optional): Filter by branch/tag name
- `project` (optional): Filter by project name (substring match)

**Example Requests:**
```bash
# Default (last 50 pipelines)
GET /api/pipelines

# Last 100 pipelines
GET /api/pipelines?limit=100

# Only failed pipelines
GET /api/pipelines?status=failed

# Pipelines on main branch
GET /api/pipelines?ref=main

# Failed pipelines on main branch
GET /api/pipelines?status=failed&ref=main

# Pipelines for specific project
GET /api/pipelines?project=my-app
```

**Response:**
```json
{
  "pipelines": [
    {
      "id": 98765,
      "project_id": 12345,
      "project_name": "my-awesome-project",
      "project_path": "my-group/my-awesome-project",
      "status": "success",
      "ref": "main",
      "sha": "a1b2c3d4",
      "web_url": "https://gitlab.com/my-group/my-awesome-project/-/pipelines/98765",
      "created_at": "2024-01-15T11:20:00.000Z",
      "updated_at": "2024-01-15T11:25:00.000Z",
      "duration": 245
    }
  ],
  "total": 50,
  "total_before_limit": 150,
  "last_updated": "2024-01-15T12:00:00.000000"
}
```

**Pipeline Status Values:**
- `success`: Pipeline completed successfully
- `failed`: Pipeline failed
- `running`: Pipeline currently running
- `pending`: Pipeline queued/waiting
- `canceled`: Pipeline was canceled
- `skipped`: Pipeline was skipped
- `manual`: Pipeline requires manual action

### POST `/api/mock/reload`

Hot-reload mock data from `mock_data.json` without restarting the server. Only available when running in mock mode (`USE_MOCK_DATA=true`).

**Request:**
```bash
curl -X POST http://localhost:8080/api/mock/reload
```

**Response (200 OK - Success):**
```json
{
  "reloaded": true,
  "timestamp": "2024-01-15T12:00:00.000000",
  "summary": {
    "repositories": 8,
    "pipelines": 45
  }
}
```

**Response (400 Bad Request - Not in mock mode):**
```json
{
  "error": "Mock reload endpoint only available in mock mode",
  "hint": "Set USE_MOCK_DATA=true or use_mock_data: true in config.json"
}
```

**Response (500 Internal Server Error - Failed to load):**
```json
{
  "error": "Failed to load mock_data.json",
  "details": "Check server logs for details"
}
```

**Use Cases:**
- Rapid iteration during development (edit mock data and reload)
- Testing different data scenarios without server restart
- Demo preparation (swap mock data snapshots quickly)

## Frontend Features

### Dashboard Views

#### Summary Statistics (Top)
- **Total Repositories**: Count of monitored repos
- **Active Repositories**: Repos with recent activity
- **Total Pipelines**: Recent pipeline runs
- **Success Rate**: Percentage of successful pipelines
- Color-coded KPI cards with icons

#### Repository Cards (Middle)
- Grid layout of project cards
- Each card shows:
  - Project name and description
  - Stars, forks, open issues
  - Last pipeline status badge
  - Recent success rate
  - Link to GitLab project
- Sortable by name, activity, or pipeline status

#### Pipeline Table (Bottom)
- Recent pipeline runs across all projects
- Columns: Project, Status, Branch, Commit SHA, Duration, Timestamp
- Status badges with color coding
- Links to pipeline details in GitLab
- Auto-refresh every 60 seconds

### TV/Kiosk Mode

Enable full-screen dashboard mode for team displays:

```
http://localhost:8080/?tv=true
```

**TV Mode Features:**
- Full-screen layout
- Larger text and cards
- Optimized for viewing from a distance
- Auto-refresh continues in background

### Dark Neomorphic Theme

The UI uses a dark neomorphic design with:
- **Soft shadows** for depth and elevation
- **Dark color palette** (easy on the eyes)
- **Smooth transitions** for interactive elements
- **High contrast text** for readability
- **Responsive layout** (mobile, tablet, desktop)

**Color Palette:**
- Background: Dark blue-gray (`#1a1d29`)
- Cards: Slightly lighter (`#22252f`)
- Text: Light gray (`#e8eaed`)
- Accents: Blue (`#4a9eff`)
- Success: Green (`#34a853`)
- Error: Red (`#ea4335`)

## Development

### Project Structure

```
DSO-Dashboard/
├── server.py                 # Backend (Python stdlib only)
├── config.json.example       # Configuration template
├── .env.example              # Environment variables template
│
├── frontend/                 # Static frontend files
│   ├── index.html            # Page structure
│   ├── app.js                # JavaScript logic (vanilla)
│   └── styles.css            # Neomorphic dark theme
│
├── tests/                    # Unit tests (stdlib unittest)
│   ├── __init__.py
│   └── test_smoke.py         # Smoke tests
│
├── .github/
│   ├── copilot-instructions.md        # Copilot guidance (repo-wide)
│   ├── instructions/
│   │   ├── backend.instructions.md    # Backend-specific guidance
│   │   └── frontend.instructions.md   # Frontend-specific guidance
│   ├── workflows/
│   │   └── ci.yml                      # CI/CD pipeline
│   └── ISSUE_TEMPLATE/
│       ├── bug_report.md
│       └── feature_request.md
│
├── AGENTS.md                 # Agent workflow guidance
├── README.md                 # This file
└── .gitignore                # Git ignore rules
```

### Making Changes

**Before making any changes:**
1. Read [AGENTS.md](AGENTS.md) for workflow guidance
2. Read `.github/copilot-instructions.md` for constraints
3. For backend: Read `.github/instructions/backend.instructions.md`
4. For frontend: Read `.github/instructions/frontend.instructions.md`

**Key Constraints:**
- ⚠️ Backend must remain **Python stdlib only** (no pip dependencies)
- ⚠️ Frontend must remain **vanilla JS/HTML/CSS** (no frameworks, no build tools)
- ⚠️ Preserve dark neomorphic UI theme
- ⚠️ Don't break API endpoint contracts
- ⚠️ Don't break frontend DOM structure

### Running Locally

```bash
# Start the server
python3 server.py

# In another terminal, test the API
curl http://localhost:8080/api/health
curl http://localhost:8080/api/summary
curl http://localhost:8080/api/repos
curl http://localhost:8080/api/pipelines

# Open in browser
open http://localhost:8080
```

### Code Style

**Python:**
- Follow PEP 8 style guide
- Use type hints (optional, don't add mypy)
- Small, testable functions
- Docstrings for classes and complex functions
- Meaningful logging (INFO, WARNING, ERROR)
- Never log API tokens

**JavaScript:**
- Modern ES6+ syntax
- Use const/let (not var)
- Arrow functions, template literals
- Small, focused functions
- Sanitize user input with `escapeHtml()`

**CSS:**
- Use CSS custom properties (variables)
- Mobile-first responsive design
- Maintain neomorphic shadow effects
- Keep dark color palette

## Testing

### Running Tests

```bash
# Run all tests
python -m unittest discover -s tests -p "test_*.py" -v

# Run specific test file
python -m unittest tests.test_smoke -v

# Check Python syntax
python -m py_compile server.py
```

### Test Coverage

Current tests cover:
- Configuration loading (config.json + env vars)
- State management (thread-safe updates)
- GitLab API client initialization
- Helper functions (parsing, validation)
- Import validation (stdlib-only check)

### Writing Tests

Use stdlib `unittest` and `unittest.mock`:

```python
import unittest
from unittest.mock import patch, MagicMock

class TestMyFeature(unittest.TestCase):
    def setUp(self):
        # Setup before each test
        pass
    
    def test_something(self):
        # Your test here
        self.assertEqual(actual, expected)
    
    def tearDown(self):
        # Cleanup after each test
        pass
```

### CI/CD Pipeline

GitHub Actions runs on every push and PR:
1. **Syntax Check**: `python -m py_compile server.py`
2. **Unit Tests**: `python -m unittest`
3. **Dependency Check**: Ensures no external dependencies
4. **Frontend Check**: Ensures no frameworks/build tools
5. **Integration Test**: Server startup and API endpoints

View CI results in the "Actions" tab on GitHub.

## Troubleshooting

### Common Issues

#### "GITLAB_API_TOKEN not set"

**Problem:** API token is missing.

**Solution:**
```bash
# Option 1: Set environment variable
export GITLAB_API_TOKEN="your_token_here"

# Option 2: Add to config.json
{
  "api_token": "your_token_here"
}
```

#### "Failed to fetch data from GitLab API"

**Problem:** Cannot connect to GitLab or invalid token.

**Solutions:**
1. Verify GitLab URL is correct
2. Check API token is valid and has `read_api` scope
3. Test connectivity: `curl -H "PRIVATE-TOKEN: your_token" https://gitlab.com/api/v4/projects`
4. Check firewall/network settings

#### SSL Certificate Errors

**Problem:** Self-signed certificates or internal CA.

**Solution:**
```json
{
  "insecure_skip_verify": true
}
```

⚠️ **Security Warning:** Only use `insecure_skip_verify: true` on trusted internal networks. This disables TLS verification.

#### No Projects/Pipelines Showing

**Problem:** API token lacks permissions or no projects accessible.

**Solutions:**
1. Verify token has `read_api` scope
2. Check token user has access to projects/groups
3. Check `group_ids` or `project_ids` config is correct
4. Test API manually:
   ```bash
   curl -H "PRIVATE-TOKEN: your_token" https://gitlab.com/api/v4/projects
   ```

#### Port Already in Use

**Problem:** Port 8080 is already bound.

**Solution:**
```bash
# Use a different port
PORT=8081 python3 server.py

# Or in config.json, set via env var only
export PORT=8081
```

#### Frontend Not Loading

**Problem:** Browser shows blank page or 404.

**Solutions:**
1. Check `frontend/` directory exists with `index.html`, `app.js`, `styles.css`
2. Check browser console for JavaScript errors (F12)
3. Verify server is running: `curl http://localhost:8080/`
4. Check server logs for errors

#### Server Crashes or Exits

**Problem:** Python exceptions or errors.

**Solutions:**
1. Check Python version: `python3 --version` (must be 3.10+)
2. Review server logs for stack traces
3. Verify config.json is valid JSON
4. Check for conflicting environment variables

### Debug Mode

Enable debug logging:

```python
# In server.py, change logging level temporarily
logging.basicConfig(
    level=logging.DEBUG,  # Changed from INFO
    format='%(asctime)s - %(levelname)s - %(message)s'
)
```

Then restart the server to see detailed logs.

### Getting Help

1. Check this README's troubleshooting section
2. Review server logs for error messages
3. Test API endpoints manually with `curl`
4. Check browser console for frontend errors
5. Open an issue on GitHub with:
   - Python version
   - GitLab version (SaaS or self-hosted)
   - Configuration (redact tokens!)
   - Error messages/logs
   - Steps to reproduce

## Contributing

Contributions are welcome! Please follow these guidelines:

### Before Contributing

1. Read [AGENTS.md](AGENTS.md) for development workflow
2. Read `.github/copilot-instructions.md` for project constraints
3. Check existing issues and PRs to avoid duplicates
4. For large changes, open an issue first to discuss

### Development Workflow

1. **Fork** the repository
2. **Create a branch** for your feature/fix
3. **Make minimal changes** (follow constraints)
4. **Write/update tests** for your changes
5. **Run validation**:
   ```bash
   python -m py_compile server.py
   python -m unittest
   ```
6. **Test manually** (start server, test in browser)
7. **Commit** with clear message
8. **Push** to your fork
9. **Open Pull Request** using the PR template

### Pull Request Checklist

Before submitting a PR, ensure:

- [ ] Code follows existing style and patterns
- [ ] **Backend remains stdlib-only** (no pip dependencies)
- [ ] **Frontend remains vanilla JS** (no frameworks/build tools)
- [ ] Dark neomorphic theme preserved
- [ ] No breaking changes to API endpoints
- [ ] No breaking changes to frontend DOM structure
- [ ] All tests pass: `python -m unittest`
- [ ] Manual testing completed
- [ ] Documentation updated (if needed)
- [ ] No secrets committed

### Issue Templates

Use the provided templates:
- **Bug Report**: `.github/ISSUE_TEMPLATE/bug_report.md`
- **Feature Request**: `.github/ISSUE_TEMPLATE/feature_request.md`

### Code Review

All PRs require review. Reviewers will check:
- Adherence to constraints (stdlib-only, vanilla-only)
- Code quality and style
- Test coverage
- Documentation updates
- Security (no secrets, input sanitization)
- Backward compatibility

## License

This project is open source and available for use.

## Acknowledgments

- Built with Python standard library (no external dependencies)
- Frontend uses vanilla JavaScript (no frameworks)
- Designed for DevSecOps teams monitoring GitLab
- Inspired by modern dark UI design patterns

---

**Quick Links:**
- [GitHub Repository](https://github.com/deveydtj/DSO-Dashboard)
- [Issue Tracker](https://github.com/deveydtj/DSO-Dashboard/issues)
- [Agent Instructions](AGENTS.md)
- [Copilot Instructions](.github/copilot-instructions.md)

# Architecture Overview

This document provides a high-level overview of the DSO-Dashboard project for new developers and the GitHub Copilot Coding Agent.

## What Is DSO-Dashboard?

DSO-Dashboard is a **lightweight GitLab DevSecOps monitoring dashboard** designed for teams that need real-time visibility into their CI/CD pipelines and repository health. It provides:

- **Repository health metrics**: Pipeline status, success rates, consecutive failures
- **Pipeline monitoring**: Recent runs across all projects with status tracking
- **External service health**: Monitor Artifactory, Confluence, Jira, or other tools
- **TV/Kiosk mode**: Full-screen dashboard for team displays

**Key design principles**:
- **Zero dependencies**: Pure Python stdlib backend + vanilla JavaScript frontend
- **Easy deployment**: Single `python backend/app.py` command, no build step
- **GitLab native**: Works with GitLab SaaS or self-hosted instances

## Directory Structure

```
DSO-Dashboard/
├── backend/                      # Backend server package (Python stdlib only)
│   ├── __init__.py               # Package init
│   ├── app.py                    # HTTP server, routes, and entry point
│   ├── config_loader.py          # Configuration from config.json / env vars
│   ├── gitlab_client.py          # GitLab API client and data processing
│   └── services.py               # External service health checks
│
├── frontend/                     # Static frontend files (vanilla JS only)
│   ├── index.html                # Main HTML page
│   ├── styles.css                # Dark neomorphic CSS theme
│   ├── app.js                    # DEPRECATED: Thin wrapper for backward compat
│   └── src/                      # ES modules (main source)
│       ├── main.js               # Application bootstrap / entrypoint
│       ├── dashboardApp.js       # DashboardApp class (orchestration)
│       ├── api/
│       │   └── apiClient.js      # API client with timeout support
│       ├── utils/
│       │   ├── formatters.js     # escapeHtml, formatDate, formatDuration
│       │   ├── status.js         # normalizeStatus, normalizeServiceStatus
│       │   └── dom.js            # DOM updates (showError, updateStatusIndicator)
│       └── views/
│           ├── headerView.js     # TV/Compact/Wallboard toggles
│           ├── kpiView.js        # Summary KPI cards rendering
│           ├── repoView.js       # Repository cards with status animations
│           ├── pipelineView.js   # Pipelines table rendering
│           └── serviceView.js    # External services cards
│
├── data/                         # Data files
│   └── mock_scenarios/           # Mock data for testing/demos
│       ├── healthy.json          # Healthy CI/CD state scenario
│       ├── failing.json          # Failing pipeline scenario
│       └── running.json          # Active builds scenario
│
├── tests/                        # Test suite
│   ├── backend_tests/            # Backend unit tests (stdlib unittest)
│   └── frontend_tests/           # Frontend tests
│
├── docs/                         # Documentation
│   └── architecture-overview.md  # This file (start here!)
│
├── config.json.example           # Configuration template
├── .env.example                  # Environment variables template
├── mock_data.json                # Default mock data file
├── README.md                     # Full documentation
└── AGENTS.md                     # Agent workflow guidance
```

## Module Responsibilities

### Backend Modules

| Module | File | Responsibilities |
|--------|------|------------------|
| **HTTP Server** | `backend/app.py` | Entry point, route handlers (`/api/*`), background poller, global STATE management |
| **Config Loader** | `backend/config_loader.py` | Load config from `config.json` and env vars, validate settings, load mock data |
| **GitLab Client** | `backend/gitlab_client.py` | `GitLabAPIClient` class, retry/rate limiting, pagination, data enrichment |
| **Services** | `backend/services.py` | External service health checks (Artifactory, Confluence, etc.) |

**Dependency graph**:
```
app.py
├── imports from config_loader (load_config, validate_config, load_mock_data)
├── imports from gitlab_client (GitLabAPIClient, get_summary, get_repositories, ...)
└── imports from services (get_service_statuses)
```

### Frontend Modules

| Module | File | Responsibilities |
|--------|------|------------------|
| **Entrypoint** | `frontend/src/main.js` | Bootstrap, sanitization checks, DOM ready handling |
| **App Orchestration** | `frontend/src/dashboardApp.js` | `DashboardApp` class, data loading, auto-refresh |
| **API Client** | `frontend/src/api/apiClient.js` | `fetchWithTimeout`, `fetchSummary`, `fetchRepos`, etc. |
| **Formatters** | `frontend/src/utils/formatters.js` | `escapeHtml` (XSS prevention), `formatDate`, `formatDuration` |
| **Status Utils** | `frontend/src/utils/status.js` | `normalizeStatus`, `normalizeServiceStatus` |
| **DOM Utils** | `frontend/src/utils/dom.js` | `showError`, `updateStatusIndicator`, `updateLastUpdated` |
| **Header View** | `frontend/src/views/headerView.js` | TV mode, compact mode, wallboard preset toggles |
| **KPI View** | `frontend/src/views/kpiView.js` | Summary KPI cards rendering |
| **Repo View** | `frontend/src/views/repoView.js` | Repository cards with status animations |
| **Pipeline View** | `frontend/src/views/pipelineView.js` | Pipelines table rendering |
| **Service View** | `frontend/src/views/serviceView.js` | External services cards |

**Frontend module flow**:
```
index.html
└── loads src/main.js (ES module entrypoint)
    └── instantiates DashboardApp (src/dashboardApp.js)
        ├── calls initHeaderToggles() from views/headerView.js
        ├── fetches data via api/apiClient.js
        ├── renders via views/*.js modules
        └── uses utils/*.js for formatting and DOM updates
```

## Data Flow

```
┌─────────────────┐
│   GitLab API    │
└────────┬────────┘
         │ HTTP/HTTPS (urllib)
         ↓
┌─────────────────────────────────────┐
│   BackgroundPoller (Thread)         │
│   - Polls every N seconds           │
│   - Enriches data with metrics      │
│   - Checks external services        │
└────────┬────────────────────────────┘
         │ Thread-safe updates
         ↓
┌─────────────────────────────────────┐
│   Global STATE (in-memory)          │
│   - projects, pipelines, summary    │
│   - services (external health)      │
└────────┬────────────────────────────┘
         │ Fast, non-blocking reads
         ↓
┌─────────────────────────────────────┐
│   HTTP Request Handler (app.py)     │
│   - Serves JSON API endpoints       │
│   - Serves static frontend files    │
└────────┬────────────────────────────┘
         │ HTTP Responses
         ↓
┌─────────────────────────────────────┐
│   Browser (Frontend)                │
│   - DashboardApp fetches every 60s  │
│   - View modules render UI          │
└─────────────────────────────────────┘
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | Health check and backend status |
| `GET /api/summary` | Dashboard statistics (KPIs) |
| `GET /api/repos` | Repository list with pipeline health metrics |
| `GET /api/pipelines` | Recent pipeline runs (supports `?limit=`, `?status=`, `?ref=`, `?project=`) |
| `GET /api/services` | External service health status |
| `POST /api/mock/reload` | Hot-reload mock data (mock mode only) |

## Key Constraints

1. **Backend**: Python standard library only (no pip dependencies)
2. **Frontend**: Vanilla JavaScript only (no frameworks, no build tools)
3. **Theme**: Preserve dark neomorphic UI design
4. **API**: Maintain backward-compatible response shapes

## Where to Make Changes

| Task | Where to Look |
|------|---------------|
| Change how repo cards look | `frontend/src/views/repoView.js` |
| Change how pipelines table looks | `frontend/src/views/pipelineView.js` |
| Change KPI cards | `frontend/src/views/kpiView.js` |
| Change service cards | `frontend/src/views/serviceView.js` |
| Add/modify header toggles | `frontend/src/views/headerView.js` |
| Add date/time formatting | `frontend/src/utils/formatters.js` |
| Modify status normalization | `frontend/src/utils/status.js` |
| Add API fetch function | `frontend/src/api/apiClient.js` |
| Change API routes/handlers | `backend/app.py` |
| Change GitLab API logic | `backend/gitlab_client.py` |
| Change config loading | `backend/config_loader.py` |
| Add external service logic | `backend/services.py` |
| Add new mock scenario | `data/mock_scenarios/` |

## Next Steps

- For full documentation, see [README.md](../README.md)
- For agent workflow guidance, see [AGENTS.md](../AGENTS.md)
- For backend constraints, see `.github/instructions/backend.instructions.md`
- For frontend constraints, see `.github/instructions/frontend.instructions.md`

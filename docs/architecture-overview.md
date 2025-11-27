# Architecture Overview

This document provides a high-level overview of the DSO-Dashboard project structure and components.

## Directory Structure

```
DSO-Dashboard/
├── backend/               # Backend server package
│   ├── __init__.py        # Package init
│   └── app.py             # Main server application (Python stdlib only)
│
├── frontend/              # Static frontend files
│   ├── index.html         # Main HTML page
│   ├── app.js             # Vanilla JavaScript application logic
│   └── styles.css         # Dark neomorphic CSS styles
│
├── data/                  # Data files
│   └── mock_scenarios/    # Mock data scenarios for testing/demos
│       ├── healthy.json   # Healthy CI/CD state scenario
│       ├── failing.json   # Failing pipeline scenario
│       └── running.json   # Active builds scenario
│
├── tests/                 # Test suite
│   ├── backend_tests/     # Backend unit tests (stdlib unittest)
│   └── frontend_tests/    # Frontend tests
│
├── docs/                  # Documentation
│   └── architecture-overview.md  # This file
│
├── config.json.example    # Configuration template
├── .env.example           # Environment variables template
├── mock_data.json         # Default mock data file
├── README.md              # Main documentation
└── AGENTS.md              # AI agent workflow guidance
```

## Component Details

### Backend (`backend/`)

The backend is a pure Python standard library implementation that provides:

- **HTTP Server**: Uses `http.server.HTTPServer` and `SimpleHTTPRequestHandler`
- **GitLab API Client**: Handles all communication with GitLab API via `urllib`
- **Background Poller**: Daemon thread that polls GitLab periodically
- **Thread-Safe State**: In-memory cache protected by `threading.Lock`
- **Static File Server**: Serves frontend files from `frontend/` directory

Key features:
- Zero external dependencies (stdlib-only)
- Retry logic with exponential backoff
- Rate limiting support (429 response handling)
- Full pagination support
- SSL/TLS configuration (custom CA bundles, skip verify option)
- Mock data mode for development and testing

**Entry point**: `python backend/app.py`

### Frontend (`frontend/`)

The frontend is a vanilla JavaScript single-page application:

- **HTML5**: Semantic structure with accessibility features
- **CSS3**: Dark neomorphic theme with CSS custom properties
- **ES6+ JavaScript**: Modern vanilla JS with no frameworks

Key features:
- Auto-refresh every 60 seconds
- TV/Kiosk mode (`?tv=true`)
- XSS prevention (`escapeHtml()`)
- Responsive design (mobile, tablet, desktop)
- Status badges with color coding

**Entry point**: `frontend/index.html` (served by backend)

### Data (`data/`)

Contains mock data scenarios for testing and demonstrations:

- `mock_scenarios/healthy.json`: Mostly successful pipelines
- `mock_scenarios/failing.json`: Multiple consecutive failures
- `mock_scenarios/running.json`: Many active/pending pipelines

Enable mock mode with `USE_MOCK_DATA=true` environment variable.

### Tests (`tests/`)

Test suite organized by component:

- `tests/backend_tests/`: Backend unit tests using `unittest` and `unittest.mock`
- `tests/frontend_tests/`: Frontend tests (JavaScript validation)

Run tests: `python -m unittest discover -s tests -p "test_*.py"`

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
└─────────────────────────────────────┘
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | Health check and status |
| `GET /api/summary` | Dashboard statistics |
| `GET /api/repos` | Repository list with metrics |
| `GET /api/pipelines` | Recent pipeline runs |
| `GET /api/services` | External service health |
| `POST /api/mock/reload` | Hot-reload mock data |

## Key Constraints

1. **Backend**: Python standard library only (no pip dependencies)
2. **Frontend**: Vanilla JavaScript only (no frameworks, no build tools)
3. **Theme**: Preserve dark neomorphic UI design
4. **API**: Maintain backward-compatible response shapes

See [AGENTS.md](../AGENTS.md) for complete development guidelines.

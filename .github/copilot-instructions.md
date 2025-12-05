# GitHub Copilot Instructions for DSO-Dashboard

## What This Project Is

DSO-Dashboard is a GitLab DevSecOps monitoring dashboard with a pure Python standard library backend and vanilla JavaScript frontend. It provides real-time monitoring of GitLab repositories and CI/CD pipelines with a dark neomorphic UI design. The project emphasizes zero external dependencies, making it lightweight, portable, and easy to deploy.

## Project Structure

```
DSO-Dashboard/
├── backend/               # Backend package (Python stdlib only)
│   ├── __init__.py        # Package init
│   └── app.py             # Main server application
├── frontend/              # Static UI assets
│   ├── index.html         # Main page
│   ├── app.js             # Frontend logic (vanilla JS)
│   └── styles.css         # Dark neomorphic styles
├── data/                  # Data files
│   └── mock_scenarios/    # Mock data for testing/demos
├── tests/                 # Test suite
│   ├── backend_tests/     # Backend unit tests (stdlib unittest)
│   └── frontend_tests/    # Frontend tests
├── docs/                  # Documentation
│   └── architecture-overview.md  # Architecture guide
├── config.json.example    # Configuration template
├── .env.example           # Environment variables template
└── .github/               # GitHub configuration
    ├── copilot-instructions.md
    ├── instructions/      # Path-specific instructions
    └── workflows/         # CI/CD workflows
```

## Non-Negotiable Constraints

### Backend Constraints
- **Pure stdlib ONLY**: No pip dependencies. Use only Python standard library modules (`http.server`, `urllib`, `json`, `threading`, etc.)
- Do NOT suggest or add: `requests`, `Flask`, `FastAPI`, `aiohttp`, or any third-party HTTP libraries
- SSL/TLS must use `ssl` module from stdlib
- All HTTP operations must use `urllib.request`

### Frontend Constraints
- **Vanilla JavaScript ONLY**: No frameworks, no build tools
- Do NOT suggest or add: React, Vue, Angular, jQuery, or any JavaScript framework
- No npm, webpack, babel, or Node.js build process
- All code must run directly in the browser

### UI/UX Constraints
- **Preserve dark neomorphic theme**: Don't modify the visual design without explicit request
- Keep existing color palette and shadow effects in `styles.css`
- Maintain TV mode behavior and auto-refresh functionality
- Don't introduce external fonts, icon libraries, or CSS frameworks

## How to Run Locally

1. **Setup configuration:**
   ```bash
   cp config.json.example config.json
   # Edit config.json with your GitLab URL and API token
   ```

2. **Set environment variables (optional):**
   ```bash
   export GITLAB_URL="https://gitlab.com"
   export GITLAB_API_TOKEN="your_token_here"
   export PORT=8080
   export POLL_INTERVAL=60
   export CACHE_TTL=300
   export PER_PAGE=100
   # For self-signed certs (use cautiously):
   export INSECURE_SKIP_VERIFY=false
   ```
   
   Environment variables override `config.json` values.

3. **Run the server:**
   ```bash
   python3 backend/app.py
   ```

4. **Access the dashboard:**
   Open `http://localhost:8080` in your browser

## How to Validate Changes

### Syntax Check
```bash
python -m py_compile backend/app.py
```

### Run Tests
```bash
python -m unittest discover -s tests -p "test_*.py"
```

### Manual Testing
1. Start the server: `python3 backend/app.py`
2. Test API endpoints:
   - `curl http://localhost:8080/api/health`
   - `curl http://localhost:8080/api/summary`
   - `curl http://localhost:8080/api/repos`
   - `curl http://localhost:8080/api/pipelines`
3. Test frontend: Open browser to `http://localhost:8080`

## API Endpoints

The backend provides these JSON endpoints that the frontend depends on:

- `GET /api/health` - Health check (status, timestamp, last poll)
- `GET /api/summary` - Overall statistics (repos, pipelines, success rates)
- `GET /api/repos` - List of repositories with pipeline health metrics
- `GET /api/pipelines` - Recent pipeline runs (supports `?limit=`, `?status=`, `?ref=`, `?project=`)

**Do not modify endpoint paths or break response structure compatibility.**

## Style Guidance

### Python Code Style
- Small, testable functions
- Type hints are acceptable but don't add mypy or ruff
- Meaningful variable names
- Docstrings for classes and non-trivial functions
- Log errors meaningfully but avoid noisy logs
- Follow existing patterns in the codebase

### JavaScript Code Style
- Use modern ES6+ syntax
- Avoid introducing polyfills or transpilation
- Keep functions small and focused
- Use existing `escapeHtml()` for XSS prevention
- Follow the existing code structure

### CSS Style
- Maintain dark color palette
- Keep neomorphic shadow effects
- Use CSS custom properties (CSS variables) for consistency
- Mobile-responsive design

## Safe Editing Rules

### Security
- **Never commit secrets**: API tokens must be in `config.json` (gitignored) or environment variables
- **Never log API tokens**: Redact sensitive data in logs
- **Keep TLS verification on by default**: `insecure_skip_verify` should only be used with explicit user consent
- **Sanitize user input**: Continue using `escapeHtml()` in frontend
- **No SQL injection risk**: This project doesn't use databases

### Backward Compatibility
- Don't rename or remove existing API endpoints
- Don't change response structure of existing endpoints (you can add fields)
- Don't remove or rename DOM element IDs used by JavaScript
- Don't break existing configuration file format

### Testing
- Run tests before committing: `python -m unittest`
- Test both config.json and environment variable configuration methods
- Verify server starts without errors
- Check that all API endpoints return valid JSON

## Architecture Notes

### Backend Architecture
- **Background Polling Thread**: Continuously fetches data from GitLab API
- **Thread-Safe Global STATE**: Shared memory protected by `threading.Lock`
- **Request Handler**: Reads cached state and serves JSON responses
- **Static File Server**: Serves frontend files from `frontend/` directory
- **Retry Logic**: Automatic retry with exponential backoff for transient failures
- **Rate Limiting**: Handles GitLab API 429 responses with Retry-After header

### Frontend Architecture
- **Auto-refresh**: Polls API endpoints every 60 seconds
- **TV Mode**: URL parameter `?tv=true` enables full-screen mode
- **Status Cards**: KPI display with color-coded metrics
- **Repository Cards**: Sortable grid view with pipeline health
- **Pipeline Table**: Recent pipeline runs with filtering

## Common Tasks

### Adding a New API Endpoint
1. Add handler method in `DashboardRequestHandler` class
2. Add route in `do_GET()` method
3. Update frontend `app.js` to consume the endpoint
4. Add tests in `tests/test_*.py`
5. Document in README

### Modifying Frontend
1. Edit HTML/CSS/JS in `frontend/` directory
2. Reload browser to see changes (no build step needed)
3. Test with different screen sizes
4. Verify TV mode still works

### Adding Configuration Options
1. Add field to `config.json.example`
2. Add corresponding environment variable to `.env.example`
3. Update `load_config()` in `backend/app.py`
4. Document in README
5. Add test case

### Adding a New Summary KPI
1. **Backend**: Add the new field to `get_summary()` in `backend/gitlab_client.py` or `_calculate_summary()` in `backend/app.py`
2. **Frontend HTML**: Add a new KPI card or field in `frontend/index.html` with a unique ID
3. **Frontend JS**: Update `renderSummaryKpis()` in `frontend/src/views/kpiView.js` to populate the new field
4. **Tests**: Add backend tests in `tests/backend_tests/test_response_shapes.py` or `test_slo_summary.py`
5. **Tests**: Add frontend tests in `tests/frontend_tests/test_kpi_slo_rendering.py`
6. **Docs**: Update `docs/architecture-overview.md` if the KPI is part of the SLO or observability features

### Extending the Attention Strip with New Signals
1. **Identify the source**: Determine if the signal comes from repos, services, or pipelines
2. **Add detection logic**: Update the appropriate builder function in `frontend/src/views/attentionView.js`:
   - `buildRepoAttentionItems()` for repository signals
   - `buildServiceAttentionItems()` for service signals
   - `buildPipelineAttentionItems()` for pipeline signals
3. **Assign severity**: Use existing levels: `critical`, `high`, `medium`, `low`
4. **Add icon**: Update `getTypeIcon()` if introducing a new item type
5. **Tests**: Add tests in `tests/frontend_tests/test_attention_strip_logic.py` and `test_attention_strip_basic.py`
6. **Respect limits**: Items are capped at `MAX_ATTENTION_ITEMS` (currently 8)

### Extending Sparkline History with New Metric Types
1. **Add history buffer**: Create a new `Map` in `DashboardApp` constructor (e.g., `this.newMetricHistory = new Map()`)
2. **Implement update method**: Add `_updateNewMetricHistory(items)` in `frontend/src/dashboardApp.js` following the pattern of `_updateRepoHistory()`
3. **Create sparkline renderer**: Add `createNewMetricSparkline(history)` in the appropriate view module
4. **Handle edge cases**: Skip null/undefined/NaN values; require minimum 2 data points
5. **Keep window bounded**: Use `this.historyWindow` (default 20) to limit retained data points
6. **Tests**: Add tests in `tests/frontend_tests/test_sparklines_rendering.py`

## Troubleshooting

### Common Issues
- **"GITLAB_API_TOKEN not set"**: Set the token in config.json or environment
- **"Failed to fetch data"**: Check GitLab URL and network connectivity
- **SSL certificate errors**: For self-signed certs, set `insecure_skip_verify: true` (use cautiously)
- **No data showing**: Verify API token has `read_api` scope
- **Port already in use**: Change PORT in config or use `PORT=8081 python3 backend/app.py`

## Contributing

When making changes:
1. Follow the constraints above (stdlib-only, vanilla-only)
2. Write or update tests for your changes
3. Run validation: `python -m py_compile backend/app.py && python -m unittest`
4. Update documentation if adding features or changing behavior
5. Keep commits focused and well-described
6. Ensure backward compatibility with existing deployments

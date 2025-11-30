# Agent Instructions for DSO-Dashboard

This file provides guidance for GitHub Copilot Coding Agents working on this repository.

> **Start here**: Read [`docs/architecture-overview.md`](docs/architecture-overview.md) for a quick understanding of the codebase structure and module responsibilities.

## Quick Reference: Non-Negotiable Constraints

⚠️ **Read `.github/copilot-instructions.md` first** for complete context.

### Stdlib-Only Backend
- ✅ Python standard library only (`http.server`, `urllib`, `json`, `threading`)
- ❌ NO pip dependencies (`requests`, `Flask`, `FastAPI`, etc.)

### Vanilla-Only Frontend
- ✅ Plain HTML/CSS/JavaScript (ES6+)
- ❌ NO frameworks (`React`, `Vue`, `jQuery`, etc.)
- ❌ NO build tools (`npm`, `webpack`, `babel`, etc.)

### Preserve Existing Design
- ✅ Keep dark neomorphic UI theme
- ✅ Maintain API endpoint contracts
- ✅ Preserve DOM structure and IDs

### Use Existing Modules - Don't Duplicate
- ✅ Import helpers from `frontend/src/utils/` (formatters, status, dom)
- ✅ Import API functions from `frontend/src/api/apiClient.js`
- ✅ Import backend helpers from `backend/config_loader.py`, `backend/gitlab_client.py`, `backend/services.py`
- ❌ Don't re-implement `escapeHtml()`, `formatDate()`, `normalizeStatus()` etc.
- ❌ Don't duplicate GitLab API client logic

## Checklists for Adding Features

### Adding a New Dashboard Section (Frontend)

1. **Create view module**: Add `frontend/src/views/<section>View.js`
   - Export a `render<Section>(data)` function
   - Import from `utils/formatters.js` for `escapeHtml()`, `formatDate()`, etc.
   - Import from `utils/status.js` for status normalization
2. **Add API fetch function** (if new endpoint): Update `frontend/src/api/apiClient.js`
3. **Add container element**: Update `frontend/index.html` with ID for the section
4. **Wire up in DashboardApp**: Import and call view in `frontend/src/dashboardApp.js`
5. **Add styles**: Update `frontend/styles.css` (use CSS custom properties)
6. **Test**: Verify rendering, TV mode, auto-refresh, responsive design

### Adding a New API Endpoint (Backend)

1. **Add handler method**: Create `handle_<name>(self)` in `DashboardRequestHandler` (`backend/app.py`)
2. **Add route**: Register in `do_GET()` method path matching
3. **Use existing helpers**: Import from `gitlab_client.py` or `services.py` if applicable
4. **Return proper JSON shape**: Use `send_json_response()` with `backend_status`, `last_updated`, `is_mock`
5. **Add tests**: Create or update `tests/backend_tests/test_<feature>.py`
6. **Document**: Update README "API Endpoints" section

### Adding a New External Service Type

1. **No code change needed** for standard HTTP health checks
2. **Add to config.json**: Include in `external_services` array with `url`, `name`, `id`
3. **For custom logic**: Modify `backend/services.py` `_check_single_service()`
4. **Test**: Use mock data with services array to verify `/api/services` response

### Adding a New Configuration Option

1. **Add to template**: Update `config.json.example`
2. **Add env var**: Update `.env.example`
3. **Load in config_loader.py**: Add parsing in `load_config()`, add to `validate_config()` if needed
4. **Use in app.py**: Access via `config['new_option']`
5. **Document**: Update README "Configuration Options" section
6. **Test**: Verify loading from both config.json and env var

## Definition of Done for Pull Requests

Before marking a PR as complete, ensure:

### Code Quality
- [ ] Changes compile/run without errors: `python -m py_compile backend/app.py`
- [ ] All tests pass: `python -m unittest discover -s tests`
- [ ] No external dependencies added (stdlib-only for backend, vanilla-only for frontend)
- [ ] Code follows existing style and patterns
- [ ] Logging is appropriate (informative, not noisy, no secrets)

### Testing
- [ ] Tests added or updated for new functionality
- [ ] Edge cases covered (empty data, None vs [], API failures)
- [ ] Manual testing performed (see validation section below)

### Documentation
- [ ] README updated if behavior changes
- [ ] API endpoint documentation updated if endpoints modified
- [ ] Configuration options documented if config changes
- [ ] Comments added for complex logic (if needed)

### Compatibility
- [ ] No breaking changes to existing API endpoints
- [ ] No breaking changes to frontend DOM IDs or structure
- [ ] Backend endpoints return expected JSON structure
- [ ] Frontend works with both config.json and environment variables
- [ ] TV mode still works (`?tv=true`)
- [ ] Auto-refresh still works

### Security
- [ ] No secrets committed (API tokens in config.json or env vars only)
- [ ] API tokens not logged (use `'***'` redaction)
- [ ] User input sanitized (use `escapeHtml()` in frontend)
- [ ] TLS verification enabled by default
- [ ] No new security vulnerabilities introduced

## Agent Workflow

Follow this workflow when addressing tasks:

### 1. Read Context
```bash
# Read the repository instructions
cat .github/copilot-instructions.md
cat .github/instructions/backend.instructions.md  # If touching Python
cat .github/instructions/frontend.instructions.md  # If touching JS/HTML/CSS

# Read the architecture overview
cat docs/architecture-overview.md
```

**Key things to understand:**
- Project structure and architecture
- Constraints (stdlib-only, vanilla-only)
- API contracts and data flow
- Testing approach

### 2. Identify Impacted Files

Based on the task, determine which files need changes:

**Backend tasks (API, polling, config):**
- `backend/app.py` - Core backend logic (main server file, route handlers)
- `backend/gitlab_client.py` - GitLab API client and data processing functions
- `backend/services.py` - External service health check functions
- `backend/config_loader.py` - Configuration loading from config.json and environment variables
- `config.json.example` - Configuration template
- `.env.example` - Environment variables
- `tests/backend_tests/test_*.py` - Backend tests

## Backend Modules

The backend is organized into focused modules for maintainability:

### `backend/app.py` - HTTP Server & Routes
The main entry point that:
- Sets up the HTTP server (`DashboardServer`, `DashboardRequestHandler`)
- Defines route handlers for API endpoints (`/api/summary`, `/api/repos`, `/api/pipelines`, `/api/services`, `/api/health`)
- Manages the background poller (`BackgroundPoller`)
- Handles global state management (`STATE`, `STATE_LOCK`)

### `backend/gitlab_client.py` - GitLab API Client
Contains GitLab-specific functionality:
- `GitLabAPIClient` class - HTTP client with retry, rate limiting, and pagination
- `get_summary()` - Calculate summary statistics from projects and pipelines
- `get_repositories()` - Format repository data for API response
- `get_pipelines()` - Format and filter pipeline data for API response
- `enrich_projects_with_pipelines()` - Add pipeline health metrics to projects
- Constants: `MAX_PROJECTS_FOR_PIPELINES`, `PIPELINES_PER_PROJECT`, `IGNORED_PIPELINE_STATUSES`

### `backend/services.py` - External Service Checks
Handles external service health monitoring:
- `get_service_statuses()` - Check health of configured external services
- `_check_single_service()` - Perform HTTP health check on a single service
- Constants: `DEFAULT_SERVICE_CHECK_TIMEOUT`

### `backend/config_loader.py` - Configuration Management
Configuration loading and validation:
- `load_config()` - Load config from config.json and environment variables
- `validate_config()` - Validate configuration values (fail-fast on invalid)
- `load_mock_data()` - Load mock data from mock_data.json or scenario files
- `parse_int_config()`, `parse_csv_list()` - Config parsing helpers
- Constants: `PROJECT_ROOT`, `VALID_LOG_LEVELS`

### Module Dependencies
```
app.py
├── imports from config_loader (load_config, validate_config, load_mock_data, ...)
├── imports from gitlab_client (GitLabAPIClient, get_summary, get_repositories, ...)
└── imports from services (get_service_statuses, ...)
```

When modifying backend behavior:
- **GitLab API calls**: Modify `backend/gitlab_client.py`
- **Service health checks**: Modify `backend/services.py`
- **Configuration loading/validation**: Modify `backend/config_loader.py`
- **Route handlers and server setup**: Modify `backend/app.py`

**Frontend tasks (UI, dashboard, display):**
- `frontend/src/main.js` - Main JavaScript entrypoint (ES module)
- `frontend/src/dashboardApp.js` - DashboardApp class (ES module)
- `frontend/index.html` - Page structure (main HTML entry point)
- `frontend/app.js` - DEPRECATED: Thin wrapper for backward compatibility
- `frontend/styles.css` - Styles and theme (main CSS entry point)
- `tests/frontend_tests/test_*.py` - Frontend tests

**Frontend entrypoints:**
Start with these files when working on JavaScript logic:
- `frontend/src/main.js` - Application bootstrap, sanitization checks, DOM ready handling
- `frontend/src/dashboardApp.js` - Main `DashboardApp` class with dashboard orchestration

The HTML loads the entrypoint via `<script type="module" src="./src/main.js"></script>`.

**View modules (UI rendering):**
All UI rendering is organized under `frontend/src/views/`. Each file corresponds to a specific section of the dashboard:
- `frontend/src/views/headerView.js` - Header toggles (TV Mode, Compact Mode, Wallboard View). Exports `initHeaderToggles()`, `checkTVMode()`, `checkDensityMode()`, `setupTVToggle()`, `setupDensityToggle()`, `setupWallboardPreset()`, `updateWallboardButtonState()`
- `frontend/src/views/kpiView.js` - Summary KPI cards rendering. Exports `renderSummaryKpis(data)`
- `frontend/src/views/repoView.js` - Repository cards with status animations. Exports `renderRepositories(repos, previousState)`, `createRepoCard(repo, extraClasses)`, `getRepoKey(repo)`
- `frontend/src/views/pipelineView.js` - Pipelines table rendering. Exports `renderPipelines(pipelines)`, `createPipelineRow(pipeline)`
- `frontend/src/views/serviceView.js` - External services cards. Exports `renderServices(services)`, `createServiceCard(service)`

When making UI tweaks, go to the appropriate view module. The `DashboardApp` class coordinates data fetching and calls these view functions for rendering.

**Utility modules:**
Reusable helpers extracted from `DashboardApp` to keep code focused and DRY:
- `frontend/src/api/apiClient.js` - API client with `fetchWithTimeout`, `fetchSummary()`, `fetchRepos()`, `fetchPipelines()`, `fetchServices()`, `checkBackendHealth()`
- `frontend/src/utils/formatters.js` - Data formatting: `escapeHtml()`, `formatDate()`, `formatDuration()`
- `frontend/src/utils/status.js` - Status normalization: `normalizeStatus()`, `normalizeServiceStatus()`
- `frontend/src/utils/dom.js` - DOM updates: `showError()`, `updateStatusIndicator()`, `updateLastUpdated()`, `showPartialStaleWarning()`, `showAllStaleWarning()`, `updateMockBadge()`

When implementing new features, import from these modules instead of re-implementing helpers.

**Documentation tasks:**
- `README.md` - Main documentation
- `docs/architecture-overview.md` - Architecture guide (starting point for agents)
- `.github/copilot-instructions.md` - Agent instructions

**Infrastructure tasks:**
- `.github/workflows/*.yml` - CI/CD
- `.gitignore` - Ignored files
- `tests/` - Test infrastructure

### 3. Implement Smallest Viable Change

**Make minimal modifications:**
- Don't refactor unrelated code
- Don't "improve" working code unless asked
- Don't change visual design unless requested
- Don't add features beyond the task scope

**Examples:**

✅ **Good (minimal):** Add a new query parameter to `/api/pipelines`
- Modify only the `handle_pipelines()` method
- Add parameter parsing
- Update tests for the new parameter
- Document the new parameter in README

❌ **Bad (scope creep):** Add a new query parameter to `/api/pipelines`
- Refactor entire `DashboardRequestHandler` class
- Add a new caching layer
- Redesign the frontend to use the parameter
- Add a new database backend

### 4. Run Validations

**Before committing, validate your changes:**

```bash
# Validate Python syntax
python -m py_compile backend/app.py

# Run tests (if tests exist)
python -m unittest discover -s tests -p "test_*.py"

# Start server manually
python3 backend/app.py
# Keep running and test in another terminal...

# Test API endpoints
curl http://localhost:8080/api/health
curl http://localhost:8080/api/summary
curl http://localhost:8080/api/repos
curl http://localhost:8080/api/pipelines

# Test frontend in browser
# Open http://localhost:8080
# Verify UI renders correctly
# Test TV mode: http://localhost:8080?tv=true
# Check browser console for errors
```

### 5. Update Documentation

**If your changes affect behavior, update:**

- **README.md**: For user-facing changes (new config options, new endpoints, setup changes)
- **docs/architecture-overview.md**: For structural changes
- **API Documentation**: If you modified endpoint behavior or added parameters
- **Configuration examples**: Update `config.json.example` and `.env.example`
- **Comments**: Add comments only if the code is not self-explanatory

**Don't update docs if:**
- Internal implementation changes only
- No user-visible behavior changes
- Fixing bugs that restore intended behavior

## Common Task Patterns

### Adding a New Configuration Option

1. Add field to `config.json.example` with comment
2. Add corresponding env var to `.env.example`
3. Update `load_config()` in `backend/config_loader.py` to read the option
4. Add validation in `validate_config()` if needed
5. Use the config value in your feature
6. Document in README "Configuration Options" section
7. Add test case for config loading

### Adding a New API Endpoint

1. Add handler method in `DashboardRequestHandler` class (`backend/app.py`)
2. Add route in `do_GET()` method
3. Return JSON with `send_json_response()`
4. Import and use helpers from `backend/gitlab_client.py` or `backend/services.py` if applicable
5. Update frontend if needed (add fetch in `frontend/src/api/apiClient.js`)
6. Add tests for the endpoint
7. Document in README "API Endpoints" section

### Modifying Frontend UI

1. Edit HTML structure in `frontend/index.html`
2. Add styles in `frontend/styles.css` (use CSS variables)
3. For rendering logic, modify the appropriate view module in `frontend/src/views/`:
   - **Header toggles** (TV/Compact/Wallboard): `views/headerView.js`
   - **Summary KPIs**: `views/kpiView.js`
   - **Repository cards**: `views/repoView.js`
   - **Pipelines table**: `views/pipelineView.js`
   - **Services cards**: `views/serviceView.js`
4. For orchestration logic, modify `frontend/src/dashboardApp.js`
5. Test in browser at multiple screen sizes
6. Test TV mode (`?tv=true`)
7. Verify auto-refresh still works

### Adding Tests

1. Create `tests/test_<feature>.py` if new module
2. Import `unittest` and the code under test
3. Write test class extending `unittest.TestCase`
4. Add test methods starting with `test_`
5. Use `unittest.mock` for external dependencies
6. Run: `python -m unittest tests.test_<feature>`

### Fixing a Bug

1. Reproduce the bug
2. Write a test that fails due to the bug
3. Fix the bug with minimal code change
4. Verify the test now passes
5. Run all tests to ensure no regressions
6. Update docs only if behavior was unclear

### Working with External Services

The `external_services` configuration allows monitoring of external tools (Artifactory, Confluence, Jira, etc.). When working with this feature:

**Configuration:**
- Each service entry requires a `url` field (the health-check endpoint to probe)
- Optional fields: `id`, `name`, `timeout`, `critical`, `kind`
- Services are validated at startup; invalid entries (non-dict or missing `url`) cause a fatal error and the server will not start

**Backend Behavior:**
- Services are checked during each poll cycle via `BackgroundPoller._check_external_services()`
- Service checks run independently of GitLab API calls (continue even when GitLab is unreachable)
- Results are available via `GET /api/services` endpoint

**Frontend Behavior:**
- The Core Services panel renders service cards from `/api/services` response
- Panel shows "No services configured" when the list is empty
- Service status is displayed as UP (green) or DOWN (red) with latency and last check time

**Testing:**
- Use `USE_MOCK_DATA=true` with mock data that includes a `services` array
- Validate `/api/services` returns proper JSON shape (always has `services` array)

## Troubleshooting Common Issues

### "ImportError: No module named 'requests'"
- ❌ Someone added a non-stdlib import
- ✅ Remove the import and use `urllib.request` instead

### Frontend not loading after changes
- Check browser console for JavaScript errors
- Verify API endpoints return valid JSON: `curl http://localhost:8080/api/summary`
- Check if DOM IDs changed (JavaScript expects specific IDs)

### Tests failing after changes
- Run tests individually to isolate: `python -m unittest tests.test_<module>.TestClass.test_method`
- Check if you modified the API contract (response structure)
- Verify test mocks match actual function signatures

### CI workflow failing
- Run the same commands locally: `python -m py_compile backend/app.py && python -m unittest`
- Check if you need to update test fixtures
- Review CI logs for specific error messages

### Server won't start
- Check if GITLAB_API_TOKEN is set
- Verify port is available: `lsof -i :8080`
- Look for Python syntax errors: `python -m py_compile backend/app.py`
- Check logs for specific error messages

## Security Checklist

Before committing, verify:

- [ ] No API tokens in code or config files (only in gitignored `config.json`)
- [ ] API tokens not logged (check logger calls)
- [ ] User input sanitized (frontend uses `escapeHtml()`)
- [ ] No SQL injection risk (this project doesn't use SQL, but be aware)
- [ ] TLS verification enabled by default (only disable with explicit flag)
- [ ] Error messages don't leak sensitive information
- [ ] No hardcoded credentials or secrets

## Testing Matrix

### Backend Testing
```bash
# Syntax check
python -m py_compile backend/app.py

# Unit tests
python -m unittest discover -s tests

# Integration test
python3 backend/app.py &
sleep 5
curl http://localhost:8080/api/health
curl http://localhost:8080/api/summary
kill %1
```

### Frontend Testing
- [ ] Desktop Chrome (1920x1080)
- [ ] Desktop Firefox (1920x1080)
- [ ] Tablet (768x1024)
- [ ] Mobile (375x667)
- [ ] TV mode enabled (`?tv=true`)
- [ ] Auto-refresh (wait 60s, verify data updates)

### API Contract Testing
```bash
# Test expected response structure
curl http://localhost:8080/api/summary | jq '.total_repositories'
curl http://localhost:8080/api/repos | jq '.repositories[0].name'
curl http://localhost:8080/api/pipelines | jq '.pipelines[0].status'
curl http://localhost:8080/api/health | jq '.backend_status'
```

## Examples of Good vs. Bad Changes

### ✅ Good: Minimal, Focused Change
**Task:** Add a `?ref=` filter to `/api/pipelines`

**Changes:**
1. Modify `handle_pipelines()` to parse `ref` query parameter
2. Filter pipelines by `ref` if parameter provided
3. Add test case for ref filtering
4. Document in README under "API Endpoints"

**Lines changed:** ~15 lines

### ❌ Bad: Scope Creep
**Task:** Add a `?ref=` filter to `/api/pipelines`

**Changes made:**
1. Added ref filtering ✓
2. Refactored entire request handler class
3. Added a new caching layer
4. Redesigned frontend to add ref dropdown
5. Added SQLite database for query history
6. Added new dependency `flask-sqlalchemy`

**Lines changed:** ~500 lines, added external dependency

**Problems:** Violates stdlib-only constraint, introduces breaking changes, massive scope increase

### ✅ Good: Bug Fix with Test
**Task:** Fix bug where empty pipeline list causes crash

**Changes:**
1. Add test that reproduces bug with empty list
2. Add null check in `handle_pipelines()`: `if not pipelines: pipelines = []`
3. Verify test passes

**Lines changed:** ~5 lines + test

### ❌ Bad: Over-Engineering
**Task:** Fix bug where empty pipeline list causes crash

**Changes made:**
1. Added comprehensive error handling framework
2. Added retry logic to all API endpoints
3. Added error reporting to external service
4. Redesigned state management

**Lines changed:** ~200 lines

**Problems:** Over-engineered solution, added complexity unnecessarily

## Questions to Ask Before Submitting

1. **Constraints:**
   - Did I add any external dependencies? (Should be NO)
   - Did I use stdlib for backend? (Should be YES)
   - Did I use vanilla JS for frontend? (Should be YES)

2. **Testing:**
   - Do all tests pass? (Should be YES)
   - Did I add tests for new functionality? (Should be YES if applicable)
   - Did I test manually? (Should be YES)

3. **Compatibility:**
   - Did I break any existing API contracts? (Should be NO)
   - Did I change frontend DOM structure unnecessarily? (Should be NO)
   - Does TV mode still work? (Should be YES)

4. **Documentation:**
   - Did I update README for user-facing changes? (Should be YES if applicable)
   - Are config examples up to date? (Should be YES)

5. **Security:**
   - Did I commit any secrets? (Should be NO)
   - Did I log any sensitive data? (Should be NO)
   - Did I sanitize user input? (Should be YES)

6. **Scope:**
   - Did I make the minimal change needed? (Should be YES)
   - Did I refactor unrelated code? (Should be NO)
   - Did I add requested features only? (Should be YES)

## Getting Help

If you're unsure about:
- **Constraints:** Re-read `.github/copilot-instructions.md`
- **Backend patterns:** Check `.github/instructions/backend.instructions.md`
- **Frontend patterns:** Check `.github/instructions/frontend.instructions.md`
- **Existing code:** Look at similar functionality already implemented
- **Testing:** Check existing tests in `tests/` directory

**When in doubt, ask the user for clarification rather than making assumptions.**

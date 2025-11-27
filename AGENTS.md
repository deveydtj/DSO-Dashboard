# Agent Instructions for DSO-Dashboard

This file provides guidance for GitHub Copilot Coding Agents working on this repository.

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

## Definition of Done for Pull Requests

Before marking a PR as complete, ensure:

### Code Quality
- [ ] Changes compile/run without errors: `python -m py_compile server.py`
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
```

**Key things to understand:**
- Project structure and architecture
- Constraints (stdlib-only, vanilla-only)
- API contracts and data flow
- Testing approach

### 2. Identify Impacted Files

Based on the task, determine which files need changes:

**Backend tasks (API, polling, config):**
- `server.py` - Core backend logic
- `config.json.example` - Configuration template
- `.env.example` - Environment variables
- `tests/test_*.py` - Backend tests

**Frontend tasks (UI, dashboard, display):**
- `frontend/index.html` - Page structure
- `frontend/app.js` - Frontend logic
- `frontend/styles.css` - Styles and theme

**Documentation tasks:**
- `README.md` - Main documentation
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
python -m py_compile server.py

# Run tests (if tests exist)
python -m unittest discover -s tests -p "test_*.py"

# Start server manually
python3 server.py
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
3. Update `load_config()` in `server.py` to read the option
4. Use the config value in your feature
5. Document in README "Configuration Options" section
6. Add test case for config loading

### Adding a New API Endpoint

1. Add handler method in `DashboardRequestHandler` class
2. Add route in `do_GET()` method
3. Return JSON with `send_json_response()`
4. Update frontend if needed (`app.js`)
5. Add tests for the endpoint
6. Document in README "API Endpoints" section

### Modifying Frontend UI

1. Edit HTML structure in `frontend/index.html`
2. Add styles in `frontend/styles.css` (use CSS variables)
3. Add JavaScript logic in `frontend/app.js`
4. Test in browser at multiple screen sizes
5. Test TV mode (`?tv=true`)
6. Verify auto-refresh still works

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
- Run the same commands locally: `python -m py_compile server.py && python -m unittest`
- Check if you need to update test fixtures
- Review CI logs for specific error messages

### Server won't start
- Check if GITLAB_API_TOKEN is set
- Verify port is available: `lsof -i :8080`
- Look for Python syntax errors: `python -m py_compile server.py`
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
python -m py_compile server.py

# Unit tests
python -m unittest discover -s tests

# Integration test
python3 server.py &
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

# Plan: Handle Client Disconnect Errors During JSON Writes

## Context
Users are seeing `ConnectionAbortedError: [WinError 10053]` when the backend writes JSON responses (e.g., `/api/health`). This typically means the client closed the connection before the server finished writing. The current implementation writes directly to `self.wfile` without handling client disconnects in `send_json_response()`.

## Goals
- Avoid noisy tracebacks when clients disconnect mid-response.
- Preserve existing API response shapes and behavior.
- Keep backend stdlib-only and minimal changes.

## Non-Negotiable Constraints
- **Stdlib-only backend** (no third-party dependencies).
- **No API contract changes** (same JSON shape, same endpoints).
- **Minimal changes** limited to error handling around writes.

## Affected Area
- `backend/app.py` → `DashboardRequestHandler.send_json_response()`

## Proposed Fix (Minimal)
1. **Add safe write handling** in `send_json_response()`:
   - Wrap `self.wfile.write(...)` in a `try/except`.
   - Catch `ConnectionAbortedError`, `ConnectionResetError`, `BrokenPipeError`.
   - Log at a low severity (debug/info) to avoid noise.
   - Return early without raising.
2. **(Optional)** Add a small helper method (e.g., `_safe_write`) if that keeps the code clearer, but avoid unnecessary refactors.

## Test Plan
- **Manual** (no new automated tests required unless behavior changes):
  1. Start server: `python3 backend/app.py`
  2. Trigger `/api/health` from a client and cancel mid-request (e.g., close tab or abort fetch).
  3. Confirm server does **not** emit a stack trace; logs show a single low-severity entry.
- **Sanity checks**:
  - `python -m py_compile backend/app.py`
  - `python -m unittest discover -s tests -p "test_*.py"`

## Acceptance Criteria
- Client disconnects no longer produce stack traces in logs.
- Normal requests still return valid JSON.
- No changes to API response structure or endpoint behavior.

## Notes for the Coding Agent
- Keep changes tight and localized.
- Do **not** add dependencies or refactor unrelated code.
- Preserve existing logging conventions.

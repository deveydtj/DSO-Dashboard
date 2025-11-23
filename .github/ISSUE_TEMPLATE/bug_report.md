---
name: Bug Report
about: Report a bug or issue with the DSO-Dashboard
title: '[BUG] '
labels: bug
assignees: ''
---

## Bug Summary
<!-- Provide a clear and concise description of the bug -->


## Steps to Reproduce
<!-- Detailed steps to reproduce the behavior -->

1. Setup/Configuration:
   - GitLab URL: 
   - Config method: `config.json` / Environment variables / Both
   - Specific config values (redact tokens):
   
2. Actions taken:
   - 
   - 
   - 

3. Observed behavior:
   - 

## Expected Behavior
<!-- What should happen instead? -->


## Actual Behavior
<!-- What actually happened? -->


## Environment
<!-- Please complete the following information -->

- **Python Version:** [e.g., Python 3.10.5]
- **OS:** [e.g., Ubuntu 22.04, macOS 13, Windows 11]
- **Browser (if frontend issue):** [e.g., Chrome 120, Firefox 121]
- **Deployment:** [e.g., local development, Docker, production server]

## Logs/Screenshots
<!-- Provide relevant logs, error messages, or screenshots -->

### Server Logs
```
[Paste relevant server logs here]
```

### Browser Console (if applicable)
```
[Paste browser console errors here]
```

### Screenshots (if applicable)
<!-- Drag and drop images here -->


## Configuration
<!-- Share your configuration (REDACT API TOKENS) -->

**config.json (redacted):**
```json
{
  "gitlab_url": "https://gitlab.example.com",
  "api_token": "***REDACTED***",
  "group_ids": [],
  "poll_interval_sec": 60
}
```

**Environment Variables (redacted):**
```bash
GITLAB_URL=https://gitlab.example.com
GITLAB_API_TOKEN=***REDACTED***
```

## Acceptance Criteria
<!-- What needs to happen for this bug to be considered fixed? -->

- [ ] Bug no longer occurs when following reproduction steps
- [ ] No regressions in related functionality
- [ ] Tests added to prevent regression
- [ ] Documentation updated if needed

## Files Likely to Change
<!-- Help the agent identify relevant files -->

**Backend:**
- [ ] `server.py` - Core backend logic
- [ ] `config.json.example` - Config template
- [ ] `tests/test_*.py` - Backend tests

**Frontend:**
- [ ] `frontend/index.html` - Page structure
- [ ] `frontend/app.js` - Frontend logic
- [ ] `frontend/styles.css` - Styles

**Infrastructure:**
- [ ] `.github/workflows/*.yml` - CI/CD
- [ ] `README.md` - Documentation

**Constraints reminder:**
- Backend must remain stdlib-only (no pip dependencies)
- Frontend must remain vanilla JS/HTML/CSS (no frameworks)

## Additional Context
<!-- Any other information that might be helpful -->


## Related Issues/PRs
<!-- Link to related issues or pull requests -->


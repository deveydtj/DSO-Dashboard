## Summary
<!-- Provide a brief summary of your changes -->


## Related Issue
<!-- Link to the issue this PR addresses -->

Fixes #
Closes #
Related to #

## What Changed
<!-- Describe the changes made in this PR -->

### Backend Changes
<!-- List backend modifications -->

- 
- 

### Frontend Changes
<!-- List frontend modifications -->

- 
- 

### Infrastructure Changes
<!-- List CI/CD, config, or tooling changes -->

- 
- 

### Documentation Changes
<!-- List documentation updates -->

- 
- 

## Why These Changes
<!-- Explain the reasoning behind your approach -->


## Validation Steps
<!-- Describe how you tested these changes -->

### Automated Tests
```bash
# Syntax check
python -m py_compile server.py

# Unit tests
python -m unittest discover -s tests
```

**Test Results:**
- [ ] All tests pass
- [ ] New tests added for new functionality
- [ ] Edge cases covered

### Manual Testing

#### Backend Testing
```bash
# Server starts successfully
python3 server.py

# API endpoints work
curl http://localhost:8080/api/health
curl http://localhost:8080/api/summary
curl http://localhost:8080/api/repos
curl http://localhost:8080/api/pipelines
```

**Results:**
- [ ] Server starts without errors
- [ ] All API endpoints return valid JSON
- [ ] No exceptions in server logs

#### Frontend Testing
- [ ] Dashboard loads in browser (http://localhost:8080)
- [ ] No JavaScript errors in console
- [ ] Data displays correctly
- [ ] TV mode works (`?tv=true`)
- [ ] Auto-refresh works (wait 60 seconds)
- [ ] Mobile responsive (tested at 375px, 768px, 1024px)
- [ ] Dark neomorphic theme preserved

#### Configuration Testing
- [ ] Works with `config.json`
- [ ] Works with environment variables
- [ ] Environment variables override `config.json` correctly
- [ ] Handles missing/invalid config gracefully

### Test Environment
- **Python Version:** 
- **OS:** 
- **Browser (if applicable):** 

## Screenshots/Demo
<!-- If UI changes, include before/after screenshots or video -->

### Before
<!-- Screenshot or description of old behavior -->


### After
<!-- Screenshot or description of new behavior -->


## Risks and Rollback
<!-- Identify potential risks and how to mitigate them -->

### Risks
- 
- 

### Rollback Plan
<!-- How to revert these changes if needed -->

1. 
2. 

## Checklist
<!-- Complete this checklist before requesting review -->

### Code Quality
- [ ] Code follows existing style and patterns
- [ ] Functions are small and focused
- [ ] Complex logic has comments/docstrings
- [ ] No dead code or commented-out code
- [ ] Error handling is appropriate

### Constraints (Critical)
- [ ] **Backend remains stdlib-only** (no `requests`, `Flask`, etc.)
- [ ] **Frontend remains vanilla JS/HTML/CSS** (no React, Vue, jQuery, npm, webpack)
- [ ] No external dependencies added
- [ ] Dark neomorphic UI theme preserved

### Compatibility
- [ ] **No breaking changes** to existing API endpoints
- [ ] **No breaking changes** to frontend DOM IDs/structure
- [ ] Endpoint response structures maintain backward compatibility
- [ ] TV mode functionality preserved
- [ ] Auto-refresh functionality preserved

### Testing
- [ ] All existing tests pass
- [ ] New tests added for new functionality
- [ ] Manual testing completed
- [ ] Edge cases tested (empty data, None, errors)

### Security
- [ ] **No secrets committed** (tokens only in `config.json` or env vars)
- [ ] **API tokens not logged** (redacted with `'***'`)
- [ ] User input sanitized (frontend uses `escapeHtml()`)
- [ ] TLS verification enabled by default
- [ ] No new security vulnerabilities introduced

### Documentation
- [ ] README updated (if user-facing changes)
- [ ] API documentation updated (if endpoints changed)
- [ ] Config examples updated (`config.json.example`, `.env.example`)
- [ ] Code comments added (where needed for clarity)

### Validation
- [ ] `python -m py_compile server.py` passes
- [ ] `python -m unittest` passes
- [ ] Server starts and runs without errors
- [ ] Browser console has no errors
- [ ] Tested in multiple browsers (if frontend changes)

## Additional Notes
<!-- Any other information reviewers should know -->


## Reviewer Guidance
<!-- Help reviewers focus on important aspects -->

**Key areas to review:**
- 
- 

**Questions for reviewers:**
- 
- 

---

## For Maintainers

### Merge Checklist
- [ ] PR title is clear and descriptive
- [ ] All CI checks pass
- [ ] Code review completed
- [ ] Breaking changes documented (if any)
- [ ] Release notes updated (if applicable)

### Post-Merge Tasks
- [ ] Monitor for issues after deployment
- [ ] Update related documentation
- [ ] Notify stakeholders (if significant change)

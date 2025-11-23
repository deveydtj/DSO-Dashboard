---
applyTo:
  - "frontend/**"
---

# Frontend Instructions (Vanilla JavaScript Only)

## Absolute Rule: Vanilla Only

**NEVER suggest or add frameworks, build tools, or npm packages.** This frontend must remain pure HTML/CSS/JavaScript that runs directly in the browser.

### Prohibited Tools/Libraries
- ❌ React, Vue, Angular, Svelte - Use vanilla JavaScript
- ❌ jQuery - Use native DOM APIs
- ❌ npm, webpack, babel, rollup - No build process
- ❌ TypeScript - Use vanilla JavaScript
- ❌ Sass, Less, PostCSS - Use plain CSS
- ❌ Bootstrap, Tailwind - Use custom CSS
- ❌ Icon libraries (Font Awesome, etc.) - Use Unicode symbols or inline SVG
- ❌ External fonts (Google Fonts, etc.) - Use system fonts

### Allowed Technologies
- ✅ HTML5 with semantic elements
- ✅ CSS3 with custom properties (variables)
- ✅ Modern JavaScript (ES6+)
- ✅ Native Fetch API for HTTP requests
- ✅ Native DOM APIs (`querySelector`, `addEventListener`, etc.)
- ✅ CSS Grid and Flexbox for layout
- ✅ CSS animations and transitions

## UI Preservation Requirements

### Dark Neomorphic Theme
The current design is a carefully crafted dark neomorphic theme. **Preserve these characteristics:**

#### Color Palette
```css
/* Core colors from styles.css - DO NOT MODIFY without explicit request */
--bg-primary: #1a1d29;      /* Main background */
--bg-secondary: #22252f;    /* Card background */
--shadow-dark: #12141a;     /* Darker shadow for depth */
--shadow-light: #2a2e3a;    /* Lighter shadow for highlights */
--text-primary: #e8eaed;    /* Main text */
--text-secondary: #9aa0a6;  /* Secondary text */
--accent-blue: #4a9eff;     /* Primary accent */
--success: #34a853;         /* Success status */
--warning: #fbbc04;         /* Warning status */
--error: #ea4335;           /* Error/failed status */
--running: #4a9eff;         /* Running status */
```

#### Neomorphic Effects
```css
/* Card shadows create soft, raised appearance */
box-shadow: 
  8px 8px 16px var(--shadow-dark),
  -8px -8px 16px var(--shadow-light);

/* Inset shadows for pressed/input elements */
box-shadow: 
  inset 4px 4px 8px var(--shadow-dark),
  inset -4px -4px 8px var(--shadow-light);
```

**Don't flatten the design, remove shadows, or change the neomorphic aesthetic.**

### TV Mode Behavior
The dashboard supports a TV/kiosk mode via `?tv=true` URL parameter:
- Full-screen layout
- Removes unnecessary UI chrome
- Larger text and cards
- **Must continue working after any changes**

### Auto-Refresh
- Frontend polls API endpoints every 60 seconds
- Visual indicator shows last update time
- Continues polling even when tab is inactive (for TV mode)
- **Don't break the polling mechanism**

## Data Contract with Backend

### API Endpoints Used
The frontend depends on these API contracts:

#### GET /api/summary
```javascript
{
  "total_repositories": 10,
  "active_repositories": 8,
  "total_pipelines": 50,
  "successful_pipelines": 45,
  "failed_pipelines": 3,
  "running_pipelines": 2,
  "pending_pipelines": 1,
  "pipeline_success_rate": 0.90,
  "last_updated": "2024-01-01T12:00:00"
}
```

#### GET /api/repos
```javascript
{
  "repositories": [
    {
      "id": 123,
      "name": "project-name",
      "path_with_namespace": "group/project",
      "description": "...",
      "web_url": "https://...",
      "last_activity_at": "2024-01-01T12:00:00",
      "star_count": 5,
      "forks_count": 2,
      "open_issues_count": 3,
      "default_branch": "main",
      "last_pipeline_status": "success",
      "recent_success_rate": 0.85
    }
  ],
  "total": 10,
  "last_updated": "2024-01-01T12:00:00"
}
```

#### GET /api/pipelines
```javascript
{
  "pipelines": [
    {
      "id": 456,
      "project_id": 123,
      "project_name": "project-name",
      "project_path": "group/project",
      "status": "success",
      "ref": "main",
      "sha": "abc12345",
      "web_url": "https://...",
      "created_at": "2024-01-01T12:00:00",
      "updated_at": "2024-01-01T12:05:00",
      "duration": 300
    }
  ],
  "total": 50,
  "last_updated": "2024-01-01T12:00:00"
}
```

#### GET /api/health
```javascript
{
  "status": "healthy",
  "backend_status": "ONLINE",
  "timestamp": "2024-01-01T12:00:00",
  "last_poll": "2024-01-01T11:59:00"
}
```

**Do not break these contracts. The frontend must continue working with these response structures.**

## Security Requirements

### XSS Prevention
Always escape untrusted data before inserting into DOM:

```javascript
// ✅ GOOD: Use existing escapeHtml helper
function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

const projectName = escapeHtml(project.name);
card.innerHTML = `<h3>${projectName}</h3>`;

// ❌ BAD: Direct insertion of untrusted data
card.innerHTML = `<h3>${project.name}</h3>`;  // XSS risk!
```

### Safe DOM Manipulation
```javascript
// ✅ GOOD: Use textContent for plain text
element.textContent = userInput;

// ✅ GOOD: Use createElement for complex structures
const card = document.createElement('div');
card.className = 'card';
const title = document.createElement('h3');
title.textContent = project.name;  // Safe
card.appendChild(title);

// ⚠️ Use innerHTML only with escaped data
card.innerHTML = `<h3>${escapeHtml(project.name)}</h3>`;
```

## Accessibility Guidelines

### Semantic HTML
Use appropriate HTML5 elements:

```html
<!-- ✅ GOOD: Semantic structure -->
<main>
  <section aria-label="Summary Statistics">
    <h2>Dashboard Overview</h2>
    <article class="kpi-card">
      <h3>Total Repositories</h3>
      <p>42</p>
    </article>
  </section>
</main>

<!-- ❌ BAD: Generic divs everywhere -->
<div>
  <div>
    <div class="kpi-card">
      <div>Total Repositories</div>
      <div>42</div>
    </div>
  </div>
</div>
```

### ARIA Labels
Add labels for dynamic content and interactive elements:

```html
<button aria-label="Refresh dashboard data">
  🔄 Refresh
</button>

<div role="status" aria-live="polite">
  Last updated: <time id="last-update">2 minutes ago</time>
</div>

<table aria-label="Recent CI/CD pipelines">
  <!-- ... -->
</table>
```

### Keyboard Navigation
Ensure interactive elements are keyboard accessible:

```css
/* Add visible focus styles */
button:focus,
a:focus {
  outline: 2px solid var(--accent-blue);
  outline-offset: 2px;
}

/* Don't remove focus styles unless replacing with better alternative */
*:focus {
  outline: none;  /* ❌ BAD - removes accessibility */
}
```

## Code Style and Patterns

### Modern JavaScript (ES6+)
```javascript
// ✅ GOOD: Use const/let, arrow functions, template literals
const fetchData = async () => {
  const response = await fetch('/api/summary');
  const data = await response.json();
  return data;
};

// ✅ GOOD: Destructuring
const { total_repositories, active_repositories } = summary;

// ✅ GOOD: Array methods
const failedPipelines = pipelines.filter(p => p.status === 'failed');
const projectNames = projects.map(p => p.name);

// ❌ BAD: Old var syntax
var data = {};  // Use const or let

// ❌ BAD: String concatenation when template literals are cleaner
var html = '<div>' + name + '</div>';  // Use template literals
```

### Error Handling
```javascript
// ✅ GOOD: Handle fetch errors gracefully
async function loadData() {
  try {
    const response = await fetch('/api/summary');
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Failed to load data:', error);
    showErrorMessage('Unable to load dashboard data. Retrying...');
    return null;
  }
}

// ❌ BAD: Unhandled promise rejection
fetch('/api/summary')
  .then(r => r.json())
  .then(data => updateUI(data));  // No error handling!
```

### Function Organization
```javascript
// ✅ GOOD: Small, focused functions
function formatDuration(seconds) {
  if (!seconds) return 'N/A';
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ${seconds % 60}s`;
}

function createPipelineRow(pipeline) {
  const row = document.createElement('tr');
  row.innerHTML = `
    <td>${escapeHtml(pipeline.project_name)}</td>
    <td><span class="status-badge status-${pipeline.status}">${pipeline.status}</span></td>
    <td>${formatDuration(pipeline.duration)}</td>
  `;
  return row;
}

function renderPipelines(pipelines) {
  const tbody = document.querySelector('#pipeline-table tbody');
  tbody.innerHTML = '';
  pipelines.forEach(pipeline => {
    tbody.appendChild(createPipelineRow(pipeline));
  });
}

// ❌ BAD: One giant function doing everything
function updateEverything() {
  // 200 lines of mixed concerns...
}
```

### DOM Queries
```javascript
// ✅ GOOD: Cache selectors when used multiple times
const container = document.querySelector('#repos-container');
repos.forEach(repo => {
  container.appendChild(createRepoCard(repo));
});

// ⚠️ OK for one-time use
document.querySelector('#summary-stats').textContent = stats.total;

// ❌ BAD: Repeated queries in loop
repos.forEach(repo => {
  document.querySelector('#repos-container').appendChild(createRepoCard(repo));
});
```

## CSS Best Practices

### Use CSS Custom Properties
```css
/* ✅ GOOD: Use existing CSS variables */
.card {
  background: var(--bg-secondary);
  color: var(--text-primary);
  box-shadow: 
    8px 8px 16px var(--shadow-dark),
    -8px -8px 16px var(--shadow-light);
}

/* ❌ BAD: Hardcoded colors break theme consistency */
.card {
  background: #22252f;  /* Should use var(--bg-secondary) */
}
```

### Mobile Responsiveness
```css
/* ✅ GOOD: Mobile-first approach with breakpoints */
.grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1rem;
}

@media (min-width: 768px) {
  .grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (min-width: 1024px) {
  .grid {
    grid-template-columns: repeat(3, 1fr);
  }
}
```

### Performance
```css
/* ✅ GOOD: Use transform for animations (GPU accelerated) */
.card {
  transition: transform 0.3s ease;
}

.card:hover {
  transform: translateY(-4px);
}

/* ❌ AVOID: Animating expensive properties */
.card:hover {
  margin-top: -4px;  /* Triggers layout recalculation */
}
```

## Common UI Patterns

### Status Badges
```javascript
// Status color mapping
const statusColors = {
  success: 'var(--success)',
  failed: 'var(--error)',
  running: 'var(--running)',
  pending: 'var(--warning)'
};

function createStatusBadge(status) {
  return `<span class="status-badge status-${status}">${status}</span>`;
}
```

### Loading States
```javascript
// Show loading indicator while fetching
function showLoading() {
  const container = document.querySelector('#main-content');
  container.innerHTML = '<div class="loading">Loading dashboard data...</div>';
}

function hideLoading() {
  document.querySelector('.loading')?.remove();
}
```

### Time Formatting
```javascript
// Format ISO timestamps to relative time
function formatRelativeTime(isoString) {
  if (!isoString) return 'Never';
  
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);
  
  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins} minute${diffMins > 1 ? 's' : ''} ago`;
  
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
  
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
}
```

## Stable DOM IDs and Classes

### Don't Remove or Rename These IDs
The following IDs are used by JavaScript and must remain stable:

```html
<!-- Core containers -->
<div id="summary-stats"></div>
<div id="repos-container"></div>
<div id="pipelines-container"></div>
<table id="pipeline-table"></table>

<!-- Update indicators -->
<span id="last-update"></span>
<div id="health-indicator"></div>

<!-- TV mode elements -->
<div class="tv-mode"></div>
```

**Changing these IDs will break the JavaScript.**

## Testing Frontend Changes

### Manual Testing Checklist
1. ✅ Dashboard loads without console errors
2. ✅ Summary stats display correctly
3. ✅ Repository cards render with data
4. ✅ Pipeline table shows recent runs
5. ✅ Status badges have correct colors
6. ✅ Last update time refreshes
7. ✅ Auto-refresh works (wait 60 seconds)
8. ✅ TV mode works (`?tv=true`)
9. ✅ Mobile responsive (test at 375px, 768px, 1024px)
10. ✅ Dark theme preserved
11. ✅ Neomorphic shadows visible
12. ✅ No XSS vulnerabilities (test with `<script>alert('xss')</script>` in data)

### Browser Compatibility
Test in modern browsers (last 2 versions):
- Chrome/Edge
- Firefox
- Safari

Don't add polyfills for old browsers (IE11, etc.)

## What NOT to Do

### ❌ Don't Add Build Tools
```json
// ❌ BAD: No package.json
{
  "scripts": {
    "build": "webpack"
  }
}
```

### ❌ Don't Add Frameworks
```html
<!-- ❌ BAD: No framework CDN imports -->
<script src="https://unpkg.com/react@17/umd/react.production.min.js"></script>
<script src="https://unpkg.com/vue@3/dist/vue.global.js"></script>
<script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
```

### ❌ Don't Break the Theme
```css
/* ❌ BAD: Don't flatten the neomorphic design */
.card {
  box-shadow: none;  /* Removes neomorphic effect! */
  background: white;  /* Breaks dark theme! */
}

/* ❌ BAD: Don't change core colors without request */
:root {
  --bg-primary: #ffffff;  /* User chose dark theme! */
}
```

### ❌ Don't Break API Contracts
```javascript
// ❌ BAD: Assuming different response structure
const repos = data.projects;  // Backend returns 'repositories', not 'projects'!

// ✅ GOOD: Use the actual API contract
const repos = data.repositories;
```

## Questions Before Making Changes

1. Can this be done with vanilla JavaScript? (Usually yes!)
2. Does this preserve the neomorphic dark theme?
3. Does this maintain backward compatibility with existing DOM structure?
4. Does TV mode still work?
5. Is user input properly escaped (XSS prevention)?
6. Does auto-refresh continue working?
7. Is the code accessible (semantic HTML, ARIA labels)?
8. Will this work without a build step?
9. Are all interactive elements keyboard accessible?
10. Does this work on mobile devices?

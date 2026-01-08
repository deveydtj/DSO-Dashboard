# Job Performance Analytics API

This document describes the job performance analytics endpoints added to the DSO-Dashboard backend.

## Overview

The job performance analytics feature computes 7-day aggregate statistics (avg, p95, p99) for job durations across pipelines. Analytics are computed separately for:
- **Default-branch pipelines**: Pipelines on the repository's main/master branch
- **Merge-request pipelines**: Pipelines explicitly tagged as merge request events

## Configuration

### Enable Analytics

Job analytics only run when `project_ids` are configured in `config.json` or via environment variables:

```json
{
  "project_ids": [123, 456, 789],
  "job_analytics": {
    "window_days": 7,
    "max_pipelines_per_project": 100,
    "max_job_calls_per_refresh": 50
  },
  "job_analytics_refresh_interval_sec": 43200
}
```

### Configuration Options

| Setting | Default | Description |
|---------|---------|-------------|
| `window_days` | 7 | Number of days to look back for analytics |
| `max_pipelines_per_project` | 100 | Maximum pipelines to inspect per project |
| `max_job_calls_per_refresh` | 50 | Maximum job API calls per refresh cycle |
| `job_analytics_refresh_interval_sec` | 43200 | Refresh interval (12 hours = twice per day) |

## API Endpoints

### GET /api/job-analytics/{project_id}

Fetch cached job performance analytics for a specific project.

**Parameters:**
- `project_id` (path): GitLab project ID

**Response (200 OK):**
```json
{
  "project_id": 123,
  "window_days": 7,
  "computed_at": "2024-01-08T15:30:00Z",
  "staleness_seconds": 3600,
  "error": null,
  "data": [
    {
      "pipeline_id": 1001,
      "pipeline_ref": "main",
      "pipeline_status": "success",
      "created_at": "2024-01-08T10:00:00Z",
      "is_default_branch": true,
      "is_merge_request": false,
      "avg_duration": 245.5,
      "p95_duration": 350.2,
      "p99_duration": 398.7,
      "job_count": 12
    },
    {
      "pipeline_id": 1002,
      "pipeline_ref": "feature/new-widget",
      "pipeline_status": "success",
      "created_at": "2024-01-08T09:30:00Z",
      "is_default_branch": false,
      "is_merge_request": true,
      "avg_duration": 180.3,
      "p95_duration": 250.1,
      "p99_duration": 275.8,
      "job_count": 8
    }
  ]
}
```

**Response (404 Not Found):**
```json
{
  "error": "Analytics not available for this project",
  "message": "Analytics may not have been computed yet. Try triggering a refresh."
}
```

**Field Descriptions:**

- `project_id`: GitLab project ID
- `window_days`: Number of days of historical data included
- `computed_at`: ISO 8601 timestamp when analytics were computed
- `staleness_seconds`: Seconds since last computation (freshness indicator)
- `error`: Error message if computation failed, null otherwise
- `data`: Array of per-pipeline analytics items

Per-pipeline fields:
- `pipeline_id`: GitLab pipeline ID
- `pipeline_ref`: Branch/tag name
- `pipeline_status`: Pipeline status (success, failed, etc.)
- `created_at`: Pipeline creation timestamp
- `is_default_branch`: True if pipeline is on default branch
- `is_merge_request`: True if pipeline is for a merge request
- `avg_duration`: Average job duration in seconds (null if insufficient data)
- `p95_duration`: 95th percentile job duration in seconds (null if insufficient data)
- `p99_duration`: 99th percentile job duration in seconds (null if insufficient data)
- `job_count`: Number of valid jobs included in calculations

### POST /api/job-analytics/{project_id}/refresh

Trigger a manual refresh of analytics for a specific project.

**Parameters:**
- `project_id` (path): GitLab project ID

**Response (200 OK):**
```json
{
  "message": "Analytics refresh completed",
  "analytics": {
    "project_id": 123,
    "window_days": 7,
    "computed_at": "2024-01-08T15:35:00Z",
    "staleness_seconds": 0,
    "error": null,
    "data": [...]
  }
}
```

**Response (409 Conflict):**
```json
{
  "message": "Refresh already in progress or failed",
  "status": "in_progress_or_failed"
}
```

**Response (503 Service Unavailable):**
```json
{
  "error": "Analytics poller not available",
  "message": "Job analytics feature may not be enabled"
}
```

## Job Filtering Rules

Analytics computation excludes the following jobs:
- Jobs with status `manual` (user-triggered, not automatic)
- Jobs with status `skipped` (didn't execute)
- Jobs with `duration` field missing or zero

Only jobs with valid duration data are included in statistics.

## Merge Request Pipeline Identification

Pipelines are identified as merge request pipelines when their `source` field equals `merge_request_event`. This is GitLab's standard marker for MR pipelines.

Regular push pipelines, API-triggered pipelines, and scheduled pipelines are NOT considered merge request pipelines.

## Percentile Calculation

Percentiles (p95, p99) use linear interpolation between closest ranks:
- Requires minimum 2 data points for meaningful calculation
- Returns `null` if insufficient data
- Values are sorted before calculation

Average is computed as simple arithmetic mean.

## Rate Limiting & Protection

### Automatic Refresh
- Runs on a slow cadence (default: twice per day)
- Respects configured caps to protect GitLab API
- Only processes projects in `project_ids` configuration

### Manual Refresh
- **Single-flight protection**: Only one refresh per project at a time
- Returns 409 Conflict if refresh already in progress
- Useful for on-demand updates or debugging

### API Call Caps
- `max_pipelines_per_project`: Limits pipelines fetched per project
- `max_job_calls_per_refresh`: Limits total job API calls per refresh
- Time window filter reduces unnecessary API calls

## Example Usage

### Fetch Analytics with curl

```bash
# Get analytics for project 123
curl http://localhost:8080/api/job-analytics/123 | jq

# Trigger manual refresh
curl -X POST http://localhost:8080/api/job-analytics/123/refresh | jq
```

### Python Example

```python
import requests

# Fetch analytics
response = requests.get('http://localhost:8080/api/job-analytics/123')
if response.status_code == 200:
    analytics = response.json()
    print(f"Project: {analytics['project_id']}")
    print(f"Data points: {len(analytics['data'])}")
    
    # Find default-branch pipelines
    default_branch_pipelines = [
        item for item in analytics['data'] 
        if item['is_default_branch']
    ]
    print(f"Default-branch pipelines: {len(default_branch_pipelines)}")

# Trigger refresh
response = requests.post('http://localhost:8080/api/job-analytics/123/refresh')
if response.status_code == 200:
    print("Refresh successful")
elif response.status_code == 409:
    print("Refresh already in progress")
```

## Troubleshooting

### Analytics not available (404)
- Ensure `project_ids` includes the target project
- Wait for automatic refresh or trigger manual refresh
- Check server logs for computation errors

### Analytics poller not available (503)
- Verify `project_ids` is configured (not empty)
- Ensure server is running in non-mock mode
- Check server logs for startup errors

### Refresh returns 409 (Conflict)
- Another refresh is already running for this project
- Wait for current refresh to complete
- Single-flight protection prevents concurrent refreshes

### Empty data array
- No pipelines found in 7-day window
- All pipelines filtered out (no valid jobs)
- Check GitLab API connectivity and project accessibility

## Backend Implementation Notes

- **Thread-safe**: All state access protected by `STATE_LOCK`
- **Atomic updates**: Analytics updates are atomic per project
- **Staleness tracking**: Tracks time since last computation
- **Error preservation**: Computation errors stored with analytics
- **Memory efficient**: Only stores aggregate statistics, not raw job data

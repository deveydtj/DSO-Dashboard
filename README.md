# GitLab DSO Dashboard

A production-ready, dark neomorphic dashboard for monitoring GitLab repositories and CI/CD pipelines. Built with Python 3.10 standard library only (no external dependencies) and vanilla JavaScript.

## ✨ Features

- **Real-time Monitoring**: Background poller continuously updates data from GitLab API
- **Production-Ready**: Thread-safe architecture with retry logic and rate limiting
- **Flexible Configuration**: Load config from JSON file or environment variables
- **Pagination Support**: Handles large groups (>100 projects) efficiently
- **SSL Support**: Works with internal CAs and self-signed certificates
- **Retry & Rate Limiting**: Automatic retry with exponential backoff and 429 handling
- **Dark Neomorphic UI**: Modern, eye-friendly dark theme with neomorphic design
- **KPI Dashboard**: View key metrics at a glance
  - Total repositories
  - Successful/failed/running pipelines
  - Repository statistics
- **Repository Cards**: Browse your GitLab repositories with stats
- **Pipeline Table**: Monitor recent pipeline runs across projects
- **Auto-refresh**: Frontend updates automatically every 60 seconds

## 🏗️ Architecture

### Backend (Python 3.10 stdlib-only)
- `http.server`: HTTP server for serving API and static files
- `urllib`: GitLab API client with retry and pagination (no requests library needed)
- Thread-safe global STATE with background poller
- Automatic retry with exponential backoff for transient errors
- Rate limiting support (429 responses with Retry-After)
- Full pagination support for large datasets
- RESTful JSON API endpoints

### Frontend (Vanilla HTML/CSS/JS)
- Pure JavaScript (no frameworks)
- Dark neomorphic CSS design
- Responsive layout
- Auto-polling for updates

## 📁 Project Structure

```
DSO-Dashboard/
├── server.py              # Backend server (Python 3.10 stdlib only)
├── config.json.example    # Configuration file template
├── frontend/              # Static frontend files
│   ├── index.html        # Main HTML page
│   ├── styles.css        # Dark neomorphic styles
│   └── app.js            # Frontend JavaScript
├── .env.example          # Environment configuration template
├── .gitignore           # Git ignore rules
└── README.md            # This file
```

## 🚀 Quick Start

### Prerequisites

- Python 3.10 or higher
- GitLab account with API access
- GitLab Personal Access Token (with `read_api` scope)

### Installation & Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/deveydtj/DSO-Dashboard.git
   cd DSO-Dashboard
   ```

2. **Configure the application**
   
   You have two options for configuration:
   
   **Option A: Using config.json (Recommended for production)**
   ```bash
   # Copy the example config file
   cp config.json.example config.json
   
   # Edit config.json with your settings
   nano config.json
   ```
   
   Example `config.json`:
   ```json
   {
     "gitlab_url": "https://gitlab.example.com",
     "api_token": "your_gitlab_api_token_here",
     "group_ids": ["group1", "group2"],
     "project_ids": [],
     "poll_interval_sec": 60,
     "cache_ttl_sec": 300,
     "per_page": 100,
     "insecure_skip_verify": false
   }
   ```
   
   **Option B: Using environment variables**
   ```bash
   export GITLAB_URL="https://gitlab.com"
   export GITLAB_API_TOKEN="your_token_here"
   export GITLAB_GROUP_IDS="group1,group2"
   export PORT="8080"
   export POLL_INTERVAL="60"
   export CACHE_TTL="300"
   export PER_PAGE="100"
   ```
   
   **Note**: If both config.json and environment variables are present, environment variables take precedence.

3. **Run the server**
   ```bash
   python3 server.py
   ```

4. **Access the dashboard**
   
   Open your browser and navigate to:
   ```
   http://localhost:8080
   ```

### Configuration Options

Configure the application using `config.json` or environment variables:

| JSON Field / Environment Variable | Description | Default |
|----------------------------------|-------------|---------|
| `gitlab_url` / `GITLAB_URL` | GitLab instance URL | `https://gitlab.com` |
| `api_token` / `GITLAB_API_TOKEN` | GitLab API token (required) | - |
| `group_ids` / `GITLAB_GROUP_IDS` | Comma-separated list of group IDs to monitor | All accessible projects |
| `project_ids` / `GITLAB_PROJECT_IDS` | Comma-separated list of specific project IDs | - |
| `poll_interval_sec` / `POLL_INTERVAL` | Background poll interval in seconds | `60` |
| `cache_ttl_sec` / `CACHE_TTL` | Cache TTL in seconds (deprecated, kept for compatibility) | `300` |
| `per_page` / `PER_PAGE` | Items per page for pagination | `100` |
| `insecure_skip_verify` / `INSECURE_SKIP_VERIFY` | Skip SSL verification for self-signed certs | `false` |
| - / `PORT` | Server port | `8080` |

### Creating a GitLab API Token

1. Go to GitLab → Settings → Access Tokens
2. Create a new token with `read_api` scope
3. Copy the token and add it to your `config.json` or set it as `GITLAB_API_TOKEN`

### Production Deployment Tips

1. **Internal CA / Self-Signed Certificates**
   - Set `insecure_skip_verify: true` in config.json or `INSECURE_SKIP_VERIFY=true`
   - Only use this for trusted internal networks

2. **Large Groups**
   - The dashboard automatically paginates through all projects
   - Set `per_page` to a higher value (e.g., 100) for better performance
   - Monitor logs to see pagination progress

3. **Rate Limiting**
   - The backend automatically handles 429 responses
   - Implements exponential backoff with Retry-After header support
   - Retries transient errors (5xx, timeouts) up to 3 times

4. **Background Polling**
   - All data is fetched by a background thread
   - API endpoints return immediately from in-memory STATE
   - `/api/health` returns ONLINE even while polling
   - Adjust `poll_interval_sec` based on your needs (default: 60s)

5. **Thread Safety**
   - Global STATE is protected by threading.Lock
   - Safe for concurrent requests
   - No race conditions or blocking issues

## 📡 API Endpoints

The backend provides these JSON API endpoints:

### GET /api/summary
Returns overall statistics:
```json
{
  "total_repositories": 10,
  "active_repositories": 8,
  "total_pipelines": 50,
  "successful_pipelines": 45,
  "failed_pipelines": 3,
  "running_pipelines": 2,
  "last_updated": "2024-01-01T12:00:00"
}
```

### GET /api/repos
Returns list of repositories:
```json
{
  "repositories": [
    {
      "id": 123,
      "name": "my-project",
      "description": "Project description",
      "web_url": "https://gitlab.com/user/project",
      "star_count": 5,
      "forks_count": 2,
      "open_issues_count": 3
    }
  ],
  "total": 10,
  "last_updated": "2024-01-01T12:00:00"
}
```

### GET /api/pipelines
Returns recent pipelines:
```json
{
  "pipelines": [
    {
      "id": 456,
      "project_name": "my-project",
      "status": "success",
      "ref": "main",
      "sha": "abc12345",
      "web_url": "https://gitlab.com/...",
      "created_at": "2024-01-01T12:00:00",
      "duration": 120
    }
  ],
  "total": 30,
  "last_updated": "2024-01-01T12:00:00"
}
```

### GET /api/health
Health check endpoint:
```json
{
  "status": "healthy",
  "backend_status": "ONLINE",
  "timestamp": "2024-01-01T12:00:00",
  "last_poll": "2024-01-01T11:59:00"
}
```

**Status values:**
- `INITIALIZING`: Backend is starting up and polling data for the first time
- `ONLINE`: Backend is healthy and data is being polled regularly
- `ERROR`: Backend encountered errors during polling

**Note:** The health endpoint returns 200 OK even during `INITIALIZING` state, allowing the dashboard to remain responsive while data loads.

## 🎨 UI Features

### Dark Neomorphic Design
- Modern dark theme with soft shadows
- Smooth animations and transitions
- Responsive layout for mobile and desktop
- Color-coded pipeline statuses

### KPI Cards
- Visual metrics display
- Icon-based indicators
- Real-time updates

### Repository Cards
- Repository information at a glance
- Statistics (stars, forks, issues)
- Direct links to GitLab

### Pipeline Table
- Recent pipeline runs
- Status indicators (success, failed, running)
- Duration and timestamp information
- Quick links to pipeline details

## 🔧 Development

### Running in Development Mode

```bash
# Set environment variables
export GITLAB_URL="https://gitlab.com"
export GITLAB_API_TOKEN="your_token"
export PORT=8080

# Run server
python3 server.py
```

### Testing

Test individual API endpoints:
```bash
# Test health endpoint
curl http://localhost:8080/api/health

# Test summary
curl http://localhost:8080/api/summary

# Test repositories
curl http://localhost:8080/api/repos

# Test pipelines
curl http://localhost:8080/api/pipelines
```

## 🛡️ Security Notes

- Never commit your `.env` file with real credentials
- Use environment variables for sensitive data
- The API token should have minimal required permissions (`read_api`)
- Run behind a reverse proxy (nginx, Apache) for production
- Consider adding authentication for production deployments

## 🐛 Troubleshooting

### Server won't start
- Check Python version: `python3 --version` (must be 3.10+)
- Verify port is not in use: `lsof -i :8080`
- Check environment variables are set

### No data showing
- Verify `GITLAB_API_TOKEN` is set correctly
- Check token has `read_api` permission
- Look at server logs for API errors
- Test API manually: `curl -H "PRIVATE-TOKEN: your_token" https://gitlab.com/api/v4/projects`

### Connection errors
- Check `GITLAB_URL` is correct
- Verify network connectivity to GitLab
- Check firewall settings

## 📝 License

This project is open source and available for use.

## 🤝 Contributing

Contributions are welcome! Feel free to submit issues and pull requests.

## 📧 Support

For issues and questions, please use the GitHub issue tracker.

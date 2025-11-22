# GitLab DSO Dashboard

A modern, dark neomorphic dashboard for monitoring GitLab repositories and CI/CD pipelines. Built with Python 3.10 standard library only (no external dependencies) and vanilla JavaScript.

## ✨ Features

- **Real-time Monitoring**: Polls GitLab API and displays live data
- **Dark Neomorphic UI**: Modern, eye-friendly dark theme with neomorphic design
- **KPI Dashboard**: View key metrics at a glance
  - Total repositories
  - Successful/failed/running pipelines
  - Repository statistics
- **Repository Cards**: Browse your GitLab repositories with stats
- **Pipeline Table**: Monitor recent pipeline runs across projects
- **Auto-refresh**: Data updates automatically every 60 seconds
- **Caching**: Built-in caching to reduce API calls

## 🏗️ Architecture

### Backend (Python 3.10 stdlib-only)
- `http.server`: HTTP server for serving API and static files
- `urllib`: GitLab API client (no requests library needed)
- Built-in caching with TTL
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

2. **Configure environment variables**
   
   The server reads configuration from environment variables. You have two options:
   
   **Option A: Export variables in your shell (recommended for development)**
   ```bash
   export GITLAB_URL="https://gitlab.com"
   export GITLAB_API_TOKEN="your_token_here"
   export PORT="8080"
   export CACHE_TTL="300"
   ```
   
   **Option B: Use a shell script**
   ```bash
   # Create a run script
   cat > run.sh << 'EOF'
   #!/bin/bash
   export GITLAB_URL="https://gitlab.com"
   export GITLAB_API_TOKEN="your_token_here"
   export PORT="8080"
   export CACHE_TTL="300"
   python3 server.py
   EOF
   
   chmod +x run.sh
   ./run.sh
   ```
   
   **Note**: The `.env.example` file is provided as a reference for required variables,
   but the server does not automatically load `.env` files (keeping it stdlib-only).
   You must export the variables before running the server.

3. **Run the server**
   ```bash
   python3 server.py
   ```

4. **Access the dashboard**
   
   Open your browser and navigate to:
   ```
   http://localhost:8080
   ```

### Environment Variables

Configure the application using these environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `GITLAB_URL` | GitLab instance URL | `https://gitlab.com` |
| `GITLAB_API_TOKEN` | GitLab API token (required) | - |
| `PORT` | Server port | `8080` |
| `CACHE_TTL` | Cache TTL in seconds | `300` |

### Creating a GitLab API Token

1. Go to GitLab → Settings → Access Tokens
2. Create a new token with `read_api` scope
3. Copy the token and set it in your `.env` file

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
  "timestamp": "2024-01-01T12:00:00",
  "cache_entries": 3
}
```

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

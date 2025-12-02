# DSO Dashboard

A zero-dependency dashboard for monitoring GitLab repositories and CI/CD pipelines. Built with **Python standard library only** and **vanilla JavaScript**.

## Quick Start

### Prerequisites
- Python 3.10+
- GitLab Personal Access Token with `read_api` scope

### Installation

```bash
# Clone and configure
git clone https://github.com/deveydtj/DSO-Dashboard.git
cd DSO-Dashboard

# Option A: config.json
cp config.json.example config.json
# Edit config.json with your GitLab URL and API token

# Option B: Environment variables
export GITLAB_URL="https://gitlab.com"
export GITLAB_API_TOKEN="your_token_here"

# Run
python3 backend/app.py
```

Open **http://localhost:8080** in your browser.

## Features

- **Zero Dependencies**: Pure Python stdlib backend + vanilla JS frontend
- **Real-time Updates**: Background polling with auto-refresh UI
- **TV/Kiosk Mode**: Full-screen display mode (`?tv=true`)
- **Dark Neomorphic Theme**: Modern UI with soft shadows
- **External Services**: Monitor additional health endpoints

## Configuration

Environment variables override `config.json` values.

| Setting | Environment Variable | Default |
|---------|---------------------|---------|
| GitLab URL | `GITLAB_URL` | `https://gitlab.com` |
| API Token | `GITLAB_API_TOKEN` | (required) |
| Group IDs | `GITLAB_GROUP_IDS` | All accessible |
| Project IDs | `GITLAB_PROJECT_IDS` | - |
| Poll Interval | `POLL_INTERVAL` | `60` seconds |
| Port | `PORT` | `8080` |
| Mock Mode | `USE_MOCK_DATA` | `false` |
| Mock Scenario | `MOCK_SCENARIO` | - |

### SSL/TLS for Internal GitLab

```json
{
  "ca_bundle_path": "/etc/ssl/certs/corporate-ca-bundle.crt"
}
```

Or as last resort: `"insecure_skip_verify": true`

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | Health check |
| `GET /api/summary` | Dashboard statistics |
| `GET /api/repos` | Repository list with pipeline health |
| `GET /api/pipelines` | Recent pipeline runs |
| `GET /api/services` | External service health |

## Development

### Key Constraints
- ⚠️ **Backend**: Python stdlib only (no pip dependencies)
- ⚠️ **Frontend**: Vanilla JS only (no frameworks)
- ⚠️ **Theme**: Preserve dark neomorphic UI

### Running Tests

```bash
python -m py_compile backend/app.py
python -m unittest discover -s tests -p "test_*.py" -v
```

### Project Structure

```
DSO-Dashboard/
├── backend/app.py        # Server application
├── frontend/             # Static UI files
├── data/mock_scenarios/  # Mock data for testing
├── tests/                # Test suite
└── docs/                 # Documentation
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Token not set | Set `GITLAB_API_TOKEN` env var or in `config.json` |
| SSL errors | Use `ca_bundle_path` for corporate CAs |
| Port in use | Set `PORT=8081` environment variable |
| No data | Verify token has `read_api` scope |

## Documentation

- [Architecture Overview](docs/architecture-overview.md)
- [Agent Instructions](AGENTS.md)
- [Copilot Instructions](.github/copilot-instructions.md)

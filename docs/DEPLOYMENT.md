# Astra Agent: Deployment & Operations Guide

## 1. Quick Local Setup

### Prerequisites
- Python 3.11+
- Git

### Installation Steps
```bash
# 1. Clone repository
git clone https://github.com/your-org/astra-agent.git
cd astra-agent

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies in editable mode
pip install -e ".[dev]"

# 4. Copy environment configuration
cp .env.example .env

# 5. Run tests to confirm environment integrity
pytest
```

---

## 2. Docker & Compose Deployment

Astra Agent provides hardened multi-stage Docker packaging.

### Build and Run with Docker
```bash
# Build Docker image
docker build -t astra-agent:latest .

# Run container with mounted workspace
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/workspace:/app/workspace \
  -v $(pwd)/data:/app/data \
  --name astra-agent \
  astra-agent:latest
```

### Run Full Stack with Docker Compose
```bash
docker compose up -d
```
This launches Astra Agent API along with a persistent PostgreSQL database instance.

---

## 3. Configuration Reference

All settings can be configured via environment variables with prefix `ASTRA_`:

| Environment Variable | Default | Description |
|---|---|---|
| `ASTRA_APP_NAME` | `Astra Agent` | Service name |
| `ASTRA_ENVIRONMENT` | `development` | `development`, `staging`, `production` |
| `ASTRA_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `ASTRA_DATABASE_URL` | `sqlite+aiosqlite:///astra_agent.db` | SQLAlchemy connection string |
| `ASTRA_WORKSPACE_DIR` | `./workspace` | Base directory for execution jail |
| `ASTRA_ENFORCE_WORKSPACE_JAIL` | `true` | Restrict all filesystem access to workspace |
| `ASTRA_PROVIDER` | `mock` | `mock`, `deterministic`, `openai`, `anthropic`, `gemini`, `ollama` |
| `ASTRA_MODEL_NAME` | `gpt-4o` | Model name for provider |
| `ASTRA_OPENAI_API_KEY` | None | OpenAI API Secret |
| `ASTRA_ANTHROPIC_API_KEY` | None | Anthropic API Secret |
| `ASTRA_GEMINI_API_KEY` | None | Google Gemini API Secret |
| `ASTRA_OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama local endpoint |
| `ASTRA_API_HOST` | `0.0.0.0` | API bind host |
| `ASTRA_API_PORT` | `8000` | API bind port |
| `ASTRA_API_AUTH_TOKEN` | None | Optional Bearer token for API protection |

---

## 4. Production Hardening Checklist

1. **Enable Authentication:** Set `ASTRA_API_AUTH_TOKEN` to a cryptographically secure random token (e.g. `openssl rand -hex 32`).
2. **Switch to PostgreSQL:** Use `postgresql+asyncpg://...` in production for high-concurrency connection pooling.
3. **Container Sandboxing:** Drop privileges (`cap-drop ALL`, `no-new-privileges`) in container runtime configurations.
4. **Volume Mounts:** Mount `workspace_dir` on a fast SSD with explicit storage quotas.
5. **Reverse Proxy:** Terminate TLS using Nginx or Caddy with rate limiting on `/api/v1/tasks`.

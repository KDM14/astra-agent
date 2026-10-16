# Contributing to Astra Agent

Thank you for your interest in contributing to Astra Agent! We welcome contributions across all areas: new typed tools, verifiers, provider integrations, security hardening, and documentation.

## Development Setup

1. Fork and clone the repository:
   ```bash
   git clone https://github.com/your-org/astra-agent.git
   cd astra-agent
   ```

2. Create a virtual environment and install development dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   ```

3. Run the automated test suite:
   ```bash
   pytest tests -v
   ```

4. Run the benchmark evaluation suite:
   ```bash
   python scripts/run_eval.py --suite all --provider deterministic
   ```

## Contribution Guidelines

- **Code Standards:** Use Python 3.11+ type annotations and Pydantic v2 schemas.
- **Evidence-Based Contract:** Any new agent feature or tool must include unit tests and independent verification checks.
- **Security:** Do not bypass workspace containment or execute arbitrary shell commands directly on the host. Always use `PathValidator` and `SubprocessSandbox`.
- **Formatting & Linting:** Run `ruff check src tests` and `ruff format src tests` prior to submitting pull requests.
- **No Hardcoded Secrets:** Never commit real API keys, bearer tokens, or local credentials.

## Pull Request Process

1. Create a feature branch: `git checkout -b feat/your-feature-name`.
2. Commit small, reviewable changes with descriptive commit messages.
3. Ensure all automated tests pass (`pytest`).
4. Submit a Pull Request targeting the `main` branch.

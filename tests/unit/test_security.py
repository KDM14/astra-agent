"""Unit tests for security boundaries and controls."""

import pytest
from pathlib import Path

from astra_agent.core.state import PathSecurityViolationError, SecurityViolationError
from astra_agent.security.path_validator import PathValidator
from astra_agent.security.secret_redactor import SecretRedactor
from astra_agent.security.sandbox import SubprocessSandbox


def test_path_validator_safe(tmp_path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    file_path = ws / "sub" / "data.txt"
    file_path.parent.mkdir()
    file_path.write_text("ok", encoding="utf-8")

    # Safe relative path
    safe = PathValidator.resolve_safe_path(ws, "sub/data.txt")
    assert safe == file_path.resolve()

    # Safe child path
    safe2 = PathValidator.resolve_safe_path(ws, "output.json")
    assert safe2 == (ws / "output.json").resolve()


def test_path_validator_traversal_blocked(tmp_path):
    ws = tmp_path / "workspace"
    ws.mkdir()

    # Relative path escaping workspace
    with pytest.raises(PathSecurityViolationError):
        PathValidator.resolve_safe_path(ws, "../secret.txt")

    # Multiple dots escaping
    with pytest.raises(PathSecurityViolationError):
        PathValidator.resolve_safe_path(ws, "sub/../../etc/passwd")

    # Absolute path outside workspace
    with pytest.raises(PathSecurityViolationError):
        PathValidator.resolve_safe_path(ws, "/etc/passwd")


def test_secret_redactor_text():
    # OpenAI key
    text_openai = "Connecting with key sk-abcdef1234567890abcdef1234567890 to backend"
    assert "[REDACTED_SECRET]" in SecretRedactor.redact_text(text_openai)

    # AWS Key
    text_aws = "Deploying to AWS using AKIAIOSFODNN7EXAMPLE credentials"
    assert "[REDACTED_SECRET]" in SecretRedactor.redact_text(text_aws)

    # GitHub token
    text_gh = "GitHub auth token: ghp_123456789012345678901234567890123456"
    assert "[REDACTED_SECRET]" in SecretRedactor.redact_text(text_gh)


def test_secret_redactor_nested_dict():
    payload = {
        "user": "developer",
        "api_key": "super_secret_value_12345",
        "nested": {
            "auth_token": "bearer_secret_xyz",
            "normal_field": "public_data",
        },
        "list_items": [
            {"password": "hidden_password"},
            "clean_string",
        ]
    }
    redacted = SecretRedactor.redact_data(payload)
    assert redacted["api_key"] == "[REDACTED_SECRET]"
    assert redacted["nested"]["auth_token"] == "[REDACTED_SECRET]"
    assert redacted["nested"]["normal_field"] == "public_data"
    assert redacted["list_items"][0]["password"] == "[REDACTED_SECRET]"


def test_subprocess_sandbox_whitelist(tmp_path):
    ws = tmp_path
    sandbox = SubprocessSandbox(workspace_dir=ws, allowed_executables=["python3", "echo"])

    # Allowed executable
    res = sandbox.run(["echo", "hello sandbox"])
    assert res.exit_code == 0
    assert "hello sandbox" in res.stdout

    # Disallowed executable (e.g. bash or rm or curl)
    with pytest.raises(SecurityViolationError):
        sandbox.run(["curl", "http://evil.com"])

    with pytest.raises(SecurityViolationError):
        sandbox.run(["bash", "-c", "whoami"])


def test_subprocess_sandbox_timeout(tmp_path):
    ws = tmp_path
    sandbox = SubprocessSandbox(workspace_dir=ws, allowed_executables=["python3"], default_timeout=1.0)

    # Sleep longer than timeout
    res = sandbox.run(["python3", "-c", "import time; time.sleep(5)"], timeout=0.5)
    assert res.timed_out is True
    assert "timed out" in res.stderr.lower()

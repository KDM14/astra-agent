"""Security penetration tests targeting sandbox, path containment, and secret redaction."""

import pytest
from pathlib import Path

from astra_agent.core.state import PathSecurityViolationError, SecurityViolationError
from astra_agent.security.path_validator import PathValidator
from astra_agent.security.secret_redactor import SecretRedactor
from astra_agent.tools.file_reader import FileReaderTool
from astra_agent.tools.file_writer import FileWriterTool


def test_pen_test_path_traversal_attacks(tmp_path):
    ws = str(tmp_path)
    reader = FileReaderTool(workspace_dir=ws)
    writer = FileWriterTool(workspace_dir=ws)

    malicious_paths = [
        "../../etc/passwd",
        "../../../etc/shadow",
        "sub/../../../../../../private/etc/hosts",
        "/etc/passwd",
        "test/../../..",
    ]

    for p in malicious_paths:
        # Direct path validator raises PathSecurityViolationError
        with pytest.raises(PathSecurityViolationError):
            PathValidator.resolve_safe_path(ws, p)

        # Tool execution safely intercepts and reports error without crashing
        res_read = reader.run({"path": p})
        assert res_read.success is False
        assert "PathSecurityViolationError" in res_read.error or "traversal" in res_read.error.lower()

        res_write = writer.run({"path": p, "content": "malicious injection"})
        assert res_write.success is False
        assert "PathSecurityViolationError" in res_write.error or "traversal" in res_write.error.lower()


def test_pen_test_command_injection(tmp_path):
    ws = str(tmp_path)
    from astra_agent.security.sandbox import SubprocessSandbox

    sandbox = SubprocessSandbox(workspace_dir=ws, allowed_executables=["python3"])

    # Attempting shell chaining operators
    with pytest.raises(SecurityViolationError):
        sandbox.run(["python3; rm -rf /"])

    with pytest.raises(SecurityViolationError):
        sandbox.run(["bash", "-c", "echo pwned"])


def test_pen_test_secret_leakage():
    fake_tokens = [
        "sk-proj-1234567890abcdef1234567890abcdef1234567890",
        "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890",
        "AKIAIOSFODNN7EXAMPLE",
    ]

    for token in fake_tokens:
        redacted = SecretRedactor.redact_text(f"API token is: {token}")
        assert token not in redacted
        assert "[REDACTED_SECRET]" in redacted

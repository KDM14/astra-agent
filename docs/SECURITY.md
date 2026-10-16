# Astra Agent: Security Architecture & Policy

## 1. Threat Model & Security Principles

Astra Agent operates in environments where language model outputs, external web data, and user-supplied scripts can be adversarial or malformed. To prevent compromise of the host system, data exfiltration, or unintended destructive actions, Astra Agent applies the **Principle of Least Privilege** and assumes **Zero Trust** for model outputs and external inputs.

### 1.1 Threat Vectors Addressed
1. **Arbitrary Code / Shell Injection:** Language model attempting to execute malicious shell commands (e.g. `rm -rf /`, `curl | bash`, reverse shells).
2. **Directory Traversal / Arbitrary File Access:** Path manipulation (e.g. `../../../etc/shadow`, symlink attacks) to access files outside the designated workspace.
3. **Indirect Prompt Injection:** Malicious instructions hidden within retrieved files, web pages, or repository content designed to hijack the agent's intent.
4. **Credential & Secret Exposure:** Accidentally writing API keys, tokens, or environment passwords into task outputs, logs, or persistent databases.
5. **Denial of Service / Resource Exhaustion:** Runaway loops, infinite recursions, fork bombs, or excessive memory allocation consuming host resources.
6. **Unauthorized Sensitive Side-Effects:** Unapproved file deletions, external network requests, or repository pushes.

---

## 2. Security Boundaries & Controls

### 2.1 Workspace Filesystem Isolation (Chroot / Path Jail)
Every file operation (read, write, search, python execution) is strictly bound to a designated `workspace_dir`.
- **Path Resolution:** Every user- or model-provided path is evaluated through `PathValidator.resolve_safe_path(workspace_dir, candidate_path)`.
- **Canonicalization:** Paths are resolved via `os.path.realpath` to dereference symbolic links before boundary verification.
- **Traversal Defense:** If `resolved_path` does not start with `workspace_real_path`, execution is aborted immediately with `PathSecurityViolationError` and an audit alert is triggered.

### 2.2 Subprocess Sandboxing & Execution Constraints
When running approved Python scripts or test suites:
- **No Direct Shell Execution:** Subprocesses are invoked via explicit executable parameter lists (`argv`), avoiding `shell=True` to prevent shell injection.
- **Working Directory Locking:** The subprocess execution directory is locked to `workspace_dir`.
- **Environment Sanitization:** Host environment variables are purged. Sensitive tokens (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `AWS_SECRET_ACCESS_KEY`, etc.) are stripped from the child process environment.
- **Resource Limits & Timeouts:** Hard timeouts (default 30 seconds) kill non-responsive or hanging child processes using `SIGKILL` if `SIGTERM` is unacknowledged within 2 seconds.
- **Output Truncation:** stdout and stderr streams are capped (e.g., 50 KB max) to prevent memory exhaustion from verbose output loops.

### 2.3 Secret Redaction Subsystem
The `SecretRedactor` automatically intercepts all inputs, outputs, memory writes, and structured log events.
- Employs regex patterns for high-entropy tokens, AWS keys, GitHub tokens, Bearer authorization headers, private keys, and standard API key prefixes (`sk-`, `ghp_`, `xoxb-`, etc.).
- Replaces matches with `[REDACTED_SECRET]` before persistence or logging.
- Disallows storing plaintext secrets in working or long-term memory.

### 2.4 Action Classification & Human Approval Gates
Every tool declares a `PermissionLevel`:
- `READ_ONLY`: Safe for autonomous execution (e.g., reading files in workspace, math calculation, state inspection).
- `WORKSPACE_WRITE`: Modifying files strictly within the workspace directory.
- `SUBPROCESS_EXEC`: Running sandboxed workspace commands or tests.
- `SENSITIVE`: Requires explicit human confirmation via `/api/v1/tasks/{id}/approve` before execution proceeds.

#### Mandatory Approval Triggers:
- Deletion of files or directories.
- Any network request directed outside localhost.
- Code execution with external dependencies.
- Modifying security configurations or permissions.
- Git push or deployment operations.

### 2.5 Prompt Injection Resistance & Untrusted Content Handling
All content retrieved from files, browser sessions, or external search is treated as untrusted:
- Encapsulated within explicit data markers (`<UNTRUSTED_CONTENT>...</UNTRUSTED_CONTENT>`) in LLM prompts.
- Instructions found within untrusted content cannot elevate tool permissions, modify the state machine, or bypass human approval gates.

---

## 3. Sandboxing Isolation Levels & Known Limitations

| Level | Mechanism | Scope | Isolation Boundary | Known Limitations |
|---|---|---|---|---|
| **Level 1 (Default)** | Subprocess Jail & Path Chroot | Local process | Path sanitization, environment sanitization, process limits | Shares host kernel and system libraries; not a virtualization boundary. |
| **Level 2 (Container)** | Docker Container Sandbox | Container | Namespaces (pid, net, ipc, mnt, uts), cgroups, `cap-drop ALL`, read-only root | Requires Docker daemon; slight overhead per container spin-up. |

> [!WARNING]
> Subprocess isolation is an application-level control preventing accidental and standard path/command traversal. In untrusted multi-tenant environments, run Astra Agent inside the provided hardened Docker container or an isolated VM.

---

## 4. Audit Logging & Security Events

Security-critical events generate structured audit records:
```json
{
  "event_type": "SECURITY_PATH_VIOLATION",
  "task_id": "tsk_01j7xyz...",
  "timestamp": "2026-10-16T13:25:00.000Z",
  "tool_name": "file_reader",
  "attempted_path": "/etc/passwd",
  "workspace_dir": "/tmp/astra_workspace_123",
  "action_taken": "BLOCKED",
  "ip_address": "127.0.0.1"
}
```

---

## 5. Vulnerability Disclosure Policy

If you discover a security vulnerability in Astra Agent:
1. Do not open a public GitHub issue.
2. Email security details to `security@astra-agent.org` or report via GitHub Private Vulnerability Reporting.
3. The maintainers will respond within 48 hours and provide a patch timeline.

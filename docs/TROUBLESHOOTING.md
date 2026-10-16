# Astra Agent: Troubleshooting Guide

## 1. Common Issues & Resolutions

### 1.1 `PathSecurityViolationError: Path traversal detected`
- **Symptom:** Task fails with error indicating path escapes workspace.
- **Cause:** A tool attempted to read or write a file outside `workspace_dir` (e.g. using `../` or an absolute host path like `/etc/passwd`).
- **Resolution:** Ensure all file paths supplied in task objectives or step parameters are relative to the designated workspace root.

---

### 1.2 `ApprovalRequiredError` / Task Stuck in `WAITING_FOR_APPROVAL`
- **Symptom:** Task execution pauses and does not transition to `COMPLETED`.
- **Cause:** The agent reached a sensitive tool (e.g. file deletion, external network call, or system configuration).
- **Resolution:**
  1. Inspect the pending approval using `GET /api/v1/tasks/{task_id}/status`.
  2. Approve or reject via `POST /api/v1/tasks/{task_id}/approve` with payload:
     ```json
     {"approval_id": "app_xxx", "approved": true, "reviewer": "operator"}
     ```

---

### 1.3 `ExecutionTimeoutError` or Step Times Out
- **Symptom:** Subprocess execution reports `Process timed out after 30s`.
- **Cause:** A script ran an infinite loop or performed slow operations exceeding the step limit.
- **Resolution:** Increase timeout in `TaskInput`:
  ```json
  {"timeout_seconds": 180, "parameters": {"step_timeout": 60}}
  ```

---

### 1.4 Database Locked (`sqlite3.OperationalError: database is locked`)
- **Symptom:** Concurrent API requests fail with SQLite locking errors.
- **Cause:** SQLite does not support high concurrency writes from multiple processes.
- **Resolution:** Switch to PostgreSQL in `ASTRA_DATABASE_URL`:
  ```bash
  export ASTRA_DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/astra"
  ```

---

### 1.5 `ERR_PLAN_INVALID: Cyclic dependency detected`
- **Symptom:** Planning phase rejects model output with cyclic DAG error.
- **Cause:** The language model generated step dependencies with circular references (`stp_1` depends on `stp_2` which depends on `stp_1`).
- **Resolution:** Use an upgraded reasoning model (`gpt-4o`, `claude-3-5-sonnet`) or verify prompt clarity.

---

## 2. Inspecting Logs and Traces

Astra Agent outputs structured JSON logs. To filter logs using `jq`:

```bash
# View errors and security audit records
python scripts/run_local.py --mode server | jq 'select(.level=="ERROR" or .logger=="astra_agent.audit")'

# View task transitions
python scripts/run_local.py --mode server | jq 'select(.event_type=="TOOL_DISPATCH" or .event_type=="APPROVAL_REQUIRED")'
```

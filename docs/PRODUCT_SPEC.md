# Astra Agent: Product Specification & Success Criteria

## 1. Product Overview & Core Mission

**Astra Agent** is an autonomous, production-oriented task execution system built to transform high-level user objectives into rigorously verified, reproducible outcomes. 

Unlike traditional conversational agents that terminate upon generating explanatory text, Astra Agent operates under an **Evidence-First Contract**:
> A task is completed if and only if verifiable execution artifacts (test results, file integrity, schema adherence, process exit codes) satisfy the task's explicit acceptance criteria.

---

## 2. User Personas & Use Cases

### 2.1 Personas
- **Software Engineers:** Automate multi-step code refactoring, test execution, dependency updates, and bug reproduction.
- **Data & DevOps Engineers:** Automate pipeline sanity verification, file parsing, documentation indexing, and environment audits.
- **Security & QA Auditors:** Validate system configurations against strict security policies in isolated environments.

### 2.2 Key Use Cases
1. **Autonomous Code Modification & Test Verification:** Given a codebase and a feature/bug description, plan edits, apply changes safely in a designated workspace, run the test runner, and verify passes.
2. **Data Transformation & Ingestion:** Ingest raw structured/unstructured files, perform calculations, write processed data, and verify schema compliance.
3. **Research & Synthesis with Grounding:** Query local or indexed documentation, extract facts with source provenance, and generate an evidence-backed report.
4. **Interactive Governed Workflows:** Execute safe steps autonomously, pause at sensitive boundaries (e.g., file deletions or external network calls) for human sign-off, and resume immediately upon approval.

---

## 3. Measurable Acceptance Criteria (12 Dimensions)

| Dimension | Metric / Criterion | Threshold / Target | Verification Method |
|---|---|---|---|
| **1. Task Interpretation** | Semantic intent extraction and constraint parsing | 100% of required constraints mapped to TaskPlan | Schema validation of generated TaskPlan against Pydantic schema |
| **2. Valid Execution Plans** | Directed Acyclic Graph (DAG) plan validity | Zero cyclic dependencies; all prerequisites resolvable | Topological sort validation on plan creation |
| **3. Correct Tool Selection** | Tool choice matching step action type | Zero invalid tool calls for approved tool registries | Type-checked tool dispatch filter |
| **4. Tool Execution Reliability** | Graceful handling of timeouts, bad parameters, and missing resources | 0 unhandled tool exceptions crash the orchestrator | Automated tool boundary test suite |
| **5. Error Handling** | Categorization of errors (transient, permanent, security, validation) | 100% of errors classified into standard taxonomy | Error classifier unit tests |
| **6. Retry Behavior** | Exponential backoff with jitter on transient failures; zero retries on permanent/auth failures | Max retries enforced (default: 3); no retry storms | State machine transition assertions |
| **7. Task-State Persistence** | Checkpoint integrity across transitions | 100% recoverable state after simulated worker process kill | Database snapshot reload integration test |
| **8. Verification Accuracy** | Evidence-based completion confirmation | Zero false completions when verification checks fail | Negative verification benchmark tests |
| **9. Security Enforcement** | Prevention of path traversal, unauthorized tool access, and secret leakage | 100% blocked traversal attempts; 0 unmasked secrets in logs | Security penetration test suite |
| **10. Reproducibility** | Deterministic replay given fixed inputs and mock LLM providers | 100% identical step execution traces across runs | Deterministic offline test suite |
| **11. Resource Usage** | Step limits, memory limits, and subprocess CPU/wall-time bounds | Subprocess timeout <= 30s; step count <= max_steps | Resource constraint enforcement tests |
| **12. End-to-End Success** | Completion of full multi-step lifecycle tasks with verified artifacts | >= 90% benchmark task success in offline suite | End-to-end evaluation runner |

---

## 4. Execution Lifecycle States

The execution engine is governed by a strict Finite State Machine:

```
[PENDING] 
   │
   ▼
[PLANNED] ── (requires clarification) ──► [FAILED]
   │
   ▼
[RUNNING] ── (sensitive action detected) ──► [WAITING_FOR_APPROVAL]
   │  ▲                                              │
   │  └────────────────── (approved) ────────────────┘
   │
   ├── (step error & retriable) ──► [RETRYING] ──► [RUNNING]
   │
   ▼
[VERIFYING] ── (criteria not met & retriable) ──► [RETRYING]
   │
   ├── (criteria satisfied) ──► [COMPLETED]
   └── (criteria failed & non-retriable) ──► [FAILED]

* [CANCELLED] can be transitioned to from any active non-terminal state.
```

### Legal Transitions Matrix:
- `PENDING` -> `PLANNED`, `FAILED`, `CANCELLED`
- `PLANNED` -> `RUNNING`, `FAILED`, `CANCELLED`
- `RUNNING` -> `WAITING_FOR_APPROVAL`, `RETRYING`, `VERIFYING`, `FAILED`, `CANCELLED`
- `WAITING_FOR_APPROVAL` -> `RUNNING` (approved), `FAILED` (rejected), `CANCELLED`
- `RETRYING` -> `RUNNING`, `FAILED`, `CANCELLED`
- `VERIFYING` -> `COMPLETED` (verified), `RETRYING` (correction needed), `FAILED`, `CANCELLED`
- Terminal states: `COMPLETED`, `FAILED`, `CANCELLED` (no outbound transitions)

---

## 5. Non-Functional Requirements

1. **Clean Code & Modern Python:** Python 3.11+ using standard async idioms, strict type annotations, and Pydantic v2.
2. **Zero External Daemon Prerequisite for Core Tests:** System unit and integration tests run entirely offline with zero external dependencies (e.g., using in-memory or SQLite database and deterministic mock providers).
3. **Pluggable Architecture:** Database engines (SQLite / PostgreSQL), LLM providers (Mock, OpenAI, Anthropic, Gemini, Ollama), and Tools can be extended without modifying core orchestration logic.
4. **Auditability & Observability:** Every state transition, tool call, observation, and approval decision emits a structured JSON log entry with microsecond timestamps and trace IDs.

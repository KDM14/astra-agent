"""Unit tests for the three-tier memory subsystem."""

import pytest
from astra_agent.memory.models import MemoryCategory
from astra_agent.memory.working_memory import WorkingMemory
from astra_agent.memory.task_memory import PersistentTaskMemory
from astra_agent.memory.semantic_memory import SemanticMemory
from astra_agent.memory.manager import MemoryManager
from astra_agent.core.models import ToolResult


def test_working_memory():
    wm = WorkingMemory(task_id="tsk_wm_1")
    wm.set("result", 42)
    wm.set("api_key", "sk-secret1234567890abcdef")  # should be redacted

    assert wm.get("result") == 42
    assert wm.get("api_key") == "[REDACTED_SECRET]"
    assert "result" in wm.keys()

    snap = wm.snapshot()
    assert snap["result"] == 42

    wm.delete("result")
    assert wm.get("result") is None


def test_task_memory():
    tm = PersistentTaskMemory(task_id="tsk_tm_1")
    tm.record_tool_result("stp_1", ToolResult(
        call_id="call_1",
        tool_name="calculator",
        success=True,
        output={"result": 100},
        duration_ms=12.5,
    ))

    events = tm.get_events()
    assert len(events) == 1
    assert events[0].event_type == "TOOL_EXEC"

    evidence = tm.get_evidence()
    assert len(evidence) == 1
    assert evidence[0]["type"] == "TOOL_OUTPUT"
    assert evidence[0]["source"] == "calculator"


def test_semantic_memory_recall_and_confidence():
    sem = SemanticMemory(max_entries=10)
    
    # Store verified fact
    sem.store(
        task_id="tsk_1",
        category=MemoryCategory.USER_FACT,
        key="project_name",
        content="The application name is Astra Agent.",
        confidence=1.0,
    )

    # Store hypothesis
    sem.store(
        task_id="tsk_1",
        category=MemoryCategory.MODEL_HYPOTHESIS,
        key="performance_guess",
        content="The server might be CPU bound.",
        confidence=0.5,
    )

    # Retrieve by query
    results = sem.retrieve("Astra Agent application", top_k=2)
    assert len(results) >= 1
    assert results[0].key == "project_name"

    # Low confidence filter
    results_high = sem.retrieve("CPU bound server", min_confidence=0.8)
    assert len(results_high) == 0  # Hypothesis filtered out


def test_memory_manager_snapshot():
    mm = MemoryManager(task_id="tsk_mgr_1")
    mm.working.set("x", 10)
    mm.task.log_event("TEST_EVENT", data={"info": "sample"})

    snap = mm.snapshot()
    assert snap["task_id"] == "tsk_mgr_1"
    assert snap["working_memory"] == {"x": 10}
    assert snap["events_count"] == 1

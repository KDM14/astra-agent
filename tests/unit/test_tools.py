"""Unit tests for all Astra Agent tools."""

import json
import pytest
from pathlib import Path

from astra_agent.tools.calculator import CalculatorTool
from astra_agent.tools.file_reader import FileReaderTool
from astra_agent.tools.file_writer import FileWriterTool
from astra_agent.tools.file_search import FileSearchTool
from astra_agent.tools.doc_search import DocSearchTool
from astra_agent.tools.python_exec import PythonExecTool
from astra_agent.tools.state_inspect import StateInspectTool
from astra_agent.tools.test_runner import TestRunnerTool
from astra_agent.tools.browser import BrowserTool


def test_calculator_tool():
    calc = CalculatorTool()
    
    # Basic math
    res = calc.run({"expression": "12 * (4.5 + 3.5)"})
    assert res.success is True
    assert res.output["result"] == 96.0

    # Math function
    res_sqrt = calc.run({"expression": "sqrt(144) + sin(0)"})
    assert res_sqrt.success is True
    assert res_sqrt.output["result"] == 12.0

    # Malicious injection attempt blocked
    res_bad = calc.run({"expression": "__import__('os').system('ls')"})
    assert res_bad.success is False
    assert "Unsupported" in res_bad.error or "not defined" in res_bad.error or "syntax" in res_bad.error.lower()


def test_file_writer_and_reader(tmp_path):
    workspace = str(tmp_path)
    writer = FileWriterTool(workspace_dir=workspace)
    reader = FileReaderTool(workspace_dir=workspace)

    # Write file
    write_res = writer.run({"path": "test.txt", "content": "Hello Astra Agent!\nSecond line.\nThird line."})
    assert write_res.success is True
    assert write_res.output["action"] == "written"

    # Read full file
    read_res = reader.run({"path": "test.txt"})
    assert read_res.success is True
    assert "Hello Astra Agent!" in read_res.output["content"]
    assert read_res.output["total_lines"] == 3

    # Read slice (lines 2 to 3)
    slice_res = reader.run({"path": "test.txt", "start_line": 2, "end_line": 3})
    assert slice_res.success is True
    assert slice_res.output["content"] == "Second line.\nThird line."


def test_file_search_tool(tmp_path):
    workspace = str(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello world')", encoding="utf-8")
    (tmp_path / "src" / "utils.py").write_text("def add(a, b): return a + b", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Documentation", encoding="utf-8")

    search_tool = FileSearchTool(workspace_dir=workspace)
    res = search_tool.run({"pattern": "*.py"})
    assert res.success is True
    assert res.output["count"] == 2
    paths = [r["path"] for r in res.output["results"]]
    assert any("main.py" in p for p in paths)
    assert any("utils.py" in p for p in paths)


def test_doc_search_tool(tmp_path):
    workspace = str(tmp_path)
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "architecture.md").write_text(
        "Astra Agent features an independent evidence-based verification subsystem.",
        encoding="utf-8"
    )

    doc_search = DocSearchTool(workspace_dir=workspace)
    res = doc_search.run({"query": "verification subsystem", "docs_dir": "docs"})
    assert res.success is True
    assert res.output["total_matches"] >= 1
    assert "verification" in res.output["results"][0]["excerpt"].lower()


def test_python_exec_tool(tmp_path):
    workspace = str(tmp_path)
    py_tool = PythonExecTool(workspace_dir=workspace)

    # Valid code
    res = py_tool.run({"code": "print(sum([1, 2, 3, 4]))"})
    assert res.success is True
    assert res.output["stdout"].strip() == "10"
    assert res.output["exit_code"] == 0

    # Failing code
    res_fail = py_tool.run({"code": "raise ValueError('Test error')"})
    assert res_fail.success is True  # Tool executed successfully, captured failure
    assert res_fail.output["exit_code"] != 0
    assert "ValueError: Test error" in res_fail.output["stderr"]


def test_state_inspect_tool():
    def mock_state():
        return {
            "task_id": "tsk_test",
            "current_state": "RUNNING",
            "working_memory": {"key": "val"},
            "steps": [{"step_id": "stp_1", "title": "Step 1", "status": "SUCCESS"}],
        }

    inspect_tool = StateInspectTool(state_provider=mock_state)
    res = inspect_tool.run({"include_memory": True, "include_steps": True})
    assert res.success is True
    assert res.output["task_id"] == "tsk_test"
    assert res.output["working_memory"] == {"key": "val"}
    assert len(res.output["steps_summary"]) == 1


def test_browser_tool_graceful_handling():
    browser = BrowserTool()
    # If playwright is not available or url is blocked, it gracefully reports without crashing
    res = browser.run({"url": "http://example.com"})
    assert res.success is True or "playwright" in str(res.output or "").lower() or "error" in str(res.output or "").lower()

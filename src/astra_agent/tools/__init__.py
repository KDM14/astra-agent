"""Tool exports and default registry factory."""

from astra_agent.tools.base import BaseTool
from astra_agent.tools.registry import ToolRegistry
from astra_agent.tools.calculator import CalculatorTool
from astra_agent.tools.file_reader import FileReaderTool
from astra_agent.tools.file_writer import FileWriterTool
from astra_agent.tools.file_search import FileSearchTool
from astra_agent.tools.doc_search import DocSearchTool
from astra_agent.tools.python_exec import PythonExecTool
from astra_agent.tools.state_inspect import StateInspectTool
from astra_agent.tools.test_runner import TestRunnerTool
from astra_agent.tools.browser import BrowserTool


def create_default_registry(workspace_dir: str) -> ToolRegistry:
    """Builds and populates a tool registry with all standard tools bound to workspace."""
    registry = ToolRegistry()
    registry.register(CalculatorTool(workspace_dir=workspace_dir))
    registry.register(FileReaderTool(workspace_dir=workspace_dir))
    registry.register(FileWriterTool(workspace_dir=workspace_dir))
    registry.register(FileSearchTool(workspace_dir=workspace_dir))
    registry.register(DocSearchTool(workspace_dir=workspace_dir))
    registry.register(PythonExecTool(workspace_dir=workspace_dir))
    registry.register(StateInspectTool(workspace_dir=workspace_dir))
    registry.register(TestRunnerTool(workspace_dir=workspace_dir))
    registry.register(BrowserTool(workspace_dir=workspace_dir))
    return registry


__all__ = [
    "BaseTool",
    "ToolRegistry",
    "CalculatorTool",
    "FileReaderTool",
    "FileWriterTool",
    "FileSearchTool",
    "DocSearchTool",
    "PythonExecTool",
    "StateInspectTool",
    "TestRunnerTool",
    "BrowserTool",
    "create_default_registry",
]

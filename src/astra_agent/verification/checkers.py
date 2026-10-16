"""Independent verification criteria checkers."""

from __future__ import annotations

import abc
import json
import re
from pathlib import Path
from typing import Any, Dict
from astra_agent.core.models import VerificationCriterion, VerificationResult
from astra_agent.security.path_validator import PathValidator
from astra_agent.security.sandbox import SubprocessSandbox


class BaseChecker(abc.ABC):
    """Abstract base for verification checkers."""

    @abc.abstractmethod
    def verify(self, criterion: VerificationCriterion, workspace_dir: str, context: Dict[str, Any]) -> VerificationResult:
        pass


class FileExistsChecker(BaseChecker):
    """Verifies that an expected file exists in the workspace and meets size requirements."""

    def verify(self, criterion: VerificationCriterion, workspace_dir: str, context: Dict[str, Any]) -> VerificationResult:
        rel_path = criterion.parameters.get("path")
        if not rel_path:
            return VerificationResult(
                criterion_id=criterion.criterion_id,
                name=criterion.name,
                passed=False,
                message="Criterion parameter 'path' is missing.",
            )

        try:
            safe_path = PathValidator.resolve_safe_path(workspace_dir, rel_path)
            exists = safe_path.is_file()
            size = safe_path.stat().st_size if exists else 0
            min_bytes = criterion.parameters.get("min_bytes", 1)

            passed = exists and (size >= min_bytes)
            msg = f"File '{rel_path}' exists (size: {size} bytes, min: {min_bytes})" if passed else f"File '{rel_path}' not found or below min size {min_bytes}."
            return VerificationResult(
                criterion_id=criterion.criterion_id,
                name=criterion.name,
                passed=passed,
                message=msg,
                actual_value={"exists": exists, "size_bytes": size},
                expected_value={"exists": True, "min_bytes": min_bytes},
            )
        except Exception as e:
            return VerificationResult(
                criterion_id=criterion.criterion_id,
                name=criterion.name,
                passed=False,
                message=f"File check error: {str(e)}",
            )


class FileContainsChecker(BaseChecker):
    """Verifies that a workspace file contains a specific text string or regex."""

    def verify(self, criterion: VerificationCriterion, workspace_dir: str, context: Dict[str, Any]) -> VerificationResult:
        rel_path = criterion.parameters.get("path")
        expected_text = criterion.parameters.get("text")
        expected_regex = criterion.parameters.get("regex")

        try:
            safe_path = PathValidator.resolve_safe_path(workspace_dir, rel_path)
            if not safe_path.is_file():
                return VerificationResult(
                    criterion_id=criterion.criterion_id,
                    name=criterion.name,
                    passed=False,
                    message=f"File '{rel_path}' does not exist.",
                )

            content = safe_path.read_text(encoding="utf-8", errors="ignore")
            if expected_text:
                passed = expected_text in content
                msg = f"File contains '{expected_text}'" if passed else f"Expected text not found in '{rel_path}'."
                return VerificationResult(
                    criterion_id=criterion.criterion_id,
                    name=criterion.name,
                    passed=passed,
                    message=msg,
                    actual_value=passed,
                    expected_value=True,
                )
            elif expected_regex:
                matched = bool(re.search(expected_regex, content))
                msg = f"File matched regex '{expected_regex}'" if matched else f"Regex did not match '{rel_path}'."
                return VerificationResult(
                    criterion_id=criterion.criterion_id,
                    name=criterion.name,
                    passed=matched,
                    message=msg,
                    actual_value=matched,
                    expected_value=True,
                )

            return VerificationResult(
                criterion_id=criterion.criterion_id,
                name=criterion.name,
                passed=False,
                message="Neither 'text' nor 'regex' provided in criterion parameters.",
            )
        except Exception as e:
            return VerificationResult(
                criterion_id=criterion.criterion_id,
                name=criterion.name,
                passed=False,
                message=f"File contains check error: {str(e)}",
            )


class FileJsonSchemaChecker(BaseChecker):
    """Verifies that a JSON file parses and contains required top-level keys."""

    def verify(self, criterion: VerificationCriterion, workspace_dir: str, context: Dict[str, Any]) -> VerificationResult:
        rel_path = criterion.parameters.get("path")
        required_keys = criterion.parameters.get("required_keys", [])

        try:
            safe_path = PathValidator.resolve_safe_path(workspace_dir, rel_path)
            if not safe_path.is_file():
                return VerificationResult(
                    criterion_id=criterion.criterion_id,
                    name=criterion.name,
                    passed=False,
                    message=f"JSON file '{rel_path}' not found.",
                )

            data = json.loads(safe_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return VerificationResult(
                    criterion_id=criterion.criterion_id,
                    name=criterion.name,
                    passed=False,
                    message="JSON file root must be an object/dict.",
                )

            missing = [k for k in required_keys if k not in data]
            passed = len(missing) == 0
            msg = f"JSON schema valid with keys {list(data.keys())}" if passed else f"Missing required keys: {missing}"
            return VerificationResult(
                criterion_id=criterion.criterion_id,
                name=criterion.name,
                passed=passed,
                message=msg,
                actual_value=list(data.keys()),
                expected_value=required_keys,
            )
        except Exception as e:
            return VerificationResult(
                criterion_id=criterion.criterion_id,
                name=criterion.name,
                passed=False,
                message=f"JSON validation failed: {str(e)}",
            )


class TestSuiteChecker(BaseChecker):
    """Executes workspace pytest suite to verify test passes."""

    __test__ = False

    def verify(self, criterion: VerificationCriterion, workspace_dir: str, context: Dict[str, Any]) -> VerificationResult:
        test_path = criterion.parameters.get("test_path", "tests")
        ws = Path(workspace_dir).resolve()
        sandbox = SubprocessSandbox(workspace_dir=ws, default_timeout=45.0)

        cmd = ["pytest", "-v"]
        if test_path:
            cmd.append(test_path)

        res = sandbox.run(cmd)
        passed = (res.exit_code == 0) and not res.timed_out
        msg = "All workspace tests passed." if passed else f"Tests failed with exit code {res.exit_code}:\n{res.stdout[-300:]}"
        return VerificationResult(
            criterion_id=criterion.criterion_id,
            name=criterion.name,
            passed=passed,
            message=msg,
            actual_value={"exit_code": res.exit_code, "timed_out": res.timed_out},
            expected_value={"exit_code": 0, "timed_out": False},
        )


class NumericEqualityChecker(BaseChecker):
    """Verifies that a computed numeric variable matches an expected value within tolerance."""

    def verify(self, criterion: VerificationCriterion, workspace_dir: str, context: Dict[str, Any]) -> VerificationResult:
        var_name = criterion.parameters.get("variable_name")
        expected_val = criterion.parameters.get("expected_value")
        tolerance = criterion.parameters.get("tolerance", 1e-6)

        actual_val = context.get(var_name)
        if actual_val is None:
            # Check nested results in context
            actual_val = context.get("tool_results", {}).get(var_name)

        if actual_val is None:
            return VerificationResult(
                criterion_id=criterion.criterion_id,
                name=criterion.name,
                passed=False,
                message=f"Variable '{var_name}' not found in execution context.",
            )

        try:
            diff = abs(float(actual_val) - float(expected_val))
            passed = diff <= tolerance
            msg = f"Value {actual_val} matches expected {expected_val} (diff {diff})" if passed else f"Value {actual_val} differs from {expected_val} (diff {diff} > tol {tolerance})"
            return VerificationResult(
                criterion_id=criterion.criterion_id,
                name=criterion.name,
                passed=passed,
                message=msg,
                actual_value=actual_val,
                expected_value=expected_val,
            )
        except (ValueError, TypeError) as e:
            return VerificationResult(
                criterion_id=criterion.criterion_id,
                name=criterion.name,
                passed=False,
                message=f"Non-numeric comparison error: {e}",
            )

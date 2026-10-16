"""Unit tests for independent verification engine."""

import json
import pytest
from pathlib import Path

from astra_agent.core.models import (
    VerificationCriterion,
    VerificationCriterionType,
)
from astra_agent.verification.checkers import (
    FileContainsChecker,
    FileExistsChecker,
    FileJsonSchemaChecker,
    NumericEqualityChecker,
)
from astra_agent.verification.verifier import IndependentVerifier


def test_file_exists_checker(tmp_path):
    ws = str(tmp_path)
    (tmp_path / "valid.txt").write_text("content", encoding="utf-8")

    checker = FileExistsChecker()
    crit_pass = VerificationCriterion(
        name="Valid file check",
        criterion_type=VerificationCriterionType.FILE_EXISTS,
        parameters={"path": "valid.txt", "min_bytes": 4},
    )
    res_pass = checker.verify(crit_pass, ws, {})
    assert res_pass.passed is True

    crit_fail = VerificationCriterion(
        name="Missing file check",
        criterion_type=VerificationCriterionType.FILE_EXISTS,
        parameters={"path": "missing.txt"},
    )
    res_fail = checker.verify(crit_fail, ws, {})
    assert res_fail.passed is False


def test_file_contains_checker(tmp_path):
    ws = str(tmp_path)
    (tmp_path / "code.py").write_text("def solve(): return 42", encoding="utf-8")

    checker = FileContainsChecker()
    crit = VerificationCriterion(
        name="Function check",
        criterion_type=VerificationCriterionType.FILE_CONTAINS,
        parameters={"path": "code.py", "text": "def solve():"},
    )
    res = checker.verify(crit, ws, {})
    assert res.passed is True


def test_file_json_schema_checker(tmp_path):
    ws = str(tmp_path)
    json_data = {"status": "ok", "count": 100, "data": [1, 2, 3]}
    (tmp_path / "summary.json").write_text(json.dumps(json_data), encoding="utf-8")

    checker = FileJsonSchemaChecker()
    crit = VerificationCriterion(
        name="JSON schema check",
        criterion_type=VerificationCriterionType.FILE_JSON_SCHEMA,
        parameters={"path": "summary.json", "required_keys": ["status", "count", "data"]},
    )
    res = checker.verify(crit, ws, {})
    assert res.passed is True

    crit_missing = VerificationCriterion(
        name="Missing key check",
        criterion_type=VerificationCriterionType.FILE_JSON_SCHEMA,
        parameters={"path": "summary.json", "required_keys": ["status", "missing_key"]},
    )
    res_missing = checker.verify(crit_missing, ws, {})
    assert res_missing.passed is False


def test_numeric_equality_checker():
    checker = NumericEqualityChecker()
    crit = VerificationCriterion(
        name="Numeric result check",
        criterion_type=VerificationCriterionType.NUMERIC_EQUALITY,
        parameters={"variable_name": "total", "expected_value": 42.0, "tolerance": 0.01},
    )

    res_pass = checker.verify(crit, "/tmp", {"total": 42.005})
    assert res_pass.passed is True

    res_fail = checker.verify(crit, "/tmp", {"total": 50.0})
    assert res_fail.passed is False


def test_independent_verifier_aggregate(tmp_path):
    ws = str(tmp_path)
    (tmp_path / "out.txt").write_text("Astra Verification", encoding="utf-8")

    verifier = IndependentVerifier()
    criteria = [
        VerificationCriterion(
            name="Check out.txt exists",
            criterion_type=VerificationCriterionType.FILE_EXISTS,
            parameters={"path": "out.txt"},
        ),
        VerificationCriterion(
            name="Check text",
            criterion_type=VerificationCriterionType.FILE_CONTAINS,
            parameters={"path": "out.txt", "text": "Astra"},
        ),
    ]

    results = verifier.verify(criteria, ws, {})
    assert len(results) == 2
    assert verifier.is_all_passed(results) is True

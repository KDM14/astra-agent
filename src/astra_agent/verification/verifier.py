"""Independent verification engine."""

from __future__ import annotations

from typing import Any, Dict, List
from astra_agent.core.models import VerificationCriterion, VerificationCriterionType, VerificationResult
from astra_agent.verification.checkers import (
    BaseChecker,
    FileExistsChecker,
    FileContainsChecker,
    FileJsonSchemaChecker,
    TestSuiteChecker,
    NumericEqualityChecker,
)


class IndependentVerifier:
    """Verifies task completion based strictly on concrete execution evidence."""

    def __init__(self):
        self._checkers: Dict[VerificationCriterionType, BaseChecker] = {
            VerificationCriterionType.FILE_EXISTS: FileExistsChecker(),
            VerificationCriterionType.FILE_CONTAINS: FileContainsChecker(),
            VerificationCriterionType.FILE_JSON_SCHEMA: FileJsonSchemaChecker(),
            VerificationCriterionType.TEST_SUITE_PASS: TestSuiteChecker(),
            VerificationCriterionType.NUMERIC_EQUALITY: NumericEqualityChecker(),
        }

    def register_checker(self, criterion_type: VerificationCriterionType, checker: BaseChecker) -> None:
        self._checkers[criterion_type] = checker

    def verify(
        self,
        criteria: List[VerificationCriterion],
        workspace_dir: str,
        context: Dict[str, Any],
    ) -> List[VerificationResult]:
        """Runs all criteria against the workspace and context."""
        results: List[VerificationResult] = []

        for crit in criteria:
            checker = self._checkers.get(crit.criterion_type)
            if not checker:
                results.append(VerificationResult(
                    criterion_id=crit.criterion_id,
                    name=crit.name,
                    passed=False,
                    message=f"No verification checker registered for type: {crit.criterion_type.value}",
                ))
                continue

            res = checker.verify(crit, workspace_dir, context)
            results.append(res)

        return results

    @staticmethod
    def is_all_passed(results: List[VerificationResult]) -> bool:
        """True if all criteria passed; False if any failed or if criteria list was non-empty and unverified."""
        if not results:
            return True
        return all(r.passed for r in results)

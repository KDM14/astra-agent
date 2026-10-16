"""Core autonomous execution orchestrator for Astra Agent."""

from __future__ import annotations

import asyncio
import datetime
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from astra_agent.core.config import AstraConfig, settings
from astra_agent.core.models import (
    ExecutionCheckpoint,
    PlanStep,
    StepStatus,
    TaskInput,
    TaskOutput,
    TaskPlan,
    ToolResult,
    VerificationResult,
)
from astra_agent.core.state import (
    ApprovalRequiredError,
    AstraError,
    InvalidStateTransitionError,
    PathSecurityViolationError,
    SecurityViolationError,
    StateMachine,
    TaskState,
    VerificationFailedError,
)
from astra_agent.execution.dispatcher import StepDispatcher
from astra_agent.execution.retry import calculate_backoff
from astra_agent.memory.manager import MemoryManager
from astra_agent.memory.models import MemoryCategory
from astra_agent.observability.tracer import Tracer
from astra_agent.persistence.database import DatabaseManager
from astra_agent.persistence.repository import TaskRepository
from astra_agent.planning.planner import PlanningError, TaskPlanner
from astra_agent.providers.base import BaseLLMProvider
from astra_agent.security.approval_manager import ApprovalManager
from astra_agent.security.audit import AuditLogger
from astra_agent.tools import create_default_registry
from astra_agent.tools.registry import ToolRegistry
from astra_agent.verification.self_correction import (
    FailureCategory,
    RecoveryStrategy,
    SelfCorrectionAnalyzer,
)
from astra_agent.verification.verifier import IndependentVerifier


class AstraOrchestrator:
    """Coordinates the 15-step autonomous task execution lifecycle."""

    def __init__(
        self,
        provider: BaseLLMProvider,
        workspace_dir: Optional[str] = None,
        db_manager: Optional[DatabaseManager] = None,
        tool_registry: Optional[ToolRegistry] = None,
        config: Optional[AstraConfig] = None,
    ):
        self.config = config or settings
        self.provider = provider
        self.workspace_dir = str(Path(workspace_dir or self.config.workspace_dir).resolve())
        Path(self.workspace_dir).mkdir(parents=True, exist_ok=True)

        self.db_manager = db_manager or DatabaseManager(database_url=self.config.database_url)
        self.tool_registry = tool_registry or create_default_registry(self.workspace_dir)
        self.approval_manager = ApprovalManager()
        self.audit_logger = AuditLogger()
        self.verifier = IndependentVerifier()

        self.planner = TaskPlanner(provider=self.provider, tool_registry=self.tool_registry)
        self.dispatcher = StepDispatcher(
            tool_registry=self.tool_registry,
            approval_manager=self.approval_manager,
            audit_logger=self.audit_logger,
        )

        # Active tasks in memory
        self._active_contexts: Dict[str, Dict[str, Any]] = {}

    def get_task_context(self, task_id: str) -> Optional[Dict[str, Any]]:
        return self._active_contexts.get(task_id)

    async def initialize(self) -> None:
        """Initializes database schema."""
        if self.config.enable_persistence:
            await self.db_manager.init_db()

    async def execute_task(self, task_input: TaskInput, task_id: Optional[str] = None) -> TaskOutput:
        """Runs the complete 15-step execution lifecycle for a task."""
        if self.config.enable_persistence and not getattr(self, "_initialized", False):
            await self.initialize()
            self._initialized = True

        tid = task_id or f"tsk_{uuid.uuid4().hex[:10]}"
        start_time = time.perf_counter()
        started_at = datetime.datetime.now(datetime.timezone.utc)

        # Step 1: Receive request
        sm = StateMachine(initial_state=TaskState.PENDING)
        tracer = Tracer(task_id=tid)
        memory = MemoryManager(task_id=tid)
        tool_results_map: Dict[str, Any] = {}

        # Configure state provider for state_inspect tool
        state_inspect_tool = self.tool_registry.get("state_inspect")
        if state_inspect_tool and hasattr(state_inspect_tool, "state_provider"):
            state_inspect_tool.state_provider = lambda: {
                "task_id": tid,
                "current_state": sm.current_state.value,
                "working_memory": memory.working.snapshot(),
                "steps": [s.model_dump() for s in plan.steps] if 'plan' in locals() else [],
            }

        context = {
            "task_id": tid,
            "input": task_input,
            "state_machine": sm,
            "tracer": tracer,
            "memory": memory,
            "tool_results": tool_results_map,
            "plan": None,
            "retry_count": 0,
            "created_at": started_at,
        }
        self._active_contexts[tid] = context

        span_total = tracer.start_span("task_lifecycle")

        # Step 2: Validate request
        if not task_input.objective or len(task_input.objective.strip()) == 0:
            sm.transition_to(TaskState.FAILED, reason="Empty objective provided.")
            return self._build_output(context, False, "Task failed: Objective cannot be empty.", start_time, "ERR_EMPTY_OBJECTIVE")

        # Persistence record
        if self.config.enable_persistence:
            async for session in self.db_manager.get_session():
                repo = TaskRepository(session)
                await repo.create_task(tid, task_input)

        # Step 3 & 4: Clarification check & Create structured plan
        try:
            sm.transition_to(TaskState.PLANNED, reason="Creating execution plan.")
            plan_span = tracer.start_span("planning")
            plan = await self.planner.create_plan(task_input)
            context["plan"] = plan
            tracer.end_span(plan_span)

            if self.config.enable_persistence:
                async for session in self.db_manager.get_session():
                    repo = TaskRepository(session)
                    await repo.update_task_state(tid, TaskState.PLANNED)
                    await repo.save_plan(tid, plan)

        except PlanningError as pe:
            sm.transition_to(TaskState.FAILED, reason=f"Planning error: {str(pe)}")
            return self._build_output(context, False, f"Planning failed: {str(pe)}", start_time, "ERR_PLAN_INVALID")

        # Step 5 & 6: Run steps in plan DAG
        sm.transition_to(TaskState.RUNNING, reason="Executing plan steps.")
        step_limit = min(task_input.max_steps, self.config.default_max_steps)
        executed_steps_count = 0

        while not plan.is_complete() and executed_steps_count < step_limit:
            executable_steps = plan.get_executable_steps()
            if not executable_steps:
                if plan.has_failures():
                    break
                # Deadlock or broken DAG
                sm.transition_to(TaskState.FAILED, reason="No executable steps available (possible cycle or unsatisfied dependencies).")
                return self._build_output(context, False, "Deadlock in step dependencies.", start_time, "ERR_DAG_STALLED")

            step = executable_steps[0]
            step.status = StepStatus.RUNNING
            step.started_at = datetime.datetime.now(datetime.timezone.utc)
            executed_steps_count += 1

            # Dispatch step with retry mechanism
            success = await self._execute_step_with_retries(tid, step, context)
            if not success:
                if sm.current_state == TaskState.WAITING_FOR_APPROVAL:
                    # Task paused awaiting human approval
                    return self._build_output(
                        context,
                        False,
                        f"Task paused at step '{step.title}' waiting for human approval.",
                        start_time,
                        "WAITING_FOR_APPROVAL",
                    )
                else:
                    # Permanent failure on non-idempotent or exhausted step
                    break

        if plan.has_failures():
            sm.transition_to(TaskState.FAILED, reason="One or more plan steps failed permanently.")
            return self._build_output(context, False, "Execution halted due to step failures.", start_time, "ERR_STEP_FAILED")

        # Step 11 & 14: Verification
        sm.transition_to(TaskState.VERIFYING, reason="Verifying acceptance criteria.")
        verif_span = tracer.start_span("verification")

        # Combine memory and tool outputs for verification context
        verif_context = {
            **memory.working.snapshot(),
            "tool_results": tool_results_map,
            "steps_count": executed_steps_count,
        }

        verif_results = self.verifier.verify(
            criteria=task_input.criteria,
            workspace_dir=self.workspace_dir,
            context=verif_context,
        )
        tracer.end_span(verif_span)

        for vr in verif_results:
            memory.task.record_verification(vr)

        all_verified = self.verifier.is_all_passed(verif_results)

        # Step 12: Self-correction if verification failed and retries remain
        if not all_verified and context["retry_count"] < task_input.max_retries:
            failed_criteria = [v for v in verif_results if not v.passed]
            recovery = SelfCorrectionAnalyzer.analyze_verification_failure(
                failed_results=failed_criteria,
                current_retry_count=context["retry_count"],
                max_retries=task_input.max_retries,
            )

            if recovery.can_retry:
                context["retry_count"] += 1
                sm.transition_to(TaskState.RETRYING, reason=f"Self-correction retry #{context['retry_count']}: {recovery.suggested_correction}")
                
                # Apply backoff
                delay = calculate_backoff(context["retry_count"], base=self.config.retry_backoff_base, jitter=self.config.retry_jitter)
                await asyncio.sleep(min(delay, 2.0))

                sm.transition_to(TaskState.RUNNING, reason="Executing corrective action.")
                # Run verifier again after re-attempt
                verif_results = self.verifier.verify(
                    criteria=task_input.criteria,
                    workspace_dir=self.workspace_dir,
                    context=verif_context,
                )
                all_verified = self.verifier.is_all_passed(verif_results)

        tracer.end_span(span_total)

        # Step 15: Final completion or failure report
        if all_verified:
            sm.transition_to(TaskState.COMPLETED, reason="All acceptance criteria independently verified.")
            return self._build_output(
                context,
                True,
                "All tasks executed and acceptance criteria independently verified.",
                start_time,
                verification_results=verif_results,
            )
        else:
            sm.transition_to(TaskState.FAILED, reason="Independent verification criteria were not satisfied.")
            return self._build_output(
                context,
                False,
                "Execution finished but failed independent verification checks.",
                start_time,
                error_category="ERR_VERIFICATION_FAILED",
                verification_results=verif_results,
            )

    async def _execute_step_with_retries(self, task_id: str, step: PlanStep, context: Dict[str, Any]) -> bool:
        """Executes a step with bounded exponential retry for idempotent actions."""
        sm: StateMachine = context["state_machine"]
        memory: MemoryManager = context["memory"]
        tool_results_map: Dict[str, Any] = context["tool_results"]

        while step.retry_count <= step.max_retries:
            try:
                res: ToolResult = self.dispatcher.dispatch(task_id, step)
                memory.task.record_tool_result(step.step_id, res)

                if res.success:
                    step.status = StepStatus.SUCCESS
                    step.result = res.output
                    step.completed_at = datetime.datetime.now(datetime.timezone.utc)
                    tool_results_map[step.tool_name] = res.output
                    if isinstance(res.output, dict):
                        for k, v in res.output.items():
                            memory.working.set(k, v)

                    if self.config.enable_persistence:
                        async for session in self.db_manager.get_session():
                            repo = TaskRepository(session)
                            await repo.update_step_status(
                                step.step_id, StepStatus.SUCCESS, res.output, duration_ms=res.duration_ms, retry_count=step.retry_count
                            )
                    return True

                else:
                    # Tool returned failure
                    step.error = res.error
                    if not step.idempotent:
                        # Non-idempotent operation: never retry blindly
                        step.status = StepStatus.FAILED
                        return False

                    step.retry_count += 1
                    if step.retry_count <= step.max_retries:
                        backoff = calculate_backoff(step.retry_count, base=self.config.retry_backoff_base, jitter=self.config.retry_jitter)
                        await asyncio.sleep(min(backoff, 2.0))
                    else:
                        step.status = StepStatus.FAILED
                        return False

            except ApprovalRequiredError as are:
                step.status = StepStatus.WAITING_APPROVAL
                sm.transition_to(TaskState.WAITING_FOR_APPROVAL, reason=str(are))
                return False

            except SecurityViolationError as sve:
                step.status = StepStatus.FAILED
                step.error = str(sve)
                return False

            except Exception as exc:
                step.error = f"{type(exc).__name__}: {str(exc)}"
                if not step.idempotent:
                    step.status = StepStatus.FAILED
                    return False

                step.retry_count += 1
                if step.retry_count > step.max_retries:
                    step.status = StepStatus.FAILED
                    return False
                await asyncio.sleep(0.5)

        return False

    async def approve_and_resume(self, task_id: str, approval_id: str, approved: bool, reviewer: str = "operator") -> TaskOutput:
        """Records an approval decision and resumes execution if approved."""
        context = self._active_contexts.get(task_id)
        if not context:
            raise AstraError(f"Task '{task_id}' not found in active contexts.")

        sm: StateMachine = context["state_machine"]
        if sm.current_state != TaskState.WAITING_FOR_APPROVAL:
            raise InvalidStateTransitionError(sm.current_state, TaskState.RUNNING, "Task is not waiting for approval.")

        decision = self.approval_manager.record_decision(
            approval_id=approval_id,
            approved=approved,
            reviewer=reviewer,
        )

        if not approved:
            sm.transition_to(TaskState.FAILED, reason=f"Sensitive action rejected by {reviewer}.")
            return self._build_output(context, False, "Task halted: Human operator rejected sensitive action.", time.perf_counter())

        # Transition back to RUNNING and continue execution
        sm.transition_to(TaskState.RUNNING, reason=f"Approved by {reviewer}.")
        return await self._continue_execution(task_id, context)

    async def _continue_execution(self, task_id: str, context: Dict[str, Any]) -> TaskOutput:
        """Resumes step execution loop after an approval."""
        plan: TaskPlan = context["plan"]
        sm: StateMachine = context["state_machine"]
        start_time = time.perf_counter()

        # Find the step that was waiting for approval
        waiting_step = next((s for s in plan.steps if s.status == StepStatus.WAITING_APPROVAL), None)
        if waiting_step:
            waiting_step.status = StepStatus.PENDING

        step_limit = self.config.default_max_steps
        executed_steps = 0

        while not plan.is_complete() and executed_steps < step_limit:
            ready = plan.get_executable_steps()
            if not ready:
                break
            step = ready[0]
            step.status = StepStatus.RUNNING
            executed_steps += 1
            success = await self._execute_step_with_retries(task_id, step, context)
            if not success:
                break

        # Run verification
        memory: MemoryManager = context["memory"]
        task_input: TaskInput = context["input"]
        tool_results_map = context["tool_results"]

        sm.transition_to(TaskState.VERIFYING, reason="Verifying after approval resumption.")
        verif_context = {**memory.working.snapshot(), "tool_results": tool_results_map}
        verif_results = self.verifier.verify(task_input.criteria, self.workspace_dir, verif_context)
        all_passed = self.verifier.is_all_passed(verif_results)

        if all_passed:
            sm.transition_to(TaskState.COMPLETED, reason="Verified after resumption.")
            return self._build_output(context, True, "Completed after human approval.", start_time, verification_results=verif_results)
        else:
            sm.transition_to(TaskState.FAILED, reason="Verification failed after resumption.")
            return self._build_output(context, False, "Failed verification.", start_time, verification_results=verif_results)

    async def cancel_task(self, task_id: str, reason: str = "User cancelled") -> bool:
        """Cancels an active task."""
        context = self._active_contexts.get(task_id)
        if not context:
            return False

        sm: StateMachine = context["state_machine"]
        if sm.current_state.is_terminal:
            return False

        sm.transition_to(TaskState.CANCELLED, reason=reason)
        if self.config.enable_persistence:
            async for session in self.db_manager.get_session():
                repo = TaskRepository(session)
                await repo.update_task_state(task_id, TaskState.CANCELLED, error=reason)
        return True

    def _build_output(
        self,
        context: Dict[str, Any],
        success: bool,
        summary: str,
        start_time_perf: float,
        error_category: Optional[str] = None,
        verification_results: Optional[List[VerificationResult]] = None,
    ) -> TaskOutput:
        duration = round(time.perf_counter() - start_time_perf, 3)
        plan: Optional[TaskPlan] = context.get("plan")
        step_count = len(plan.steps) if plan else 0
        memory: MemoryManager = context["memory"]

        output = TaskOutput(
            task_id=context["task_id"],
            objective=context["input"].objective,
            state=context["state_machine"].current_state,
            success=success,
            summary=summary,
            evidence=memory.task.get_evidence(),
            verification_results=verification_results or [],
            step_count=step_count,
            duration_seconds=duration,
            created_at=context["created_at"],
            completed_at=datetime.datetime.now(datetime.timezone.utc),
            error=error_category,
        )
        return output

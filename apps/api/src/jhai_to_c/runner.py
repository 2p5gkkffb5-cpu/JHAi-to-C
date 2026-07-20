from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Mapping
from contextlib import AsyncExitStack, suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command

from jhai_to_c.contracts.project import AgentDecisionRequest
from jhai_to_c.contracts.video import VideoGenerationRequest, VideoTask
from jhai_to_c.db.models import ContentProject, WorkflowJob
from jhai_to_c.services import ContentProjectService
from jhai_to_c.workflow import build_content_project_graph
from jhai_to_c.workflow.errors import InvalidReferenceSubsetError
from jhai_to_c.workflow.nodes import APPROVAL_NODE_BY_AGENT_NODE
from jhai_to_c.workflow.production import project_production_input
from jhai_to_c.workflow.runtime_contracts import (
    AGENT_OUTPUT_SPECS,
    AgentOutputExtractionError,
    extract_agent_output,
)

logger = logging.getLogger(__name__)

AGENT_BY_NODE = {node_name: spec.agent_name for node_name, spec in AGENT_OUTPUT_SPECS.items()}

APPROVAL_AGENT_NODE_BY_GATE = {
    gate_name: node_name for node_name, gate_name in APPROVAL_NODE_BY_AGENT_NODE.items()
}
ALL_APPROVAL_NODE_NAMES = frozenset(APPROVAL_AGENT_NODE_BY_GATE)

ARTIFACTS_BY_NODE = {
    "director": (("creative_brief", "creative_brief"),),
    "research": (("research", "research"), ("strategy", "strategies")),
    "production": (
        ("copywriting", "copywriting"),
        ("storyboard", "storyboard"),
        ("video_prompt", "video_prompt"),
    ),
    "brand_packaging": (("brand_packaging", "brand_packaging"),),
    "video_clone_analysis": (("video_clone_analysis", "video_clone_analysis"),),
    "video_clone_mapping": (("video_clone_mapping", "video_clone_mapping"),),
    "video_clone_prompt": (
        ("video_clone_prompt", "video_clone_prompt"),
        ("video_prompt", "video_prompt"),
    ),
    "video_clone_review": (("video_clone_review", "video_clone_review"),),
}

Namespace = tuple[str, ...]
ActiveRunKey = tuple[Namespace, str]


@dataclass(slots=True)
class ActiveAgentRun:
    run_id: str
    node_name: str
    agent_input: Any = None
    agent_name: str | None = None
    attempt: int | None = None
    tools: list[dict[str, str]] = field(default_factory=list)
    provider: str = "mock"


@dataclass(slots=True)
class ExecutionState:
    active_runs: dict[ActiveRunKey, ActiveAgentRun] = field(default_factory=dict)
    nested_failure_seen: set[str] = field(default_factory=set)
    failure_node: str | None = None
    failure_error: dict[str, Any] | None = None


class WorkflowRunner:
    """Single-process async runner for the financing Demo.

    HTTP only queues work. The worker owns graph execution and all persistence through
    ``ContentProjectService``; graph nodes remain database-agnostic.
    """

    def __init__(
        self,
        service: ContentProjectService,
        checkpoint_path: str,
        *,
        graph_builder: Callable[..., Any] = build_content_project_graph,
        provider_names: Mapping[str, str] | None = None,
    ) -> None:
        self.service = service
        self.checkpoint_path = checkpoint_path
        self.graph_builder = graph_builder
        self.provider_names = {
            "llm": "mock",
            "research": "mock",
            "video": "mock",
            "video_understanding": "mock-video-understanding",
            **dict(provider_names or {}),
        }
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._exit_stack: AsyncExitStack | None = None
        self._worker_task: asyncio.Task[None] | None = None
        self._active_job_tasks: dict[str, asyncio.Task[None]] = {}
        self._graph: Any = None

    async def start(self) -> None:
        if self._worker_task is not None:
            return

        checkpoint_path = Path(self.checkpoint_path).expanduser()
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        stack = AsyncExitStack()
        saver = await stack.enter_async_context(
            AsyncSqliteSaver.from_conn_string(str(checkpoint_path))
        )
        await saver.setup()

        self._exit_stack = stack
        self._graph = self.graph_builder(
            checkpointer=saver,
            video_status_callback=self._persist_live_video_status,
        )
        self._worker_task = asyncio.create_task(
            self._worker_loop(), name="content-project-workflow-runner"
        )

    async def stop(self) -> None:
        worker = self._worker_task
        self._worker_task = None
        if worker is not None:
            worker.cancel()
            with suppress(asyncio.CancelledError):
                await worker
        self._graph = None
        if self._exit_stack is not None:
            await self._exit_stack.aclose()
            self._exit_stack = None

    async def enqueue(self, project_id: str) -> WorkflowJob:
        if self._worker_task is None or self._graph is None:
            raise RuntimeError("WorkflowRunner has not been started")

        job = await self.service.create_start_job(
            project_id,
            provider=self.provider_names["video"],
        )
        self._queue.put_nowait(job.id)
        return job

    async def enqueue_strategy_selection(
        self,
        project_id: str,
        strategy_id: str,
    ) -> WorkflowJob:
        if self._worker_task is None or self._graph is None:
            raise RuntimeError("WorkflowRunner has not been started")

        job = await self.service.create_strategy_resume_job(
            project_id,
            strategy_id=strategy_id,
            provider=self.provider_names["video"],
        )
        self._queue.put_nowait(job.id)
        return job

    async def enqueue_agent_decision(
        self,
        project_id: str,
        decision: AgentDecisionRequest,
    ) -> WorkflowJob:
        if self._worker_task is None or self._graph is None:
            raise RuntimeError("WorkflowRunner has not been started")

        job = await self.service.create_agent_decision_resume_job(
            project_id,
            decision,
            provider=self.provider_names["video"],
        )
        self._queue.put_nowait(job.id)
        return job

    async def cancel(self, project_id: str) -> None:
        await self.service.cancel_project(project_id)
        task = self._active_job_tasks.get(project_id)
        if task is not None and not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    async def _worker_loop(self) -> None:
        while True:
            job_id = await self._queue.get()
            try:
                job = await self.service.claim_job(job_id)
                if job is not None:
                    execution_task = asyncio.create_task(
                        self._execute_job(job),
                        name=f"content-project-{job.project_id}",
                    )
                    self._active_job_tasks[job.project_id] = execution_task
                    try:
                        await execution_task
                    except asyncio.CancelledError:
                        if self._worker_task is None:
                            raise
                    finally:
                        self._active_job_tasks.pop(job.project_id, None)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Unexpected workflow worker error for job %s", job_id)
            finally:
                self._queue.task_done()

    async def _execute_job(self, job: WorkflowJob) -> None:
        execution = ExecutionState()
        project_id = job.project_id
        try:
            project = await self.service.get_project(project_id)
            if project is None:
                raise LookupError(f"ContentProject not found: {project_id}")

            graph_input: dict[str, Any] | Command
            if job.job_type == "resume_project":
                resume_payload = job.resume_payload
                if not isinstance(resume_payload, dict):
                    if not project.selected_strategy_id:
                        raise RuntimeError("Resume job has no persisted decision payload")
                    resume_payload = {"strategy_id": project.selected_strategy_id}
                graph_input = Command(resume=resume_payload)
                last_state: dict[str, Any] = {}
            else:
                graph_input = self._initial_state(project)
                last_state = dict(graph_input)
            pending_approval: dict[str, Any] | None = None
            await self.service.append_event(
                project_id,
                "workflow.started",
                payload={
                    "job_id": job.id,
                    "job_type": job.job_type,
                    "providers": self.provider_names,
                },
            )

            config = {"configurable": {"thread_id": project_id}}
            async for part in self._graph.astream(
                graph_input,
                config=config,
                stream_mode=["tasks", "values"],
                subgraphs=True,
                version="v2",
            ):
                part_type = part.get("type")
                data = part.get("data")
                namespace = self._namespace(part.get("ns"))
                if part_type == "values" and not namespace and isinstance(data, dict):
                    last_state = data
                if part_type == "values":
                    approval = self._approval_from_interrupts(part.get("interrupts"))
                    if approval is not None:
                        pending_approval = approval
                elif part_type == "tasks" and isinstance(data, dict):
                    await self._handle_task_event(
                        project_id,
                        namespace,
                        data,
                        execution,
                    )

            await self._complete_job(job, last_state, pending_approval=pending_approval)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self._fail_job(job, exc, execution)

    async def _handle_task_event(
        self,
        project_id: str,
        namespace: Namespace,
        data: dict[str, Any],
        execution: ExecutionState,
    ) -> None:
        task_id = str(data.get("id", ""))
        node_name = str(data.get("name", ""))
        if "input" in data and "result" not in data and "error" not in data:
            await self._start_node(
                project_id,
                namespace,
                task_id,
                node_name,
                data,
                execution,
            )
            return
        if "result" not in data and "error" not in data:
            return

        error = data.get("error")
        result = data.get("result")
        active_key = (namespace, task_id)

        if node_name in ALL_APPROVAL_NODE_NAMES:
            if error is not None:
                await self._record_task_failure(
                    project_id,
                    namespace,
                    task_id,
                    APPROVAL_AGENT_NODE_BY_GATE[node_name],
                    error,
                    execution,
                )
            return

        if node_name == "video_generation":
            if error is not None:
                await self._record_task_failure(
                    project_id,
                    namespace,
                    task_id,
                    node_name,
                    error,
                    execution,
                )
                return
            result_data = result if isinstance(result, dict) else {}
            await self._persist_node_output(project_id, node_name, result_data)
            video_output = result_data.get("video_task", {})
            observation_summary = "视频生成工具已返回终态结果。"
            await self.service.append_event(
                project_id,
                "node.completed",
                node_name=node_name,
                payload={
                    "task_id": task_id,
                    "agent_name": None,
                    "attempt": None,
                    "tools": self._tools_for_node(node_name),
                    "provider": self._provider_for_node(node_name),
                    "summary": observation_summary,
                    "output": video_output if isinstance(video_output, Mapping) else {},
                },
            )
            await self._append_trace_event(
                project_id,
                "observation",
                task_id=task_id,
                node_name=node_name,
                summary=observation_summary,
                status="completed",
            )
            return

        if node_name == "intent_router":
            if error is not None:
                await self._record_task_failure(
                    project_id,
                    namespace,
                    task_id,
                    node_name,
                    error,
                    execution,
                )
                return
            result_data = result if isinstance(result, dict) else {}
            decision = result_data.get("intent_decision")
            if not isinstance(decision, Mapping) or not isinstance(decision.get("intent"), str):
                await self._record_task_failure(
                    project_id,
                    namespace,
                    task_id,
                    node_name,
                    ValueError("Intent router returned no validated intent decision"),
                    execution,
                )
                return
            await self.service.update_status(
                project_id,
                "running",
                resolved_intent=str(decision["intent"]),
            )
            summary = self._safe_output_summary(node_name, decision)
            await self.service.append_event(
                project_id,
                "node.completed",
                node_name=node_name,
                payload={
                    "task_id": task_id,
                    "agent_name": None,
                    "attempt": None,
                    "tools": self._tools_for_node(node_name),
                    "provider": self._provider_for_node(node_name),
                    "summary": summary,
                    "output": dict(decision),
                },
            )
            await self._append_trace_event(
                project_id,
                "observation",
                task_id=task_id,
                node_name=node_name,
                summary=summary,
                status="completed",
            )
            return

        if error is not None:
            await self._record_task_failure(
                project_id,
                namespace,
                task_id,
                node_name,
                error,
                execution,
            )
            return

        active = execution.active_runs.get(active_key)
        try:
            output_data = extract_agent_output(
                node_name,
                result,
                agent_input=None if active is None else active.agent_input,
            )
        except (AgentOutputExtractionError, InvalidReferenceSubsetError) as exc:
            await self._record_task_failure(
                project_id,
                namespace,
                task_id,
                node_name,
                exc,
                execution,
            )
            raise

        if active is None:
            raise AgentOutputExtractionError(node_name, "active AgentRun is unavailable")
        await self.service.finish_agent_run(
            active.run_id,
            status="completed",
            output_data=output_data,
        )
        execution.active_runs.pop(active_key, None)

        result_data = result if isinstance(result, dict) else {}
        await self._persist_node_output(project_id, node_name, result_data)
        observation_summary = self._safe_output_summary(node_name, output_data)
        await self.service.append_event(
            project_id,
            "node.completed",
            node_name=node_name,
            payload={
                "task_id": task_id,
                "agent_name": active.agent_name,
                "attempt": active.attempt,
                "tools": active.tools,
                "provider": active.provider,
                "summary": observation_summary,
                "output": output_data,
            },
        )
        await self._append_trace_event(
            project_id,
            "observation",
            task_id=task_id,
            node_name=node_name,
            summary=observation_summary,
            attempt=active.attempt,
            agent_name=active.agent_name,
            tools=active.tools,
            provider=active.provider,
            status="completed",
        )

    async def _record_task_failure(
        self,
        project_id: str,
        namespace: Namespace,
        task_id: str,
        node_name: str,
        error: object,
        execution: ExecutionState,
    ) -> None:
        public_node = self._public_node(node_name)
        error_payload = self._error_payload(
            error,
            public_node,
            internal_node=node_name,
            internal_agent=AGENT_BY_NODE.get(node_name),
            failure_scope="descendant" if namespace else "task",
        )
        active_key = (namespace, task_id)
        active = execution.active_runs.get(active_key)
        if active is not None:
            await self.service.finish_agent_run(
                active.run_id,
                status="failed",
                error=error_payload,
            )
            execution.active_runs.pop(active_key, None)
        if namespace:
            execution.nested_failure_seen.add(namespace[0])
        execution.failure_node = public_node
        execution.failure_error = error_payload
        await self.service.update_status(
            project_id,
            "failed",
            current_node=public_node,
            error=error_payload,
        )
        await self.service.append_event(
            project_id,
            "node.failed",
            node_name=public_node,
            payload={"task_id": task_id, **error_payload},
        )
        await self._append_trace_event(
            project_id,
            "observation",
            task_id=task_id,
            node_name=public_node,
            summary="当前步骤未完成，错误已记录，后续执行已停止。",
            attempt=None if active is None else active.attempt,
            agent_name=None if active is None else active.agent_name,
            tools=None if active is None else active.tools,
            provider=None if active is None else active.provider,
            status="failed",
        )

    async def _start_node(
        self,
        project_id: str,
        namespace: Namespace,
        task_id: str,
        node_name: str,
        data: dict[str, Any],
        execution: ExecutionState,
    ) -> None:
        if node_name in ALL_APPROVAL_NODE_NAMES:
            return
        public_node = self._public_node(node_name)
        execution.failure_node = public_node
        project_status = {
            "video_generation": "generating",
            "video_clone_review": "reviewing",
        }.get(node_name, "running")
        await self.service.update_status(
            project_id,
            project_status,
            current_node=public_node,
        )
        agent_name = AGENT_BY_NODE.get(node_name)
        if agent_name is not None:
            input_data = data.get("input")
            agent_input = None
            persisted_input: Mapping[str, Any] | None = None
            if node_name == "production" and isinstance(input_data, Mapping):
                try:
                    agent_input = project_production_input(input_data)
                    persisted_input = agent_input.model_dump(mode="json")
                except Exception as exc:
                    persisted_input = {
                        "projection_error": {
                            "code": type(exc).__name__.lower()[:100],
                            "message": str(exc)[:1000],
                        }
                    }
            elif isinstance(input_data, Mapping):
                persisted_input = input_data
            if isinstance(input_data, Mapping):
                feedback_by_node = input_data.get("agent_feedback")
                feedback = (
                    feedback_by_node.get(node_name)
                    if isinstance(feedback_by_node, Mapping)
                    else None
                )
                if isinstance(feedback, str) and feedback:
                    persisted_input = dict(persisted_input or {})
                    persisted_input["user_feedback"] = feedback
            run = await self.service.start_agent_run(
                project_id,
                agent_name=agent_name,
                node_name=node_name,
                input_data=persisted_input,
            )
            execution.active_runs[(namespace, task_id)] = ActiveAgentRun(
                run_id=run.id,
                node_name=node_name,
                agent_input=agent_input,
                agent_name=agent_name,
                attempt=run.attempt,
                tools=self._tools_for_node(node_name),
                provider=self._provider_for_node(node_name),
            )
        active = execution.active_runs.get((namespace, task_id))
        await self.service.append_event(
            project_id,
            "node.started",
            node_name=public_node,
            payload={
                "task_id": task_id,
                "agent_name": None if active is None else active.agent_name,
                "attempt": None if active is None else active.attempt,
                "tools": self._tools_for_node(node_name),
                "provider": self._provider_for_node(node_name),
                "summary": self._started_summary(node_name),
            },
        )
        trace_context = {
            "task_id": task_id,
            "node_name": public_node,
            "attempt": None if active is None else active.attempt,
            "agent_name": None if active is None else active.agent_name,
            "tools": self._tools_for_node(node_name),
            "provider": self._provider_for_node(node_name),
            "status": "running",
        }
        await self._append_trace_event(
            project_id,
            "thought",
            summary=self._started_summary(node_name),
            **trace_context,
        )
        await self._append_trace_event(
            project_id,
            "action",
            summary=self._action_summary(node_name),
            **trace_context,
        )

    async def _persist_node_output(
        self,
        project_id: str,
        node_name: str,
        result: dict[str, Any],
    ) -> None:
        for artifact_type, result_key in ARTIFACTS_BY_NODE.get(node_name, ()):
            content = result.get(result_key)
            if isinstance(content, Mapping):
                await self.service.save_artifact(
                    project_id,
                    artifact_type,
                    content,
                )

        if node_name == "research":
            selected_strategy_id = result.get("selected_strategy_id")
            if isinstance(selected_strategy_id, str):
                await self.service.update_status(
                    project_id,
                    "running",
                    selected_strategy_id=selected_strategy_id,
                )

    async def _persist_live_video_status(
        self,
        request: VideoGenerationRequest,
        task: VideoTask,
    ) -> None:
        await self._persist_video_state(
            request.project_id,
            task.model_dump(mode="json"),
            request_data=request,
        )

    async def _persist_video_state(
        self,
        project_id: str,
        task_state: Mapping[str, Any],
        *,
        request_data: VideoGenerationRequest | None = None,
    ) -> None:
        external_task_id = str(task_state["task_id"])
        provider = str(task_state.get("provider", "mock"))
        status = str(task_state["status"])
        error = None
        if task_state.get("error_code") or task_state.get("error_message"):
            error = {
                "code": task_state.get("error_code"),
                "message": task_state.get("error_message"),
            }
        await self.service.create_or_update_video_task(
            project_id,
            provider=provider,
            is_mock=bool(task_state.get("is_mock", provider == "mock")),
            status=status,
            request_data=request_data,
            external_task_id=external_task_id,
            progress=task_state.get("progress"),
            result_url=task_state.get("result_url"),
            error=error,
        )
        await self.service.append_event(
            project_id,
            f"video.{status}",
            node_name="video_generation",
            payload={
                "task_id": external_task_id,
                "provider": provider,
                "is_mock": bool(task_state.get("is_mock", provider == "mock")),
                "progress": task_state.get("progress"),
            },
        )

    async def _complete_job(
        self,
        job: WorkflowJob,
        state: dict[str, Any],
        *,
        pending_approval: dict[str, Any] | None = None,
    ) -> None:
        if pending_approval is not None:
            node_name = str(pending_approval["node_name"])
            await self.service.update_status(
                job.project_id,
                "waiting_approval",
                current_node=node_name,
                error=None,
            )
            await self.service.finish_job(job.id, status="completed")
            await self.service.append_event(
                job.project_id,
                "workflow.waiting_approval",
                node_name=node_name,
                payload={
                    "job_id": job.id,
                    **pending_approval,
                    "tools": self._tools_for_node(node_name),
                    "provider": self._provider_for_node(node_name),
                    "summary": "Agent 已完成本轮产出，等待用户确认或要求重做。",
                },
            )
            return

        if (
            isinstance(state.get("strategies"), dict)
            and not state.get("selected_strategy_id")
            and not isinstance(state.get("production"), dict)
        ):
            await self.service.update_status(
                job.project_id,
                "waiting_strategy",
                current_node="research",
                selected_strategy_id=None,
                error=None,
            )
            await self.service.finish_job(job.id, status="completed")
            await self.service.append_event(
                job.project_id,
                "workflow.waiting_strategy",
                node_name="research",
                payload={"job_id": job.id, "providers": self.provider_names},
            )
            return

        decision = state.get("intent_decision")
        resolved_intent = (
            decision.get("intent") if isinstance(decision, Mapping) else "full_creation"
        )
        if resolved_intent == "brand_packaging":
            packaging = state.get("brand_packaging")
            if not isinstance(packaging, dict):
                raise RuntimeError("Packaging workflow completed without a validated package")
            final_result = {
                "project_id": job.project_id,
                "status": "completed",
                "resolved_intent": resolved_intent,
                "strategy": state.get("strategies", {}),
                "brand_packaging": packaging,
                "copywriting": {},
                "storyboard": {},
                "video_prompt": {},
                "video_task": None,
                "providers": self._providers_from_state(state),
            }
            await self.service.update_status(
                job.project_id,
                "completed",
                current_node=None,
                selected_strategy_id=state.get("selected_strategy_id"),
                resolved_intent=resolved_intent,
                final_result=final_result,
                error=None,
            )
            await self.service.finish_job(job.id, status="completed")
            await self.service.append_event(
                job.project_id,
                "workflow.completed",
                payload={"job_id": job.id, "providers": self._providers_from_state(state)},
            )
            return

        video_task = state.get("video_task")
        if not isinstance(video_task, dict) or video_task.get("status") != "completed":
            raise RuntimeError("Workflow completed without a completed video task")

        direct_video = resolved_intent in {"video_generation", "video_clone"}
        final_result = {
            "project_id": job.project_id,
            "status": "completed",
            "resolved_intent": resolved_intent,
            "strategy": {} if direct_video else state["strategies"],
            "copywriting": {} if direct_video else state["copywriting"],
            "storyboard": {} if direct_video else state["storyboard"],
            "video_prompt": state["video_prompt"],
            "video_task": video_task,
            "video_clone_analysis": state.get("video_clone_analysis", {}),
            "video_clone_mapping": state.get("video_clone_mapping", {}),
            "video_clone_prompt": state.get("video_clone_prompt", {}),
            "video_clone_review": state.get("video_clone_review"),
            "providers": self._providers_from_state(state),
        }
        await self.service.update_status(
            job.project_id,
            "completed",
            current_node=None,
            selected_strategy_id=state.get("selected_strategy_id"),
            resolved_intent=str(resolved_intent),
            final_result=final_result,
            error=None,
        )
        await self.service.finish_job(job.id, status="completed")
        await self.service.append_event(
            job.project_id,
            "workflow.completed",
            payload={"job_id": job.id, "providers": self._providers_from_state(state)},
        )

    async def _fail_job(
        self,
        job: WorkflowJob,
        exc: Exception,
        execution: ExecutionState,
    ) -> None:
        error = execution.failure_error or self._error_payload(
            exc,
            execution.failure_node,
        )
        for active in list(execution.active_runs.values()):
            with suppress(Exception):
                await self.service.finish_agent_run(
                    active.run_id,
                    status="failed",
                    error=error,
                )
        with suppress(Exception):
            await self.service.update_status(
                job.project_id,
                "failed",
                current_node=execution.failure_node,
                error=error,
            )
        with suppress(Exception):
            await self.service.finish_job(
                job.id,
                status="failed",
                last_error=str(exc),
            )
        with suppress(Exception):
            await self.service.append_event(
                job.project_id,
                "workflow.failed",
                payload={"job_id": job.id, **error},
            )
        logger.exception("Workflow job %s failed", job.id, exc_info=exc)

    @staticmethod
    def _initial_state(project: ContentProject) -> dict[str, Any]:
        references = [
            {
                "type": reference.reference_type,
                "id": reference.reference_id,
                "label": reference.label,
                "snapshot": reference.snapshot,
            }
            for reference in sorted(project.references, key=lambda item: item.position)
        ]
        blueprint = next(
            (reference["snapshot"] for reference in references if reference["type"] == "blueprint"),
            None,
        )
        return {
            "project_id": project.id,
            "request_text": project.request_text,
            "references": references,
            "blueprint": blueprint,
            "target_platform": project.target_platform,
            "duration_seconds": project.duration_seconds,
            "aspect_ratio": project.aspect_ratio,
            "requested_mode": project.requested_mode,
            "completed_nodes": [],
            "provider_usage": {},
            "agent_feedback": {},
            "agent_attempts": {},
            "retry_count": 0,
            "errors": [],
        }

    @staticmethod
    def _error_payload(
        error: object,
        node_name: str | None,
        **details: Any,
    ) -> dict[str, Any]:
        message = str(error) or type(error).__name__
        error_details = getattr(error, "details", None)
        if isinstance(error_details, Mapping):
            details = {**error_details, **details}
        code = getattr(error, "code", None)
        return {
            "code": str(code or type(error).__name__.lower())[:100],
            "message": message[:1000],
            "node": node_name,
            "details": {key: value for key, value in details.items() if value is not None},
        }

    @staticmethod
    def _namespace(value: object) -> Namespace:
        if isinstance(value, (list, tuple)):
            return tuple(str(item) for item in value)
        return ()

    @staticmethod
    def _public_node(node_name: str) -> str:
        return node_name

    def _provider_for_node(self, node_name: str) -> str:
        if node_name == "video_generation":
            return self.provider_names["video"]
        if node_name in {"video_clone_analysis", "video_clone_review"}:
            return self.provider_names["video_understanding"]
        if node_name == "research":
            return self.provider_names["llm"]
        return self.provider_names["llm"]

    def _tools_for_node(self, node_name: str) -> list[dict[str, str]]:
        if node_name == "research":
            return [
                {
                    "name": "research_search",
                    "provider": self.provider_names["research"],
                },
                {
                    "name": "structured_generation",
                    "provider": self.provider_names["llm"],
                },
            ]
        if node_name == "video_generation":
            return [
                {
                    "name": "video_generation",
                    "provider": self.provider_names["video"],
                }
            ]
        if node_name in {"video_clone_analysis", "video_clone_review"}:
            return [
                {
                    "name": "video_understanding",
                    "provider": self.provider_names["video_understanding"],
                }
            ]
        return [
            {
                "name": "structured_generation",
                "provider": self.provider_names["llm"],
            }
        ]

    async def _append_trace_event(
        self,
        project_id: str,
        phase: str,
        *,
        task_id: str,
        node_name: str,
        summary: str,
        attempt: int | None = None,
        agent_name: str | None = None,
        tools: list[dict[str, str]] | None = None,
        provider: str | None = None,
        status: str,
    ) -> None:
        """Persist a safe, user-facing execution trace.

        ``thought`` is a concise progress summary authored by the application. It is
        intentionally not a model's hidden reasoning or token-by-token chain of thought.
        """

        await self.service.append_event(
            project_id,
            f"trace.{phase}",
            node_name=node_name,
            payload={
                "phase": phase,
                "task_id": task_id,
                "iteration": attempt or 1,
                "agent_name": agent_name,
                "tools": tools or [],
                "provider": provider or self._provider_for_node(node_name),
                "summary": summary,
                "status": status,
            },
        )

    def _action_summary(self, node_name: str) -> str:
        tools = self._tools_for_node(node_name)
        tool_names = {
            "research_search": "资料检索",
            "structured_generation": "结构化内容生成",
            "video_generation": "视频生成服务",
        }
        display_tools = "、".join(tool_names.get(tool["name"], tool["name"]) for tool in tools)
        if node_name == "video_generation":
            return f"调用{display_tools}并持续同步任务状态。"
        if node_name == "intent_router":
            return "分析请求与素材类型，并选择一条固定执行流程。"
        return f"调用 {self._node_display_name(node_name)}，使用{display_tools}执行当前步骤。"

    @staticmethod
    def _node_display_name(node_name: str) -> str:
        labels = {
            "intent_router": "智能意图路由",
            "image_generation": "图片生成工具",
            "director": "需求导演 Agent",
            "research": "研究策略 Agent",
            "production": "整合制作 Agent",
            "brand_packaging": "一站式包装 Agent",
            "strategy": "内容策划 Agent",
            "production_coordinator": "制作统筹 Agent",
            "copywriting": "营销文案 Agent",
            "storyboard": "分镜设计 Agent",
            "video_prompt": "提示词工程 Agent",
            "reviewer": "质量审核 Agent",
            "video_generation": "视频生成工具",
            "video_clone_analysis": "参考视频解析 Agent",
            "video_clone_mapping": "素材映射 Agent",
            "video_clone_prompt": "复刻提示词 Agent",
            "video_clone_review": "复刻验收 Agent",
        }
        return labels.get(node_name, "当前 Agent")

    @staticmethod
    def _started_summary(node_name: str) -> str:
        summaries = {
            "intent_router": "正在判断最适合当前请求的执行方式。",
            "image_generation": "正在准备图片生成能力。",
            "director": "正在解析需求并生成创意简报。",
            "research": "正在检索资料，并生成研究结论与三套内容策略。",
            "production": "正在一次生成制作计划、文案、分镜和视频提示词。",
            "brand_packaging": "正在把定位、视觉、店铺物料与品牌文案整理成完整包装方案。",
            "strategy": "正在生成并比较内容策略。",
            "production_coordinator": "正在规划内容制作约束与交接。",
            "copywriting": "正在生成标题、口播与行动号召。",
            "storyboard": "正在把文案拆解为连续分镜。",
            "video_prompt": "正在把文案与分镜整理为视频提示词。",
            "reviewer": "正在检查内容一致性与可生成性。",
            "video_generation": "正在调用视频生成工具。",
            "video_clone_analysis": "正在读取视频技术参数并分析关键帧、钩子与镜头结构。",
            "video_clone_mapping": "正在把用户素材映射到每个复刻镜头。",
            "video_clone_prompt": "正在优化逐镜头提示词和生成约束。",
            "video_clone_review": "正在抽取生成视频关键帧并执行复刻验收。",
        }
        return summaries.get(node_name, "正在执行当前步骤。")

    @staticmethod
    def _safe_output_summary(node_name: str, output: Mapping[str, Any]) -> str:
        if node_name == "intent_router":
            labels = {
                "full_creation": "完整 Agent 创作",
                "video_generation": "直接视频生成",
                "image_generation": "图片生成",
                "brand_packaging": "一站式包装服务",
                "video_clone": "视频复刻",
            }
            intent = str(output.get("intent", "full_creation"))
            confidence = output.get("confidence")
            suffix = (
                f"，置信度 {round(float(confidence) * 100)}%"
                if isinstance(confidence, (int, float))
                else ""
            )
            return f"已识别为{labels.get(intent, intent)}{suffix}。"
        if node_name == "director":
            brief = output.get("creative_brief")
            product = brief.get("product") if isinstance(brief, Mapping) else None
            return f"已生成创意简报：{product or '需求结构化完成'}。"
        if node_name == "research":
            research = output.get("research")
            strategies = output.get("strategies")
            insights = research.get("audience_insights") if isinstance(research, Mapping) else None
            sources = research.get("sources") if isinstance(research, Mapping) else None
            options = (
                strategies.get("strategy_options") if isinstance(strategies, Mapping) else None
            )
            return (
                f"已整理 {len(insights) if isinstance(insights, list) else 0} 条受众洞察，"
                f"关联 {len(sources) if isinstance(sources, list) else 0} 个来源，"
                f"并生成 {len(options) if isinstance(options, list) else 0} 个策略方案。"
            )
        if node_name == "production":
            storyboard = output.get("storyboard")
            shots = storyboard.get("shots") if isinstance(storyboard, Mapping) else None
            shot_count = len(shots) if isinstance(shots, list) else 0
            return f"已完成文案、{shot_count} 个分镜和视频提示词。"
        if node_name == "brand_packaging":
            assets = output.get("assets")
            asset_count = len(assets) if isinstance(assets, list) else 0
            return f"已完成品牌定位、视觉系统、{asset_count} 项包装物料与上线计划。"
        if node_name == "strategy":
            options = output.get("strategy_options")
            return (
                f"已生成 {len(options) if isinstance(options, list) else 0} 个策略方案，"
                f"推荐方案为 {output.get('recommended_strategy_id', '未指定')}。"
            )
        if node_name == "copywriting":
            return f"已完成文案《{output.get('title', '未命名')}》。"
        if node_name == "storyboard":
            shots = output.get("shots")
            return f"已生成 {len(shots) if isinstance(shots, list) else 0} 个连续分镜。"
        if node_name == "video_prompt":
            return (
                f"已生成 {output.get('duration_seconds', '目标')} 秒、"
                f"{output.get('aspect_ratio', '指定画幅')} 的视频提示词。"
            )
        if node_name == "reviewer":
            return (
                f"审核结果 {output.get('status', 'unknown')}，"
                f"评分 {output.get('score', '未提供')}。"
            )
        if node_name == "video_clone_analysis":
            shots = output.get("shots")
            return f"已解析视频 DNA 与 {len(shots) if isinstance(shots, list) else 0} 个镜头。"
        if node_name == "video_clone_mapping":
            mappings = output.get("mappings")
            return f"已完成 {len(mappings) if isinstance(mappings, list) else 0} 个镜头的素材映射。"
        if node_name == "video_clone_prompt":
            prompts = output.get("shot_prompts")
            return f"已优化 {len(prompts) if isinstance(prompts, list) else 0} 条逐镜头提示词。"
        if node_name == "video_clone_review":
            return (
                f"复刻验收为 {output.get('status', 'unknown')}，"
                f"评分 {output.get('score', '未提供')}。"
            )
        return "当前步骤已完成并产生结构化结果。"

    @staticmethod
    def _approval_from_interrupts(value: object) -> dict[str, Any] | None:
        if not isinstance(value, (list, tuple)):
            return None
        for item in value:
            interrupt_value = getattr(item, "value", None)
            if interrupt_value is None and isinstance(item, Mapping):
                interrupt_value = item.get("value")
            if not isinstance(interrupt_value, Mapping):
                continue
            if interrupt_value.get("type") != "agent_approval":
                continue
            node_name = interrupt_value.get("node_name")
            agent_name = interrupt_value.get("agent_name")
            if not isinstance(node_name, str) or not isinstance(agent_name, str):
                continue
            return dict(interrupt_value)
        return None

    def _providers_from_state(self, state: Mapping[str, Any]) -> dict[str, str]:
        usage = state.get("provider_usage")
        if not isinstance(usage, Mapping):
            return dict(self.provider_names)

        director = usage.get("director")
        research = usage.get("research")
        video = usage.get("video_generation")
        video_understanding = usage.get("video_clone_review") or usage.get(
            "video_clone_analysis"
        )
        return {
            "llm": self._provider_value(director, "provider", self.provider_names["llm"]),
            "research": self._provider_value(
                research,
                "research_provider",
                self.provider_names["research"],
            ),
            "video": self._provider_value(video, "provider", self.provider_names["video"]),
            "video_understanding": self._provider_value(
                video_understanding,
                "provider",
                self.provider_names["video_understanding"],
            ),
        }

    @staticmethod
    def _provider_value(value: object, key: str, fallback: str) -> str:
        if isinstance(value, Mapping):
            provider = value.get(key)
            if isinstance(provider, str) and provider:
                return provider
        return fallback

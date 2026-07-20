import asyncio

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from jhai_to_c.config import Settings
from jhai_to_c.contracts.director import DirectorOutput
from jhai_to_c.contracts.production import ProductionPackageOutput
from jhai_to_c.contracts.research import ResearchStrategyOutput
from jhai_to_c.db import AgentRun, Artifact, WorkflowJob
from jhai_to_c.main import create_app


@pytest.mark.asyncio
async def test_content_projects_can_be_listed_as_recent_conversations(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'project-history.db'}",
        langgraph_checkpoint_path=str(tmp_path / "project-history-checkpoints.db"),
        llm_provider="mock",
        research_provider="mock",
        video_provider="mock",
        mock_provider_latency_ms=0,
    )
    app = create_app(settings)

    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for title in ("第一条历史对话", "第二条历史对话"):
                response = await client.post(
                    "/api/content-projects",
                    json={"title": title, "request_text": f"{title}的创作需求"},
                )
                assert response.status_code == 201

            history_response = await client.get("/api/content-projects")

    assert history_response.status_code == 200
    history = history_response.json()
    assert [item["title"] for item in history] == ["第二条历史对话", "第一条历史对话"]
    assert set(history[0]) == {
        "id",
        "title",
        "request_text",
        "requested_mode",
        "origin",
        "status",
        "created_at",
        "updated_at",
    }


@pytest.mark.asyncio
async def test_video_workspaces_have_isolated_histories(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'project-origin.db'}",
        langgraph_checkpoint_path=str(tmp_path / "project-origin-checkpoints.db"),
        llm_provider="mock",
        research_provider="mock",
        video_provider="mock",
        mock_provider_latency_ms=0,
    )
    app = create_app(settings)

    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            agent_project = await client.post(
                "/api/content-projects",
                json={
                    "title": "Agent 视频任务",
                    "request_text": "让蓝鲸穿过暴风雨",
                    "requested_mode": "video_generation",
                },
            )
            ai_video_project = await client.post(
                "/api/content-projects",
                json={
                    "title": "AI 视频任务",
                    "request_text": "让产品缓慢旋转",
                    "requested_mode": "video_generation",
                    "origin": "ai_video",
                },
            )
            video_clone_project = await client.post(
                "/api/content-projects",
                json={
                    "title": "视频复刻任务",
                    "request_text": "复刻参考视频的镜头节奏",
                    "origin": "video_clone",
                    "requested_mode": "video_clone",
                },
            )

            agent_history = await client.get("/api/content-projects?origin=agent")
            ai_video_history = await client.get("/api/content-projects?origin=ai_video")
            video_clone_history = await client.get("/api/content-projects?origin=video_clone")

    assert agent_project.status_code == 201
    assert ai_video_project.status_code == 201
    assert video_clone_project.status_code == 201
    assert [item["title"] for item in agent_history.json()] == ["Agent 视频任务"]
    assert [item["title"] for item in ai_video_history.json()] == ["AI 视频任务"]
    assert [item["title"] for item in video_clone_history.json()] == ["视频复刻任务"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("origin", "required_mode"),
    [("ai_video", "video_generation"), ("video_clone", "video_clone")],
)
async def test_video_origins_reject_non_video_workflows(
    tmp_path, origin: str, required_mode: str
) -> None:
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / f'invalid-{origin}-origin.db'}",
        langgraph_checkpoint_path=str(tmp_path / f"invalid-{origin}-origin-checkpoints.db"),
        llm_provider="mock",
        research_provider="mock",
        video_provider="mock",
        mock_provider_latency_ms=0,
    )
    app = create_app(settings)

    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/content-projects",
                json={
                    "title": "错误归类的完整工作流",
                    "request_text": "执行完整 Agent 创作",
                    "requested_mode": "full_creation",
                    "origin": origin,
                },
            )

    assert response.status_code == 422
    assert f"{origin} origin requires requested_mode={required_mode}" in response.text


@pytest.mark.asyncio
async def test_video_clone_runs_and_persists_each_auditable_stage(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'video-clone.db'}",
        langgraph_checkpoint_path=str(tmp_path / "video-clone-checkpoints.db"),
        llm_provider="mock",
        research_provider="mock",
        video_provider="mock",
        mock_provider_latency_ms=0,
    )
    app = create_app(settings)

    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            created_response = await client.post(
                "/api/content-projects",
                json={
                    "title": "咖啡机视频复刻",
                    "request_text": (
                        "复刻强度：平衡复刻\n"
                        "改编目标：换成新品咖啡机"
                    ),
                    "requested_mode": "video_clone",
                    "origin": "video_clone",
                    "duration_seconds": 10,
                    "aspect_ratio": "9:16",
                    "references": [
                        {
                            "type": "reference_video",
                            "id": "reference-video",
                            "label": "@参考.mp4",
                            "snapshot": {"url": "https://mock.local/reference.mp4"},
                        },
                        {
                            "type": "image",
                            "id": "replacement-image",
                            "label": "@咖啡机.png",
                            "snapshot": {"url": "https://mock.local/coffee.png"},
                        },
                    ],
                },
            )
            assert created_response.status_code == 201, created_response.text
            project_id = created_response.json()["id"]
            start_response = await client.post(f"/api/content-projects/{project_id}/start")
            assert start_response.status_code == 202

            for _ in range(250):
                project_response = await client.get(f"/api/content-projects/{project_id}")
                project = project_response.json()
                if project["status"] in {"completed", "failed"}:
                    break
                await asyncio.sleep(0.02)
            else:
                pytest.fail("video clone workflow did not finish")

            assert project["status"] == "completed", project.get("errors")
            assert set(project["artifacts"]) == {
                "video_clone_analysis",
                "video_clone_mapping",
                "video_clone_prompt",
                "video_prompt",
                "video_clone_review",
            }
            assert project["artifacts"]["video_clone_analysis"]["analysis_basis"] == (
                "mock_fixture"
            )
            assert project["artifacts"]["video_clone_review"]["status"] == "pass"

            result_response = await client.get(f"/api/content-projects/{project_id}/result")
            result = result_response.json()
            assert result["resolved_intent"] == "video_clone"
            assert result["video_clone_mapping"]["replacement_reference_ids"] == [
                "replacement-image"
            ]
            assert result["video_task"]["status"] == "completed"

            events_response = await client.get(f"/api/content-projects/{project_id}/events")
            completed = [
                event
                for event in events_response.json()
                if event["event_type"] == "node.completed"
            ]
            assert [event["node_name"] for event in completed] == [
                "intent_router",
                "video_clone_analysis",
                "video_clone_mapping",
                "video_clone_prompt",
                "video_generation",
                "video_clone_review",
            ]
            assert all("output" in event["payload"] for event in completed)


@pytest.mark.asyncio
async def test_auto_mode_routes_direct_video_without_running_content_agents(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'direct-video.db'}",
        langgraph_checkpoint_path=str(tmp_path / "direct-video-checkpoints.db"),
        llm_provider="mock",
        research_provider="mock",
        video_provider="mock",
        mock_provider_latency_ms=0,
    )
    app = create_app(settings)

    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            created_response = await client.post(
                "/api/content-projects",
                json={
                    "title": "图片转视频",
                    "request_text": "让这张图片里的模特缓慢转身并挥手",
                    "requested_mode": "auto",
                    "duration_seconds": 10,
                    "aspect_ratio": "9:16",
                },
            )
            assert created_response.status_code == 201
            project_id = created_response.json()["id"]
            start_response = await client.post(f"/api/content-projects/{project_id}/start")
            assert start_response.status_code == 202

            for _ in range(100):
                project_response = await client.get(f"/api/content-projects/{project_id}")
                project = project_response.json()
                if project["status"] in {"completed", "failed"}:
                    break
                await asyncio.sleep(0.01)
            else:
                pytest.fail("direct video workflow did not finish")

            assert project["status"] == "completed", project.get("errors")
            assert project["resolved_intent"] == "video_generation"
            assert project["artifacts"] == {}
            result = (await client.get(f"/api/content-projects/{project_id}/result")).json()
            assert result["resolved_intent"] == "video_generation"
            assert result["strategy"] == {}
            assert result["copywriting"] == {}
            assert result["storyboard"] == {}
            assert result["video_prompt"]["prompt"] == "让这张图片里的模特缓慢转身并挥手"
            assert result["video_task"]["status"] == "completed"
            events = (await client.get(f"/api/content-projects/{project_id}/events")).json()
            assert [
                event["node_name"]
                for event in events
                if event["event_type"] == "node.completed"
            ] == ["intent_router", "video_generation"]

        async with app.state.database.session_factory() as session:
            agent_run_count = await session.scalar(
                select(func.count()).select_from(AgentRun).where(AgentRun.project_id == project_id)
            )
        assert agent_run_count == 0


@pytest.mark.asyncio
async def test_content_project_full_backend_loop(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'app.db'}",
        langgraph_checkpoint_path=str(tmp_path / "checkpoints.db"),
        llm_provider="mock",
        research_provider="mock",
        video_provider="mock",
        mock_provider_latency_ms=50,
    )
    app = create_app(settings)

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            create_response = await client.post(
                "/api/content-projects",
                json={
                    "title": "气泡水融资 Demo",
                    "request_text": "用年轻、清爽的风格制作一条无糖气泡水营销视频",
                    "references": [
                        {
                            "type": "brand",
                            "id": "brand-demo",
                            "label": "@清爽实验室",
                            "snapshot": {"tone": "年轻、可信"},
                        },
                        {
                            "type": "product",
                            "id": "product-demo",
                            "label": "@无糖气泡水",
                            "snapshot": {"selling_points": ["无糖", "清爽口感"]},
                        },
                        {
                            "type": "reference_video",
                            "id": "video-demo",
                            "label": "@参考视频",
                            "snapshot": {"url": "https://mock.local/reference.mp4"},
                        },
                        {
                            "type": "blueprint",
                            "id": "blueprint-demo",
                            "label": "@案例模板",
                            "snapshot": {"structure": ["hook", "proof", "cta"]},
                        },
                    ],
                    "blueprint_id": "blueprint-demo",
                    "duration_seconds": 20,
                    "aspect_ratio": "9:16",
                },
            )
            assert create_response.status_code == 201
            created = create_response.json()
            project_id = created["id"]
            assert created["status"] == "draft"
            assert created["providers"] == {
                "llm": "mock",
                "research": "mock",
                "video": "mock",
                "video_understanding": "mock-video-understanding",
            }
            assert len(created["references"]) == 4

            not_ready = await client.get(f"/api/content-projects/{project_id}/result")
            assert not_ready.status_code == 409

            start_responses = await asyncio.gather(
                client.post(f"/api/content-projects/{project_id}/start"),
                client.post(f"/api/content-projects/{project_id}/start"),
            )
            assert sorted(response.status_code for response in start_responses) == [202, 409]
            start_response = next(
                response for response in start_responses if response.status_code == 202
            )
            assert start_response.json()["status"] == "pending"
            in_progress = await client.get(f"/api/content-projects/{project_id}")
            assert in_progress.json()["status"] in {
                "running",
                "reviewing",
                "generating",
            }

            async def wait_for_approval(node_name: str) -> dict:
                for _ in range(500):
                    response = await client.get(f"/api/content-projects/{project_id}")
                    assert response.status_code == 200
                    waiting = response.json()
                    if (
                        waiting["status"] == "waiting_approval"
                        and waiting["current_node"] == node_name
                    ):
                        return waiting
                    if waiting["status"] in {"failed", "cancelled"}:
                        pytest.fail(f"workflow stopped before {node_name}: {waiting}")
                    await asyncio.sleep(0.02)
                pytest.fail(f"workflow did not pause after {node_name}")

            async def approve(node_name: str) -> None:
                response = await client.post(
                    f"/api/content-projects/{project_id}/agent-decisions",
                    json={"node_name": node_name, "action": "approve"},
                )
                assert response.status_code == 202, response.text

            waiting_project = await wait_for_approval("production")
            assert set(waiting_project["artifacts"]) == {
                "creative_brief",
                "research",
                "strategy",
                "copywriting",
                "storyboard",
                "video_prompt",
            }
            selected_strategy_id = waiting_project["artifacts"]["strategy"][
                "recommended_strategy_id"
            ]
            assert waiting_project["selected_strategy_id"] == selected_strategy_id
            await approve("production")

            observed_video_statuses: list[str] = []
            for _ in range(250):
                project_response = await client.get(f"/api/content-projects/{project_id}")
                assert project_response.status_code == 200
                polled_project = project_response.json()
                if polled_project["video_task"] is not None:
                    observed_video_statuses.append(polled_project["video_task"]["status"])
                if polled_project["status"] in {"completed", "failed"}:
                    break
                await asyncio.sleep(0.02)
            else:
                pytest.fail("workflow did not finish within the polling window")

            project = project_response.json()
            assert project["status"] == "completed", project.get("errors")
            assert project["selected_strategy_id"] == selected_strategy_id
            assert set(project["artifacts"]) == {
                "creative_brief",
                "research",
                "strategy",
                "copywriting",
                "storyboard",
                "video_prompt",
            }
            creative_brief = project["artifacts"]["creative_brief"]
            assert creative_brief["product"] == "@无糖气泡水"
            assert "@清爽实验室" in creative_brief["must_include"]

            result_response = await client.get(f"/api/content-projects/{project_id}/result")
            assert result_response.status_code == 200
            result = result_response.json()
            assert result["selected_strategy_id"] == selected_strategy_id
            assert result["strategy"]["strategy_options"]
            assert result["copywriting"]["voiceover"]
            assert result["storyboard"]["shots"]
            assert result["video_prompt"]["prompt"]
            assert result["video_task"]["status"] == "completed"
            assert result["video_task"]["provider"] == "mock"
            assert result["video_task"]["is_mock"] is True
            assert "queued" in observed_video_statuses
            assert "processing" in observed_video_statuses
            assert result["providers"] == {
                "llm": "mock",
                "research": "mock",
                "video": "mock",
                "video_understanding": "mock-video-understanding",
            }

            events_response = await client.get(f"/api/content-projects/{project_id}/events")
            assert events_response.status_code == 200
            events = events_response.json()
            completed_nodes = [
                event["node_name"] for event in events if event["event_type"] == "node.completed"
            ]
            assert completed_nodes == [
                "intent_router",
                "director",
                "research",
                "production",
                "video_generation",
            ]
            approval_events = [
                event for event in events if event["event_type"] == "workflow.waiting_approval"
            ]
            assert [event["node_name"] for event in approval_events] == ["production"]
            assert not any(event["event_type"] == "strategy.selected" for event in events)
            production_started = [
                event
                for event in events
                if event["event_type"] == "node.started" and event["node_name"] == "production"
            ]
            assert [event["payload"]["agent_name"] for event in production_started] == [
                "production"
            ]
            assert all(
                {"agent_name", "attempt", "tools", "provider", "summary"} <= event["payload"].keys()
                for event in events
                if event["event_type"] in {"node.started", "node.completed"}
            )
            assert all(
                "output" in event["payload"]
                for event in events
                if event["event_type"] == "node.completed"
            )
            director_completed = next(
                event
                for event in events
                if event["event_type"] == "node.completed" and event["node_name"] == "director"
            )
            assert director_completed["payload"]["output"]["creative_brief"]["product"] == (
                "@无糖气泡水"
            )
            trace_events = [event for event in events if event["event_type"].startswith("trace.")]
            for node_name in completed_nodes:
                node_trace = [event for event in trace_events if event["node_name"] == node_name]
                assert [event["payload"]["phase"] for event in node_trace] == [
                    "thought",
                    "action",
                    "observation",
                ]
            assert all(
                {
                    "phase",
                    "task_id",
                    "iteration",
                    "agent_name",
                    "tools",
                    "provider",
                    "summary",
                    "status",
                }
                <= event["payload"].keys()
                for event in trace_events
            )
            assert all(
                not ({"reasoning", "tokens", "chain_of_thought", "raw"} & event["payload"].keys())
                for event in trace_events
            )
            assert [
                event["event_type"] for event in events if event["event_type"].startswith("video.")
            ] == ["video.queued", "video.processing", "video.completed"]

        async with app.state.database.session_factory() as session:
            agent_runs = list(
                (
                    await session.scalars(
                        select(AgentRun)
                        .where(AgentRun.project_id == project_id)
                        .order_by(AgentRun.created_at)
                    )
                ).all()
            )
            artifact_count = await session.scalar(
                select(func.count()).select_from(Artifact).where(Artifact.project_id == project_id)
            )
            jobs = list(
                (
                    await session.scalars(
                        select(WorkflowJob).where(WorkflowJob.project_id == project_id)
                    )
                ).all()
            )

        assert [run.node_name for run in agent_runs] == [
            "director",
            "research",
            "production",
        ]
        assert [run.agent_name for run in agent_runs] == [
            "director",
            "research",
            "production",
        ]
        assert all(run.status == "completed" for run in agent_runs)
        assert all(run.output_data for run in agent_runs)
        assert all(
            not ({"current_node", "completed_nodes", "provider_usage"} & run.output_data.keys())
            for run in agent_runs
        )
        output_models = {
            "director": DirectorOutput,
            "research": ResearchStrategyOutput,
            "production": ProductionPackageOutput,
        }
        assert all(
            output_models[run.node_name].model_validate(run.output_data) for run in agent_runs
        )
        production_inputs = {
            run.node_name: set(run.input_data)
            for run in agent_runs
            if run.node_name == "production"
        }
        assert production_inputs == {
            "production": {"creative_brief", "selected_strategy", "references"},
        }
        assert artifact_count == 6
        assert [job.job_type for job in jobs] == [
            "run_project",
            "resume_project",
        ]
        assert all(job.resume_payload for job in jobs[1:])
        assert all(job.status == "completed" for job in jobs)

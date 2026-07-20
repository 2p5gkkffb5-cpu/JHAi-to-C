# Database schema

`draft.sql` 仅保留为最初的逻辑草案，不参与数据库升级。正式 Schema 以 Alembic migration 为唯一事实来源：

- `20260716_0001_phase1_schema.py`：项目、引用、Agent Run、Artifact、Event 和 Video Task 基础表；
- `20260716_0002_phase_c_agent_run_identities.py`：Agent Run 身份约束；
- `20260716_0003_agent_approval_and_cancel.py`：审批、取消状态与恢复 payload；
- `20260717_0004_studio_collaboration.py`：Studio Resource 与 Revision；
- `20260717_0005_intent_routing.py`：请求模式与意图路由字段。

开发和 Demo 启动前执行：

```bash
uv run alembic upgrade head
```

业务数据库和 LangGraph checkpoint 使用独立 SQLite 文件，均属于本地运行数据，不提交到 Git。新增或调整字段必须创建新的 Alembic migration，不修改已提交迁移。

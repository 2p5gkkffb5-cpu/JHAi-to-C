# JHAi-to-C API

主应用后端，提供内容项目、Agent 工作流、事件流、审批、取消、结果查询和 Studio 资源 API。

## 启动

从仓库根目录的 `apps/api` 执行：

```bash
set -a
source ../../.env
set +a
uv sync --frozen
uv run alembic upgrade head
uv run uvicorn jhai_to_c.main:app --app-dir src --reload
```

默认地址为 `http://127.0.0.1:8000`，交互文档位于 `/docs`。

## 验证

```bash
uv run ruff check .
uv run pytest
```

## 代码结构

```text
src/jhai_to_c/
├── agents/       # Agent 定义与注册
├── api/          # FastAPI 路由
├── contracts/    # API 与工作流结构化契约
├── db/           # SQLAlchemy 模型和会话
├── prompts/      # 版本化提示词模板
├── providers/    # Mock 与真实 Provider
├── services/     # 业务服务
├── workflow/     # LangGraph 图、节点和状态
├── main.py       # 应用工厂
└── runner.py     # 后台任务、事件与检查点恢复
```

业务数据库迁移位于 `migrations/versions/`。LangGraph checkpoint 使用独立 SQLite 文件；两者都属于本地运行数据，不提交到 Git。

真实 Provider 的凭据只通过仓库根目录 `.env` 或部署环境注入，禁止写入源码、测试 fixture 或日志。

# 开发与提交规范

本项目处于持续开发阶段。提交目标是让任何开发者都能从一个干净 checkout 安装依赖、运行主应用并验证改动。

## 分支与提交

- `master` 保持可构建、可运行；功能和修复通过短生命周期分支开发。
- 分支建议使用 `feature/<name>`、`fix/<name>`、`docs/<name>`。
- Commit 使用简短、单一目的描述，例如 `feat: add provider health check`。
- 不把格式化、无关重命名和功能修改混在同一个提交中。
- 合并前同步目标分支并解决冲突，禁止提交生成产物来“解决”构建问题。

## 代码边界

- 正式前端：`apps/web`。
- 正式后端：`apps/api`。
- 前后端接口、状态和交互必须在同一发布基线中保持一致。
- API 契约、状态枚举、审批行为变化必须同步前端类型、测试和文档。
- 数据库结构只通过 Alembic migration 变更，不直接修改已有迁移。

## 提交内容

应提交：

- 应用源码、迁移、测试、配置样例；
- 运行时确实引用的静态资源；
- 当前有效的 PRD、技术方案和开发说明。

禁止提交：

- `.env`、Token、API Key、真实用户数据；
- 数据库、checkpoint、日志、缓存、依赖目录和构建产物；
- 参考截图、QA 对比图、Playwright 输出；
- 临时计划、Agent 执行记录和已完成阶段报告。

如果新增本地生成文件，应同时更新 `.gitignore`。

## 验收清单

根据改动范围执行：

```bash
# 主前端
cd apps/web
npm test
npm run build

# 后端
cd apps/api
uv run ruff check .
uv run pytest
```

也可以在仓库根目录运行完整检查：

```bash
npm run check
```

GitHub Pull Request 会通过 `.github/workflows/ci.yml` 执行同等范围的前后端检查。CI 失败时不得把变更标记为可合并。

提交前复核：

```bash
git status --short
git diff --check
git diff --stat
```

不得声称未实际运行的验证已经通过。受环境限制无法执行的检查，应在提交说明中明确列出。

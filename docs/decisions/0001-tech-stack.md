# ADR 0001 — 技术栈与基线架构

- 状态：Accepted
- 日期：2026-07-07

## 背景
keeplix 是中国为主的 Agentic GEO 平台。第一原则是**可移交性**：基建要能顺利交给其他工程师/agent 接班。首轮交付端到端行走骨架。已确认：Next.js 前端 + Python 后端、服务交付优先、模型只有部分 key。

## 决策

1. **Monorepo**（`backend/` + `frontend/` + `docs/`）：一次 clone 拿到全栈，降低接手门槛。
2. **后端 FastAPI + SQLModel + Alembic + Pydantic v2**：类型清晰、文档自动生成（OpenAPI）、SQLModel 让「表=模型」，易读易移交。
3. **uv 管依赖 + ruff + mypy + pytest**：现代、快、主流，招人/接手成本低。
4. **前端 Next.js App Router + TS + Tailwind + shadcn/ui + TanStack Query + next-intl**：生态成熟、组件可复制、中文优先 i18n。
5. **PostgreSQL 生产 / SQLite 本地退化**：本地零配置即可跑，CI 无需外部服务。
6. **Provider 抽象（api/browser/stub 三态）**：应对「部分引擎无 API、部分无 key」的现实；stub 保证全链路随时可跑、测试可重放。
7. **Rubric 外置为 YAML**：评分是易变 IP，配置化避免改代码。
8. **自研轻量 Agent/Workflow，不引入私有框架**：`product.md` 原提到的 Hermes/OpenClaw/Pluto 是私有、非可售、阻碍移交，已彻底移除。

## 取舍
- 选 SQLModel 而非裸 SQLAlchemy：牺牲一点灵活度换可读性与移交性。
- 选 uv 而非 poetry/pip-tools：更快、单工具、锁文件清晰。
- 抓取默认 Playwright，但**自动降级 httpx**：保证没装浏览器的机器也能跑骨架。
- 真实引擎首轮只接 1 个（DeepSeek）：验证抽象正确性，其余靠 stub，接入成本已文档化。

## 影响
- 任何新引擎：加 `providers/<engine>.py` + registry 注册。
- 任何评分调整：改 `config/rubric.zh.yaml`。
- 任何新能力：加一个 Agent，编进 Workflow。

# AGENTS.md — 给接手的工程师 / agent

这是 keeplix 的工作约定与「改动落点速查」。**动手前先读 [docs/architecture.md](docs/architecture.md)。**

## 第一原则
**可移交性 > 一切。** 写让下一个人一眼能懂的代码：贴合现有分层、命名、约定。不引入私有/不可售框架。

## 项目速览
- 中文优先、双语。代码标识 `keeplix`。
- 后端 `backend/`（FastAPI · SQLModel · uv），前端 `frontend/`（Next.js · TS）。
- 无 API key 也能全链路跑（stub provider）。别让改动破坏这一点。

## 常见任务 → 落点

| 我要… | 改这里 |
|---|---|
| 加一个 AI 引擎 | `backend/keeplix/providers/<engine>.py` + `providers/registry.py` 注册 + `.env.example` 加 key（见 [docs/citation-engine.md](docs/citation-engine.md) §6） |
| 改评分项/权重/引擎档位 | `backend/keeplix/config/rubric.zh.yaml`（+ 需要新信号时 `engines/scoring/checks.py`，见 [docs/geo-rubric.md](docs/geo-rubric.md)） |
| 加一个 API endpoint | `backend/keeplix/api/` + `schemas/` DTO + `services/` 编排 |
| 加一种自主/半自主能力 | `backend/keeplix/agents/`（继承 `Agent` 基类，编进 `Workflow`） |
| 改数据表 | `backend/keeplix/models/` + 新增 Alembic 迁移（**别改历史迁移**） |
| 改抓取/解析 | `backend/keeplix/engines/analysis/` |

## 约定
- **Provider 三态**：`api`/`browser`/`stub`。新引擎无 key 必须能回退 stub。
- **Rubric 只读配置**：scoring 不硬编码权重。未实现的 check 记 0 分 + `not_implemented`，不得崩。
- **合规红线**：建议层命中刷量/虚假信息模式要置 `compliance_flag`（见 [docs/product.md](docs/product.md) §8）。
- **纯内核**：`engines/` 不依赖 web 框架，保持易测。

## 验证
- 后端：`cd backend && uv run pytest`（stub 让 citation 测试可重放）；`uv run ruff check` + `uv run mypy keeplix`。
- 端到端：README 的冒烟测试要通过。
- 改前跑一遍，改后再跑一遍。

## 别做
- 别硬编码引擎信源偏好（放 `Engine.source_preferences` / rubric）。
- 别让任何改动要求「必须有某个 key 才能跑」。
- 别引入私有框架或不可售依赖。

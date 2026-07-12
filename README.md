# 可见力 · keeplix

**中国为主、兼顾海外的 Agentic GEO（生成式引擎优化）平台** —— 让你的内容被 AI 主动看见、引用、推荐。既提供 GEO 工具，也能给客户交付 GEO 服务。

> 愿景见 [docs/product.md](docs/product.md)。架构见 [docs/architecture.md](docs/architecture.md)。给接手的工程师/agent 看 [AGENTS.md](AGENTS.md)。

## 这是什么

输入一个网址，keeplix 会：
1. 抓取内容 → 按可配置 **rubric** 打 0–100 分（技术/结构/权威/新鲜/引用友好/实体对齐/墙花园存在感），给出可执行优化建议 + Schema JSON-LD。
2. 对已通过真实数据验收的 AI 答案面做 citation 采样，计算品牌可见度 SoV；未接入的引擎仅可作为本地 Stub 演示，不能用于正式报告。

无任何模型 API key 也能**完整跑通**（用确定性 stub provider）。有 key 的引擎自动切真实。

## 5 分钟本地起步

前置：Python 3.12+、[uv](https://docs.astral.sh/uv/)、Node 20+、（可选）[just](https://github.com/casey/just)。

```bash
# 1) 后端
cd backend
uv sync                        # 装依赖
cp .env.example .env           # 配置（不填 key 也能跑，全 stub）
uv run alembic upgrade head    # 建库（默认 SQLite，零外部依赖）
uv run uvicorn keeplix.main:app --reload   # → http://127.0.0.1:8000  (/docs 看 API)

# 2) 前端（另开终端）
cd frontend
npm install
npm run dev                    # → http://127.0.0.1:3000
```

用 `just`（更短）：`just dev`（前后端一起起）、`just test`、`just lint`、`just migrate`。

也可以在项目根目录直接一键启动：

```bash
make dev
```

它会自动应用数据库迁移，同时启动前端与后端；按 `Ctrl+C` 会一起关闭。

## 冒烟测试

```bash
curl -s -X POST http://127.0.0.1:8000/api/analyses \
  -H 'content-type: application/json' \
  -d '{"url":"https://example.com"}' | jq
```
应返回 `total` 分数、`breakdown`、`recommendations`。

## 目录

```
docs/        愿景 + 架构 + 数据模型 + rubric + citation 方法论 + ADR
backend/     FastAPI 后端（keeplix/ 下按层组织，见 architecture.md）
frontend/    Next.js 前端（中文优先，i18n 壳）
```

## 状态

首轮 = **端到端行走骨架**：每层薄但跑通，供后续按图扩展。真实 GEO 数据层是下一阶段的放行条件，完整顺序见 [docs/roadmap.md](docs/roadmap.md)。

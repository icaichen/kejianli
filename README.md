# 可见力 · keeplix

**面向企业品牌团队与咨询公司的 AI 市场情报与 Agentic GEO 平台** —— 研究 AI 如何描述市场、比较品牌并影响选择，让每条结论都能回到真实答案与来源。

> 愿景见 [docs/product.md](docs/product.md)。架构见 [docs/architecture.md](docs/architecture.md)。给接手的工程师/agent 看 [AGENTS.md](AGENTS.md)。

## 这是什么

创建一个客户研究项目后，keeplix 会：
1. 按市场、品类、核心品牌、竞品和研究目标管理固定问题范围。
2. 对已通过真实数据验收的 AI 答案面采样，计算品牌与竞品的答案份额、引用来源和变化，并保存可复查证据。
3. 将竞争差距转成研究洞察和后续行动；网站审计与内容优化作为辅助能力接入同一证据链。

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

当前已跑通企业研究项目、企业问题框架、正式答案面验收、证据仓库、竞品与来源聚合、持续追踪，以及项目内可打印的企业研究报告。真实 Provider 仍需逐答案面人工验收后才能进入正式报告，完整顺序见 [docs/roadmap.md](docs/roadmap.md)。

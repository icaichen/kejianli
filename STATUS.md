# keeplix — Agentic GEO 平台骨架状态

**当前里程碑**：服务交付工作流已跑通 ✅

---

## ✅ 已完成功能

### 1. 核心 GEO 引擎
- **URL 分析**：抓取 + HTML 解析 → 17+ signals（标题、结构、作者、日期...）
- **Rubric 打分**：可配置评分规则（`config/rubric.zh.yaml`）→ 0–100 分
  - 7 维度：technical_crawlability / content_structure / authority_eeat / freshness / citation_friendliness / entity_alignment / walled_garden_presence
  - 支持 engine_overrides（按引擎调权重）
  - Rule check（17 项）+ LLM check（2 项，当前走 heuristic）
- **建议生成**：未达标的 check → 可执行建议清单（按 severity 排序）

### 2. 可见度采样（Citation）
- **多引擎采样**：对 N 个引擎 × M 个 prompt 重复采样
- **SoV 聚合**：entity-SoV（品牌被提及率）+ citation-SoV（内容被引用率）+ avg_rank
- **Stub 模式**：确定性假数据（hash 派生），无需 API key，可测试
- **真实引擎准备就绪**：DeepSeekProvider 已实现，registry 自动切换（填 `.env` 即可）

### 3. 服务交付工作流（Engagement）⭐
**一次完整交付 = Analysis + Recommendation + Citation → Deliverable**

```bash
POST /api/engagements/run
{
  "url": "https://客户首页",
  "brand_name": "客户品牌",
  "engine_ids": ["deepseek", "kimi", "baidu_ernie"],
  "prompts": ["核心问题1", "核心问题2"],
  "brand_domains": ["客户域名"],
  "samples": 5
}
```

**产出**：
- `deliverable_id`（落库，可追溯）
- 完整报告：
  - GEO 总分 + breakdown（7 维度详情）
  - 优化建议清单（按优先级排序，含 JSON-LD）
  - 可见度报告（多引擎 SoV）
  - executive summary（一段话概括）

### 4. Agent 层 + Workflow
- **AnalysisAgent** / **RecommendationAgent** / **CitationAgent**：可复用工作单元
- **Workflow**：顺序编排多个 agent，记录每步产物（便于观测 + 移交）
- 预留「自主循环」扩展点（把现有 agent 编进循环 workflow）

### 5. 数据模型（SQLite + Alembic）
- **entities**: Organization / Client / Project / Page / BrandEntity
- **runs**: AuditRun / CitationRun（跑过的任务）
- **results**: Score / Recommendation / CitationResult / VisibilityScore / **Deliverable**
- Alembic 迁移已生成（`alembic upgrade head` 建表）

### 6. API 路由（FastAPI）
| 端点 | 功能 |
|------|------|
| `POST /api/analyses` | 分析单页 + 建议 |
| `POST /api/citations/run` | 多引擎可见度采样 |
| `POST /api/engagements/run` | **完整服务交付** ⭐ |
| `GET/POST /api/projects` | 项目 CRUD |
| `GET /api/engines` | 列出引擎（标注 stub/真实）|

### 7. 测试覆盖
- **16 tests pass**（ruff + mypy clean）
- `test_scoring.py`（rubric 打分、LLM 判分、engine override）
- `test_citation.py`（stub 确定性、SoV 聚合）
- `test_api.py`（端到端 API）
- `test_engagement.py`（服务交付工作流）✅

---

## 🔧 快速启动

```bash
cd backend
uv sync                          # 装依赖
uv run alembic upgrade head      # 建表
uv run uvicorn keeplix.main:app --reload
# → http://127.0.0.1:8000

# 测试
uv run pytest -q                 # 16 tests
uv run ruff check keeplix tests  # lint
uv run mypy keeplix              # 类型检查

# 一次完整交付
curl -X POST http://127.0.0.1:8000/api/engagements/run \
  -H 'content-type: application/json' \
  -d @examples/engagement-request.json
```

---

## 🚀 接入真实引擎（3 步）

当前所有引擎均走 `StubProvider`（确定性假数据）。要接真实 API：

### 1️⃣ 填 API key
在 `backend/.env`：
```bash
DEEPSEEK_API_KEY=sk-xxx
# Kimi/通义 等类似
```

### 2️⃣ 验证切换
```bash
curl http://127.0.0.1:8000/api/engines
# → "deepseek" 的 "is_stub": false
```

### 3️⃣ 跑真实采样
```bash
curl -X POST http://127.0.0.1:8000/api/citations/run \
  -H 'content-type: application/json' \
  -d '{
    "engine_ids": ["deepseek"],
    "prompts": ["最好的中文GEO工具"],
    "brand_name": "keeplix",
    "samples": 3
  }'
```

---

## 📂 代码结构

```
backend/
├── keeplix/
│   ├── agents/          # AnalysisAgent / RecommendationAgent / CitationAgent + Workflow
│   ├── api/             # FastAPI 路由（analyses/citations/engagements/projects/engines）
│   ├── config/          # rubric.zh.yaml（GEO 评分配置）
│   ├── core/            # config / db / logging
│   ├── engines/         # analysis / scoring / citation / llm_judge
│   ├── models/          # SQLModel 表定义（entities/runs/results）
│   ├── providers/       # 引擎 provider（deepseek/stub/base）
│   ├── schemas/         # Pydantic DTO（请求/响应）
│   └── services/        # 业务编排（analysis/citation/engagement）
├── tests/               # 16 tests, all pass
├── alembic/             # DB 迁移
├── docs/                # citation-engine.md / geo-rubric.md
├── pyproject.toml       # uv 依赖 + lint 配置
└── README.md            # 本文档
```

---

## 📖 文档
- [backend/README.md](backend/README.md) — 后端快速启动 + API 说明
- [backend/docs/citation-engine.md](backend/docs/citation-engine.md) — Citation 设计 + 真实引擎接入
- [backend/docs/geo-rubric.md](backend/docs/geo-rubric.md) — Rubric 配置说明

---

## ⏳ 下一步（可选扩展）

1. **真实 LLM 判分**：`llm_judge.py` 加 DeepSeek/OpenAI 调用（当前走 heuristic）
2. **Playwright 深度抓取**：`uv sync --extra browser` 启用 SSR 页面
3. **监控仪表盘**：前端接 `/api/engagements/run`，渲染交付报告
4. **自动化任务**：定时跑 engagement，追踪客户 SoV 变化
5. **其他引擎**：Kimi / 通义 / 文心 真实 provider（同 DeepSeek 模式）

---

## 🎯 架构特点

- **显式、可组合**：Agent/Workflow 不依赖私有框架，易迁移
- **确定性测试**：StubProvider 确保无 key 时可测、可演示
- **灵活评分**：rubric 全在 YAML，加项 = 在配置加一条 + 注册函数
- **服务交付优先**：Engagement = 完整交付流程，产出 Deliverable（客户报告）
- **可观测**：Workflow 记录每步产物，Agent 日志清晰

---

**当前里程碑 ✅**：
- ✅ 核心 GEO 评分引擎
- ✅ 多引擎可见度采样
- ✅ 服务交付工作流（analysis → recommendation → citation → deliverable）
- ✅ 16 tests, lint/type clean
- ⏳ 真实引擎接入（需填 API key）

**商业就绪度**：
- 可演示完整服务交付流程（stub 模式）
- 填 key 即可切真实引擎
- 数据模型已落库（Deliverable 可追溯）
- API 就绪（前端可接入）

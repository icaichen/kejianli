# keeplix 后端骨架 — 已完成清单

**当前状态**：GEO 分析 + 可见度采样 + 服务交付工作流 均已跑通。
所有核心功能（analysis/scoring/citation/engagement）已实现并测试覆盖。

---

## ✅ 已实现（可直接使用）

### 1. 核心引擎 (`keeplix/engines/`)
- **analysis.py** — URL 抓取（httpx/Playwright 降级）+ HTML 解析 → signals
- **scoring.py** — 可配置 rubric（`config/rubric.zh.yaml`）→ GEO 总分 0–100
- **citation.py** — 多引擎采样聚合 → entity-SoV / citation-SoV
- **llm_judge.py** — LLM 判分基础设施：
  - 无 key 时走确定性 heuristic（`llm_stub`）
  - 有 key 时升级为真实模型判分（预留，待 §3 接入）

### 2. Agent 层 (`keeplix/agents/`)
- **AnalysisAgent** — URL → signals + score
- **RecommendationAgent** — breakdown → 优化建议清单 + Schema JSON-LD
- **CitationAgent** — prompts → SoV 报告
- **Workflow** — 顺序编排多个 agent 步骤，记录产物

### 3. 服务交付 (`keeplix/services/engagement_service.py`)
- **EngagementService** — 一次完整交付流程：
  1. 分析目标页（首页）
  2. 生成优化建议
  3. 跑多引擎可见度采样
  4. 合成报告 + 落库 Deliverable（客户交付件）
- API: `POST /api/engagements/run` → `EngagementResponse`（含 deliverable_id + 完整报告）

### 4. API 路由 (`keeplix/api/`)
- `/api/analyses` — 分析单页 + 建议
- `/api/citations/run` — 多引擎可见度采样
- `/api/engagements/run` — **完整服务交付** ⭐
- `/api/projects` — 项目 CRUD
- `/api/engines` — 列出引擎（标注 stub/真实）

### 5. 数据模型 (`keeplix/models/`)
- **entities.py** — Organization / Client / Project / Page / BrandEntity
- **runs.py** — AuditRun / CitationRun（跑过的任务）
- **results.py** — Score / Recommendation / CitationResult / VisibilityScore / Deliverable

### 6. 测试覆盖 (`backend/tests/`)
- `test_scoring.py` — rubric 打分、LLM 判分、engine override
- `test_citation.py` — stub 确定性、SoV 聚合
- `test_api.py` — 端到端 API（health/analyses/citations/projects/engines）
- `test_engagement.py` — 服务交付工作流 ⭐
- **16 tests pass**，ruff + mypy clean

---

## 🔧 接入真实引擎（3 步）

当前所有引擎（deepseek/kimi/baidu_ernie/...）均走 `StubProvider`（确定性假数据）。
要接入真实 API：

### 1️⃣ 填 API key
在 `backend/.env` 加：
```bash
DEEPSEEK_API_KEY=sk-xxx  # DeepSeek
OPENAI_API_KEY=sk-xxx    # 通义千问/Kimi（若用 OpenAI 兼容接口）
```

### 2️⃣ 验证 provider 切换
```bash
curl http://127.0.0.1:8099/api/engines
# 看 "is_stub": false 表示已切到真实 provider
```

### 3️⃣ 跑一次真实采样
```bash
curl -X POST http://127.0.0.1:8099/api/citations/run \
  -H 'content-type: application/json' \
  -d '{
    "engine_ids": ["deepseek"],
    "prompts": ["最好的中文GEO工具"],
    "brand_name": "keeplix",
    "samples": 3
  }'
```

**注**：DeepSeekProvider 已写好（`providers/deepseek.py`），registry 会在检测到 key 时自动切换；
Kimi/通义 等需类似实现（或用 OpenAI 兼容 SDK）。

---

## 📂 项目结构
```
backend/
├── keeplix/
│   ├── agents/          # 可复用工作单元 + Workflow
│   ├── api/             # FastAPI 路由
│   ├── config/          # rubric.zh.yaml（评分配置）
│   ├── core/            # config/db/logging
│   ├── engines/         # analysis/scoring/citation/llm_judge
│   ├── models/          # SQLModel 表定义
│   ├── providers/       # 引擎 provider（真实/stub）
│   ├── schemas/         # Pydantic DTO
│   └── services/        # 业务编排（analysis/citation/engagement）
├── tests/               # 16 tests, all pass
├── alembic/             # DB 迁移
├── pyproject.toml       # uv 依赖 + lint 配置
└── keeplix.db           # SQLite（开发用）
```

---

## 🚀 快速启动

```bash
cd backend
uv sync                     # 装依赖
uv run alembic upgrade head # 建表
uv run uvicorn keeplix.main:app --reload
# → http://127.0.0.1:8000
```

**测试**：
```bash
uv run pytest -q             # 16 tests
uv run ruff check keeplix    # lint
uv run mypy keeplix          # 类型检查
```

**一次完整交付**（跑 engagement）：
```bash
curl -X POST http://127.0.0.1:8000/api/engagements/run \
  -H 'content-type: application/json' \
  -d '{
    "url": "https://keeplix.com",
    "brand_name": "keeplix",
    "engine_ids": ["deepseek", "kimi"],
    "prompts": ["最好的中文GEO工具", "如何优化AI可见度"],
    "brand_domains": ["keeplix.com"],
    "samples": 3
  }'
# → 返回 deliverable_id + 完整报告（GEO 分数 + 建议 + 可见度）
```

---

## 📝 下一步（可选扩展）

1. **Playwright extras**（SSR 抓取）：`uv sync --extra browser`
2. **真实 LLM 判分**：在 `llm_judge.py` 加调用（DeepSeek/OpenAI SDK）
3. **监控仪表盘**：前端接 `/api/engagements/run`，渲染交付报告
4. **自动化任务**：定时跑 engagement，追踪客户 SoV 变化

---

**当前里程碑**：
✅ 核心 GEO 评分引擎  
✅ 多引擎可见度采样  
✅ 服务交付工作流（analysis → recommendation → citation → deliverable）  
✅ 16 tests, lint/type clean  
⏳ 真实引擎接入（需填 API key）

# keeplix 系统架构

> 面向接手的工程师/agent。读完这份 + [data-model.md](data-model.md) 应能定位任何改动落点。

## 1. 全局视图

```
┌─────────────────────────────────────────────────────────────┐
│  frontend/  Next.js (App Router, TS, Tailwind, shadcn)        │
│  中文优先 + i18n 壳。通过 lib/api.ts (类型化) 调后端 REST。      │
└───────────────┬─────────────────────────────────────────────┘
                │ HTTP/JSON
┌───────────────▼─────────────────────────────────────────────┐
│  backend/  FastAPI (Python, uv)                              │
│                                                              │
│  api/        路由层：projects / analyses / citations          │
│    │  只做 请求校验 + 调 service + 返回 DTO                     │
│  services/   业务编排（薄）：把 engines + agents + db 串起来     │
│    │                                                         │
│  agents/     Agent 基类 + Workflow runner（显式、可移交）       │
│    ├─ AnalysisAgent        URL → score + findings            │
│    ├─ RecommendationAgent  findings → 清单 + JSON-LD          │
│    └─ CitationAgent        prompts → 采样 → SoV               │
│                                                              │
│  engines/    纯计算内核（无 web 依赖，易测）                     │
│    ├─ analysis   抓取(Playwright→httpx 降级) + HTML 结构解析    │
│    ├─ scoring    读 rubric.zh.yaml → 0-100 分 + breakdown     │
│    └─ citation   采样 N 次 → 解析提及/URL → 聚合 SoV           │
│                                                              │
│  providers/  EngineProvider 抽象 + registry                   │
│    ├─ stub       确定性假数据（默认，可重放，无需 key）          │
│    ├─ deepseek   真实 API（示例真实 provider）                 │
│    └─ (browser)  抓取式引擎占位（文心/豆包，后续补齐）           │
│                                                              │
│  models/     SQLModel 实体（见 data-model.md）                 │
│  core/       config / db session / logging                   │
└───────────────┬─────────────────────────────────────────────┘
                │
        ┌───────▼────────┐
        │ PostgreSQL      │  本地零配置可退化 SQLite
        └────────────────┘
```

## 2. 分层职责（改动落点速查）

| 层 | 目录 | 职责 | 什么时候动它 |
|---|---|---|---|
| 路由 | `keeplix/api/` | HTTP 契约、校验、调 service | 加/改 API endpoint |
| DTO | `keeplix/schemas/` | 请求/响应 Pydantic 模型 | 改 API 输入输出形状 |
| 编排 | `keeplix/services/` | 串 engines/agents/db 的业务流 | 改「一次分析/采样做哪些步骤」 |
| Agent | `keeplix/agents/` | 有明确 I/O 的可复用工作单元 | 加一种自主/半自主能力 |
| 内核 | `keeplix/engines/` | 纯计算（抓取/评分/采样聚合） | 改算法、加解析规则 |
| Provider | `keeplix/providers/` | 对接某个 LLM/AI 引擎 | **加一个新引擎** |
| 配置 | `keeplix/config/` | rubric 等外置配置 | **改评分项/权重/引擎档位** |
| 模型 | `keeplix/models/` | 数据表 | 加/改持久化字段 |

## 3. 三个决定「可移交性」的抽象

### 3.1 EngineProvider（对接引擎）
所有 AI 引擎统一到一个接口，屏蔽「有的有 API、有的只能抓浏览器、有的还没接」：

```python
class EngineProvider(Protocol):
    engine_id: str                                  # "deepseek" / "baidu_ernie" ...
    acquisition: Literal["api", "browser", "stub"]  # 数据获取方式
    async def query(self, prompt: str) -> EngineResponse
    # EngineResponse = answer_text + cited_sources[] + raw
```

- 通过 `providers/registry.py` 按 `engine_id` 装配。
- 没配 key 的引擎自动落到 `StubProvider`（确定性输出，全链路可跑、测试可重放）。
- **加新引擎 = 新增一个 provider 文件 + 在 registry 注册**，其余层不动。详见 [citation-engine.md](citation-engine.md)。

### 3.2 可配置 Rubric（评分）
评分项/权重/判定方式/按引擎档位全在 `config/rubric.zh.yaml`，`engines/scoring` 只读它。**模型或信源偏好变了，改 YAML 不改代码**。见 [geo-rubric.md](geo-rubric.md)。

### 3.3 Agent / Workflow（编排）
轻量、显式、无私有框架依赖：
- `Agent` 基类：`async run(input) -> output`，input/output 是 Pydantic schema。
- `Workflow`：把多个 agent 步骤按顺序/并行组合，记录每步产物，便于观测与移交。
- 后续的「自主循环」只是把现有 agent 编进一个循环 workflow，不需要重写内核。

## 4. 一次请求的数据流（竖切片）

**`POST /analyses { url }`**：
```
api.analyses → services.analysis_service
  → AnalysisAgent
      → engines.analysis.fetch(url)     # Playwright 或 httpx 降级
      → engines.analysis.parse(html)    # 结构/权威/新鲜度信号
      → engines.scoring.score(signals, rubric)  # 0-100 + breakdown
  → RecommendationAgent(findings)        # 可执行清单 + JSON-LD + 合规红线
  → db 落库 (Page, AuditRun, Score, Recommendation)
  → 返回 AnalysisResultDTO
```

**`POST /citations/run { project_id, engine_ids, prompts, samples }`**：
```
api.citations → services.citation_service
  → CitationAgent
      → 对每个 engine：providers.registry.get(engine_id)
      → engines.citation.sample(provider, prompt, N)  # 采样 N 次
      → 解析 brand_mentioned / rank / cited_urls / sentiment
      → 聚合 entity-SoV & citation-SoV
  → db 落库 (CitationRun, CitationResult, VisibilityScore)
  → 返回 SoVReportDTO
```

## 5. 技术选型与「为什么」

选型均以**主流、易招人、易移交**为准（决策记录见 [decisions/](decisions/)）：

- **后端 FastAPI + SQLModel + Alembic + Pydantic v2 + uv + ruff + mypy + pytest**
- **前端 Next.js App Router + TS + Tailwind + shadcn/ui + TanStack Query + next-intl（zh 默认）**
- **DB PostgreSQL（docker-compose），本地退化 SQLite**
- **抓取 Playwright（SSR）+ BeautifulSoup**；缺 Playwright 环境时 `engines.analysis` 自动降级到 httpx 抓静态 HTML，保证骨架任何机器可跑。
- **LLM 接入 httpx**，不绑定单一 SDK，便于多引擎并存。

## 6. 环境与配置

所有密钥/开关走环境变量（`core/config.py` 用 pydantic-settings 读 `.env`）。见 `.env.example`。没有任何 key 时系统仍完整可跑（全 stub）。

## 7. 本轮边界（未做，但已留位）

- 鉴权/多租户 UI/计费：`Organization` 实体已建，UI 单租户。
- 自主定时循环、微信集成、topical cluster、Lighthouse 深度审计：留接口/占位。
- 真实引擎仅接 1 个（DeepSeek 示例），其余 stub；接入步骤见 citation-engine.md。

# Citation 引擎设计 + 接入指南

## 概述
Citation 引擎负责「引用采样 + 可见度聚合」：对多个 AI 引擎（DeepSeek/Kimi/文心/...）重复采样同一组 prompt，解析每次回答，统计品牌被提及率（entity-SoV）和内容被引用率（citation-SoV）。

**核心产物**：`SoVReport`（一个引擎的 SoV + 所有样本详情）

---

## 实现层次

```
CitationAgent (agents/)
  ↓
run_sampling (engines/citation.py)
  ↓ 调 provider.query() N 次
EngineProvider (providers/base.py)
  ↓
DeepSeekProvider / StubProvider (providers/)
```

### 骨架阶段：StubProvider（已完成 ✅）
- **确定性**：相同 (engine_id, prompt, brand_name) → 相同回答（hash 派生）
- **可测**：pytest 里验证 SoV 计算正确，不需真实 API key
- **切换**：registry 根据 env 有无 key 自动选 stub/真实

---

## §1 数据模型

### EngineResponse（单次查询结果）
```python
@dataclass
class EngineResponse:
    answer_text: str
    cited_sources: list[CitedSource]
```

### SampleParse（解析后的样本）
```python
@dataclass
class SampleParse:
    prompt: str
    sample_index: int
    answer_text: str
    brand_mentioned: bool       # 品牌被点名
    cited_urls: list[str]
    own_domain_cited: bool      # 内容被引用
    rank: int | None            # 品牌首次出现位置（粗分 1/2/3）
```

### SoVReport（一个引擎的聚合报告）
```python
@dataclass
class SoVReport:
    engine_id: str
    entity_sov: float       # [0,1]：N 次采样中品牌被提及的比例
    citation_sov: float     # [0,1]：N 次采样中内容被引用的比例
    avg_rank: float | None  # 品牌平均排名
    sample_size: int
    samples: list[SampleParse]
```

---

## §2 采样流程（`run_sampling`）

```python
async def run_sampling(
    provider: EngineProvider,
    prompts: list[str],
    brand_name: str,
    aliases: list[str] | None = None,
    brand_domains: list[str] | None = None,
    samples: int = 3,
) -> SoVReport
```

**步骤**：
1. 对每个 prompt 采样 `samples` 次（默认 3）
2. 每次调 `provider.query(prompt)` → `EngineResponse`
3. 解析成 `SampleParse`：检测品牌点名、域名引用
4. 聚合 → `entity_sov` / `citation_sov` / `avg_rank`

**关键设计**：
- `brand_name` + `aliases`：多名称匹配（"keeplix" / "可见力" 都算）
- `brand_domains`：["keeplix.com"] → 判断 cited_urls 是否自家内容
- `rank`：首次出现在回答前 1/3=1、中段=2、后段=3（粗略位置）

---

## §3 Provider 接口

### 基类（base.py）
```python
class EngineProvider(Protocol):
    engine_id: str
    acquisition: Literal["api", "browser", "stub"]

    async def query(self, prompt: str) -> EngineResponse: ...
```

### StubProvider（已完成 ✅）
- 用 `hash(engine_id + prompt + brand_name)` 决定是否提及
- 确定性、可复现、无 API 开销
- **用途**：测试、骨架阶段、演示

### 真实 Provider（DeepSeekProvider）
```python
class DeepSeekProvider:
    engine_id = "deepseek"
    acquisition: Literal["api", "browser", "stub"] = "api"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(...)

    async def query(self, prompt: str) -> EngineResponse:
        # 调 DeepSeek API
        # 解析 citations（如果有）
        # 返回 EngineResponse
```

---

## §4 Registry + 自动切换（已完成 ✅）

`providers/registry.py` 根据 env 自动选 provider：

```python
def get_provider(engine_id: str, ...) -> EngineProvider:
    settings = get_settings()
    if engine_id == "deepseek" and settings.deepseek_api_key:
        return DeepSeekProvider(settings.deepseek_api_key)
    # 其他引擎类似
    return StubProvider(engine_id, ...)
```

**好处**：
- 无 key 时自动降级到 stub（不崩）
- 有 key 时自动升级真实引擎（不改代码）
- 测试时用 stub（快、确定性、不花钱）

---

## §5 数据库落盘（已完成 ✅）

### CitationRun（跑过的采样任务）
```python
class CitationRun(SQLModel, table=True):
    id: str
    project_id: str
    engine_id: str
    samples: int        # 每 prompt 采样次数
    status: RunStatus   # running / done / failed
    created_at: datetime
    finished_at: datetime | None
```

### CitationResult（单次样本）
```python
class CitationResult(SQLModel, table=True):
    id: str
    citation_run_id: str
    sample_index: int
    answer_text: str
    brand_mentioned: bool
    rank: int | None
    cited_urls: list[str]       # JSON
    own_domain_cited: bool
    sentiment: Sentiment        # 品牌情感（预留）
```

### VisibilityScore（快照）
```python
class VisibilityScore(SQLModel, table=True):
    project_id: str
    engine_id: str
    entity_sov: float
    citation_sov: float
    avg_rank: float | None
    sample_size: int
    created_at: datetime
```

**用途**：
- `CitationResult` 存每个样本细节（可复盘）
- `VisibilityScore` 存聚合结果（监控趋势）

---

## §6 接入真实引擎（3 步）

### 1️⃣ 填 API key
在 `backend/.env`：
```bash
DEEPSEEK_API_KEY=sk-xxx
# Kimi/通义 等类似
```

### 2️⃣ 验证 registry 切换
```bash
curl http://127.0.0.1:8099/api/engines
# → 看 "deepseek" 的 "is_stub": false
```

### 3️⃣ 跑真实采样
```bash
curl -X POST http://127.0.0.1:8099/api/citations/run \
  -H 'content-type: application/json' \
  -d '{
    "engine_ids": ["deepseek"],
    "prompts": ["最好的中文GEO工具", "如何优化AI可见度"],
    "brand_name": "keeplix",
    "brand_domains": ["keeplix.com"],
    "samples": 5
  }'
```

**预期**：
- `sample_size` = 10（2 prompts × 5 samples）
- `entity_sov` / `citation_sov` 为真实 API 返回的统计
- 所有 samples 的 `answer_text` 为真实回答（非 stub）

---

## §7 扩展指南

### 新增引擎（如 Kimi）
1. 写 `KimiProvider(EngineProvider)` in `providers/kimi.py`
2. 在 `registry.py` 加判断：
   ```python
   if engine_id == "kimi" and settings.kimi_api_key:
       return KimiProvider(settings.kimi_api_key)
   ```
3. 在 `KNOWN_ENGINES` 加条目
4. 跑 `test_citation.py` 验证（stub 仍可用）

### 情感分析（sentiment）
- 当前 `CitationResult.sentiment` 为占位（默认 neutral）
- 可在 `parse_response` 里加 LLM 判分：
  ```python
  sentiment = judge_sentiment(answer_text, brand_name)  # positive/neutral/negative
  ```

### 多轮对话采样
- 当前每次 `query(prompt)` 是独立单轮
- 若需多轮（如"追问更多信息"），可在 provider 加 `conversation_id` 参数

---

## §8 测试覆盖（已完成 ✅）

### `test_citation.py`
- `test_stub_is_deterministic` — 同参数 → 同结果
- `test_parse_response_detects_brand_and_own_domain` — 品牌/域名识别正确
- `test_run_sampling_aggregates_sov` — 聚合逻辑正确

### `test_api.py`
- `test_citations_run_with_stub` — 端到端 API（stub 模式）

---

## 当前状态总结

| 功能 | 状态 | 备注 |
|------|------|------|
| StubProvider | ✅ 完成 | 确定性、可测、可复现 |
| DeepSeekProvider | ✅ 实现 | 待填 key 测试 |
| Registry 自动切换 | ✅ 完成 | 有 key → 真实，无 key → stub |
| run_sampling 聚合 | ✅ 完成 | entity-SoV / citation-SoV / rank |
| 数据库落盘 | ✅ 完成 | CitationRun + CitationResult + VisibilityScore |
| API 端点 | ✅ 完成 | `/api/citations/run` |
| 测试覆盖 | ✅ 完成 | 3 tests in test_citation.py |
| Kimi/通义/文心 | ⏳ 待实现 | 同 DeepSeek 模式 |

**下一步**：填 `DEEPSEEK_API_KEY` 到 `.env`，跑一次真实采样验证接入路径。

# Citation 引擎与 Provider 矩阵

> 这是产品命脉。核心事实：**AI 回答非确定性，没有「AI 版 Search Console」。citation 只能靠采样统计。**

## 1. 方法论：采样统计

对每个「引擎 × prompt」组合，**重复采样 N 次**，解析每次回答，聚合成频率指标：

```
for prompt in prompt_set:          # 50–200 个代表性 prompt（骨架阶段可少）
  for i in range(N):               # N 次采样（默认 3–5，配置项）
    resp = provider.query(prompt)
    parse: brand_mentioned? rank? cited_urls? own_domain_cited? sentiment?
aggregate:
  entity_sov    = mean(brand_mentioned)      # 品牌被点名率
  citation_sov  = mean(own_domain_cited)     # 内容被引用率
  avg_rank      = mean(rank | mentioned)
```

- **N 与判定策略是配置项**（`core/config.py` / 请求参数）。
- **prompt 集质量 = 测量质量**：覆盖 branded / category / problem / comparison 四类意图。prompt 集烂，公式再对也没用。

## 2. 两种 SoV（不要混）

| 指标 | 定义 | 何时用 |
|---|---|---|
| **entity-SoV** | 回答里品牌被**点名/推荐**的样本占比 | 中国 B2B 首选，直接对应「有没有被推荐」 |
| **citation-SoV** | 回答里**你的 URL 被当来源引用**的样本占比 | 对用户常不可见，但影响答案；做内容资产分析用 |

竞争视角：把竞品名一并统计，得到相对 SoV（你 vs 竞品）。

## 3. Provider 抽象：三种数据获取方式

不同引擎能拿到 citation 的方式不同，统一到一个接口（`providers/base.py`）：

```python
@dataclass
class CitedSource:
    url: str
    title: str | None

@dataclass
class EngineResponse:
    answer_text: str
    cited_sources: list[CitedSource]
    raw: dict            # 原始响应，便于排查

class EngineProvider(Protocol):
    engine_id: str
    acquisition: Literal["api", "browser", "stub"]
    async def query(self, prompt: str) -> EngineResponse
```

### acquisition 三态
| 值 | 含义 | 例子 |
|---|---|---|
| `api` | 官方 API；只有经验证的联网/引用模式才可用于正式 Citation | 普通 Chat API 或联网/搜索 API |
| `browser` | 无合适 API，需真实浏览器抓答案（Playwright） | 百度文心检索结果、豆包 C 端 |
| `stub` | 未接入/无 key，返回**确定性假数据** | 默认兜底，保证全链路可跑 |

## 4. 各引擎获取矩阵（现状与路线）

| engine_id | 名称 | 建议 acquisition | citation 可得性 | 本轮状态 |
|---|---|---|---|---|
| `deepseek` | DeepSeek | api | 当前仅普通 Chat 回答；未验证联网引用 | **真实品牌认知采样，不可作 Citation 追踪** |
| `qwen` | 千问联网检索 Agent | api | 强制联网、返回引用，原始 SSE 证据可保存 | **真实答案面（已验收）** |
| `kimi` | Kimi K2.6 官方 `$web_search` | api | 真实联网回答与来源 URL；两阶段原始证据可保存 | **真实答案面（已验收）** |
| `baidu_ernie` | 百度智能搜索生成 | api | 返回结构化 `references` | **真实答案面（已验收）** |
| `doubao` | 豆包 | browser/api | C 端偏抓取 | stub |
| `yuanbao` | 腾讯元宝 | browser | 微信生态 | stub |
| `chatgpt` | ChatGPT | api（需代理） | search 模式返回来源 | stub |
| `perplexity` | Perplexity | api | 原生带 citation | stub |

> 千问、Kimi、百度智能搜索生成已通过真实联网及来源保存验收。真实连通不等于有 GEO 报告资格：必须通过 [roadmap.md](roadmap.md) 的真实答案面、证据保存和人工对照验收。**接一个新引擎不仅要改 providers/ + registry，还必须完成该验收。**

## 5. StubProvider 为什么重要

- 无任何 key 也能跑通全链路、录 demo、写可重放测试。
- 输出**确定性**（同 prompt 同结果）：CI 里 citation 测试稳定不 flaky。
- 假数据带真实结构（answer + cited_sources + 品牌提及），前端/聚合逻辑照真实形状开发。

## 6. 如何接入一个真实引擎（给接手者，5 步）

1. 新建 `providers/<engine>.py`，实现 `EngineProvider.query()`：调 API 或 Playwright，映射到 `EngineResponse`。
2. 在 `providers/registry.py` 注册：有 key → 用真实，无 key → 回退 stub。
3. 在 `Engine` 目录表补 `acquisition` 与 `source_preferences`。
4. 在 `.env.example` 加对应 `KEEPLIX_<ENGINE>_API_KEY`。
5. 加 provider 测试（真实的可用 VCR/录制；stub 的直接断言确定性输出）。

## 7. 成本与合规

- **成本**：采样是主要成本项 → 缓存相同 prompt 的近期结果、批量、简单任务用轻量模型（`core/config.py` 可配模型分级）。
- **合规**：采样只做**观测**，不伪造/注入内容到引擎。优化建议侧遵守真实信息红线（见 [product.md](product.md) §8）。

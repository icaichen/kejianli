# 术语表

| 术语 | 英文 | 含义 |
|---|---|---|
| GEO | Generative Engine Optimization | 生成式引擎优化：让内容被 AI 引擎引用/推荐 |
| SEO | Search Engine Optimization | 传统搜索引擎优化（排名/点击） |
| citation | citation | AI 回答中对某来源/品牌的一次具名引用 |
| entity-SoV | entity Share of Voice | 品牌在 AI 回答中被**点名/推荐**的样本占比 |
| citation-SoV | citation Share of Voice | 你的**内容 URL 被当来源引用**的样本占比 |
| SoV | Share of Voice | 声量占比，AI 回答中你 vs 竞品的提及份额 |
| 采样 | sampling | 因 AI 回答非确定性，对同一 prompt 重复查询取统计 |
| provider | EngineProvider | 对接某个 AI 引擎的适配器（api/browser/stub） |
| acquisition | — | 引擎数据获取方式：api / browser / stub |
| rubric | scoring rubric | 可配置的 GEO 评分标准（`rubric.zh.yaml`） |
| E-E-A-T | Experience, Expertise, Authoritativeness, Trust | 权威性信号 |
| 墙花园 | walled garden | 封闭内容平台（知乎/微信公号/百家号/抖音等），国产引擎信源偏好高 |
| fan-out queries | — | 一个主问题衍生的子问题集，覆盖它们利于被引用 |
| dogfooding | — | 用产品优化/推广产品自身 |
| stub | — | 无 key 时的确定性假 provider，保证全链路可跑 |

## 引擎 id 约定（代码中使用）
`deepseek` · `qwen`(通义千问) · `kimi` · `baidu_ernie`(文心) · `doubao`(豆包) · `yuanbao`(元宝) · `chatgpt` · `perplexity`

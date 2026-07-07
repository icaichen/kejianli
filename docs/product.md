# 可见力 / keeplix —— 产品愿景

> 文档修订：rev 2（2026-07-07）
> 定位：中国 indie dev 友好的 **Agentic GEO（生成式引擎优化）平台**，中文优先、双语界面，既提供工具也交付服务。
> 本文件是**愿景文档**，只讲「我们要做什么、为什么」。工程实现见 [architecture.md](architecture.md)、[data-model.md](data-model.md)。

---

## 1. 一句话

**让你的内容被 AI 主动看见、引用、推荐 —— 自助、自动化、懂中文、支持百度与国产模型。**

- 中文名：可见力 · 英文/代码标识：**keeplix**
- Slogan：Agentic GEO，让中国内容被 AI 看见。

---

## 2. 背景：GEO 是什么，为什么现在做

**GEO（Generative Engine Optimization，生成式引擎优化）**：针对 ChatGPT、Claude、Perplexity、以及国内的百度文心、豆包、Kimi、通义千问、DeepSeek、腾讯元宝等生成式引擎，优化内容，让品牌/产品被 AI **引用、总结、推荐**。

- **和 SEO 的关系**：GEO 是 SEO 在 AI 时代的延伸，不是取代。SEO 赢的是「排名」（用户要点链接跳转）；GEO 赢的是「**citation**」——AI 生成答案里对你的一次具名引用，用户在对话内直接接收。
- **测量差异**：SEO 看排名/流量；GEO 看 citation 率、AI 回答中的品牌可见度（Share of Voice）、情感倾向、AI 引荐流量。
- **学术根基**：GEO 概念由 Princeton / Georgia Tech / IIT Delhi 团队在 KDD 2024 首次系统定义——通过结构化内容与信任信号，可让品牌成为 LLM 生成答案的优先引用源。

## 3. 市场：机会在「工具层」，尤其自助 + agentic

- **中国增长迅猛**：GEO 服务市场 2025 起同比高速增长（艾瑞口径 200%+），2026 进入商业化加速期，已有专著、行业公约、信通院/网信办相关规范。
- **服务商多、工具少**：国内以「代做」的服务商为主（围绕百度生态 + 国产大模型做内容优化、监控、对赌）。**自助式、agentic、低成本、indie 友好的 SaaS 工具明显欠缺**——这是最大机会点。
- **全球工具对中国用户有摩擦**：英文界面、价格偏高、缺百度专项、prompt 不适配中文内容、需 VPN。
- **中国生态是碎片化的**：不存在单一引擎可优化。各引擎信源偏好差异极大（见下），必须**按引擎分档**优化，这是本地化工具的护城河。

### 各引擎信源偏好（决定优化打法与 rubric）

| 引擎 | 主导信源偏好 | 备注 |
|---|---|---|
| 百度文心 ERNIE | 百度生态（百家号/百科/知道/文库）、知乎 | 更像 Google AI Overviews，检索强绑定 |
| 豆包 Doubao | 抖音/今日头条/搜狐号/网易号、小红书、B站、微博热搜 | 字节内容宇宙，偏 C 端/消费 |
| DeepSeek | 百度百科、淘宝、网易、腾讯；财经偏 Wind/研报 | 无自建内容生态 |
| Kimi | 中科院文献、国际会议论文、企业报告 | 长文档强，引用链接最精准 |
| 通义千问 Qwen | 各大新闻媒体 + 自媒体（网易号/企鹅号/搜狐/新浪财经） | API 联网性价比高 |
| 腾讯元宝 Yuanbao | 微信生态 | 后续接入 |

> 来源偏好会随模型更新变化，所以在产品里**以可配置数据存在**（见 [citation-engine.md](citation-engine.md)、[geo-rubric.md](geo-rubric.md)），不硬编码。

## 4. 目标用户

- **Primary**：中国 indie dev、内容创作者、工具/SaaS 开发者、中小团队；以及给这些客户**交付 GEO 服务的 agency/顾问**（我们首要服务的业务线）。
- **Secondary**：语言学习、edtech、生产力工具垂直创作者。
- **Later**：想进入中文内容市场的全球 indie dev。

## 5. 价值主张与差异化

**核心价值**：全球工具贵/不适配、国内服务商贵/不自助、自己手动做太耗时 —— keeplix 用「懂中文 + 支持百度国产 + agentic 自主 + indie 友好定价」一次解决。

**差异化亮点**：
1. 中文内容深度优化（语义、表达习惯、实体定义）。
2. 百度/国产模型**专项 rubric 与 citation 模拟**（按引擎分档）。
3. **Agentic 自主循环**：扫描 → 分析差距 → 生成优化 → 建议更新 → 重新监控。
4. Indie 友好定价 + 轻量自助。
5. **产品自己推广自己（Dogfooding）**：用 keeplix 优化自身落地页/博客/帖文，公开 before/after citation 数据——最强 credibility。

## 6. 产品能力（愿景全景，非本轮范围）

> 本轮工程实现的范围与边界，以 [architecture.md](architecture.md) 和实施计划为准。这里是完整愿景。

- **分析器**：技术审计（crawlability/robots/SSR/CWV）+ 内容结构评分 + 权威信号检测 + 中文语义分析。
- **GEO 评分系统**：0–100 分 + 分项 breakdown，按引擎分档（百度/国产专项 + 全球通用）。见 [geo-rubric.md](geo-rubric.md)。
- **优化建议 + 可执行清单**：结构重构、Schema JSON-LD 自动生成、标题/开头答案改写、fan-out 子问题覆盖。
- **多模型 Citation 模拟与监控**：多引擎采样，输出 entity-SoV / citation-SoV 与历史趋势。见 [citation-engine.md](citation-engine.md)。
- **内容生成**：LLM 驱动优化生成（带 diff、支持中文）。
- **自推广模块**：一键为产品自身生成优化内容并追踪自身 citation 变化。
- **Agentic 循环**：定期自主扫描→优化→监控；topical cluster 规划器；外部 mention 发现；微信生态集成（后期）。

## 7. 商业化与 GTM（方向，非本轮）

- **两条业务线**：① 给客户**交付 GEO 服务**（agency 工作流，首要）；② **自助 SaaS 工具**（后置）。
- **定价（indie 友好）**：Freemium 基础分析免费；Starter ¥29–49/月；Pro ¥99–199/月；后期企业/白标。
- **渠道**：X 中文 tech/indie 圈、V2EX、少数派、即刻、微信生态、indie hacker 社区；内容营销用产品自产 GEO 内容反哺。

## 8. 合规红线（硬约束，写进产品逻辑）

依据《生成式人工智能服务管理暂行办法》：GEO 优化必须基于**真实、可溯源**的信息。产品在建议层内建红线：
- 拒绝关键词堆砌、批量低质刷量、虚假信息（AI 会识别不自然内容并降权，且违规）。
- 不做「包首位/100% 收录」绝对承诺。
- 明确用户内容所有权与数据政策。

## 9. 风险与应对

| 风险 | 应对 |
|---|---|
| 模型/信源偏好变化 | rubric 与信源偏好**可配置**，持续更新机制 |
| citation 无法直接观测 | 采样统计方法论（多次采样取频率/置信区间），见 citation-engine.md |
| API 成本 | 缓存、批量、模型分级（简单任务用轻量模型） |
| 数据获取（部分引擎无 API） | Provider 抽象：api / browser / stub 三态 |
| 合规 | 真实信息红线 + 数据脱敏 + 内容所有权 |
| 竞争 | 专注中国 niche + agentic 差异化 + 快速迭代 + dogfooding |

---

### 术语与实现细节
- 名词解释见 [glossary.md](glossary.md)
- 系统架构见 [architecture.md](architecture.md)
- 数据模型见 [data-model.md](data-model.md)
- 评分标准见 [geo-rubric.md](geo-rubric.md)
- Citation 方法论见 [citation-engine.md](citation-engine.md)

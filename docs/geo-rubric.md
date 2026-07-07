# GEO 评分 Rubric

> 评分是产品核心 IP。**判定逻辑与配分全在 `backend/keeplix/config/rubric.zh.yaml`**，`engines/scoring` 只读它。改评分 = 改 YAML，不改代码。

## 设计原则

1. **可配置**：模型/信源偏好会变，rubric 以数据存在。
2. **按引擎分档**：通用基线 + 各引擎 `override`（权重或阈值）。例如「墙花园平台存在感」对文心权重高，对 Kimi 低（Kimi 偏学术）。
3. **判定分两类**：`rule`（确定性、可离线、无成本）与 `llm`（需模型、语义判断、有成本）。骨架阶段优先 `rule`，`llm` 项留位。
4. **可解释**：每项输出 `score / weight / evidence`，直接映射到建议。
5. **合规内建**：命中刷量/虚假信息模式的项，产出 `compliance_flag`。

## 分项（7 维，通用基线）

| 维度 dimension | 权重(基线) | 判定 | 说明 |
|---|---|---|---|
| `technical_crawlability` | 15 | rule | robots 可抓、SSR/静态可见正文、无 JS 死锁、状态码、canonical |
| `content_structure` | 20 | rule | heading 层级、问答格式、开头直接答案、列表/表格、段落长度 |
| `authority_eeat` | 20 | rule+llm | 作者 bio、资质、来源引用、外链权威度 |
| `freshness` | 10 | rule | 更新日期、内容时效信号（季度刷新原则） |
| `citation_friendliness` | 15 | rule+llm | 可提取的独立事实句、数据化表达、明确实体定义、fan-out 子问题覆盖 |
| `entity_alignment` | 10 | rule | Schema/JSON-LD 实体标注、名称与知识图谱一致性 |
| `walled_garden_presence` | 10 | rule | 品牌在该引擎偏好平台（百家号/知乎/抖音…）的存在感（由 Engine.source_preferences 驱动） |

> 权重合计 100。各维内可再拆 check（见 YAML）。

## YAML 结构（示例，实际文件更全）

```yaml
version: 1
locale: zh-CN
dimensions:
  technical_crawlability:
    weight: 15
    checks:
      - id: robots_allows
        method: rule
        weight: 5
      - id: ssr_content_visible
        method: rule
        weight: 6
      - id: http_ok
        method: rule
        weight: 4
  content_structure:
    weight: 20
    checks:
      - id: direct_answer_lead
        method: rule
        weight: 6
      - id: heading_hierarchy
        method: rule
        weight: 5
      - id: qa_or_list_format
        method: rule
        weight: 5
      - id: paragraph_length
        method: rule
        weight: 4
  # ... 其余维度
engine_overrides:
  baidu_ernie:
    walled_garden_presence: { weight: 18 }   # 文心重百度生态
    entity_alignment:       { weight: 14 }
  kimi:
    authority_eeat:         { weight: 26 }    # Kimi 偏学术权威
    walled_garden_presence: { weight: 4 }
  doubao:
    walled_garden_presence: { weight: 16 }    # 豆包重社媒/字节生态
compliance:
  forbidden_patterns:        # 命中→compliance_flag，且降权
    - keyword_stuffing
    - fake_reviews
    - guaranteed_ranking_claim
```

> `engine_overrides` 里改的是该维度**总权重**；scoring 引擎会按引擎重新归一化到 100。

## 打分流程（engines/scoring）

```
signals = analysis.parse(html)          # 每个 check 的原始信号
for dim in rubric.dimensions:
    for check in dim.checks:
        check.score = evaluate(check, signals)   # rule: 0/部分/满分; llm: 留位
    dim.score = Σ check.score
apply engine_overrides(engine_id) → 重新归一化
total = Σ dim.score  (0..100)
breakdown = {dim: {score, weight, evidence}}
```

## 如何加一项 check（给接手者）
1. 在 `rubric.zh.yaml` 对应维度下加一条 `{id, method, weight}`。
2. 在 `engines/scoring/checks.py` 为该 `id` 实现一个评估函数（`rule` 直接算；`llm` 调 provider）。
3. `engines/analysis` 若需新信号，补一个解析器输出到 `signals`。
4. 加一条 pytest。

> 没有第 2 步的实现时，scoring 对未知 check 记 0 分并在 evidence 标注 `not_implemented`，不会崩——保证 rubric 可先行扩展。

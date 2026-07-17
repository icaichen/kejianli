# keeplix 数据模型

> 与 `backend/keeplix/models/` 一一对应。服务交付优先 → 实体围绕「客户 × 品牌 × 引擎 × prompt 集 × 采样 × 交付物」。

## 实体关系（ER 概览）

```
Organization (agency, 多租户预留)
   └─< Client
          └─< Project ─── BrandEntity (1:1, 品牌名/别名/域名/竞品)
                 ├─< BrandFact       (已核验品牌事实与来源)
                 ├─< Page ─< AuditRun ─┬─ Score (1:1, breakdown JSON)
                 │                     └─< Recommendation
                 ├─< Prompt
                 ├─< CitationRun ─< CitationResult
                 ├─< VisibilityScore   (聚合快照)
                 ├─< WorkItem ─< OptimizationArtifact ─< DeliveryRecord
                 │                                      └─ CycleRetestPlan
                 └─< Deliverable       (客户交付报告)

Engine (引擎目录, 全局配置表: acquisition / source_preferences)
   ├── EngineQualification (人工验收与正式报告资格)
   ├── EngineValidationRun (Provider 验证证据与审核记录)
   └── EngineRuntimeStatus (真实 Provider 最近连通状态)
```

## 表定义

### Organization
agency 自身。多租户预留，本轮固定单条 default org。
| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID PK | |
| name | str | |
| created_at | datetime | |

### Client
agency 服务的客户。
| id | UUID PK |
| org_id | FK→Organization |
| name | str |
| notes | str? |

### Project
客户下的一项 AI 市场研究或 GEO engagement。企业/咨询场景中，项目名代表研究课题，不代表品牌本身。
| id | UUID PK |
| client_id | FK→Client |
| name | str | 研究项目名称 |
| primary_domain | str | 主域名；辅助字段，可空 |
| locale | str | 默认 `zh-CN` |
| market | str | 研究市场或地区，如“中国大陆” |
| category | str | 研究品类，如“个人护理” |
| research_objective | str | 商业问题与研究目标 |
| brief_version | int | 研究范围版本；品牌、域名、市场、品类、竞品或目标实质变化时递增 |

API 会从 `Project` 和 `BrandEntity` 实时计算 `brief_ready` 与 `brief_missing_fields`，不重复落库。该状态是问题框架、问题集、追踪计划和正式可见度指标的统一门槛。
| status | enum | active/paused/archived |

### BrandEntity
研究中的核心品牌实体（citation 匹配目标）及竞争集合。
| id | UUID PK |
| project_id | FK→Project |
| brand_name | str | 主名 |
| aliases | JSON[str] | 别名/简称/英文名 |
| domains | JSON[str] | 自有域名（判 citation-SoV 用） |
| competitors | JSON[str] | 竞品名（算相对 SoV 用） |

### BrandFact
用户确认、可追溯的品牌事实。Improve 和 Agent 生成产物时不允许使用本表之外的产品事实。
| id | UUID PK |
| project_id | FK→Project |
| fact_type | str | `product` / `audience` / `proof` / `pricing` / `limitation` / `policy` |
| claim | text | 用户确认的原子事实 |
| source_url | str | 能直接支持该事实的 HTTP(S) 来源 |
| status | str | `draft` / `verified` / `rejected` |
| created_by | str | 当前默认 `user` |
| created_at / updated_at | datetime | 审计时间 |

### Engine（全局目录表，非按项目）
引擎的能力与偏好配置。**信源偏好在这里，不硬编码。**
| id | str PK | `deepseek`/`baidu_ernie`/`doubao`/`kimi`/`qwen`/`yuanbao`/`chatgpt`/`perplexity` |
| display_name | str | |
| acquisition | enum | `api`/`browser`/`stub` |
| source_preferences | JSON[str] | 该引擎偏好信源（如百家号/知乎/抖音），供 rubric override 与建议用 |
| enabled | bool | |

### EngineQualification（答案面资格矩阵）
同一模型名称不等于同一产品答案面。本表记录具体答案面的联网状态、采集方式、地区语言、引用可得性、人工验收状态与正式报告资格。运行时还会校验当前 Provider 是否真实连接且能力与验收记录一致；两者同时成立才可写入正式可见度趋势。

### EngineValidationRun（Provider 验证记录）
每次验证使用 `config/provider_validation.zh.yaml` 中的固定题集，保存完整答案、归一化引用 URL、请求标识、模型/Agent 标识、观测时间和逐项检查结果。自动检查通过不等于正式资格；只有最新记录经人工 `accepted` 后，才会更新 `EngineQualification`。Stub 可生成失败记录用于解释未连接状态，但永远不能被接受。

同一引擎只允许一条 `running` 验证，服务层检查与数据库部分唯一索引共同防止重复付费调用。启动更新验证时，尚未审核的旧证据会保留，但标记为 `rejected` 并注明已被新记录替代，避免审计队列长期悬挂。
| id | UUID PK | 验证记录 id |
| engine_id | FK→Engine | 被验证引擎 |
| profile_version | int | 固定题集配置版本 |
| status | str | `running` / `passed` / `failed` |
| review_status | str | `pending` / `accepted` / `rejected` |
| provider_acquisition | str | 本次实际采集方式 |
| measurement_scope | str | 本次实际观测范围 |
| checks | JSON | 自动检查结果 |
| evidence | JSON | 答案、引用及安全的 Provider 元数据 |
| error_summary | str | 不含密钥和原始响应的失败摘要 |
| started_at / finished_at | datetime | 执行时间 |
| reviewed_at / review_notes | datetime / str | 人工审核轨迹 |

### EngineRuntimeStatus（真实 Provider 运行状态）
记录每个真实 Provider 最近一次调用的成功或失败结果，供 `/api/engines` 和 UI 展示当前连通性。Stub 调用不写入本表，避免无 key 的演示运行被误报为真实接入成功。
| engine_id | str PK, FK→Engine | 引擎 id |
| status | str | `unknown` / `ready` / `degraded` |
| last_success_at | datetime? | 最近真实调用成功时间 |
| last_failure_at | datetime? | 最近真实调用失败时间 |
| last_error | str | 最近失败的安全摘要 |
| last_observed_at | datetime? | 最近真实调用观测时间 |
| updated_at | datetime | 状态行更新时间 |

### Prompt
采样查询。prompt 集的质量 = 测量质量。
| id | UUID PK |
| project_id | FK→Project |
| text | str | 查询语句 |
| intent | enum | `branded`/`category`/`problem`/`comparison` |
| active | bool | |

### PromptSet
一组可版本化的研究问题，冻结创建时的 `brief_version`。项目 Brief 更新后，旧问题集仍保留为历史证据，但不能用于创建当前追踪计划；基于旧问题集编辑会产生绑定最新 Brief 的新版本。
| id | UUID PK |
| project_id | FK→Project |
| source_prompt_set_id | FK→PromptSet? | 版本来源 |
| name / version | str / int | 问题集名称与版本 |
| brief_version | int | 创建时的研究 Brief 版本 |
| active | bool | 同名问题集当前版本标记 |

### Page
被审计的 URL。
| id | UUID PK |
| project_id | FK→Project |
| url | str |
| last_fetched_at | datetime? |
| content_snapshot | text? | 抓取正文快照 |

### AuditRun
一次对某 Page 的分析运行。
| id | UUID PK |
| page_id | FK→Page |
| engine_id | str? FK→Engine | null=通用档；否则按引擎档评分 |
| started_at / finished_at | datetime |
| status | enum | pending/running/done/failed |

### Score
AuditRun 的评分结果（1:1）。
| id | UUID PK |
| audit_run_id | FK→AuditRun |
| total | int | 0–100 |
| breakdown | JSON | `{dimension: {score, weight, evidence}}` |

### Recommendation
可执行建议条目。
| id | UUID PK |
| audit_run_id | FK→AuditRun |
| dimension | str | 对应 rubric 分项 |
| title | str |
| detail | str |
| severity | enum | high/medium/low |
| jsonld | JSON? | 自动生成的 Schema JSON-LD（如适用） |
| compliance_flag | bool | 命中合规红线时置 true（见 product.md §8） |

### CitationRun
一次采样批次。
| id | UUID PK |
| project_id | FK→Project |
| engine_id | str FK→Engine |
| samples | int | 每 prompt 采样次数 N |
| started_at / finished_at | datetime |
| status | enum |
| surface_name | str | 本次实际测量的具体答案面 |
| provider_acquisition | str | `api` / `browser` / `stub` / `unknown` |
| measurement_scope | str | `citation` / `answer_visibility` / `brand_awareness` / `stub` / `legacy_unclassified` |
| report_eligible | bool | 本次运行是否允许进入正式报告与自动决策 |
| brief_version | int | 采样时的研究 Brief 版本；用于隔离历史范围与当前报告 |

### TrackingPlan
项目级持续追踪配置。`next_run_at` 决定调度时间，`lease_token` 与 `lease_expires_at` 组成短期执行租约，确保多个调度器不会同时执行同一计划；进程异常退出后租约会自动过期并允许恢复。

当项目 Brief 实质更新时，绑定旧 Brief 问题集的活跃计划自动暂停，避免调度器继续为已经失效的研究范围产生费用和不可比较数据。

### CitationResult
单次采样样本（一个 prompt 的一次回答）。
| id | UUID PK |
| citation_run_id | FK→CitationRun |
| prompt_id | FK→Prompt |
| sample_index | int | 第几次采样 |
| answer_text | text | 原始回答 |
| brand_mentioned | bool | 品牌被点名（entity 信号） |
| rank | int? | 品牌在答案中的相对位置（1=最靠前） |
| cited_urls | JSON[str] | 回答引用的来源 URL（citation 信号） |
| own_domain_cited | bool | cited_urls 是否命中自有域名 |
| sentiment | enum? | positive/neutral/negative |

### VisibilityScore
聚合快照（供趋势图）。
| id | UUID PK |
| project_id | FK→Project |
| engine_id | str FK→Engine |
| surface_name | str | 实际观测的答案面名称 |
| provider_acquisition | str | 本次采集方式；历史数据为 `legacy_unclassified` |
| measurement_scope | str | `citation` / `answer_visibility` / `brand_awareness` / `legacy_unclassified` |
| tracking_plan_id | FK→TrackingPlan? | 为空表示单次检测，不进入正式趋势 |
| brief_version | int | 生成指标时的研究 Brief 版本 |
| period | date | 快照日期 |
| entity_sov | float | 品牌被点名率（0–1） |
| citation_sov | float | 内容被引用率（0–1） |
| avg_rank | float? |
| sample_size | int |

趋势可比较性不额外写入数据库，而是由项目服务按 Brief 版本、追踪计划、引擎、答案面、采集方式与测量范围计算。只有范围一致的连续快照返回变化值；范围变化会返回新基线状态。项目概览、当前诊断和企业报告只消费当前 Brief 版本，旧证据仍在运行记录中可复查。

### Deliverable
客户交付物（报告）。
| id | UUID PK |
| project_id | FK→Project |
| kind | enum | audit_report/sov_report/content_plan |
| payload | JSON | 报告内容快照 |
| created_at | datetime |

### WorkItem / OptimizationArtifact / DeliveryRecord / CycleRetestPlan
`WorkItem` 将正式诊断变成可执行工作，并在 `evidence_snapshot` 中冻结诊断、问题、采样运行和 `brief_version`。

`OptimizationArtifact` 保存内容、执行说明或 JSON-LD 的每个版本。证据化生成会在 `source_snapshot` 中保存诊断证据、`brand_fact_ids`、`brief_version`、生成引擎和生成时间；新版本不删除旧版本。

`DeliveryRecord` 记录已批准产物的导出或实施位置，用于将「诊断 → 产物 → 实施 → 复测」连成同一个可审计周期。

`CycleRetestPlan` 在本周期选定工作全部完成或明确跳过后，由最后一条实施记录自动建立。它持久化计划时间、执行状态、失败原因和完成时间；到期任务复用周期冻结的问题、答案面与采样次数，不能改用另一套口径制造表面提升。

周期的 `verification_summary` 同时保存逐答案面的 `comparison_status` 与 `comparison_reasons`。只有 Brief 版本、答案面、采集方式、测量范围、正式资格和样本数全部一致时，才写入变化值与提升/下降判断；范围漂移时变化值为 `null`，本次正式结果只能作为新口径证据，不能归因于已实施内容。

## 两种 SoV（重要区分，见 citation-engine.md）
- **entity-SoV** = `brand_mentioned=true` 的样本占比 → 品牌是否被 AI 点名推荐（中国 B2B 更可执行）。
- **citation-SoV** = `own_domain_cited=true` 的样本占比 → 你的内容 URL 是否被当作来源引用。

## 迁移
Alembic 管理。首个迁移建全部上述表。改字段 = 新增迁移，不手改历史迁移。

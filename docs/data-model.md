# keeplix 数据模型

> 与 `backend/keeplix/models/` 一一对应。服务交付优先 → 实体围绕「客户 × 品牌 × 引擎 × prompt 集 × 采样 × 交付物」。

## 实体关系（ER 概览）

```
Organization (agency, 多租户预留)
   └─< Client
          └─< Project ─── BrandEntity (1:1, 品牌名/别名/域名/竞品)
                 ├─< Page ─< AuditRun ─┬─ Score (1:1, breakdown JSON)
                 │                     └─< Recommendation
                 ├─< Prompt
                 ├─< CitationRun ─< CitationResult
                 ├─< VisibilityScore   (聚合快照)
                 └─< Deliverable       (客户交付报告)

Engine (引擎目录, 全局配置表: acquisition / source_preferences)
   ├── EngineQualification (人工验收与正式报告资格)
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
一次 GEO 服务合约/engagement。
| id | UUID PK |
| client_id | FK→Client |
| name | str |
| primary_domain | str | 主域名 |
| locale | str | 默认 `zh-CN` |
| status | enum | active/paused/archived |

### BrandEntity
被优化的品牌实体（citation 匹配的目标）。
| id | UUID PK |
| project_id | FK→Project |
| brand_name | str | 主名 |
| aliases | JSON[str] | 别名/简称/英文名 |
| domains | JSON[str] | 自有域名（判 citation-SoV 用） |
| competitors | JSON[str] | 竞品名（算相对 SoV 用） |

### Engine（全局目录表，非按项目）
引擎的能力与偏好配置。**信源偏好在这里，不硬编码。**
| id | str PK | `deepseek`/`baidu_ernie`/`doubao`/`kimi`/`qwen`/`yuanbao`/`chatgpt`/`perplexity` |
| display_name | str | |
| acquisition | enum | `api`/`browser`/`stub` |
| source_preferences | JSON[str] | 该引擎偏好信源（如百家号/知乎/抖音），供 rubric override 与建议用 |
| enabled | bool | |

### EngineQualification（答案面资格矩阵）
同一模型名称不等于同一产品答案面。本表记录具体答案面的联网状态、采集方式、地区语言、引用可得性、人工验收状态与正式报告资格。运行时还会校验当前 Provider 是否真实连接且能力与验收记录一致；两者同时成立才可写入正式可见度趋势。

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

### TrackingPlan
项目级持续追踪配置。`next_run_at` 决定调度时间，`lease_token` 与 `lease_expires_at` 组成短期执行租约，确保多个调度器不会同时执行同一计划；进程异常退出后租约会自动过期并允许恢复。

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
| period | date | 快照日期 |
| entity_sov | float | 品牌被点名率（0–1） |
| citation_sov | float | 内容被引用率（0–1） |
| avg_rank | float? |
| sample_size | int |

### Deliverable
客户交付物（报告）。
| id | UUID PK |
| project_id | FK→Project |
| kind | enum | audit_report/sov_report/content_plan |
| payload | JSON | 报告内容快照 |
| created_at | datetime |

## 两种 SoV（重要区分，见 citation-engine.md）
- **entity-SoV** = `brand_mentioned=true` 的样本占比 → 品牌是否被 AI 点名推荐（中国 B2B 更可执行）。
- **citation-SoV** = `own_domain_cited=true` 的样本占比 → 你的内容 URL 是否被当作来源引用。

## 迁移
Alembic 管理。首个迁移建全部上述表。改字段 = 新增迁移，不手改历史迁移。

"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api, type CitationRunResponse, type EngineInfo, type ResearchQuestionFramework } from "@/lib/api";

const ALL_ENGINES = [
  "deepseek",
  "qwen",
  "kimi",
  "baidu_ernie",
  "doubao",
  "yuanbao",
  "chatgpt",
  "perplexity",
];
const INTENT_GROUPS = [
  { id: "branded", label: "品牌认知", detail: "AI 如何定义与推荐核心品牌" },
  { id: "category", label: "品类地图", detail: "市场品牌、趋势与选择标准" },
  { id: "problem", label: "需求问题", detail: "消费者或采购者的真实任务" },
  { id: "comparison", label: "竞品比较", detail: "品牌在直接比较中的位置" },
] as const;
const BRIEF_FIELD_LABEL: Record<string, string> = {
  brand_name: "核心品牌",
  market: "研究市场",
  category: "明确品类",
  competitors: "主要竞品",
  research_objective: "研究目标",
};

function VisibilityContent() {
  const params = useSearchParams();
  const initialDomain = params.get("domain") ?? "";
  const initialBrand = params.get("brand") ?? initialDomain;
  const initialProjectId = params.get("project") ?? "";
  const [brand, setBrand] = useState(initialBrand);
  const [domain, setDomain] = useState(initialDomain);
  const [competitorsText, setCompetitorsText] = useState("");
  const [promptsText, setPromptsText] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [samples, setSamples] = useState(3);
  const [projectId] = useState<string | null>(initialProjectId || null);
  const [previousQuestions, setPreviousQuestions] = useState<string[]>([]);
  const [questionSource, setQuestionSource] = useState<"previous" | "framework" | "custom">("custom");
  const [questionFramework, setQuestionFramework] = useState<ResearchQuestionFramework | null>(null);
  const [saveTrackingPlan, setSaveTrackingPlan] = useState(true);
  const [cadence, setCadence] = useState("weekly");
  const [data, setData] = useState<CitationRunResponse | null>(null);
  const [engines, setEngines] = useState<EngineInfo[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [providerErrors, setProviderErrors] = useState<Record<string, string>>({});
  const [briefReady, setBriefReady] = useState(false);
  const [briefMissingFields, setBriefMissingFields] = useState<string[]>([]);
  const [executionConfirmed, setExecutionConfirmed] = useState(false);
  const [preparedPromptSet, setPreparedPromptSet] = useState<{ id: string; signature: string } | null>(null);
  const [preparedTrackingPlan, setPreparedTrackingPlan] = useState<{ id: string; signature: string } | null>(null);

  useEffect(() => {
    if (!initialProjectId) return;
    api.project(initialProjectId).then((project) => {
      setBrand(project.brand_name);
      setDomain(project.primary_domain);
      setCompetitorsText(project.competitors.join("，"));
      setBriefReady(project.brief_ready);
      setBriefMissingFields(project.brief_missing_fields);
      if (!project.brief_ready) {
        setPromptsText("");
        setQuestionSource("custom");
        return;
      }
      const latestRun = project.activities.find((activity) => activity.kind === "visibility" && (activity.input_snapshot.questions?.length ?? 0) > 0);
      const questions = latestRun?.input_snapshot.questions ?? [];
      if (questions.length > 0) {
        setPreviousQuestions(questions);
        setPromptsText(questions.join("\n"));
        setQuestionSource("previous");
      } else {
        const comparisonTarget = project.competitors[0] ?? "主要竞品";
        setPromptsText([
          `${project.brand_name}在${project.category || "这个品类"}市场的主要特点是什么？`,
          `${project.market}${project.category || "相关品类"}有哪些值得考虑的品牌？`,
          `选择${project.category || "这类产品"}时应重点关注哪些问题？`,
          `${project.brand_name}与${comparisonTarget}相比有什么区别？`,
        ].join("\n"));
      }
      void api.questionFramework(initialProjectId).then((framework) => {
        setQuestionFramework(framework);
        if (questions.length === 0) {
          setQuestionSource("framework");
          setSamples(framework.recommended_samples);
        }
      }).catch(() => undefined);
    }).catch(() => setError("项目历史未能加载，你仍可输入本次检测问题。"));
  }, [initialProjectId]);

  useEffect(() => {
    api.engines().then((items) => {
      setEngines(items);
      const eligibleIds = items.filter((item) => item.report_eligible).map((item) => item.id);
      const readyEligibleIds = items.filter((item) => item.report_eligible && item.runtime_status === "ready").map((item) => item.id);
      setSelected((current) => {
        const retained = current.filter((id) => eligibleIds.includes(id));
        return retained.length ? retained : readyEligibleIds.length ? readyEligibleIds : eligibleIds.slice(0, 1);
      });
    }).catch(() => setEngines(null));
  }, []);

  const activePrompts = questionSource === "framework" && questionFramework
    ? questionFramework.items.filter((item) => item.selected).map((item) => item.text.trim()).filter(Boolean)
    : promptsText.split("\n").map((item) => item.trim()).filter(Boolean);
  const selectedSurfaces = selected.map((id) => engines?.find((item) => item.id === id)?.display_name ?? id);
  const plannedSampleCount = activePrompts.length * selected.length * samples;
  const executionSignature = JSON.stringify({
    projectId,
    brand: brand.trim(),
    domain: domain.trim(),
    competitors: competitorsText.split(/[，,\n]/).map((item) => item.trim()).filter(Boolean),
    prompts: activePrompts,
    engines: selected,
    samples,
    saveTrackingPlan,
    cadence,
  });

  useEffect(() => {
    setExecutionConfirmed(false);
  }, [executionSignature]);

  async function loadEngines() {
    try {
      setEngines(await api.engines());
    } catch {
      setEngines(null);
    }
  }

  async function ensureProject() {
    if (projectId) return projectId;
    throw new Error("请先建立一个完整的研究项目。");
  }

  async function run(engineOverride?: string[], shouldSavePlan = saveTrackingPlan) {
    const prompts = activePrompts;
    const activeEngines = engineOverride ?? selected;
    if (!brand.trim() || prompts.length === 0 || activeEngines.length === 0) {
      setError("请填写品牌名称、至少一个问题，并选择一个引擎。");
      return;
    }

    setLoading(true);
    setError(null);
    setProviderErrors({});
    const previousResult = engineOverride ? data : null;
    if (!engineOverride) setData(null);
    try {
      const savedProjectId = await ensureProject();
      const promptSetSignature = JSON.stringify({ savedProjectId, brand: brand.trim(), domain: domain.trim(), competitors: competitorsText, prompts });
      let promptSetId = preparedPromptSet?.signature === promptSetSignature ? preparedPromptSet.id : null;
      if (!promptSetId) {
        const promptSet = await api.createPromptSet(savedProjectId, {
          name: `${questionSource === "framework" ? "企业研究框架" : "追踪问题"} ${new Date().toLocaleDateString("zh-CN")}`,
          prompts,
          kind: "tracking",
        });
        promptSetId = promptSet.id;
        setPreparedPromptSet({ id: promptSet.id, signature: promptSetSignature });
      }
      const trackingPlanSignature = JSON.stringify({ promptSetId, engines: selected, samples, cadence });
      let trackingPlanId = (shouldSavePlan || engineOverride !== undefined) && preparedTrackingPlan?.signature === trackingPlanSignature ? preparedTrackingPlan.id : null;
      if (shouldSavePlan && !trackingPlanId) {
        const trackingPlan = await api.createTrackingPlan(savedProjectId, {
          prompt_set_id: promptSetId,
          engine_ids: selected,
          samples,
          cadence,
        });
        trackingPlanId = trackingPlan.id;
        setPreparedTrackingPlan({ id: trackingPlan.id, signature: trackingPlanSignature });
      }
      const result = await api.runCitations({
        engine_ids: activeEngines,
        prompts,
        brand_name: brand.trim(),
        brand_domains: domain.trim() ? [domain.trim()] : undefined,
        competitors: competitorsText.split(/[，,\n]/).map((item) => item.trim()).filter(Boolean),
        samples,
        project_id: savedProjectId,
        prompt_set_id: promptSetId,
        tracking_plan_id: trackingPlanId ?? undefined,
      });
      const mergedResults = new Map(previousResult?.results.map((item) => [item.engine_id, item]) ?? []);
      for (const item of result.results) mergedResults.set(item.engine_id, item);
      const remainingErrors = { ...(previousResult?.errors ?? {}), ...result.errors };
      for (const item of result.results) delete remainingErrors[item.engine_id];
      const combined = {
        ...result,
        results: Array.from(mergedResults.values()),
        errors: remainingErrors,
        status: Object.keys(remainingErrors).length
          ? mergedResults.size ? "partial" as const : "failed" as const
          : "done" as const,
      };
      setData(combined);
      setProviderErrors(remainingErrors);
      setExecutionConfirmed(false);
      await loadEngines();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "采样请求失败，请稍后再试。");
    } finally {
      setLoading(false);
    }
  }

  function toggle(id: string) {
    const engine = engines?.find((item) => item.id === id);
    if (!engine?.report_eligible) return;
    setSelected((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  }

  function updateFrameworkItem(id: string, update: { text?: string; selected?: boolean }) {
    setQuestionFramework((current) => current ? {
      ...current,
      items: current.items.map((item) => item.id === id ? { ...item, ...update } : item),
    } : current);
    setQuestionSource("framework");
  }

  return (
    <div className="legacy-page space-y-8">
      <section className="visibility-intro">
        <div className="overline"><span>AI 市场基线</span><span>多答案面研究</span></div>
        <h1>测量 AI 如何<br />描述并<em>比较品牌</em>。</h1>
        <p>围绕目标市场中的消费者、采购与比较问题，测量品牌提及、竞品份额、推荐理由和引用来源。</p>
      </section>

      <section className="visibility-panel">
        {!projectId ? <div className="visibility-readiness" role="status"><strong>正式基线必须属于一个研究项目</strong><p>先固定品牌、市场、品类、竞品和研究目标；问题、原始回答和后续趋势才能保持同一口径。</p><Link href="/start">新建研究项目 →</Link></div> : !briefReady ? <div className="visibility-readiness" role="alert"><strong>研究 Brief 还不能支撑正式基线</strong><p>还需要：{briefMissingFields.map((field) => BRIEF_FIELD_LABEL[field] ?? field).join("、")}。补齐后系统才会生成问题框架并调用真实答案面。</p><Link href={`/projects/${projectId}#research-brief`}>返回项目完善 Brief →</Link></div> : null}
        <div className="visibility-fields">
          <label><span>核心品牌 · 来自 Brief</span><input suppressHydrationWarning value={brand} readOnly placeholder="例如：多芬" /></label>
          <label><span>品牌域名 · 来自 Brief</span><input suppressHydrationWarning value={domain} readOnly placeholder="例如：keeplix.com" /></label>
          <label><span>主要竞品 · 来自 Brief</span><input suppressHydrationWarning value={competitorsText} readOnly placeholder="例如：海飞丝，潘婷" /></label>
          <label><span>每个问题的采样次数</span><input suppressHydrationWarning type="number" min={1} max={20} value={samples} onChange={(event) => setSamples(Number(event.target.value) || 1)} /></label>
        </div>
        {projectId && <p className="brief-lock-note">品牌、域名和竞品已锁定到当前项目 Brief。需要修改时，先<Link href={`/projects/${projectId}#research-brief`}>更新研究范围</Link>，系统会为新范围建立新基线。</p>}
        <div className="prompt-field"><span>研究问题</span><div className="question-source-controls">{questionFramework && <button type="button" className={questionSource === "framework" ? "is-active" : ""} onClick={() => setQuestionSource("framework")}>企业研究框架</button>}{previousQuestions.length > 0 && <button type="button" className={questionSource === "previous" ? "is-active" : ""} onClick={() => { setPromptsText(previousQuestions.join("\n")); setQuestionSource("previous"); }}>复用上次 {previousQuestions.length} 个问题</button>}<button type="button" className={questionSource === "custom" ? "is-active" : ""} onClick={() => { setPromptsText(""); setQuestionSource("custom"); }}>自由输入</button></div>{questionSource === "framework" && questionFramework ? <section className="question-framework"><header><div><strong>{questionFramework.title}</strong><p>{questionFramework.summary}</p></div><span>{questionFramework.items.filter((item) => item.selected).length} / {questionFramework.items.length} 个问题已选择</span></header><div className="question-framework-groups">{INTENT_GROUPS.map((group) => <article key={group.id}><div><span>{group.label}</span><small>{group.detail}</small></div>{questionFramework.items.filter((item) => item.intent === group.id).map((item) => <div key={item.id} className={`framework-question${item.selected ? " is-selected" : ""}`}><input aria-label={`选择${item.text}`} type="checkbox" checked={item.selected} onChange={(event) => updateFrameworkItem(item.id, { selected: event.target.checked })} /><textarea aria-label={`${group.label}研究题`} value={item.text} onChange={(event) => updateFrameworkItem(item.id, { text: event.target.value })} /><small>{item.rationale}</small></div>)}</article>)}</div><footer><span>建议每题采样 {questionFramework.recommended_samples} 次 · 当前仅使用已验收答案面</span><button type="button" onClick={() => setQuestionFramework((current) => current ? { ...current, items: current.items.map((item) => ({ ...item, selected: true })) } : current)}>选择全部 16 个问题</button></footer></section> : <textarea aria-label="研究问题，每行一个" suppressHydrationWarning value={promptsText} onChange={(event) => { setPromptsText(event.target.value); setQuestionSource("custom"); }} />}</div>
        <div className="engine-selector">
          <span>选择引擎</span>
          <div>{ALL_ENGINES.map((id) => {
            const engine = engines?.find((item) => item.id === id);
            const eligible = engine?.report_eligible === true;
            const scopeLabel = eligible
              ? engine?.runtime_status === "degraded" ? "正式答案面 · 最近失败" : "正式答案面"
              : engine?.is_stub ? "当前未连接" : engine?.measurement_scope === "brand_awareness" ? "仅品牌认知" : engine?.validation_status === "pending" ? "待验收" : "不可用于正式报告";
            return <button key={id} type="button" onClick={() => toggle(id)} aria-pressed={selected.includes(id)} disabled={!eligible} className={`${selected.includes(id) ? "is-selected" : ""}${eligible ? "" : " is-unavailable"}`}><b>{engine?.display_name ?? id}</b><small>{scopeLabel}</small></button>;
          })}</div>
        </div>
        {engines && engines.every((engine) => !engine.report_eligible) && <div className="visibility-readiness" role="status"><strong>真实 AI 市场基线暂不可用</strong><p>当前没有完成验收的答案面，因此不会生成模拟结论。研究范围已经保存；答案面就绪后可按当前问题集继续采样。</p>{projectId && <Link href={`/projects/${projectId}`}>返回研究项目 →</Link>}</div>}
        {engines && <details className="provider-matrix"><summary><span>答案面资格矩阵</span><b>{engines.filter((engine) => engine.report_eligible).length} 个可进入正式报告 · {engines.filter((engine) => engine.runtime_status === "ready").length} 个最近跑通</b><i>↓</i></summary><div className="provider-matrix-table"><div className="provider-matrix-head"><span>答案面</span><span>报告资格</span><span>当前连通性</span><span>观测能力</span><span>验收与限制</span></div>{engines.map((engine) => <div className="provider-matrix-row" key={engine.id}><div><strong>{engine.display_name}</strong><small>{engine.surface_name}</small></div><div><b className={engine.report_eligible ? "is-formal" : ""}>{engine.report_eligible ? "正式报告" : engine.is_stub ? "未连接" : engine.measurement_scope === "brand_awareness" ? "仅品牌认知" : "待验收"}</b><small>{engine.acquisition} · {engine.region_language} · {engine.auth_mode}</small></div><div><b className={engine.runtime_status === "ready" ? "is-formal" : engine.runtime_status === "degraded" ? "is-degraded" : ""}>{runtimeLabel(engine)}</b><small>{runtimeDetail(engine)}</small></div><div><span>{engine.network_enabled ? "联网答案" : "普通回答"}</span><small>{engine.citation_availability === "structured" ? "结构化来源" : engine.citation_availability === "urls" ? "来源 URL" : "无引用来源"}</small></div><div><p>{engine.validation_notes}</p>{engine.cost_note && <small>{engine.cost_note}</small>}{engine.last_validated_at && <small>最近验收：{new Date(engine.last_validated_at).toLocaleDateString("zh-CN")}</small>}</div></div>)}</div></details>}
        <div className="tracking-controls">
          <label><input type="checkbox" checked={saveTrackingPlan} onChange={(event) => setSaveTrackingPlan(event.target.checked)} />保存为追踪计划</label>
          <label><span>频率</span><select value={cadence} onChange={(event) => setCadence(event.target.value)} disabled={!saveTrackingPlan}><option value="manual">手动</option><option value="daily">每日</option><option value="weekly">每周</option><option value="monthly">每月</option></select></label>
        </div>
        <section className="baseline-execution-review" aria-label="基线执行确认">
          <header><span>执行前确认</span><strong>本次预计产生 {plannedSampleCount} 个真实答案样本</strong></header>
          <div><article><span>研究问题</span><b>{activePrompts.length} 个</b></article><article><span>正式答案面</span><b>{selectedSurfaces.join("、") || "尚未选择"}</b></article><article><span>重复采样</span><b>每题每答案面 {samples} 次</b></article><article><span>后续复测</span><b>{saveTrackingPlan ? `${cadence === "daily" ? "每日" : cadence === "weekly" ? "每周" : cadence === "monthly" ? "每月" : "手动"}追踪` : "仅保存本次基线"}</b></article></div>
          <label><input type="checkbox" checked={executionConfirmed} onChange={(event) => setExecutionConfirmed(event.target.checked)} disabled={!projectId || !briefReady || !activePrompts.length || !selected.length} /><span>我已确认问题、答案面和采样规模；实际费用按各 Provider 账户计费。</span></label>
        </section>
        <button className="primary-button" type="button" onClick={() => void run()} disabled={loading || selected.length === 0 || activePrompts.length === 0 || !projectId || !briefReady || !executionConfirmed}>{loading ? `正在执行 ${plannedSampleCount} 个答案样本…` : "确认并建立 AI 市场基线"}<span aria-hidden="true">→</span></button>
        <p className="panel-note" role="status" aria-live="polite">{!projectId ? "请先从完整的研究项目进入；单次无归属搜索不会被写成市场基线。" : !briefReady ? "当前不会生成问题集或调用模型；请先返回项目完成研究 Brief。" : questionSource === "previous" ? "正在复用上次检测问题；本次完成后可直接比较变化。" : questionSource === "framework" ? "企业研究框架覆盖品牌、品类、需求和比较意图；你可以编辑或取消任一问题。" : "本次使用了新的问题范围；项目会保存完整输入和结果，趋势比较将标注范围变化。"}</p>
      </section>

      {error && <div className="error-banner" role="alert"><strong>采样没有完成</strong><p>{error}</p><button type="button" onClick={() => void run()}>重新尝试</button></div>}

      {Object.keys(providerErrors).length > 0 && <div className="error-banner provider-error-banner" role="status"><strong>{data?.results.length ? "部分引擎未完成" : "本次引擎均未完成"}</strong><p>{Object.entries(providerErrors).map(([engine, message]) => `${engine}：${message}`).join("；")}。已成功引擎的结果已保存，不需要重跑。</p><button type="button" onClick={() => void run(Object.keys(providerErrors), false)} disabled={loading}>仅重试失败引擎</button></div>}

      {data && <section className="visibility-results">
        <div className="result-heading"><span>已保存的 AI 市场基线</span><h2>品牌与竞品出现在什么答案中</h2><p>这些结果会成为后续竞争洞察、趋势监测和客户汇报的证据基础。</p></div>
        {data.results[0]?.measurement_quality && <div className="measurement-quality-summary"><strong>{data.results[0].measurement_quality.status === "comprehensive" ? "问题覆盖完整" : data.results[0].measurement_quality.status === "balanced" ? "问题覆盖较均衡" : "问题覆盖有限"}</strong><div>{Object.entries(data.results[0].measurement_quality.coverage).map(([intent, count]) => <span key={intent}>{intent} {count}</span>)}</div>{data.results[0].measurement_quality.warnings.length > 0 && <p>{data.results[0].measurement_quality.warnings.join("；")}</p>}</div>}
        <div className="sov-table-wrap"><table><thead><tr><th>答案面</th><th>品牌提及</th><th>域名引用</th><th>相对份额</th><th>竞品提及</th><th>样本</th></tr></thead><tbody>{data.results.map((result) => <tr key={result.engine_id}><td>{result.surface_name || result.engine_id}<small>{result.report_eligible ? "正式报告" : "非正式样本"}</small></td><td><Bar value={result.entity_sov} /></td><td><Bar value={result.citation_sov} /></td><td>{result.relative_sov === null ? "—" : `${Math.round(result.relative_sov * 100)}%`}</td><td>{Object.keys(result.competitor_sov).length ? Object.entries(result.competitor_sov).map(([name, value]) => <small key={name}>{name} {Math.round(value * 100)}%</small>) : "—"}</td><td>{result.sample_size}</td></tr>)}</tbody></table></div>
        {engines && <p className="provider-note">本次进入正式项目趋势：{data.results.filter((result) => result.report_eligible).map((result) => result.surface_name || result.engine_id).join("、") || "无"}</p>}
        {projectId && <Link className="primary-button visibility-return" href={`/projects/${projectId}?view=visibility`}>进入项目查看证据与诊断 <span aria-hidden="true">→</span></Link>}
      </section>}
    </div>
  );
}

function Bar({ value }: { value: number }) {
  const percent = Math.round(value * 100);
  return <div className="sov-bar"><i style={{ width: `${percent}%` }} /><span>{percent}%</span></div>;
}

function runtimeLabel(engine: EngineInfo) {
  if (engine.runtime_status === "ready") return "当前可用";
  if (engine.runtime_status === "degraded") return "最近失败";
  if (engine.runtime_status === "not_connected") return "未接入";
  return "尚未观测";
}

function runtimeDetail(engine: EngineInfo) {
  if (engine.runtime_status === "not_connected") return "需要配置 API key 或接入方式";
  if (engine.runtime_status === "degraded") return engine.last_error || "最近调用未完成";
  if (engine.last_success_at) return `最近成功：${new Date(engine.last_success_at).toLocaleString("zh-CN")}`;
  return "还没有真实调用记录";
}

export default function VisibilityPage() {
  return <Suspense fallback={<div className="legacy-page"><div className="audit-skeleton"><div /><div /></div></div>}><VisibilityContent /></Suspense>;
}

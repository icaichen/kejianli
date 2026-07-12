"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api, type CitationRunResponse, type EngineInfo } from "@/lib/api";

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

function VisibilityContent() {
  const params = useSearchParams();
  const initialDomain = params.get("domain") ?? "";
  const initialBrand = params.get("brand") ?? initialDomain;
  const initialProjectId = params.get("project") ?? "";
  const [brand, setBrand] = useState(initialBrand);
  const [domain, setDomain] = useState(initialDomain);
  const [promptsText, setPromptsText] = useState("最好的 GEO 工具\n如何做中文内容优化");
  // 默认选择已验收的联网答案面，避免把演示数据误认为真实监测。
  const [selected, setSelected] = useState<string[]>(["qwen"]);
  const [samples, setSamples] = useState(3);
  const [projectId, setProjectId] = useState<string | null>(initialProjectId || null);
  const [previousQuestions, setPreviousQuestions] = useState<string[]>([]);
  const [questionSource, setQuestionSource] = useState<"previous" | "custom">("custom");
  const [saveTrackingPlan, setSaveTrackingPlan] = useState(true);
  const [cadence, setCadence] = useState("weekly");
  const [data, setData] = useState<CitationRunResponse | null>(null);
  const [engines, setEngines] = useState<EngineInfo[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [providerErrors, setProviderErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!initialProjectId) return;
    api.project(initialProjectId).then((project) => {
      const latestRun = project.activities.find((activity) => activity.kind === "visibility" && (activity.input_snapshot.questions?.length ?? 0) > 0);
      const questions = latestRun?.input_snapshot.questions ?? [];
      if (questions.length === 0) return;
      setPreviousQuestions(questions);
      setPromptsText(questions.join("\n"));
      setQuestionSource("previous");
    }).catch(() => setError("项目历史未能加载，你仍可输入本次检测问题。"));
  }, [initialProjectId]);

  useEffect(() => {
    api.engines().then(setEngines).catch(() => setEngines(null));
  }, []);

  async function loadEngines() {
    try {
      setEngines(await api.engines());
    } catch {
      setEngines(null);
    }
  }

  async function ensureProject() {
    if (projectId) return projectId;
    const project = await api.createProject({
      name: brand.trim() || domain.trim() || "未命名品牌",
      primary_domain: domain.trim(),
    });
    setProjectId(project.id);
    return project.id;
  }

  async function run(engineOverride?: string[], shouldSavePlan = saveTrackingPlan) {
    const prompts = promptsText.split("\n").map((item) => item.trim()).filter(Boolean);
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
      const promptSet = shouldSavePlan ? await api.createPromptSet(savedProjectId, {
        name: `追踪问题 ${new Date().toLocaleDateString("zh-CN")}`,
        prompts,
        kind: "tracking",
      }) : null;
      const result = await api.runCitations({
        engine_ids: activeEngines,
        prompts,
        brand_name: brand.trim(),
        brand_domains: domain.trim() ? [domain.trim()] : undefined,
        samples,
        project_id: savedProjectId,
        prompt_set_id: promptSet?.id,
      });
      if (promptSet) {
        await api.createTrackingPlan(savedProjectId, {
          prompt_set_id: promptSet.id,
          engine_ids: activeEngines,
          samples,
          cadence,
        });
      }
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

  return (
    <div className="legacy-page space-y-8">
      <section className="visibility-intro">
        <div className="overline"><span>第一层 · 持续追踪</span><span>多引擎 Citation 采样</span></div>
        <h1>确认 AI 是否<br />真的在<em>提及</em>你。</h1>
        <p>从审计结果带来的品牌与域名已经填好。选择用户真正会问的问题，建立可见度、引用率和平均排名的第一条基线。</p>
      </section>

      <section className="visibility-panel">
        <div className="visibility-fields">
          <label><span>品牌名称</span><input suppressHydrationWarning value={brand} onChange={(event) => setBrand(event.target.value)} placeholder="例如：可见力" /></label>
          <label><span>品牌域名</span><input suppressHydrationWarning value={domain} onChange={(event) => setDomain(event.target.value)} placeholder="例如：keeplix.com" /></label>
          <label><span>每个问题的采样次数</span><input suppressHydrationWarning type="number" min={1} max={20} value={samples} onChange={(event) => setSamples(Number(event.target.value) || 1)} /></label>
        </div>
        <label className="prompt-field"><span>本次检测问题（每行一个）</span>{previousQuestions.length > 0 && <div className="question-source-controls"><button type="button" className={questionSource === "previous" ? "is-active" : ""} onClick={() => { setPromptsText(previousQuestions.join("\n")); setQuestionSource("previous"); }}>复用上次 {previousQuestions.length} 个问题</button><button type="button" className={questionSource === "custom" ? "is-active" : ""} onClick={() => { setPromptsText(""); setQuestionSource("custom"); }}>输入新问题</button></div>}<textarea suppressHydrationWarning value={promptsText} onChange={(event) => { setPromptsText(event.target.value); setQuestionSource("custom"); }} /></label>
        <div className="engine-selector">
          <span>选择引擎</span>
          <div>{ALL_ENGINES.map((id) => {
            const engine = engines?.find((item) => item.id === id);
            const eligible = engine?.report_eligible === true;
            const scopeLabel = eligible ? "正式答案面" : engine?.is_stub ? "当前未连接" : engine?.measurement_scope === "brand_awareness" ? "仅品牌认知" : engine?.validation_status === "pending" ? "待验收" : "不可用于正式报告";
            return <button key={id} type="button" onClick={() => toggle(id)} aria-pressed={selected.includes(id)} disabled={!eligible} className={`${selected.includes(id) ? "is-selected" : ""}${eligible ? "" : " is-unavailable"}`}><b>{engine?.display_name ?? id}</b><small>{scopeLabel}</small></button>;
          })}</div>
        </div>
        <div className="tracking-controls">
          <label><input type="checkbox" checked={saveTrackingPlan} onChange={(event) => setSaveTrackingPlan(event.target.checked)} />保存为追踪计划</label>
          <label><span>频率</span><select value={cadence} onChange={(event) => setCadence(event.target.value)} disabled={!saveTrackingPlan}><option value="manual">手动</option><option value="daily">每日</option><option value="weekly">每周</option><option value="monthly">每月</option></select></label>
        </div>
        <button className="primary-button" type="button" onClick={() => void run()} disabled={loading || selected.length === 0}>{loading ? "正在采样并保存项目…" : "建立可见度基线"}<span aria-hidden="true">→</span></button>
        <p className="panel-note" role="status" aria-live="polite">{projectId ? questionSource === "previous" ? "正在复用上次检测问题；本次完成后可直接比较变化。" : "本次使用了新的问题范围；项目会保存完整输入和结果，趋势比较将标注范围变化。" : "默认使用已验收的千问联网检索；首次运行会自动创建项目。"}</p>
      </section>

      {error && <div className="error-banner" role="alert"><strong>采样没有完成</strong><p>{error}</p><button type="button" onClick={() => void run()}>重新尝试</button></div>}

      {Object.keys(providerErrors).length > 0 && <div className="error-banner provider-error-banner" role="status"><strong>{data?.results.length ? "部分引擎未完成" : "本次引擎均未完成"}</strong><p>{Object.entries(providerErrors).map(([engine, message]) => `${engine}：${message}`).join("；")}。已成功引擎的结果已保存，不需要重跑。</p><button type="button" onClick={() => void run(Object.keys(providerErrors), false)} disabled={loading}>仅重试失败引擎</button></div>}

      {data && <section className="visibility-results">
        <div className="result-heading"><span>已保存的可见度基线</span><h2>你的品牌出现在哪里</h2><p>这些结果会成为后续优化和再次检测的对比基础。</p></div>
        <div className="sov-table-wrap"><table><thead><tr><th>答案面</th><th>被点名率</th><th>被引用率</th><th>平均位置</th><th>样本数</th></tr></thead><tbody>{data.results.map((result) => <tr key={result.engine_id}><td>{result.surface_name || result.engine_id}<small>{result.report_eligible ? "正式报告" : "非正式样本"}</small></td><td><Bar value={result.entity_sov} /></td><td><Bar value={result.citation_sov} /></td><td>{result.avg_rank ?? "—"}</td><td>{result.sample_size}</td></tr>)}</tbody></table></div>
        {engines && <p className="provider-note">本次进入正式项目趋势：{data.results.filter((result) => result.report_eligible).map((result) => result.surface_name || result.engine_id).join("、") || "无"}</p>}
      </section>}
    </div>
  );
}

function Bar({ value }: { value: number }) {
  const percent = Math.round(value * 100);
  return <div className="sov-bar"><i style={{ width: `${percent}%` }} /><span>{percent}%</span></div>;
}

export default function VisibilityPage() {
  return <Suspense fallback={<div className="legacy-page"><div className="audit-skeleton"><div /><div /></div></div>}><VisibilityContent /></Suspense>;
}

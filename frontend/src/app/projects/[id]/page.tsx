"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type CitationEvidence, type EngineInfo, type ProjectActivity, type ProjectDashboard, type VisibilitySnapshot } from "@/lib/api";

const ACTIVITY_LABEL: Record<string, string> = {
  audit: "网站审计",
  visibility: "AI 可见度",
  optimization: "GEO 优化",
  agent: "Agent 执行",
};
const CADENCE_LABEL: Record<string, string> = {
  manual: "手动",
  daily: "每日",
  weekly: "每周",
  monthly: "每月",
};
const STAGE_LABEL: Record<string, string> = { baseline: "建立基线", improve: "制定优化", execute: "执行中", verify: "等待复测", complete: "已完成" };
const ASSESSMENT_LABEL: Record<string, string> = { improved: "明确提升", declined: "明确下降", unchanged: "无变化", uncertain: "暂不能判断" };
const INTENT_LABEL: Record<string, string> = { branded: "品牌", category: "品类", problem: "问题", comparison: "比较" };
const QUALITY_LABEL: Record<string, string> = { comprehensive: "覆盖完整", balanced: "覆盖较均衡", limited: "覆盖有限" };

function percent(value: number) { return `${Math.round(value * 100)}%`; }
function confidenceRange(low: number | null, high: number | null) {
  return low === null || high === null ? null : `95% 区间 ${percent(low)}–${percent(high)}`;
}
function signedPercent(value: number) { return `${value > 0 ? "+" : ""}${Math.round(value * 100)}%`; }
function isWebUrl(value: string) { return /^https?:\/\//i.test(value); }
function planTrend(snapshots: VisibilitySnapshot[], planId: string) {
  const grouped = new Map<string, VisibilitySnapshot[]>();
  for (const snapshot of snapshots.filter((item) => item.tracking_plan_id === planId)) {
    grouped.set(snapshot.engine_id, [...(grouped.get(snapshot.engine_id) ?? []), snapshot]);
  }
  return Array.from(grouped.entries()).map(([engineId, values]) => {
    const ordered = values.sort((a, b) => Date.parse(b.period) - Date.parse(a.period));
    return { engineId, latest: ordered[0], previous: ordered[1] };
  });
}
function formatTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

export default function ProjectDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const [dashboard, setDashboard] = useState<ProjectDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [verifying, setVerifying] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [runningPlanId, setRunningPlanId] = useState<string | null>(null);
  const [trackingError, setTrackingError] = useState<string | null>(null);
  const [agentBusy, setAgentBusy] = useState(false);
  const [agentError, setAgentError] = useState<string | null>(null);
  const [agentConfig, setAgentConfig] = useState({ maxActions: 3, perRunBudget: 0.25, monthlyBudget: 5, autoPlanOnTracking: false });
  const [editingPromptSetId, setEditingPromptSetId] = useState<string | null>(null);
  const [promptSetDraft, setPromptSetDraft] = useState({ name: "", prompts: "" });
  const [promptSetBusy, setPromptSetBusy] = useState(false);
  const [promptSetError, setPromptSetError] = useState<string | null>(null);
  const [availableEngines, setAvailableEngines] = useState<EngineInfo[]>([]);
  const [showTrackingComposer, setShowTrackingComposer] = useState(false);
  const [trackingDraft, setTrackingDraft] = useState({ promptSetId: "", engineIds: ["qwen"], samples: 3, cadence: "weekly" });
  const [creatingDiagnosisId, setCreatingDiagnosisId] = useState<string | null>(null);
  const [diagnosisError, setDiagnosisError] = useState<string | null>(null);

  useEffect(() => {
    void params.then(({ id }) => api.project(id).then(setDashboard).catch((reason: unknown) => {
      setError(reason instanceof Error ? reason.message : "项目无法读取。");
    }));
  }, [params]);

  useEffect(() => {
    if (!dashboard?.agent_policy) return;
    setAgentConfig({
      maxActions: dashboard.agent_policy.max_actions_per_run,
      perRunBudget: dashboard.agent_policy.per_run_budget,
      monthlyBudget: dashboard.agent_policy.monthly_budget,
      autoPlanOnTracking: dashboard.agent_policy.auto_plan_on_tracking,
    });
  }, [dashboard?.agent_policy]);

  useEffect(() => {
    void api.engines().then((items) => {
      const eligible = items.filter((item) => item.report_eligible);
      setAvailableEngines(eligible);
      setTrackingDraft((current) => {
        const retained = current.engineIds.filter((id) => eligible.some((item) => item.id === id));
        return { ...current, engineIds: retained.length ? retained : eligible.slice(0, 1).map((item) => item.id) };
      });
    }).catch(() => setAvailableEngines([]));
  }, []);

  if (error) return <div className="project-shell"><div className="error-banner" role="alert"><strong>项目无法打开</strong><p>{error}</p><Link href="/projects">返回项目列表</Link></div></div>;
  if (!dashboard) return <div className="project-shell"><div className="projects-loading">正在读取项目状态…</div></div>;

  const latestByEngine = Array.from(new Map(dashboard.visibility.map((item) => [item.engine_id, item])).values());
  const latestVisibility = dashboard.activities.find((activity) => activity.kind === "visibility");
  const currentCycle = dashboard.cycles.find((cycle) => cycle.status === "active") ?? dashboard.cycles[0];
  const activeCycle = dashboard.cycles.find((cycle) => cycle.status === "active");
  const currentWork = currentCycle ? dashboard.work_items.filter((item) => item.cycle_id === currentCycle.id && item.status !== "dismissed") : [];
  const dashboardId = dashboard.id;
  const lastUpdated = dashboard.activities[0]?.started_at;
  const trackHref = `/visibility?domain=${encodeURIComponent(dashboard.primary_domain)}&brand=${encodeURIComponent(dashboard.name)}&project=${dashboard.id}`;
  const auditHref = `/analyses?url=${encodeURIComponent(`https://${dashboard.primary_domain}`)}&brand=${encodeURIComponent(dashboard.name)}&project=${dashboard.id}`;
  const latestAgentRun = dashboard.agent_runs[0];

  async function updateWork(itemId: string, status: "open" | "in_progress" | "review" | "done") {
    const updated = await api.updateWorkItem(dashboard!.id, itemId, { status });
    setDashboard((current) => current ? { ...current, work_items: current.work_items.map((item) => item.id === updated.id ? updated : item) } : current);
  }

  async function createWorkFromDiagnosis(diagnosisId: string) {
    setCreatingDiagnosisId(diagnosisId); setDiagnosisError(null);
    try {
      await api.createWorkItemFromDiagnosis(dashboardId, diagnosisId);
      await refreshProject();
      window.location.hash = "work";
    } catch (reason) {
      setDiagnosisError(reason instanceof Error ? reason.message : "无法基于这条诊断创建优化工作。");
    } finally { setCreatingDiagnosisId(null); }
  }

  async function verifyCycle() {
    if (!currentCycle) return;
    setVerifying(true); setActionError(null);
    try {
      await api.verifyCycle(dashboardId, currentCycle.id);
      setDashboard(await api.project(dashboardId));
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : "复测未能完成。");
    } finally { setVerifying(false); }
  }

  async function runTrackingPlan(planId: string) {
    setRunningPlanId(planId); setTrackingError(null);
    try {
      await api.runTrackingPlan(dashboardId, planId);
      setDashboard(await api.project(dashboardId));
    } catch (reason) {
      setTrackingError(reason instanceof Error ? reason.message : "追踪计划未能完成。");
    } finally { setRunningPlanId(null); }
  }

  function openTrackingComposer(promptSetId?: string) {
    const activePromptSet = dashboard?.prompt_sets.find((item) => item.active);
    setTrackingDraft((current) => ({ ...current, promptSetId: promptSetId ?? activePromptSet?.id ?? current.promptSetId }));
    setTrackingError(null);
    setShowTrackingComposer(true);
  }

  async function createTrackingPlan() {
    if (!trackingDraft.promptSetId || !trackingDraft.engineIds.length) { setTrackingError("请选择当前问题集和至少一个正式答案面。"); return; }
    setRunningPlanId("creating"); setTrackingError(null);
    try {
      await api.createTrackingPlan(dashboardId, { prompt_set_id: trackingDraft.promptSetId, engine_ids: trackingDraft.engineIds, samples: trackingDraft.samples, cadence: trackingDraft.cadence });
      await refreshProject();
      setShowTrackingComposer(false);
    } catch (reason) { setTrackingError(reason instanceof Error ? reason.message : "追踪计划创建失败。"); }
    finally { setRunningPlanId(null); }
  }

  async function refreshProject() { setDashboard(await api.project(dashboardId)); }

  async function saveAgentPolicy(enabled: boolean) {
    setAgentBusy(true); setAgentError(null);
    try {
      await api.saveAgentPolicy(dashboardId, {
        enabled,
        generation_engine: "deepseek",
        approval_required: true,
        max_actions_per_run: agentConfig.maxActions,
        per_run_budget: agentConfig.perRunBudget,
        monthly_budget: agentConfig.monthlyBudget,
        auto_plan_on_tracking: agentConfig.autoPlanOnTracking,
      });
      await refreshProject();
    } catch (reason) { setAgentError(reason instanceof Error ? reason.message : "Agent 策略保存失败。"); }
    finally { setAgentBusy(false); }
  }

  async function planAgentRun() {
    if (!activeCycle) return;
    setAgentBusy(true); setAgentError(null);
    try {
      await api.planAgentRun(dashboardId, { cycle_id: activeCycle.id, goal: "根据当前证据准备下一批优化草稿" });
      await refreshProject();
    } catch (reason) { setAgentError(reason instanceof Error ? reason.message : "Agent 计划生成失败。"); }
    finally { setAgentBusy(false); }
  }

  async function decideAgentRun(decision: "approve" | "reject" | "takeover") {
    if (!latestAgentRun) return;
    setAgentBusy(true); setAgentError(null);
    try { await api.decideAgentRun(dashboardId, latestAgentRun.id, decision); await refreshProject(); }
    catch (reason) { setAgentError(reason instanceof Error ? reason.message : "Agent 计划审批失败。"); }
    finally { setAgentBusy(false); }
  }

  async function executeAgentRun() {
    if (!latestAgentRun) return;
    setAgentBusy(true); setAgentError(null);
    try { await api.executeAgentRun(dashboardId, latestAgentRun.id); await refreshProject(); }
    catch (reason) { setAgentError(reason instanceof Error ? reason.message : "Agent 执行失败。"); }
    finally { setAgentBusy(false); }
  }

  function beginPromptSetVersion(promptSet: ProjectDashboard["prompt_sets"][number]) {
    setEditingPromptSetId(promptSet.id);
    setPromptSetDraft({ name: promptSet.name, prompts: promptSet.prompts.join("\n") });
    setPromptSetError(null);
  }

  async function savePromptSetVersion() {
    if (!editingPromptSetId) return;
    const prompts = promptSetDraft.prompts.split("\n").map((item) => item.trim()).filter(Boolean);
    if (!prompts.length) { setPromptSetError("至少保留一个问题。"); return; }
    setPromptSetBusy(true); setPromptSetError(null);
    try {
      await api.createPromptSetVersion(dashboardId, editingPromptSetId, { name: promptSetDraft.name.trim() || undefined, prompts });
      await refreshProject();
      setEditingPromptSetId(null);
    } catch (reason) { setPromptSetError(reason instanceof Error ? reason.message : "新版本保存失败。"); }
    finally { setPromptSetBusy(false); }
  }

  return <div className="project-shell">
    <div className="project-breadcrumb"><Link href="/projects">项目</Link><span>/</span><span>{dashboard.name}</span></div>

    <header className="project-header">
      <div><div className="project-status"><i />{dashboard.status === "active" ? "运行中" : dashboard.status}</div><h1>{dashboard.name}</h1><p>{dashboard.primary_domain || "尚未设置域名"} · {dashboard.locale}{lastUpdated ? ` · 更新于 ${formatTime(lastUpdated)}` : ""}</p></div>
      <div className="project-header-actions"><Link href={auditHref}>运行网站审计</Link><Link className="project-primary-action" href={trackHref}>运行可见度检测 <span>→</span></Link></div>
    </header>

    <nav className="project-nav" aria-label="项目导航"><a className="is-active" href="#overview">概览</a><a href="#visibility">可见度</a><a href="#diagnosis">诊断</a><a href="#questions">问题集</a><a href="#tracking">追踪计划</a><a href="#work">优化工作</a><a href="#agent">Agent</a><a href="#activity">活动</a></nav>

    <main id="overview" className="project-main">
      <section className="project-overview-grid">
        <article className="project-state-card">
          <div className="card-eyebrow"><span>当前状态</span><span>真实数据</span></div>
          <div className="state-score"><strong>{latestByEngine.length ? percent(latestByEngine.reduce((sum, item) => sum + item.entity_sov, 0) / latestByEngine.length) : "—"}</strong><div><h2>{latestByEngine.length ? latestByEngine.some((item) => item.entity_sov > 0) ? "品牌已进入部分 AI 回答" : "品牌尚未进入当前 AI 回答" : "等待建立第一条基线"}</h2><p>{latestByEngine.length ? `已覆盖 ${latestByEngine.length} 个真实答案面；最近一次共 ${latestVisibility?.output_summary.sample_count ?? 0} 个样本。` : "运行网站审计和 AI 可见度检测，建立项目现状。"}</p></div></div>
          <div className="state-metrics"><div><span>品牌提及率</span><b>{latestByEngine[0] ? percent(latestByEngine[0].entity_sov) : "—"}</b></div><div><span>自有域名引用率</span><b>{latestByEngine[0] ? percent(latestByEngine[0].citation_sov) : "—"}</b></div><div><span>正式答案面</span><b>{latestByEngine.length}</b></div></div>
        </article>

        <aside className="next-action-card"><span>{currentCycle ? `当前周期 · ${STAGE_LABEL[currentCycle.stage] ?? currentCycle.stage}` : "建议下一步"}</span><h2>{dashboard.diagnosis.insights.length ? "先审查证据诊断" : currentWork.length ? `${currentWork.filter((item) => item.status !== "done").length} 项工作待推进` : latestByEngine.length ? "建立第一个优化周期" : "完成项目基线"}</h2><p>{dashboard.diagnosis.insights.length ? "先确认每个缺口对应的问题、答案面和来源证据，再决定是否进入优化工作。" : currentCycle ? currentCycle.objective : "将审计、真实答案面、优化执行和复测放进同一个可验证周期。"}</p><Link href={dashboard.diagnosis.insights.length ? "#diagnosis" : currentWork.length ? "#work" : latestByEngine.length ? `/optimize?url=${encodeURIComponent(`https://${dashboard.primary_domain}`)}&brand=${encodeURIComponent(dashboard.name)}&project=${dashboard.id}` : trackHref}>{dashboard.diagnosis.insights.length ? "查看诊断依据" : currentWork.length ? "查看优化工作" : latestByEngine.length ? "启动优化周期" : "运行第一次检测"}<span>→</span></Link></aside>
      </section>

      <section id="visibility" className="project-section">
        <div className="project-section-head"><div><span>AI 可见度</span><h2>当前答案面表现</h2></div><p>基于每个引擎最近一次成功检测。</p></div>
        {latestByEngine.length ? <div className="visibility-summary-table"><div className="table-head"><span>答案面</span><span>品牌提及</span><span>域名引用</span><span>相对份额</span><span>样本</span></div>{latestByEngine.map((item) => <div className="table-row" key={item.engine_id}><strong>{item.surface_name || item.engine_id}</strong><span>{percent(item.entity_sov)}{confidenceRange(item.entity_ci_low, item.entity_ci_high) && <small>{confidenceRange(item.entity_ci_low, item.entity_ci_high)}</small>}</span><span>{percent(item.citation_sov)}{confidenceRange(item.citation_ci_low, item.citation_ci_high) && <small>{confidenceRange(item.citation_ci_low, item.citation_ci_high)}</small>}</span><span>{item.relative_sov === null ? "—" : percent(item.relative_sov)}{Object.entries(item.competitor_sov).map(([name, value]) => <small key={name}>{name} {percent(value)}</small>)}</span><span>{item.sample_size}</span></div>)}</div> : <div className="project-empty"><p>还没有正式可见度数据。运行一次已验收答案面检测后建立基线。</p><Link href={trackHref}>运行第一次检测 →</Link></div>}
      </section>

      <section id="diagnosis" className="project-section diagnosis-section">
        <div className="project-section-head"><div><span>证据诊断</span><h2>结果背后的具体缺口</h2></div><p>仅使用已认证答案面的原始样本；这是判断依据，不会自动替你创建或发布优化任务。</p></div>
        {dashboard.diagnosis.insights.length ? <><div className="diagnosis-meta"><span>{dashboard.diagnosis.qualified_run_count} 次正式检测 · {dashboard.diagnosis.qualified_sample_count} 个样本</span><b>{QUALITY_LABEL[dashboard.diagnosis.coverage_status] ?? "当前范围"}</b></div><div className="diagnosis-list">{dashboard.diagnosis.insights.map((insight) => <article key={insight.id} className={`diagnosis-card priority-${insight.priority}`}><header><span>{insight.priority === "high" ? "优先处理" : "需要复核"}</span><div><b>{insight.engine_id}</b><small>{INTENT_LABEL[insight.prompt_intent] ?? insight.prompt_intent}问题 · {insight.sample_size} 个样本</small></div></header><h3>{insight.title}</h3><p className="diagnosis-question">{insight.prompt_text}</p><p>{insight.detail}</p><div className="diagnosis-facts"><span>品牌 {insight.brand_mentions}/{insight.sample_size}</span><span>自有域名引用 {insight.own_domain_citations}/{insight.sample_size}</span>{Object.entries(insight.competitor_mentions).map(([name, count]) => <span key={name}>{name} {count}/{insight.sample_size}</span>)}</div><details><summary>查看依据 <span>↓</span></summary><div className="diagnosis-evidence">{insight.cited_urls.length ? <ul>{insight.cited_urls.map((url) => <li key={url}><a href={url} target="_blank" rel="noreferrer">{url}</a></li>)}</ul> : <p>该答案没有返回可访问来源链接；可到下方活动记录查看原始回答。</p>}<a href="#activity">在项目活动中查看原始回答 →</a></div></details><button className="diagnosis-create-work" type="button" onClick={() => void createWorkFromDiagnosis(insight.id)} disabled={creatingDiagnosisId !== null}>{creatingDiagnosisId === insight.id ? "正在建立工作…" : "基于此证据建立优化工作 →"}</button></article>)}</div></> : <div className="project-empty"><p>{dashboard.diagnosis.warnings[0] ?? "当前没有需要提示的正式样本缺口。"}</p>{latestByEngine.length ? <a href="#activity">查看本次原始证据 →</a> : <Link href={trackHref}>运行已认证答案面检测 →</Link>}</div>}
        {dashboard.diagnosis.warnings.length > 0 && <div className="diagnosis-warnings">{dashboard.diagnosis.warnings.map((warning) => <p key={warning}>{warning}</p>)}</div>}
        {diagnosisError && <p className="cycle-action-error" role="alert">{diagnosisError}</p>}
      </section>

      <section id="work" className="project-section">
        <div className="project-section-head"><div><span>优化工作</span><h2>{currentCycle?.name ?? "从观测进入行动"}</h2></div><p>这些工作来自真实审计与观测，可由用户、团队或 Agent 共享执行，完成后回到同一周期复测。</p></div>
        {currentWork.length ? <div className="work-item-table">{currentWork.map((item) => <article key={item.id} className={`work-item-row is-${item.status}`}><span className={`severity severity-${item.priority}`}>{item.priority === "high" ? "高" : item.priority === "medium" ? "中" : "低"}</span><div><h3><Link href={`/projects/${dashboard.id}/work/${item.id}`}>{item.title}</Link></h3><p>{item.detail}</p><small>{item.category} · 基线 {String(item.evidence_snapshot.baseline_score ?? "—")} 分</small></div><select aria-label={`${item.title}状态`} value={item.status} disabled={item.status === "done"} onChange={(event) => void updateWork(item.id, event.target.value as "open" | "in_progress" | "review")}><option value="open">待处理</option><option value="in_progress">进行中</option><option value="review">待审批</option>{item.status === "done" && <option value="done">已完成</option>}</select></article>)}</div> : <div className="project-empty"><p>尚未建立优化周期。运行完整工作包后，审计结果会成为这里的可执行工作。</p><Link href={`/optimize?url=${encodeURIComponent(`https://${dashboard.primary_domain}`)}&brand=${encodeURIComponent(dashboard.name)}&project=${dashboard.id}`}>启动第一个周期 →</Link></div>}
      </section>

      {currentCycle && <section id="cycle-result" className="project-section cycle-result-section">
        <div className="project-section-head"><div><span>周期验证</span><h2>{currentCycle.stage === "complete" ? "基线与复测结果" : "用原测量方法验证改变"}</h2></div><p>系统会自动复用本周期的问题、引擎和采样次数，不会把不同测量范围强行比较。</p></div>
        {currentCycle.verification_summary.engines?.length ? <><div className="cycle-comparison-table"><div className="cycle-comparison-head"><span>引擎</span><span>品牌提及</span><span>域名引用</span><span>判定</span></div>{currentCycle.verification_summary.engines.map((result) => <div className="cycle-comparison-row" key={result.engine_id}><strong>{result.engine_id}</strong><span>{percent(result.baseline.entity_sov)} → {percent(result.verification.entity_sov)} <small>{signedPercent(result.entity_delta)}</small></span><span>{percent(result.baseline.citation_sov)} → {percent(result.verification.citation_sov)} <small>{signedPercent(result.citation_delta)}</small></span><span><b className={`assessment assessment-${result.entity_assessment}`}>{ASSESSMENT_LABEL[result.entity_assessment]}</b><small>提及 / {ASSESSMENT_LABEL[result.citation_assessment]} 引用</small></span></div>)}</div>{currentCycle.verification_summary.changes?.length ? <div className="cycle-change-log"><span>本轮实际改动</span>{currentCycle.verification_summary.changes.map((change) => <div key={`${change.artifact_id}-${change.published_at}`}><strong>{change.work_item_title}</strong><p>{change.notes || "已记录实施"}</p>{change.target_url && (isWebUrl(change.target_url) ? <a href={change.target_url} target="_blank" rel="noreferrer">{change.target_url}</a> : <code>{change.target_url}</code>)}</div>)}</div> : null}</> : <div className="cycle-verify-action"><div><strong>{currentCycle.measurement_config.questions?.length ?? 0} 个原问题</strong><span>{currentCycle.measurement_config.engine_ids?.join("、") || "原引擎"} · 每题 {currentCycle.measurement_config.samples ?? "—"} 次</span></div><button type="button" onClick={() => void verifyCycle()} disabled={verifying}>{verifying ? "正在复用基线采样…" : "复测本周期"}</button></div>}
        {actionError && <p className="cycle-action-error" role="alert">{actionError}</p>}
      </section>}

      <section id="questions" className="project-section prompt-set-section">
        <div className="project-section-head"><div><span>测量问题集</span><h2>问题范围是可版本化资产</h2></div><p>每次编辑都会创建新版本；已有追踪计划继续锁定原问题，历史趋势不会被改写。</p></div>
        {dashboard.prompt_sets.length ? <div className="prompt-set-list">{dashboard.prompt_sets.map((promptSet) => <article key={promptSet.id} data-prompt-set-id={promptSet.id} className={`prompt-set-card${promptSet.active ? " is-active" : ""}`}><header><div><span>{promptSet.active ? "当前版本" : "历史版本"}</span><h3>{promptSet.name} <small>v{promptSet.version}</small></h3></div><div className="prompt-card-actions"><button type="button" onClick={() => beginPromptSetVersion(promptSet)} disabled={promptSetBusy}>基于此版本编辑</button>{promptSet.active && <button data-testid={`track-prompt-set-${promptSet.id}`} type="button" onClick={() => openTrackingComposer(promptSet.id)}>用于追踪计划</button>}</div></header><div className="prompt-intent-coverage">{Object.entries(promptSet.measurement_quality.coverage).map(([intent, count]) => <span className={count > 0 ? "is-covered" : ""} key={intent}>{INTENT_LABEL[intent] ?? intent} {count}</span>)}</div><ol>{promptSet.prompt_items.map((item) => <li key={item.id}><b>{INTENT_LABEL[item.intent]}</b><span>{item.text}</span></li>)}</ol>{promptSet.measurement_quality.warnings.length > 0 && <p className="measurement-warning">{promptSet.measurement_quality.warnings.join("；")}</p>}</article>)}</div> : <div className="project-empty"><p>尚未保存问题集。</p><Link href={trackHref}>先建立第一组测量问题 →</Link></div>}
        {editingPromptSetId && <div className="prompt-set-editor"><div><span>创建新版本</span><strong>历史版本不会被修改</strong></div><label><span>问题集名称</span><input value={promptSetDraft.name} onChange={(event) => setPromptSetDraft((current) => ({ ...current, name: event.target.value }))} /></label><label><span>问题（每行一个）</span><textarea value={promptSetDraft.prompts} onChange={(event) => setPromptSetDraft((current) => ({ ...current, prompts: event.target.value }))} /></label><footer><button type="button" onClick={() => setEditingPromptSetId(null)} disabled={promptSetBusy}>取消</button><button className="agent-primary-button" type="button" onClick={() => void savePromptSetVersion()} disabled={promptSetBusy}>{promptSetBusy ? "正在保存…" : "保存为新版本"}</button></footer>{promptSetError && <p className="cycle-action-error" role="alert">{promptSetError}</p>}</div>}
      </section>

      <section id="tracking" className="project-section">
        <div className="project-section-head"><div><span>追踪计划</span><h2>持续观测范围</h2></div><div><p>基于保存的问题集、引擎和频率，形成可复测的观测范围。</p>{dashboard.prompt_sets.some((item) => item.active) && <button className="tracking-create-button" type="button" onClick={() => openTrackingComposer()}>新建追踪计划</button>}</div></div>
        {showTrackingComposer && <div className="tracking-composer"><label><span>当前问题集</span><select value={trackingDraft.promptSetId} onChange={(event) => setTrackingDraft((current) => ({ ...current, promptSetId: event.target.value }))}>{dashboard.prompt_sets.filter((item) => item.active).map((item) => <option key={item.id} value={item.id}>{item.name} · v{item.version}</option>)}</select></label><label><span>采样次数</span><input type="number" min={1} max={20} value={trackingDraft.samples} onChange={(event) => setTrackingDraft((current) => ({ ...current, samples: Number(event.target.value) || 1 }))} /></label><label><span>频率</span><select value={trackingDraft.cadence} onChange={(event) => setTrackingDraft((current) => ({ ...current, cadence: event.target.value }))}><option value="weekly">每周</option><option value="daily">每日</option><option value="monthly">每月</option><option value="manual">手动</option></select></label><fieldset><legend>正式答案面</legend>{availableEngines.map((engine) => <label key={engine.id}><input type="checkbox" checked={trackingDraft.engineIds.includes(engine.id)} onChange={(event) => setTrackingDraft((current) => ({ ...current, engineIds: event.target.checked ? [...current.engineIds, engine.id] : current.engineIds.filter((id) => id !== engine.id) }))} />{engine.display_name}</label>)}</fieldset><footer><button type="button" onClick={() => setShowTrackingComposer(false)} disabled={runningPlanId === "creating"}>取消</button><button className="agent-primary-button" type="button" onClick={() => void createTrackingPlan()} disabled={runningPlanId === "creating"}>{runningPlanId === "creating" ? "正在创建…" : "保存追踪计划"}</button></footer></div>}
        {dashboard.tracking_plans.length ? <div className="tracking-plan-list">{dashboard.tracking_plans.map((plan) => { const trends = planTrend(dashboard.visibility, plan.id); return <article key={plan.id} className="tracking-plan-row"><div><span>{CADENCE_LABEL[plan.cadence] ?? plan.cadence} · {QUALITY_LABEL[plan.measurement_quality.status] ?? plan.measurement_quality.status}</span><h3>{plan.prompt_set_name}</h3><p>{plan.question_count} 个问题 · {plan.engine_ids.join("、")} · 每题 {plan.samples} 次</p><div className="prompt-intent-coverage">{Object.entries(plan.measurement_quality.coverage).map(([intent, count]) => <span className={count > 0 ? "is-covered" : ""} key={intent}>{INTENT_LABEL[intent] ?? intent} {count}</span>)}</div>{plan.measurement_quality.warnings.length > 0 && <p className="measurement-warning">{plan.measurement_quality.warnings.join("；")}</p>}{trends.length > 0 && <div className="tracking-mini-trend">{trends.map(({ engineId, latest, previous }) => <span key={engineId}><b>{engineId}</b>{percent(latest.entity_sov)}{previous ? <small className={latest.entity_sov >= previous.entity_sov ? "trend-up" : "trend-down"}>{signedPercent(latest.entity_sov - previous.entity_sov)}</small> : <small>首次基线</small>}</span>)}</div>}</div><div><b>{plan.last_error ? `运行异常 · ${plan.consecutive_failures}` : plan.status === "active" ? "运行中" : plan.status}</b><small>{plan.last_run_at ? `上次 ${formatTime(plan.last_run_at)}` : "尚未自动执行"}</small><small>{plan.next_run_at ? `下次 ${formatTime(plan.next_run_at)}` : "手动计划"}</small><button type="button" onClick={() => void runTrackingPlan(plan.id)} disabled={runningPlanId !== null}>{runningPlanId === plan.id ? "正在运行…" : "立即运行"}</button></div></article>; })}</div> : <div className="project-empty"><p>还没有持续追踪计划。</p><Link href={trackHref}>保存第一组追踪问题 →</Link></div>}
        {trackingError && <p className="cycle-action-error" role="alert">{trackingError}</p>}
      </section>

      <section id="agent" className="project-section agent-control-section">
        <div className="project-section-head"><div><span>Agent 托管执行</span><h2>在预算和审批内工作</h2></div><p>Agent 只能从当前周期的真实证据和工作项出发，生成新草稿版本；不能自行审批或发布。</p></div>
        <div className="agent-control-grid">
          <aside className="agent-policy-card"><div><span>执行策略</span><b>{dashboard.agent_policy?.enabled ? "已启用" : "未启用"}</b></div><label><span>单次最多动作</span><input type="number" min={1} max={20} value={agentConfig.maxActions} onChange={(event) => setAgentConfig((current) => ({ ...current, maxActions: Number(event.target.value) || 1 }))} /></label><label><span>单次预算（USD）</span><input type="number" min={0} step="0.01" value={agentConfig.perRunBudget} onChange={(event) => setAgentConfig((current) => ({ ...current, perRunBudget: Number(event.target.value) || 0 }))} /></label><label><span>每月预算（USD）</span><input type="number" min={0} step="0.1" value={agentConfig.monthlyBudget} onChange={(event) => setAgentConfig((current) => ({ ...current, monthlyBudget: Number(event.target.value) || 0 }))} /></label><label><span>追踪后自动提案</span><input type="checkbox" checked={agentConfig.autoPlanOnTracking} onChange={(event) => setAgentConfig((current) => ({ ...current, autoPlanOnTracking: event.target.checked }))} /></label><div className="agent-policy-facts"><span>DeepSeek 生成</span><span>强制人工审批</span><span>禁止直接发布</span></div><button type="button" onClick={() => void saveAgentPolicy(!dashboard.agent_policy?.enabled)} disabled={agentBusy}>{dashboard.agent_policy?.enabled ? "暂停 Agent" : "启用 Agent"}</button>{dashboard.agent_policy?.enabled && <button className="agent-secondary-button" type="button" onClick={() => void saveAgentPolicy(true)} disabled={agentBusy}>保存策略</button>}</aside>

          <div className="agent-run-card">{!dashboard.agent_policy?.enabled ? <div className="agent-empty"><span>01</span><h3>先确定 Agent 边界</h3><p>启用后 Agent 才能读取当前周期并提交计划。</p></div> : !latestAgentRun ? <div className="agent-empty"><span>02</span><h3>让 Agent 提交第一份计划</h3><p>{activeCycle ? "它会选择当前周期中最高优先级的可编辑草稿。" : "需要先建立一个活跃优化周期。"}</p><button type="button" onClick={() => void planAgentRun()} disabled={agentBusy || !activeCycle}>生成 Agent 计划</button></div> : <div className="agent-run-detail"><header><div><span>{latestAgentRun.trigger === "tracking" ? "追踪自动提案" : "Agent 运行"}</span><h3>{latestAgentRun.goal}</h3></div><div><b>{latestAgentRun.status}</b><small>预估 ${latestAgentRun.estimated_cost.toFixed(2)} · 实际 ${latestAgentRun.actual_cost.toFixed(2)}</small><small>尝试 {latestAgentRun.attempt_count}/{latestAgentRun.max_attempts}{latestAgentRun.next_attempt_at ? ` · ${formatTime(latestAgentRun.next_attempt_at)} 重试` : ""}</small></div></header><div className="agent-action-list">{latestAgentRun.actions.map((action) => <div key={action.id}><i className={`status-${action.status}`} /><div><strong>{action.work_item_title}</strong><p>{action.rationale}</p><small>{action.status} · ${action.estimated_cost.toFixed(2)}</small></div>{action.output_artifact_id && <Link href={`/projects/${dashboard.id}/work/${action.work_item_id}`}>审查草稿 →</Link>}</div>)}</div><footer>{latestAgentRun.status === "awaiting_approval" && <><button type="button" onClick={() => void decideAgentRun("reject")} disabled={agentBusy}>拒绝计划</button><button className="agent-primary-button" type="button" onClick={() => void decideAgentRun("approve")} disabled={agentBusy}>批准计划</button></>}{latestAgentRun.status === "approved" && <button className="agent-primary-button" type="button" onClick={() => void executeAgentRun()} disabled={agentBusy}>执行并生成草稿</button>}{["approved", "running", "retry_scheduled", "partial", "failed"].includes(latestAgentRun.status) && <button type="button" onClick={() => void decideAgentRun("takeover")} disabled={agentBusy}>人工接管</button>}{["done", "partial", "failed", "rejected", "taken_over"].includes(latestAgentRun.status) && activeCycle && <button type="button" onClick={() => void planAgentRun()} disabled={agentBusy}>提交新计划</button>}</footer></div>}</div>
        </div>
        {agentError && <p className="cycle-action-error" role="alert">{agentError}</p>}
      </section>

      <section id="activity" className="project-section activity-section">
        <div className="project-section-head"><div><span>项目活动</span><h2>发生了什么</h2></div><p>检测、优化、审批与 Agent 执行都会按时间记录在这里。</p></div>
        {dashboard.activities.length ? <div className="activity-list">{dashboard.activities.map((activity) => <ActivityItem key={activity.id} activity={activity} evidence={dashboard.evidence.filter((item) => item.activity_id === activity.id)} />)}</div> : <div className="project-empty"><p>项目还没有活动。</p></div>}
      </section>
    </main>
  </div>;
}

function ActivityItem({ activity, evidence }: { activity: ProjectActivity; evidence: CitationEvidence[] }) {
  const questions = activity.input_snapshot.questions ?? [];
  const engineIds = activity.input_snapshot.engine_ids ?? [];
  return <article className="activity-item">
    <div className="activity-rail"><i className={`status-${activity.status}`} /><span /></div>
    <div className="activity-content">
      <header><div><span>{ACTIVITY_LABEL[activity.kind] ?? activity.kind}</span><h3>{activity.title}</h3></div><time>{formatTime(activity.started_at)}</time></header>
      <div className="activity-facts">
        {questions.length > 0 && <span>{questions.length} 个问题</span>}
        {engineIds.length > 0 && <span>{engineIds.join("、")}</span>}
        {activity.input_snapshot.samples_per_question && <span>每题 {activity.input_snapshot.samples_per_question} 次采样</span>}
        {activity.output_summary.sample_count !== undefined && <span>{activity.output_summary.sample_count} 个结果</span>}
        {activity.output_summary.total_score !== undefined && <span>GEO 得分 {activity.output_summary.total_score}</span>}
        <span>{activity.status === "done" ? "已完成" : activity.status === "partial" ? "部分完成" : activity.status === "failed" ? "失败" : "进行中"}</span>
      </div>
      {questions.length > 0 ? <details className="activity-details"><summary>查看本次输入与结果 <span>↓</span></summary><div className="activity-question-list">{questions.map((question, index) => {
        const samples = evidence.filter((item) => item.prompt_text === question);
        return <div key={question}><b>{index + 1}</b><p>{question}</p><span>{samples.length} 个回答 · {samples.filter((item) => item.brand_mentioned).length} 次提及 · {new Set(samples.flatMap((item) => item.cited_urls)).size} 个来源</span>{samples.length > 0 && <details><summary>原始证据</summary><EvidenceSamples samples={samples} /></details>}</div>;
      })}</div></details> : activity.kind === "visibility" && <p className="legacy-note">这次历史检测发生在输入快照上线前，结果与证据仍保留，但当时的问题原文无法恢复。</p>}
    </div>
  </article>;
}

function EvidenceSamples({ samples }: { samples: CitationEvidence[] }) {
  return <div className="evidence-samples">{samples.map((sample, index) => <details key={`${sample.request_id}-${index}`}><summary>样本 {index + 1} · {sample.cited_urls.length} 个来源</summary><p>{sample.answer_text}</p>{sample.cited_urls.length > 0 && <ul>{sample.cited_urls.map((url) => <li key={url}><a href={url} target="_blank" rel="noreferrer">{url}</a></li>)}</ul>}</details>)}</div>;
}

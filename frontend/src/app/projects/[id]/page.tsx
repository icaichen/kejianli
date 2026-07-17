"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api, type BrandFact, type BrandFactType, type CitationEvidence, type EngineInfo, type ProjectActivity, type ProjectDashboard, type ResearchReport, type VisibilitySnapshot } from "@/lib/api";

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
const ASSESSMENT_LABEL: Record<string, string> = { improved: "明确提升", declined: "明确下降", unchanged: "无变化", uncertain: "暂不能判断", not_comparable: "范围已变化" };
const INTENT_LABEL: Record<string, string> = { branded: "品牌", category: "品类", problem: "问题", comparison: "比较" };
const QUALITY_LABEL: Record<string, string> = { comprehensive: "覆盖完整", balanced: "覆盖较均衡", limited: "覆盖有限" };
const FACT_TYPE_LABEL: Record<BrandFactType, string> = { product: "产品能力", audience: "适用对象", proof: "证明与数据", pricing: "价格", limitation: "局限", policy: "政策" };
const PROJECT_VIEWS = [
  { id: "overview", label: "市场概览" },
  { id: "visibility", label: "答案证据" },
  { id: "report", label: "研究报告" },
  { id: "optimization", label: "研究行动" },
  { id: "tracking", label: "研究设计" },
  { id: "activity", label: "运行记录" },
] as const;
type ProjectView = (typeof PROJECT_VIEWS)[number]["id"];

function isProjectView(value: string | null): value is ProjectView {
  return PROJECT_VIEWS.some((view) => view.id === value);
}

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
    return { engineId, latest: ordered[0] };
  });
}
function latestSnapshotsByEngine(snapshots: VisibilitySnapshot[]) {
  const latest = new Map<string, VisibilitySnapshot>();
  for (const snapshot of snapshots.filter((item) => item.scope_current).sort((a, b) => Date.parse(b.period) - Date.parse(a.period))) {
    if (!latest.has(snapshot.engine_id)) latest.set(snapshot.engine_id, snapshot);
  }
  return Array.from(latest.values());
}
function formatTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}
function formatDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "long", day: "numeric" }).format(new Date(value));
}
function averageRate(snapshots: VisibilitySnapshot[], key: "entity_sov" | "citation_sov") {
  if (!snapshots.length) return 0;
  return snapshots.reduce((sum, item) => sum + item[key], 0) / snapshots.length;
}
function competitiveRanking(brandName: string, snapshots: VisibilitySnapshot[]) {
  const totals = new Map<string, { sum: number; count: number; isBrand: boolean }>();
  totals.set(brandName, { sum: averageRate(snapshots, "entity_sov") * Math.max(snapshots.length, 1), count: Math.max(snapshots.length, 1), isBrand: true });
  for (const snapshot of snapshots) {
    for (const [name, value] of Object.entries(snapshot.competitor_sov)) {
      const current = totals.get(name) ?? { sum: 0, count: 0, isBrand: false };
      totals.set(name, { sum: current.sum + value, count: current.count + 1, isBrand: false });
    }
  }
  return Array.from(totals.entries())
    .map(([name, value]) => ({ name, rate: value.count ? value.sum / value.count : 0, isBrand: value.isBrand }))
    .sort((a, b) => b.rate - a.rate);
}
function statusHeadline(brandName: string, entityRate: number, hasData: boolean) {
  if (!hasData) return { title: "还不知道品牌在 AI 答案里的位置", detail: "补齐研究范围后，一键测量即可看到提及率、竞品排名和引用来源。" };
  if (entityRate <= 0) return { title: `${brandName} 几乎未出现在当前 AI 答案中`, detail: "在已测问题里品牌提及很低；优先看品类与需求类问题的竞品被推荐原因。" };
  if (entityRate < 0.2) return { title: `${brandName} 偶有出现，但市场声量偏弱`, detail: "已进入部分答案，但份额不高；对照竞品与来源结构找差距。" };
  if (entityRate < 0.45) return { title: `${brandName} 已有可见度，仍有提升空间`, detail: "品牌会被提到，但尚未稳定成为首选推荐。关注缺席的问题类型。" };
  return { title: `${brandName} 在当前样本中表现较强`, detail: "保持同一问题集与答案面复测，观察份额是否可复现、可维持。" };
}

export default function ProjectDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestedView = searchParams.get("view");
  const isWelcome = searchParams.get("welcome") === "1";
  const activeView: ProjectView = isProjectView(requestedView) ? requestedView : "overview";
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
  const [researchReport, setResearchReport] = useState<ResearchReport | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);
  const [briefEditing, setBriefEditing] = useState(false);
  const [briefBusy, setBriefBusy] = useState(false);
  const [briefError, setBriefError] = useState<string | null>(null);
  const [briefDraft, setBriefDraft] = useState({ brandName: "", domain: "", market: "", category: "", competitors: "", objective: "" });
  const [brandFacts, setBrandFacts] = useState<BrandFact[]>([]);
  const [factDraft, setFactDraft] = useState<{ factType: BrandFactType; claim: string; sourceUrl: string }>({ factType: "product", claim: "", sourceUrl: "" });
  const [factBusy, setFactBusy] = useState(false);
  const [factError, setFactError] = useState<string | null>(null);
  const [baselineBusy, setBaselineBusy] = useState(false);
  const [baselineError, setBaselineError] = useState<string | null>(null);

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

  useEffect(() => {
    if (!dashboard || activeView !== "report") return;
    setReportLoading(true);
    setReportError(null);
    void api.researchReport(dashboard.id).then(setResearchReport).catch((reason: unknown) => {
      setReportError(reason instanceof Error ? reason.message : "研究报告无法读取。");
    }).finally(() => setReportLoading(false));
  }, [activeView, dashboard]);

  useEffect(() => {
    if (!dashboard?.id || activeView !== "optimization") return;
    void api.brandFacts(dashboard.id).then(setBrandFacts).catch((reason: unknown) => {
      setFactError(reason instanceof Error ? reason.message : "品牌事实无法读取。");
    });
  }, [activeView, dashboard?.id]);

  if (error) return <div className="project-shell"><div className="error-banner" role="alert"><strong>项目无法打开</strong><p>{error}</p><Link href="/projects">返回项目列表</Link></div></div>;
  if (!dashboard) return <div className="project-shell"><div className="projects-loading">正在读取项目状态…</div></div>;

  const latestByEngine = latestSnapshotsByEngine(dashboard.visibility);
  const latestVisibility = dashboard.activities.find((activity) => activity.kind === "visibility" && Number(activity.input_snapshot.brief_version ?? 1) === dashboard.brief_version);
  const currentCycle = dashboard.cycles.find((cycle) => cycle.status === "active") ?? dashboard.cycles[0];
  const activeCycle = dashboard.cycles.find((cycle) => cycle.status === "active");
  const currentWork = currentCycle ? dashboard.work_items.filter((item) => item.cycle_id === currentCycle.id && item.status !== "dismissed") : [];
  const dashboardId = dashboard.id;
  const lastUpdated = dashboard.activities[0]?.started_at;
  const trackHref = `/visibility?domain=${encodeURIComponent(dashboard.primary_domain)}&brand=${encodeURIComponent(dashboard.brand_name)}&project=${dashboard.id}`;
  const latestAgentRun = dashboard.agent_runs[0];
  const viewHref = (view: ProjectView) => view === "overview"
    ? `/projects/${dashboard.id}`
    : `/projects/${dashboard.id}?view=${view}`;
  const hasVisibility = latestByEngine.length > 0;
  const hasInsights = dashboard.diagnosis.qualified_sample_count > 0;
  const hasTracking = dashboard.tracking_plans.some((plan) => plan.scope_current && plan.status === "active");
  const briefComplete = dashboard.brief_ready;
  const avgEntitySov = averageRate(latestByEngine, "entity_sov");
  const avgCitationSov = averageRate(latestByEngine, "citation_sov");
  const ranking = competitiveRanking(dashboard.brand_name, latestByEngine);
  const brandRank = ranking.findIndex((item) => item.isBrand) + 1;
  const statusCopy = statusHeadline(dashboard.brand_name, avgEntitySov, hasVisibility);
  const comparableDeltas = latestByEngine.filter((item) => item.comparison_status === "comparable" && item.entity_delta !== null);
  const avgEntityDelta = comparableDeltas.length
    ? comparableDeltas.reduce((sum, item) => sum + (item.entity_delta ?? 0), 0) / comparableDeltas.length
    : null;
  const topInsights = dashboard.diagnosis.insights.slice(0, 3);
  const journeySteps = [
    { label: "研究范围", detail: briefComplete ? `${dashboard.market} · ${dashboard.category}` : "补齐品类、目标与竞品", complete: briefComplete },
    { label: "AI 市场基线", detail: "测量品牌、竞品与引用来源", complete: briefComplete && hasVisibility },
    { label: "竞争洞察", detail: "解释品牌为何出现或缺席", complete: briefComplete && hasVisibility && hasInsights },
    { label: "持续追踪", detail: "固定口径并观察市场变化", complete: briefComplete && hasTracking },
  ];
  const currentJourneyIndex = journeySteps.findIndex((step) => !step.complete);
  const canMeasureNow = briefComplete || hasTracking;
  const nextAction = !briefComplete
    ? { eyebrow: "第 1 步 · 研究范围", title: "先明确我们正在研究哪个市场问题", detail: "品类、竞品和研究目标会直接决定问题集；范围含糊时，AI 答案也会偏离真实产品。", href: "#research-brief", label: "完善研究范围", action: "brief" as const }
    : !hasVisibility
    ? { eyebrow: "第 2 步 · 立刻看清现状", title: `一键测量 ${dashboard.brand_name} 在 AI 答案中的位置`, detail: `用默认企业问题框架，在已验收答案面上采样，得到品牌提及、竞品排名与引用来源。`, href: trackHref, label: baselineBusy ? "正在测量…" : "一键测量市场位置", action: "measure" as const }
    : !hasInsights
      ? { eyebrow: "第 3 步 · 竞争洞察", title: "从答案证据解释市场差距", detail: "按问题意图、答案面和来源查看品牌为何出现、竞品为何被推荐，以及当前样本范围的限制。", href: viewHref("visibility"), label: "审阅答案证据", action: "link" as const }
      : !hasTracking
        ? { eyebrow: "第 4 步 · 持续追踪", title: "固定研究口径，开始观察变化", detail: "保存问题集、答案面、采样次数和频率，让后续结果可以与本次基线直接比较。", href: viewHref("tracking"), label: "建立持续追踪", action: "link" as const }
        : { eyebrow: "更新现状", title: "用同一口径重新测量市场位置", detail: "复用当前追踪计划，刷新品牌份额、竞品排名与证据，形成可比较的变化。", href: viewHref("visibility"), label: baselineBusy ? "正在更新…" : "重新测量", action: "measure" as const };

  async function updateWork(itemId: string, status: "open" | "in_progress" | "review" | "done" | "dismissed") {
    const updated = await api.updateWorkItem(dashboard!.id, itemId, { status });
    setDashboard((current) => current ? { ...current, work_items: current.work_items.map((item) => item.id === updated.id ? updated : item) } : current);
  }

  async function createWorkFromDiagnosis(diagnosisId: string) {
    setCreatingDiagnosisId(diagnosisId); setDiagnosisError(null);
    try {
      await api.createWorkItemFromDiagnosis(dashboardId, diagnosisId);
      await refreshProject();
      router.push(viewHref("optimization"));
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
    const activePromptSet = dashboard?.prompt_sets.find((item) => item.active && item.scope_current);
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

  async function measureCompanyStatus() {
    setBaselineBusy(true);
    setBaselineError(null);
    try {
      const existingPlan = dashboard?.tracking_plans.find((plan) => plan.scope_current && plan.status === "active");
      if (existingPlan) {
        await api.runTrackingPlan(dashboardId, existingPlan.id);
        await refreshProject();
        return;
      }
      if (!dashboard?.brief_ready) {
        throw new Error("请先补齐研究 Brief（品牌、市场、品类、竞品、研究目标），再测量市场位置。");
      }
      const engines = availableEngines.length
        ? availableEngines
        : (await api.engines()).filter((engine) => engine.report_eligible);
      if (!engines.length) {
        throw new Error("当前没有已验收的正式答案面。请先配置并验收 Provider（如千问联网、百度智能搜索）。");
      }
      let promptSetId = dashboard.prompt_sets.find((item) => item.active && item.scope_current)?.id;
      if (!promptSetId) {
        const framework = await api.questionFramework(dashboardId);
        const prompts = framework.items.filter((item) => item.selected).map((item) => item.text.trim()).filter(Boolean);
        if (!prompts.length) throw new Error("问题框架为空。请完善品类与竞品后再试。");
        const promptSet = await api.createPromptSet(dashboardId, {
          name: `企业研究基线 ${new Date().toLocaleDateString("zh-CN")}`,
          prompts,
          kind: "tracking",
        });
        promptSetId = promptSet.id;
      }
      const plan = await api.createTrackingPlan(dashboardId, {
        prompt_set_id: promptSetId,
        engine_ids: engines.map((engine) => engine.id),
        samples: 3,
        cadence: "weekly",
      });
      await api.runTrackingPlan(dashboardId, plan.id);
      await refreshProject();
    } catch (reason) {
      setBaselineError(reason instanceof Error ? reason.message : "市场测量未能完成。");
    } finally {
      setBaselineBusy(false);
    }
  }

  async function addBrandFact() {
    if (!factDraft.claim.trim() || !factDraft.sourceUrl.trim()) {
      setFactError("请填写可验证的事实和公开来源链接。");
      return;
    }
    setFactBusy(true); setFactError(null);
    try {
      await api.createBrandFact(dashboardId, {
        fact_type: factDraft.factType,
        claim: factDraft.claim.trim(),
        source_url: factDraft.sourceUrl.trim(),
      });
      setBrandFacts(await api.brandFacts(dashboardId));
      setFactDraft((current) => ({ ...current, claim: "", sourceUrl: "" }));
    } catch (reason) {
      setFactError(reason instanceof Error ? reason.message : "事实保存失败。");
    } finally { setFactBusy(false); }
  }

  async function rejectBrandFact(factId: string) {
    setFactBusy(true); setFactError(null);
    try {
      await api.updateBrandFact(dashboardId, factId, { status: "rejected" });
      setBrandFacts(await api.brandFacts(dashboardId));
    } catch (reason) {
      setFactError(reason instanceof Error ? reason.message : "事实状态更新失败。");
    } finally { setFactBusy(false); }
  }

  function beginBriefEdit() {
    setBriefDraft({
      brandName: dashboard!.brand_name,
      domain: dashboard!.primary_domain,
      market: dashboard!.market,
      category: dashboard!.category,
      competitors: dashboard!.competitors.join("\n"),
      objective: dashboard!.research_objective,
    });
    setBriefError(null);
    setBriefEditing(true);
  }

  async function saveBrief() {
    if (!briefDraft.brandName.trim() || !briefDraft.market.trim() || !briefDraft.category.trim() || !briefDraft.objective.trim()) {
      setBriefError("品牌、市场、品类和研究目标不能为空。");
      return;
    }
    setBriefBusy(true); setBriefError(null);
    try {
      await api.updateProject(dashboardId, {
        brand_name: briefDraft.brandName.trim(),
        primary_domain: briefDraft.domain.trim(),
        market: briefDraft.market.trim(),
        category: briefDraft.category.trim(),
        competitors: briefDraft.competitors.split(/[，,\n]/).map((item) => item.trim()).filter(Boolean),
        research_objective: briefDraft.objective.trim(),
      });
      await refreshProject();
      setBriefEditing(false);
    } catch (reason) {
      setBriefError(reason instanceof Error ? reason.message : "研究范围保存失败。");
    } finally { setBriefBusy(false); }
  }

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
      <div><div className="project-status"><i />{dashboard.status === "active" ? "研究进行中" : dashboard.status}</div><h1>{dashboard.name}</h1><p>{dashboard.client_name} · {dashboard.market} · {dashboard.category || "未设置品类"} · 核心品牌 {dashboard.brand_name}{lastUpdated ? ` · 更新于 ${formatTime(lastUpdated)}` : ""}</p></div>
      <div className="project-header-actions">
        {nextAction.action === "measure" ? (
          <button className="project-primary-action" type="button" onClick={() => void measureCompanyStatus()} disabled={baselineBusy || !canMeasureNow}>
            {nextAction.label} <span>→</span>
          </button>
        ) : nextAction.action === "brief" ? (
          <a className="project-primary-action" href={nextAction.href}>{nextAction.label} <span>→</span></a>
        ) : (
          <Link className="project-primary-action" href={nextAction.href}>{nextAction.label} <span>→</span></Link>
        )}
      </div>
    </header>

    <nav className="project-nav" aria-label="项目导航">{PROJECT_VIEWS.map((view) => <Link key={view.id} className={activeView === view.id ? "is-active" : ""} aria-current={activeView === view.id ? "page" : undefined} href={viewHref(view.id)}>{view.label}</Link>)}</nav>

    <main className="project-main">
      <div className={`project-view project-view-${activeView}`}>
      {activeView === "overview" && <>
      {isWelcome && <section className="project-welcome"><span>研究项目已创建</span><div><strong>先看清品牌在 AI 答案里的位置，再决定改什么。</strong><p>补齐研究范围后一键测量；结果会按同一口径保存，方便复测与汇报。</p></div></section>}

      <section className="project-overview-grid company-status-grid">
        <article className="project-state-card">
          <div className="card-eyebrow"><span>公司 AI 市场现状</span><span>{hasVisibility ? "基于最新正式样本" : "尚未测量"}</span></div>
          <div className="state-score">
            <strong>{hasVisibility ? percent(avgEntitySov) : "—"}</strong>
            <div>
              <h2>{statusCopy.title}</h2>
              <p>{hasVisibility
                ? `${statusCopy.detail} 已覆盖 ${latestByEngine.length} 个答案面；最近一次 ${latestVisibility?.output_summary.sample_count ?? 0} 个样本。`
                : statusCopy.detail}</p>
            </div>
          </div>
          <div className="state-metrics">
            <div><span>品牌提及率</span><b>{hasVisibility ? percent(avgEntitySov) : "—"}</b></div>
            <div><span>自有域名引用</span><b>{hasVisibility ? percent(avgCitationSov) : "—"}</b></div>
            <div><span>竞品排名</span><b>{hasVisibility && brandRank > 0 ? `第 ${brandRank} / ${ranking.length}` : "—"}</b></div>
            <div><span>相对上次</span><b>{avgEntityDelta === null ? "—" : signedPercent(avgEntityDelta)}</b></div>
          </div>
          {hasVisibility && ranking.length > 0 && (
            <div className="company-ranking" aria-label="品牌与竞品提及排名">
              <header><span>AI 答案提及排名</span><small>按当前答案面平均提及率</small></header>
              {ranking.slice(0, 6).map((item, index) => (
                <div className={`company-ranking-row${item.isBrand ? " is-brand" : ""}`} key={item.name}>
                  <b>{String(index + 1).padStart(2, "0")}</b>
                  <strong>{item.name}{item.isBrand ? " · 本品牌" : ""}</strong>
                  <div className="company-ranking-bar"><i style={{ width: `${Math.max(item.rate * 100, item.rate ? 4 : 0)}%` }} /></div>
                  <span>{percent(item.rate)}</span>
                </div>
              ))}
            </div>
          )}
          {!hasVisibility && (
            <div className="company-status-empty">
              <p>{briefComplete
                ? "研究范围已就绪。点击一键测量，系统会用企业问题框架在已验收答案面上采样。"
                : "还缺研究范围。先补齐品类、竞品和研究目标，否则测到的答案可能偏题。"}</p>
              {briefComplete ? (
                <button type="button" className="agent-primary-button" onClick={() => void measureCompanyStatus()} disabled={baselineBusy || !canMeasureNow}>
                  {baselineBusy ? "正在测量市场位置…" : "一键测量市场位置"}
                </button>
              ) : (
                <a className="agent-primary-button" href="#research-brief">去完善研究范围</a>
              )}
              <Link href={trackHref}>或手动设计问题与答案面 →</Link>
            </div>
          )}
          {baselineError && <p className="cycle-action-error" role="alert">{baselineError}</p>}
        </article>

        <aside className="next-action-card">
          <span>{nextAction.eyebrow}</span>
          <h2>{nextAction.title}</h2>
          <p>{nextAction.detail}</p>
          {nextAction.action === "measure" ? (
            <button type="button" onClick={() => void measureCompanyStatus()} disabled={baselineBusy || !canMeasureNow}>
              {nextAction.label}<span>→</span>
            </button>
          ) : nextAction.action === "brief" ? (
            <a href={nextAction.href}>{nextAction.label}<span>→</span></a>
          ) : (
            <Link href={nextAction.href}>{nextAction.label}<span>→</span></Link>
          )}
          {hasVisibility && (
            <div className="next-action-links">
              <Link href={viewHref("visibility")}>看答案证据</Link>
              <Link href={viewHref("report")}>打开研究报告</Link>
            </div>
          )}
        </aside>
      </section>

      {topInsights.length > 0 && (
        <section className="company-insight-strip">
          <div className="project-section-head">
            <div><span>现在该关注什么</span><h2>来自最新正式证据的优先信号</h2></div>
            <Link href={viewHref("visibility")}>全部诊断 →</Link>
          </div>
          <div className="company-insight-list">
            {topInsights.map((insight) => (
              <article key={insight.id}>
                <span>{insight.priority === "high" ? "优先" : "关注"} · {INTENT_LABEL[insight.prompt_intent] ?? insight.prompt_intent}</span>
                <strong>{insight.title}</strong>
                <p>{insight.detail}</p>
              </article>
            ))}
          </div>
        </section>
      )}

      <ol className="project-journey" aria-label="项目进度">
        {journeySteps.map((step, index) => <li key={step.label} className={step.complete ? "is-complete" : index === currentJourneyIndex ? "is-current" : "is-upcoming"}><span>{step.complete ? "✓" : String(index + 1).padStart(2, "0")}</span><div><strong>{step.label}</strong><p>{step.detail}</p></div></li>)}
      </ol>

      <section id="research-brief" className={`project-research-brief${briefComplete ? " is-complete" : " is-incomplete"}`}>
        <div className="project-section-head"><div><span>研究 Brief</span><h2>{briefComplete ? "当前研究范围" : "先固定研究对象与商业问题"}</h2></div>{!briefEditing && <button type="button" onClick={beginBriefEdit}>{briefComplete ? "编辑研究范围" : "完善研究范围"}</button>}</div>
        {briefEditing ? <div className="research-brief-form">
          <label><span>核心品牌</span><input value={briefDraft.brandName} onChange={(event) => setBriefDraft((current) => ({ ...current, brandName: event.target.value }))} /></label>
          <label><span>品牌域名</span><input value={briefDraft.domain} onChange={(event) => setBriefDraft((current) => ({ ...current, domain: event.target.value }))} /></label>
          <label><span>研究市场</span><input value={briefDraft.market} onChange={(event) => setBriefDraft((current) => ({ ...current, market: event.target.value }))} /></label>
          <label><span>明确品类</span><input placeholder="例如：家庭物品整理与库存管理应用" value={briefDraft.category} onChange={(event) => setBriefDraft((current) => ({ ...current, category: event.target.value }))} /></label>
          <label className="is-wide"><span>竞品（每行一个）</span><textarea value={briefDraft.competitors} onChange={(event) => setBriefDraft((current) => ({ ...current, competitors: event.target.value }))} /></label>
          <label className="is-wide"><span>研究目标</span><textarea placeholder="我们希望用这项研究回答什么商业问题？" value={briefDraft.objective} onChange={(event) => setBriefDraft((current) => ({ ...current, objective: event.target.value }))} /></label>
          <footer><button type="button" onClick={() => setBriefEditing(false)} disabled={briefBusy}>取消</button><button className="agent-primary-button" type="button" onClick={() => void saveBrief()} disabled={briefBusy}>{briefBusy ? "正在保存…" : "保存研究 Brief"}</button></footer>
          {briefError && <p className="cycle-action-error is-wide" role="alert">{briefError}</p>}
        </div> : <div className="research-brief-summary">
          <div><span>市场 / 品类</span><strong>{dashboard.market || "待设置"}</strong><p>{dashboard.category || "尚未定义明确品类"}</p></div>
          <div><span>核心品牌 / 域名</span><strong>{dashboard.brand_name}</strong><p>{dashboard.primary_domain || "尚未设置品牌域名"}</p></div>
          <div><span>竞争范围</span><strong>{dashboard.competitors.length ? `${dashboard.competitors.length} 个竞品` : "待设置"}</strong><p>{dashboard.competitors.length ? dashboard.competitors.join("、") : "没有竞品就无法计算相对份额"}</p></div>
          <div><span>研究目标</span><strong>{dashboard.research_objective ? "已定义" : "待设置"}</strong><p>{dashboard.research_objective || "明确这项研究要支持的决策"}</p></div>
        </div>}
      </section>

      <section className="project-overview-recent">
        <div className="project-section-head"><div><span>最近动态</span><h2>项目刚刚发生了什么</h2></div><Link href={viewHref("activity")}>查看完整历史 →</Link></div>
        {dashboard.activities.length ? <div className="overview-activity-list">{dashboard.activities.slice(0, 4).map((activity) => <article key={activity.id}><i className={`status-${activity.status}`} /><div><span>{ACTIVITY_LABEL[activity.kind] ?? activity.kind}</span><strong>{activity.title}</strong></div><time>{formatTime(activity.started_at)}</time></article>)}</div> : <div className="project-empty"><p>还没有测量记录。完成第一次市场位置测量后，关键变化会显示在这里。</p></div>}
      </section>
      </>}

      {activeView === "visibility" && <>
      <section className="project-section">
        <div className="project-section-head"><div><span>AI 可见度</span><h2>当前答案面表现</h2></div><p>基于每个引擎最近一次成功检测。</p></div>
        {latestByEngine.length ? <div className="visibility-summary-table"><div className="table-head"><span>答案面</span><span>品牌提及</span><span>域名引用</span><span>相对份额</span><span>样本</span></div>{latestByEngine.map((item) => <div className="table-row" key={item.engine_id}><strong>{item.surface_name || item.engine_id}</strong><span>{percent(item.entity_sov)}{confidenceRange(item.entity_ci_low, item.entity_ci_high) && <small>{confidenceRange(item.entity_ci_low, item.entity_ci_high)}</small>}</span><span>{percent(item.citation_sov)}{confidenceRange(item.citation_ci_low, item.citation_ci_high) && <small>{confidenceRange(item.citation_ci_low, item.citation_ci_high)}</small>}</span><span>{item.relative_sov === null ? "—" : percent(item.relative_sov)}{Object.entries(item.competitor_sov).map(([name, value]) => <small key={name}>{name} {percent(value)}</small>)}</span><span>{item.sample_size}</span></div>)}</div> : <div className="project-empty"><p>还没有正式可见度数据。运行一次已验收答案面检测后建立基线。</p><Link href={trackHref}>运行第一次检测 →</Link></div>}
      </section>

      <section className="project-section diagnosis-section">
        <div className="project-section-head"><div><span>证据诊断</span><h2>结果背后的具体缺口</h2></div><p>仅使用已认证答案面的原始样本；这是判断依据，不会自动替你创建或发布优化任务。</p></div>
        {dashboard.diagnosis.insights.length ? <><div className="diagnosis-meta"><span>{dashboard.diagnosis.qualified_run_count} 次正式检测 · {dashboard.diagnosis.qualified_sample_count} 个样本</span><b>{QUALITY_LABEL[dashboard.diagnosis.coverage_status] ?? "当前范围"}</b></div><div className="diagnosis-list">{dashboard.diagnosis.insights.map((insight) => <article key={insight.id} className={`diagnosis-card priority-${insight.priority}`}><header><span>{insight.priority === "high" ? "优先处理" : "需要复核"}</span><div><b>{insight.engine_id}</b><small>{INTENT_LABEL[insight.prompt_intent] ?? insight.prompt_intent}问题 · {insight.sample_size} 个样本</small></div></header><h3>{insight.title}</h3><p className="diagnosis-question">{insight.prompt_text}</p><p>{insight.detail}</p><div className="diagnosis-facts"><span>品牌 {insight.brand_mentions}/{insight.sample_size}</span><span>自有域名引用 {insight.own_domain_citations}/{insight.sample_size}</span>{Object.entries(insight.competitor_mentions).map(([name, count]) => <span key={name}>{name} {count}/{insight.sample_size}</span>)}</div><details><summary>查看依据 <span>↓</span></summary><div className="diagnosis-evidence">{insight.cited_urls.length ? <ul>{insight.cited_urls.map((url) => <li key={url}><a href={url} target="_blank" rel="noreferrer">{url}</a></li>)}</ul> : <p>该答案没有返回可访问来源链接；可到项目历史查看原始回答。</p>}<Link href={viewHref("activity")}>在项目历史中查看原始回答 →</Link></div></details><button className="diagnosis-create-work" type="button" onClick={() => void createWorkFromDiagnosis(insight.id)} disabled={creatingDiagnosisId !== null}>{creatingDiagnosisId === insight.id ? "正在建立工作…" : "基于此证据建立优化工作 →"}</button></article>)}</div></> : <div className="project-empty"><p>{dashboard.diagnosis.warnings[0] ?? "当前没有需要提示的正式样本缺口。"}</p>{latestByEngine.length ? <Link href={viewHref("activity")}>查看本次原始证据 →</Link> : <Link href={trackHref}>运行已认证答案面检测 →</Link>}</div>}
        {dashboard.diagnosis.warnings.length > 0 && <div className="diagnosis-warnings">{dashboard.diagnosis.warnings.map((warning) => <p key={warning}>{warning}</p>)}</div>}
        {diagnosisError && <p className="cycle-action-error" role="alert">{diagnosisError}</p>}
      </section>
      </>}

      {activeView === "report" && <section className="research-report-view">
        <header className="research-report-toolbar">
          <div><span>CLIENT-READY RESEARCH REPORT</span><h2>AI 市场研究报告</h2></div>
          {researchReport?.status === "ready" && <button type="button" onClick={() => window.print()}>打印 / 导出 PDF</button>}
        </header>
        {reportLoading && !researchReport ? <div className="project-empty"><p>正在聚合最新正式证据…</p></div> : reportError ? <div className="error-banner" role="alert"><strong>报告无法生成</strong><p>{reportError}</p></div> : researchReport?.status === "waiting_for_baseline" ? <div className="research-report-waiting"><span>BASELINE REQUIRED</span><h3>研究范围已经定义，但还没有可交付证据</h3><p>{researchReport.executive_summary}</p><Link href={trackHref}>建立第一次正式基线 →</Link></div> : researchReport ? <article className="research-report-document">
          <section className="report-cover">
            <div className="report-cover-meta"><span>{researchReport.client_name}</span><span>{researchReport.market} · {researchReport.category || "未设置品类"}</span></div>
            <h3>{researchReport.project_name}</h3>
            <p>{researchReport.research_objective || `评估 ${researchReport.brand_name} 在 AI 答案市场中的品牌位置、竞品表现与来源结构。`}</p>
            <footer><span>核心品牌 · {researchReport.brand_name}</span><span>{researchReport.period_end ? `证据截至 ${formatDate(researchReport.period_end)}` : formatDate(researchReport.generated_at)}</span></footer>
          </section>

          <section className="report-executive-summary">
            <div><span>01 · 管理层摘要</span><h3>当前市场位置</h3></div>
            <p>{researchReport.executive_summary}</p>
          </section>

          <section className="report-scope" aria-label="报告研究范围">
            <div><span>研究范围</span><strong>Brief v{researchReport.brief_version}</strong></div>
            <div><span>固定问题</span><strong>{researchReport.question_count}</strong></div>
            <div><span>问题覆盖</span><strong>{QUALITY_LABEL[researchReport.measurement_quality.status] ?? researchReport.measurement_quality.status}</strong></div>
            <div><span>追踪计划</span><strong>{researchReport.tracking_plan_ids.length ? researchReport.tracking_plan_ids.length : "未绑定"}</strong></div>
          </section>

          <section className="report-kpis" aria-label="报告核心指标">
            <div><span>非品牌自然发现率</span><strong>{percent(researchReport.discovery_sov)}</strong><small>品类与需求问题 · 总体提及 {percent(researchReport.entity_sov)}</small></div>
            <div><span>自有域名引用率</span><strong>{percent(researchReport.citation_sov)}</strong><small>答案引用品牌域名的比例</small></div>
            <div><span>正式答案面</span><strong>{researchReport.engine_count}</strong><small>{researchReport.qualified_run_count} 次最新正式运行</small></div>
            <div><span>研究样本</span><strong>{researchReport.sample_count}</strong><small>只计当前最新正式样本</small></div>
          </section>

          <section className="report-section report-intents">
            <header><span>02 · 问题意图表现</span><h3>品牌在哪类研究问题中出现</h3></header>
            <div>{researchReport.intent_results.map((intent) => <article key={intent.intent}><span>{intent.label}</span><strong>{percent(intent.entity_sov)}</strong><p>{intent.sample_count} 个样本 · 自有域名引用 {percent(intent.citation_sov)}</p><div><i style={{ width: `${Math.max(intent.entity_sov * 100, intent.entity_sov ? 3 : 0)}%` }} /></div></article>)}</div>
          </section>

          <section className="report-section report-findings">
            <header><span>03 · 核心发现</span><h3>值得管理层关注的差异</h3></header>
            <div>{researchReport.findings.map((finding, index) => <article key={`${finding.kind}-${finding.title}`}><b>{String(index + 1).padStart(2, "0")}</b><div><span>{finding.kind}</span><h4>{finding.title}</h4><p>{finding.detail}</p><small>{finding.evidence}</small></div></article>)}</div>
          </section>

          <div className="report-analysis-grid">
            <section className="report-section">
              <header><span>04 · 答案面表现</span><h3>品牌在不同 AI 答案面的总体表现</h3></header>
              <div className="report-ranking-list">{researchReport.engine_results.map((engine) => <div key={engine.engine_id}><div><strong>{engine.surface_name}</strong><small>{engine.sample_size} 个样本</small></div><span>{percent(engine.entity_sov)} 提及</span><span>{percent(engine.citation_sov)} 引用</span></div>)}</div>
            </section>
            <section className="report-section">
              <header><span>05 · 竞品基准</span><h3>设定竞品在当前样本中的出现率</h3></header>
              {researchReport.competitor_results.length ? <div className="report-ranking-list">{researchReport.competitor_results.map((competitor) => <div key={competitor.name}><div><strong>{competitor.name}</strong><small>{competitor.mention_count}/{researchReport.sample_count} 个样本</small></div><span>{percent(competitor.mention_rate)}</span></div>)}</div> : <p className="report-section-empty">研究范围尚未设置竞品。</p>}
            </section>
          </div>

          <section className="report-section report-sources">
            <header><span>06 · 来源结构</span><h3>AI 答案正在引用谁</h3></header>
            {researchReport.source_results.length ? <div>{researchReport.source_results.map((source) => <article key={source.domain}><div><strong>{source.domain}</strong>{source.owned && <b>自有域名</b>}</div><div><i style={{ width: `${Math.max(source.citation_share * 100, 3)}%` }} /></div><span>{source.citation_count} 次 · {percent(source.citation_share)}</span></article>)}</div> : <p className="report-section-empty">当前答案没有返回可识别的来源链接。</p>}
          </section>

          <section className="report-methodology">
            <div><span>07 · 研究方法与限制</span><h3>这份报告能说明什么</h3></div>
            <ol>{researchReport.methodology.map((item) => <li key={item}>{item}</li>)}</ol>
            {researchReport.warnings.length > 0 && <aside><strong>解读提醒</strong>{researchReport.warnings.map((warning) => <p key={warning}>{warning}</p>)}</aside>}
          </section>
        </article> : null}
      </section>}

      {activeView === "optimization" && <>
      <section className="project-section fact-library-section">
        <div className="project-section-head"><div><span>生成依据</span><h2>已核验品牌事实</h2></div><p>内容、结构化数据和 Agent 只能使用这里确认过的事实。每条事实保留来源，避免生成时编造产品能力。</p></div>
        <div className="fact-library-grid">
          <div className="fact-list">
            <header><span>{brandFacts.filter((fact) => fact.status === "verified").length} 条可用事实</span><small>{brandFacts.filter((fact) => fact.status === "rejected").length} 条已停用</small></header>
            {brandFacts.some((fact) => fact.status === "verified") ? brandFacts.filter((fact) => fact.status === "verified").map((fact) => <article key={fact.id}><div><b>{FACT_TYPE_LABEL[fact.fact_type]}</b><p>{fact.claim}</p><a href={fact.source_url} target="_blank" rel="noreferrer">{fact.source_url}</a></div><button type="button" onClick={() => void rejectBrandFact(fact.id)} disabled={factBusy}>停用</button></article>) : <div className="fact-empty"><strong>还没有可用事实</strong><p>添加产品页、官方文档、价格页或政策页中能够直接证明的内容。</p></div>}
          </div>
          <div className="fact-composer">
            <div><span>添加事实</span><strong>用一条公开来源确认</strong></div>
            <label><span>类型</span><select value={factDraft.factType} onChange={(event) => setFactDraft((current) => ({ ...current, factType: event.target.value as BrandFactType }))}>{Object.entries(FACT_TYPE_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
            <label><span>可验证的事实</span><textarea value={factDraft.claim} onChange={(event) => setFactDraft((current) => ({ ...current, claim: event.target.value }))} placeholder="例：官方文档明确说明的功能、限制或适用对象。" /></label>
            <label><span>事实来源 URL</span><input type="url" value={factDraft.sourceUrl} onChange={(event) => setFactDraft((current) => ({ ...current, sourceUrl: event.target.value }))} placeholder="https://" /></label>
            <button type="button" onClick={() => void addBrandFact()} disabled={factBusy}>{factBusy ? "正在保存…" : "确认并加入事实库"}</button>
            {factError && <p className="cycle-action-error" role="alert">{factError}</p>}
          </div>
        </div>
      </section>

      <section className="project-section">
        <div className="project-section-head"><div><span>优化工作</span><h2>{currentCycle?.name ?? "从观测进入行动"}</h2></div><p>这些工作来自真实审计与观测，可由用户、团队或 Agent 共享执行，完成后回到同一周期复测。</p></div>
        {currentWork.length ? <div className="work-item-table">{currentWork.map((item) => <article key={item.id} className={`work-item-row is-${item.status}`}><span className={`severity severity-${item.priority}`}>{item.priority === "high" ? "高" : item.priority === "medium" ? "中" : "低"}</span><div><h3><Link href={`/projects/${dashboard.id}/work/${item.id}`}>{item.title}</Link></h3><p>{item.detail}</p><small>{item.category} · 基线 {String(item.evidence_snapshot.baseline_score ?? "—")} 分</small></div><select aria-label={`${item.title}状态`} value={item.status} disabled={item.status === "done"} onChange={(event) => void updateWork(item.id, event.target.value as "open" | "in_progress" | "review" | "dismissed")}><option value="open">待处理</option><option value="in_progress">进行中</option><option value="review">待审批</option><option value="dismissed">本周期不做</option>{item.status === "done" && <option value="done">已完成</option>}</select></article>)}</div> : <div className="project-empty"><p>尚未建立优化周期。运行完整工作包后，审计结果会成为这里的可执行工作。</p><Link href={`/optimize?url=${encodeURIComponent(`https://${dashboard.primary_domain}`)}&brand=${encodeURIComponent(dashboard.name)}&project=${dashboard.id}`}>启动第一个周期 →</Link></div>}
      </section>

      {currentCycle && <section className="project-section cycle-result-section">
        <div className="project-section-head"><div><span>周期验证</span><h2>{currentCycle.stage === "complete" ? "基线与复测结果" : "用原测量方法验证改变"}</h2></div><p>系统会自动复用本周期的问题、引擎和采样次数，不会把不同测量范围强行比较。</p></div>
        {currentCycle.verification_summary.engines?.length ? <>{currentCycle.verification_summary.comparison_note && <div className={`cycle-comparison-notice is-${currentCycle.verification_summary.comparison_status ?? "comparable"}`}><strong>{currentCycle.verification_summary.comparison_status === "scope_changed" ? "本次不能计算提升" : "复测口径一致"}</strong><p>{currentCycle.verification_summary.comparison_note}</p></div>}<div className="cycle-comparison-table"><div className="cycle-comparison-head"><span>引擎</span><span>品牌提及</span><span>域名引用</span><span>判定</span></div>{currentCycle.verification_summary.engines.map((result) => <div className="cycle-comparison-row" key={result.engine_id}><strong>{result.engine_id}</strong><span>{percent(result.baseline.entity_sov)} → {percent(result.verification.entity_sov)} <small>{result.entity_delta === null ? "不可比" : signedPercent(result.entity_delta)}</small></span><span>{percent(result.baseline.citation_sov)} → {percent(result.verification.citation_sov)} <small>{result.citation_delta === null ? "不可比" : signedPercent(result.citation_delta)}</small></span><span><b className={`assessment assessment-${result.entity_assessment}`}>{ASSESSMENT_LABEL[result.entity_assessment]}</b><small>{result.comparison_reasons.length ? result.comparison_reasons.join("；") : `提及 / ${ASSESSMENT_LABEL[result.citation_assessment]} 引用`}</small></span></div>)}</div>{currentCycle.verification_summary.changes?.length ? <div className="cycle-change-log"><span>本轮实际改动</span>{currentCycle.verification_summary.changes.map((change) => <div key={`${change.artifact_id}-${change.published_at}`}><strong>{change.work_item_title}</strong><p>{change.notes || "已记录实施"}</p>{change.target_url && (isWebUrl(change.target_url) ? <a href={change.target_url} target="_blank" rel="noreferrer">{change.target_url}</a> : <code>{change.target_url}</code>)}</div>)}</div> : null}</> : <div className="cycle-verify-action"><div><strong>{currentCycle.retest_plan ? `复测${currentCycle.retest_plan.status === "failed" ? "需要重试" : "已安排"} · ${formatDate(currentCycle.retest_plan.scheduled_for)}` : currentCycle.stage === "verify" ? "实施已完成，可以复测" : "完成实施后自动安排复测"}</strong><span>{currentCycle.measurement_config.questions?.length ?? 0} 个原问题 · {currentCycle.measurement_config.engine_ids?.join("、") || "原引擎"} · 每题 {currentCycle.measurement_config.samples ?? "—"} 次</span>{currentCycle.retest_plan?.last_error && <small>{currentCycle.retest_plan.last_error}</small>}</div><button type="button" onClick={() => void verifyCycle()} disabled={verifying || currentCycle.stage !== "verify"}>{verifying ? "正在复用基线采样…" : currentCycle.retest_plan ? "现在复测" : "复测本周期"}</button></div>}
        {actionError && <p className="cycle-action-error" role="alert">{actionError}</p>}
      </section>}

      <section className="project-section agent-control-section">
        <div className="project-section-head"><div><span>Agent 托管执行</span><h2>在预算和审批内工作</h2></div><p>Agent 只能从当前周期的真实证据和工作项出发，生成新草稿版本；不能自行审批或发布。</p></div>
        <div className="agent-control-grid">
          <aside className="agent-policy-card"><div><span>执行策略</span><b>{dashboard.agent_policy?.enabled ? "已启用" : "未启用"}</b></div><label><span>单次最多动作</span><input type="number" min={1} max={20} value={agentConfig.maxActions} onChange={(event) => setAgentConfig((current) => ({ ...current, maxActions: Number(event.target.value) || 1 }))} /></label><label><span>单次预算（USD）</span><input type="number" min={0} step="0.01" value={agentConfig.perRunBudget} onChange={(event) => setAgentConfig((current) => ({ ...current, perRunBudget: Number(event.target.value) || 0 }))} /></label><label><span>每月预算（USD）</span><input type="number" min={0} step="0.1" value={agentConfig.monthlyBudget} onChange={(event) => setAgentConfig((current) => ({ ...current, monthlyBudget: Number(event.target.value) || 0 }))} /></label><label><span>追踪后自动提案</span><input type="checkbox" checked={agentConfig.autoPlanOnTracking} onChange={(event) => setAgentConfig((current) => ({ ...current, autoPlanOnTracking: event.target.checked }))} /></label><div className="agent-policy-facts"><span>DeepSeek 生成</span><span>强制人工审批</span><span>禁止直接发布</span></div><button type="button" onClick={() => void saveAgentPolicy(!dashboard.agent_policy?.enabled)} disabled={agentBusy}>{dashboard.agent_policy?.enabled ? "暂停 Agent" : "启用 Agent"}</button>{dashboard.agent_policy?.enabled && <button className="agent-secondary-button" type="button" onClick={() => void saveAgentPolicy(true)} disabled={agentBusy}>保存策略</button>}</aside>

          <div className="agent-run-card">{!dashboard.agent_policy?.enabled ? <div className="agent-empty"><span>01</span><h3>先确定 Agent 边界</h3><p>启用后 Agent 才能读取当前周期并提交计划。</p></div> : !latestAgentRun ? <div className="agent-empty"><span>02</span><h3>让 Agent 提交第一份计划</h3><p>{activeCycle ? "它会选择当前周期中最高优先级的可编辑草稿。" : "需要先建立一个活跃优化周期。"}</p><button type="button" onClick={() => void planAgentRun()} disabled={agentBusy || !activeCycle}>生成 Agent 计划</button></div> : <div className="agent-run-detail"><header><div><span>{latestAgentRun.trigger === "tracking" ? "追踪自动提案" : "Agent 运行"}</span><h3>{latestAgentRun.goal}</h3></div><div><b>{latestAgentRun.status}</b><small>预估 ${latestAgentRun.estimated_cost.toFixed(2)} · 实际 ${latestAgentRun.actual_cost.toFixed(2)}</small><small>尝试 {latestAgentRun.attempt_count}/{latestAgentRun.max_attempts}{latestAgentRun.next_attempt_at ? ` · ${formatTime(latestAgentRun.next_attempt_at)} 重试` : ""}</small></div></header><div className="agent-action-list">{latestAgentRun.actions.map((action) => <div key={action.id}><i className={`status-${action.status}`} /><div><strong>{action.work_item_title}</strong><p>{action.rationale}</p><small>{action.status} · ${action.estimated_cost.toFixed(2)}</small></div>{action.output_artifact_id && <Link href={`/projects/${dashboard.id}/work/${action.work_item_id}`}>审查草稿 →</Link>}</div>)}</div><footer>{latestAgentRun.status === "awaiting_approval" && <><button type="button" onClick={() => void decideAgentRun("reject")} disabled={agentBusy}>拒绝计划</button><button className="agent-primary-button" type="button" onClick={() => void decideAgentRun("approve")} disabled={agentBusy}>批准计划</button></>}{latestAgentRun.status === "approved" && <button className="agent-primary-button" type="button" onClick={() => void executeAgentRun()} disabled={agentBusy}>执行并生成草稿</button>}{["approved", "running", "retry_scheduled", "partial", "failed"].includes(latestAgentRun.status) && <button type="button" onClick={() => void decideAgentRun("takeover")} disabled={agentBusy}>人工接管</button>}{["done", "partial", "failed", "rejected", "taken_over"].includes(latestAgentRun.status) && activeCycle && <button type="button" onClick={() => void planAgentRun()} disabled={agentBusy}>提交新计划</button>}</footer></div>}</div>
        </div>
        {agentError && <p className="cycle-action-error" role="alert">{agentError}</p>}
      </section>
      </>}

      {activeView === "tracking" && <>
      <section className="project-section prompt-set-section">
        <div className="project-section-head"><div><span>测量问题集</span><h2>问题范围是可版本化资产</h2></div><p>每次编辑都会创建新版本；已有追踪计划继续锁定原问题，历史趋势不会被改写。</p></div>
        {dashboard.prompt_sets.length ? <div className="prompt-set-list">{dashboard.prompt_sets.map((promptSet) => <article key={promptSet.id} data-prompt-set-id={promptSet.id} className={`prompt-set-card${promptSet.active && promptSet.scope_current ? " is-active" : ""}`}><header><div><span>{!promptSet.scope_current ? `旧 Brief v${promptSet.brief_version}` : promptSet.active ? "当前版本" : "历史版本"}</span><h3>{promptSet.name} <small>v{promptSet.version}</small></h3></div><div className="prompt-card-actions"><button type="button" onClick={() => beginPromptSetVersion(promptSet)} disabled={promptSetBusy}>基于此版本编辑</button>{promptSet.active && promptSet.scope_current && <button data-testid={`track-prompt-set-${promptSet.id}`} type="button" onClick={() => openTrackingComposer(promptSet.id)}>用于追踪计划</button>}</div></header>{!promptSet.scope_current && <p className="measurement-warning">研究 Brief 已更新；此问题集仅保留为历史证据，编辑后会生成当前范围的新版本。</p>}<div className="prompt-intent-coverage">{Object.entries(promptSet.measurement_quality.coverage).map(([intent, count]) => <span className={count > 0 ? "is-covered" : ""} key={intent}>{INTENT_LABEL[intent] ?? intent} {count}</span>)}</div><ol>{promptSet.prompt_items.map((item) => <li key={item.id}><b>{INTENT_LABEL[item.intent]}</b><span>{item.text}</span></li>)}</ol>{promptSet.measurement_quality.warnings.length > 0 && <p className="measurement-warning">{promptSet.measurement_quality.warnings.join("；")}</p>}</article>)}</div> : <div className="project-empty"><p>尚未保存问题集。</p><Link href={trackHref}>先建立第一组测量问题 →</Link></div>}
        {editingPromptSetId && <div className="prompt-set-editor"><div><span>创建新版本</span><strong>历史版本不会被修改</strong></div><label><span>问题集名称</span><input value={promptSetDraft.name} onChange={(event) => setPromptSetDraft((current) => ({ ...current, name: event.target.value }))} /></label><label><span>问题（每行一个）</span><textarea value={promptSetDraft.prompts} onChange={(event) => setPromptSetDraft((current) => ({ ...current, prompts: event.target.value }))} /></label><footer><button type="button" onClick={() => setEditingPromptSetId(null)} disabled={promptSetBusy}>取消</button><button className="agent-primary-button" type="button" onClick={() => void savePromptSetVersion()} disabled={promptSetBusy}>{promptSetBusy ? "正在保存…" : "保存为新版本"}</button></footer>{promptSetError && <p className="cycle-action-error" role="alert">{promptSetError}</p>}</div>}
      </section>

      <section className="project-section">
        <div className="project-section-head"><div><span>追踪计划</span><h2>持续观测范围</h2></div><div><p>基于保存的问题集、引擎和频率，形成可复测的观测范围。</p>{dashboard.prompt_sets.some((item) => item.active && item.scope_current) && <button className="tracking-create-button" type="button" onClick={() => openTrackingComposer()}>新建追踪计划</button>}</div></div>
        {showTrackingComposer && <div className="tracking-composer"><label><span>当前问题集</span><select value={trackingDraft.promptSetId} onChange={(event) => setTrackingDraft((current) => ({ ...current, promptSetId: event.target.value }))}>{dashboard.prompt_sets.filter((item) => item.active && item.scope_current).map((item) => <option key={item.id} value={item.id}>{item.name} · v{item.version}</option>)}</select></label><label><span>采样次数</span><input type="number" min={1} max={20} value={trackingDraft.samples} onChange={(event) => setTrackingDraft((current) => ({ ...current, samples: Number(event.target.value) || 1 }))} /></label><label><span>频率</span><select value={trackingDraft.cadence} onChange={(event) => setTrackingDraft((current) => ({ ...current, cadence: event.target.value }))}><option value="weekly">每周</option><option value="daily">每日</option><option value="monthly">每月</option><option value="manual">手动</option></select></label><fieldset><legend>正式答案面</legend>{availableEngines.map((engine) => <label key={engine.id}><input type="checkbox" checked={trackingDraft.engineIds.includes(engine.id)} onChange={(event) => setTrackingDraft((current) => ({ ...current, engineIds: event.target.checked ? [...current.engineIds, engine.id] : current.engineIds.filter((id) => id !== engine.id) }))} />{engine.display_name}</label>)}</fieldset><footer><button type="button" onClick={() => setShowTrackingComposer(false)} disabled={runningPlanId === "creating"}>取消</button><button className="agent-primary-button" type="button" onClick={() => void createTrackingPlan()} disabled={runningPlanId === "creating"}>{runningPlanId === "creating" ? "正在创建…" : "保存追踪计划"}</button></footer></div>}
        {dashboard.tracking_plans.length ? <div className="tracking-plan-list">{dashboard.tracking_plans.map((plan) => { const trends = planTrend(dashboard.visibility, plan.id); return <article key={plan.id} className="tracking-plan-row"><div><span>{!plan.scope_current ? "旧研究范围" : CADENCE_LABEL[plan.cadence] ?? plan.cadence} · {QUALITY_LABEL[plan.measurement_quality.status] ?? plan.measurement_quality.status}</span><h3>{plan.prompt_set_name}</h3><p>{plan.question_count} 个问题 · {plan.engine_ids.join("、")} · 每题 {plan.samples} 次</p><div className="prompt-intent-coverage">{Object.entries(plan.measurement_quality.coverage).map(([intent, count]) => <span className={count > 0 ? "is-covered" : ""} key={intent}>{INTENT_LABEL[intent] ?? intent} {count}</span>)}</div>{plan.measurement_quality.warnings.length > 0 && <p className="measurement-warning">{plan.measurement_quality.warnings.join("；")}</p>}{trends.length > 0 && <div className="tracking-mini-trend">{trends.map(({ engineId, latest }) => <span key={engineId} title={latest.comparison_note}><b>{engineId}</b>{percent(latest.entity_sov)}{latest.comparison_status === "comparable" && latest.entity_delta !== null ? <small className={latest.entity_delta >= 0 ? "trend-up" : "trend-down"}>{signedPercent(latest.entity_delta)}</small> : latest.comparison_status === "scope_changed" ? <small className="trend-reset">范围变化 · 新基线</small> : <small>首次基线</small>}</span>)}</div>}</div><div><b>{!plan.scope_current ? "已暂停 · Brief 已更新" : plan.last_error ? `运行异常 · ${plan.consecutive_failures}` : plan.status === "active" ? "运行中" : plan.status}</b><small>{plan.last_run_at ? `上次 ${formatTime(plan.last_run_at)}` : "尚未自动执行"}</small><small>{plan.next_run_at ? `下次 ${formatTime(plan.next_run_at)}` : "手动计划"}</small><button type="button" onClick={() => void runTrackingPlan(plan.id)} disabled={runningPlanId !== null || !plan.scope_current}>{runningPlanId === plan.id ? "正在运行…" : !plan.scope_current ? "需要新计划" : "立即运行"}</button></div></article>; })}</div> : <div className="project-empty"><p>还没有持续追踪计划。</p><Link href={trackHref}>保存第一组追踪问题 →</Link></div>}
        {trackingError && <p className="cycle-action-error" role="alert">{trackingError}</p>}
      </section>
      </>}

      {activeView === "activity" && <section className="project-section activity-section">
        <div className="project-section-head"><div><span>项目活动</span><h2>发生了什么</h2></div><p>检测、优化、审批与 Agent 执行都会按时间记录在这里。</p></div>
        {dashboard.activities.length ? <div className="activity-list">{dashboard.activities.map((activity) => <ActivityItem key={activity.id} activity={activity} currentBriefVersion={dashboard.brief_version} evidence={dashboard.evidence.filter((item) => item.activity_id === activity.id)} />)}</div> : <div className="project-empty"><p>项目还没有活动。</p></div>}
      </section>}
      </div>
    </main>
  </div>;
}

function ActivityItem({ activity, evidence, currentBriefVersion }: { activity: ProjectActivity; evidence: CitationEvidence[]; currentBriefVersion: number }) {
  const questions = activity.input_snapshot.questions ?? [];
  const engineIds = activity.input_snapshot.engine_ids ?? [];
  const activityBriefVersion = Number(activity.input_snapshot.brief_version ?? 1);
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
        {activity.kind === "visibility" && <span>{activityBriefVersion === currentBriefVersion ? `当前 Brief v${activityBriefVersion}` : `历史 Brief v${activityBriefVersion}`}</span>}
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
  return <div className="evidence-samples">{samples.map((sample, index) => {
    const model = typeof sample.provider_metadata.model === "string" ? sample.provider_metadata.model : "";
    const agentId = typeof sample.provider_metadata.agent_id === "string" ? sample.provider_metadata.agent_id : "";
    const agentVersion = typeof sample.provider_metadata.agent_version === "string" ? sample.provider_metadata.agent_version : "";
    return <details key={`${sample.run_id}-${sample.request_id}-${index}`}><summary><b>{sample.surface_name || sample.engine_id}</b> · 样本 {index + 1} · {sample.cited_urls.length} 个来源 · {sample.scope_current ? `Brief v${sample.brief_version}` : `历史 Brief v${sample.brief_version}`}</summary><div className="evidence-provenance"><span>采集：{formatTime(sample.captured_at)}</span><span>范围：{sample.measurement_scope === "citation" ? "联网引用" : sample.measurement_scope}</span>{model && <span>模型：{model}</span>}{agentId && <span>Agent：{agentId}{agentVersion ? ` · ${agentVersion}` : ""}</span>}{sample.request_id && <span>请求 ID：{sample.request_id}</span>}</div><p>{sample.answer_text}</p>{sample.cited_urls.length > 0 && <ul>{sample.cited_urls.map((url) => <li key={url}><a href={url} target="_blank" rel="noreferrer">{url}</a></li>)}</ul>}</details>;
  })}</div>;
}

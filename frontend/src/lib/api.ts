// 类型化后端 client。所有后端调用走这里，便于接手与替换。
// 后端基地址走 NEXT_PUBLIC_API_URL，默认 http://127.0.0.1:8000

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export interface Recommendation {
  dimension: string;
  title: string;
  detail: string;
  severity: "high" | "medium" | "low";
  jsonld: Record<string, unknown> | null;
  compliance_flag: boolean;
  generated_content?: string | null;
}

export interface CheckResult {
  id: string;
  method: string;
  got: number;
  evidence: string;
}

export interface DimensionScore {
  score: number;
  weight: number;
  checks: CheckResult[];
}

export interface AnalysisResponse {
  audit_run_id: string;
  url: string;
  status: number;
  total: number;
  breakdown: Record<string, DimensionScore>;
  recommendations: Recommendation[];
}

export interface AnalysisRequest {
  url: string;
  engine_id?: string | null;
  brand_name?: string;
  preferred_sources?: string[];
  project_id?: string | null;
}

export interface SoVEngineResult {
  engine_id: string;
  surface_name: string;
  acquisition: string;
  measurement_scope: "citation" | "answer_visibility" | "brand_awareness" | "stub";
  report_eligible: boolean;
  measurement_quality: MeasurementQuality;
  entity_sov: number;
  citation_sov: number;
  competitor_sov: Record<string, number>;
  relative_sov: number | null;
  avg_rank: number | null;
  sample_size: number;
  entity_ci_low: number;
  entity_ci_high: number;
  citation_ci_low: number;
  citation_ci_high: number;
}

export interface CitationRunResponse {
  results: SoVEngineResult[];
  status: "done" | "partial" | "failed";
  errors: Record<string, string>;
}

export interface CitationRunRequest {
  engine_ids: string[];
  prompts: string[];
  brand_name: string;
  aliases?: string[];
  brand_domains?: string[];
  competitors?: string[];
  samples?: number;
  project_id?: string | null;
  prompt_set_id?: string | null;
}

export interface ProjectCreateRequest {
  name: string;
  primary_domain?: string;
  client_name?: string;
  locale?: string;
}

export interface PromptSetCreateRequest { name: string; prompts: string[]; kind?: string; }
export interface PromptSetVersionCreateRequest { name?: string; prompts: string[]; }

export interface TrackingPlanCreateRequest {
  prompt_set_id: string;
  engine_ids: string[];
  samples?: number;
  cadence?: string;
  next_run_at?: string | null;
}

export interface Project {
  id: string;
  name: string;
  primary_domain: string;
  locale: string;
  status: string;
}

export interface VisibilitySnapshot extends Omit<SoVEngineResult, "entity_ci_low" | "entity_ci_high" | "citation_ci_low" | "citation_ci_high"> {
  entity_ci_low: number | null;
  entity_ci_high: number | null;
  citation_ci_low: number | null;
  citation_ci_high: number | null;
  period: string;
  tracking_plan_id: string | null;
}

export interface ProjectDashboard extends Project {
  citation_runs: number;
  visibility: VisibilitySnapshot[];
  evidence: CitationEvidence[];
  diagnosis: DiagnosisSummary;
  prompt_sets: PromptSet[];
  tracking_plans: TrackingPlan[];
  activities: ProjectActivity[];
  cycles: GeoCycle[];
  work_items: WorkItem[];
  agent_policy: AgentPolicy | null;
  agent_runs: AgentRun[];
}

export interface VisibilityDiagnosis {
  id: string;
  priority: "high" | "medium" | "low";
  kind: "competitor_gap" | "citation_gap" | "visibility_gap";
  title: string;
  detail: string;
  engine_id: string;
  prompt_text: string;
  prompt_intent: "branded" | "category" | "problem" | "comparison";
  sample_size: number;
  brand_mentions: number;
  own_domain_citations: number;
  competitor_mentions: Record<string, number>;
  cited_urls: string[];
  evidence_run_ids: string[];
}

export interface DiagnosisSummary {
  qualified_sample_count: number;
  qualified_run_count: number;
  coverage_status: "unavailable" | "limited" | "balanced" | "comprehensive";
  warnings: string[];
  insights: VisibilityDiagnosis[];
}

export interface AgentPolicy {
  id: string;
  project_id: string;
  enabled: boolean;
  generation_engine: string;
  approval_required: boolean;
  max_actions_per_run: number;
  per_run_budget: number;
  monthly_budget: number;
  allow_direct_publish: boolean;
  auto_plan_on_tracking: boolean;
  created_at: string;
  updated_at: string;
}

export interface AgentAction {
  id: string;
  work_item_id: string;
  work_item_title: string;
  source_artifact_id: string;
  action_type: string;
  status: string;
  rationale: string;
  estimated_cost: number;
  output_artifact_id: string | null;
  error_type: string | null;
}

export interface AgentRun {
  id: string;
  cycle_id: string;
  trigger: string;
  goal: string;
  status: string;
  plan: Record<string, unknown>;
  estimated_cost: number;
  actual_cost: number;
  error_summary: Record<string, string>;
  attempt_count: number;
  max_attempts: number;
  heartbeat_at: string | null;
  next_attempt_at: string | null;
  created_at: string;
  approved_at: string | null;
  finished_at: string | null;
  actions: AgentAction[];
}

export interface GeoCycle {
  id: string;
  name: string;
  objective: string;
  stage: "baseline" | "improve" | "execute" | "verify" | "complete";
  status: string;
  measurement_config: { questions?: string[]; engine_ids?: string[]; samples?: number };
  baseline_summary: { captured_at?: string; engines?: SoVEngineResult[] };
  verification_summary: {
    captured_at?: string;
    questions?: string[];
    engines?: Array<{
      engine_id: string;
      baseline: SoVEngineResult;
      verification: SoVEngineResult;
      entity_delta: number;
      citation_delta: number;
      entity_assessment: "improved" | "declined" | "unchanged" | "uncertain";
      citation_assessment: "improved" | "declined" | "unchanged" | "uncertain";
    }>;
    changes?: Array<{
      work_item_id: string;
      work_item_title: string;
      artifact_id: string;
      method: string;
      target_url: string;
      notes: string;
      published_at: string | null;
    }>;
  };
  started_at: string;
  completed_at: string | null;
}

export interface WorkItem {
  id: string;
  cycle_id: string;
  source_activity_id: string | null;
  title: string;
  detail: string;
  category: string;
  priority: "high" | "medium" | "low";
  status: "open" | "in_progress" | "review" | "done" | "dismissed";
  execution_mode: "unassigned" | "self" | "team" | "agent";
  evidence_snapshot: Record<string, unknown>;
  output_snapshot: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface OptimizationArtifact {
  id: string;
  work_item_id: string;
  kind: "content" | "jsonld" | "instructions";
  title: string;
  version: number;
  status: "draft" | "approved" | "implemented" | "superseded";
  content: string;
  structured_content: Record<string, unknown>;
  source_snapshot: Record<string, unknown>;
  created_by: string;
  created_at: string;
  updated_at: string;
  approved_at: string | null;
  implemented_at: string | null;
}

export interface DeliveryRecord {
  id: string;
  artifact_id: string;
  work_item_id: string;
  method: "export" | "manual" | "cms" | "repository";
  status: "exported" | "published";
  target_url: string;
  notes: string;
  created_by: string;
  created_at: string;
  published_at: string | null;
}

export interface WorkItemDetail { item: WorkItem; artifacts: OptimizationArtifact[]; deliveries: DeliveryRecord[]; }

export interface ProjectActivity {
  id: string;
  kind: string;
  title: string;
  triggered_by: string;
  status: string;
  input_snapshot: {
    questions?: string[];
    engine_ids?: string[];
    samples_per_question?: number;
    url?: string;
    brand_name?: string;
    legacy?: boolean;
  };
  output_summary: {
    engines?: SoVEngineResult[];
    question_count?: number;
    sample_count?: number;
    brand_mention_count?: number;
    own_domain_citation_count?: number;
    total_score?: number;
    recommendation_count?: number;
    high_priority_count?: number;
    error_type?: string;
  };
  started_at: string;
  finished_at: string | null;
}

export interface PromptItem { id: string; text: string; intent: "branded" | "category" | "problem" | "comparison"; }
export interface MeasurementQuality {
  status: "comprehensive" | "balanced" | "limited";
  question_count: number;
  coverage: Record<string, number>;
  covered_intents: string[];
  missing_intents: string[];
  warnings: string[];
  prompt_intents: Array<{ text: string; intent: string }>;
}
export interface PromptSet { id: string; source_prompt_set_id: string | null; name: string; version: number; kind: string; active: boolean; prompts: string[]; prompt_items: PromptItem[]; measurement_quality: MeasurementQuality; created_at: string; }

export interface TrackingPlan {
  id: string;
  prompt_set_id: string;
  prompt_set_name: string;
  question_count: number;
  prompt_items: PromptItem[];
  measurement_quality: MeasurementQuality;
  engine_ids: string[];
  samples: number;
  cadence: string;
  status: string;
  next_run_at: string | null;
  last_run_at: string | null;
  last_error: string | null;
  consecutive_failures: number;
  created_at: string;
}

export interface TrackingExecution {
  plan_id: string;
  status: "done" | "partial" | "failed";
  results: SoVEngineResult[];
  errors: Record<string, string>;
  last_run_at: string;
  next_run_at: string | null;
}

export interface CitationEvidence {
  run_id: string;
  activity_id: string | null;
  engine_id: string;
  captured_at: string;
  prompt_text: string;
  answer_text: string;
  cited_urls: string[];
  brand_mentioned: boolean;
  own_domain_cited: boolean;
  competitor_mentions: string[];
  request_id: string | null;
  surface_name: string;
  measurement_scope: string;
  report_eligible: boolean;
}

export interface EngagementReport {
  url: string;
  brand_name: string;
  total: number;
  breakdown: Record<string, DimensionScore>;
  recommendations: Recommendation[];
  visibility: SoVEngineResult[];
  summary: string;
}

export interface EngagementRequest {
  url: string;
  brand_name: string;
  engine_ids: string[];
  prompts: string[];
  brand_domains?: string[];
  samples?: number;
  project_id?: string | null;
}

export interface EngagementResponse {
  deliverable_id: string;
  report: EngagementReport;
  created_at: string;
}

export interface EngineInfo {
  id: string;
  display_name: string;
  acquisition: string;
  is_stub: boolean;
  measurement_scope: "citation" | "answer_visibility" | "brand_awareness" | "stub";
  surface_name: string;
  network_enabled: boolean;
  region_language: string;
  auth_mode: string;
  citation_availability: "none" | "urls" | "structured";
  validation_status: "pending" | "accepted" | "rejected";
  report_eligible: boolean;
  last_validated_at: string | null;
  validation_notes: string;
  cost_note: string;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    const payload = (await resp.json().catch(() => null)) as
      | { detail?: string | Array<{ msg?: string }> }
      | null;
    const detail = Array.isArray(payload?.detail)
      ? payload.detail.map((item) => item.msg).filter(Boolean).join("；")
      : payload?.detail;
    throw new Error(detail || `请求失败（HTTP ${resp.status}）`);
  }
  return (await resp.json()) as T;
}

async function get<T>(path: string): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`);
  if (!resp.ok) throw new Error(`${path} 失败：HTTP ${resp.status}`);
  return (await resp.json()) as T;
}

async function patch<T>(path: string, body: unknown): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw new Error(`更新失败（HTTP ${resp.status}）`);
  return (await resp.json()) as T;
}

async function put<T>(path: string, body: unknown): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    const payload = await resp.json().catch(() => null) as { detail?: string } | null;
    throw new Error(payload?.detail || `更新失败（HTTP ${resp.status}）`);
  }
  return (await resp.json()) as T;
}

export const api = {
  health: () => get<{ status: string }>("/health"),
  analyze: (req: AnalysisRequest) =>
    post<AnalysisResponse>("/api/analyses", req),
  runCitations: (req: CitationRunRequest) =>
    post<CitationRunResponse>("/api/citations/run", req),
  createProject: (req: ProjectCreateRequest) =>
    post<Project>("/api/projects", req),
  projects: () => get<Project[]>("/api/projects"),
  project: (id: string) => get<ProjectDashboard>(`/api/projects/${id}`),
  promptSets: (id: string) => get<PromptSet[]>(`/api/projects/${id}/prompt-sets`),
  createPromptSet: (id: string, req: PromptSetCreateRequest) => post<PromptSet>(`/api/projects/${id}/prompt-sets`, req),
  createPromptSetVersion: (id: string, promptSetId: string, req: PromptSetVersionCreateRequest) => post<PromptSet>(`/api/projects/${id}/prompt-sets/${promptSetId}/versions`, req),
  trackingPlans: (id: string) => get<TrackingPlan[]>(`/api/projects/${id}/tracking-plans`),
  createTrackingPlan: (id: string, req: TrackingPlanCreateRequest) => post<TrackingPlan>(`/api/projects/${id}/tracking-plans`, req),
  runTrackingPlan: (projectId: string, planId: string) => post<TrackingExecution>(`/api/projects/${projectId}/tracking-plans/${planId}/run`, {}),
  updateWorkItem: (projectId: string, itemId: string, req: { status?: WorkItem["status"]; execution_mode?: WorkItem["execution_mode"] }) => patch<WorkItem>(`/api/projects/${projectId}/work-items/${itemId}`, req),
  createWorkItemFromDiagnosis: (projectId: string, diagnosisId: string) => post<WorkItem>(`/api/projects/${projectId}/diagnosis/${encodeURIComponent(diagnosisId)}/work-items`, {}),
  workItem: (projectId: string, itemId: string) => get<WorkItemDetail>(`/api/projects/${projectId}/work-items/${itemId}`),
  createArtifactRevision: (projectId: string, itemId: string, req: { kind: OptimizationArtifact["kind"]; title: string; content: string; structured_content: Record<string, unknown> }) => post<OptimizationArtifact>(`/api/projects/${projectId}/work-items/${itemId}/artifacts`, req),
  updateArtifactStatus: (projectId: string, artifactId: string, status: "approved") => patch<OptimizationArtifact>(`/api/projects/${projectId}/artifacts/${artifactId}`, { status }),
  exportArtifact: (projectId: string, artifactId: string) => post<{ filename: string; media_type: string; content: string; delivery: DeliveryRecord }>(`/api/projects/${projectId}/artifacts/${artifactId}/export`, {}),
  createDelivery: (projectId: string, artifactId: string, req: { method: "manual" | "cms" | "repository"; status: "published"; target_url: string; notes: string }) => post<DeliveryRecord>(`/api/projects/${projectId}/artifacts/${artifactId}/deliveries`, req),
  verifyCycle: (projectId: string, cycleId: string) => post<{ cycle_id: string; status: string; verification_summary: GeoCycle["verification_summary"] }>(`/api/projects/${projectId}/cycles/${cycleId}/verify`, {}),
  saveAgentPolicy: (projectId: string, req: { enabled: boolean; generation_engine: string; approval_required: boolean; max_actions_per_run: number; per_run_budget: number; monthly_budget: number; auto_plan_on_tracking: boolean }) => put<AgentPolicy>(`/api/projects/${projectId}/agent-policy`, req),
  planAgentRun: (projectId: string, req: { cycle_id: string; goal: string }) => post<AgentRun>(`/api/projects/${projectId}/agent-runs`, req),
  decideAgentRun: (projectId: string, runId: string, decision: "approve" | "reject" | "takeover") => patch<AgentRun>(`/api/projects/${projectId}/agent-runs/${runId}`, { decision }),
  executeAgentRun: (projectId: string, runId: string) => post<AgentRun>(`/api/projects/${projectId}/agent-runs/${runId}/execute`, {}),
  runEngagement: (req: EngagementRequest) =>
    post<EngagementResponse>("/api/engagements/run", req),
  engines: () => get<EngineInfo[]>("/api/engines"),
};

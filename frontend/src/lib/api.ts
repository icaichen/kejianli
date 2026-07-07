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
}

export interface SoVEngineResult {
  engine_id: string;
  entity_sov: number;
  citation_sov: number;
  avg_rank: number | null;
  sample_size: number;
}

export interface CitationRunResponse {
  results: SoVEngineResult[];
}

export interface CitationRunRequest {
  engine_ids: string[];
  prompts: string[];
  brand_name: string;
  aliases?: string[];
  brand_domains?: string[];
  samples?: number;
}

export interface EngineInfo {
  id: string;
  display_name: string;
  acquisition: string;
  is_stub: boolean;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    throw new Error(`${path} 失败：HTTP ${resp.status}`);
  }
  return (await resp.json()) as T;
}

async function get<T>(path: string): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`);
  if (!resp.ok) throw new Error(`${path} 失败：HTTP ${resp.status}`);
  return (await resp.json()) as T;
}

export const api = {
  health: () => get<{ status: string }>("/health"),
  analyze: (req: AnalysisRequest) =>
    post<AnalysisResponse>("/api/analyses", req),
  runCitations: (req: CitationRunRequest) =>
    post<CitationRunResponse>("/api/citations/run", req),
  engines: () => get<EngineInfo[]>("/api/engines"),
};

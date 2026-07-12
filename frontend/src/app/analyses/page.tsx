"use client";

import Link from "next/link";
import { FormEvent, Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api, type AnalysisResponse, type Recommendation } from "@/lib/api";

const DIMENSION_LABEL: Record<string, string> = {
  technical_crawlability: "技术可访问性",
  content_structure: "内容结构",
  authority_eeat: "权威与可信度",
  freshness: "内容新鲜度",
  citation_friendliness: "引用友好度",
  entity_alignment: "实体清晰度",
  walled_garden_presence: "中文生态存在感",
};

const SEVERITY_LABEL: Record<Recommendation["severity"], string> = {
  high: "高优先级",
  medium: "中优先级",
  low: "低优先级",
};

function normalizeUrl(value: string) {
  const trimmed = value.trim();
  return /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
}

function AnalysesContent() {
  const params = useSearchParams();
  const initialUrl = params.get("url") ?? "https://example.com";
  const projectId = params.get("project");
  const [url, setUrl] = useState(initialUrl);
  const [brand, setBrand] = useState(params.get("brand") ?? "");
  const [engineId, setEngineId] = useState("");
  const [data, setData] = useState<AnalysisResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const autoRan = useRef(false);

  const run = useCallback(async (targetUrl?: string) => {
    const normalized = normalizeUrl(targetUrl ?? url);
    setUrl(normalized);
    setLoading(true);
    setError(null);
    setData(null);
    try {
      const result = await api.analyze({
        url: normalized,
        brand_name: brand.trim() || undefined,
        engine_id: engineId || null,
        project_id: projectId,
      });
      setData(result);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "暂时无法完成检测，请稍后再试。");
    } finally {
      setLoading(false);
    }
  }, [brand, engineId, projectId, url]);

  useEffect(() => {
    if (params.get("run") === "1" && !autoRan.current) {
      autoRan.current = true;
      void run(initialUrl);
    }
  }, [initialUrl, params, run]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void run();
  }

  return (
    <div className="audit-page">
      <section className="audit-intro">
        <div className="overline"><span>第一步 · 看见</span><span>真实网站检测</span></div>
        <h1>你的品牌，<br />准备好被 AI <em>引用</em>了吗？</h1>
        <p>可见力会抓取目标页面，检查技术、结构、权威、实体和引用信号，并把问题变成下一步可以执行的任务。</p>
      </section>

      <form className="audit-panel" onSubmit={submit}>
        <div className="audit-fields">
          <label className="field field-wide"><span>网站地址</span><input inputMode="url" autoComplete="url" suppressHydrationWarning value={url} onChange={(event) => setUrl(event.target.value)} required /></label>
          <label className="field"><span>品牌名称（可选）</span><input suppressHydrationWarning value={brand} onChange={(event) => setBrand(event.target.value)} placeholder="例如：可见力" /></label>
          <label className="field"><span>分析档位</span><select value={engineId} onChange={(event) => setEngineId(event.target.value)}><option value="">通用 GEO</option><option value="deepseek">DeepSeek</option><option value="baidu_ernie">百度文心</option><option value="doubao">豆包</option><option value="kimi">Kimi</option><option value="qwen">通义千问</option></select></label>
        </div>
        <button className="primary-button" type="submit" disabled={loading}>{loading ? "正在读取和分析…" : "开始检测"}<span aria-hidden="true">→</span></button>
        <p className="panel-note" role="status" aria-live="polite">{loading ? "复杂页面可能需要约一分钟，请不要关闭页面。" : "检测结果会包含证据、分项得分和可执行建议。"}</p>
      </form>

      {error && <div className="error-banner" role="alert"><strong>检测没有完成</strong><p>{error}</p><button type="button" onClick={() => void run()}>重新尝试</button></div>}
      {loading && <AuditSkeleton />}
      {data && <AuditReport brand={brand.trim()} data={data} />}
    </div>
  );
}

function domainFromUrl(value: string) {
  try {
    return new URL(value).hostname.replace(/^www\./, "");
  } catch {
    return value;
  }
}

function AuditReport({ brand, data }: { brand: string; data: AnalysisResponse }) {
  const dimensions = Object.entries(data.breakdown).sort(([, a], [, b]) => a.score / Math.max(a.weight, 1) - b.score / Math.max(b.weight, 1));
  const highPriority = data.recommendations.filter((item) => item.severity === "high").length;
  const domain = domainFromUrl(data.url);
  const trackingHref = `/visibility?domain=${encodeURIComponent(domain)}&brand=${encodeURIComponent(brand || domain)}`;
  const optimizerHref = `/optimize?url=${encodeURIComponent(data.url)}&brand=${encodeURIComponent(brand || domain)}`;

  return (
    <div className="audit-results">
      <section className="result-overview">
        <div className="result-score"><span>GEO 综合得分</span><strong>{data.total}<small>/100</small></strong><p>{data.status === 200 ? "页面已成功抓取" : `页面返回状态 ${data.status}`}</p></div>
        <div className="result-summary"><span>检测结论</span><h2>{data.total >= 75 ? "基础扎实，下一步是提高引用率。" : data.total >= 50 ? "已经能够被理解，但仍有明显引用障碍。" : "目前的页面很难成为 AI 的可信答案。"}</h2><p>发现 {data.recommendations.length} 项优化机会，其中 {highPriority} 项需要优先处理。下面先展示最影响结果的维度和建议。</p><div className="total-track"><i style={{ width: `${data.total}%` }} /></div></div>
      </section>

      <section className="dimension-section">
        <div className="result-heading"><span>分项证据</span><h2>问题出在哪里</h2></div>
        <div className="dimension-grid">
          {dimensions.map(([key, dimension]) => {
            const percent = Math.round((dimension.score / Math.max(dimension.weight, 1)) * 100);
            return <article className="dimension-card" key={key}><div><span>{DIMENSION_LABEL[key] ?? key}</span><strong>{percent}%</strong></div><div className="dimension-track"><i style={{ width: `${Math.min(100, percent)}%` }} /></div><p>{dimension.checks.filter((check) => check.got < 1).length} 个信号仍需改进</p></article>;
          })}
        </div>
      </section>

      <section className="recommendation-section" id="recommendations">
        <div className="result-heading"><span>第二步 · 提升</span><h2>从最重要的修复开始</h2><p>每条建议都来自本次检测，而不是通用的内容清单。</p></div>
        <div className="recommendation-list">
          {data.recommendations.length === 0 ? <div className="empty-result"><strong>没有发现明显问题</strong><p>可以继续进行多引擎可见度采样，验证品牌是否真正被提及和引用。</p></div> : data.recommendations.map((item, index) => (
            <article className="recommendation-card" key={`${item.dimension}-${item.title}-${index}`}>
              <div className="recommendation-index">{String(index + 1).padStart(2, "0")}</div>
              <div className="recommendation-copy"><div><span className={`severity severity-${item.severity}`}>{SEVERITY_LABEL[item.severity]}</span><small>{DIMENSION_LABEL[item.dimension] ?? item.dimension}</small>{item.compliance_flag && <b>合规提醒</b>}</div><h3>{item.title}</h3><p>{item.detail}</p>{item.generated_content && <details><summary>查看 AI 生成的可用草稿</summary><div className="generated-content">{item.generated_content}</div></details>}{item.jsonld && <details><summary>查看结构化数据</summary><pre>{JSON.stringify(item.jsonld, null, 2)}</pre></details>}</div>
              <a href="#next-step">处理这项问题 <span aria-hidden="true">→</span></a>
            </article>
          ))}
        </div>
      </section>

      <section className="next-step-section" id="next-step">
        <div className="result-heading"><span>下一步</span><h2>你希望如何继续？</h2><p>同一份检测结果可以进入三种不同深度的工作方式，不需要重新开始。</p></div>
        <div className="next-step-grid">
          <Link href={trackingHref} className="next-step-card"><span>01 · 持续追踪</span><h3>监测 AI 可见度</h3><p>选择目标引擎和真实用户问题，建立品牌提及与引用基线。</p><b>开始可见度采样 →</b></Link>
          <Link href={optimizerHref} className="next-step-card featured"><span>02 · 自己优化</span><h3>生成优化工作包</h3><p>把诊断、内容草稿、结构化数据和可见度采样合并成一次可执行交付。</p><b>打开优化工作台 →</b></Link>
          <div className="next-step-card"><span>03 · 交给 AI</span><h3>建立 AI 执行计划</h3><p>让 Agent 根据检测结果规划任务，生成内容并等待你的审批。</p><b className="coming-soon">执行工作流正在接入</b></div>
        </div>
      </section>
    </div>
  );
}

function AuditSkeleton() {
  return <div className="audit-skeleton" aria-label="正在生成检测结果"><div /><div /><div className="skeleton-grid"><i /><i /><i /></div></div>;
}

export default function AnalysesPage() {
  return <Suspense fallback={<div className="audit-page"><AuditSkeleton /></div>}><AnalysesContent /></Suspense>;
}

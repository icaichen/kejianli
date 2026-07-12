"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api, type EngagementResponse, type Project } from "@/lib/api";

const ENGINES = ["qwen"];

function normalizeUrl(value: string) {
  return /^https?:\/\//i.test(value.trim()) ? value.trim() : `https://${value.trim()}`;
}

function OptimizeContent() {
  const params = useSearchParams();
  const [url, setUrl] = useState(params.get("url") ?? "");
  const [brand, setBrand] = useState(params.get("brand") ?? "");
  const [questions, setQuestions] = useState("最好的 GEO 工具\n如何做中文内容优化");
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState(params.get("project") ?? "");
  const [activeProjectId, setActiveProjectId] = useState("");
  const [data, setData] = useState<EngagementResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { api.projects().then(setProjects).catch(() => setProjects([])); }, []);

  async function run() {
    const normalizedUrl = normalizeUrl(url);
    const prompts = questions.split("\n").map((item) => item.trim()).filter(Boolean);
    if (!url.trim() || !brand.trim() || prompts.length === 0) {
      setError("请填写网站、品牌名称和至少一个用户问题。");
      return;
    }
    setLoading(true); setError(null); setData(null);
    try {
      let savedProjectId = projectId;
      if (!savedProjectId) {
        const domain = new URL(normalizedUrl).hostname.replace(/^www\./, "");
        const project = await api.createProject({ name: brand.trim(), primary_domain: domain });
        savedProjectId = project.id;
        setProjects((current) => [project, ...current]);
        setProjectId(project.id);
      }
      setUrl(normalizedUrl);
      setData(await api.runEngagement({ url: normalizedUrl, brand_name: brand.trim(), engine_ids: ENGINES, prompts, brand_domains: [new URL(normalizedUrl).hostname], samples: 2, project_id: savedProjectId }));
      setActiveProjectId(savedProjectId);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "优化工作包生成失败，请稍后再试。");
    } finally { setLoading(false); }
  }

  return <div className="audit-page optimize-page">
    <section className="audit-intro"><div className="overline"><span>第二层 · GEO 工作台</span><span>一键生成可执行工作包</span></div><h1>把诊断变成<br /><em>可以交付</em>的优化。</h1><p>一次运行会完成网站审计、优化建议、多引擎可见度采样，并将结果保存到项目。适合希望自己执行，但不想拼凑工具的人。</p></section>
    <section className="audit-panel optimize-form">
      <div className="audit-fields"><label className="field field-wide"><span>网站地址</span><input suppressHydrationWarning inputMode="url" value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://your-site.com" /></label><label className="field"><span>品牌名称</span><input suppressHydrationWarning value={brand} onChange={(event) => setBrand(event.target.value)} placeholder="例如：可见力" /></label><label className="field"><span>保存到项目</span><select value={projectId} onChange={(event) => setProjectId(event.target.value)}><option value="">新建项目</option>{projects.map((project) => <option value={project.id} key={project.id}>{project.name}</option>)}</select></label></div>
      <label className="prompt-field"><span>目标用户问题（每行一个）</span><textarea suppressHydrationWarning value={questions} onChange={(event) => setQuestions(event.target.value)} /></label>
      <button className="primary-button" type="button" onClick={() => void run()} disabled={loading}>{loading ? "正在生成完整工作包…" : "生成优化工作包"}<span aria-hidden="true">→</span></button><p className="panel-note">默认采样已验收的千问联网检索；其他模型需完成真实 Provider 接入后再纳入正式报告。</p>
    </section>
    {error && <div className="error-banner" role="alert"><strong>工作包没有完成</strong><p>{error}</p><button type="button" onClick={() => void run()}>重新尝试</button></div>}
    {data && <section className="workpack-result"><div className="result-heading"><span>已保存的优化工作包</span><h2>{data.report.summary}</h2><p>交付编号：{data.deliverable_id}</p></div><div className="workpack-grid"><div><span>GEO 得分</span><strong>{data.report.total}<small>/100</small></strong></div><div><span>优化任务</span><strong>{data.report.recommendations.length}</strong><small>按优先级排序</small></div><div><span>追踪引擎</span><strong>{data.report.visibility.length}</strong><small>已经保存基线</small></div></div><div className="recommendation-list">{data.report.recommendations.map((item, index) => <article className="recommendation-card" key={`${item.title}-${index}`}><div className="recommendation-index">{String(index + 1).padStart(2, "0")}</div><div className="recommendation-copy"><div><span className={`severity severity-${item.severity}`}>{item.severity === "high" ? "高优先级" : item.severity === "medium" ? "中优先级" : "低优先级"}</span><small>{item.dimension}</small></div><h3>{item.title}</h3><p>{item.detail}</p>{item.generated_content && <details><summary>展开可直接使用的内容草稿</summary><div className="generated-content">{item.generated_content}</div></details>}{item.jsonld && <details><summary>展开 JSON-LD</summary><pre>{JSON.stringify(item.jsonld, null, 2)}</pre></details>}</div></article>)}</div><Link className="primary-button" href={activeProjectId ? `/projects/${activeProjectId}` : "/projects"}>前往项目工作台 <span aria-hidden="true">→</span></Link></section>}
  </div>;
}

export default function OptimizePage() { return <Suspense fallback={<div className="audit-page"><div className="audit-skeleton"><div /><div /></div></div>}><OptimizeContent /></Suspense>; }

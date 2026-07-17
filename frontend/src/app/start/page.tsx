"use client";

import Link from "next/link";
import { FormEvent, Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api, type SiteProfile } from "@/lib/api";

const EVIDENCE_LABEL: Record<SiteProfile["evidence"][number]["field"], string> = {
  brand_name: "品牌",
  category: "业务品类",
  summary: "官网描述",
  language: "网站语言",
};

function urlFromInput(value: string) {
  const trimmed = value.trim();
  return new URL(/^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`);
}

function domainFromInput(value: string) {
  return urlFromInput(value).hostname.replace(/^www\./, "");
}

function StartProjectContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [clientName, setClientName] = useState("");
  const [projectName, setProjectName] = useState("");
  const [brand, setBrand] = useState(searchParams.get("brand") ?? "");
  const [market, setMarket] = useState("中国大陆");
  const [category, setCategory] = useState("");
  const [domain, setDomain] = useState(searchParams.get("domain") ?? "");
  const [competitors, setCompetitors] = useState("");
  const [objective, setObjective] = useState("");
  const [busy, setBusy] = useState(false);
  const [discovering, setDiscovering] = useState(false);
  const [profile, setProfile] = useState<SiteProfile | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function discover() {
    if (!domain.trim()) {
      setError("请先输入企业官网。");
      return;
    }
    setDiscovering(true); setError(null); setProfile(null);
    try {
      const discovered = await api.discoverSite(urlFromInput(domain).toString());
      setProfile(discovered);
      const detectedDomain = domainFromInput(discovered.url);
      setDomain(detectedDomain);
      if (discovered.brand_name) {
        setBrand((current) => current || discovered.brand_name || "");
        setClientName((current) => current || discovered.brand_name);
        setProjectName((current) => current || `${discovered.brand_name} GEO 可见度`);
      }
      if (discovered.category) setCategory((current) => current || discovered.category || "");
      if (discovered.summary) {
        setObjective((current) => current || `了解潜在用户询问${discovered.category || discovered.brand_name || "目标业务"}相关问题时，品牌在 AI 答案中的提及、推荐、引用和竞品差距。`);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "网站无法读取。");
    } finally { setDiscovering(false); }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    let normalizedDomain = "";
    if (domain.trim()) {
      try {
        normalizedDomain = domainFromInput(domain);
      } catch {
        setError("请输入有效的网站地址，例如 dove.com.cn。");
        return;
      }
    }
    setBusy(true);
    try {
      const project = await api.createProject({
        name: projectName.trim(),
        client_name: clientName.trim(),
        brand_name: brand.trim(),
        primary_domain: normalizedDomain,
        market: market.trim(),
        category: category.trim(),
        competitors: competitors.split(/[，,\n]/).map((item) => item.trim()).filter(Boolean),
        research_objective: objective.trim(),
      });
      router.push(`/projects/${project.id}?welcome=1`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "研究项目创建失败，请稍后再试。");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="start-page research-start-page">
      <section className="start-intro">
        <div className="overline"><span>新建 GEO 研究项目</span><span>范围 → 问题 → 基线 → 优化 → 复测</span></div>
        <h1>先定义研究范围，<br />再看清 AI <em>如何影响选择</em>。</h1>
        <p>围绕一个品牌、市场、品类和真实竞品建立长期项目。首次检测不是终点，而是后续诊断、优化与可比复测的基线。</p>
      </section>

      <div className="start-layout research-start-layout">
        <form className="start-form research-brief" onSubmit={submit}>
          <div><span>研究 Brief</span><h2>定义这次要研究什么</h2><p>这些字段会冻结为研究版本，决定后续的问题集、模型采样、报告和可比趋势。</p></div>
          <div className="research-field-grid">
            <label><span>企业或客户</span><input value={clientName} onChange={(event) => setClientName(event.target.value)} placeholder="例如：Example 企业" autoFocus required /></label>
            <label><span>项目名称</span><input value={projectName} onChange={(event) => setProjectName(event.target.value)} placeholder="例如：Example 中国市场 GEO 研究" required /></label>
            <label><span>核心品牌或产品</span><input value={brand} onChange={(event) => setBrand(event.target.value)} placeholder="本项目要追踪的品牌" required /></label>
            <label><span>市场或地区</span><input value={market} onChange={(event) => setMarket(event.target.value)} placeholder="例如：中国大陆" required /></label>
            <label><span>业务品类</span><input value={category} onChange={(event) => setCategory(event.target.value)} placeholder="用户会用什么品类来寻找你" required /></label>
          </div>
          <div className="site-discovery-input">
            <label><span>品牌官网（辅助证据，可选）</span><input value={domain} onChange={(event) => { setDomain(event.target.value); setProfile(null); }} placeholder="example.com" inputMode="url" autoComplete="url" /></label>
            <button type="button" onClick={() => void discover()} disabled={discovering || !domain.trim()}>{discovering ? "正在读取首页…" : "读取并辅助填写"}</button>
          </div>
          {profile && <section className="site-profile-result" aria-label="网站识别结果">
            <header><div><span>官网证据建议</span><strong>{profile.title || profile.url}</strong></div><b>HTTP {profile.status}</b></header>
            <div className="site-profile-evidence">{profile.evidence.map((item) => <article key={`${item.field}-${item.source}`}><span>{EVIDENCE_LABEL[item.field]}</span><strong>{item.value}</strong><small>来源：{item.source}</small></article>)}</div>
            {profile.warnings.map((warning) => <p key={warning}>{warning}</p>)}
          </section>}
          <label><span>主要竞品</span><input value={competitors} onChange={(event) => setCompetitors(event.target.value)} placeholder="输入你真正想对比的品牌，用逗号分隔" required /></label>
          <label><span>研究目标</span><textarea value={objective} onChange={(event) => setObjective(event.target.value)} placeholder="例如：了解潜在用户询问这一品类、需求或品牌比较时，品牌被发现、推荐和引用的情况，以及主要竞品差距。" required /></label>
          {error && <p className="start-error" role="alert">{error}</p>}
          <button type="submit" disabled={busy}>{busy ? "正在建立项目…" : "确认并创建 GEO 项目"}<span aria-hidden="true">→</span></button>
          <small>创建后先确认研究问题、答案面与采样范围；确认前不会产生真实模型采样费用。</small>
        </form>

        <aside className="start-outcomes">
          <span>建立项目后</span>
          <ol>
            <li><b>01</b><div><strong>确认真正值得检测的问题</strong><p>系统根据品牌、品类、市场和竞品提出问题范围。</p></div></li>
            <li><b>02</b><div><strong>建立多个 AI 答案面的首次基线</strong><p>保存每个问题的原始回答、品牌、竞品与引用来源。</p></div></li>
            <li><b>03</b><div><strong>找到优先级最高的可见度差距</strong><p>从问题和证据进入可执行的优化工作。</p></div></li>
            <li><b>04</b><div><strong>优化后按原范围持续复测</strong><p>区分首次基线、可比变化与范围变更。</p></div></li>
          </ol>
          <Link href="/projects">查看现有研究项目 →</Link>
        </aside>
      </div>
    </div>
  );
}

export default function StartProjectPage() {
  return <Suspense fallback={<div className="start-page"><div className="projects-loading">正在准备研究空间…</div></div>}><StartProjectContent /></Suspense>;
}

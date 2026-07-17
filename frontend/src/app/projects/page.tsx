"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type Project } from "@/lib/api";

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.projects().then(setProjects).catch((reason: unknown) => {
      setError(reason instanceof Error ? reason.message : "无法读取项目列表。");
    });
  }, []);

  return <div className="legacy-page projects-page">
    <section className="projects-hero">
      <div className="overline"><span>研究工作台</span><span>客户、市场与答案证据</span></div>
      <h1>管理每一个客户的<br /><em>AI 市场研究</em>。</h1>
      <p>按客户、市场和品类组织研究。进入项目即可查看品牌与竞品的当前答案份额、来源证据、洞察和持续追踪范围。</p>
      <Link className="primary-button" href="/start">新建研究项目 <span aria-hidden="true">→</span></Link>
    </section>

    {error && <div className="error-banner" role="alert"><strong>项目列表未能加载</strong><p>{error}</p></div>}
    {projects === null && !error && <div className="projects-loading">正在读取你的项目…</div>}
    {projects?.length === 0 && <section className="empty-projects"><span>01</span><h2>从一份研究 Brief 开始</h2><p>填写客户、市场、品类、核心品牌、竞品和研究目标，再设计用于真实 AI 答案采样的问题范围。</p><Link href="/start">创建第一个研究项目 →</Link></section>}
    {projects && projects.length > 0 && <section className="project-grid" aria-label="已创建项目">
      {projects.map((project, index) => <Link href={`/projects/${project.id}`} className="project-card" key={project.id}>
        <span className="project-index">{String(index + 1).padStart(2, "0")}</span>
        <h2>{project.name}</h2>
        <p>{project.client_name} · {project.brand_name}{project.competitors.length ? ` vs ${project.competitors.join("、")}` : ""}</p>
        <div><span>{project.market} · {project.category || "未设置品类"}</span><span>{project.status === "active" ? "研究进行中" : project.status}</span></div>
        <b>打开研究项目 <span aria-hidden="true">↗</span></b>
      </Link>)}
    </section>}
  </div>;
}

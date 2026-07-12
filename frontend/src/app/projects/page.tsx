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
      <div className="overline"><span>第一层 · 工作台</span><span>项目与采样历史</span></div>
      <h1>每一个品牌，<br />都有一条<em>可见度轨迹</em>。</h1>
      <p>这里集中放置你已经建立的品牌项目。进入项目即可查看各引擎的最近基线，并继续追加采样。</p>
      <Link className="primary-button" href="/analyses">新建一次检测 <span aria-hidden="true">→</span></Link>
    </section>

    {error && <div className="error-banner" role="alert"><strong>项目列表未能加载</strong><p>{error}</p></div>}
    {projects === null && !error && <div className="projects-loading">正在读取你的项目…</div>}
    {projects?.length === 0 && <section className="empty-projects"><span>01</span><h2>从第一次检测开始</h2><p>完成网站审计后，进入可见度追踪；系统会自动为你的品牌建立第一个项目。</p><Link href="/analyses">检测一个网站 →</Link></section>}
    {projects && projects.length > 0 && <section className="project-grid" aria-label="已创建项目">
      {projects.map((project, index) => <Link href={`/projects/${project.id}`} className="project-card" key={project.id}>
        <span className="project-index">{String(index + 1).padStart(2, "0")}</span>
        <h2>{project.name}</h2>
        <p>{project.primary_domain || "尚未设置品牌域名"}</p>
        <div><span>{project.locale}</span><span>{project.status === "active" ? "正在追踪" : project.status}</span></div>
        <b>打开工作台 <span aria-hidden="true">↗</span></b>
      </Link>)}
    </section>}
  </div>;
}

"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { api, type OptimizationArtifact, type WorkItemDetail } from "@/lib/api";

const KIND_LABEL: Record<string, string> = { content: "内容草稿", jsonld: "JSON-LD", instructions: "执行说明" };
const STATUS_LABEL: Record<string, string> = { draft: "草稿", approved: "已审批", implemented: "已实施", superseded: "旧版本" };

export default function WorkItemPage({ params }: { params: Promise<{ id: string; workItemId: string }> }) {
  const [ids, setIds] = useState<{ id: string; workItemId: string } | null>(null);
  const [detail, setDetail] = useState<WorkItemDetail | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [content, setContent] = useState("");
  const [structured, setStructured] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deliveryMethod, setDeliveryMethod] = useState<"manual" | "cms" | "repository">("manual");
  const [targetUrl, setTargetUrl] = useState("");
  const [deliveryNotes, setDeliveryNotes] = useState("");

  useEffect(() => {
    void params.then((value) => {
      setIds(value);
      return api.workItem(value.id, value.workItemId);
    }).then(setDetail).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "优化工作无法读取。"));
  }, [params]);

  const currentArtifacts = useMemo(() => {
    if (!detail) return [];
    const latest = new Map<string, OptimizationArtifact>();
    for (const artifact of detail.artifacts) {
      if (artifact.status !== "superseded" && !latest.has(artifact.kind)) latest.set(artifact.kind, artifact);
    }
    return Array.from(latest.values());
  }, [detail]);
  const selected = currentArtifacts.find((artifact) => artifact.id === selectedId) ?? currentArtifacts[0];

  useEffect(() => {
    if (!selected) return;
    setSelectedId(selected.id);
    setContent(selected.content);
    setStructured(Object.keys(selected.structured_content).length ? JSON.stringify(selected.structured_content, null, 2) : "");
  }, [selected]);

  async function refresh() {
    if (!ids) return;
    setDetail(await api.workItem(ids.id, ids.workItemId));
  }

  async function saveRevision() {
    if (!ids || !selected) return;
    setBusy(true); setError(null);
    try {
      const structuredContent = structured.trim() ? JSON.parse(structured) as Record<string, unknown> : {};
      const revision = await api.createArtifactRevision(ids.id, ids.workItemId, { kind: selected.kind, title: selected.title, content, structured_content: structuredContent });
      await refresh(); setSelectedId(revision.id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "新版本保存失败。");
    } finally { setBusy(false); }
  }

  async function approveArtifact() {
    if (!ids || !selected) return;
    setBusy(true); setError(null);
    try { await api.updateArtifactStatus(ids.id, selected.id, "approved"); await refresh(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "状态更新失败。"); }
    finally { setBusy(false); }
  }

  async function exportCurrent() {
    if (!ids || !selected) return;
    setBusy(true); setError(null);
    try {
      const exported = await api.exportArtifact(ids.id, selected.id);
      const blob = new Blob([exported.content], { type: exported.media_type });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url; anchor.download = exported.filename; anchor.click();
      URL.revokeObjectURL(url);
      await refresh();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "导出失败。"); }
    finally { setBusy(false); }
  }

  async function recordDelivery() {
    if (!ids || !selected) return;
    setBusy(true); setError(null);
    try {
      await api.createDelivery(ids.id, selected.id, { method: deliveryMethod, status: "published", target_url: targetUrl, notes: deliveryNotes });
      await refresh();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "实施记录保存失败。"); }
    finally { setBusy(false); }
  }

  if (error && !detail) return <div className="project-shell"><div className="error-banner" role="alert"><strong>工作无法打开</strong><p>{error}</p><Link href={ids ? `/projects/${ids.id}` : "/projects"}>返回项目</Link></div></div>;
  if (!detail || !ids) return <div className="project-shell"><div className="projects-loading">正在读取优化产物…</div></div>;

  return <div className="project-shell work-detail-shell">
    <div className="project-breadcrumb"><Link href="/projects">项目</Link><span>/</span><Link href={`/projects/${ids.id}`}>优化工作</Link><span>/</span><span>{detail.item.title}</span></div>
    <header className="work-detail-header"><div><span className={`severity severity-${detail.item.priority}`}>{detail.item.priority === "high" ? "高优先级" : detail.item.priority === "medium" ? "中优先级" : "低优先级"}</span><h1>{detail.item.title}</h1><p>{detail.item.detail}</p></div><div><small>执行方式</small><strong>{detail.item.execution_mode === "agent" ? "Agent" : detail.item.execution_mode === "team" ? "团队" : "用户"}</strong><small>基线得分</small><strong>{String(detail.item.evidence_snapshot.baseline_score ?? "—")}</strong></div></header>

    <main className="work-editor-layout">
      <aside className="artifact-nav"><span>优化产物</span>{currentArtifacts.map((artifact) => <button type="button" className={selected?.id === artifact.id ? "is-active" : ""} key={artifact.id} onClick={() => setSelectedId(artifact.id)}><b>{KIND_LABEL[artifact.kind]}</b><small>v{artifact.version} · {STATUS_LABEL[artifact.status]}</small></button>)}<div><span>证据来源</span><p>审计 {String(detail.item.evidence_snapshot.audit_run_id ?? "—")}</p><p>GEO 基线 {String(detail.item.evidence_snapshot.baseline_score ?? "—")} / 100</p></div></aside>

      {selected ? <section className="artifact-editor"><header><div><span>{KIND_LABEL[selected.kind]}</span><h2>{selected.title}</h2></div><div><span>v{selected.version}</span><b>{STATUS_LABEL[selected.status]}</b></div></header>{selected.kind === "jsonld" ? <label><span>结构化数据</span><textarea className="code-editor" value={structured} onChange={(event) => setStructured(event.target.value)} spellCheck={false} /></label> : <label><span>{selected.kind === "content" ? "可交付内容" : "执行内容"}</span><textarea value={content} onChange={(event) => setContent(event.target.value)} /></label>}<footer><button type="button" onClick={() => void saveRevision()} disabled={busy || selected.status === "implemented"}>保存新版本</button><div>{selected.status === "draft" && <button className="approve" type="button" onClick={() => void approveArtifact()} disabled={busy}>审批通过</button>}{(selected.status === "approved" || selected.status === "implemented") && <button type="button" onClick={() => void exportCurrent()} disabled={busy}>导出文件</button>}</div></footer>{selected.status === "approved" && <div className="delivery-form"><div><label><span>实施方式</span><select value={deliveryMethod} onChange={(event) => setDeliveryMethod(event.target.value as "manual" | "cms" | "repository")}><option value="manual">人工发布</option><option value="cms">CMS</option><option value="repository">代码仓库</option></select></label><label><span>实际位置</span><input value={targetUrl} onChange={(event) => setTargetUrl(event.target.value)} placeholder="https://… 或文件路径" /></label></div><label><span>实施说明</span><textarea value={deliveryNotes} onChange={(event) => setDeliveryNotes(event.target.value)} placeholder="记录具体改了什么、发布到哪里。" /></label><button type="button" onClick={() => void recordDelivery()} disabled={busy || (!targetUrl.trim() && !deliveryNotes.trim())}>记录实施并完成</button></div>}{error && <p className="cycle-action-error" role="alert">{error}</p>}</section> : <div className="project-empty"><p>该工作尚无优化产物。</p></div>}

      <aside className="artifact-history"><span>版本与审批</span>{detail.artifacts.map((artifact) => <div key={artifact.id}><i className={`status-${artifact.status}`} /><p><b>{KIND_LABEL[artifact.kind]} v{artifact.version}</b><small>{STATUS_LABEL[artifact.status]} · {artifact.created_by === "user" ? "用户" : artifact.created_by}</small></p></div>)}{detail.deliveries.length > 0 && <><span className="history-subhead">导出与实施</span>{detail.deliveries.map((delivery) => <div key={delivery.id}><i className={`status-${delivery.status}`} /><p><b>{delivery.status === "published" ? "已实施" : "已导出"}</b><small>{delivery.method}{delivery.target_url ? ` · ${delivery.target_url}` : ""}</small></p></div>)}</>}</aside>
    </main>
  </div>;
}

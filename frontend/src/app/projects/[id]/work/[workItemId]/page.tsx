"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { api, type OptimizationArtifact, type WorkItemDetail } from "@/lib/api";

const KIND_LABEL: Record<string, string> = { content: "内容草稿", jsonld: "JSON-LD", instructions: "执行说明" };
const STATUS_LABEL: Record<string, string> = { draft: "草稿", approved: "已审批", implemented: "已实施", superseded: "旧版本" };

function initialArtifact(kind: OptimizationArtifact["kind"], item: WorkItemDetail["item"]) {
  const evidence = item.evidence_snapshot;
  const question = String(evidence.prompt_text ?? item.title);
  if (kind === "jsonld") {
    return { title: `待补全实体数据 · ${question}`, content: "", structured_content: { "@context": "https://schema.org", "@type": "SoftwareApplication", name: "", description: "" } };
  }
  if (kind === "content") {
    return { title: `回答「${question}」的内容草稿`, content: `# ${question}\n\n> 请先用已验证的产品事实补全此草稿；不要编造功能、客户、数据或外部引用。\n\n## 直接回答\n[用一句话说明产品适合谁、解决什么问题。]\n\n## 如何选择\n- [可验证的能力或条件]\n- [适用场景与限制]\n\n## 常见问题\n### [用户会继续追问的问题]\n[基于真实产品资料回答。]\n\n## 来源与更新\n[链接到本项目可验证的产品页面、文档或价格页。]`, structured_content: {} };
  }
  const competitors = Object.entries((evidence.competitor_mentions ?? {}) as Record<string, number>).map(([name, count]) => `${name} 出现 ${count} 次`).join("；") || "未记录竞品提及";
  return { title: `基于证据的执行说明 · ${question}`, content: `# 本工作要解决什么\n\n- 检测问题：${question}\n- 答案面：${String(evidence.engine_id ?? "—")}\n- 样本：${String(evidence.sample_size ?? "—")} 个\n- 品牌提及：${String(evidence.brand_mentions ?? "—")} 次\n- 自有域名引用：${String(evidence.own_domain_citations ?? "—")} 次\n- 竞品情况：${competitors}\n\n## 先核验\n1. 在项目活动中阅读原始回答与来源链接。\n2. 核对目标页面是否已有可验证的产品事实、明确的实体定义与直接回答。\n3. 仅将真实、可证明的信息写入内容或结构化数据。\n\n## 建议产物\n- 建立一份回答该问题的内容草稿，或补充可验证的 FAQ/产品说明。\n- 如需 JSON-LD，只填写网站已公开且可核验的字段。\n- 发布后，使用此工作冻结的问题与答案面进行复测。`, structured_content: {} };
}

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
  const [newKind, setNewKind] = useState<OptimizationArtifact["kind"]>("instructions");

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

  async function createInitialArtifact() {
    if (!ids || !detail) return;
    setBusy(true); setError(null);
    try {
      const artifact = initialArtifact(newKind, detail.item);
      const created = await api.createArtifactRevision(ids.id, ids.workItemId, { kind: newKind, ...artifact });
      await refresh(); setSelectedId(created.id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "无法建立可编辑产物。");
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
    <header className="work-detail-header"><div><span className={`severity severity-${detail.item.priority}`}>{detail.item.priority === "high" ? "高优先级" : detail.item.priority === "medium" ? "中优先级" : "低优先级"}</span><h1>{detail.item.title}</h1><p>{detail.item.detail}</p></div><div><small>执行方式</small><strong>{detail.item.execution_mode === "agent" ? "Agent" : detail.item.execution_mode === "team" ? "团队" : "用户"}</strong><small>{detail.item.evidence_snapshot.sample_size ? "正式样本" : "基线得分"}</small><strong>{detail.item.evidence_snapshot.sample_size ? `${String(detail.item.evidence_snapshot.sample_size)} 个` : String(detail.item.evidence_snapshot.baseline_score ?? "—")}</strong></div></header>

    <main className="work-editor-layout">
      <aside className="artifact-nav"><span>优化产物</span>{currentArtifacts.map((artifact) => <button type="button" className={selected?.id === artifact.id ? "is-active" : ""} key={artifact.id} onClick={() => setSelectedId(artifact.id)}><b>{KIND_LABEL[artifact.kind]}</b><small>v{artifact.version} · {STATUS_LABEL[artifact.status]}</small></button>)}<div><span>证据来源</span>{detail.item.evidence_snapshot.prompt_text ? <><p>问题：{String(detail.item.evidence_snapshot.prompt_text)}</p><p>答案面：{String(detail.item.evidence_snapshot.engine_id ?? "—")}</p><p>运行：{String(detail.item.evidence_snapshot.citation_run_ids ?? "—")}</p></> : <><p>审计 {String(detail.item.evidence_snapshot.audit_run_id ?? "—")}</p><p>GEO 基线 {String(detail.item.evidence_snapshot.baseline_score ?? "—")} / 100</p></>}</div></aside>

      {selected ? <section className="artifact-editor"><header><div><span>{KIND_LABEL[selected.kind]}</span><h2>{selected.title}</h2></div><div><span>v{selected.version}</span><b>{STATUS_LABEL[selected.status]}</b></div></header>{selected.kind === "jsonld" ? <label><span>结构化数据</span><textarea className="code-editor" value={structured} onChange={(event) => setStructured(event.target.value)} spellCheck={false} /></label> : <label><span>{selected.kind === "content" ? "可交付内容" : "执行内容"}</span><textarea value={content} onChange={(event) => setContent(event.target.value)} /></label>}<footer><button type="button" onClick={() => void saveRevision()} disabled={busy || selected.status === "implemented"}>保存新版本</button><div>{selected.status === "draft" && <button className="approve" type="button" onClick={() => void approveArtifact()} disabled={busy}>审批通过</button>}{(selected.status === "approved" || selected.status === "implemented") && <button type="button" onClick={() => void exportCurrent()} disabled={busy}>导出文件</button>}</div></footer>{selected.status === "approved" && <div className="delivery-form"><div><label><span>实施方式</span><select value={deliveryMethod} onChange={(event) => setDeliveryMethod(event.target.value as "manual" | "cms" | "repository")}><option value="manual">人工发布</option><option value="cms">CMS</option><option value="repository">代码仓库</option></select></label><label><span>实际位置</span><input value={targetUrl} onChange={(event) => setTargetUrl(event.target.value)} placeholder="https://… 或文件路径" /></label></div><label><span>实施说明</span><textarea value={deliveryNotes} onChange={(event) => setDeliveryNotes(event.target.value)} placeholder="记录具体改了什么、发布到哪里。" /></label><button type="button" onClick={() => void recordDelivery()} disabled={busy || (!targetUrl.trim() && !deliveryNotes.trim())}>记录实施并完成</button></div>}{error && <p className="cycle-action-error" role="alert">{error}</p>}</section> : <section className="artifact-start"><span>下一步</span><h2>先建立一份可审查的产物</h2><p>系统会带入当前问题与证据，但不会替你虚构产品事实。你可以先创建执行说明，再补充内容草稿或 JSON-LD。</p><label><span>产物类型</span><select value={newKind} onChange={(event) => setNewKind(event.target.value as OptimizationArtifact["kind"])}><option value="instructions">执行说明</option><option value="content">内容草稿</option><option value="jsonld">JSON-LD</option></select></label><button type="button" onClick={() => void createInitialArtifact()} disabled={busy}>{busy ? "正在建立…" : `建立${KIND_LABEL[newKind]} →`}</button>{error && <p className="cycle-action-error" role="alert">{error}</p>}</section>}

      <aside className="artifact-history"><span>版本与审批</span>{detail.artifacts.map((artifact) => <div key={artifact.id}><i className={`status-${artifact.status}`} /><p><b>{KIND_LABEL[artifact.kind]} v{artifact.version}</b><small>{STATUS_LABEL[artifact.status]} · {artifact.created_by === "user" ? "用户" : artifact.created_by}</small></p></div>)}{detail.deliveries.length > 0 && <><span className="history-subhead">导出与实施</span>{detail.deliveries.map((delivery) => <div key={delivery.id}><i className={`status-${delivery.status}`} /><p><b>{delivery.status === "published" ? "已实施" : "已导出"}</b><small>{delivery.method}{delivery.target_url ? ` · ${delivery.target_url}` : ""}</small></p></div>)}</>}</aside>
    </main>
  </div>;
}

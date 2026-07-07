"use client";

import { useState } from "react";
import { api, type CitationRunResponse, type EngineInfo } from "@/lib/api";

const ALL_ENGINES = [
  "deepseek",
  "qwen",
  "kimi",
  "baidu_ernie",
  "doubao",
  "yuanbao",
  "chatgpt",
  "perplexity",
];

export default function VisibilityPage() {
  const [brand, setBrand] = useState("keeplix");
  const [domain, setDomain] = useState("keeplix.com");
  const [promptsText, setPromptsText] = useState(
    "最好的 GEO 工具\n如何做中文内容优化",
  );
  const [selected, setSelected] = useState<string[]>(["deepseek", "kimi", "baidu_ernie"]);
  const [samples, setSamples] = useState(3);
  const [data, setData] = useState<CitationRunResponse | null>(null);
  const [engines, setEngines] = useState<EngineInfo[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadEngines() {
    try {
      setEngines(await api.engines());
    } catch {
      setEngines(null);
    }
  }

  async function run() {
    setLoading(true);
    setError(null);
    setData(null);
    try {
      const prompts = promptsText.split("\n").map((s) => s.trim()).filter(Boolean);
      const result = await api.runCitations({
        engine_ids: selected,
        prompts,
        brand_name: brand,
        brand_domains: domain ? [domain] : undefined,
        samples,
      });
      setData(result);
      await loadEngines();
    } catch (e) {
      setError(e instanceof Error ? e.message : "请求失败");
    } finally {
      setLoading(false);
    }
  }

  function toggle(id: string) {
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  }

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold">引擎可见度（Citation 采样）</h1>

      <section className="rounded-lg border border-neutral-200 bg-white p-6">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <label>
            <span className="mb-1 block text-sm text-neutral-600">品牌名</span>
            <input
              className="w-full rounded-md border border-neutral-300 px-3 py-2"
              value={brand}
              onChange={(e) => setBrand(e.target.value)}
            />
          </label>
          <label>
            <span className="mb-1 block text-sm text-neutral-600">品牌域名</span>
            <input
              className="w-full rounded-md border border-neutral-300 px-3 py-2"
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
            />
          </label>
          <label>
            <span className="mb-1 block text-sm text-neutral-600">每 prompt 采样次数</span>
            <input
              type="number"
              min={1}
              max={20}
              className="w-full rounded-md border border-neutral-300 px-3 py-2"
              value={samples}
              onChange={(e) => setSamples(Number(e.target.value) || 1)}
            />
          </label>
        </div>
        <label className="mt-4 block">
          <span className="mb-1 block text-sm text-neutral-600">Prompt 集（每行一条）</span>
          <textarea
            className="h-24 w-full rounded-md border border-neutral-300 px-3 py-2"
            value={promptsText}
            onChange={(e) => setPromptsText(e.target.value)}
          />
        </label>
        <div className="mt-4">
          <span className="mb-1 block text-sm text-neutral-600">引擎</span>
          <div className="flex flex-wrap gap-2">
            {ALL_ENGINES.map((id) => (
              <button
                key={id}
                onClick={() => toggle(id)}
                className={`rounded-full border px-3 py-1 text-sm ${
                  selected.includes(id)
                    ? "border-black bg-black text-white"
                    : "border-neutral-300 hover:bg-neutral-100"
                }`}
              >
                {id}
              </button>
            ))}
          </div>
        </div>
        <button
          onClick={run}
          disabled={loading || selected.length === 0}
          className="mt-4 rounded-md bg-black px-4 py-2 text-sm font-medium text-white hover:opacity-80 disabled:opacity-50"
        >
          {loading ? "采样中…" : "运行采样"}
        </button>
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      </section>

      {data && (
        <section className="rounded-lg border border-neutral-200 bg-white p-6">
          <h2 className="mb-4 text-lg font-semibold">Share of Voice</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-neutral-200 text-left text-neutral-500">
                  <th className="py-2">引擎</th>
                  <th>entity-SoV（被点名率）</th>
                  <th>citation-SoV（被引用率）</th>
                  <th>平均排名</th>
                  <th>样本数</th>
                </tr>
              </thead>
              <tbody>
                {data.results.map((r) => (
                  <tr key={r.engine_id} className="border-b border-neutral-100">
                    <td className="py-2 font-medium">{r.engine_id}</td>
                    <td>
                      <Bar value={r.entity_sov} />
                    </td>
                    <td>
                      <Bar value={r.citation_sov} />
                    </td>
                    <td>{r.avg_rank ?? "—"}</td>
                    <td>{r.sample_size}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {engines && (
            <p className="mt-4 text-xs text-neutral-400">
              当前 provider 状态：{engines.filter((e) => !e.is_stub).map((e) => e.id).join(", ") || "全部为 stub（未配置 key）"}
            </p>
          )}
        </section>
      )}
    </div>
  );
}

function Bar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-32 overflow-hidden rounded bg-neutral-200">
        <div className="h-full bg-black" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-neutral-600">{pct}%</span>
    </div>
  );
}

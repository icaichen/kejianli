"use client";

import { useState } from "react";
import { api, type AnalysisResponse, type Recommendation } from "@/lib/api";

const SEVERITY_STYLE: Record<Recommendation["severity"], string> = {
  high: "bg-red-100 text-red-700",
  medium: "bg-amber-100 text-amber-700",
  low: "bg-neutral-100 text-neutral-600",
};

const SEVERITY_LABEL: Record<Recommendation["severity"], string> = {
  high: "高",
  medium: "中",
  low: "低",
};

export default function AnalysesPage() {
  const [url, setUrl] = useState("https://example.com");
  const [brand, setBrand] = useState("keeplix");
  const [engineId, setEngineId] = useState("");
  const [data, setData] = useState<AnalysisResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setLoading(true);
    setError(null);
    setData(null);
    try {
      const result = await api.analyze({
        url,
        brand_name: brand || undefined,
        engine_id: engineId || null,
      });
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "请求失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold">内容 GEO 分析</h1>

      <section className="rounded-lg border border-neutral-200 bg-white p-6">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <label className="md:col-span-2">
            <span className="mb-1 block text-sm text-neutral-600">网址 URL</span>
            <input
              className="w-full rounded-md border border-neutral-300 px-3 py-2"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://your-site.com/page"
            />
          </label>
          <label>
            <span className="mb-1 block text-sm text-neutral-600">品牌名</span>
            <input
              className="w-full rounded-md border border-neutral-300 px-3 py-2"
              value={brand}
              onChange={(e) => setBrand(e.target.value)}
            />
          </label>
          <label className="md:col-span-3">
            <span className="mb-1 block text-sm text-neutral-600">
              引擎档（可选，留空=通用档）
            </span>
            <input
              className="w-full rounded-md border border-neutral-300 px-3 py-2"
              value={engineId}
              onChange={(e) => setEngineId(e.target.value)}
              placeholder="如 baidu_ernie / kimi / doubao"
            />
          </label>
        </div>
        <button
          onClick={run}
          disabled={loading}
          className="mt-4 rounded-md bg-black px-4 py-2 text-sm font-medium text-white hover:opacity-80 disabled:opacity-50"
        >
          {loading ? "分析中…" : "开始分析"}
        </button>
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      </section>

      {data && (
        <>
          <section className="rounded-lg border border-neutral-200 bg-white p-6">
            <div className="flex items-baseline gap-4">
              <div>
                <div className="text-sm text-neutral-500">GEO 总分</div>
                <div className="text-4xl font-bold">{data.total}</div>
              </div>
              <div className="text-sm text-neutral-500">
                抓取状态 {data.status} · {data.url}
              </div>
            </div>
            <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {Object.entries(data.breakdown).map(([dim, d]) => (
                <div key={dim} className="rounded-md border border-neutral-200 p-3">
                  <div className="text-xs text-neutral-500">{dim}</div>
                  <div className="text-lg font-semibold">
                    {d.score}
                    <span className="text-xs font-normal text-neutral-400">
                      {" "}
                      / 权重 {d.weight}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="rounded-lg border border-neutral-200 bg-white p-6">
            <h2 className="mb-4 text-lg font-semibold">
              可执行建议（{data.recommendations.length}）
            </h2>
            <ul className="space-y-3">
              {data.recommendations.map((r, i) => (
                <li key={i} className="rounded-md border border-neutral-200 p-4">
                  <div className="flex items-center gap-2">
                    <span
                      className={`rounded px-2 py-0.5 text-xs ${SEVERITY_STYLE[r.severity]}`}
                    >
                      {SEVERITY_LABEL[r.severity]}
                    </span>
                    <span className="text-xs text-neutral-400">{r.dimension}</span>
                    {r.compliance_flag && (
                      <span className="rounded bg-red-600 px-2 py-0.5 text-xs text-white">
                        合规红线
                      </span>
                    )}
                  </div>
                  <div className="mt-1 font-medium">{r.title}</div>
                  <div className="text-sm text-neutral-600">{r.detail}</div>
                  {r.jsonld && (
                    <details className="mt-2">
                      <summary className="cursor-pointer text-xs text-neutral-500">
                        生成的 Schema JSON-LD
                      </summary>
                      <pre className="mt-1 overflow-x-auto rounded bg-neutral-50 p-2 text-xs">
                        {JSON.stringify(r.jsonld, null, 2)}
                      </pre>
                    </details>
                  )}
                </li>
              ))}
            </ul>
          </section>
        </>
      )}
    </div>
  );
}

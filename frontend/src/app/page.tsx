export default function Home() {
  return (
    <div className="space-y-8">
      <section className="space-y-4">
        <h1 className="text-3xl font-bold tracking-tight">
          让你的内容被 AI 主动看见、引用、推荐
        </h1>
        <p className="max-w-2xl text-neutral-600">
          可见力（keeplix）是面向中国 indie dev 与内容创作者的 Agentic GEO
          平台：内容审计打分、可执行优化建议、多引擎 citation 采样。
          无需任何模型 key 即可完整体验（确定性 stub 数据）。
        </p>
        <div className="flex gap-4">
          <a
            href="/analyses"
            className="rounded-md bg-black px-4 py-2 text-sm font-medium text-white hover:opacity-80"
          >
            开始内容分析 →
          </a>
          <a
            href="/visibility"
            className="rounded-md border border-neutral-300 px-4 py-2 text-sm font-medium hover:bg-neutral-100"
          >
            查看引擎可见度
          </a>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {[
          {
            t: "GEO 评分",
            d: "7 维 rubric（技术/结构/权威/新鲜/引用友好/实体对齐/墙花园），按引擎分档，0–100 分。",
          },
          {
            t: "可执行建议",
            d: "从每个未达标项生成建议，含 Schema JSON-LD 自动生成与合规红线提示。",
          },
          {
            t: "Citation 采样",
            d: "对文心/豆包/Kimi/通义/DeepSeek 等采样，输出 entity-SoV 与 citation-SoV。",
          },
        ].map((c) => (
          <div key={c.t} className="rounded-lg border border-neutral-200 bg-white p-5">
            <h3 className="mb-2 font-semibold">{c.t}</h3>
            <p className="text-sm text-neutral-600">{c.d}</p>
          </div>
        ))}
      </section>
    </div>
  );
}

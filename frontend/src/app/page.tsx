import Link from "next/link";
import { AuditEntry } from "./audit-entry";

const layers = [
  {
    number: "01",
    label: "看见",
    title: "检测与追踪",
    promise: "告诉我，现在表现如何。",
    detail: "审计你的网站，追踪品牌在 DeepSeek、豆包、Kimi、文心、通义和海外 AI 中的提及、引用与竞争位置。",
    action: "检测我的网站",
    href: "/analyses",
  },
  {
    number: "02",
    label: "提升",
    title: "GEO 工具箱",
    promise: "给我做好优化需要的一切。",
    detail: "把每个问题直接变成行动：研究用户问题、重写可引用内容、生成 FAQ 与结构化数据，并在发布前验证。",
    action: "从建议开始优化",
    href: "/analyses",
  },
  {
    number: "03",
    label: "托管",
    title: "AI GEO 执行",
    promise: "告诉我目标，持续替我完成。",
    detail: "AI 制定计划、调用工具、生成任务与内容，等待你的审批，并根据可见度变化进入下一轮优化。",
    action: "了解 AI 执行",
    href: "#agent",
  },
];

const engineNames = ["DeepSeek", "豆包", "Kimi", "文心", "通义", "ChatGPT", "Perplexity"];

export default function Home() {
  return (
    <>
      <section className="home-hero">
        <div className="hero-copy">
          <div className="overline"><span>中文 GEO 平台</span><span>为答案时代而生</span></div>
          <h1>成为 AI<br />选择的<em>答案。</em></h1>
          <p className="hero-lede">检测你的品牌是否被 AI 理解、引用和推荐。修复最重要的问题，或者让 AI 持续替你完成 GEO 工作。</p>
          <AuditEntry />
          <div className="engine-line" aria-label="支持的 AI 引擎">
            <span>覆盖</span>
            {engineNames.map((name) => <b key={name}>{name}</b>)}
          </div>
        </div>

        <aside className="hero-report" aria-label="示例 GEO 检测报告">
          <div className="report-head">
            <div><small>AI 可见度检测</small><strong>yourbrand.cn</strong></div>
            <span className="status-dot">示例报告</span>
          </div>
          <div className="report-score">
            <div><small>综合可见度</small><strong>72<span>/100</span></strong></div>
            <div className="score-explain">
              <p><b>基础良好。</b>品牌信息可以被理解，但缺少容易被引用的权威表达。</p>
              <div className="score-track"><i style={{ width: "72%" }} /></div>
              <small>高于同类项目中的多数基础页面</small>
            </div>
          </div>
          <div className="report-signals">
            {[
              ["实体清晰度", "86%"],
              ["引用准备度", "61%"],
              ["内容权威性", "58%"],
            ].map(([label, value], index) => (
              <div className="signal" key={label}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <strong>{label}</strong>
                <b>{value}</b>
              </div>
            ))}
          </div>
          <div className="report-finding">
            <span className="finding-index">01</span>
            <div><small>最高影响问题</small><h2>缺少可引用的品牌定义</h2><p>页面介绍了功能，却没有一句能够让 AI 直接提取和引用的清晰定义。</p></div>
          </div>
        </aside>
      </section>

      <section className="promise-strip">
        <p>一个项目，完成从检测到增长的整个循环。</p>
        <span>检测</span><i>→</i><span>优化</span><i>→</i><span>执行</span><i>→</i><span>再验证</span>
      </section>

      <section className="product-section" id="product">
        <div className="section-heading">
          <div className="overline"><span>三层产品</span><span>一个持续升级的旅程</span></div>
          <h2>从看见问题，<br />到把事情<em>做完。</em></h2>
          <p>你不需要先理解复杂的 GEO 工具。先从一次检测开始，再决定自己优化、持续追踪，还是把执行交给 AI。</p>
        </div>
        <div className="layer-list">
          {layers.map((layer) => (
            <article className="layer-card" key={layer.number}>
              <div className="layer-number">{layer.number}</div>
              <div className="layer-body"><span>{layer.label}</span><h3>{layer.title}</h3><blockquote>{layer.promise}</blockquote><p>{layer.detail}</p></div>
              <Link href={layer.href}>{layer.action} <span aria-hidden="true">→</span></Link>
            </article>
          ))}
        </div>
      </section>

      <section className="agent-section" id="agent">
        <div className="agent-intro">
          <div className="overline overline-light"><span>AI GEO 执行</span><span>不是另一个聊天框</span></div>
          <h2>你给目标，<br />可见力负责<em>循环。</em></h2>
          <p>AI Agent 读取检测结果，制定优先级，调用优化工具，生成可审批的任务，并通过下一轮检测验证真实变化。</p>
          <Link href="/analyses" className="light-action">先建立我的基线 <span aria-hidden="true">↗</span></Link>
        </div>
        <ol className="agent-loop">
          {[
            ["诊断", "找到最影响 AI 引用和推荐的问题"],
            ["计划", "按预期影响、工作量和风险安排任务"],
            ["执行", "生成内容、结构化数据和发布建议"],
            ["审批", "由你决定修改、发布或跳过"],
            ["验证", "重新检测并进入下一轮优化"],
          ].map(([title, detail], index) => (
            <li key={title}><span>{String(index + 1).padStart(2, "0")}</span><div><strong>{title}</strong><p>{detail}</p></div></li>
          ))}
        </ol>
      </section>

      <section className="method-section" id="method">
        <div><small>我们的原则</small><h2>证据优先，<br />拒绝空洞分数。</h2></div>
        <p>每项建议都应该对应可检查的页面信号、引擎表现或竞争差距。可见力不会承诺“百分之百被收录”，也不会用低质量刷量冒充增长。</p>
        <AuditEntry compact />
      </section>
    </>
  );
}

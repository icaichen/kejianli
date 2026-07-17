import Link from "next/link";
import { AuditEntry } from "./audit-entry";

const layers = [
  {
    number: "01",
    label: "基线",
    title: "AI 市场测量",
    promise: "品牌在 AI 答案中的位置如何？",
    detail: "围绕真实消费者与采购问题，测量品牌提及、推荐、引用来源和相对竞品份额。",
    action: "新建研究项目",
    href: "/start",
  },
  {
    number: "02",
    label: "洞察",
    title: "竞争与来源分析",
    promise: "解释品牌为何出现，竞品为何被推荐。",
    detail: "按市场、品类、问题意图和答案面拆解推荐理由、内容主题、来源结构与证据缺口。",
    action: "定义研究范围",
    href: "/start",
  },
  {
    number: "03",
    label: "持续",
    title: "追踪与客户交付",
    promise: "固定口径，持续观察市场变化。",
    detail: "保存问题集、答案证据和趋势，为品牌团队、管理层或咨询客户提供可复查的研究结论。",
    action: "了解持续研究",
    href: "#agent",
  },
];

const engineNames = ["DeepSeek", "豆包", "Kimi", "文心", "通义", "ChatGPT", "Perplexity"];

export default function Home() {
  return (
    <>
      <section className="home-hero">
        <div className="hero-copy">
          <div className="overline"><span>企业 AI 市场研究</span><span>面向品牌与咨询团队</span></div>
          <h1>看见 AI<br />如何<em>定义市场。</em></h1>
          <p className="hero-lede">研究你的品牌和竞品在 AI 答案中如何被提及、推荐与引用，并让每一条市场结论都能回到真实证据。</p>
          <AuditEntry />
          <div className="engine-line" aria-label="支持的 AI 引擎">
            <span>覆盖</span>
            {engineNames.map((name) => <b key={name}>{name}</b>)}
          </div>
        </div>

        <aside className="hero-report" aria-label="示例 GEO 检测报告">
          <div className="report-head">
            <div><small>AI 市场基线</small><strong>中国个人护理 · 示例</strong></div>
            <span className="status-dot">研究摘要</span>
          </div>
          <div className="report-score">
            <div><small>品牌答案份额</small><strong>32<span>%</span></strong></div>
            <div className="score-explain">
              <p><b>品类认知较强。</b>但在问题型查询中，竞品更常因具体功效和第三方来源被推荐。</p>
              <div className="score-track"><i style={{ width: "32%" }} /></div>
              <small>基于同一问题集中的品牌与竞品提及份额</small>
            </div>
          </div>
          <div className="report-signals">
            {[
              ["品牌提及率", "46%"],
              ["最高竞品", "38%"],
              ["自有来源引用", "18%"],
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
            <div><small>最高影响洞察</small><h2>敏感肌问题中，竞品更常被推荐</h2><p>差距主要来自功效证据和第三方专业来源，而不是品牌知名度本身。</p></div>
          </div>
        </aside>
      </section>

      <section className="promise-strip">
        <p>一个研究项目，保持从问题到结论的完整证据链。</p>
        <span>研究范围</span><i>→</i><span>答案采样</span><i>→</i><span>竞争洞察</span><i>→</i><span>持续追踪</span>
      </section>

      <section className="product-section" id="product">
        <div className="section-heading">
          <div className="overline"><span>三层产品</span><span>一个持续升级的旅程</span></div>
          <h2>从商业问题，<br />到可交付的<em>市场证据。</em></h2>
          <p>咨询顾问和品牌团队先定义市场、品类、品牌与竞品，再用一致口径采样、分析和追踪 AI 答案。</p>
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
          <div className="overline overline-light"><span>持续研究工作流</span><span>不是一次性截图</span></div>
          <h2>你定义问题，<br />可见力保持<em>研究口径。</em></h2>
          <p>固定市场、品牌、竞品、问题集和答案面，持续保存原始证据与变化，让团队和客户可以复查每一条结论。</p>
          <Link href="/start" className="light-action">建立第一份研究 Brief <span aria-hidden="true">↗</span></Link>
        </div>
        <ol className="agent-loop">
          {[
            ["定义", "明确客户、市场、品类、品牌和竞争范围"],
            ["采样", "用固定问题集收集真实 AI 答案"],
            ["核验", "保存请求、答案、来源和采集条件"],
            ["解释", "比较品牌份额、推荐理由和来源差距"],
            ["追踪", "用相同口径观察变化并形成汇报"],
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

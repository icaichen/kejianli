import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { Providers } from "./providers";

const siteUrl = new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000");

export const metadata: Metadata = {
  metadataBase: siteUrl,
  title: "可见力 · 企业 AI 市场研究与品牌可见度",
  description: "为品牌团队与咨询公司研究 AI 答案中的品牌份额、竞品表现、推荐理由与来源证据。",
  openGraph: {
    title: "可见力 · 成为 AI 选择的答案",
    description: "研究 AI 答案中的品牌份额、竞品表现与来源证据。",
    type: "website",
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "可见力 GEO 平台" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "可见力 · 成为 AI 选择的答案",
    description: "研究 AI 答案中的品牌份额、竞品表现与来源证据。",
    images: ["/og.png"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="zh-CN"
      data-scroll-behavior="smooth"
    >
      <body>
        <Providers>
          <a className="skip-link" href="#main-content">跳到主要内容</a>
          <header className="site-header">
            <nav className="nav-shell" aria-label="主导航">
              <Link href="/" className="wordmark" aria-label="可见力首页">
                <span className="wordmark-seal" aria-hidden="true">见</span>
                <span>可见力</span>
                <small>keeplix</small>
              </Link>
              <div className="nav-links">
                <Link href="/#product">怎么工作</Link>
                <Link href="/projects">项目</Link>
                <Link href="/#method">方法</Link>
              </div>
              <Link className="nav-cta" href="/start">新建研究项目 <span aria-hidden="true">↗</span></Link>
            </nav>
          </header>
          <main id="main-content">{children}</main>
          <footer className="site-footer">
            <div className="footer-shell">
              <Link href="/" className="wordmark wordmark-inverse">
                <span className="wordmark-seal" aria-hidden="true">见</span>
                <span>可见力</span>
              </Link>
              <p>让每一个 AI 市场结论都能回到真实答案与来源。</p>
              <Link href="/start" className="footer-action">新建 AI 市场研究 <span aria-hidden="true">↗</span></Link>
            </div>
          </footer>
        </Providers>
      </body>
    </html>
  );
}

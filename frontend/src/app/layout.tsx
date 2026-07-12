import type { Metadata } from "next";
import Link from "next/link";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

const geist = Geist({ subsets: ["latin"], variable: "--font-geist" });
const geistMono = Geist_Mono({ subsets: ["latin"], variable: "--font-geist-mono" });

const siteUrl = new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000");

export const metadata: Metadata = {
  metadataBase: siteUrl,
  title: "可见力 · 让 AI 看见、引用和推荐你的品牌",
  description: "从检测 AI 可见度，到完成 GEO 优化，再到让 AI 持续执行。面向中文内容与国产模型的 GEO 平台。",
  openGraph: {
    title: "可见力 · 成为 AI 选择的答案",
    description: "检测、优化并持续提升你的 AI 可见度。",
    type: "website",
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "可见力 GEO 平台" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "可见力 · 成为 AI 选择的答案",
    description: "检测、优化并持续提升你的 AI 可见度。",
    images: ["/og.png"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="zh-CN"
      className={`${geist.variable} ${geistMono.variable}`}
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
                <Link href="/#product">产品</Link>
                <Link href="/analyses">检测</Link>
                <Link href="/visibility">可见度</Link>
                <Link href="/optimize">优化</Link>
                <Link href="/projects">项目</Link>
                <Link href="/#method">方法</Link>
              </div>
              <Link className="nav-cta" href="/analyses">免费检测 <span aria-hidden="true">↗</span></Link>
            </nav>
          </header>
          <main id="main-content">{children}</main>
          <footer className="site-footer">
            <div className="footer-shell">
              <Link href="/" className="wordmark wordmark-inverse">
                <span className="wordmark-seal" aria-hidden="true">见</span>
                <span>可见力</span>
              </Link>
              <p>从发现问题，到完成优化，再到持续增长。</p>
              <Link href="/analyses" className="footer-action">检测我的 AI 可见度 <span aria-hidden="true">↗</span></Link>
            </div>
          </footer>
        </Providers>
      </body>
    </html>
  );
}

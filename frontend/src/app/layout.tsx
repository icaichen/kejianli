import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "可见力 keeplix · Agentic GEO 平台",
  description: "让你的内容被 AI 主动看见、引用、推荐 —— 懂中文、支持百度与国产模型。",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen bg-neutral-50 text-neutral-900 antialiased">
        <Providers>
          <header className="border-b border-neutral-200 bg-white">
            <nav className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
              <a href="/" className="font-semibold">
                可见力 <span className="text-neutral-400">keeplix</span>
              </a>
              <div className="flex gap-6 text-sm text-neutral-600">
                <a href="/analyses" className="hover:text-black">
                  内容分析
                </a>
                <a href="/visibility" className="hover:text-black">
                  引擎可见度
                </a>
              </div>
            </nav>
          </header>
          <main className="mx-auto max-w-5xl px-6 py-10">{children}</main>
        </Providers>
      </body>
    </html>
  );
}

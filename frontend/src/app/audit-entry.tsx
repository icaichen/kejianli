"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

export function AuditEntry({ compact = false }: { compact?: boolean }) {
  const router = useRouter();
  const [url, setUrl] = useState("");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = url.trim();
    if (!value) return;
    const normalized = /^https?:\/\//i.test(value) ? value : `https://${value}`;
    router.push(`/analyses?url=${encodeURIComponent(normalized)}&run=1`);
  }

  return (
    <form className={compact ? "audit-entry audit-entry-compact" : "audit-entry"} onSubmit={submit}>
      <label htmlFor={compact ? "footer-url" : "hero-url"}>网站地址</label>
      <div>
        <span aria-hidden="true">https://</span>
        <input
          id={compact ? "footer-url" : "hero-url"}
          value={url}
          onChange={(event) => setUrl(event.target.value)}
          placeholder="你的品牌网址"
          inputMode="url"
          autoComplete="url"
          suppressHydrationWarning
          required
        />
        <button type="submit">免费检测 <span aria-hidden="true">→</span></button>
      </div>
      {!compact && <p>无需注册 · 先查看基础结果 · 约 30–60 秒</p>}
    </form>
  );
}

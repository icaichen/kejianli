"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

export function AuditEntry({ compact = false }: { compact?: boolean }) {
  const router = useRouter();
  const [brand, setBrand] = useState("");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = brand.trim();
    if (!value) return;
    router.push(`/start?brand=${encodeURIComponent(value)}`);
  }

  return (
    <form className={compact ? "audit-entry audit-entry-compact" : "audit-entry"} onSubmit={submit}>
      <label htmlFor={compact ? "footer-url" : "hero-url"}>品牌或客户</label>
      <div>
        <span aria-hidden="true">研究</span>
        <input
          id={compact ? "footer-url" : "hero-url"}
          value={brand}
          onChange={(event) => setBrand(event.target.value)}
          placeholder="客户、品牌或品类"
          autoComplete="organization"
          suppressHydrationWarning
          required
        />
        <button type="submit">创建研究项目 <span aria-hidden="true">→</span></button>
      </div>
      {!compact && <p>适用于品牌团队、咨询公司与市场研究项目</p>}
    </form>
  );
}

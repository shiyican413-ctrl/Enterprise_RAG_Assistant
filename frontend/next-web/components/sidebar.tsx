"use client";

import { cn } from "@/lib/utils";
import { navItems, productHighlights } from "@/lib/types";
import { API_BASE_URL } from "@/lib/api";
import { LogoIcon } from "@/components/icons";
import { Separator } from "@/components/ui/separator";

type SidebarProps = {
  isHealthy: boolean;
};

export function Sidebar({ isHealthy }: SidebarProps) {
  return (
    <aside className="sticky top-4 flex h-[calc(100vh-2rem)] flex-col gap-5 rounded-xl border border-border bg-card p-4">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-500 text-white">
          <LogoIcon className="size-5" />
        </div>
        <div>
          <div className="text-sm font-semibold tracking-tight">企业知识库助手</div>
          <div className="text-xs text-muted-foreground">智能问答平台</div>
        </div>
      </div>

      <nav className="grid gap-1">
        {navItems.map((item, index) => (
          <button
            key={item}
            type="button"
            className={cn(
              "flex h-9 items-center gap-3 rounded-lg px-3 text-sm transition-colors",
              index === 0
                ? "bg-brand-50 font-medium text-brand-700"
                : "text-muted-foreground hover:bg-muted",
            )}
          >
            <span className="font-mono text-xs font-bold text-brand-400">
              {String(index + 1).padStart(2, "0")}
            </span>
            {item}
          </button>
        ))}
      </nav>

      <Separator />

      <section>
        <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-brand-500">
          项目能力
        </p>
        <div className="grid gap-2">
          {productHighlights.map((item) => (
            <div key={item} className="flex items-center gap-2 text-sm text-muted-foreground">
              <span className="size-1.5 rounded-full bg-brand-400" />
              {item}
            </div>
          ))}
        </div>
      </section>

      <Separator />

      <section className="mt-auto">
        <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-brand-500">
          服务状态
        </p>
        <code className="mb-2 block truncate rounded-lg border border-border bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
          {API_BASE_URL}
        </code>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span
            className={cn(
              "size-2 rounded-full",
              isHealthy ? "bg-green-500" : "bg-muted-foreground/50",
            )}
          />
          {isHealthy ? "后端服务在线" : "等待后端启动"}
        </div>
      </section>
    </aside>
  );
}

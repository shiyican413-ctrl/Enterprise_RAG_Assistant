"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ArrowLeft,
  CircleHelp,
  Database,
  FileClock,
  FileSearch,
  MessageCircleQuestion,
  Route,
  ShieldCheck,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { productHighlights } from "@/lib/types";
import { useAuth } from "@/components/auth/auth-provider";

type SidebarProps = {
  isHealthy: boolean;
};

const navItems = [
  { label: "智能问答", href: "/console", icon: FileSearch },
  { label: "知识库", href: "/knowledge", icon: Database },
  { label: "会话记录", href: "/conversations", icon: FileClock },
  { label: "权限审计", href: "/audit", icon: ShieldCheck, disabled: true },
];

export function Sidebar({ isHealthy }: SidebarProps) {
  const { user } = useAuth();
  const pathname = usePathname();
  const highlightIcons = [Route, FileSearch, Database, ShieldCheck];
  const highlightItems = productHighlights.map((label, index) => ({
    label,
    icon: highlightIcons[index] ?? Route,
  }));

  const footerItems = [
    { label: "帮助中心", icon: CircleHelp },
    { label: isHealthy ? "后端服务在线" : "等待后端启动", icon: ShieldCheck },
    { label: "企微助手", icon: MessageCircleQuestion },
  ];

  // Palette is driven by CSS variables so the same component can sit inside
  // the dark console shell or a workspace shell without duplicating markup.
  return (
    <aside className="flex h-full w-full flex-col border-r border-[var(--side-border)] bg-[var(--side-bg)] shadow-[8px_0_32px_rgba(16,24,40,0.04)]">
      <div className="flex h-[72px] items-center gap-3 px-6">
        <div className="relative grid size-11 shrink-0 place-items-center rounded-[14px] bg-[var(--side-active-ring)] text-sm font-bold text-[var(--side-avatar-fg)] shadow-[0_10px_24px_rgba(17,19,23,0.16)]">
          {user?.name?.slice(0, 1).toUpperCase() ?? "R"}
        </div>
        <div className="text-[20px] font-bold leading-none tracking-normal text-[var(--side-fg)]">
          <span className="min-w-0 truncate">{user?.tenant_name || "企业 RAG"}</span>
        </div>
      </div>

      <div className="flex items-center gap-3 px-6 pb-7 pt-3 text-[20px] font-semibold text-[var(--side-fg)]">
        <ArrowLeft className="size-5" strokeWidth={2.1} />
        <span>工作台</span>
      </div>

      <nav className="flex-1 px-3">
        <p className="px-3 pb-3 text-sm font-medium text-[var(--side-muted)]">核心功能</p>
        <div className="grid gap-1.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive =
              item.href === "/console" ? pathname === "/console" : pathname.startsWith(item.href);
            const className = cn(
              "flex h-11 items-center gap-3 rounded-[12px] border border-transparent px-4 text-[16px] font-medium text-[var(--side-fg)] transition-colors hover:bg-[var(--side-hover)]",
              isActive && "border-[var(--side-border)] bg-[var(--side-active-bg)] font-semibold shadow-sm",
              item.disabled && "cursor-not-allowed opacity-60 hover:bg-transparent",
            );

            if (item.disabled) {
              return (
                <div key={item.label} className={className} aria-disabled="true">
                  <Icon className="size-5" strokeWidth={2.1} />
                  <span>{item.label}</span>
                </div>
              );
            }

            return (
              <Link key={item.label} href={item.href} className={className}>
                <Icon className="size-5" strokeWidth={2.1} />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </div>

        <p className="px-3 pb-3 pt-7 text-sm font-medium text-[var(--side-muted)]">项目能力</p>
        <div className="grid gap-1">
          {highlightItems.map((item) => {
            const Icon = item.icon;
            return (
              <div
                key={item.label}
                className="flex h-9 items-center gap-3 rounded-[10px] px-4 text-sm font-medium text-[var(--side-muted)]"
              >
                <Icon className="size-4 text-[var(--side-accent)]" strokeWidth={2.1} />
                <span>{item.label}</span>
              </div>
            );
          })}
        </div>
      </nav>

      <div className="border-t border-[var(--side-border)] px-3 py-5">
        {footerItems.map((item, index) => {
          const Icon = item.icon;
          return (
            <button
              key={item.label}
              type="button"
              className="flex h-11 w-full items-center gap-3 rounded-[12px] px-4 text-[16px] font-medium text-[var(--side-fg)] transition-colors hover:bg-[var(--side-hover)]"
            >
              <Icon
                className={cn(
                  "size-5",
                  index === 1 && (isHealthy ? "text-emerald-500" : "text-[var(--side-muted)]"),
                )}
                strokeWidth={2.1}
              />
              <span>{item.label}</span>
            </button>
          );
        })}
      </div>
    </aside>
  );
}

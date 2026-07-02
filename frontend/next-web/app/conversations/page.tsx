"use client";

import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  CircleCheck,
  Edit3,
  Loader2,
  MessageSquareText,
  Pin,
  PinOff,
  Search,
  Trash2,
  UserRound,
} from "lucide-react";
import {
  checkHealth,
  deleteConversation,
  fetchConversations,
  updateConversation,
} from "@/lib/api";
import type { ConversationSummary } from "@/lib/api";
import { RequireAuth } from "@/components/auth/require-auth";
import { useAuth } from "@/components/auth/auth-provider";
import { Sidebar } from "@/components/sidebar";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import "../console/console.css";

export default function ConversationsPage() {
  const router = useRouter();
  const { user, logout } = useAuth();
  const [isHealthy, setIsHealthy] = useState(false);
  const [query, setQuery] = useState("");
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [notice, setNotice] = useState<string>();

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setIsLoading(true);
      const [healthy, items] = await Promise.all([
        checkHealth(),
        fetchConversations(query).catch((error) => {
          setNotice(error instanceof Error ? error.message : "会话加载失败");
          return [];
        }),
      ]);
      if (cancelled) return;
      setIsHealthy(healthy);
      setConversations(items);
      setIsLoading(false);
    }

    const timer = setTimeout(() => {
      void load();
    }, 180);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [query]);

  const grouped = useMemo(() => {
    return [...conversations].sort((a, b) => {
      if (a.pinned !== b.pinned) return a.pinned ? -1 : 1;
      return dateValue(b.last_message_at ?? b.updated_at) - dateValue(a.last_message_at ?? a.updated_at);
    });
  }, [conversations]);

  async function handleRename(item: ConversationSummary) {
    const title = window.prompt("重命名会话", item.title);
    if (title === null) return;
    const nextTitle = title.trim();
    if (!nextTitle) {
      setNotice("会话标题不能为空。");
      return;
    }
    const updated = await updateConversation(item.conversation_id, { title: nextTitle });
    setConversations((current) =>
      current.map((conversation) =>
        conversation.conversation_id === item.conversation_id ? updated : conversation,
      ),
    );
  }

  async function handleTogglePinned(item: ConversationSummary) {
    const updated = await updateConversation(item.conversation_id, {
      pinned: !item.pinned,
    });
    setConversations((current) =>
      current.map((conversation) =>
        conversation.conversation_id === item.conversation_id ? updated : conversation,
      ),
    );
  }

  async function handleDelete(item: ConversationSummary) {
    const ok = window.confirm(`删除会话“${item.title}”？此操作会同时删除完整问答记录。`);
    if (!ok) return;
    await deleteConversation(item.conversation_id);
    setConversations((current) =>
      current.filter((conversation) => conversation.conversation_id !== item.conversation_id),
    );
  }

  return (
    <RequireAuth>
      <div className="workspace-root min-h-screen bg-[var(--workspace-canvas)] text-[var(--work-text)] lg:overflow-hidden">
        <div className="grid min-h-screen grid-cols-1 lg:h-screen lg:grid-cols-[280px_minmax(0,1fr)]">
          <div className="hidden min-h-0 lg:block">
            <Sidebar isHealthy={isHealthy} />
          </div>

          <main className="flex min-h-0 min-w-0 flex-col">
            <header className="flex h-14 shrink-0 items-center justify-between border-b border-[var(--work-border)] bg-[var(--work-surface)] px-4 sm:px-7">
              <div className="hidden items-center gap-3 lg:flex">
                <span className="console-mono">企业知识库智能问答平台</span>
                <span className="h-4 w-px bg-[var(--work-border)]" />
                <span className="text-[15px] font-semibold text-[var(--work-text)]">会话记录</span>
              </div>
              <div className="flex items-center gap-3 lg:hidden">
                <span className="grid size-8 place-items-center rounded-full bg-[var(--workspace-brand)] text-sm font-bold text-white">
                  R
                </span>
                <span className="text-lg font-bold text-[var(--work-text)]">会话记录</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="hidden h-10 items-center gap-2 rounded-[10px] px-3 text-sm font-semibold text-[var(--ash)] sm:flex">
                  <CircleCheck
                    className={isHealthy ? "size-4 text-emerald-500" : "size-4 text-[var(--ash)]"}
                  />
                  {isHealthy ? "服务在线" : "等待后端"}
                </div>
                <button
                  type="button"
                  className="grid size-10 place-items-center rounded-full border border-[var(--work-border-strong)] bg-[var(--work-surface)] text-[var(--work-text)] transition-colors hover:border-[var(--work-accent)] hover:bg-[var(--work-accent-soft)]"
                  aria-label={`${user?.name ?? "用户"}，点击退出登录`}
                  title={`${user?.name ?? "用户"} · ${user?.role ?? ""}（点击退出）`}
                  onClick={() => {
                    logout();
                    router.push("/");
                  }}
                >
                  <UserRound className="size-5 fill-current" strokeWidth={2.2} />
                </button>
              </div>
            </header>

            <div className="min-h-0 flex-1 p-3 sm:p-4">
              <section className="flex min-h-[calc(100vh-80px)] flex-col overflow-hidden rounded-[12px] border border-[var(--work-border)] bg-[var(--work-surface)] shadow-[0_1px_2px_rgba(15,23,42,0.04),0_18px_42px_rgba(15,23,42,0.06)] sm:min-h-[calc(100vh-88px)] lg:h-full lg:min-h-0">
                <div className="border-b border-[var(--work-border)] px-5 py-5 sm:px-8">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                    <div>
                      <h1 className="text-[24px] font-bold tracking-normal text-[var(--work-text)]">
                        会话记录
                      </h1>
                      <p className="mt-1 text-sm leading-6 text-[var(--work-muted)]">
                        查看历史问答、继续上下文、管理需要保留的企业知识讨论。
                      </p>
                    </div>
                    <Button
                      type="button"
                      className="h-10 rounded-[8px] bg-[var(--workspace-brand)] px-4 text-white hover:bg-[var(--workspace-brand)]/90"
                      onClick={() => router.push("/console")}
                    >
                      <MessageSquareText className="size-4" />
                      新建对话
                    </Button>
                  </div>

                  <div className="mt-5 flex h-11 max-w-[560px] items-center gap-2 rounded-[9px] border border-[var(--work-border)] bg-white px-3">
                    <Search className="size-4 shrink-0 text-[var(--work-muted)]" />
                    <input
                      value={query}
                      onChange={(event) => setQuery(event.target.value)}
                      className="h-full min-w-0 flex-1 bg-transparent text-sm font-medium text-[var(--work-text)] outline-none placeholder:text-[var(--work-muted)]"
                      placeholder="搜索标题、最近提问或摘要"
                    />
                  </div>
                </div>

                {notice ? (
                  <div className="mx-5 mt-4 rounded-[8px] border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-medium text-amber-800 sm:mx-8">
                    {notice}
                  </div>
                ) : null}

                <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5 sm:px-8">
                  {isLoading ? (
                    <div className="flex h-full min-h-[260px] items-center justify-center gap-2 text-sm font-semibold text-[var(--work-muted)]">
                      <Loader2 className="size-4 animate-spin" />
                      正在加载会话
                    </div>
                  ) : grouped.length === 0 ? (
                    <div className="flex h-full min-h-[260px] flex-col items-center justify-center text-center">
                      <MessageSquareText className="mb-4 size-10 text-[var(--work-muted)]" />
                      <h2 className="text-lg font-bold text-[var(--work-text)]">暂无会话记录</h2>
                      <p className="mt-2 max-w-[420px] text-sm leading-6 text-[var(--work-muted)]">
                        发起一次企业知识库问答后，这里会自动保存会话，方便后续继续追问。
                      </p>
                    </div>
                  ) : (
                    <div className="grid gap-3">
                      {grouped.map((item) => (
                        <article
                          key={item.conversation_id}
                          className="rounded-[8px] border border-[var(--work-border)] bg-white px-4 py-4 transition-colors hover:border-[var(--work-accent)]"
                        >
                          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                            <button
                              type="button"
                              className="min-w-0 flex-1 cursor-pointer text-left"
                              onClick={() => router.push(`/console?conversation_id=${item.conversation_id}`)}
                            >
                              <div className="flex min-w-0 items-center gap-2">
                                {item.pinned ? (
                                  <Pin className="size-4 shrink-0 text-[var(--work-accent-strong)]" />
                                ) : null}
                                <h2 className="truncate text-[17px] font-bold text-[var(--work-text)]">
                                  {item.title}
                                </h2>
                              </div>
                              <p className="mt-2 line-clamp-2 text-sm leading-6 text-[var(--work-muted)]">
                                {item.last_question || "暂无最近提问"}
                              </p>
                              <div className="mt-3 flex flex-wrap items-center gap-2 text-xs font-semibold text-[var(--work-muted)]">
                                <span className="rounded-[6px] border border-[var(--work-border)] px-2 py-1">
                                  {item.message_count} 轮问答
                                </span>
                                <span className="rounded-[6px] border border-[var(--work-border)] px-2 py-1">
                                  {formatTime(item.last_message_at ?? item.updated_at)}
                                </span>
                                <span className="font-mono tracking-normal">
                                  {item.conversation_id.slice(0, 8)}
                                </span>
                              </div>
                            </button>

                            <div className="flex shrink-0 flex-wrap items-center gap-2">
                              <IconAction
                                label={item.pinned ? "取消置顶" : "置顶"}
                                onClick={() => void handleTogglePinned(item)}
                              >
                                {item.pinned ? <PinOff className="size-4" /> : <Pin className="size-4" />}
                              </IconAction>
                              <IconAction label="重命名" onClick={() => void handleRename(item)}>
                                <Edit3 className="size-4" />
                              </IconAction>
                              <IconAction label="删除" danger onClick={() => void handleDelete(item)}>
                                <Trash2 className="size-4" />
                              </IconAction>
                              <Button
                                type="button"
                                className="h-9 rounded-[8px] bg-[var(--workspace-brand)] px-3 text-white hover:bg-[var(--workspace-brand)]/90"
                                onClick={() => router.push(`/console?conversation_id=${item.conversation_id}`)}
                              >
                                继续
                                <ArrowRight className="size-4" />
                              </Button>
                            </div>
                          </div>
                        </article>
                      ))}
                    </div>
                  )}
                </div>
              </section>
            </div>
          </main>
        </div>
      </div>
    </RequireAuth>
  );
}

function IconAction({
  label,
  danger,
  children,
  onClick,
}: {
  label: string;
  danger?: boolean;
  children: ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className={cn(
        "grid size-9 cursor-pointer place-items-center rounded-[8px] border border-[var(--work-border)] text-[var(--work-muted)] transition-colors hover:border-[var(--work-accent)] hover:text-[var(--work-text)]",
        danger && "hover:border-red-300 hover:text-red-600",
      )}
      title={label}
      aria-label={label}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

function dateValue(value: string | null | undefined): number {
  return value ? new Date(value).getTime() : 0;
}

function formatTime(value: string | null | undefined): string {
  if (!value) return "暂无时间";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

"use client";

import { FormEvent, Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  checkHealth,
  fetchConversation,
  fetchDocuments,
  streamQuestion,
  uploadDocument,
} from "@/lib/api";
import type {
  AgentStep,
  AnswerMode,
  KnowledgeDocument,
  PhaseState,
  Plan,
  RouteStep,
  Source,
} from "@/lib/api";
import type { Message } from "@/lib/types";
import { Sidebar } from "@/components/sidebar";
import { ChatPanel } from "@/components/chat-panel";
import { InspectorPanel } from "@/components/inspector-panel";
import { CircleCheck, Plus, UserRound } from "lucide-react";
import "./console.css";
import { RequireAuth } from "@/components/auth/require-auth";
import { useAuth } from "@/components/auth/auth-provider";
import { useRouter } from "next/navigation";

export default function Home() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[var(--workspace-canvas)]" />}>
      <ConsolePageContent />
    </Suspense>
  );
}

function ConsolePageContent() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [question, setQuestion] = useState("");
  const [conversationId, setConversationId] = useState<string>();
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "企业知识库已就绪。你可以上传制度、产品手册或常见问题文档，然后向我提问；回答会同时返回引用来源，方便核验依据。",
    },
  ]);
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [latestSources, setLatestSources] = useState<Source[]>([]);
  const [isHealthy, setIsHealthy] = useState(false);
  const [isAsking, setIsAsking] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [answerMode, setAnswerMode] = useState<AnswerMode>("fast");
  const [notice, setNotice] = useState<string>();
  const [selectedFileName, setSelectedFileName] = useState("尚未选择文件");
  const fileRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setInterval> | undefined;

    async function check() {
      const healthy = await checkHealth();
      if (cancelled) return;
      if (healthy) {
        setIsHealthy(true);
        const docs = await fetchDocuments().catch(() => []);
        if (!cancelled) setDocuments(docs);
      } else {
        setIsHealthy(false);
        timer = setInterval(check, 5000);
      }
    }

    void check();
    return () => { cancelled = true; clearInterval(timer); };
  }, []);

  useEffect(() => {
    const requestedConversationId = searchParams.get("conversation_id");
    if (!requestedConversationId || requestedConversationId === conversationId) return;
    const targetConversationId = requestedConversationId;

    let cancelled = false;
    async function loadConversation() {
      setNotice(undefined);
      try {
        const payload = await fetchConversation(targetConversationId);
        if (cancelled) return;
        const restoredMessages: Message[] = payload.messages.flatMap((turn) => [
          {
            id: `${turn.id}-user`,
            role: "user" as const,
            content: turn.question,
          },
          {
            id: `${turn.id}-assistant`,
            role: "assistant" as const,
            content: turn.answer,
            sources: turn.sources ?? [],
            answerMode: turn.answer_mode ?? "fast",
            model: turn.model,
            traceId: turn.trace_id,
            agentSteps: turn.agent_steps ?? [],
            route: turn.route ?? [],
          },
        ]);
        setConversationId(payload.conversation_id);
        setMessages(restoredMessages.length ? restoredMessages : [
          {
            id: "welcome",
            role: "assistant",
            content:
              "企业知识库已就绪。你可以上传制度、产品手册或常见问题文档，然后向我提问；回答会同时返回引用来源，方便核验依据。",
          },
        ]);
        const lastAssistant = [...restoredMessages]
          .reverse()
          .find((message) => message.role === "assistant");
        setLatestSources(lastAssistant?.sources ?? []);
      } catch (error) {
        if (cancelled) return;
        setNotice(error instanceof Error ? error.message : "会话加载失败。");
      }
    }

    void loadConversation();
    return () => {
      cancelled = true;
    };
  }, [searchParams, conversationId]);

  async function refreshConsole() {
    const [healthy, documentList] = await Promise.all([
      checkHealth(),
      fetchDocuments().catch(() => []),
    ]);
    setIsHealthy(healthy);
    setDocuments(documentList);
  }

  async function handleAsk(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || isAsking) return;

    const requestMode = answerMode;
    const assistantMessageId = crypto.randomUUID();
    let hasAssistantMessage = false;
    let streamContent = "";
    let streamSources: Source[] = [];
    let streamAgentSteps: AgentStep[] = [];
    let streamRoute: RouteStep[] = [];
    let streamPlan: Plan | undefined;
    let streamPhases: PhaseState[] = [];
    let streamModel: string | null | undefined;
    let streamTraceId: string | null | undefined;

    const upsertPhase = (phases: PhaseState[], next: PhaseState): PhaseState[] => {
      const others = phases.filter((phase) => phase.layer !== next.layer);
      return [...others, next];
    };

    const syncAssistant = () => {
      setMessages((current) => {
        if (!hasAssistantMessage) {
          hasAssistantMessage = true;
          return [
            ...current,
            {
              id: assistantMessageId,
              role: "assistant" as const,
              content: streamContent,
              sources: streamSources,
              agentSteps: streamAgentSteps,
              route: streamRoute,
              plan: streamPlan,
              phases: streamPhases,
              model: streamModel,
              traceId: streamTraceId,
              answerMode: requestMode,
            },
          ];
        }
        return current.map((message) =>
          message.id === assistantMessageId
            ? {
                ...message,
                content: streamContent,
                sources: streamSources,
                agentSteps: streamAgentSteps,
                route: streamRoute,
                plan: streamPlan,
                phases: streamPhases,
                model: streamModel ?? message.model,
                traceId: streamTraceId ?? message.traceId,
                answerMode: message.answerMode ?? requestMode,
              }
            : message,
        );
      });
    };

    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: "user", content: trimmed },
    ]);
    setQuestion("");
    setIsAsking(true);
    setNotice(undefined);
    const abortController = new AbortController();
    abortRef.current = abortController;

    try {
      await streamQuestion(trimmed, requestMode, conversationId, (event) => {
        if (event.type === "phase") {
          streamPhases = upsertPhase(streamPhases, {
            layer: event.layer,
            label: event.label,
            status: event.status === "start" ? "running" : "done",
          });
          syncAssistant();
          return;
        }

        if (event.type === "plan") {
          streamPlan = {
            strategy: event.strategy,
            rationale: event.rationale,
            steps: event.steps,
          };
          syncAssistant();
          return;
        }

        if (event.type === "route_step") {
          if (event.step) {
            streamRoute = [...streamRoute, event.step];
            syncAssistant();
          }
          return;
        }

        if (event.type === "agent_step") {
          streamAgentSteps = [...streamAgentSteps, event.content];
          syncAssistant();
          return;
        }

        if (event.type === "sources") {
          streamSources = event.content;
          setLatestSources(event.content);
          syncAssistant();
          return;
        }

        if (event.type === "answer_delta") {
          streamContent += event.content;
          syncAssistant();
          return;
        }

        if (event.type === "done") {
          setConversationId(event.conversation_id);
          if (!conversationId) {
            const nextUrl = `/console?conversation_id=${event.conversation_id}`;
            window.history.replaceState(null, "", nextUrl);
          }
          streamModel = event.model ?? null;
          streamTraceId = event.trace_id ?? null;
          streamRoute = event.route ?? streamRoute;
          syncAssistant();
          return;
        }

        if (event.type === "error") {
          streamContent = hasAssistantMessage
            ? `${streamContent}\n\n流式生成中断：${event.message}`
            : `流式生成失败：${event.message}`;
          syncAssistant();
          setNotice(event.message);
          return;
        }
      }, undefined, abortController.signal);
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        streamContent = hasAssistantMessage
          ? `${streamContent}\n\n已停止生成。`
          : "已停止生成。";
        syncAssistant();
        return;
      }
      const errorMessage =
        error instanceof Error
          ? error.message
          : "问答请求失败，请确认后端服务是否启动。";
      streamContent = hasAssistantMessage
        ? `${streamContent}\n\n流式生成中断：${errorMessage}`
        : `流式生成失败：${errorMessage}`;
      syncAssistant();
      setNotice(errorMessage);
    } finally {
      setIsAsking(false);
      abortRef.current = null;
    }
  }

  function handleStop() {
    abortRef.current?.abort();
    setIsAsking(false);
  }

  async function handleUpload() {
    const files = Array.from(fileRef.current?.files ?? []);
    if (isUploading) return;
    if (files.length === 0) {
      setNotice("请先选择要上传的文件。");
      return;
    }

    setIsUploading(true);
    setNotice(`正在入库 0/${files.length}`);
    const failed: string[] = [];
    try {
      for (const [index, file] of files.entries()) {
        setNotice(`正在入库 ${index + 1}/${files.length}：${file.name}`);
        try {
          await uploadDocument(file);
        } catch (error) {
          const reason = error instanceof Error ? error.message : "上传失败";
          failed.push(`${file.name}：${reason}`);
        }
      }

      if (fileRef.current) fileRef.current.value = "";
      setSelectedFileName("尚未选择文件");
      await refreshConsole();

      if (failed.length) {
        setNotice(`已完成 ${files.length - failed.length}/${files.length} 个文件，失败：${failed.join("；")}`);
        return;
      }

      setNotice(`已完成入库：${files.length} 个文件`);
    } finally {
      setIsUploading(false);
    }
  }

  return <RequireAuth>{(
    <div className="workspace-root min-h-screen bg-[var(--workspace-canvas)] text-[var(--work-text)] lg:overflow-hidden">
      <div className="grid min-h-screen grid-cols-1 lg:h-screen lg:grid-cols-[280px_minmax(0,1fr)]">
        <div className="hidden min-h-0 lg:block">
          <Sidebar isHealthy={isHealthy} />
        </div>

        <main className="flex min-h-0 min-w-0 flex-col">
          <header className="flex h-14 shrink-0 items-center justify-between border-b border-[var(--work-border)] bg-white/80 px-4 shadow-sm backdrop-blur-xl sm:px-7">
            <div className="flex items-center gap-3 lg:hidden">
              <span className="grid size-8 place-items-center rounded-full bg-[var(--workspace-brand)] text-sm font-bold text-white">
                R
              </span>
              <span className="text-lg font-bold text-[var(--work-text)]">企业 RAG</span>
            </div>
            <div className="hidden items-center gap-3 lg:flex">
              <span className="console-mono">企业知识库智能问答平台</span>
              <span className="h-4 w-px bg-[var(--work-border)]" />
              <span className="text-[15px] font-semibold text-[var(--work-text)]">智能问答</span>
            </div>
            <div className="flex items-center gap-3">
              <button
                type="button"
                className="console-pill console-pill--ghost"
                onClick={() => {
                  setConversationId(undefined);
                  window.history.replaceState(null, "", "/console");
                  setMessages([
                    {
                      id: "welcome",
                      role: "assistant",
                      content:
                        "企业知识库已就绪。你可以上传制度、产品手册或常见问题文档，然后向我提问；回答会同时返回引用来源，方便核验依据。",
                    },
                  ]);
                  setLatestSources([]);
                  setQuestion("");
                }}
              >
                <Plus className="size-4" strokeWidth={2} />
                <span className="hidden sm:inline">新建对话</span>
                <span className="sm:hidden">新建</span>
              </button>
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
                onClick={() => { logout(); router.push("/"); }}
              >
                <UserRound className="size-5 fill-current" strokeWidth={2.2} />
              </button>
            </div>
          </header>

          <div className="min-h-0 flex-1 p-3 sm:p-4">
            <section className="flex min-h-[calc(100vh-80px)] flex-col overflow-hidden rounded-[20px] border border-[var(--work-border)] bg-[var(--work-surface)] shadow-[0_1px_2px_rgba(16,24,40,0.05),0_28px_70px_rgba(16,24,40,0.09)] sm:min-h-[calc(100vh-88px)] lg:h-full lg:min-h-0">
              <div className="grid min-h-0 flex-1 grid-cols-1 lg:min-h-0 xl:grid-cols-[minmax(0,1fr)_324px]">
                <ChatPanel
                  messages={messages}
                  question={question}
                  setQuestion={setQuestion}
                  isAsking={isAsking}
                  answerMode={answerMode}
                  setAnswerMode={setAnswerMode}
                  conversationId={conversationId}
                onAsk={handleAsk}
                onStop={handleStop}
              />
                <InspectorPanel
                  documents={documents}
                  latestSources={latestSources}
                  isUploading={isUploading}
                  selectedFileName={selectedFileName}
                  notice={notice}
                  onUpload={handleUpload}
                  onFileSelect={setSelectedFileName}
                  onRefresh={refreshConsole}
                  fileRef={fileRef}
                />
              </div>
            </section>
          </div>
        </main>
      </div>
    </div>
  )}</RequireAuth>;
}

"use client";

import { type FormEvent, useEffect, useMemo, useRef } from "react";
import {
  Box,
  Brain,
  CheckCircle2,
  Globe2,
  Info,
  Loader2,
  Paperclip,
  Quote,
  Settings2,
  Sparkles,
  Square,
  Route,
  UploadCloud,
  Wrench,
  X,
  Zap,
} from "lucide-react";
import type { AgentStep, AnswerMode, PhaseState, Plan } from "@/lib/api";
import type { Message } from "@/lib/types";
import { samplePrompts } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";

type ChatPanelProps = {
  messages: Message[];
  question: string;
  setQuestion: (q: string) => void;
  isAsking: boolean;
  answerMode: AnswerMode;
  setAnswerMode: (mode: AnswerMode) => void;
  conversationId?: string;
  onAsk: (e: FormEvent<HTMLFormElement>) => void;
};

export function ChatPanel({
  messages,
  question,
  setQuestion,
  isAsking,
  answerMode,
  setAnswerMode,
  conversationId,
  onAsk,
}: ChatPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const previousMessageCountRef = useRef(messages.length);
  const hasUserMessages = useMemo(
    () => messages.some((message) => message.role === "user"),
    [messages],
  );
  const visibleMessages = hasUserMessages
    ? messages.filter((message) => message.id !== "welcome")
    : [];

  const modeOptions = [
    {
      mode: "fast" as const,
      label: "快速模式",
      model: "qwen3.5-flash",
      icon: Zap,
    },
    {
      mode: "thinking" as const,
      label: "思考模式",
      model: "qwen3.7-plus",
      icon: Brain,
    },
  ];
  const activeMode = modeOptions.find((item) => item.mode === answerMode) ?? modeOptions[0];
  const ActiveModeIcon = activeMode.icon;

  useEffect(() => {
    if (messages.length > previousMessageCountRef.current) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }
    previousMessageCountRef.current = messages.length;
  }, [messages]);

  return (
    <section className="relative flex min-h-0 flex-col">
      <div className="flex h-full min-h-0 flex-col px-4 pb-4 pt-5 sm:px-8 lg:px-10 xl:px-16">
        <div className="mx-auto flex w-full max-w-[1180px] shrink-0 items-center justify-between gap-3">
          <div className="inline-flex min-w-0 items-center gap-2.5 rounded-[10px] border border-[var(--graphite)] bg-transparent px-2.5 py-1.5 sm:gap-2.5 sm:px-3">
            <span className="grid size-8 shrink-0 place-items-center rounded-[7px] border border-[var(--graphite)] text-[var(--stellar-white)]">
              <Box className="size-4" />
            </span>
            <span className="truncate text-[16px] font-semibold text-[var(--stellar-white)] sm:text-[18px]">
              <span className="sm:hidden">RAG 助手</span>
              <span className="hidden sm:inline">企业 RAG 助手</span>
            </span>
            <Info className="hidden size-4 shrink-0 text-[var(--ash)] sm:block" />
            <button
              type="button"
              className="console-mono inline-flex h-7 min-w-[90px] items-center justify-center gap-1.5 whitespace-nowrap rounded-[6px] border border-[var(--graphite)] bg-transparent px-2 normal-case tracking-normal hover:border-[var(--stellar-white)] sm:min-w-0 sm:gap-2 sm:px-3"
              style={{ textTransform: "none", letterSpacing: "-0.025em", fontSize: "13px" }}
              onClick={() => setAnswerMode(answerMode === "thinking" ? "fast" : "thinking")}
              disabled={isAsking}
              title={`当前模式：${activeMode.model}`}
            >
              <ActiveModeIcon className="size-3.5" />
              {activeMode.label}
              <span className="size-2 rounded-full bg-[var(--signal-blue)]" />
            </button>
          </div>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="ghost"
              size="icon-lg"
              className="rounded-[9px] border border-[var(--graphite)] text-[var(--ash)] hover:border-[var(--stellar-white)] hover:bg-transparent [&_svg]:size-4"
              aria-label="参数设置"
            >
              <Settings2 className="size-5" />
            </Button>
          </div>
        </div>

        <div className="relative mx-auto flex min-h-0 w-full max-w-[1180px] flex-1 flex-col">
          {!hasUserMessages ? (
            <div className="relative flex flex-1 flex-col items-center justify-center gap-6 py-8 text-center lg:pb-5">
              <div className="console-bloom" aria-hidden />
              <div className="relative">
                <h2 className="console-headline text-[28px] font-semibold leading-tight tracking-tight sm:text-[40px]">
                  <span className="block sm:inline">让企业资料</span>{" "}
                  <span className="block sm:inline">可检索、可引用、可追溯</span>
                </h2>
                <p className="mx-auto mt-4 max-w-[680px] text-sm leading-6 text-[var(--ash)] sm:text-base">
                  上传企业资料后直接提问，系统会完成知识检索、流式生成与引用溯源。
                </p>
              </div>
              <Composer
                question={question}
                setQuestion={setQuestion}
                isAsking={isAsking}
                onAsk={onAsk}
                activeModeLabel={activeMode.label}
              />
              <PromptStrip onSelect={setQuestion} />
            </div>
          ) : (
            <>
              <ScrollArea className="min-h-0 flex-1 py-7">
                <div className="mx-auto flex max-w-[900px] flex-col gap-4">
                  {visibleMessages.map((message) => (
                    <MessageBubble
                      key={message.id}
                      message={message}
                      isAsking={isAsking}
                    />
                  ))}
                  {isAsking ? (
                    <div className="flex justify-center">
                      <Button
                        type="button"
                        variant="outline"
                        className="console-pill console-pill--ghost h-10 px-5 text-sm"
                      >
                        <Square className="size-4" />
                        停止生成
                      </Button>
                    </div>
                  ) : null}
                  <div ref={bottomRef} />
                </div>
              </ScrollArea>

              <div className="shrink-0 pb-1">
                <Composer
                  question={question}
                  setQuestion={setQuestion}
                  isAsking={isAsking}
                  onAsk={onAsk}
                  activeModeLabel={activeMode.label}
                />
              </div>
            </>
          )}
        </div>

        <p className="console-mono shrink-0 px-2 pt-3 text-center normal-case" style={{ textTransform: "none", letterSpacing: "-0.01em" }}>
          以上内容为 AI 生成，请结合引用来源核验关键信息。
          {conversationId ? ` 当前会话 ${conversationId.slice(0, 8)}` : ""}
        </p>
      </div>
    </section>
  );
}

function MessageBubble({ message, isAsking }: { message: Message; isAsking: boolean }) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <article className="ml-auto max-w-[70%] animate-in fade-in slide-in-from-bottom-2 duration-300 rounded-[12px] border border-[var(--work-accent)] bg-[var(--work-accent-soft)] px-5 py-3.5 text-base font-medium leading-7 text-[var(--work-text)]">
        <p className="whitespace-pre-wrap">{message.content}</p>
      </article>
    );
  }

  const phases = message.phases ?? [];
  const phaseOf = (layer: string) => phases.find((phase) => phase.layer === layer)?.status;
  const agentRunning = phaseOf("agent") === "running";
  const answerRunning = phaseOf("answer") === "running";
  const plannerRunning = phaseOf("planner") === "running";
  const agentSteps = message.agentSteps ?? [];
  const hasLiveArea = phases.length > 0 || Boolean(message.plan) || agentSteps.length > 0;
  const generating = isAsking && !message.content && !message.model;

  return (
    <article className="relative flex animate-in fade-in slide-in-from-bottom-2 duration-300 gap-3">
      <div className="pt-3 text-[var(--stellar-white)]">
        <Sparkles
          className={cn(
            "size-5",
            (generating || answerRunning) && "animate-pulse",
          )}
          style={(generating || answerRunning) ? { filter: "drop-shadow(0 0 8px rgba(151,196,255,0.7))" } : undefined}
        />
      </div>
      <div className="min-w-0 flex-1 space-y-3">
        {hasLiveArea ? (
          <VerticalPipeline
            phases={phases}
            plan={message.plan}
            agentSteps={agentSteps}
            plannerRunning={plannerRunning}
            agentRunning={agentRunning}
          />
        ) : null}

        {message.sources?.length ? (
          <div className="flex items-center justify-between rounded-[12px] border border-[var(--graphite)] bg-transparent px-4 py-3 text-base font-semibold text-[var(--stellar-white)]">
            <span className="flex min-w-0 items-center gap-2.5">
              <Globe2 className="size-5 shrink-0 text-[var(--ash)]" />
              <span className="truncate">
                完成知识检索：{message.sources.length} 条企业资料引用
              </span>
            </span>
            <span className="text-[var(--ash)]">⌄</span>
          </div>
        ) : null}

        <div className="rounded-[12px] border border-[var(--graphite)] bg-transparent px-5 py-4 text-[17px] font-medium leading-8 text-[var(--stellar-white)]">
          <div className="mb-3 flex items-center gap-2.5 text-[16px] font-semibold text-[var(--stellar-white)]">
            {generating || answerRunning ? (
              <Loader2 className="size-5 animate-spin text-[var(--signal-blue)]" />
            ) : (
              <Brain className="size-5 text-[var(--ash)]" />
            )}
            {message.model ? "助手回答" : "生成中"}
            {generating && !message.content ? (
              <span className="text-[15px] font-medium text-[var(--signal-blue)]">正在思考…</span>
            ) : null}
          </div>
          {message.content ? (
            <p className="whitespace-pre-wrap tracking-normal">{message.content}</p>
          ) : generating ? (
            <GeneratingDots />
          ) : null}
          {message.model ? (
            <div className="mt-4 flex flex-wrap items-center gap-2 text-sm font-semibold text-[var(--ash)]">
              <span className="rounded-[6px] border border-[var(--graphite)] px-2.5 py-1">
                {message.answerMode === "thinking" ? "思考模式" : "快速模式"}
              </span>
              <span className="font-mono text-xs tracking-normal">{message.model}</span>
            </div>
          ) : null}
        </div>

      </div>
    </article>
  );
}

const PIPELINE_LAYERS = [
  { layer: "planner", name: "规划层", Icon: Route },
  { layer: "agent", name: "执行层", Icon: Brain },
  { layer: "answer", name: "命令层", Icon: Sparkles },
] as const;

function VerticalPipeline({
  phases,
  plan,
  agentSteps,
  plannerRunning,
  agentRunning,
}: {
  phases: PhaseState[];
  plan?: Plan;
  agentSteps: AgentStep[];
  plannerRunning: boolean;
  agentRunning: boolean;
}) {
  const byLayer = new Map(phases.map((phase) => [phase.layer, phase]));

  return (
    <div className="space-y-0 rounded-[12px] border border-[var(--graphite)] bg-transparent px-4 py-3">
      {PIPELINE_LAYERS.map((def, index) => {
        const status = byLayer.get(def.layer)?.status;
        const Icon = def.Icon;
        const isLast = index === PIPELINE_LAYERS.length - 1;

        return (
          <div key={def.layer} className="animate-in fade-in slide-in-from-bottom-2 duration-300">
            {/* Layer row: icon + name + status */}
            <div className="flex items-center gap-2.5 py-1.5">
              {/* Connecting line */}
              {!isLast && (
                <div className="relative ml-[9px] h-full min-h-[20px] w-px grow bg-[var(--graphite)]" />
              )}
              {/* Status icon */}
              <div
                className={cn(
                  "relative z-10 grid size-[18px] shrink-0 place-items-center rounded-full border-2 transition-all duration-300",
                  status === "done" && "border-emerald-500 bg-transparent",
                  status === "running" && "border-[var(--signal-blue)] bg-transparent console-dot-running",
                  !status && "border-[var(--graphite)] bg-transparent",
                )}
              >
                {status === "running" ? (
                  <Loader2 className="size-3 animate-spin text-[var(--signal-blue)]" />
                ) : status === "done" ? (
                  <CheckCircle2 className="size-3.5 text-emerald-500" />
                ) : (
                  <Icon className="size-3.5 text-[var(--ash)]" />
                )}
              </div>
              <span
                className={cn(
                  "text-[13px] font-semibold tracking-wide transition-colors duration-300",
                  status === "done" && "text-[var(--stellar-white)]",
                  status === "running" && "text-[var(--signal-blue)]",
                  !status && "text-[var(--ash)]",
                )}
              >
                {def.name}
              </span>
              {status === "running" ? (
                <span className="text-[12px] font-medium text-[var(--signal-blue)]">进行中…</span>
              ) : status === "done" ? (
                <span className="text-[12px] font-medium text-emerald-500/80">已完成</span>
              ) : null}
            </div>

            {/* Layer content */}
            <div className="ml-[25px] min-h-[4px]">
              {/* 规划层 content: show rationale */}
              {def.layer === "planner" && plan && (
                <div className="animate-in fade-in duration-300 rounded-[8px] border border-[var(--graphite)] bg-transparent px-3 py-2 mt-1 text-xs leading-5 text-[var(--ash)]">
                  <span className="console-mono mr-1.5 rounded-[5px] border border-[var(--graphite)] px-1.5 py-0.5 text-[10px]">
                    {plan.strategy === "llm" ? "AI 决策" : "规则决策"}
                  </span>
                  {plan.rationale ? (
                    <p className="mt-1.5 text-[var(--ash)]">{plan.rationale}</p>
                  ) : null}
                </div>
              )}

              {/* 执行层 content: show agent thinking steps */}
              {def.layer === "agent" && (
                <AgentStepsInline steps={agentSteps} running={agentRunning} />
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function AgentStepsInline({ steps, running }: { steps: AgentStep[]; running: boolean }) {
  if (steps.length === 0 && !running) return null;
  return (
    <div className="mt-1 space-y-1.5">
      {steps.map((step, index) => (
        <div
          key={`${step.action ?? "final"}-${index}`}
          className="animate-in fade-in slide-in-from-bottom-2 duration-300 rounded-[8px] border border-[var(--graphite)] bg-transparent p-2.5 text-xs leading-5 text-[var(--ash)]"
          style={{ animationDelay: `${index * 60}ms` }}
        >
          <div className="mb-1 flex items-center justify-between gap-2">
            <span className="font-semibold text-[var(--stellar-white)]">
              第 {index + 1} 轮
            </span>
            {step.action ? (
              <span className="rounded-[5px] border border-[var(--graphite)] px-1.5 py-0.5 text-[10px] font-semibold text-[var(--signal-blue)]">
                {step.action}
              </span>
            ) : (
              <span className="rounded-[5px] border border-[var(--graphite)] px-1.5 py-0.5 text-[10px] font-semibold text-[var(--ash)]">
                final
              </span>
            )}
          </div>
          {step.thought ? (
            <p className="whitespace-pre-wrap text-[var(--ash)]">{step.thought}</p>
          ) : null}
          {step.observation ? (
            <p className="mt-1.5 line-clamp-4 rounded-[5px] border border-[var(--graphite)] p-1.5 text-[10px] leading-4 text-[var(--ash)]">
              {step.observation}
            </p>
          ) : null}
        </div>
      ))}
      {running && steps.length === 0 ? (
        <div className="flex items-center gap-2 px-1 py-1 text-xs text-[var(--ash)]">
          <Loader2 className="size-3.5 animate-spin text-[var(--signal-blue)]" />
          智能体正在思考…
        </div>
      ) : null}
    </div>
  );
}


function GeneratingDots() {
  return (
    <div className="flex items-center gap-1.5 py-1">
      {[0, 1, 2].map((index) => (
        <span
          key={index}
          className="size-2 animate-bounce rounded-full bg-[var(--signal-blue)]"
          style={{ animationDelay: `${index * 0.15}s` }}
        />
      ))}
    </div>
  );
}

function PromptStrip({ onSelect }: { onSelect: (prompt: string) => void }) {
  const icons = [Quote, UploadCloud, Sparkles];

  return (
    <div className="relative flex flex-wrap justify-center gap-2.5 sm:gap-3">
      {samplePrompts.map((prompt, index) => {
        const Icon = icons[index] ?? Quote;
        return (
          <button
            key={prompt}
            type="button"
            className="inline-flex h-11 items-center gap-2 rounded-full border border-[var(--graphite)] bg-transparent px-4 text-sm font-semibold text-[var(--stellar-white)] transition-colors hover:border-[var(--stellar-white)] sm:h-12 sm:px-5 sm:text-[15px]"
            onClick={() => onSelect(prompt)}
          >
            <Icon className="size-[18px] text-[var(--signal-blue)]" />
            {prompt}
          </button>
        );
      })}
    </div>
  );
}

function Composer({
  question,
  setQuestion,
  isAsking,
  onAsk,
  activeModeLabel,
}: {
  question: string;
  setQuestion: (q: string) => void;
  isAsking: boolean;
  onAsk: (e: FormEvent<HTMLFormElement>) => void;
  activeModeLabel: string;
}) {
  return (
    <form
      className="console-composer mx-auto w-full max-w-[900px] rounded-[24px] border bg-[var(--work-surface)] p-3"
      onSubmit={onAsk}
    >
      <label className="sr-only" htmlFor="question">
        输入企业知识库问题
      </label>
      <Textarea
        id="question"
        rows={2}
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            event.currentTarget.form?.requestSubmit();
          }
        }}
        placeholder="请输入企业知识库问题，例如：报销多久可以打款？"
        className="min-h-[58px] resize-none border-0 bg-transparent px-3 py-2 text-base leading-7 text-[var(--stellar-white)] shadow-none outline-none placeholder:text-[var(--ash)] focus-visible:ring-0"
      />
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <Button
            type="button"
            variant="ghost"
            size="icon-lg"
            className="rounded-[8px] border border-[var(--graphite)] bg-transparent text-[var(--ash)] hover:border-[var(--stellar-white)] hover:bg-transparent"
            aria-label="添加附件"
          >
            <Paperclip className="size-5" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon-lg"
            className="rounded-[8px] border border-[var(--graphite)] bg-transparent text-[var(--ash)] hover:border-[var(--stellar-white)] hover:bg-transparent"
            aria-label="工具设置"
          >
            <Wrench className="size-5" />
          </Button>
          <button
            type="button"
            className="inline-flex min-w-0 max-w-[190px] items-center gap-2 rounded-full border border-[var(--graphite)] bg-transparent px-3 py-2 text-sm font-semibold text-[var(--stellar-white)] hover:border-[var(--stellar-white)] sm:max-w-none"
            title={`当前回答模式：${activeModeLabel}`}
          >
            <Globe2 className="size-5 shrink-0 text-[var(--ash)]" />
            <span className="truncate">知识库检索</span>
            <X className="size-5 shrink-0 text-[var(--ash)]" />
          </button>
        </div>
        <button
          type="submit"
          disabled={isAsking || !question.trim()}
          className={cn(
            "grid size-11 place-items-center rounded-full border border-[var(--graphite)] bg-transparent text-[var(--stellar-white)] transition-colors hover:border-[var(--stellar-white)] disabled:cursor-not-allowed",
            !question.trim() && "opacity-45",
          )}
          aria-label="发送问题"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
            <path
              d="M12 19V5M12 5l-7 7M12 5l7 7"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </div>
    </form>
  );
}

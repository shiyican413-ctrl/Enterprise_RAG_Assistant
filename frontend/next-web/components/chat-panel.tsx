"use client";

import { type FormEvent, useEffect, useRef } from "react";
import { Brain, Zap } from "lucide-react";
import type { AnswerMode } from "@/lib/api";
import type { Message } from "@/lib/types";
import { samplePrompts } from "@/lib/types";
import { cn } from "@/lib/utils";
import { SendIcon } from "@/components/icons";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
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
  const modeOptions = [
    {
      mode: "fast" as const,
      label: "快速模式",
      shortLabel: "快速",
      model: "GLM-4V-Flash",
      statusText: "当前使用快速模式",
      runningText: "快速模式生成中",
      icon: Zap,
    },
    {
      mode: "thinking" as const,
      label: "思考模式",
      shortLabel: "思考",
      model: "GLM-4.1V-Thinking-Flash",
      statusText: "当前使用思考模式",
      runningText: "思考模式生成中",
      icon: Brain,
    },
  ];
  const activeMode = modeOptions.find((item) => item.mode === answerMode) ?? modeOptions[0];
  const ActiveIcon = activeMode.icon;
  const isThinkingMode = answerMode === "thinking";

  useEffect(() => {
    if (messages.length > previousMessageCountRef.current) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }
    previousMessageCountRef.current = messages.length;
  }, [messages]);

  return (
    <div className="flex flex-col gap-4 md:h-[calc(100vh-2rem)] md:min-h-0">
      {/* Hero */}
      <Card className="rounded-xl">
        <CardContent className="flex items-start justify-between gap-3 p-3">
          <div className="min-w-0">
            <p className="mb-0.5 text-xs font-semibold uppercase tracking-wider text-brand-500">
              企业级检索增强生成智能问答
            </p>
            <h1 className="text-base font-bold leading-tight tracking-tight">
              让企业文档变成可检索、可引用、可追溯的知识助手。
            </h1>
            <p className="mt-0.5 max-w-xl text-xs leading-tight text-muted-foreground">
              系统支持文档上传、文本切分、知识检索、问答生成、引用溯源与会话记录，
              为企业制度查询、产品资料问答和客服辅助提供统一入口。
            </p>
          </div>
          <div className="shrink-0 rounded-lg border border-border bg-muted/50 px-3 py-1 text-center">
            <span className="block text-xs font-medium text-muted-foreground">当前会话</span>
            <strong className="mt-1 block text-sm font-semibold text-brand-600">
              {conversationId ? conversationId.slice(0, 8) : "新会话"}
            </strong>
          </div>
        </CardContent>
      </Card>

      {/* Chat */}
      <Card className="flex min-h-0 flex-1 flex-col rounded-xl">
        <CardHeader className="flex shrink-0 flex-row items-start justify-between gap-4 border-b pb-3">
          <div>
            <p className="mb-0.5 text-xs font-semibold uppercase tracking-wider text-brand-500">
              基于知识库提问
            </p>
            <CardTitle className="text-base">智能问答工作台</CardTitle>
          </div>
          <div className="flex flex-wrap justify-end gap-1.5">
            <Badge
              variant="default"
              className={cn(
                "gap-1 text-xs",
                isThinkingMode && "bg-blue-600 text-white",
              )}
            >
              <ActiveIcon className="size-3" />
              {isAsking ? activeMode.runningText : activeMode.statusText}
            </Badge>
            {["知识检索", "引用溯源", "多轮会话"].map((label, i) => (
              <Badge key={label} variant={i === 0 ? "default" : "secondary"} className="text-xs">
                {label}
              </Badge>
            ))}
          </div>
        </CardHeader>

        <CardContent className="flex min-h-0 flex-1 flex-col gap-3 overflow-hidden p-4">
          <ScrollArea className="h-[320px] rounded-lg border border-border bg-muted/30 md:h-auto md:min-h-0 md:flex-1">
            <div className="flex flex-col gap-3 p-3">
              {messages.map((message) => (
                <article
                  key={message.id}
                  className={cn(
                    "max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed",
                    message.role === "user"
                      ? "ml-auto bg-brand-500 text-white"
                      : "border border-border bg-card",
                  )}
                >
                  <div
                    className={cn(
                      "mb-1.5 flex items-center justify-between text-xs font-medium",
                      message.role === "user"
                        ? "text-white/70"
                        : "text-brand-600",
                    )}
                  >
                    <span>{message.role === "user" ? "用户提问" : "助手回答"}</span>
                    {message.sources?.length ? (
                      <span className={message.role === "user" ? "text-white/60" : "text-muted-foreground"}>
                        {message.sources.length} 条引用
                      </span>
                    ) : null}
                  </div>
                  <p className="whitespace-pre-wrap">{message.content}</p>
                  {message.model ? (
                    <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
                      <Badge variant="secondary" className="text-xs">
                        {message.answerMode === "thinking" ? "思考模式" : "快速模式"}
                      </Badge>
                      <span>{message.model}</span>
                    </div>
                  ) : null}
                </article>
              ))}
              {isAsking ? (
                <article className="max-w-[85%] rounded-2xl border border-brand-200 bg-brand-50 px-4 py-3 text-sm leading-relaxed text-brand-900">
                  <div className="mb-1.5 flex items-center justify-between gap-3 text-xs font-medium text-brand-700">
                    <span className="flex items-center gap-1.5">
                      <ActiveIcon className="size-3.5" />
                      {activeMode.runningText}
                    </span>
                    <span className="text-brand-500">{activeMode.model}</span>
                  </div>
                  <p className="text-brand-800">
                    正在检索知识片段并生成回答，请稍候。
                  </p>
                </article>
              ) : null}
              <div ref={bottomRef} />
            </div>
          </ScrollArea>

          <div className="flex shrink-0 flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex flex-wrap gap-2">
              {samplePrompts.map((prompt) => (
                <Button
                  key={prompt}
                  variant="outline"
                  size="sm"
                  className="rounded-full text-xs"
                  onClick={() => setQuestion(prompt)}
                  type="button"
                >
                  {prompt}
                </Button>
              ))}
            </div>
            <div
              role="radiogroup"
              aria-label="回答模式"
              className={cn(
                "relative grid h-10 w-full max-w-[224px] shrink-0 grid-cols-2 overflow-hidden rounded-lg border p-1 transition-all",
                isThinkingMode
                  ? "border-blue-300 bg-blue-50 shadow-[inset_0_0_0_1px_rgba(59,130,246,0.12)]"
                  : "border-brand-300 bg-brand-50 shadow-[inset_0_0_0_1px_rgba(124,58,237,0.12)]",
              )}
            >
              <div
                className={cn(
                  "pointer-events-none absolute inset-y-1 w-[calc(50%-0.25rem)] rounded-md transition-all duration-200",
                  isThinkingMode
                    ? "right-1 bg-blue-500/20 ring-1 ring-blue-400/60"
                    : "left-1 bg-brand-500/20 ring-1 ring-brand-400/60",
                )}
              />
              {modeOptions.map((item) => {
                const Icon = item.icon;
                const isActive = answerMode === item.mode;
                return (
                  <button
                    key={item.mode}
                    type="button"
                    role="radio"
                    className={cn(
                      "relative z-10 inline-flex h-8 min-w-0 cursor-pointer items-center justify-center gap-1.5 rounded-md px-2 text-xs font-medium transition-all",
                      isActive && item.mode === "thinking"
                        ? "bg-blue-600 text-white shadow-sm"
                        : isActive
                          ? "bg-brand-600 text-white shadow-sm"
                          : "text-muted-foreground hover:bg-background/70 hover:text-foreground",
                      isAsking && "cursor-not-allowed opacity-70",
                    )}
                    onClick={() => setAnswerMode(item.mode)}
                    disabled={isAsking}
                    aria-checked={isActive}
                    title={`${item.label}：${item.model}`}
                  >
                    <Icon className="size-3.5" />
                    <span>{item.shortLabel}</span>
                    {isActive ? (
                      <span className="rounded bg-white/20 px-1 text-[10px] leading-4">
                        当前
                      </span>
                    ) : null}
                  </button>
                );
              })}
            </div>
          </div>

          <form className="flex shrink-0 items-end gap-2" onSubmit={onAsk}>
            <label className="sr-only" htmlFor="question">
              输入企业知识库问题
            </label>
            <Textarea
              id="question"
              rows={2}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="请输入问题，例如：报销多久可以打款？"
              className="min-h-[42px] resize-none"
            />
            <Button type="submit" disabled={isAsking} size="lg" className="shrink-0">
              <SendIcon className="size-4" />
              {isAsking ? activeMode.runningText : `${activeMode.shortLabel}发送`}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

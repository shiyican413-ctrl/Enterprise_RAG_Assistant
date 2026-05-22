"use client";

import { type FormEvent, useEffect, useMemo, useRef } from "react";
import {
  Box,
  Brain,
  Globe2,
  Info,
  Paperclip,
  Quote,
  SendHorizontal,
  Settings2,
  Sparkles,
  Square,
  UploadCloud,
  Wrench,
  X,
  Zap,
} from "lucide-react";
import type { AnswerMode } from "@/lib/api";
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
      model: "GLM-4V-Flash",
      icon: Zap,
    },
    {
      mode: "thinking" as const,
      label: "思考模式",
      model: "GLM-4.1V-Thinking-Flash",
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
    <section className="relative flex min-h-0 flex-col bg-[#f3f6fb] xl:bg-[#f3f6fb]">
      <div className="flex h-full min-h-0 flex-col px-4 pb-4 pt-5 sm:px-8 lg:px-10 xl:px-16">
        <div className="mx-auto flex w-full max-w-[1180px] shrink-0 items-center justify-between gap-3">
          <div className="inline-flex min-w-0 items-center gap-2 rounded-[10px] border border-[#e4e8f0] bg-white px-2.5 py-1.5 shadow-[0_1px_2px_rgba(16,24,40,0.03)] sm:gap-2.5 sm:px-3">
            <span className="grid size-8 shrink-0 place-items-center rounded-[7px] bg-gradient-to-br from-[#2f66ff] to-[#7e4dff] text-white">
              <Box className="size-4" />
            </span>
            <span className="truncate text-[16px] font-semibold text-[#080b10] sm:text-[18px]">
              <span className="sm:hidden">RAG 助手</span>
              <span className="hidden sm:inline">企业 RAG 助手</span>
            </span>
            <Info className="hidden size-4 shrink-0 text-[#2d3543] sm:block" />
            <button
              type="button"
              className="inline-flex h-7 min-w-[78px] items-center justify-center gap-1.5 whitespace-nowrap rounded-[6px] bg-[#eef4ff] px-2 text-[13px] font-semibold text-[#2b64ff] transition-colors hover:bg-[#e3edff] sm:min-w-0 sm:gap-2 sm:px-3 sm:text-sm"
              onClick={() => setAnswerMode(answerMode === "thinking" ? "fast" : "thinking")}
              disabled={isAsking}
              title={`当前模式：${activeMode.model}`}
            >
              <ActiveModeIcon className="size-3.5" />
              {activeMode.label}
              <span className="size-2 rounded-full bg-emerald-500" />
            </button>
          </div>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="ghost"
              size="icon-lg"
              className="rounded-[9px] text-[#566072] hover:bg-white [&_svg]:size-4"
              aria-label="参数设置"
            >
              <Settings2 className="size-5" />
            </Button>
          </div>
        </div>

        <div className="mx-auto flex min-h-0 w-full max-w-[1180px] flex-1 flex-col">
          {!hasUserMessages ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-6 py-8 text-center lg:pb-5">
              <div>
                <h2 className="text-[28px] font-bold leading-tight tracking-normal text-[#07090d] sm:text-[38px]">
                  <span className="block sm:inline">让企业资料</span>
                  <span className="block bg-gradient-to-r from-[#005dff] via-[#345dff] to-[#9b4cff] bg-clip-text text-transparent sm:inline">
                    {" "}可检索、可引用{" "}
                  </span>
                  <span className="block sm:inline">可追溯</span>
                </h2>
                <p className="mx-auto mt-4 max-w-[680px] text-sm leading-6 text-[#697386] sm:text-base">
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
                    <MessageBubble key={message.id} message={message} />
                  ))}
                  {isAsking ? (
                    <div className="flex justify-center">
                      <Button
                        type="button"
                        variant="outline"
                        className="h-10 rounded-[8px] border-[#e4e8f0] bg-white px-5 text-sm font-semibold text-[#151922]"
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

        <p className="shrink-0 px-2 pt-3 text-center text-xs font-medium leading-5 text-[#b9c0cc]">
          以上内容为 AI 生成，请结合引用来源核验关键信息。
          {conversationId ? ` 当前会话 ${conversationId.slice(0, 8)}` : ""}
        </p>
      </div>
    </section>
  );
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <article className="ml-auto max-w-[70%] rounded-[12px] bg-[#eaf2ff] px-5 py-3.5 text-base font-medium leading-7 text-[#151922]">
        <p className="whitespace-pre-wrap">{message.content}</p>
      </article>
    );
  }

  return (
    <article className="relative flex gap-3">
      <div className="pt-3 text-[#7b4cff]">
        <Sparkles className="size-5" />
      </div>
      <div className="min-w-0 flex-1 space-y-3">
        {message.sources?.length ? (
          <div className="flex items-center justify-between rounded-[12px] bg-[#f3f5f8] px-4 py-3 text-base font-semibold text-[#242933]">
            <span className="flex min-w-0 items-center gap-2.5">
              <Globe2 className="size-5 shrink-0 text-[#647083]" />
              <span className="truncate">
                完成知识检索：{message.sources.length} 条企业资料引用
              </span>
            </span>
            <span className="text-[#647083]">⌄</span>
          </div>
        ) : null}

        <div className="rounded-[12px] border border-[#dfe5ef] bg-white px-5 py-4 text-[17px] font-medium leading-8 text-[#1f2937] shadow-[0_8px_24px_rgba(16,24,40,0.06)]">
          <div className="mb-3 flex items-center gap-2.5 text-[18px] font-bold text-[#111827]">
            <Brain className="size-5" />
            {message.model ? "助手回答" : "生成中"}
            {!message.model ? <span>....</span> : null}
          </div>
          <p className="whitespace-pre-wrap tracking-normal">{message.content}</p>
          {message.model ? (
            <div className="mt-4 flex flex-wrap items-center gap-2 text-sm font-semibold text-[#7a8393]">
              <span className="rounded-[6px] bg-white px-2.5 py-1">
                {message.answerMode === "thinking" ? "思考模式" : "快速模式"}
              </span>
              <span>{message.model}</span>
            </div>
          ) : null}
        </div>
      </div>
    </article>
  );
}

function PromptStrip({ onSelect }: { onSelect: (prompt: string) => void }) {
  const icons = [Quote, UploadCloud, Sparkles];

  return (
    <div className="flex flex-wrap justify-center gap-2.5 sm:gap-3">
      {samplePrompts.map((prompt, index) => {
        const Icon = icons[index] ?? Quote;
        return (
          <button
            key={prompt}
            type="button"
            className="inline-flex h-11 items-center gap-2 rounded-full border border-[#e2e6ee] bg-white px-4 text-sm font-semibold text-[#171b22] shadow-[0_1px_1px_rgba(16,24,40,0.02)] transition-colors hover:border-[#cbd5e7] hover:bg-[#f9fbff] sm:h-12 sm:px-5 sm:text-[15px]"
            onClick={() => onSelect(prompt)}
          >
            <Icon className="size-[18px] text-[#2d71ff]" />
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
      className="mx-auto w-full max-w-[900px] rounded-[14px] border border-[#dfe4ed] bg-white p-3 shadow-[0_10px_28px_rgba(16,24,40,0.05)]"
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
        className="min-h-[58px] resize-none border-0 bg-transparent px-3 py-2 text-base leading-7 shadow-none outline-none placeholder:text-[#b8bec9] focus-visible:ring-0"
      />
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="icon-lg"
            className="rounded-[8px] border-[#e7ebf2] bg-white text-[#8b95a6]"
            aria-label="添加附件"
          >
            <Paperclip className="size-5" />
          </Button>
          <Button
            type="button"
            variant="outline"
            size="icon-lg"
            className="rounded-[8px] border-[#e7ebf2] bg-white text-[#8b95a6]"
            aria-label="工具设置"
          >
            <Wrench className="size-5" />
          </Button>
          <button
            type="button"
            className="inline-flex min-w-0 max-w-[190px] items-center gap-2 rounded-[8px] border border-[#cfe0ff] bg-[#edf5ff] px-3 py-2 text-sm font-semibold text-[#2a68ff] sm:max-w-none"
            title={`当前回答模式：${activeModeLabel}`}
          >
            <Globe2 className="size-5 shrink-0" />
            <span className="truncate">知识库检索</span>
            <X className="size-5 shrink-0" />
          </button>
        </div>
        <Button
          type="submit"
          disabled={isAsking || !question.trim()}
          size="icon-lg"
          className={cn(
            "size-11 rounded-[9px] bg-gradient-to-br from-[#2f66ff] to-[#7c53ff] text-white shadow-[0_8px_18px_rgba(47,102,255,0.22)] hover:opacity-95",
            !question.trim() && "opacity-45",
          )}
          aria-label="发送问题"
        >
          <SendHorizontal className="size-5" />
        </Button>
      </div>
    </form>
  );
}

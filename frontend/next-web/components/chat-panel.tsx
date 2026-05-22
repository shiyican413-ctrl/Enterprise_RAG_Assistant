"use client";

import type { FormEvent } from "react";
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
  conversationId?: string;
  onAsk: (e: FormEvent<HTMLFormElement>) => void;
};

export function ChatPanel({
  messages,
  question,
  setQuestion,
  isAsking,
  conversationId,
  onAsk,
}: ChatPanelProps) {
  return (
    <div className="flex flex-col gap-4">
      {/* Hero */}
      <Card className="rounded-xl">
        <CardContent className="flex items-start justify-between gap-6 p-5">
          <div className="min-w-0">
            <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-brand-500">
              企业级检索增强生成智能问答
            </p>
            <h1 className="text-xl font-bold leading-tight tracking-tight">
              让企业文档变成可检索、可引用、可追溯的知识助手。
            </h1>
            <p className="mt-2 max-w-xl text-sm leading-relaxed text-muted-foreground">
              系统支持文档上传、文本切分、知识检索、问答生成、引用溯源与会话记录，
              为企业制度查询、产品资料问答和客服辅助提供统一入口。
            </p>
          </div>
          <div className="shrink-0 rounded-lg border border-border bg-muted/50 px-3 py-2 text-center">
            <span className="block text-xs font-medium text-muted-foreground">当前会话</span>
            <strong className="mt-1 block text-sm font-semibold text-brand-600">
              {conversationId ? conversationId.slice(0, 8) : "新会话"}
            </strong>
          </div>
        </CardContent>
      </Card>

      {/* Chat */}
      <Card className="flex flex-1 flex-col overflow-hidden rounded-xl">
        <CardHeader className="flex-row items-start justify-between gap-4 border-b pb-3">
          <div>
            <p className="mb-0.5 text-xs font-semibold uppercase tracking-wider text-brand-500">
              基于知识库提问
            </p>
            <CardTitle className="text-base">智能问答工作台</CardTitle>
          </div>
          <div className="flex gap-1.5">
            {["知识检索", "引用溯源", "多轮会话"].map((label, i) => (
              <Badge key={label} variant={i === 0 ? "default" : "secondary"} className="text-xs">
                {label}
              </Badge>
            ))}
          </div>
        </CardHeader>

        <CardContent className="flex flex-1 flex-col gap-3 overflow-hidden p-4">
          <ScrollArea className="min-h-[320px] flex-1 rounded-lg border border-border bg-muted/30">
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
                </article>
              ))}
            </div>
          </ScrollArea>

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

          <form className="flex items-end gap-2" onSubmit={onAsk}>
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
              {isAsking ? "检索中" : "发送"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

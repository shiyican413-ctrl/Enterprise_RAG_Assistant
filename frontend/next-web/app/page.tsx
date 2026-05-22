"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import {
  checkHealth,
  fetchDocuments,
  streamQuestion,
  uploadDocument,
} from "@/lib/api";
import type { AnswerMode, KnowledgeDocument, Source } from "@/lib/api";
import type { Message } from "@/lib/types";
import { Sidebar } from "@/components/sidebar";
import { ChatPanel } from "@/components/chat-panel";
import { InspectorPanel } from "@/components/inspector-panel";
import { CircleCheck, Plus, UserRound } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function Home() {
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

  useEffect(() => {
    void refreshConsole();
  }, []);

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
    let streamSources: Source[] = [];
    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: "user", content: trimmed },
    ]);
    setQuestion("");
    setIsAsking(true);
    setNotice(undefined);

    try {
      await streamQuestion(trimmed, requestMode, conversationId, (event) => {
        if (event.type === "answer_delta") {
          if (!hasAssistantMessage) {
            hasAssistantMessage = true;
            setMessages((current) => [
              ...current,
              {
                id: assistantMessageId,
                role: "assistant",
                content: event.content,
                sources: streamSources,
                answerMode: requestMode,
              },
            ]);
          } else {
            setMessages((current) =>
              current.map((message) =>
                message.id === assistantMessageId
                  ? { ...message, content: message.content + event.content }
                  : message,
              ),
            );
          }
          return;
        }

        if (event.type === "sources") {
          streamSources = event.content;
          setLatestSources(event.content);
          setMessages((current) =>
            current.map((message) =>
              message.id === assistantMessageId
                ? { ...message, sources: event.content }
                : message,
            ),
          );
          return;
        }

        if (event.type === "done") {
          setConversationId(event.conversation_id);
          setMessages((current) =>
            current.map((message) =>
              message.id === assistantMessageId
                ? {
                    ...message,
                    answerMode: event.answer_mode,
                    model: event.model,
                  }
                : message,
            ),
          );
        }
      });
    } catch (error) {
      const errorMessage =
        error instanceof Error
          ? error.message
          : "问答请求失败，请确认后端服务是否启动。";
      setMessages((current) => {
        if (hasAssistantMessage) {
          return current.map((message) =>
            message.id === assistantMessageId
              ? {
                  ...message,
                  content: `${message.content}\n\n流式生成中断：${errorMessage}`,
                }
              : message,
          );
        }

        return [
          ...current,
          {
            id: assistantMessageId,
            role: "assistant",
            content: `流式生成失败：${errorMessage}`,
            answerMode: requestMode,
          },
        ];
      });
      setNotice(errorMessage);
    } finally {
      setIsAsking(false);
    }
  }

  async function handleUpload() {
    const file = fileRef.current?.files?.[0];
    if (!file || isUploading) return;

    setIsUploading(true);
    setNotice(undefined);
    try {
      await uploadDocument(file);
      setNotice(`已完成入库：${file.name}`);
      if (fileRef.current) fileRef.current.value = "";
      setSelectedFileName("尚未选择文件");
      await refreshConsole();
    } catch (error) {
      setNotice(
        error instanceof Error ? error.message : "上传失败，请检查文件格式。",
      );
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#f4f6fa] text-[#101318] lg:overflow-hidden">
      <div className="grid min-h-screen grid-cols-1 lg:h-screen lg:grid-cols-[280px_minmax(0,1fr)]">
        <div className="hidden min-h-0 lg:block">
          <Sidebar isHealthy={isHealthy} />
        </div>

        <main className="flex min-h-0 min-w-0 flex-col">
          <header className="flex h-[72px] shrink-0 items-center justify-between border-b border-[#e8ebf1] bg-[#f7f8fb] px-4 sm:px-7">
            <div className="flex items-center gap-3 lg:hidden">
              <div className="relative h-6 w-8">
                <span className="absolute left-0 top-0 h-2 w-8 skew-x-[-24deg] bg-[#111317]" />
                <span className="absolute bottom-0 left-0 h-2 w-8 skew-x-[-24deg] bg-[#111317]" />
              </div>
              <span className="text-xl font-bold">企业 RAG</span>
            </div>
            <div className="hidden text-[18px] font-semibold text-[#2b3038] lg:block">
              企业知识库智能问答平台
            </div>
            <div className="flex items-center gap-3">
              <div className="hidden h-10 items-center gap-2 rounded-[10px] px-3 text-sm font-semibold text-[#667085] sm:flex">
                <CircleCheck
                  className={isHealthy ? "size-4 text-emerald-500" : "size-4 text-[#a5acb8]"}
                />
                {isHealthy ? "服务在线" : "等待后端"}
              </div>
              <button
                type="button"
                className="grid size-10 place-items-center rounded-full text-[#111317] transition-colors hover:bg-white"
                aria-label="用户中心"
              >
                <UserRound className="size-5 fill-current" strokeWidth={2.2} />
              </button>
            </div>
          </header>

          <div className="min-h-0 flex-1 p-3 sm:p-4">
            <section className="flex min-h-[calc(100vh-96px)] flex-col overflow-hidden rounded-[16px] border border-[#e4e8f0] bg-white shadow-[0_1px_2px_rgba(16,24,40,0.02)] lg:h-full lg:min-h-0">
              <div className="flex min-h-[76px] shrink-0 flex-col gap-3 border-b border-[#e8ebf1] px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-7">
                <h1 className="text-[24px] font-bold leading-none tracking-normal text-[#06080c]">
                  智能问答
                </h1>
                <div className="flex flex-wrap items-center gap-3">
                  <Button
                    type="button"
                    variant="outline"
                    className="h-10 rounded-[8px] border-[#e3e7ef] bg-white px-4 text-[15px] font-semibold text-[#111317] hover:bg-[#f6f8fc]"
                    onClick={() => {
                      setConversationId(undefined);
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
                    <Plus className="size-5 text-[#a5acb8]" />
                    新建对话
                  </Button>
                </div>
              </div>

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
  );
}

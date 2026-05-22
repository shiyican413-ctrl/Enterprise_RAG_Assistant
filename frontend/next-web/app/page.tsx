"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import {
  askQuestion,
  checkHealth,
  fetchDocuments,
  uploadDocument,
} from "@/lib/api";
import type { KnowledgeDocument, Source } from "@/lib/api";
import type { Message } from "@/lib/types";
import { Sidebar } from "@/components/sidebar";
import { ChatPanel } from "@/components/chat-panel";
import { MetricsBar } from "@/components/metrics-bar";
import { PipelineBar } from "@/components/pipeline-bar";
import { InspectorPanel } from "@/components/inspector-panel";

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

    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: "user", content: trimmed },
    ]);
    setQuestion("");
    setIsAsking(true);
    setNotice(undefined);

    try {
      const payload = await askQuestion(trimmed, conversationId);
      setConversationId(payload.conversation_id);
      setLatestSources(payload.sources);
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: payload.answer,
          sources: payload.sources,
        },
      ]);
    } catch (error) {
      setNotice(
        error instanceof Error
          ? error.message
          : "问答请求失败，请确认后端服务是否启动。",
      );
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
    <div className="grid grid-cols-1 gap-4 p-4 min-h-screen md:grid-cols-[240px_minmax(0,1fr)] xl:grid-cols-[240px_minmax(0,1fr)_320px]">
      <Sidebar isHealthy={isHealthy} />
      <main className="flex flex-col gap-4 min-w-0">
        <ChatPanel
          messages={messages}
          question={question}
          setQuestion={setQuestion}
          isAsking={isAsking}
          conversationId={conversationId}
          onAsk={handleAsk}
        />
        <MetricsBar documents={documents} latestSources={latestSources} />
        <PipelineBar />
      </main>
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
  );
}

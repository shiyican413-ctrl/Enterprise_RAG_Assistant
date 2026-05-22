export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export type Source = {
  document_id: string;
  document_name: string;
  chunk_id: string;
  chunk_index: number;
  snippet: string;
  score: number;
  metadata?: Record<string, string>;
};

export type AskResponse = {
  conversation_id: string;
  answer: string;
  sources: Source[];
  answer_mode: AnswerMode;
  model?: string | null;
};

export type AnswerMode = "fast" | "thinking";

export type KnowledgeDocument = {
  document_id: string;
  document_name: string;
  chunk_count: number;
  created_at: string;
  metadata?: Record<string, string>;
};

export type StreamEvent =
  | {
      type: "answer_delta";
      content: string;
    }
  | {
      type: "sources";
      content: Source[];
    }
  | {
      type: "done";
      conversation_id: string;
      answer_mode: AnswerMode;
      model?: string | null;
    };

export async function askQuestion(
  question: string,
  answerMode: AnswerMode,
  conversationId?: string,
): Promise<AskResponse> {
  const response = await fetch(`${API_BASE_URL}/api/chat/ask`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      question,
      conversation_id: conversationId,
      top_k: 4,
      answer_mode: answerMode,
    }),
  });

  if (!response.ok) {
    throw new Error(await response.text());
  }

  return response.json();
}

export async function streamQuestion(
  question: string,
  answerMode: AnswerMode,
  conversationId: string | undefined,
  onEvent: (event: StreamEvent) => void,
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      question,
      conversation_id: conversationId,
      top_k: 4,
      answer_mode: answerMode,
    }),
  });

  if (!response.ok) {
    throw new Error(await response.text());
  }

  if (!response.body) {
    throw new Error("当前浏览器不支持流式响应。");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    buffer = consumeSseBuffer(buffer, onEvent);
  }

  buffer += decoder.decode();
  consumeSseBuffer(buffer, onEvent, true);
}

function consumeSseBuffer(
  buffer: string,
  onEvent: (event: StreamEvent) => void,
  flush = false,
): string {
  const normalized = buffer.replace(/\r\n/g, "\n");
  const parts = normalized.split("\n\n");
  const remaining = flush ? "" : (parts.pop() ?? "");
  const events = flush ? parts.filter(Boolean) : parts;

  for (const rawEvent of events) {
    const data = rawEvent
      .split("\n")
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).trim())
      .join("\n");
    if (!data) continue;
    onEvent(JSON.parse(data) as StreamEvent);
  }

  return remaining;
}

export async function fetchDocuments(): Promise<KnowledgeDocument[]> {
  const response = await fetch(`${API_BASE_URL}/api/documents`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await response.text());
  }

  const payload = await response.json();
  return payload.documents ?? [];
}

export async function uploadDocument(file: File): Promise<void> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/api/documents/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(await response.text());
  }
}

export async function checkHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/health`, {
      cache: "no-store",
    });
    return response.ok;
  } catch {
    return false;
  }
}

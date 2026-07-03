export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  (process.env.NODE_ENV === "production" ? "" : "http://127.0.0.1:8000");

import { clearAccessToken, getAccessToken } from "@/lib/auth";

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const token = getAccessToken();
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  if (response.status === 401 && typeof window !== "undefined") {
    clearAccessToken();
    if (!window.location.pathname.startsWith("/login")) {
      window.location.assign(`/login?next=${encodeURIComponent(window.location.pathname)}`);
    }
  }
  return response;
}

export type Source = {
  document_id: string;
  document_name: string;
  chunk_id: string;
  chunk_index: number;
  snippet: string;
  score: number;
  metadata?: Record<string, string>;
};

export type AgentStep = {
  thought?: string;
  action?: string | null;
  action_input?: Record<string, unknown> | null;
  observation?: string | null;
};

export type RouteStep = {
  step: string;
  status: string;
  duration_ms?: number | null;
  error?: string | null;
};

export type PlanStep = {
  name: string;
  step_type: string;
};

export type Plan = {
  strategy: string;
  rationale: string;
  steps: PlanStep[];
};

export type PhaseState = {
  layer: string;
  label: string;
  status: "running" | "done";
};

export type AskResponse = {
  conversation_id: string;
  trace_id?: string | null;
  answer: string;
  sources: Source[];
  answer_mode: AnswerMode;
  model?: string | null;
  agent_steps?: AgentStep[];
  route?: RouteStep[];
};

export type AnswerMode = "fast" | "thinking";

export type ConversationSummary = {
  id: string;
  conversation_id: string;
  user_id?: string | null;
  tenant_id?: string | null;
  title: string;
  summary: string;
  pinned: boolean;
  archived: boolean;
  message_count: number;
  created_at: string;
  updated_at: string;
  last_message_at?: string | null;
  last_question: string;
};

export type ConversationTurn = {
  id: string;
  conversation_id: string;
  user_id?: string | null;
  tenant_id?: string | null;
  question: string;
  answer: string;
  sources: Source[];
  created_at: string;
  model?: string | null;
  answer_mode?: AnswerMode | null;
  trace_id?: string | null;
  route?: RouteStep[];
  agent_steps?: AgentStep[];
};

export type KnowledgeDocument = {
  document_id: string;
  document_name: string;
  chunk_count: number;
  created_at: string;
  metadata?: Record<string, string>;
};

export type DocumentChunk = {
  chunk_id: string;
  document_id: string;
  document_name: string;
  chunk_index: number;
  content: string;
  metadata?: Record<string, string>;
  created_at: string;
  embedding_model?: string | null;
};

export type DeleteDocumentResult = {
  document_id: string;
  deleted_chunks: number;
};

export type RebuildKnowledgeResult = {
  message: string;
  documents?: Array<{
    document_id?: string;
    document_name?: string;
    file_name?: string;
    chunk_count?: number;
    error?: string;
  }>;
};

export type StreamEvent =
  | {
      type: "phase";
      layer: string;
      label: string;
      status: "start" | "done";
    }
  | {
      type: "plan";
      strategy: string;
      rationale: string;
      steps: PlanStep[];
    }
  | {
      type: "route_step";
      step: RouteStep | null;
    }
  | {
      type: "answer_delta";
      content: string;
    }
  | {
      type: "agent_step";
      content: AgentStep;
    }
  | {
      type: "sources";
      content: Source[];
    }
  | {
      type: "error";
      message: string;
    }
  | {
      type: "done";
      conversation_id: string;
      trace_id?: string | null;
      answer_mode: AnswerMode;
      model?: string | null;
      route?: RouteStep[];
    };

export async function askQuestion(
  question: string,
  answerMode: AnswerMode,
  conversationId?: string,
  topK?: number,
): Promise<AskResponse> {
  const response = await apiFetch(`/api/chat/ask`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      question,
      conversation_id: conversationId,
      top_k: topK,
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
  topK?: number,
  signal?: AbortSignal,
): Promise<void> {
  const response = await apiFetch(`/api/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      question,
      conversation_id: conversationId,
      top_k: topK,
      answer_mode: answerMode,
    }),
    signal,
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

export async function fetchConversations(
  query?: string,
  limit = 50,
): Promise<ConversationSummary[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (query?.trim()) params.set("q", query.trim());
  const response = await apiFetch(`/api/chat/conversations?${params.toString()}`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await readApiError(response));
  }

  const payload = await response.json();
  return payload.conversations ?? [];
}

export async function fetchConversation(
  conversationId: string,
): Promise<{ conversation_id: string; messages: ConversationTurn[] }> {
  const response = await apiFetch(`/api/chat/conversations/${conversationId}`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await readApiError(response));
  }

  return response.json();
}

export async function updateConversation(
  conversationId: string,
  payload: { title?: string; pinned?: boolean },
): Promise<ConversationSummary> {
  const response = await apiFetch(`/api/chat/conversations/${conversationId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await readApiError(response));
  }

  return response.json();
}

export async function deleteConversation(
  conversationId: string,
): Promise<{ conversation_id: string; deleted: boolean }> {
  const response = await apiFetch(`/api/chat/conversations/${conversationId}`, {
    method: "DELETE",
  });

  if (!response.ok) {
    throw new Error(await readApiError(response));
  }

  return response.json();
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
  const response = await apiFetch(`/api/documents`, {
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

  const response = await apiFetch(`/api/documents/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(await readApiError(response));
  }
}

export async function deleteDocument(
  documentId: string,
): Promise<DeleteDocumentResult> {
  const response = await apiFetch(`/api/documents/${documentId}`, {
    method: "DELETE",
  });

  if (!response.ok) {
    throw new Error(await readApiError(response));
  }

  return response.json();
}

export type BatchDeleteResult = {
  document_ids: string[];
  deleted_chunks: number;
};

export async function batchDeleteDocuments(
  documentIds: string[],
): Promise<BatchDeleteResult> {
  const response = await apiFetch(`/api/documents/batch-delete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document_ids: documentIds }),
  });

  if (!response.ok) {
    throw new Error(await readApiError(response));
  }

  return response.json();
}

export async function rebuildKnowledge(): Promise<RebuildKnowledgeResult> {
  const response = await apiFetch(`/api/knowledge/rebuild`, {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error(await readApiError(response));
  }

  return response.json();
}

export async function fetchDocumentChunks(
  documentId: string,
): Promise<DocumentChunk[]> {
  const response = await apiFetch(
    `/api/documents/${documentId}/chunks`,
    { cache: "no-store" },
  );

  if (!response.ok) {
    throw new Error(await readApiError(response));
  }

  const payload = await response.json();
  return payload.chunks ?? [];
}

async function readApiError(response: Response): Promise<string> {
  const text = await response.text();
  if (!text) {
    return `Request failed with status ${response.status}`;
  }

  try {
    const payload = JSON.parse(text) as { detail?: unknown };
    if (typeof payload.detail === "string") {
      return payload.detail;
    }
  } catch {
    // Fall through to the raw response body.
  }

  return text;
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

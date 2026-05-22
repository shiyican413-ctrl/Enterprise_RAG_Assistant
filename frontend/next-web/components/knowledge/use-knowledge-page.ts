"use client";

import type { ChangeEvent } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  checkHealth,
  deleteDocument,
  fetchDocumentChunks,
  fetchDocuments,
  rebuildKnowledge,
  uploadDocument,
} from "@/lib/api";
import type { DocumentChunk, KnowledgeDocument } from "@/lib/api";
import {
  ACCEPTED_EXTENSIONS,
  filterDocuments,
  isAcceptedFile,
  normalizeExtension,
} from "./knowledge-utils";
import type { KnowledgeNotice } from "./knowledge-utils";

export function useKnowledgePage() {
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [chunks, setChunks] = useState<DocumentChunk[]>([]);
  const [selectedDocument, setSelectedDocument] =
    useState<KnowledgeDocument | null>(null);
  const [pendingDelete, setPendingDelete] = useState<KnowledgeDocument | null>(null);
  const [showRebuildConfirm, setShowRebuildConfirm] = useState(false);
  const [query, setQuery] = useState("");
  const [extension, setExtension] = useState("all");
  const [isHealthy, setIsHealthy] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isRebuilding, setIsRebuilding] = useState(false);
  const [isLoadingChunks, setIsLoadingChunks] = useState(false);
  const [notice, setNotice] = useState<KnowledgeNotice>();
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    void refreshKnowledge();
  }, []);

  useEffect(() => {
    if (!selectedDocument) {
      setChunks([]);
      return;
    }

    setIsLoadingChunks(true);
    fetchDocumentChunks(selectedDocument.document_id)
      .then(setChunks)
      .catch((error) => {
        setChunks([]);
        setNotice({
          tone: "error",
          text: error instanceof Error ? error.message : "片段加载失败",
        });
      })
      .finally(() => setIsLoadingChunks(false));
  }, [selectedDocument]);

  const totalChunks = useMemo(
    () => documents.reduce((sum, doc) => sum + doc.chunk_count, 0),
    [documents],
  );

  const availableExtensions = useMemo(() => {
    const values = new Set(
      documents.map((doc) => normalizeExtension(doc)).filter(Boolean),
    );
    return Array.from(values).sort();
  }, [documents]);

  const filteredDocuments = useMemo(
    () => filterDocuments(documents, query, extension),
    [documents, extension, query],
  );

  async function refreshKnowledge() {
    setIsLoading(true);
    try {
      const [healthy, documentList] = await Promise.all([
        checkHealth(),
        fetchDocuments(),
      ]);
      setIsHealthy(healthy);
      setDocuments(documentList);
      setNotice(undefined);
      setSelectedDocument((current) => {
        if (!current) return null;
        return (
          documentList.find((doc) => doc.document_id === current.document_id) ?? null
        );
      });
    } catch (error) {
      setIsHealthy(false);
      setNotice({
        tone: "error",
        text: error instanceof Error ? error.message : "知识库数据加载失败",
      });
    } finally {
      setIsLoading(false);
    }
  }

  async function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    if (!files.length || isUploading) return;

    const unsupported = files.find((file) => !isAcceptedFile(file.name));
    if (unsupported) {
      setNotice({
        tone: "error",
        text: `不支持 ${unsupported.name}，请上传 ${ACCEPTED_EXTENSIONS.join("、")} 文件。`,
      });
      event.target.value = "";
      return;
    }

    setIsUploading(true);
    const failed: string[] = [];

    try {
      for (const [index, file] of files.entries()) {
        setNotice({
          tone: "info",
          text: `正在入库 ${index + 1}/${files.length}：${file.name}`,
        });

        try {
          await uploadDocument(file);
        } catch (error) {
          failed.push(
            `${file.name}：${error instanceof Error ? error.message : "上传失败"}`,
          );
        }
      }

      await refreshKnowledge();
      setNotice(
        failed.length
          ? {
              tone: "error",
              text: `已完成 ${files.length - failed.length}/${files.length} 个文件，失败：${failed.join("；")}`,
            }
          : {
              tone: "success",
              text: `已完成入库：${files.length} 个文件。`,
            },
      );
    } finally {
      setIsUploading(false);
      event.target.value = "";
    }
  }

  async function handleDelete() {
    if (!pendingDelete || isDeleting) return;

    setIsDeleting(true);
    try {
      const result = await deleteDocument(pendingDelete.document_id);
      setPendingDelete(null);
      setSelectedDocument((current) =>
        current?.document_id === result.document_id ? null : current,
      );
      await refreshKnowledge();
      setNotice({
        tone: "success",
        text: `已删除索引记录，并移除 ${result.deleted_chunks} 个片段。原始上传文件仍保留。`,
      });
    } catch (error) {
      setNotice({
        tone: "error",
        text: error instanceof Error ? error.message : "删除失败",
      });
    } finally {
      setIsDeleting(false);
    }
  }

  async function handleRebuild() {
    if (isRebuilding) return;

    setIsRebuilding(true);
    try {
      const result = await rebuildKnowledge();
      setShowRebuildConfirm(false);
      setSelectedDocument(null);
      await refreshKnowledge();
      setNotice({
        tone: "success",
        text: `重建完成，共处理 ${result.documents?.length ?? 0} 个上传文件。`,
      });
    } catch (error) {
      setNotice({
        tone: "error",
        text: error instanceof Error ? error.message : "重建失败",
      });
    } finally {
      setIsRebuilding(false);
    }
  }

  function copyDocumentId(documentId: string) {
    void navigator.clipboard.writeText(documentId);
    setNotice({ tone: "success", text: "文档 ID 已复制。" });
  }

  return {
    availableExtensions,
    chunks,
    documents,
    extension,
    fileRef,
    filteredDocuments,
    isDeleting,
    isHealthy,
    isLoading,
    isLoadingChunks,
    isRebuilding,
    isUploading,
    notice,
    pendingDelete,
    query,
    selectedDocument,
    showRebuildConfirm,
    totalChunks,
    copyDocumentId,
    handleDelete,
    handleFileChange,
    handleRebuild,
    refreshKnowledge,
    setExtension,
    setPendingDelete,
    setQuery,
    setSelectedDocument,
    setShowRebuildConfirm,
  };
}

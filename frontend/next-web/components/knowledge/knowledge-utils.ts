import type { KnowledgeDocument } from "@/lib/api";

export const ACCEPTED_EXTENSIONS = [".txt", ".md", ".csv", ".json", ".pdf"];

export type KnowledgeNotice = {
  tone: "success" | "error" | "info";
  text: string;
};

export function isAcceptedFile(fileName: string) {
  return ACCEPTED_EXTENSIONS.includes(getExtension(fileName));
}

export function displayExtension(document: KnowledgeDocument) {
  const value = normalizeExtension(document);
  return value ? value.replace(".", "").toUpperCase() : "未知";
}

export function normalizeExtension(document: KnowledgeDocument) {
  return getExtension(
    document.metadata?.extension ||
      document.metadata?.file_extension ||
      document.document_name,
  );
}

export function filterDocuments(
  documents: KnowledgeDocument[],
  query: string,
  extension: string,
) {
  const keyword = query.trim().toLowerCase();

  return documents.filter((doc) => {
    const docExtension = normalizeExtension(doc);
    const metadataText = Object.values(doc.metadata ?? {}).join(" ").toLowerCase();
    const matchesKeyword =
      !keyword ||
      doc.document_name.toLowerCase().includes(keyword) ||
      doc.document_id.toLowerCase().includes(keyword) ||
      metadataText.includes(keyword);
    const matchesExtension = extension === "all" || docExtension === extension;

    return matchesKeyword && matchesExtension;
  });
}

function getExtension(value: string) {
  const trimmed = value.trim().toLowerCase();
  const match = trimmed.match(/\.[a-z0-9]+$/);
  return match?.[0] ?? "";
}

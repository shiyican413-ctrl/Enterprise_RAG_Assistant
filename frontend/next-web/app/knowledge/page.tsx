"use client";

import { Sidebar } from "@/components/sidebar";
import { ConfirmDialog } from "@/components/knowledge/confirm-dialog";
import { DocumentDetailDrawer } from "@/components/knowledge/document-detail-drawer";
import { DocumentTable } from "@/components/knowledge/document-table";
import { DocumentToolbar } from "@/components/knowledge/document-toolbar";
import { KnowledgeHeader } from "@/components/knowledge/knowledge-header";
import { KnowledgeMetrics } from "@/components/knowledge/knowledge-metrics";
import { useKnowledgePage } from "@/components/knowledge/use-knowledge-page";

export default function KnowledgePage() {
  const knowledge = useKnowledgePage();

  return (
    <div className="min-h-screen bg-[#f4f6fa] text-[#101318] lg:overflow-hidden">
      <div className="grid min-h-screen grid-cols-1 lg:h-screen lg:grid-cols-[280px_minmax(0,1fr)]">
        <div className="hidden min-h-0 lg:block">
          <Sidebar isHealthy={knowledge.isHealthy} />
        </div>

        <main className="min-h-0 overflow-y-auto">
          <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-5 px-4 py-5 sm:px-6 lg:px-8">
            <KnowledgeHeader
              fileRef={knowledge.fileRef}
              isHealthy={knowledge.isHealthy}
              isLoading={knowledge.isLoading}
              isUploading={knowledge.isUploading}
              isRebuilding={knowledge.isRebuilding}
              notice={knowledge.notice}
              onFileChange={knowledge.handleFileChange}
              onRefresh={knowledge.refreshKnowledge}
              onRebuild={() => knowledge.setShowRebuildConfirm(true)}
            />

            <KnowledgeMetrics
              documents={knowledge.documents}
              isHealthy={knowledge.isHealthy}
              totalChunks={knowledge.totalChunks}
            />

            <section className="rounded-[8px] border border-[#e4e8f0] bg-white shadow-[0_1px_2px_rgba(16,24,40,0.03)]">
              <DocumentToolbar
                query={knowledge.query}
                extension={knowledge.extension}
                availableExtensions={knowledge.availableExtensions}
                filteredCount={knowledge.filteredDocuments.length}
                totalCount={knowledge.documents.length}
                onQueryChange={knowledge.setQuery}
                onExtensionChange={knowledge.setExtension}
              />
              <DocumentTable
                documents={knowledge.filteredDocuments}
                isLoading={knowledge.isLoading}
                totalDocuments={knowledge.documents.length}
                onSelect={knowledge.setSelectedDocument}
                onCopyId={knowledge.copyDocumentId}
                onDelete={knowledge.setPendingDelete}
              />
            </section>
          </div>
        </main>
      </div>

      <DocumentDetailDrawer
        document={knowledge.selectedDocument}
        chunks={knowledge.chunks}
        isLoadingChunks={knowledge.isLoadingChunks}
        onClose={() => knowledge.setSelectedDocument(null)}
      />

      {knowledge.pendingDelete ? (
        <ConfirmDialog
          title="删除文档索引"
          description={`将删除「${knowledge.pendingDelete.document_name}」及其 ${knowledge.pendingDelete.chunk_count} 个片段索引。原始上传文件不会被删除。`}
          confirmLabel="确认删除"
          busy={knowledge.isDeleting}
          tone="danger"
          onCancel={() => knowledge.setPendingDelete(null)}
          onConfirm={knowledge.handleDelete}
        />
      ) : null}

      {knowledge.showRebuildConfirm ? (
        <ConfirmDialog
          title="重建知识库索引"
          description="该操作会清空当前文档与片段索引，并从 data/uploads 目录重新解析生成。重建期间检索结果可能不完整。"
          confirmLabel="确认重建"
          busy={knowledge.isRebuilding}
          tone="danger"
          onCancel={() => knowledge.setShowRebuildConfirm(false)}
          onConfirm={knowledge.handleRebuild}
        />
      ) : null}
    </div>
  );
}

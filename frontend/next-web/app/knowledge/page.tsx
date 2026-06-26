"use client";

import { Sidebar } from "@/components/sidebar";
import { ConfirmDialog } from "@/components/knowledge/confirm-dialog";
import { DocumentDetailDrawer } from "@/components/knowledge/document-detail-drawer";
import { DocumentTable } from "@/components/knowledge/document-table";
import { DocumentToolbar } from "@/components/knowledge/document-toolbar";
import { KnowledgeHeader } from "@/components/knowledge/knowledge-header";
import { KnowledgeMetrics } from "@/components/knowledge/knowledge-metrics";
import { useKnowledgePage } from "@/components/knowledge/use-knowledge-page";
import { RequireAuth } from "@/components/auth/require-auth";
import { useAuth } from "@/components/auth/auth-provider";

export default function KnowledgePage() {
  const knowledge = useKnowledgePage();
  const { user } = useAuth();
  const canManage = user?.role === "admin";

  return <RequireAuth>{(
    <div className="workspace-root min-h-screen bg-[var(--workspace-canvas)] text-[var(--work-text)] lg:overflow-hidden">
      <div className="grid min-h-screen grid-cols-1 lg:h-screen lg:grid-cols-[280px_minmax(0,1fr)]">
        <div className="hidden min-h-0 lg:block">
          <Sidebar isHealthy={knowledge.isHealthy} />
        </div>

        <header className="flex h-14 items-center justify-between border-b border-[var(--work-border)] bg-[var(--work-surface)] px-4 text-[var(--work-text)] lg:hidden">
          <div className="flex items-center gap-3">
            <span className="grid size-8 place-items-center rounded-full bg-[var(--workspace-brand)] text-sm font-bold text-white">
              R
            </span>
            <span className="text-base font-bold">企业 RAG</span>
          </div>
          <span className="text-xs font-semibold text-[var(--work-muted)]">
            {knowledge.isHealthy ? "服务在线" : "等待后端"}
          </span>
        </header>

        <main className="min-h-0 overflow-y-auto bg-[var(--workspace-canvas)]">
          <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-5 px-4 py-5 sm:px-6 lg:px-8">
            <KnowledgeHeader
              fileRef={knowledge.fileRef}
              isHealthy={knowledge.isHealthy}
              isLoading={knowledge.isLoading}
              isUploading={knowledge.isUploading}
              isRebuilding={knowledge.isRebuilding}
              notice={knowledge.notice}
              canManage={canManage}
              onFileChange={knowledge.handleFileChange}
              onRefresh={knowledge.refreshKnowledge}
              onRebuild={() => knowledge.setShowRebuildConfirm(true)}
            />

            <KnowledgeMetrics
              documents={knowledge.documents}
              isHealthy={knowledge.isHealthy}
              totalChunks={knowledge.totalChunks}
            />

            <section className="overflow-hidden rounded-[8px] border border-[var(--work-border)] bg-[var(--work-surface)] shadow-[0_1px_2px_rgba(15,23,42,0.04),0_18px_42px_rgba(15,23,42,0.06)]">
              <DocumentToolbar
                query={knowledge.query}
                extension={knowledge.extension}
                availableExtensions={knowledge.availableExtensions}
                filteredCount={knowledge.filteredDocuments.length}
                totalCount={knowledge.documents.length}
                selectedCount={knowledge.selectedIds.size}
                canManage={canManage}
                onQueryChange={knowledge.setQuery}
                onExtensionChange={knowledge.setExtension}
                onBatchDelete={() => knowledge.setShowBatchDeleteConfirm(true)}
                onClearSelection={knowledge.clearSelection}
              />
              <DocumentTable
                documents={knowledge.filteredDocuments}
                isLoading={knowledge.isLoading}
                totalDocuments={knowledge.documents.length}
                selectedIds={knowledge.selectedIds}
                canManage={canManage}
                onSelect={knowledge.setSelectedDocument}
                onCopyId={knowledge.copyDocumentId}
                onDelete={knowledge.setPendingDelete}
                onToggleSelect={knowledge.toggleSelect}
                onToggleSelectAll={knowledge.toggleSelectAll}
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

      {knowledge.showBatchDeleteConfirm ? (
        <ConfirmDialog
          title="批量删除文档索引"
          description={`将删除已选的 ${knowledge.selectedIds.size} 个文档及其所有片段索引。原始上传文件不会被删除。`}
          confirmLabel={`确认删除 ${knowledge.selectedIds.size} 个文档`}
          busy={knowledge.isDeleting}
          tone="danger"
          onCancel={() => knowledge.setShowBatchDeleteConfirm(false)}
          onConfirm={knowledge.handleBatchDelete}
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
  )}</RequireAuth>;
}

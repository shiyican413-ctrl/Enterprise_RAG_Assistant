import { Clipboard, FileText, Trash2 } from "lucide-react";
import type { KnowledgeDocument } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatDate } from "@/lib/utils";
import { displayExtension } from "./knowledge-utils";

type DocumentTableProps = {
  documents: KnowledgeDocument[];
  isLoading: boolean;
  totalDocuments: number;
  selectedIds: Set<string>;
  canManage: boolean;
  onSelect: (document: KnowledgeDocument) => void;
  onCopyId: (documentId: string) => void;
  onDelete: (document: KnowledgeDocument) => void;
  onToggleSelect: (documentId: string) => void;
  onToggleSelectAll: () => void;
};

export function DocumentTable({
  documents,
  isLoading,
  totalDocuments,
  selectedIds,
  canManage,
  onSelect,
  onCopyId,
  onDelete,
  onToggleSelect,
  onToggleSelectAll,
}: DocumentTableProps) {
  const allSelected = documents.length > 0 && selectedIds.size === documents.length;
  const columnCount = canManage ? 7 : 6;

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[860px] border-collapse text-left">
        <thead className="bg-[var(--work-surface-subtle)] text-xs font-bold uppercase text-[var(--work-muted)]">
          <tr>
            {canManage ? <th className="w-12 px-4 py-3">
              <input
                type="checkbox"
                checked={allSelected}
                onChange={onToggleSelectAll}
                className="size-4 cursor-pointer rounded border-[var(--work-border-strong)] accent-[var(--work-accent)]"
                aria-label="全选"
              />
            </th> : null}
            <th className="px-4 py-3">文档名称</th>
            <th className="px-4 py-3">类型</th>
            <th className="px-4 py-3">片段</th>
            <th className="px-4 py-3">上传时间</th>
            <th className="px-4 py-3">状态</th>
            <th className="px-4 py-3 text-right">操作</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--work-border)]">
          {isLoading ? (
            <TableMessage text="正在加载知识库文档..." colSpan={columnCount} />
          ) : documents.length ? (
            documents.map((doc) => (
              <tr
                key={doc.document_id}
                className={`transition-colors hover:bg-[var(--work-surface-subtle)] ${selectedIds.has(doc.document_id) ? "bg-[var(--work-accent-soft)]" : ""}`}
              >
                {canManage ? <td className="px-4 py-4">
                  <input
                    type="checkbox"
                    checked={selectedIds.has(doc.document_id)}
                    onChange={() => onToggleSelect(doc.document_id)}
                    className="size-4 cursor-pointer rounded border-[var(--work-border-strong)] accent-[var(--work-accent)]"
                    aria-label={`选择 ${doc.document_name}`}
                  />
                </td> : null}
                <td className="max-w-[360px] px-4 py-4">
                  <button
                    type="button"
                    className="flex min-w-0 items-center gap-3 text-left"
                    onClick={() => onSelect(doc)}
                  >
                    <span className="grid size-9 shrink-0 place-items-center rounded-[8px] bg-[var(--work-accent-soft)] text-[var(--work-accent)]">
                      <FileText className="size-4" />
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-bold text-[var(--work-text)]">
                        {doc.document_name}
                      </span>
                      <span className="block truncate text-xs font-medium text-[var(--work-muted)]">
                        {doc.document_id}
                      </span>
                    </span>
                  </button>
                </td>
                <td className="px-4 py-4">
                  <Badge variant="secondary" className="rounded-[8px]">
                    {displayExtension(doc)}
                  </Badge>
                </td>
                <td className="px-4 py-4 text-sm font-semibold text-[var(--work-text-soft)]">
                  {doc.chunk_count}
                </td>
                <td className="px-4 py-4 text-sm font-medium text-[var(--work-muted)]">
                  {formatDate(doc.created_at)}
                </td>
                <td className="px-4 py-4">
                  <Badge className="rounded-[8px] bg-[var(--work-success-soft)] text-emerald-700">
                    成功
                  </Badge>
                </td>
                <td className="px-4 py-4">
                  <div className="flex justify-end gap-2">
                    {canManage ? <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="rounded-[8px]"
                      onClick={() => onSelect(doc)}
                    >
                      查看
                    </Button> : null}
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      className="rounded-[8px]"
                      onClick={() => onCopyId(doc.document_id)}
                      aria-label="复制文档 ID"
                    >
                      <Clipboard className="size-4" />
                    </Button>
                    {canManage ? <Button
                      type="button"
                      variant="destructive"
                      size="icon-sm"
                      className="rounded-[8px]"
                      onClick={() => onDelete(doc)}
                      aria-label="删除文档"
                    >
                      <Trash2 className="size-4" />
                    </Button> : null}
                  </div>
                </td>
              </tr>
            ))
          ) : (
            <TableMessage
              colSpan={columnCount}
              text={
                totalDocuments
                  ? "没有匹配的文档，请调整搜索或筛选条件。"
                  : "暂无文档，请上传第一份企业资料。"
              }
            />
          )}
        </tbody>
      </table>
    </div>
  );
}

function TableMessage({ text, colSpan }: { text: string; colSpan: number }) {
  return (
    <tr>
      <td colSpan={colSpan} className="px-4 py-12 text-center text-sm font-semibold text-[var(--work-muted)]">
        {text}
      </td>
    </tr>
  );
}

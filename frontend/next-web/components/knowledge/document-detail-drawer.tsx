import { CheckCircle2, Loader2, X } from "lucide-react";
import type { DocumentChunk, KnowledgeDocument } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatDate } from "@/lib/utils";
import { displayExtension } from "./knowledge-utils";

type DocumentDetailDrawerProps = {
  document: KnowledgeDocument | null;
  chunks: DocumentChunk[];
  isLoadingChunks: boolean;
  onClose: () => void;
};

const pipelineSteps = ["保存原文件", "解析文本", "切分片段", "生成向量", "写入索引"];

export function DocumentDetailDrawer({
  document,
  chunks,
  isLoadingChunks,
  onClose,
}: DocumentDetailDrawerProps) {
  if (!document) return null;

  const metadata = document.metadata ?? {};

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/20">
      <aside className="flex h-full w-full max-w-[520px] flex-col bg-white shadow-2xl">
        <div className="flex items-start justify-between border-b border-[#e8ebf1] px-5 py-4">
          <div className="min-w-0">
            <h2 className="truncate text-lg font-bold text-[#111827]">
              {document.document_name}
            </h2>
            <p className="mt-1 truncate text-xs font-semibold text-[#8a93a3]">
              {document.document_id}
            </p>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            className="rounded-[8px]"
            onClick={onClose}
            aria-label="关闭详情"
          >
            <X className="size-4" />
          </Button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          <section className="space-y-3">
            <h3 className="text-sm font-bold text-[#1d2430]">基础信息</h3>
            <InfoRow label="类型" value={displayExtension(document)} />
            <InfoRow label="片段数" value={document.chunk_count.toString()} />
            <InfoRow label="上传时间" value={formatDate(document.created_at)} />
            <InfoRow label="MD5" value={metadata.file_md5 ?? "暂无"} />
            <InfoRow label="存储路径" value={metadata.source_path ?? "暂无"} />
          </section>

          <section className="mt-6">
            <h3 className="text-sm font-bold text-[#1d2430]">入库链路</h3>
            <div className="mt-3 grid gap-2">
              {pipelineSteps.map((step, index) => (
                <div
                  key={step}
                  className="flex items-center gap-3 rounded-[8px] border border-[#e8ecf3] bg-[#fbfcff] px-3 py-2"
                >
                  <span className="grid size-6 place-items-center rounded-full bg-emerald-50 text-xs font-bold text-emerald-700">
                    {index + 1}
                  </span>
                  <span className="text-sm font-semibold text-[#344054]">{step}</span>
                  <CheckCircle2 className="ml-auto size-4 text-emerald-500" />
                </div>
              ))}
            </div>
          </section>

          <section className="mt-6">
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-sm font-bold text-[#1d2430]">片段预览</h3>
              <Badge variant="outline" className="rounded-[8px]">
                {chunks.length} 个
              </Badge>
            </div>
            <div className="mt-3 space-y-3">
              {isLoadingChunks ? (
                <div className="flex items-center gap-2 rounded-[8px] border border-[#e8ecf3] bg-[#fbfcff] p-4 text-sm font-semibold text-[#667085]">
                  <Loader2 className="size-4 animate-spin" />
                  正在加载片段
                </div>
              ) : chunks.length ? (
                chunks.slice(0, 20).map((chunk) => (
                  <article
                    key={chunk.chunk_id}
                    className="rounded-[8px] border border-[#e8ecf3] bg-[#fbfcff] p-3"
                  >
                    <div className="mb-2 flex items-center justify-between gap-2">
                      <span className="text-xs font-bold text-[#2457e8]">
                        #{chunk.chunk_index + 1}
                      </span>
                      <span className="text-xs font-semibold text-[#8a93a3]">
                        {chunk.content.length} 字符
                      </span>
                    </div>
                    <p className="line-clamp-5 whitespace-pre-wrap text-sm leading-6 text-[#344054]">
                      {chunk.content}
                    </p>
                  </article>
                ))
              ) : (
                <div className="rounded-[8px] border border-[#e8ecf3] bg-[#fbfcff] p-4 text-sm font-semibold text-[#667085]">
                  暂无片段，文档可能尚未入库或解析失败。
                </div>
              )}
            </div>
          </section>
        </div>
      </aside>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[88px_minmax(0,1fr)] gap-3 text-sm">
      <span className="font-semibold text-[#8a93a3]">{label}</span>
      <span className="min-w-0 break-words font-semibold text-[#344054]">{value}</span>
    </div>
  );
}

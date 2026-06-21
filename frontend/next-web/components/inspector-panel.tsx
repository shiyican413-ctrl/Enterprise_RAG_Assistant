"use client";

import type { ChangeEvent, RefObject } from "react";
import { useMemo } from "react";
import {
  Database,
  FileText,
  Link2,
  Route,
  RefreshCw,
  UploadCloud,
} from "lucide-react";
import type { KnowledgeDocument, Source } from "@/lib/api";
import { pipeline } from "@/lib/types";
import { formatDate } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";

type InspectorPanelProps = {
  documents: KnowledgeDocument[];
  latestSources: Source[];
  isUploading: boolean;
  selectedFileName: string;
  notice?: string;
  onUpload: () => void;
  onFileSelect: (name: string) => void;
  onRefresh: () => void;
  fileRef: RefObject<HTMLInputElement | null>;
};

export function InspectorPanel({
  documents,
  latestSources,
  isUploading,
  selectedFileName,
  notice,
  onUpload,
  onFileSelect,
  onRefresh,
  fileRef,
}: InspectorPanelProps) {
  const totalChunks = useMemo(
    () => documents.reduce((sum, doc) => sum + doc.chunk_count, 0),
    [documents],
  );

  function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    if (files.length === 0) {
      onFileSelect("尚未选择文件");
      return;
    }

    if (files.length === 1) {
      onFileSelect(files[0].name);
      return;
    }

    onFileSelect(`已选择 ${files.length} 个文件`);
  }

  return (
    <aside className="flex min-h-0 flex-col border-t border-[var(--graphite)] bg-transparent xl:border-l xl:border-t-0">
      <div className="flex h-[60px] shrink-0 items-center justify-between border-b border-[var(--graphite)] px-5">
        <div>
          <h2 className="text-[15px] font-semibold text-[var(--stellar-white)]">知识库面板</h2>
          <p className="console-mono mt-0.5 normal-case" style={{ textTransform: "none", letterSpacing: "-0.01em", fontSize: "12px" }}>
            上传、索引与引用
          </p>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          className="rounded-[8px] border border-[var(--graphite)] text-[var(--ash)] hover:border-[var(--stellar-white)] hover:bg-transparent"
          onClick={onRefresh}
          aria-label="刷新知识库"
        >
          <RefreshCw className="size-4" />
        </Button>
      </div>

      <ScrollArea className="min-h-0 flex-1">
        <div className="space-y-4 p-5">
          <div className="grid grid-cols-2 gap-2.5">
            <Metric label="文档" value={documents.length.toString()} />
            <Metric label="片段" value={totalChunks.toString()} />
            <Metric label="引用" value={latestSources.length.toString()} />
            <Metric
              label="状态"
              value={isUploading ? "入库中" : documents.length ? "就绪" : "待上传"}
            />
          </div>

          <section className="rounded-[12px] border border-[var(--graphite)] bg-transparent p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-[var(--stellar-white)]">
              <UploadCloud className="size-[18px] text-[var(--signal-blue)]" />
              文档入库
            </div>
            <label
              htmlFor="document"
              className="flex min-h-[104px] cursor-pointer flex-col justify-center rounded-[10px] border border-dashed border-[var(--graphite)] bg-transparent px-4 py-3 transition-colors hover:border-[var(--stellar-white)]"
            >
              <input
                accept=".txt,.md,.csv,.json,.pdf"
                id="document"
                multiple
                onChange={handleFileChange}
                ref={fileRef}
                type="file"
                className="sr-only"
              />
              <span className="line-clamp-2 text-sm font-semibold text-[var(--stellar-white)]">
                {selectedFileName}
              </span>
              <span className="mt-2 text-xs leading-5 text-[var(--ash)]">
                支持文本、Markdown、CSV、JSON 与 PDF。上传后自动生成可检索索引。
              </span>
            </label>
            <button
              onClick={onUpload}
              disabled={isUploading}
              type="button"
              className="console-pill console-pill--ghost mt-3 h-10 w-full justify-center"
            >
              {isUploading ? "正在入库" : "上传并入库"}
            </button>
            {notice ? (
              <p className="mt-3 rounded-[8px] border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs font-semibold leading-5 text-emerald-400">
                {notice}
              </p>
            ) : null}
          </section>

          <section>
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-[var(--stellar-white)]">
              <Database className="size-5 text-[var(--signal-blue)]" />
              文档列表
            </div>
            <div className="space-y-2">
              {documents.length ? (
                documents.slice(0, 6).map((doc) => (
                  <div
                    key={doc.document_id}
                    className="rounded-[10px] border border-[var(--graphite)] bg-transparent p-3 transition-colors hover:border-[var(--stellar-white)]"
                  >
                    <div className="flex items-center gap-3">
                      <div className="grid size-9 shrink-0 place-items-center rounded-[8px] border border-[var(--graphite)] text-[var(--signal-blue)]">
                        <FileText className="size-4" />
                      </div>
                      <div className="min-w-0">
                        <div className="truncate text-sm font-semibold text-[var(--stellar-white)]">
                          {doc.document_name}
                        </div>
                        <div className="console-mono mt-0.5 normal-case" style={{ textTransform: "none", letterSpacing: "0", fontSize: "11px" }}>
                          {doc.chunk_count} 个片段 · {formatDate(doc.created_at)}
                        </div>
                      </div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="rounded-[10px] border border-[var(--graphite)] bg-transparent px-4 py-5 text-center text-sm font-medium text-[var(--ash)]">
                  暂无文档，请先上传企业资料。
                </div>
              )}
            </div>
          </section>

          <section>
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-[var(--stellar-white)]">
              <Link2 className="size-5 text-[var(--signal-blue)]" />
              证据来源
            </div>
            <div className="space-y-2">
              {latestSources.length ? (
                latestSources.map((source) => (
                  <div
                    key={source.chunk_id}
                    className="rounded-[10px] border border-[var(--graphite)] bg-transparent p-3"
                  >
                    <div className="truncate text-sm font-semibold text-[var(--stellar-white)]">
                      {source.document_name}
                    </div>
                    <div className="mt-1 text-xs font-semibold text-[var(--signal-blue)]">
                      匹配度 {Math.round(source.score * 100)}% · 第{" "}
                      {source.chunk_index + 1} 个片段
                    </div>
                    <p className="mt-2 line-clamp-3 text-xs leading-5 text-[var(--ash)]">
                      {source.snippet}
                    </p>
                  </div>
                ))
              ) : (
                <div className="rounded-[10px] border border-[var(--graphite)] bg-transparent px-4 py-5 text-center text-sm font-medium text-[var(--ash)]">
                  提交问题后显示引用片段和匹配度。
                </div>
              )}
            </div>
          </section>

          <section>
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-[var(--stellar-white)]">
              <Route className="size-5 text-[var(--signal-blue)]" />
              处理链路
            </div>
            <div className="space-y-2">
              {pipeline.map((step, index) => (
                <div
                  key={step.label}
                  className="rounded-[10px] border border-[var(--graphite)] bg-transparent px-3 py-2.5"
                >
                  <div className="flex items-center gap-2 text-sm font-semibold text-[var(--stellar-white)]">
                    <span className="font-mono text-xs text-[var(--signal-blue)]">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    {step.label}
                  </div>
                  <p className="mt-1 text-xs leading-5 text-[var(--ash)]">{step.text}</p>
                </div>
              ))}
            </div>
          </section>
        </div>
      </ScrollArea>
    </aside>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[10px] border border-[var(--graphite)] bg-transparent p-3">
      <div className="console-mono normal-case" style={{ textTransform: "none", letterSpacing: "0", fontSize: "11px" }}>
        {label}
      </div>
      <div className="mt-1 truncate text-base font-semibold text-[var(--stellar-white)]">{value}</div>
    </div>
  );
}

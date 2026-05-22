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
    <aside className="flex min-h-0 flex-col border-t border-[#e8ebf1] bg-white xl:border-l xl:border-t-0">
      <div className="flex h-[60px] shrink-0 items-center justify-between border-b border-[#edf0f5] px-5">
        <div>
          <h2 className="text-[15px] font-bold text-[#141820]">知识库面板</h2>
          <p className="text-xs font-medium text-[#8a93a3]">上传、索引与引用</p>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          className="rounded-[8px] text-[#667085] hover:bg-[#f4f6fa]"
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

          <section className="rounded-[12px] border border-[#e6eaf2] bg-[#f8faff] p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-bold text-[#171b22]">
              <UploadCloud className="size-[18px] text-[#2f66ff]" />
              文档入库
            </div>
            <label
              htmlFor="document"
                className="flex min-h-[104px] flex-col justify-center rounded-[10px] border border-dashed border-[#cfd8e8] bg-white px-4 py-3 transition-colors hover:border-[#8badff] hover:bg-[#fbfdff]"
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
              <span className="line-clamp-2 text-sm font-semibold text-[#2d3543]">
                {selectedFileName}
              </span>
              <span className="mt-2 text-xs leading-5 text-[#7a8393]">
                支持文本、Markdown、CSV、JSON 与 PDF。上传后自动生成可检索索引。
              </span>
            </label>
            <Button
              onClick={onUpload}
              disabled={isUploading}
              type="button"
              className="mt-3 h-10 w-full rounded-[8px] bg-[#2f66ff] text-sm font-bold text-white hover:bg-[#2457e8]"
            >
              {isUploading ? "正在入库" : "上传并入库"}
            </Button>
            {notice ? (
              <p className="mt-3 rounded-[8px] border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-semibold leading-5 text-emerald-700">
                {notice}
              </p>
            ) : null}
          </section>

          <section>
            <div className="mb-3 flex items-center gap-2 text-sm font-bold text-[#171b22]">
              <Database className="size-5 text-[#2f66ff]" />
              文档列表
            </div>
            <div className="space-y-2">
              {documents.length ? (
                documents.slice(0, 6).map((doc) => (
                  <div
                    key={doc.document_id}
                    className="rounded-[10px] border border-[#e8ecf3] bg-white p-3 transition-colors hover:bg-[#f8faff]"
                  >
                    <div className="flex items-center gap-3">
                      <div className="grid size-9 shrink-0 place-items-center rounded-[8px] bg-[#eef4ff] text-[#2f66ff]">
                        <FileText className="size-4" />
                      </div>
                      <div className="min-w-0">
                        <div className="truncate text-sm font-bold text-[#252a33]">
                          {doc.document_name}
                        </div>
                        <div className="text-xs font-medium text-[#8a93a3]">
                          {doc.chunk_count} 个片段 · {formatDate(doc.created_at)}
                        </div>
                      </div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="rounded-[10px] border border-[#e8ecf3] bg-[#f8faff] px-4 py-5 text-center text-sm font-medium text-[#7a8393]">
                  暂无文档，请先上传企业资料。
                </div>
              )}
            </div>
          </section>

          <section>
            <div className="mb-3 flex items-center gap-2 text-sm font-bold text-[#171b22]">
              <Link2 className="size-5 text-[#2f66ff]" />
              证据来源
            </div>
            <div className="space-y-2">
              {latestSources.length ? (
                latestSources.map((source) => (
                  <div
                    key={source.chunk_id}
                    className="rounded-[10px] border border-[#e8ecf3] bg-[#f8faff] p-3"
                  >
                    <div className="truncate text-sm font-bold text-[#252a33]">
                      {source.document_name}
                    </div>
                    <div className="mt-1 text-xs font-bold text-[#2f66ff]">
                      匹配度 {Math.round(source.score * 100)}% · 第{" "}
                      {source.chunk_index + 1} 个片段
                    </div>
                    <p className="mt-2 line-clamp-3 text-xs leading-5 text-[#687386]">
                      {source.snippet}
                    </p>
                  </div>
                ))
              ) : (
                <div className="rounded-[10px] border border-[#e8ecf3] bg-[#f8faff] px-4 py-5 text-center text-sm font-medium text-[#7a8393]">
                  提交问题后显示引用片段和匹配度。
                </div>
              )}
            </div>
          </section>

          <section>
            <div className="mb-3 flex items-center gap-2 text-sm font-bold text-[#171b22]">
              <Route className="size-5 text-[#2f66ff]" />
              处理链路
            </div>
            <div className="space-y-2">
              {pipeline.map((step, index) => (
                <div
                  key={step.label}
                  className="rounded-[10px] border border-[#e8ecf3] bg-white px-3 py-2.5"
                >
                  <div className="flex items-center gap-2 text-sm font-bold text-[#252a33]">
                    <span className="font-mono text-xs text-[#2f66ff]">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    {step.label}
                  </div>
                  <p className="mt-1 text-xs leading-5 text-[#7a8393]">{step.text}</p>
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
    <div className="rounded-[10px] border border-[#e8ecf3] bg-[#f8faff] p-3">
      <div className="text-xs font-bold text-[#8a93a3]">{label}</div>
      <div className="mt-1 truncate text-base font-bold text-[#151922]">{value}</div>
    </div>
  );
}

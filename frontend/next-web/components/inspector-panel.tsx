"use client";

import type { ChangeEvent, RefObject } from "react";
import type { KnowledgeDocument, Source } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { UploadIcon, DocumentIcon, TraceIcon } from "@/components/icons";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
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
  function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    onFileSelect(e.target.files?.[0]?.name ?? "尚未选择文件");
  }

  return (
    <div className="flex min-h-0 flex-col gap-3 overflow-y-auto">
      {/* Upload */}
      <Card className="rounded-xl">
        <CardHeader className="flex-row items-center justify-between pb-2">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-brand-500">
              文档入库
            </p>
            <CardTitle className="text-sm">上传知识文档</CardTitle>
          </div>
          <UploadIcon className="size-5 text-muted-foreground" />
        </CardHeader>
        <CardContent className="space-y-3">
          <label
            htmlFor="document"
            className="flex cursor-pointer flex-col gap-2 rounded-lg border-2 border-dashed border-border p-4 transition-colors hover:border-brand-300 hover:bg-brand-50/50"
          >
            <input
              accept=".txt,.md,.csv,.json,.pdf"
              id="document"
              onChange={handleFileChange}
              ref={fileRef}
              type="file"
              className="sr-only"
            />
            <Badge variant="secondary" className="w-fit text-xs">
              {selectedFileName}
            </Badge>
            <span className="text-sm font-medium">选择企业资料并生成索引</span>
            <span className="text-xs text-muted-foreground">
              支持文本、标记文档、表格、结构化数据与电子文档
            </span>
          </label>
          <Button
            onClick={onUpload}
            disabled={isUploading}
            type="button"
            className="w-full"
          >
            {isUploading ? "正在入库" : "上传并入库"}
          </Button>
          {notice && (
            <p className="rounded-lg border border-green-200 bg-green-50 p-3 text-sm font-medium text-green-700">
              {notice}
            </p>
          )}
        </CardContent>
      </Card>

      <Separator />

      {/* Document list */}
      <Card className="rounded-xl">
        <CardHeader className="flex-row items-center justify-between pb-2">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-brand-500">
              知识库
            </p>
            <CardTitle className="text-sm">文档列表</CardTitle>
          </div>
          <Button variant="ghost" size="sm" onClick={onRefresh} type="button">
            刷新
          </Button>
        </CardHeader>
        <CardContent>
          <ScrollArea className="max-h-[240px]">
            <div className="space-y-1">
              {documents.length ? (
                documents.slice(0, 6).map((doc) => (
                  <div
                    key={doc.document_id}
                    className="flex items-center gap-3 rounded-lg p-2 transition-colors hover:bg-muted/50"
                  >
                    <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-500">
                      <DocumentIcon className="size-4" />
                    </div>
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium">{doc.document_name}</div>
                      <div className="text-xs text-muted-foreground">
                        {doc.chunk_count} 个片段 · {formatDate(doc.created_at)}
                      </div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="py-6 text-center text-sm text-muted-foreground">
                  暂无文档，请先上传企业资料。
                </div>
              )}
            </div>
          </ScrollArea>
        </CardContent>
      </Card>

      <Separator />

      {/* Sources */}
      <Card className="rounded-xl">
        <CardHeader className="flex-row items-center justify-between pb-2">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-brand-500">
              引用溯源
            </p>
            <CardTitle className="text-sm">证据来源</CardTitle>
          </div>
          <TraceIcon className="size-5 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <ScrollArea className="max-h-[260px]">
            <div className="space-y-2">
              {latestSources.length ? (
                latestSources.map((source) => (
                  <div
                    key={source.chunk_id}
                    className="rounded-lg border border-border p-3 space-y-1"
                  >
                    <div className="text-sm font-medium">{source.document_name}</div>
                    <div className="text-xs font-medium text-brand-500">
                      匹配度 {Math.round(source.score * 100)}% · 第{" "}
                      {source.chunk_index + 1} 个片段
                    </div>
                    <p className="line-clamp-3 text-xs leading-relaxed text-muted-foreground">
                      {source.snippet}
                    </p>
                  </div>
                ))
              ) : (
                <div className="py-6 text-center text-sm text-muted-foreground">
                  提交问题后，这里会显示引用片段和匹配度。
                </div>
              )}
            </div>
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  );
}

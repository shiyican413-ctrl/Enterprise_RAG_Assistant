import type { ChangeEvent, RefObject } from "react";
import { CheckCircle2, Loader2, RefreshCw, RotateCcw, UploadCloud } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { KnowledgeNotice } from "./knowledge-utils";
import { ACCEPTED_EXTENSIONS } from "./knowledge-utils";

type KnowledgeHeaderProps = {
  fileRef: RefObject<HTMLInputElement | null>;
  isHealthy: boolean;
  isLoading: boolean;
  isUploading: boolean;
  isRebuilding: boolean;
  notice?: KnowledgeNotice;
  onFileChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onRefresh: () => void;
  onRebuild: () => void;
};

export function KnowledgeHeader({
  fileRef,
  isHealthy,
  isLoading,
  isUploading,
  isRebuilding,
  notice,
  onFileChange,
  onRefresh,
  onRebuild,
}: KnowledgeHeaderProps) {
  return (
    <section className="rounded-[8px] border border-[var(--work-border)] bg-[var(--work-surface)] px-5 py-5 shadow-[0_1px_2px_rgba(15,23,42,0.04),0_18px_42px_rgba(15,23,42,0.06)]">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-[26px] font-bold leading-tight text-[var(--work-text)]">
              知识库
            </h1>
            <ServiceBadge isHealthy={isHealthy} />
          </div>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--work-muted)]">
            企业资料、索引状态与引用质量管理。
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <input
            ref={fileRef}
            type="file"
            multiple
            accept={ACCEPTED_EXTENSIONS.join(",")}
            className="sr-only"
            onChange={onFileChange}
          />
          <Button
            type="button"
            className="h-10 rounded-[8px] bg-[var(--work-accent)] px-4 text-sm font-semibold text-white hover:bg-[var(--work-accent-strong)]"
            disabled={isUploading || !isHealthy}
            onClick={() => fileRef.current?.click()}
          >
            {isUploading ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <UploadCloud className="size-4" />
            )}
            上传文档
          </Button>
          <Button
            type="button"
            variant="outline"
            className="h-10 rounded-[8px] border-[var(--work-border-strong)] bg-[var(--work-surface)] px-4 text-sm font-semibold text-[var(--work-text-soft)] hover:bg-[var(--work-surface-subtle)]"
            onClick={onRefresh}
            disabled={isLoading}
          >
            <RefreshCw className={cn("size-4", isLoading && "animate-spin")} />
            刷新
          </Button>
          <Button
            type="button"
            variant="destructive"
            className="h-10 rounded-[8px] px-4 text-sm font-semibold"
            disabled={isRebuilding || !isHealthy}
            onClick={onRebuild}
          >
            <RotateCcw className="size-4" />
            重建索引
          </Button>
        </div>
      </div>

      {notice ? <NoticeBar notice={notice} /> : null}
    </section>
  );
}

function ServiceBadge({ isHealthy }: { isHealthy: boolean }) {
  return (
    <Badge
      variant="outline"
      className={cn(
        "h-7 rounded-[8px] px-2.5 text-xs font-bold",
        isHealthy
          ? "border-emerald-200 bg-[var(--work-success-soft)] text-emerald-700"
          : "border-[var(--work-border-strong)] bg-[var(--work-surface-subtle)] text-[var(--work-muted)]",
      )}
    >
      <CheckCircle2 className={cn("size-3.5", !isHealthy && "text-[var(--work-faint)]")} />
      {isHealthy ? "后端在线" : "等待后端"}
    </Badge>
  );
}

function NoticeBar({ notice }: { notice: KnowledgeNotice }) {
  return (
    <div
      className={cn(
        "mt-4 rounded-[8px] border px-3 py-2 text-sm font-semibold",
        notice.tone === "success" && "border-emerald-200 bg-[var(--work-success-soft)] text-emerald-700",
        notice.tone === "error" && "border-red-200 bg-[var(--work-danger-soft)] text-red-700",
        notice.tone === "info" && "border-[var(--work-border-strong)] bg-[var(--work-surface-subtle)] text-[var(--work-text-soft)]",
      )}
    >
      {notice.text}
    </div>
  );
}

import type { KnowledgeDocument } from "@/lib/api";
import { formatDate } from "@/lib/utils";

type KnowledgeMetricsProps = {
  documents: KnowledgeDocument[];
  isHealthy: boolean;
  totalChunks: number;
};

export function KnowledgeMetrics({
  documents,
  isHealthy,
  totalChunks,
}: KnowledgeMetricsProps) {
  const newestDocument = documents[0];

  return (
    <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      <MetricCard label="文档总数" value={documents.length.toString()} />
      <MetricCard label="片段总数" value={totalChunks.toString()} />
      <MetricCard
        label="索引状态"
        value={isHealthy ? (documents.length ? "可检索" : "待入库") : "离线"}
      />
      <MetricCard
        label="最近入库"
        value={newestDocument ? formatDate(newestDocument.created_at) : "暂无记录"}
      />
    </section>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[8px] border border-[#e4e8f0] bg-white p-4 shadow-[0_1px_2px_rgba(16,24,40,0.03)]">
      <div className="text-xs font-bold text-[#8a93a3]">{label}</div>
      <div className="mt-2 truncate text-xl font-bold text-[#111827]">{value}</div>
    </div>
  );
}

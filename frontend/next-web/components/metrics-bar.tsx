"use client";

import { useMemo } from "react";
import type { KnowledgeDocument, Source } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";

type MetricsBarProps = {
  documents: KnowledgeDocument[];
  latestSources: Source[];
};

export function MetricsBar({ documents, latestSources }: MetricsBarProps) {
  const totalChunks = useMemo(
    () => documents.reduce((sum, doc) => sum + doc.chunk_count, 0),
    [documents],
  );

  const averageScore = latestSources.length
    ? Math.round(
        (latestSources.reduce((sum, s) => sum + s.score, 0) / latestSources.length) * 100,
      )
    : 0;

  const metrics = [
    { label: "知识文档", value: documents.length.toString() },
    { label: "知识片段", value: totalChunks.toString() },
    { label: "引用来源", value: latestSources.length.toString() },
    { label: "匹配均值", value: averageScore ? `${averageScore}%` : "--" },
  ];

  return (
    <div className="grid grid-cols-4 gap-3">
      {metrics.map((m) => (
        <Card key={m.label} className="rounded-xl">
          <CardContent className="p-4">
            <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              {m.label}
            </div>
            <div className="mt-1 text-2xl font-bold tracking-tight">{m.value}</div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

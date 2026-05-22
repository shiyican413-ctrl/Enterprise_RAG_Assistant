"use client";

import { pipeline } from "@/lib/types";
import { Card, CardContent } from "@/components/ui/card";

export function PipelineBar() {
  return (
    <Card className="rounded-xl">
      <CardContent className="grid grid-cols-5 divide-x divide-border p-0">
        {pipeline.map((step, index) => (
          <div key={step.label} className="p-4">
            <span className="font-mono text-xs font-bold text-brand-500">
              {String(index + 1).padStart(2, "0")}
            </span>
            <div className="mt-1.5 text-sm font-semibold">{step.label}</div>
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{step.text}</p>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

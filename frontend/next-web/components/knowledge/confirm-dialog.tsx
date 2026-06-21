import { AlertTriangle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type ConfirmDialogProps = {
  title: string;
  description: string;
  confirmLabel: string;
  busy: boolean;
  tone: "danger";
  onCancel: () => void;
  onConfirm: () => void;
};

export function ConfirmDialog({
  title,
  description,
  confirmLabel,
  busy,
  tone,
  onCancel,
  onConfirm,
}: ConfirmDialogProps) {
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/45 px-4">
      <div className="w-full max-w-[440px] rounded-[8px] border border-[var(--work-border)] bg-[var(--work-surface)] p-5 shadow-2xl">
        <div className="flex gap-3">
          <span
            className={cn(
              "grid size-10 shrink-0 place-items-center rounded-[8px]",
              tone === "danger" && "bg-[var(--work-danger-soft)] text-red-600",
            )}
          >
            <AlertTriangle className="size-5" />
          </span>
          <div>
            <h2 className="text-base font-bold text-[var(--work-text)]">{title}</h2>
            <p className="mt-2 text-sm leading-6 text-[var(--work-muted)]">{description}</p>
          </div>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            className="rounded-[8px]"
            onClick={onCancel}
            disabled={busy}
          >
            取消
          </Button>
          <Button
            type="button"
            variant="destructive"
            className="rounded-[8px]"
            onClick={onConfirm}
            disabled={busy}
          >
            {busy ? <Loader2 className="size-4 animate-spin" /> : null}
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}

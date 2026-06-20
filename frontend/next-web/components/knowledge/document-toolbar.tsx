import { Filter, Search, Trash2, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

type DocumentToolbarProps = {
  query: string;
  extension: string;
  availableExtensions: string[];
  filteredCount: number;
  totalCount: number;
  selectedCount: number;
  onQueryChange: (query: string) => void;
  onExtensionChange: (extension: string) => void;
  onBatchDelete: () => void;
  onClearSelection: () => void;
};

export function DocumentToolbar({
  query,
  extension,
  availableExtensions,
  filteredCount,
  totalCount,
  selectedCount,
  onQueryChange,
  onExtensionChange,
  onBatchDelete,
  onClearSelection,
}: DocumentToolbarProps) {
  return (
    <div className="flex flex-col gap-3 border-b border-[#e8ebf1] px-4 py-4 lg:flex-row lg:items-center lg:justify-between">
      <div className="relative min-w-0 flex-1">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[#8a93a3]" />
        <input
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="按文档名、ID、MD5、路径搜索"
          className="h-10 w-full rounded-[8px] border border-[#d9dee8] bg-[#fbfcff] pl-9 pr-3 text-sm font-medium outline-none transition-colors placeholder:text-[#98a2b3] focus:border-[#2457e8] focus:bg-white"
        />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {selectedCount > 0 && (
          <>
            <Badge variant="outline" className="h-10 gap-1.5 rounded-[8px] border-[#2457e8] bg-[#f0f5ff] px-3 text-sm font-semibold text-[#2457e8]">
              已选 {selectedCount} 项
              <button
                type="button"
                className="grid size-4 place-items-center rounded-full transition-colors hover:bg-[#2457e8]/10"
                onClick={onClearSelection}
                aria-label="取消选择"
              >
                <X className="size-3" />
              </button>
            </Badge>
            <Button
              type="button"
              variant="destructive"
              size="sm"
              className="h-10 gap-1.5 rounded-[8px]"
              onClick={onBatchDelete}
            >
              <Trash2 className="size-4" />
              批量删除
            </Button>
          </>
        )}
        <div className="flex h-10 items-center gap-2 rounded-[8px] border border-[#d9dee8] bg-white px-3">
          <Filter className="size-4 text-[#667085]" />
          <select
            value={extension}
            onChange={(event) => onExtensionChange(event.target.value)}
            className="bg-transparent text-sm font-semibold text-[#344054] outline-none"
            aria-label="文件类型筛选"
          >
            <option value="all">全部类型</option>
            {availableExtensions.map((item) => (
              <option key={item} value={item}>
                {item.replace(".", "").toUpperCase()}
              </option>
            ))}
          </select>
        </div>
        <Badge variant="outline" className="h-10 rounded-[8px] px-3 text-sm">
          {filteredCount} / {totalCount} 个文档
        </Badge>
      </div>
    </div>
  );
}

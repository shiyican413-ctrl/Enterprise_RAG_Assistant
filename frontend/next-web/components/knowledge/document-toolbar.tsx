import { Filter, Search } from "lucide-react";
import { Badge } from "@/components/ui/badge";

type DocumentToolbarProps = {
  query: string;
  extension: string;
  availableExtensions: string[];
  filteredCount: number;
  totalCount: number;
  onQueryChange: (query: string) => void;
  onExtensionChange: (extension: string) => void;
};

export function DocumentToolbar({
  query,
  extension,
  availableExtensions,
  filteredCount,
  totalCount,
  onQueryChange,
  onExtensionChange,
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

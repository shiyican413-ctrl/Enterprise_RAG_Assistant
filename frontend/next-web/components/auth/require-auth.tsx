"use client";

import { useEffect, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/components/auth/auth-provider";

export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !user) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [loading, pathname, router, user]);

  if (loading || !user) {
    return (
      <div className="grid min-h-screen place-items-center bg-[#0c0c0b] text-white">
        <div className="flex items-center gap-3 font-mono text-xs uppercase tracking-[0.18em] text-zinc-400">
          <span className="size-2 animate-pulse rounded-full bg-blue-400 shadow-[0_0_18px_rgba(151,196,255,.8)]" />
          正在验证登录状态
        </div>
      </div>
    );
  }
  return children;
}

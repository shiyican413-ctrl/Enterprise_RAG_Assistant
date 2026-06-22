"use client";

import { useCallback, useEffect, useRef, useState, type CSSProperties } from "react";
import { useRouter } from "next/navigation";

const STARS = [
  ["6%", "12%", 0],
  ["14%", "30%", 80],
  ["22%", "16%", 160],
  ["30%", "42%", 240],
  ["38%", "22%", 320],
  ["46%", "34%", 400],
  ["54%", "14%", 480],
  ["62%", "40%", 560],
  ["70%", "20%", 640],
  ["78%", "32%", 720],
  ["86%", "12%", 800],
  ["92%", "46%", 880],
  ["10%", "60%", 120],
  ["18%", "78%", 220],
  ["28%", "66%", 340],
  ["36%", "84%", 460],
  ["48%", "62%", 580],
  ["58%", "78%", 700],
  ["68%", "58%", 820],
  ["80%", "72%", 940],
  ["90%", "62%", 1060],
] as const;

export function ConsoleTransition() {
  const router = useRouter();
  const [active, setActive] = useState(false);
  const isRoutingRef = useRef(false);
  const timeoutRef = useRef<number | null>(null);

  const startConsoleTransition = useCallback(() => {
    if (isRoutingRef.current) return;

    isRoutingRef.current = true;
    setActive(true);

    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const delay = prefersReducedMotion ? 120 : 2000;

    timeoutRef.current = window.setTimeout(() => {
      router.push("/console");
    }, delay);
  }, [router]);

  useEffect(() => {
    function handleDocumentClick(event: MouseEvent) {
      if (event.defaultPrevented || event.button !== 0) return;
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;

      const target = event.target;
      if (!(target instanceof Element)) return;

      const link = target.closest<HTMLAnchorElement>("a[href]");
      if (!link || link.target) return;

      const url = new URL(link.href, window.location.href);
      if (url.origin !== window.location.origin || url.pathname !== "/console" || url.hash) return;

      event.preventDefault();
      startConsoleTransition();
    }

    function handleOpenConsole(event: Event) {
      event.preventDefault();
      startConsoleTransition();
    }

    document.addEventListener("click", handleDocumentClick, true);
    window.addEventListener("landing:open-console", handleOpenConsole);

    return () => {
      document.removeEventListener("click", handleDocumentClick, true);
      window.removeEventListener("landing:open-console", handleOpenConsole);
      if (timeoutRef.current) window.clearTimeout(timeoutRef.current);
    };
  }, [startConsoleTransition]);

  return (
    <div
      className={`console-transition ${active ? "is-active" : ""}`}
      aria-hidden={!active}
    >
      <div className="console-transition__stars" aria-hidden>
        {STARS.map(([left, top, delay], index) => (
          <span
            key={`${left}-${top}-${index}`}
            style={
              {
                left,
                top,
                "--star-delay": `${delay}ms`,
              } as CSSProperties
            }
          />
        ))}
      </div>
      <div className="console-transition__origin" aria-hidden />
      <div className="console-transition__beam" aria-hidden />
      <div className="console-transition__wipe" aria-hidden />
      <div className="console-transition__copy">
        <span>Lighting knowledge field</span>
        <strong>正在点亮企业知识星图</strong>
      </div>
    </div>
  );
}

"use client";

import { useEffect } from "react";

/**
 * Adds `.nav--scrolled` (frosted glass + hairline) to the top nav after scroll.
 * Renders nothing.
 */
export function NavScroll() {
  useEffect(() => {
    const nav = document.querySelector<HTMLElement>(".site-landing .nav");
    if (!nav) return;

    const onScroll = () => {
      nav.classList.toggle("nav--scrolled", window.scrollY > 8);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return null;
}

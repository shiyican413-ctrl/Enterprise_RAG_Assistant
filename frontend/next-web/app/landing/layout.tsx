import type { ReactNode } from "react";
import "./landing.css";

// Fonts are defined as offline-safe system stacks in landing.css
// (universalSans → Inter/Segoe; GeistMono → JetBrains Mono/Consolas).
// The whole landing is scoped under `.site-landing` so the light-themed
// console (/, /knowledge) is never affected.

export default function LandingLayout({ children }: { children: ReactNode }) {
  return (
    <div className="site-landing">
      {/* If JS is disabled, never leave reveal elements hidden */}
      <noscript>
        <style>{`.site-landing .reveal{opacity:1!important;transform:none!important;}`}</style>
      </noscript>
      {children}
    </div>
  );
}

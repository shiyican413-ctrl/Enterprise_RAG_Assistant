"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

/**
 * Hero search entry. Decorative-looking but functional: submitting navigates
 * to the console (`/`), where the user can continue the conversation.
 */
export function HeroEntry() {
  const router = useRouter();
  const [value, setValue] = useState("");

  function go(event: FormEvent) {
    event.preventDefault();
    const transitionEvent = new CustomEvent("landing:open-console", {
      cancelable: true,
    });

    window.dispatchEvent(transitionEvent);
    if (!transitionEvent.defaultPrevented) {
      router.push("/");
    }
  }

  return (
    <form className="hero-entry" onSubmit={go} role="search">
      <input
        type="text"
        aria-label="搜索企业知识库"
        placeholder="搜索你的企业知识库，或直接提问…"
        value={value}
        onChange={(e) => setValue(e.target.value)}
      />
      <button type="submit" aria-label="进入控制台">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
          <path
            d="M12 19V5M12 5l-7 7M12 5l7 7"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>
    </form>
  );
}

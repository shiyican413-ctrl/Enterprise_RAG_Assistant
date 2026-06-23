"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { ArrowRight, LockKeyhole, Mail } from "lucide-react";
import { CosmicBackground } from "@/app/landing/cosmic-background";
import { ConsoleTransition } from "@/app/landing/console-transition";
import { useAuth } from "@/components/auth/auth-provider";
import { login } from "@/lib/auth";
import "../landing/landing.css";
import "./login.css";

export default function LoginPage() {
  const { setUser } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError("");
    try {
      const user = await login(email.trim(), password);
      setUser(user);
      window.dispatchEvent(new CustomEvent("landing:open-console", { cancelable: true }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "登录失败，请稍后重试");
      setSubmitting(false);
    }
  }

  return (
    <main className="site-landing site-login">
      <CosmicBackground />
      <div className="aurora" aria-hidden><span /><span /><span /></div>
      <ConsoleTransition />

      <header className="login-nav">
        <Link className="brand" href="/" aria-label="返回 Enterprise RAG 官网">
          <span className="brand__mark" aria-hidden>
            <svg viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="6" stroke="currentColor" strokeWidth="1.4" />
              <circle cx="18.5" cy="5.5" r="1.6" fill="currentColor" />
              <path d="M12 3a9 9 0 0 1 5 1.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
            </svg>
          </span>
          <span className="brand__name">Enterprise RAG</span>
        </Link>
        <Link href="/" className="login-back">返回官网</Link>
      </header>

      <section className="login-stage">
        <div className="login-bloom" aria-hidden />
        <div className="login-copy">
          <p className="eyebrow">[ SECURE · KNOWLEDGE · ACCESS ]</p>
          <h1>连接企业<br />知识星图</h1>
          <p>登录后进入受权限保护的智能问答与知识库工作台。</p>
        </div>

        <form className="login-card" onSubmit={handleSubmit}>
          <div className="login-card__head">
            <span className="login-orbit" aria-hidden><i /></span>
            <div><p className="eyebrow">Console access</p><h2>欢迎回来</h2></div>
          </div>

          <label htmlFor="email">邮箱</label>
          <div className="login-field">
            <Mail aria-hidden size={18} />
            <input id="email" name="email" type="email" autoComplete="username" required
              placeholder="name@company.com" value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>

          <label htmlFor="password">密码</label>
          <div className="login-field">
            <LockKeyhole aria-hidden size={18} />
            <input id="password" name="password" type="password" autoComplete="current-password" required
              placeholder="输入登录密码" value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>

          <div className="login-error" role="alert" aria-live="polite">{error}</div>
          <button className="login-submit" type="submit" disabled={submitting}>
            <span>{submitting ? "正在验证身份…" : "进入控制台"}</span>
            <ArrowRight aria-hidden size={18} />
          </button>
          <p className="login-note">账号由企业管理员统一分配 · 暂不开放注册</p>
        </form>
      </section>
    </main>
  );
}

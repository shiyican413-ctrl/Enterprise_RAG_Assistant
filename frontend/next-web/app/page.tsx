import type { ReactNode } from "react";
import "./landing/landing.css";
import { HeroEntry } from "./landing/hero-entry";
import { CosmicBackground } from "./landing/cosmic-background";
import { CursorGlow } from "./landing/cursor-glow";
import { ScrollProgress } from "./landing/scroll-progress";
import { ScrollReveal } from "./landing/scroll-reveal";
import { NavScroll } from "./landing/nav-scroll";
import { ConsoleTransition } from "./landing/console-transition";

/**
 * Enterprise RAG Assistant — official landing page.
 * xAI-inspired "cosmic void" theme. Bilingual: English mono eyebrows / wordmark,
 * Chinese section titles + body. Self-contained markup; styling lives in landing.css.
 */

type Capability = {
  index: string;
  title: string;
  desc: string;
};

const CAPABILITIES: Capability[] = [
  {
    index: "01",
    title: "多格式文档入库",
    desc: "支持 .txt / .md / .csv / .json / .pdf 上传、解析、切分与入库，首启自动创建向量索引。",
  },
  {
    index: "02",
    title: "Milvus 语义检索",
    desc: "阿里云百炼 text-embedding-v4 生成 dense embedding，写入 Milvus 向量库做相似度召回。",
  },
  {
    index: "03",
    title: "SSE 流式问答",
    desc: "answer_delta → sources → done，逐字输出与引用来源同步返回，响应即时可读。",
  },
  {
    index: "04",
    title: "快速 / 思考双模式",
    desc: "统一接入阿里云百炼，快速与思考模式按问题复杂度一键切换。",
  },
  {
    index: "05",
    title: "引用追溯",
    desc: "每条回答附带命中文档、片段内容、片段序号与匹配分数，便于核验依据。",
  },
  {
    index: "06",
    title: "会话记录",
    desc: "问答历史写入 PostgreSQL，可按 conversation_id 回溯完整上下文。",
  },
  {
    index: "07",
    title: "智能体编排",
    desc: "Planner 规划 / Executor 执行 / ReAct 推理，配合可插拔工具与 MCP 适配。",
  },
  {
    index: "08",
    title: "输入护栏",
    desc: "对用户输入做安全校验，过滤越权与有害请求，守护企业知识边界。",
  },
  {
    index: "09",
    title: "可观测 Trace",
    desc: "记录规划层 / 执行层 / 命令层全链路步骤，链路透明、可调试。",
  },
  {
    index: "10",
    title: "本地降级",
    desc: "设置 VECTOR_STORE_BACKEND=local 即可离线开发与链路验证，零外部依赖。",
  },
];

const PIPELINE = [
  "文档上传",
  "文本解析",
  "文本切分",
  "Milvus 入库",
  "相似度检索",
  "流式问答",
  "引用追溯",
  "会话记录",
];

const STACK_TAGS = [
  "FastAPI",
  "Next.js",
  "React 19",
  "Milvus",
  "PostgreSQL",
  "百炼 text-embedding-v4",
  "阿里云百炼 Qwen",
  "SSE",
  "ReAct Agent",
];

function Pill({
  href,
  children,
  variant = "default",
}: {
  href: string;
  children: ReactNode;
  variant?: "default" | "smoke";
}) {
  return (
    <a className={`pill ${variant === "smoke" ? "pill--smoke" : ""}`} href={href}>
      {children}
      <span className="arrow" aria-hidden>
        ↗
      </span>
    </a>
  );
}

/* ---- Abstract line illustrations (1px #1f2228 strokes) -------------------- */

function CometArt() {
  return (
    <svg viewBox="0 0 200 160" fill="none" aria-hidden>
      <path
        d="M20 140C70 140 150 60 185 25"
        stroke="currentColor"
        strokeWidth="1"
        strokeLinecap="round"
      />
      <path
        d="M55 110C95 110 140 70 165 45"
        stroke="currentColor"
        strokeWidth="1"
        strokeLinecap="round"
        opacity="0.5"
      />
      <circle cx="185" cy="25" r="4" fill="currentColor" />
      <circle cx="185" cy="25" r="9" stroke="currentColor" strokeWidth="1" />
    </svg>
  );
}

function TerminalArt() {
  return (
    <svg viewBox="0 0 200 160" fill="none" aria-hidden>
      <rect
        x="16"
        y="24"
        width="168"
        height="112"
        stroke="currentColor"
        strokeWidth="1"
      />
      <path d="M16 48H184" stroke="currentColor" strokeWidth="1" />
      <circle cx="30" cy="36" r="2.5" fill="currentColor" />
      <circle cx="42" cy="36" r="2.5" fill="currentColor" />
      <circle cx="54" cy="36" r="2.5" fill="currentColor" />
      <path
        d="M36 76l16 14-16 14"
        stroke="currentColor"
        strokeWidth="1"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M68 110h56" stroke="currentColor" strokeWidth="1" strokeLinecap="round" />
    </svg>
  );
}

function NodesArt() {
  return (
    <svg viewBox="0 0 200 160" fill="none" aria-hidden>
      <circle cx="40" cy="40" r="6" stroke="currentColor" strokeWidth="1" />
      <circle cx="160" cy="50" r="6" stroke="currentColor" strokeWidth="1" />
      <circle cx="100" cy="120" r="6" stroke="currentColor" strokeWidth="1" />
      <circle cx="150" cy="130" r="6" stroke="currentColor" strokeWidth="1" />
      <path
        d="M46 43L154 48M43 45l54 71M155 55l-49 60M104 124l40 0"
        stroke="currentColor"
        strokeWidth="1"
        opacity="0.7"
      />
      <circle cx="100" cy="80" r="3" fill="currentColor" />
    </svg>
  );
}

/* ---- Page ----------------------------------------------------------------- */

export default function LandingPage() {
  return (
    <div className="site-landing">
      {/* If JS is disabled, never leave reveal elements hidden */}
      <noscript>
        <style>{`.site-landing .reveal{opacity:1!important;transform:none!important;}`}</style>
      </noscript>
      <CosmicBackground />
      <div className="aurora" aria-hidden>
        <span />
        <span />
        <span />
      </div>
      <CursorGlow />
      <ScrollProgress />
      <NavScroll />
      <ScrollReveal />
      <ConsoleTransition />

      {/* ===== Navigation ===== */}
      <header className="nav">
        <div className="nav__inner">
          <a className="brand" href="/">
            <span className="brand__mark" aria-hidden>
              <svg viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="6" stroke="currentColor" strokeWidth="1.4" />
                <circle cx="18.5" cy="5.5" r="1.6" fill="currentColor" />
                <path
                  d="M12 3a9 9 0 0 1 5 1.5"
                  stroke="currentColor"
                  strokeWidth="1.4"
                  strokeLinecap="round"
                />
              </svg>
            </span>
            <span className="brand__name">Enterprise RAG</span>
          </a>

          <nav className="nav__links" aria-label="主导航">
            <a className="nav__link" href="#products">
              Products
            </a>
            <a className="nav__link" href="#capabilities">
              Capabilities
            </a>
            <a className="nav__link" href="#architecture">
              Architecture
            </a>
            <a className="nav__link" href="#stack">
              Stack
            </a>
          </nav>

          <Pill href="/console">打开控制台</Pill>
        </div>
      </header>

      {/* ===== Hero ===== */}
      <section className="hero">
        <div className="hero__bloom" aria-hidden />
        <div className="hero__bloom-2" aria-hidden />
        <div className="wrap hero__content">
          <p
            className="hero__eyebrow reveal"
            style={{ transitionDelay: "0ms" }}
          >
            [ Enterprise · Retrieval · Generation ]
          </p>
          <h1
            className="hero__wordmark reveal"
            style={{ transitionDelay: "80ms" }}
          >
            Enterprise RAG
          </h1>
          <p className="hero__sub reveal" style={{ transitionDelay: "160ms" }}>
            面向企业的检索增强智能问答平台。上传制度、产品手册与常见问题，获得带引用溯源的流式回答。
          </p>
          <p className="hero__meta reveal" style={{ transitionDelay: "240ms" }}>
            文档入库 · 向量检索 · 流式问答 · 引用追溯 · 会话记录
          </p>

          <div className="reveal" style={{ transitionDelay: "320ms", width: "100%", display: "flex", justifyContent: "center" }}>
            <HeroEntry />
          </div>

          <div
            className="announce reveal"
            style={{ transitionDelay: "400ms" }}
          >
            <div className="announce__text">
              <span className="announce__head">
                已上线 Planner / Executor / ReAct 智能体编排
              </span>
              <span className="announce__sub">
                支持输入护栏与全链路 Trace 可观测
              </span>
            </div>
            <Pill href="#architecture" variant="smoke">
              查看发布说明
            </Pill>
          </div>
        </div>
      </section>

      {/* ===== Products ===== */}
      <section id="products" className="section">
        <div className="wrap">
          <div className="section__head reveal">
            <p className="eyebrow">[ Products ]</p>
            <h2 className="section-title">一个平台，覆盖知识全链路。</h2>
          </div>

          <div className="products">
            {[
              {
                tag: "Q & A",
                title: "智能问答",
                desc: "上传企业资料即可提问，默认通过 SSE 流式返回回答，并展示本次命中的引用来源，方便核验依据。",
                art: <CometArt />,
                cta: "立即体验",
                href: "/console",
              },
              {
                tag: "Knowledge",
                title: "知识库管理",
                desc: "查看文档总数、片段总数与索引状态，支持搜索、筛选、查看片段、复制 ID、删除与重建索引。",
                art: <TerminalArt />,
                cta: "管理文档",
                href: "/knowledge",
              },
              {
                tag: "Agent",
                title: "智能体编排",
                desc: "Planner 规划、Executor 执行、ReAct 推理，配合输入护栏与 Trace 全链路可观测，链路透明可控。",
                art: <NodesArt />,
                cta: "了解架构",
                href: "#architecture",
              },
            ].map((p, i) => (
              <article
                className="product reveal"
                key={p.tag}
                style={{ transitionDelay: `${i * 90}ms` }}
              >
                <span className="product__tag">{p.tag}</span>
                <h3 className="product__title">{p.title}</h3>
                <p className="product__desc">{p.desc}</p>
                <div className="product__art">{p.art}</div>
                <div className="product__cta">
                  <Pill href={p.href} variant="smoke">
                    {p.cta}
                  </Pill>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* ===== Capabilities ===== */}
      <section id="capabilities" className="section">
        <div className="wrap">
          <div className="section__head reveal">
            <p className="eyebrow">[ Capabilities ]</p>
            <h2 className="section-title">为生产环境而生的企业级能力。</h2>
          </div>

          <div className="capabilities">
            {CAPABILITIES.map((cap, i) => (
              <div
                className="cap reveal"
                key={cap.index}
                style={{ transitionDelay: `${(i % 2) * 80}ms` }}
              >
                <span className="cap__index">[ {cap.index} ]</span>
                <div className="cap__body">
                  <h3 className="cap__title">{cap.title}</h3>
                  <p className="cap__desc">{cap.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ===== Architecture ===== */}
      <section id="architecture" className="section">
        <div className="wrap">
          <div className="section__head reveal">
            <p className="eyebrow">[ Architecture ]</p>
            <h2 className="section-title">从文档到回答，一条可追溯的链路。</h2>
          </div>

          <div className="pipeline reveal">
            {PIPELINE.map((step, i) => (
              <span key={step} style={{ display: "contents" }}>
                <span className="pipeline__step">{step}</span>
                {i < PIPELINE.length - 1 && (
                  <span className="pipeline__sep" aria-hidden>
                    →
                  </span>
                )}
              </span>
            ))}
          </div>

          <div className="stack-cols">
            {[
              {
                label: "Frontend",
                title: "Next.js",
                desc: "React 19 + App Router，构建企业知识库智能问答控制台、侧边栏与知识库管理页。",
              },
              {
                label: "Backend",
                title: "FastAPI",
                desc: "路由与用例编排、RAG 门面、Planner / Executor / ReAct Agent、输入护栏与 Trace。",
              },
              {
                label: "Storage",
                title: "Milvus + PostgreSQL",
                desc: "分层存储：Milvus 承载文档片段与 embedding，PostgreSQL 记录会话历史。",
              },
            ].map((col, i) => (
              <div
                className="stack-col reveal"
                key={col.label}
                style={{ transitionDelay: `${i * 90}ms` }}
              >
                <span className="stack-col__label">{col.label}</span>
                <h3 className="stack-col__title">{col.title}</h3>
                <p className="stack-col__desc">{col.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ===== Stack ===== */}
      <section id="stack" className="section">
        <div className="wrap">
          <div className="section__head reveal">
            <p className="eyebrow">[ Stack ]</p>
            <h2 className="section-title">技术栈。</h2>
          </div>
          <div className="tags reveal">
            {STACK_TAGS.map((tag) => (
              <span className="tag" key={tag}>
                {tag}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* ===== CTA ===== */}
      <section className="cta">
        <div className="wrap">
          <div className="flow-line reveal" aria-hidden />
          <p className="eyebrow reveal" style={{ marginBottom: 24 }}>
            [ Get Started ]
          </p>
          <h2 className="cta__title reveal">开始构建你的企业知识库。</h2>
          <div className="reveal" style={{ marginTop: 8 }}>
            <Pill href="/console">打开控制台</Pill>
          </div>
        </div>
      </section>

      {/* ===== Footer ===== */}
      <footer className="footer">
        <div className="wrap">
          <div className="footer__grid">
            <div className="footer__col footer__brand">
              <a className="brand" href="/">
                <span className="brand__mark" aria-hidden>
                  <svg viewBox="0 0 24 24" fill="none">
                    <circle cx="12" cy="12" r="6" stroke="currentColor" strokeWidth="1.4" />
                    <circle cx="18.5" cy="5.5" r="1.6" fill="currentColor" />
                    <path
                      d="M12 3a9 9 0 0 1 5 1.5"
                      stroke="currentColor"
                      strokeWidth="1.4"
                      strokeLinecap="round"
                    />
                  </svg>
                </span>
                <span className="brand__name">Enterprise RAG</span>
              </a>
              <p style={{ color: "var(--ash)", fontSize: "var(--text-body)" }}>
                企业级 RAG 智能问答平台
              </p>
            </div>

            <div className="footer__col">
              <span className="footer__head">Product</span>
              <a className="footer__link" href="/console">
                智能问答
              </a>
              <a className="footer__link" href="/knowledge">
                知识库管理
              </a>
              <a className="footer__link" href="#architecture">
                智能体编排
              </a>
            </div>

            <div className="footer__col">
              <span className="footer__head">Capabilities</span>
              <a className="footer__link" href="#capabilities">
                文档入库
              </a>
              <a className="footer__link" href="#capabilities">
                向量检索
              </a>
              <a className="footer__link" href="#capabilities">
                流式问答
              </a>
              <a className="footer__link" href="#capabilities">
                引用追溯
              </a>
            </div>

            <div className="footer__col">
              <span className="footer__head">Develop</span>
              <a className="footer__link" href="#capabilities">
                快速 / 思考模式
              </a>
              <a className="footer__link" href="#capabilities">
                本地降级
              </a>
              <a className="footer__link" href="#capabilities">
                会话记录
              </a>
              <a className="footer__link" href="/console">
                Swagger 文档
              </a>
            </div>

            <div className="footer__col">
              <span className="footer__head">Resources</span>
              <a className="footer__link" href="#architecture">
                架构概览
              </a>
              <a className="footer__link" href="#stack">
                技术栈
              </a>
              <a className="footer__link" href="/console">
                接口文档
              </a>
            </div>
          </div>

          <div className="footer__bottom">
            <span className="footer__copy">© 2026 · Enterprise RAG</span>
            <span className="footer__copy">Built with FastAPI · Next.js · Milvus</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

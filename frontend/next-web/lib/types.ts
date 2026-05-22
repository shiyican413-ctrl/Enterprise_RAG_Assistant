import type { Source } from "@/lib/api";

export type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
};

export const navItems = ["智能问答", "知识库", "会话记录", "权限审计"];

export const samplePrompts = [
  "报销多久可以打款？",
  "请假超过 5 天需要谁审批？",
  "系统如何保证回答可追溯？",
];

export const pipeline = [
  { label: "文档入库", text: "上传制度、手册、常见问题" },
  { label: "文本解析", text: "抽取正文并清洗格式" },
  { label: "片段切分", text: "生成可检索知识片段" },
  { label: "语义检索", text: "召回最相关证据来源" },
  { label: "溯源回答", text: "基于资料生成可信答案" },
];

export const productHighlights = [
  "前后端分离",
  "引用可追溯",
  "流式接口预留",
  "模型服务可替换",
];

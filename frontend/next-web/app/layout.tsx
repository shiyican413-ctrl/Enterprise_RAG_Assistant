import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "企业知识库智能问答平台",
  description: "面向企业知识库的智能问答与引用溯源控制台",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}

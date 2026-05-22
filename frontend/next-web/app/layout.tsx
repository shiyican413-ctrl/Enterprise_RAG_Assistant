import type { Metadata } from "next";
import { Inter, Noto_Sans_SC } from "next/font/google";
import { cn } from "@/lib/utils";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const notoSansSC = Noto_Sans_SC({ subsets: ["latin"], variable: "--font-noto-sans-sc" });

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
    <html lang="zh-CN" className={cn("font-sans", inter.variable, notoSansSC.variable)}>
      <body>{children}</body>
    </html>
  );
}

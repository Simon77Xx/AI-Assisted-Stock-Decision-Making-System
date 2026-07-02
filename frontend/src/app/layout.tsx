import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "股海秘籍 — 双均线策略回测",
  description:
    "A股双均线趋势策略回测工具 — MA5/MA20 金叉死叉 + MA60 趋势过滤器",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" className="h-full">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
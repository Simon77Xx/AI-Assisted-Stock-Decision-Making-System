"use client";

import { motion } from "framer-motion";

export function Navbar() {
  return (
    <motion.header
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
      className="sticky top-0 z-50 backdrop-blur-xl bg-white/80 border-b border-[rgb(229,229,234)]"
    >
      <div className="mx-auto max-w-[1280px] px-6 h-14 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-lg font-semibold tracking-tight text-[rgb(29,29,31)]">
            股海秘籍
          </span>
          <span className="hidden sm:inline text-xs text-[rgb(142,142,147)] font-medium tracking-wide uppercase">
            双均线趋势策略回测
          </span>
        </div>
        <div className="flex items-center gap-1">
          <a
            href="https://github.com/your-repo"
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-[rgb(142,142,147)] hover:text-[rgb(29,29,31)] transition-colors px-3 py-1.5 rounded-full hover:bg-[rgb(245,245,247)]"
          >
            GitHub
          </a>
        </div>
      </div>
    </motion.header>
  );
}
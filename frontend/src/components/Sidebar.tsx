"use client";

import { motion } from "framer-motion";
import type { BacktestParams } from "@/lib/api";

interface SidebarProps {
  params: BacktestParams;
  onChange: (params: BacktestParams) => void;
  onRun: () => void;
  loading: boolean;
}

export function Sidebar({ params, onChange, onRun, loading }: SidebarProps) {
  const update = <K extends keyof BacktestParams>(
    key: K,
    value: BacktestParams[K]
  ) => {
    onChange({ ...params, [key]: value });
  };

  return (
    <motion.aside
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.6, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
      className="w-full lg:w-[280px] shrink-0"
    >
      <div className="sticky top-20 bg-white rounded-2xl border border-[rgb(229,229,234)] p-6 shadow-sm">
        <h2 className="text-sm font-semibold text-[rgb(29,29,31)] mb-5">
          策略参数
        </h2>

        <div className="space-y-5">
          {/* 股票代码 */}
          <div>
            <label className="block text-xs font-medium text-[rgb(142,142,147)] mb-1.5 tracking-wide">
              股票代码
            </label>
            <input
              type="text"
              value={params.stockCode}
              onChange={(e) => update("stockCode", e.target.value)}
              placeholder="000001"
              className="w-full px-3 py-2 rounded-xl border border-[rgb(229,229,234)] bg-white text-sm text-[rgb(29,29,31)] placeholder:text-[rgb(199,199,204)] focus:outline-none focus:border-[rgb(0,113,227)] transition-colors"
            />
          </div>

          {/* 日期 */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-[rgb(142,142,147)] mb-1.5 tracking-wide">
                起始
              </label>
              <input
                type="date"
                value={params.startDate}
                onChange={(e) => update("startDate", e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-[rgb(229,229,234)] bg-white text-sm text-[rgb(29,29,31)] focus:outline-none focus:border-[rgb(0,113,227)] transition-colors"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-[rgb(142,142,147)] mb-1.5 tracking-wide">
                结束
              </label>
              <input
                type="date"
                value={params.endDate}
                onChange={(e) => update("endDate", e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-[rgb(229,229,234)] bg-white text-sm text-[rgb(29,29,31)] focus:outline-none focus:border-[rgb(0,113,227)] transition-colors"
              />
            </div>
          </div>

          {/* 均线参数 */}
          <div>
            <label className="block text-xs font-medium text-[rgb(142,142,147)] mb-1.5 tracking-wide">
              快线 MA
            </label>
            <div className="flex items-center gap-3">
              <input
                type="range"
                min={2}
                max={30}
                value={params.fastMA}
                onChange={(e) => update("fastMA", Number(e.target.value))}
                className="flex-1 accent-[rgb(0,113,227)] h-1"
              />
              <span className="text-sm font-semibold text-[rgb(29,29,31)] w-6 text-right">
                {params.fastMA}
              </span>
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-[rgb(142,142,147)] mb-1.5 tracking-wide">
              慢线 MA
            </label>
            <div className="flex items-center gap-3">
              <input
                type="range"
                min={10}
                max={120}
                value={params.slowMA}
                onChange={(e) => update("slowMA", Number(e.target.value))}
                className="flex-1 accent-[rgb(0,113,227)] h-1"
              />
              <span className="text-sm font-semibold text-[rgb(29,29,31)] w-6 text-right">
                {params.slowMA}
              </span>
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-[rgb(142,142,147)] mb-1.5 tracking-wide">
              趋势线 MA
            </label>
            <div className="flex items-center gap-3">
              <input
                type="range"
                min={20}
                max={250}
                value={params.trendMA}
                onChange={(e) => update("trendMA", Number(e.target.value))}
                className="flex-1 accent-[rgb(0,113,227)] h-1"
              />
              <span className="text-sm font-semibold text-[rgb(29,29,31)] w-6 text-right">
                {params.trendMA}
              </span>
            </div>
          </div>

          {/* 运行按钮 */}
          <button
            onClick={onRun}
            disabled={loading || !params.stockCode}
            className="w-full py-2.5 rounded-xl bg-[rgb(0,113,227)] text-white text-sm font-semibold hover:bg-[rgb(0,90,200)] disabled:opacity-50 disabled:cursor-not-allowed transition-all active:scale-[0.98]"
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <svg
                  className="animate-spin h-4 w-4"
                  viewBox="0 0 24 24"
                  fill="none"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                  />
                </svg>
                运行中...
              </span>
            ) : (
              "运行回测"
            )}
          </button>
        </div>
      </div>
    </motion.aside>
  );
}
"use client";

import { motion } from "framer-motion";
import { TrendingUp, TrendingDown, Minus, RefreshCw, BarChart3 } from "lucide-react";
import type { MarketOverviewResponse } from "@/lib/api";

interface MarketOverviewPanelProps {
  data: MarketOverviewResponse | null;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
  onSelectStock: (code: string) => void;
}

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.05 } },
};

const itemAnim = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0 },
};

function MarketStateBadge({ state }: { state: string }) {
  if (state === "bull")
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-[rgb(52,199,89)]/10 text-[rgb(52,199,89)] text-xs font-semibold">
        <TrendingUp className="w-3.5 h-3.5" /> 偏强
      </span>
    );
  if (state === "bear")
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-[rgb(255,59,48)]/10 text-[rgb(255,59,48)] text-xs font-semibold">
        <TrendingDown className="w-3.5 h-3.5" /> 偏弱
      </span>
    );
  return (
    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-[rgb(255,149,0)]/10 text-[rgb(180,95,0)] text-xs font-semibold">
      <Minus className="w-3.5 h-3.5" /> 震荡
    </span>
  );
}

function ScoreBar({ score }: { score: number }) {
  const color =
    score >= 70 ? "bg-[rgb(52,199,89)]" : score >= 45 ? "bg-[rgb(255,149,0)]" : "bg-[rgb(255,59,48)]";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-[rgb(229,229,234)] rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${score}%` }} />
      </div>
      <span className="text-xs font-semibold text-[rgb(29,29,31)] w-8 text-right">{score}</span>
    </div>
  );
}

function SuggestionBadge({ suggestion }: { suggestion: string }) {
  if (suggestion === "适合关注")
    return <span className="text-[10px] font-semibold text-[rgb(52,199,89)]">{suggestion}</span>;
  if (suggestion === "暂不建议" || suggestion === "观望为主")
    return <span className="text-[10px] font-semibold text-[rgb(255,149,0)]">{suggestion}</span>;
  return <span className="text-[10px] font-semibold text-[rgb(255,59,48)]">{suggestion}</span>;
}

export function MarketOverviewPanel({ data, loading, error, onRefresh, onSelectStock }: MarketOverviewPanelProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-[rgb(245,245,247)] rounded-2xl p-6 shadow-sm"
    >
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-5">
        <div className="flex items-center gap-3">
          <BarChart3 className="w-5 h-5 text-[rgb(0,113,227)]" />
          <div>
            <h3 className="text-sm font-semibold text-[rgb(29,29,31)]">AI 选股 · 市场概览</h3>
            <p className="text-xs text-[rgb(142,142,147)] mt-0.5">
              实时市场扫描 · 多股票评分排名 · 新手友好
            </p>
          </div>
        </div>
        <button
          onClick={onRefresh}
          disabled={loading}
          className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[rgb(0,113,227)] text-white text-xs font-semibold hover:bg-[rgb(0,90,200)] disabled:opacity-50 disabled:cursor-not-allowed transition-all active:scale-[0.98]"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          {loading ? "扫描中..." : "刷新市场"}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-[rgb(255,59,48)]/5 border border-[rgb(255,59,48)]/15 rounded-xl p-3 mb-4 text-xs text-[rgb(255,59,48)]">
          {error}
        </div>
      )}

      {/* Market State + Beginner Overview */}
      {data && (
        <>
          <div className="flex flex-wrap items-center gap-3 mb-5 bg-white rounded-xl border border-[rgb(229,229,234)] p-4">
            <MarketStateBadge state={data.market_state.state} />
            <span className="text-xs text-[rgb(110,110,115)]">
              {data.beginner_market_overview.market_mood}
            </span>
            <span className="text-xs text-[rgb(142,142,147)] ml-auto">
              上涨 {data.beginner_market_overview.rising_count}/{data.beginner_market_overview.total_count} ·{" "}
              {data.timestamp}
            </span>
          </div>

          {/* Top Stocks Ranking */}
          <div className="mb-2">
            <p className="text-[10px] font-medium text-[rgb(142,142,147)] tracking-wide uppercase mb-3">
              综合评分排行 TOP {data.top_stocks.length}
            </p>
          </div>

          <motion.div variants={container} initial="hidden" animate="show" className="space-y-2">
            {data.beginner_market_overview.recommended_stocks.map((stock, i) => (
              <motion.button
                key={stock.stock_code}
                variants={itemAnim}
                onClick={() => onSelectStock(stock.stock_code)}
                className="w-full text-left bg-white rounded-xl border border-[rgb(229,229,234)] px-4 py-3 hover:border-[rgb(0,113,227)]/30 hover:shadow-sm transition-all"
              >
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-bold text-[rgb(142,142,147)] w-4">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <span className="text-sm font-semibold text-[rgb(29,29,31)]">{stock.stock_name}</span>
                    <span className="text-[10px] text-[rgb(142,142,147)]">{stock.stock_code}</span>
                    {stock.change_pct != null && (
                      <span
                        className={`text-[10px] font-medium ${
                          stock.change_pct >= 0 ? "text-[rgb(52,199,89)]" : "text-[rgb(255,59,48)]"
                        }`}
                      >
                        {stock.change_pct >= 0 ? "+" : ""}
                        {(stock.change_pct * 100).toFixed(2)}%
                      </span>
                    )}
                  </div>
                  <SuggestionBadge suggestion={stock.suggestion} />
                </div>
                <div className="flex items-center gap-3 pl-6">
                  <ScoreBar score={stock.score} />
                  <span className="text-[10px] text-[rgb(142,142,147)] max-w-[180px] truncate">
                    {stock.reason}
                  </span>
                  {stock.risk_tip && (
                    <span className="text-[10px] text-[rgb(255,149,0)] shrink-0">
                      ⚠ {stock.risk_tip}
                    </span>
                  )}
                </div>
              </motion.button>
            ))}
          </motion.div>

          <div className="mt-4">
            <p className="text-[10px] text-[rgb(199,199,204)] leading-relaxed">
              评分基于趋势强度、成交量信号、波动调整收益、AI信心和动量的加权计算。
              数据快照 ID: {data.market_state.snapshot_id} · 点击任一股票查看深度分析。
            </p>
          </div>
        </>
      )}

      {!data && !loading && !error && (
        <div className="text-center py-10">
          <BarChart3 className="w-8 h-8 text-[rgb(199,199,204)] mx-auto mb-2" />
          <p className="text-xs text-[rgb(142,142,147)]">点击「刷新市场」开始扫描</p>
        </div>
      )}

      {loading && !data && (
        <div className="flex items-center justify-center py-10">
          <RefreshCw className="w-5 h-5 animate-spin text-[rgb(0,113,227)]" />
          <span className="ml-2 text-xs text-[rgb(110,110,115)]">正在获取实时市场数据...</span>
        </div>
      )}
    </motion.div>
  );
}
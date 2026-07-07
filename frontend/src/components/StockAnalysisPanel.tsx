"use client";

import { motion, AnimatePresence } from "framer-motion";
import {
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Sparkles,
  RefreshCw,
  BarChart3,
  ArrowLeft,
  Info,
  DollarSign,
  Target,
  ShieldOff,
  PieChart,
  BookOpen,
  Activity,
} from "lucide-react";
import type { StockAnalysisResponse, StockChartPoint, IndicatorSignal } from "@/lib/api";
import { useCallback, useState } from "react";
import { TrendChart } from "./TrendChart";

interface StockAnalysisPanelProps {
  data: StockAnalysisResponse | null;
  loading: boolean;
  error: string | null;
  stockCode: string | null;
  onBack: () => void;
  onRefresh: () => void;
  chartData: StockChartPoint[];
  chartLoading: boolean;
}

function DecisionBadge({ decision }: { decision: string }) {
  if (decision === "推荐")
    return (
      <span className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-[rgb(52,199,89)]/10 text-[rgb(52,199,89)] text-sm font-bold">
        <TrendingUp className="w-4 h-4" /> 适合关注
      </span>
    );
  if (decision === "观望")
    return (
      <span className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-[rgb(255,149,0)]/10 text-[rgb(180,95,0)] text-sm font-bold">
        <Info className="w-4 h-4" /> 暂不建议
      </span>
    );
  return (
    <span className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-[rgb(255,59,48)]/10 text-[rgb(255,59,48)] text-sm font-bold">
      <TrendingDown className="w-4 h-4" /> 高风险观望
    </span>
  );
}

function RiskBadge({ level }: { level: string }) {
  if (level === "Low")
    return <span className="text-[10px] font-semibold text-[rgb(52,199,89)]">风险较低</span>;
  if (level === "Medium")
    return <span className="text-[10px] font-semibold text-[rgb(255,149,0)]">风险中等</span>;
  return <span className="text-[10px] font-semibold text-[rgb(255,59,48)]">风险较高</span>;
}

function SubScoreRow({ label, value, max }: { label: string; value: number; max?: number }) {
  const pct = max ? (value / max) * 100 : value * 100;
  const color = pct >= 60 ? "bg-[rgb(52,199,89)]" : pct >= 35 ? "bg-[rgb(255,149,0)]" : "bg-[rgb(255,59,48)]";
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] text-[rgb(110,110,115)] w-24 shrink-0">{label}</span>
      <div className="flex-1 h-1.5 bg-[rgb(229,229,234)] rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[10px] font-medium text-[rgb(29,29,31)] w-8 text-right">
        {value.toFixed(2)}
      </span>
    </div>
  );
}

function MetricCell({ label, value, good, bad, neutral }: {
  label: string;
  value: string | number | null | undefined;
  good?: boolean;
  bad?: boolean;
  neutral?: boolean;
}) {
  if (value == null) return null;
  const color = good ? "text-[rgb(52,199,89)]" : bad ? "text-[rgb(255,59,48)]" : "text-[rgb(29,29,31)]";
  return (
    <div className="flex items-center justify-between bg-[rgb(245,245,247)] rounded-lg px-3 py-1.5">
      <span className="text-[10px] text-[rgb(142,142,147)]">{label}</span>
      <span className={`text-[11px] font-semibold ${color}`}>{value}</span>
    </div>
  );
}

export function StockAnalysisPanel({
  data,
  loading,
  error,
  stockCode,
  onBack,
  onRefresh,
  chartData,
  chartLoading,
}: StockAnalysisPanelProps) {
  const showPlaceholder = !data && !loading && !error;

  // ── Helper to extract optional fields safely ──
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const ai = data?.ai_recommendation as any;
  const hasEntryRange = ai && Array.isArray(ai.entry_price_range) && ai.entry_price_range.length === 2;
  const hasTargetPrice = ai && ai.target_price != null;
  const hasStopLoss = ai && ai.stop_loss_price != null;
  const hasPosition = ai && ai.position_suggestion;
  const hasFinancialSummary = ai && ai.financial_summary;
  const hasTradingPlan = ai && ai.trading_plan;

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const fin = data?.selected_stock_analysis?.financial_metrics as any;
  const hasFinData = fin && (fin.pe_ttm != null || fin.roe != null);

  // New 8-factor sub-scores
  const sub = data?.selected_stock_analysis?.sub_scores as Record<string, number> | undefined;

  const finItems: Array<{ label: string; value: string | number | null | undefined; good?: boolean; bad?: boolean }> = fin ? [
    { label: "PE/TTM", value: fin.pe_ttm, good: fin.pe_ttm != null && fin.pe_ttm > 0 && fin.pe_ttm < 20 },
    { label: "ROE", value: fin.roe != null ? `${Number(fin.roe).toFixed(1)}%` : undefined, good: fin.roe != null && fin.roe > 15 },
    { label: "净利率", value: fin.net_profit_margin != null ? `${Number(fin.net_profit_margin).toFixed(1)}%` : undefined, good: fin.net_profit_margin != null && fin.net_profit_margin > 15 },
    { label: "毛利率", value: fin.gross_margin != null ? `${Number(fin.gross_margin).toFixed(1)}%` : undefined, good: fin.gross_margin != null && fin.gross_margin > 30 },
    { label: "营收增长率", value: fin.revenue_growth != null ? `${Number(fin.revenue_growth).toFixed(1)}%` : undefined, good: fin.revenue_growth != null && fin.revenue_growth > 10 },
    { label: "净利润增长率", value: fin.net_profit_growth != null ? `${Number(fin.net_profit_growth).toFixed(1)}%` : undefined, good: fin.net_profit_growth != null && fin.net_profit_growth > 15 },
    { label: "资产负债率", value: fin.debt_ratio != null ? `${Number(fin.debt_ratio).toFixed(1)}%` : undefined, good: fin.debt_ratio != null && fin.debt_ratio < 50 },
    { label: "每股收益", value: fin.eps != null ? Number(fin.eps) : undefined },
  ] : [];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-[rgb(245,245,247)] rounded-2xl p-6 shadow-sm"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="p-1.5 rounded-lg hover:bg-[rgb(229,229,234)] transition-colors"
          >
            <ArrowLeft className="w-4 h-4 text-[rgb(142,142,147)]" />
          </button>
          <Sparkles className="w-5 h-5 text-[rgb(0,113,227)]" />
          <div>
            <h3 className="text-sm font-semibold text-[rgb(29,29,31)]">
              {data ? `${data.beginner_output.stock_summary.name}（${data.beginner_output.stock_summary.code}）` : stockCode || "AI 深度分析"}
            </h3>
            <p className="text-xs text-[rgb(142,142,147)] mt-0.5">
              8因子评分 · AI买卖建议 · 实盘接口
            </p>
          </div>
        </div>
        <button
          onClick={onRefresh}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-[rgb(0,113,227)] text-white text-xs font-semibold hover:bg-[rgb(0,90,200)] disabled:opacity-50 disabled:cursor-not-allowed transition-all active:scale-[0.98]"
        >
          <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} />
          分析
        </button>
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-10">
          <Sparkles className="w-5 h-5 animate-pulse text-[rgb(0,113,227)]" />
          <span className="ml-2 text-xs text-[rgb(110,110,115)]">AI正在分析（含财务数据）...</span>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-[rgb(255,59,48)]/5 border border-[rgb(255,59,48)]/15 rounded-xl p-3 mb-4 text-xs text-[rgb(255,59,48)]">
          {error}
        </div>
      )}

      {/* Placeholder */}
      {showPlaceholder && (
        <div className="text-center py-10">
          <BarChart3 className="w-8 h-8 text-[rgb(199,199,204)] mx-auto mb-2" />
          <p className="text-xs text-[rgb(142,142,147)]">
            从市场概览中选择一只股票，或点击分析按钮查看深度报告
          </p>
        </div>
      )}

      {/* Analysis Content */}
      <AnimatePresence>
        {data && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="space-y-4"
          >
            {/* ── Beginner Summary ── */}
            <div className="bg-white rounded-xl border border-[rgb(229,229,234)] p-4">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <p className="text-xs text-[rgb(142,142,147)] mb-1">AI决策</p>
                  <div className="flex items-center gap-2">
                    <DecisionBadge decision={data.ai_recommendation.decision} />
                    <span className="text-xs text-[rgb(110,110,115)]">
                      信心 {(data.ai_recommendation.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-lg font-bold text-[rgb(29,29,31)]">
                    {data.beginner_output.stock_summary.score}
                  </p>
                  <p className="text-[10px] text-[rgb(142,142,147)]">综合评分</p>
                </div>
              </div>

              <p className="text-xs text-[rgb(110,110,115)] leading-relaxed mb-3">
                {data.beginner_output.stock_summary.reason}
              </p>

              <div className="flex items-center gap-2">
                <RiskBadge level={data.ai_recommendation.risk_level} />
                <span className="text-[10px] text-[rgb(142,142,147)]">
                  {data.beginner_output.stock_summary.risk_tip}
                </span>
              </div>
            </div>

            {/* ── NEW: AI Trading Guidance ── */}
            {(hasEntryRange || hasTargetPrice || hasStopLoss || hasPosition) && (
              <div className="bg-white rounded-xl border border-[rgb(52,199,89)]/20 p-4">
                <p className="text-[10px] font-medium text-[rgb(52,199,89)] tracking-wide uppercase mb-3 flex items-center gap-1">
                  <DollarSign className="w-3 h-3" /> 操作参考
                </p>
                <div className="grid grid-cols-2 gap-2">
                  {hasEntryRange && (
                    <MetricCell
                      label="买入区间"
                      value={`¥${ai.entry_price_range[0].toFixed(2)} - ¥${ai.entry_price_range[1].toFixed(2)}`}
                      good
                    />
                  )}
                  {hasTargetPrice && (
                    <MetricCell
                      label="目标价"
                      value={`¥${ai.target_price.toFixed(2)}`}
                      good
                    />
                  )}
                  {hasStopLoss && (
                    <MetricCell
                      label="止损位"
                      value={`¥${ai.stop_loss_price.toFixed(2)}`}
                      bad
                    />
                  )}
                  {hasPosition && (
                    <MetricCell
                      label="建议仓位"
                      value={ai.position_suggestion}
                      good={ai.position_ratio != null && ai.position_ratio >= 0.5}
                      neutral
                    />
                  )}
                </div>
                {hasTradingPlan && (
                  <div className="mt-2 bg-[rgb(245,245,247)] rounded-lg px-3 py-2">
                    <p className="text-[10px] text-[rgb(142,142,147)] mb-1 flex items-center gap-1">
                      <BookOpen className="w-3 h-3" /> 操作计划
                    </p>
                    <p className="text-[10px] text-[rgb(110,110,115)] leading-relaxed">
                      {ai.trading_plan}
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* ── Trend Chart ── */}
            {chartLoading ? (
              <div className="bg-white rounded-xl border border-[rgb(229,229,234)] p-4 flex items-center justify-center h-[260px]">
                <RefreshCw className="w-4 h-4 animate-spin text-[rgb(0,113,227)]" />
                <span className="ml-2 text-xs text-[rgb(142,142,147)]">加载趋势数据...</span>
              </div>
            ) : chartData.length > 0 ? (
              <TrendChart
                data={chartData}
                stockName={data.beginner_output.stock_summary.name}
                height={260}
              />
            ) : null}

            {/* ── NEW: 8-Factor Sub Scores (Technical + Financial) ── */}
            <div className="bg-white rounded-xl border border-[rgb(229,229,234)] p-4">
              <p className="text-[10px] font-medium text-[rgb(142,142,147)] tracking-wide uppercase mb-3">
                8因子评分
              </p>
              <div className="space-y-2">
                <SubScoreRow label="趋势强度" value={sub?.trend_strength ?? data.selected_stock_analysis.sub_scores.trend_strength} />
                <SubScoreRow label="成交量信号" value={sub?.volume_signal ?? data.selected_stock_analysis.sub_scores.volume_signal} />
                <SubScoreRow label="波动调整收益" value={sub?.volatility_adjusted_return ?? data.selected_stock_analysis.sub_scores.volatility_adjusted_return} />
                <SubScoreRow label="AI信心" value={sub?.ai_confidence ?? data.selected_stock_analysis.sub_scores.ai_confidence} />
                <SubScoreRow label="动量评分" value={sub?.momentum_score ?? data.selected_stock_analysis.sub_scores.momentum_score} />
                {/* Financial sub-scores (new) */}
                {sub?.valuation_score != null && <SubScoreRow label="估值评分" value={sub.valuation_score} />}
                {sub?.profitability_score != null && <SubScoreRow label="盈利能力" value={sub.profitability_score} />}
                {sub?.growth_score != null && <SubScoreRow label="成长性" value={sub.growth_score} />}
              </div>
            </div>

            {/* ── NEW: Technical Indicator Signals ── */}
            {data.selected_stock_analysis.indicator_signals && (
              <div className="bg-white rounded-xl border border-[rgb(229,229,234)] p-4">
                <p className="text-[10px] font-medium text-[rgb(142,142,147)] tracking-wide uppercase mb-3 flex items-center gap-1">
                  <Activity className="w-3 h-3" /> 技术指标信号
                  {data.selected_stock_analysis.composite_indicator_score != null && (
                    <span className="ml-auto text-[rgb(0,113,227)]">
                      {(data.selected_stock_analysis.composite_indicator_score * 100).toFixed(0)}%
                    </span>
                  )}
                </p>
                <div className="space-y-1.5">
                  {(() => {
                    const indicators = data.selected_stock_analysis.indicator_signals as Record<string, IndicatorSignal>;
                    return Object.entries(indicators).map(([key, ind]) => {
                      const icons: Record<string, string> = { macd: "MACD", rsi: "RSI", bollinger: "BB", kdj: "KDJ", atr: "ATR" };
                      const label = icons[key] || key.toUpperCase();
                      const scorePct = (ind.score * 100).toFixed(0);
                      const color = ind.score >= 0.6 ? "text-[rgb(52,199,89)]" : ind.score <= 0.4 ? "text-[rgb(255,59,48)]" : "text-[rgb(255,149,0)]";
                      return (
                        <div key={key} className="bg-[rgb(245,245,247)] rounded-lg px-3 py-1.5">
                          <div className="flex items-center justify-between">
                            <span className="text-[10px] font-medium text-[rgb(29,29,31)]">{label}</span>
                            <span className={`text-[10px] font-semibold ${color}`}>
                              {ind.signal} · {scorePct}%
                            </span>
                          </div>
                          {key === "macd" && ind.value != null && (
                            <div className="flex flex-wrap gap-x-3 mt-0.5 text-[9px] text-[rgb(142,142,147)]">
                              {ind.value != null && <span>MACD: {Number(ind.value).toFixed(4)}</span>}
                              {ind.histogram != null && <span>柱: {Number(ind.histogram).toFixed(4)}</span>}
                            </div>
                          )}
                          {key === "rsi" && ind.value != null && (
                            <span className="text-[9px] text-[rgb(142,142,147)]">RSI: {Number(ind.value).toFixed(0)}</span>
                          )}
                          {key === "bollinger" && (
                            <span className="text-[9px] text-[rgb(142,142,147)]">
                              {ind.bb_pct != null && `BB%: ${(Number(ind.bb_pct) * 100).toFixed(1)}%`}
                              {ind.bb_width != null && ` 宽: ${Number(ind.bb_width).toFixed(3)}`}
                            </span>
                          )}
                          {key === "kdj" && (
                            <span className="text-[9px] text-[rgb(142,142,147)]">
                              K: {ind.K != null ? Number(ind.K).toFixed(1) : "-"}{" "}
                              D: {ind.D != null ? Number(ind.D).toFixed(1) : "-"}{" "}
                              J: {ind.J != null ? Number(ind.J).toFixed(1) : "-"}
                            </span>
                          )}
                          {key === "atr" && ind.atr_pct != null && (
                            <span className="text-[9px] text-[rgb(142,142,147)]">波动: {Number(ind.atr_pct).toFixed(1)}%</span>
                          )}
                        </div>
                      );
                    });
                  })()}
                </div>
              </div>
            )}

            {/* ── NEW: Financial Metrics ── */}
            {hasFinData && (
              <div className="bg-white rounded-xl border border-[rgb(229,229,234)] p-4">
                <p className="text-[10px] font-medium text-[rgb(142,142,147)] tracking-wide uppercase mb-3">
                  财务数据
                </p>
                <div className="space-y-1.5">
                  {finItems.map(item =>
                    item.value != null ? (
                      <MetricCell key={item.label} {...item} />
                    ) : null
                  )}
                </div>
              </div>
            )}

            {/* ── AI Reasoning ── */}
            <div className="bg-white rounded-xl border border-[rgb(229,229,234)] p-4">
              <p className="text-[10px] font-medium text-[rgb(142,142,147)] tracking-wide uppercase mb-2">
                AI 分析
              </p>
              <p className="text-xs text-[rgb(110,110,115)] leading-relaxed mb-3">
                {data.beginner_output.ai_thinking}
              </p>
              <p className="text-xs text-[rgb(110,110,115)] leading-relaxed">
                {data.ai_recommendation.reasoning}
              </p>
              {/* Financial summary from AI */}
              {hasFinancialSummary && (
                <div className="mt-2 bg-[rgb(245,245,247)] rounded-lg px-3 py-2">
                  <p className="text-[10px] text-[rgb(142,142,147)]">财务评价</p>
                  <p className="text-[10px] text-[rgb(110,110,115)] leading-relaxed">
                    {ai!.financial_summary as string}
                  </p>
                </div>
              )}
            </div>

            {/* ── Strategy vs AI Consistency ── */}
            <div
              className={`rounded-xl border p-4 ${
                data.strategy_ai_consistency.is_consistent
                  ? "bg-[rgb(52,199,89)]/5 border-[rgb(52,199,89)]/15"
                  : "bg-[rgb(255,149,0)]/5 border-[rgb(255,149,0)]/15"
              }`}
            >
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-bold text-[rgb(29,29,31)]">
                  策略 vs AI：{data.strategy_ai_consistency.is_consistent ? "一致" : "有分歧"}
                </span>
                <span className="text-[10px] text-[rgb(142,142,147)]">
                  策略信号「{data.strategy_ai_consistency.strategy_signal}」
                </span>
              </div>
              <p className="text-xs text-[rgb(110,110,115)] leading-relaxed">
                {data.beginner_output.strategy_vs_ai}
              </p>
            </div>

            {/* ── Alternatives ── */}
            {data.beginner_output.alternatives.length > 0 && (
              <div className="bg-white rounded-xl border border-[rgb(229,229,234)] p-4">
                <p className="text-[10px] font-medium text-[rgb(142,142,147)] tracking-wide uppercase mb-3">
                  替代推荐
                </p>
                <div className="space-y-2">
                  {data.beginner_output.alternatives.map((alt) => (
                    <div
                      key={alt.code}
                      className="flex items-center justify-between bg-[rgb(245,245,247)] rounded-lg px-3 py-2"
                    >
                      <div>
                        <span className="text-xs font-semibold text-[rgb(29,29,31)]">{alt.name}</span>
                        <span className="text-[10px] text-[rgb(142,142,147)] ml-1">{alt.code}</span>
                      </div>
                      <div className="text-right">
                        <span className="text-[10px] text-[rgb(110,110,115)]">{alt.suggestion}</span>
                        <span className="text-[10px] text-[rgb(142,142,147)] ml-2">评分 {alt.score}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* ── Risk Warning ── */}
            <div className="bg-[rgb(255,149,0)]/5 border border-[rgb(255,149,0)]/15 rounded-xl p-4">
              <div className="flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-[rgb(255,149,0)] shrink-0 mt-0.5" />
                <div>
                  <p className="text-[10px] font-semibold text-[rgb(180,95,0)] mb-1">风险提示</p>
                  <p className="text-[10px] text-[rgb(142,142,147)] leading-relaxed">
                    {data.beginner_output.risk_warning}
                  </p>
                  <p className="text-[10px] text-[rgb(199,199,204)] mt-1">
                    数据快照 ID: {data.risk_warning.data_snapshot_id} ·{" "}
                    {data.risk_warning.data_timestamp}
                  </p>
                </div>
              </div>
            </div>

            {/* ── Disclaimer ── */}
            <div className="bg-[rgb(245,245,247)] rounded-xl border border-[rgb(229,229,234)] p-3">
              <p className="text-[9px] text-[rgb(199,199,204)] leading-relaxed text-center">
                {data.risk_warning.disclaimer}—— AI仅提供参考意见，一切交易以个人决策为准。投资有风险，入市需谨慎。
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
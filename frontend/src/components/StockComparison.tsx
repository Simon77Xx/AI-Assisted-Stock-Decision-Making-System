"use client";

import { motion, AnimatePresence } from "framer-motion";
import {
  BarChart3,
  TrendingUp,
  TrendingDown,
  Minus,
  RefreshCw,
  ChevronDown,
  X,
  Sparkles,
  AlertTriangle,
  Info,
  ArrowUpRight,
  ArrowDownRight,
  Check,
} from "lucide-react";
import { useCallback, useMemo, useRef, useState } from "react";
import type { CompareStocksResponse, StockChartPoint, StockListItem } from "@/lib/api";
import { ComparisonTrendChart } from "./ComparisonTrendChart";
import { fetchStockChart } from "@/lib/api";

interface StockComparisonProps {
  compareResults: CompareStocksResponse | null;
  stockList: StockListItem[];
  selectedCodes: string[];
  onSelectStocks: (codes: string[]) => void;
  onCompare: () => void;
  onSelectStock: (code: string) => void;
  loading: boolean;
  error: string | null;
}

const STOCK_COLORS = [
  "#0071e3",
  "#ff9500",
  "#34c759",
  "#ff3b30",
  "#af52de",
  "#ff2d55",
];

// ── Sub-components ─────────────────────────────────────────────────────

function ValueCell({ value, suffix = "", positive, negative }: {
  value: string | number;
  suffix?: string;
  positive?: boolean;
  negative?: boolean;
}) {
  let color = "text-[rgb(29,29,31)]";
  if (positive) color = "text-[rgb(52,199,89)]";
  else if (negative) color = "text-[rgb(255,59,48)]";

  return (
    <span className={`text-sm font-semibold tabular-nums ${color}`}>
      {value}{suffix}
    </span>
  );
}

function ScoreBarMini({ score }: { score: number }) {
  const color =
    score >= 70 ? "bg-[rgb(52,199,89)]" :
    score >= 45 ? "bg-[rgb(255,149,0)]" :
    "bg-[rgb(255,59,48)]";
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 bg-[rgb(229,229,234)] rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${score}%` }} />
      </div>
      <span className="text-xs font-semibold tabular-nums text-[rgb(29,29,31)]">{score}</span>
    </div>
  );
}

function DecisionBadgeMini({ decision }: { decision: string }) {
  if (decision === "推荐")
    return <span className="text-xs font-bold text-[rgb(52,199,89)] bg-[rgb(52,199,89)]/10 px-2 py-0.5 rounded-md">推荐</span>;
  if (decision === "观望")
    return <span className="text-xs font-bold text-[rgb(255,149,0)] bg-[rgb(255,149,0)]/10 px-2 py-0.5 rounded-md">观望</span>;
  return <span className="text-xs font-bold text-[rgb(255,59,48)] bg-[rgb(255,59,48)]/10 px-2 py-0.5 rounded-md">不推荐</span>;
}

function RiskBadgeMini({ level }: { level: string }) {
  if (level === "Low")
    return <span className="text-[10px] font-semibold text-[rgb(52,199,89)]">低</span>;
  if (level === "Medium")
    return <span className="text-[10px] font-semibold text-[rgb(255,149,0)]">中</span>;
  return <span className="text-[10px] font-semibold text-[rgb(255,59,48)]">高</span>;
}

function SuggestionTag({ suggestion }: { suggestion: string }) {
  if (suggestion === "适合关注")
    return <span className="text-[10px] font-semibold text-[rgb(52,199,89)]">{suggestion}</span>;
  return <span className="text-[10px] font-semibold text-[rgb(255,149,0)]">{suggestion}</span>;
}

function SuggestionBadge({ suggestion }: { suggestion: string }) {
  if (suggestion === "适合关注")
    return <span className="text-xs font-bold text-[rgb(52,199,89)] bg-[rgb(52,199,89)]/10 px-2 py-0.5 rounded-md">适合关注</span>;
  if (suggestion === "观望为主")
    return <span className="text-xs font-bold text-[rgb(255,149,0)] bg-[rgb(255,149,0)]/10 px-2 py-0.5 rounded-md">观望为主</span>;
  return <span className="text-xs font-bold text-[rgb(255,59,48)] bg-[rgb(255,59,48)]/10 px-2 py-0.5 rounded-md">暂不建议</span>;
}

function ChangePct({ value }: { value: number | null | undefined }) {
  if (value == null) return <span className="text-xs text-[rgb(199,199,204)]">--</span>;
  const isPositive = value >= 0;
  const color = isPositive ? "text-[rgb(52,199,89)]" : "text-[rgb(255,59,48)]";
  return (
    <span className={`text-sm font-semibold tabular-nums ${color}`}>
      {isPositive ? "+" : ""}{(value * 100).toFixed(2)}%
    </span>
  );
}

function PriceDisplay({ price }: { price: number | null | undefined }) {
  if (price == null) return <span className="text-xs text-[rgb(199,199,204)]">--</span>;
  return <span className="text-sm font-semibold tabular-nums text-[rgb(29,29,31)]">{price.toFixed(2)}</span>;
}

// ── Multi-select Dropdown ──────────────────────────────────────────────

function MultiSelect({
  options,
  selected,
  onChange,
  disabled,
  maxSelections = 6,
  minSelections = 2,
}: {
  options: StockListItem[];
  selected: string[];
  onChange: (codes: string[]) => void;
  disabled: boolean;
  maxSelections?: number;
  minSelections?: number;
}) {
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const toggleStock = useCallback((code: string) => {
    if (selected.includes(code)) {
      onChange(selected.filter((c) => c !== code));
    } else {
      if (selected.length >= maxSelections) {
        onChange([...selected.slice(1), code]); // replace oldest
      } else {
        onChange([...selected, code]);
      }
    }
  }, [selected, onChange, maxSelections]);

  const selectedNames = useMemo(() => {
    return selected.map((code) => {
      const item = options.find((o) => o.code === code);
      return item ? `${item.name} (${code})` : code;
    }).join(", ");
  }, [selected, options]);

  // Close on outside click
  const ref = useRef<HTMLDivElement>(null);
  useMemo(() => {
    if (typeof window !== "undefined") {
      const handleClick = (e: MouseEvent) => {
        if (ref.current && !ref.current.contains(e.target as Node)) {
          setOpen(false);
        }
      };
      document.addEventListener("mousedown", handleClick);
      return () => document.removeEventListener("mousedown", handleClick);
    }
  }, []);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => !disabled && setOpen(!open)}
        disabled={disabled}
        className="w-full flex items-center justify-between px-4 py-2.5 rounded-xl bg-white border border-[rgb(229,229,234)] text-sm text-left text-[rgb(29,29,31)] hover:border-[rgb(0,113,227)]/30 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
      >
        <span className="truncate mr-2">
          {selected.length === 0 ? "选择要对比的股票（2-6只）" : selectedNames}
        </span>
        <ChevronDown className={`w-4 h-4 text-[rgb(142,142,147)] shrink-0 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className="absolute z-20 mt-1 w-full bg-white border border-[rgb(229,229,234)] rounded-xl shadow-lg overflow-hidden max-h-64 overflow-y-auto"
        >
          {options.map((stock) => {
            const isSelected = selected.includes(stock.code);
            const atMax = selected.length >= maxSelections;
            return (
              <button
                key={stock.code}
                onClick={() => toggleStock(stock.code)}
                disabled={disabled}
                className={`w-full flex items-center justify-between px-4 py-2.5 text-sm transition-colors ${
                  isSelected
                    ? "bg-[rgb(0,113,227)]/5 text-[rgb(0,113,227)]"
                    : "text-[rgb(110,110,115)] hover:bg-[rgb(245,245,247)]"
                } ${!isSelected && atMax ? "opacity-40" : ""}`}
              >
                <span className="font-medium">{stock.name}</span>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-[rgb(199,199,204)]">{stock.code}</span>
                  {isSelected && (
                    <Check className="w-3.5 h-3.5" />
                  )}
                </div>
              </button>
            );
          })}
        </motion.div>
      )}
    </div>
  );
}

// ── Main Component ─────────────────────────────────────────────────────

export function StockComparison({
  compareResults,
  stockList,
  selectedCodes,
  onSelectStocks,
  onCompare,
  onSelectStock,
  loading,
  error,
}: StockComparisonProps) {
  const canCompare = selectedCodes.length >= 2;

  // ── Comparison trend chart state ──
  const [trendDataMap, setTrendDataMap] = useState<Record<string, StockChartPoint[]>>({});
  const [trendLoading, setTrendLoading] = useState(false);
  const trendRequestLocked = useRef(false);

  const loadTrendComparison = useCallback(async () => {
    if (trendRequestLocked.current || selectedCodes.length < 2) return;
    trendRequestLocked.current = true;
    setTrendLoading(true);
    try {
      const results = await Promise.all(
        selectedCodes.map((code) => fetchStockChart(code, 365))
      );
      const map: Record<string, StockChartPoint[]> = {};
      for (const r of results) {
        map[r.stock_code] = r.chart_data;
      }
      setTrendDataMap(map);
    } catch {
      // Silently fail — chart area will show empty state
    } finally {
      setTrendLoading(false);
      trendRequestLocked.current = false;
    }
  }, [selectedCodes]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-[rgb(245,245,247)] rounded-2xl p-6 shadow-sm"
    >
      {/* Header */}
      <div className="flex items-center gap-3 mb-5">
        <BarChart3 className="w-5 h-5 text-[rgb(0,113,227)]" />
        <div>
          <h3 className="text-sm font-semibold text-[rgb(29,29,31)]">股票横向对比</h3>
          <p className="text-xs text-[rgb(142,142,147)] mt-0.5">
            多只股票各维度评分对比 · 横向比较表现高低
          </p>
        </div>
      </div>

      {/* Select Controls */}
      <div className="flex flex-col sm:flex-row gap-3 mb-4">
        <div className="flex-1">
          <MultiSelect
            options={stockList}
            selected={selectedCodes}
            onChange={onSelectStocks}
            disabled={loading}
          />
        </div>
        <button
          onClick={onCompare}
          disabled={!canCompare || loading}
          className="flex items-center justify-center gap-1.5 px-5 py-2.5 rounded-xl bg-[rgb(0,113,227)] text-white text-xs font-semibold hover:bg-[rgb(0,90,200)] disabled:opacity-50 disabled:cursor-not-allowed transition-all active:scale-[0.98] shrink-0"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          {loading ? "对比中..." : "对比分析"}
        </button>
      </div>

      {selectedCodes.length > 0 && selectedCodes.length < 2 && (
        <p className="text-[10px] text-[rgb(142,142,147)] mb-3">至少选择2只股票进行对比</p>
      )}

      {/* Error */}
      {error && (
        <div className="bg-[rgb(255,59,48)]/5 border border-[rgb(255,59,48)]/15 rounded-xl p-3 mb-4 text-xs text-[rgb(255,59,48)]">
          {error}
        </div>
      )}

      {/* Empty State */}
      {!compareResults && !loading && !error && (
        <div className="text-center py-10">
          <BarChart3 className="w-8 h-8 text-[rgb(199,199,204)] mx-auto mb-2" />
          <p className="text-xs text-[rgb(142,142,147)]">选择 2-6 只股票，点击「对比分析」查看横向对比结果</p>
        </div>
      )}

      {/* Loading (no data yet) */}
      {loading && !compareResults && (
        <div className="flex items-center justify-center py-10">
          <RefreshCw className="w-5 h-5 animate-spin text-[rgb(0,113,227)]" />
          <span className="ml-2 text-xs text-[rgb(110,110,115)]">正在获取各股票分析数据...</span>
        </div>
      )}

      {/* Comparison Results Table */}
      <AnimatePresence>
        {compareResults && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-4"
          >
            {/* Timestamp info */}
            <div className="flex items-center justify-between">
              <p className="text-[10px] text-[rgb(199,199,204)]">
                快照 ID: {compareResults.snapshot_id} · {compareResults.timestamp}
              </p>
              <button
                onClick={loadTrendComparison}
                disabled={trendLoading}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[rgb(245,245,247)] border border-[rgb(229,229,234)] text-[10px] font-semibold text-[rgb(0,113,227)] hover:bg-[rgb(0,113,227)]/5 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
              >
                <TrendingUp className={`w-3 h-3 ${trendLoading ? "animate-spin" : ""}`} />
                {trendLoading ? "加载中..." : "加载趋势对比"}
              </button>
            </div>

            {/* Responsive Table: Desktop = table, Mobile = cards */}
            {/* Desktop Table */}
            <div className="hidden md:block overflow-x-auto">
              <table className="w-full border-collapse">
                <thead>
                  <tr>
                    <th className="text-left text-[10px] font-medium text-[rgb(142,142,147)] tracking-wide uppercase pb-2 pr-4 w-28">
                      指标
                    </th>
                    {compareResults.stocks.map((stock) => (
                      <th key={stock.selected_stock_analysis.stock_code} className="pb-2 px-3 text-center">
                        <button
                          onClick={() => onSelectStock(stock.selected_stock_analysis.stock_code)}
                          className="group text-center hover:opacity-70 transition-opacity"
                        >
                          <p className="text-sm font-bold text-[rgb(29,29,31)] group-hover:text-[rgb(0,113,227)] transition-colors">
                            {stock.beginner_output.stock_summary.name}
                          </p>
                          <p className="text-[10px] text-[rgb(142,142,147)]">
                            {stock.selected_stock_analysis.stock_code}
                          </p>
                        </button>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {/* Score row */}
                  <tr className="border-t border-[rgb(229,229,234)]">
                    <td className="py-3 pr-4 text-xs font-medium text-[rgb(110,110,115)]">综合评分</td>
                    {compareResults.stocks.map((stock) => (
                      <td key={stock.selected_stock_analysis.stock_code} className="py-3 px-3 text-center">
                        <ScoreBarMini score={stock.selected_stock_analysis.score} />
                      </td>
                    ))}
                  </tr>

                  {/* Price row */}
                  <tr className="border-t border-[rgb(229,229,234)]">
                    <td className="py-3 pr-4 text-xs font-medium text-[rgb(110,110,115)]">最新价</td>
                    {compareResults.stocks.map((stock) => (
                      <td key={stock.selected_stock_analysis.stock_code} className="py-3 px-3 text-center">
                        <PriceDisplay price={stock.beginner_output.stock_summary.price} />
                      </td>
                    ))}
                  </tr>

                  {/* Change% row */}
                  <tr className="border-t border-[rgb(229,229,234)]">
                    <td className="py-3 pr-4 text-xs font-medium text-[rgb(110,110,115)]">涨跌幅</td>
                    {compareResults.stocks.map((stock) => (
                      <td key={stock.selected_stock_analysis.stock_code} className="py-3 px-3 text-center">
                        <ChangePct value={stock.beginner_output.stock_summary.change} />
                      </td>
                    ))}
                  </tr>

                  {/* Trend Strength */}
                  <tr className="border-t border-[rgb(229,229,234)]">
                    <td className="py-3 pr-4 text-xs font-medium text-[rgb(110,110,115)]">趋势强度</td>
                    {compareResults.stocks.map((stock) => {
                      const v = stock.selected_stock_analysis.sub_scores.trend_strength;
                      return (
                        <td key={stock.selected_stock_analysis.stock_code} className="py-3 px-3 text-center">
                          <ValueCell value={v.toFixed(3)} positive={v > 0.6} negative={v < 0.3} />
                        </td>
                      );
                    })}
                  </tr>

                  {/* Volume Signal */}
                  <tr className="border-t border-[rgb(229,229,234)]">
                    <td className="py-3 pr-4 text-xs font-medium text-[rgb(110,110,115)]">成交量信号</td>
                    {compareResults.stocks.map((stock) => {
                      const v = stock.selected_stock_analysis.sub_scores.volume_signal;
                      return (
                        <td key={stock.selected_stock_analysis.stock_code} className="py-3 px-3 text-center">
                          <ValueCell value={v.toFixed(3)} positive={v > 0.6} negative={v < 0.3} />
                        </td>
                      );
                    })}
                  </tr>

                  {/* Momentum */}
                  <tr className="border-t border-[rgb(229,229,234)]">
                    <td className="py-3 pr-4 text-xs font-medium text-[rgb(110,110,115)]">动量评分</td>
                    {compareResults.stocks.map((stock) => {
                      const v = stock.selected_stock_analysis.sub_scores.momentum_score;
                      return (
                        <td key={stock.selected_stock_analysis.stock_code} className="py-3 px-3 text-center">
                          <ValueCell value={v.toFixed(3)} positive={v > 0.6} negative={v < 0.3} />
                        </td>
                      );
                    })}
                  </tr>

                  {/* Volatility Adjusted Return */}
                  <tr className="border-t border-[rgb(229,229,234)]">
                    <td className="py-3 pr-4 text-xs font-medium text-[rgb(110,110,115)]">波动调整收益</td>
                    {compareResults.stocks.map((stock) => {
                      const v = stock.selected_stock_analysis.sub_scores.volatility_adjusted_return;
                      return (
                        <td key={stock.selected_stock_analysis.stock_code} className="py-3 px-3 text-center">
                          <ValueCell value={v.toFixed(3)} positive={v > 0.6} negative={v < 0.3} />
                        </td>
                      );
                    })}
                  </tr>

                  {/* AI Decision + Confidence */}
                  <tr className="border-t border-[rgb(229,229,234)]">
                    <td className="py-3 pr-4 text-xs font-medium text-[rgb(110,110,115)]">AI 研判</td>
                    {compareResults.stocks.map((stock) => (
                      <td key={stock.selected_stock_analysis.stock_code} className="py-3 px-3 text-center">
                        <div className="flex flex-col items-center gap-1">
                          <DecisionBadgeMini decision={stock.ai_recommendation.decision} />
                          <span className="text-[10px] text-[rgb(142,142,147)] tabular-nums">
                            信心 {(stock.ai_recommendation.confidence * 100).toFixed(0)}%
                          </span>
                        </div>
                      </td>
                    ))}
                  </tr>

                  {/* Risk Level */}
                  <tr className="border-t border-[rgb(229,229,234)]">
                    <td className="py-3 pr-4 text-xs font-medium text-[rgb(110,110,115)]">风险等级</td>
                    {compareResults.stocks.map((stock) => (
                      <td key={stock.selected_stock_analysis.stock_code} className="py-3 px-3 text-center">
                        <RiskBadgeMini level={stock.ai_recommendation.risk_level} />
                      </td>
                    ))}
                  </tr>

                  {/* Suggestion */}
                  <tr className="border-t border-[rgb(229,229,234)]">
                    <td className="py-3 pr-4 text-xs font-medium text-[rgb(110,110,115)]">新手建议</td>
                    {compareResults.stocks.map((stock) => (
                      <td key={stock.selected_stock_analysis.stock_code} className="py-3 px-3 text-center">
                        <SuggestionBadge suggestion={stock.beginner_output.stock_summary.suggestion} />
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>

            {/* Mobile: Card-based layout */}
            <div className="md:hidden space-y-3">
              {compareResults.stocks.map((stock) => {
                const s = stock.selected_stock_analysis;
                const b = stock.beginner_output;
                const a = stock.ai_recommendation;
                return (
                  <motion.button
                    key={s.stock_code}
                    onClick={() => onSelectStock(s.stock_code)}
                    className="w-full text-left bg-white rounded-xl border border-[rgb(229,229,234)] p-4 hover:border-[rgb(0,113,227)]/30 transition-all"
                  >
                    {/* Stock Header */}
                    <div className="flex items-center justify-between mb-3">
                      <div>
                        <p className="text-sm font-bold text-[rgb(29,29,31)]">{b.stock_summary.name}</p>
                        <p className="text-[10px] text-[rgb(142,142,147)]">{s.stock_code}</p>
                      </div>
                      <div className="text-right">
                        <SuggestionBadge suggestion={b.stock_summary.suggestion} />
                      </div>
                    </div>

                    {/* Score + Price row */}
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] text-[rgb(142,142,147)]">评分</span>
                        <ScoreBarMini score={s.score} />
                      </div>
                      <PriceDisplay price={b.stock_summary.price} />
                    </div>

                    {/* Metrics grid */}
                    <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
                      <div className="flex justify-between">
                        <span className="text-[rgb(142,142,147)]">涨跌幅</span>
                        <ChangePct value={b.stock_summary.change} />
                      </div>
                      <div className="flex justify-between">
                        <span className="text-[rgb(142,142,147)]">趋势</span>
                        <ValueCell value={s.sub_scores.trend_strength.toFixed(3)} positive={s.sub_scores.trend_strength > 0.6} negative={s.sub_scores.trend_strength < 0.3} />
                      </div>
                      <div className="flex justify-between">
                        <span className="text-[rgb(142,142,147)]">动量</span>
                        <ValueCell value={s.sub_scores.momentum_score.toFixed(3)} positive={s.sub_scores.momentum_score > 0.6} negative={s.sub_scores.momentum_score < 0.3} />
                      </div>
                      <div className="flex justify-between">
                        <span className="text-[rgb(142,142,147)]">AI 研判</span>
                        <DecisionBadgeMini decision={a.decision} />
                      </div>
                      <div className="flex justify-between">
                        <span className="text-[rgb(142,142,147)]">风险</span>
                        <RiskBadgeMini level={a.risk_level} />
                      </div>
                      <div className="flex justify-between">
                        <span className="text-[rgb(142,142,147)]">信心</span>
                        <span className="font-semibold tabular-nums">{(a.confidence * 100).toFixed(0)}%</span>
                      </div>
                    </div>

                    {/* AI Reasoning */}
                    <p className="text-[10px] text-[rgb(142,142,147)] mt-2 leading-relaxed line-clamp-2">
                      {a.reasoning}
                    </p>
                  </motion.button>
                );
              })}
            </div>

            {/* Comparison Trend Overlay Chart */}
            <div className="pt-2">
              <ComparisonTrendChart
                series={compareResults.stocks.map((stock, i) => ({
                  code: stock.selected_stock_analysis.stock_code,
                  name: stock.beginner_output.stock_summary.name,
                  color: STOCK_COLORS[i % STOCK_COLORS.length],
                }))}
                dataMap={trendDataMap}
              />
            </div>

            {/* Bottom info */}
            <div className="pt-2">
              <p className="text-[10px] text-[rgb(199,199,204)] leading-relaxed">
                点击股票名称进入深度分析。评分基于趋势强度、成交量信号、波动调整收益、AI信心和动量的加权计算。
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
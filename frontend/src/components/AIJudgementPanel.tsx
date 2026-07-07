"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Sparkles, Loader2, AlertCircle } from "lucide-react";
import {
  fetchAIJudgement,
  type AIJudgementRequest,
  type AIResult,
  type BacktestParams,
  type BacktestResult,
} from "@/lib/api";

interface AIJudgementPanelProps {
  backtestResult: BacktestResult | null;
  params: BacktestParams;
  disabled: boolean;
  disabledReason: string;
}

type SignalTone = "positive" | "negative" | "neutral";

function getJudgmentColor(judgment: string) {
  switch (judgment) {
    case "看多":
      return { text: "text-[rgb(52,199,89)]", bg: "bg-[rgb(52,199,89)]/10", border: "border-[rgb(52,199,89)]/20" };
    case "看空":
      return { text: "text-[rgb(255,59,48)]", bg: "bg-[rgb(255,59,48)]/10", border: "border-[rgb(255,59,48)]/20" };
    default:
      return { text: "text-[rgb(255,149,0)]", bg: "bg-[rgb(255,149,0)]/10", border: "border-[rgb(255,149,0)]/20" };
  }
}

function signalTone(value: string): SignalTone {
  if (["买入", "看多"].includes(value)) return "positive";
  if (["卖出", "看空", "空仓"].includes(value)) return "negative";
  return "neutral";
}

function toneClass(tone: SignalTone) {
  if (tone === "positive") return "bg-[rgb(52,199,89)]/10 text-[rgb(52,199,89)] border-[rgb(52,199,89)]/20";
  if (tone === "negative") return "bg-[rgb(255,59,48)]/10 text-[rgb(255,59,48)] border-[rgb(255,59,48)]/20";
  return "bg-[rgb(255,149,0)]/10 text-[rgb(180,95,0)] border-[rgb(255,149,0)]/20";
}

function normalizeStrategy(signal: string) {
  if (signal === "买入") return "看多";
  if (signal === "卖出") return "看空";
  return "中性";
}

function getConfidenceDots(confidence: string) {
  if (confidence === "高") return "●●●";
  if (confidence === "中") return "●●○";
  return "●○○";
}

export function AIJudgementPanel({ backtestResult, params, disabled, disabledReason }: AIJudgementPanelProps) {
  const [result, setResult] = useState<AIResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestLocked = useRef(false);
  const lastRequestedVersion = useRef<string | null>(null);

  // Reset state when backtest result changes (new version)
  useEffect(() => {
    lastRequestedVersion.current = null;
    setResult(null);
    setError(null);
  }, [backtestResult]);

  const runAIJudgement = useCallback(async () => {
    if (disabled || !backtestResult || requestLocked.current) return;

    // Prevent duplicate requests for the same version
    if (backtestResult.backtestVersion === lastRequestedVersion.current) return;
    lastRequestedVersion.current = backtestResult.backtestVersion;

    requestLocked.current = true;
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      // Send minimal request — indicators loaded from server-side snapshot by version
      const request: AIJudgementRequest = {
        stock_code: params.stockCode,
        backtest_version: backtestResult.backtestVersion,
      };
      const data = await fetchAIJudgement(request);
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "AI研判请求失败");
    } finally {
      setLoading(false);
      requestLocked.current = false;
    }
  }, [backtestResult, params, disabled]);

  const judgmentColor = result ? getJudgmentColor(result.judgment) : null;
  const buttonDisabled = disabled || loading || !backtestResult;

  const snapshot = backtestResult?.snapshot;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, delay: 0.4, ease: [0.16, 1, 0.3, 1] }}
      className="bg-[rgb(245,245,247)] rounded-2xl p-6 shadow-sm"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-[rgb(29,29,31)] mb-1">AI 辅助研判</h3>
          <p className="text-xs text-[rgb(142,142,147)]">
            分析基于 {backtestResult ? `${backtestResult.backtestTimestamp} 最近一次回测结果，Version #${backtestResult.backtestVersion}` : "最近一次成功回测结果"}。
          </p>
        </div>
        <button
          onClick={runAIJudgement}
          disabled={buttonDisabled}
          className="flex min-w-[150px] items-center justify-center gap-1.5 px-4 py-2 rounded-xl bg-[rgb(0,113,227)] text-white text-xs font-semibold hover:bg-[rgb(0,90,200)] disabled:opacity-50 disabled:cursor-not-allowed transition-all active:scale-[0.98]"
        >
          {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
          {loading ? "AI正在分析..." : buttonDisabled ? disabledReason : "AI 研判"}
        </button>
      </div>

      {loading && (
        <div className="flex items-center gap-2 bg-white border border-[rgb(229,229,234)] rounded-xl p-3 mb-4">
          <Loader2 className="w-4 h-4 animate-spin text-[rgb(0,113,227)]" />
          <p className="text-xs text-[rgb(110,110,115)]">AI正在分析最近一次回测结果...</p>
        </div>
      )}

      {snapshot && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-4">
          {[
            { label: "当前价格", value: snapshot.current_price.toFixed(2) },
            { label: "MA5/MA20", value: `${snapshot.ma5?.toFixed(1) ?? "N/A"}/${snapshot.ma20?.toFixed(1) ?? "N/A"}` },
            { label: "均线状态", value: snapshot.ma_cross_status },
            { label: "趋势判定", value: snapshot.trend_filter_status },
          ].map((item) => (
            <div key={item.label} className="bg-white rounded-xl border border-[rgb(229,229,234)] px-3 py-2">
              <p className="text-[10px] text-[rgb(142,142,147)] tracking-wide uppercase">{item.label}</p>
              <p className="text-xs font-semibold text-[rgb(29,29,31)] mt-0.5">{item.value}</p>
            </div>
          ))}
        </div>
      )}

      {snapshot?.insufficient_data && (
        <div className="bg-[rgb(255,149,0)]/10 border border-[rgb(255,149,0)]/20 rounded-2xl p-3 mb-4 text-xs text-[rgb(180,95,0)]">
          数据不足：以下均线指标无法计算：{snapshot.missing_indicators.join("、")}
        </div>
      )}

      {snapshot && (
        <div className="grid grid-cols-2 gap-2 mb-3">
          <div className="bg-white rounded-xl border border-[rgb(229,229,234)] px-3 py-2">
            <p className="text-[10px] text-[rgb(142,142,147)] tracking-wide uppercase">持仓状态</p>
            <p className="text-xs font-semibold text-[rgb(29,29,31)] mt-0.5">{snapshot.position_state}（{snapshot.holding_days}天）</p>
          </div>
          <div className="bg-white rounded-xl border border-[rgb(229,229,234)] px-3 py-2">
            <p className="text-[10px] text-[rgb(142,142,147)] tracking-wide uppercase">量比</p>
            <p className="text-xs font-semibold text-[rgb(29,29,31)] mt-0.5">{snapshot.volume_ratio.toFixed(2)}</p>
          </div>
        </div>
      )}

      {error && (
        <div className="flex items-start gap-2 bg-[rgb(255,59,48)]/5 border border-[rgb(255,59,48)]/15 rounded-xl p-3 mb-3">
          <AlertCircle className="w-4 h-4 text-[rgb(255,59,48)] shrink-0 mt-0.5" />
          <p className="text-xs text-[rgb(255,59,48)]">{error}</p>
        </div>
      )}

      <AnimatePresence>
        {result && judgmentColor && backtestResult && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
            className="overflow-hidden"
          >
            <div className="bg-white rounded-xl border border-[rgb(229,229,234)] p-4">
              {result.cached && (
                <p className="text-[10px] text-[rgb(142,142,147)] mb-3">
                  使用缓存结果{typeof result.cacheAgeSeconds === "number" ? `（${result.cacheAgeSeconds}秒前）` : ""}。
                </p>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
                <div className={`rounded-xl border px-3 py-2 ${toneClass(signalTone(backtestResult.currentSignal))}`}>
                  <p className="text-[10px] font-medium opacity-80">当前策略信号</p>
                  <p className="text-sm font-bold mt-0.5">{backtestResult.currentSignal}</p>
                </div>
                <div className={`rounded-xl border px-3 py-2 ${toneClass(signalTone(result.judgment))}`}>
                  <p className="text-[10px] font-medium opacity-80">AI观点</p>
                  <p className="text-sm font-bold mt-0.5">{result.judgment}</p>
                </div>
              </div>

              {/* Strategy alignment display — from AI response */}
              {result.strategy_alignment && (
                <div
                  className={`rounded-xl border px-3 py-2 mb-4 ${
                    result.strategy_alignment === "一致"
                      ? "bg-[rgb(52,199,89)]/8 text-[rgb(36,138,61)] border-[rgb(52,199,89)]/20"
                      : "bg-[rgb(255,149,0)]/10 text-[rgb(180,95,0)] border-[rgb(255,149,0)]/20"
                  }`}
                >
                  <p className="text-xs font-bold">Signal Comparison：{result.strategy_alignment}</p>
                  {result.explanation && (
                    <p className="text-xs mt-1 leading-relaxed">{result.explanation}</p>
                  )}
                </div>
              )}
              {/* Fallback for cached responses without strategy_alignment */}
              {!result.strategy_alignment && backtestResult && (
                <ComparisonFallback strategySignal={backtestResult.currentSignal} aiJudgment={result.judgment} />
              )}

              <div className="flex items-center gap-3 mb-4">
                <div className={`px-3 py-1 rounded-lg ${judgmentColor.bg} ${judgmentColor.text} text-sm font-bold`}>
                  {result.judgment}
                </div>
                <div className="text-xs text-[rgb(142,142,147)]">
                  置信度：{result.confidence}
                  <span className="ml-1 tracking-wider">{getConfidenceDots(result.confidence)}</span>
                </div>
              </div>

              <div className="space-y-2 mb-3">
                <p className="text-[10px] font-medium text-[rgb(142,142,147)] tracking-wide uppercase">研判依据</p>
                {result.reasons.map((reason, i) => (
                  <div key={`${reason}-${i}`} className="flex items-start gap-2">
                    <span className="text-[rgb(0,113,227)] text-xs mt-0.5">·</span>
                    <p className="text-xs text-[rgb(110,110,115)] leading-relaxed">{reason}</p>
                  </div>
                ))}
              </div>

              <p className="text-[10px] text-[rgb(199,199,204)] leading-relaxed italic">{result.risk_note}</p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {!result && !error && !loading && (
        <div className="text-center py-3">
          <p className="text-xs text-[rgb(199,199,204)]">
            {buttonDisabled ? disabledReason : "点击 AI 研判，获取基于最近一次成功回测的辅助分析"}
          </p>
        </div>
      )}
    </motion.div>
  );
}

/** Fallback comparison display for cached responses without strategy_alignment. */
function ComparisonFallback({ strategySignal, aiJudgment }: { strategySignal: string; aiJudgment: string }) {
  const matched = normalizeStrategy(strategySignal) === aiJudgment;
  return (
    <div
      className={`rounded-xl border px-3 py-2 mb-4 ${
        matched
          ? "bg-[rgb(52,199,89)]/8 text-[rgb(36,138,61)] border-[rgb(52,199,89)]/20"
          : "bg-[rgb(255,149,0)]/10 text-[rgb(180,95,0)] border-[rgb(255,149,0)]/20"
      }`}
    >
      <p className="text-xs font-bold">Signal Comparison：{matched ? "一致" : "存在分歧"}</p>
      <p className="text-xs mt-1 leading-relaxed">
        {matched
          ? "机械策略与AI判断一致，可继续按既定规则观察。"
          : "AI观点与当前均线策略不同，建议结合机械信号继续观察，避免把AI观点误认为策略信号。"}
      </p>
    </div>
  );
}
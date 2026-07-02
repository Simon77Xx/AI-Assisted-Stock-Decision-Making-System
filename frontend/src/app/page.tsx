"use client";

import { useCallback, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Navbar } from "@/components/Navbar";
import { Sidebar } from "@/components/Sidebar";
import { MetricCard } from "@/components/MetricCard";
import { EquityCurve } from "@/components/EquityCurve";
import { CandlestickChart } from "@/components/CandlestickChart";
import { AIJudgementPanel } from "@/components/AIJudgementPanel";
import { fetchBacktest, type BacktestParams, type BacktestResult } from "@/lib/api";

const DEFAULT_PARAMS: BacktestParams = {
  stockCode: "000001",
  startDate: "2023-01-01",
  endDate: "2024-12-31",
  fastMA: 5,
  slowMA: 20,
  trendMA: 60,
};

function paramsKey(params: BacktestParams) {
  return [params.stockCode, params.startDate, params.endDate, params.fastMA, params.slowMA, params.trendMA].join("|");
}

export default function Home() {
  const [params, setParams] = useState<BacktestParams>(DEFAULT_PARAMS);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [completedParamsKey, setCompletedParamsKey] = useState<string | null>(null);

  const currentParamsKey = useMemo(() => paramsKey(params), [params]);
  const backtestStale = Boolean(result && completedParamsKey !== currentParamsKey);

  const updateParams = useCallback((next: BacktestParams) => {
    setParams(next);
    setError(null);
  }, []);

  const runBacktest = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchBacktest(params);
      setResult(data);
      setCompletedParamsKey(paramsKey(params));
    } catch (e) {
      setError(e instanceof Error ? e.message : "回测运行失败");
      setResult(null);
      setCompletedParamsKey(null);
    } finally {
      setLoading(false);
    }
  }, [params]);

  const aiDisabled = loading || !result || backtestStale;
  const aiDisabledReason = loading || backtestStale ? "等待回测完成..." : !result ? "请先运行回测" : "AI 研判";

  return (
    <>
      <Navbar />

      <section className="border-b border-[rgb(229,229,234)] bg-[rgb(245,245,247)]">
        <div className="mx-auto max-w-[1280px] px-6 py-16 sm:py-20 lg:py-24">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
            className="max-w-2xl"
          >
            <motion.span
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.1 }}
              className="inline-block text-xs font-semibold text-[rgb(0,113,227)] tracking-widest uppercase mb-4"
            >
              A股趋势策略回测
            </motion.span>
            <motion.h1
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.2 }}
              className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight text-[rgb(29,29,31)] leading-[1.08]"
            >
              双均线策略
              <br />
              <span className="text-[rgb(142,142,147)]">趋势过滤</span>
            </motion.h1>
            <motion.p
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.35 }}
              className="mt-5 text-base sm:text-lg text-[rgb(110,110,115)] leading-relaxed max-w-xl"
            >
              MA5 / MA20 金叉死叉信号 + MA60 趋势市判断，T+1 日执行。AI 分析只基于最近一次成功完成的回测结果。
            </motion.p>
          </motion.div>
        </div>
      </section>

      <main className="mx-auto max-w-[1280px] px-6 py-10 flex-1">
        <div className="flex flex-col lg:flex-row gap-8">
          <Sidebar params={params} onChange={updateParams} onRun={runBacktest} loading={loading} />

          <div className="flex-1 min-w-0">
            {error && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-red-50 border border-red-100 rounded-2xl p-4 mb-6 text-sm text-red-600"
              >
                {error}
              </motion.div>
            )}

            {backtestStale && (
              <div className="bg-[rgb(255,149,0)]/10 border border-[rgb(255,149,0)]/20 rounded-2xl p-4 mb-6 text-sm text-[rgb(180,95,0)]">
                参数已修改，当前展示仍为最近一次成功回测结果。请重新运行回测后再进行 AI 分析。
              </div>
            )}

            {!result && !loading && !error && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.6, delay: 0.3 }}
                className="flex flex-col items-center justify-center py-20 text-center"
              >
                <div className="w-16 h-16 rounded-full bg-[rgb(245,245,247)] flex items-center justify-center mb-4">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="rgb(142,142,147)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
                  </svg>
                </div>
                <h3 className="text-sm font-semibold text-[rgb(29,29,31)] mb-1">等待回测</h3>
                <p className="text-xs text-[rgb(142,142,147)] max-w-xs">
                  在左侧输入股票代码和参数，点击「运行回测」查看结果。
                </p>
              </motion.div>
            )}

            {loading && (
              <div className="flex flex-col items-center justify-center py-20">
                <svg className="animate-spin h-8 w-8 text-[rgb(0,113,227)] mb-4" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                <p className="text-sm text-[rgb(142,142,147)]">正在获取数据并运行回测...</p>
              </div>
            )}

            {result && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.5 }} className="space-y-6">
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
                  {Object.entries(result.metrics).map(([key, value], i) => (
                    <MetricCard key={key} label={key} value={String(value)} delay={i} />
                  ))}
                </div>

                {result.dataWarnings?.map((warning) => (
                  <div key={warning} className="bg-[rgb(255,149,0)]/10 border border-[rgb(255,149,0)]/20 rounded-2xl p-4 text-sm text-[rgb(180,95,0)]">
                    {warning}
                  </div>
                ))}

                <CandlestickChart
                  data={result.chart_data.slice(-365).map((d) => ({
                    date: d.date,
                    open: d.close,
                    close: d.close,
                    high: d.close,
                    low: d.close,
                    ma5: d.MA5,
                    ma20: d.MA20,
                    ma60: d.MA60,
                  }))}
                />

                <EquityCurve data={result.chart_data} />

                <AIJudgementPanel
                  backtestResult={result}
                  params={params}
                  disabled={aiDisabled}
                  disabledReason={aiDisabledReason}
                />

                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.6, delay: 0.5, ease: [0.16, 1, 0.3, 1] }}
                  className="bg-[rgb(245,245,247)] rounded-2xl p-6"
                >
                  <h3 className="text-sm font-semibold text-[rgb(29,29,31)] mb-3">策略说明</h3>
                  <ul className="space-y-2 text-sm text-[rgb(110,110,115)]">
                    <li>双均线策略：MA{params.fastMA} 上穿 MA{params.slowMA} 且处于趋势市时买入，下穿时卖出。</li>
                    <li>趋势过滤：收盘价在 MA{params.trendMA} 上方时视为趋势市，非趋势市空仓。</li>
                    <li>T+1 执行：信号在 T 日收盘后生成，T+1 日执行。</li>
                    <li>AI 研判：仅分析最近一次成功完成回测产生的数据，不等同于机械策略。</li>
                  </ul>
                </motion.div>
              </motion.div>
            )}
          </div>
        </div>
      </main>

      <footer className="border-t border-[rgb(229,229,234)] mt-12">
        <div className="mx-auto max-w-[1280px] px-6 py-8 flex items-center justify-between">
          <p className="text-xs text-[rgb(142,142,147)]">仅供学习参考，不构成投资建议。</p>
          <p className="text-xs text-[rgb(199,199,204)]">Built with Next.js + FastAPI + Python</p>
        </div>
      </footer>
    </>
  );
}

"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Navbar } from "@/components/Navbar";
import { StockComparison } from "@/components/StockComparison";
import { Sidebar } from "@/components/Sidebar";
import { MetricCard } from "@/components/MetricCard";
import { EquityCurve } from "@/components/EquityCurve";
import { CandlestickChart } from "@/components/CandlestickChart";
import { AIJudgementPanel } from "@/components/AIJudgementPanel";
import { MarketOverviewPanel } from "@/components/MarketOverviewPanel";
import { StockAnalysisPanel } from "@/components/StockAnalysisPanel";
import { TradingPanel } from "@/components/TradingPanel";
import { PortfolioBacktestPanel } from "@/components/PortfolioBacktestPanel";
import {
  fetchBacktest,
  fetchMarketOverview,
  fetchStockAnalysis,
  fetchStockList,
  fetchCompareStocks,
  fetchStockChart,
  type BacktestParams,
  type BacktestResult,
  type MarketOverviewResponse,
  type StockAnalysisResponse,
  type CompareStocksResponse,
  type StockListItem,
  type StockChartPoint,
} from "@/lib/api";

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
  // ── Backtest state ──
  const [params, setParams] = useState<BacktestParams>(DEFAULT_PARAMS);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [completedParamsKey, setCompletedParamsKey] = useState<string | null>(null);

  const currentParamsKey = useMemo(() => paramsKey(params), [params]);
  const backtestStale = Boolean(result && completedParamsKey !== currentParamsKey);

  // ── AI Advisor state ──
  const [marketData, setMarketData] = useState<MarketOverviewResponse | null>(null);
  const [marketLoading, setMarketLoading] = useState(false);
  const [marketError, setMarketError] = useState<string | null>(null);
  const requestLocked = useRef(false);

  const [analysisData, setAnalysisData] = useState<StockAnalysisResponse | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [selectedStock, setSelectedStock] = useState<string | null>(null);
  const [selectedStockName, setSelectedStockName] = useState<string | null>(null);
  const analysisRequestLocked = useRef(false);

  // ── Stock chart state ──
  const [stockChartData, setStockChartData] = useState<StockChartPoint[]>([]);
  const [chartLoading, setChartLoading] = useState(false);
  const compareRequestLocked = useRef(false);

  // ── Comparison state ──
  const [compareData, setCompareData] = useState<CompareStocksResponse | null>(null);
  const [compareLoading, setCompareLoading] = useState(false);
  const [compareError, setCompareError] = useState<string | null>(null);
  const [selectedCompareCodes, setSelectedCompareCodes] = useState<string[]>(["000001", "600519", "000333"]);
  const [stockList, setStockList] = useState<StockListItem[]>([]);

  // ── Backtest handlers ──
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

  // ── AI Advisor handlers ──
  const runMarketOverview = useCallback(async () => {
    if (requestLocked.current) return;
    requestLocked.current = true;
    setMarketLoading(true);
    setMarketError(null);
    try {
      const data = await fetchMarketOverview(false);
      setMarketData(data);
    } catch (e) {
      setMarketError(e instanceof Error ? e.message : "市场数据获取失败");
    } finally {
      setMarketLoading(false);
      requestLocked.current = false;
    }
  }, []);

  const refreshMarket = useCallback(async () => {
    if (requestLocked.current) return;
    requestLocked.current = true;
    setMarketLoading(true);
    setMarketError(null);
    try {
      const data = await fetchMarketOverview(true);
      setMarketData(data);
    } catch (e) {
      setMarketError(e instanceof Error ? e.message : "市场数据刷新失败");
    } finally {
      setMarketLoading(false);
      requestLocked.current = false;
    }
  }, []);

  const selectStock = useCallback(async (code: string) => {
    if (analysisRequestLocked.current) return;
    analysisRequestLocked.current = true;
    setSelectedStock(code);
    setSelectedStockName(null);
    setAnalysisLoading(true);
    setAnalysisError(null);
    setAnalysisData(null);
    setStockChartData([]);
    try {
      const [analysis, chart] = await Promise.all([
        fetchStockAnalysis(code, false),
        fetchStockChart(code, 365),
      ]);
      setAnalysisData(analysis);
      setSelectedStockName(analysis.beginner_output.stock_summary.name);
      setStockChartData(chart.chart_data);
    } catch (e) {
      setAnalysisError(e instanceof Error ? e.message : "股票分析失败");
    } finally {
      setAnalysisLoading(false);
      analysisRequestLocked.current = false;
    }
  }, []);

  const refreshAnalysis = useCallback(async () => {
    if (!selectedStock || analysisRequestLocked.current) return;
    analysisRequestLocked.current = true;
    setAnalysisLoading(true);
    setAnalysisError(null);
    setStockChartData([]);
    try {
      const [analysis, chart] = await Promise.all([
        fetchStockAnalysis(selectedStock, true),
        fetchStockChart(selectedStock, 365),
      ]);
      setAnalysisData(analysis);
      setStockChartData(chart.chart_data);
    } catch (e) {
      setAnalysisError(e instanceof Error ? e.message : "股票分析失败");
    } finally {
      setAnalysisLoading(false);
      analysisRequestLocked.current = false;
    }
  }, [selectedStock]);

  const backToOverview = useCallback(() => {
    setSelectedStock(null);
    setSelectedStockName(null);
    setAnalysisData(null);
    setAnalysisError(null);
    setStockChartData([]);
  }, []);

  // ── Comparison handlers ──
  const runComparison = useCallback(async () => {
    if (compareRequestLocked.current || selectedCompareCodes.length < 2) return;
    compareRequestLocked.current = true;
    setCompareLoading(true);
    setCompareError(null);
    try {
      const data = await fetchCompareStocks(selectedCompareCodes, false);
      setCompareData(data);
    } catch (e) {
      setCompareError(e instanceof Error ? e.message : "对比分析失败");
    } finally {
      setCompareLoading(false);
      compareRequestLocked.current = false;
    }
  }, [selectedCompareCodes]);

  const handleCompareStockSelect = useCallback((code: string) => {
    // Open stock in the analysis panel
    selectStock(code);
  }, [selectStock]);

  // Load stock list on mount
  useEffect(() => {
    fetchStockList().then(res => setStockList(res.stocks)).catch(() => {});
  }, []);

  return (
    <>
      <Navbar />

      {/* Hero */}
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
              AI 辅助选股决策系统
            </motion.span>
            <motion.h1
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.2 }}
              className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight text-[rgb(29,29,31)] leading-[1.08]"
            >
              AI 辅助选股
              <br />
              <span className="text-[rgb(142,142,147)]">实时市场 + 多股票评分</span>
            </motion.h1>
            <motion.p
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.35 }}
              className="mt-5 text-base sm:text-lg text-[rgb(110,110,115)] leading-relaxed max-w-xl"
            >
              实时市场扫描、多股票评分排名、AI 选股解释、新手友好输出。同时保留完整的双均线策略回测功能。
            </motion.p>
          </motion.div>
        </div>
      </section>

      <main className="mx-auto max-w-[1280px] px-6 py-10 flex-1">
        {/* ── AI Advisor Section ── */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          className="mb-12"
        >
          <div className="flex items-center gap-2 mb-6">
            <span className="text-xs font-semibold text-[rgb(0,113,227)] tracking-widest uppercase">
              AI 选股
            </span>
            <div className="flex-1 h-px bg-[rgb(229,229,234)]" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Left: Market Overview */}
            <MarketOverviewPanel
              data={marketData}
              loading={marketLoading}
              error={marketError}
              onRefresh={marketData ? refreshMarket : runMarketOverview}
              onSelectStock={selectStock}
            />

            {/* Right: Stock Analysis */}
            <StockAnalysisPanel
              data={analysisData}
              loading={analysisLoading}
              error={analysisError}
              stockCode={selectedStock}
              onBack={backToOverview}
              onRefresh={refreshAnalysis}
              chartData={stockChartData}
              chartLoading={chartLoading}
            />
          </div>

          {/* Comparison Section */}
          <div className="mt-6">
            <StockComparison
              compareResults={compareData}
              stockList={stockList}
              selectedCodes={selectedCompareCodes}
              onSelectStocks={setSelectedCompareCodes}
              onCompare={runComparison}
              onSelectStock={handleCompareStockSelect}
              loading={compareLoading}
              error={compareError}
            />
          </div>

          {/* ── Trading Panel ── */}
          <div className="mt-6">
            <TradingPanel stockCode={selectedStock} stockName={selectedStockName} />
          </div>

          {/* ── Portfolio Backtest ── */}
          <div className="mt-6">
            <PortfolioBacktestPanel />
          </div>
        </motion.div>

        {/* ── Backtest Section ── */}
        <div className="flex items-center gap-2 mb-6">
          <span className="text-xs font-semibold text-[rgb(142,142,147)] tracking-widest uppercase">
            双均线策略回测
          </span>
          <div className="flex-1 h-px bg-[rgb(229,229,234)]" />
        </div>

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
          <p className="text-xs text-[rgb(142,142,147)]">
            AI仅提供参考意见，一切交易以个人决策为准。投资有风险，入市需谨慎。
          </p>
          <p className="text-xs text-[rgb(199,199,204)]">Built with Next.js + FastAPI + Python + Claude AI</p>
        </div>
      </footer>
    </>
  );
}
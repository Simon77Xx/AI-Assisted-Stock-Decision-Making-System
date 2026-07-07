export interface BacktestParams {
  stockCode: string;
  startDate: string;
  endDate: string;
  fastMA: number;
  slowMA: number;
  trendMA: number;
}

export interface BacktestPoint {
  date: string;
  close: number;
  MA5: number | null;
  MA20: number | null;
  MA60: number | null;
  position: number;
  strategy_cum: number;
  benchmark_cum: number;
  daily_return: number;
  strategy_return: number;
}

export interface BacktestSnapshotData {
  current_price: number;
  ma5: number | null;
  ma20: number | null;
  ma60: number | null;
  ma_cross_status: string;
  cross_date: string;
  trend_filter_status: string;
  return_5d: number;
  return_20d: number;
  volume_ratio: number;
  current_position: string;
  current_signal: string;
  max_drawdown: number | null;
  position_state: string;
  holding_days: number;
  insufficient_data: boolean;
  missing_indicators: string[];
}

export interface BacktestResult {
  backtestVersion: string;
  backtestTimestamp: string;
  metrics: Record<string, string | number>;
  chart_data: BacktestPoint[];
  signals: Array<{
    date: string;
    position: number;
  }>;
  currentSignal: "买入" | "卖出" | "持有";
  dataWarnings?: string[];
  snapshot: BacktestSnapshotData;
}

/** Minimal request — indicators are loaded from server-side BacktestSnapshot by version. */
export interface AIJudgementRequest {
  stock_code: string;
  backtest_version: string;
  stock_name?: string;
}

export interface AIResult {
  judgment: "看多" | "看空" | "中性" | string;
  confidence: "高" | "中" | "低" | string;
  reasons: string[];
  risk_note: string;
  cached?: boolean;
  cacheAgeSeconds?: number | null;
  backtestVersion?: string;
  strategy_alignment?: string;
  explanation?: string;
}

// ── AI Stock Advisor Types ─────────────────────────────────────────────

export interface AdvisorStockItem {
  stock: string;
  name: string;
  score: number;
  reason: string;
  price: number | null;
  change_pct: number | null;
}

export interface MarketOverviewResponse {
  market_state: {
    state: string;
    timestamp: string;
    snapshot_id: string;
    stock_count: number;
  };
  top_stocks: AdvisorStockItem[];
  beginner_market_overview: {
    market_mood: string;
    rising_count: number;
    total_count: number;
    timestamp: string;
    recommended_stocks: Array<{
      stock_code: string;
      stock_name: string;
      score: number;
      suggestion: string;
      reason: string;
      risk_tip: string;
      price: number | null;
      change_pct: number | null;
    }>;
  };
  timestamp: string;
}

export interface StockAnalysisResponse {
  selected_stock_analysis: {
    stock_code: string;
    stock_name: string;
    score: number;
    sub_scores: {
      trend_strength: number;
      volume_signal: number;
      volatility_adjusted_return: number;
      ai_confidence: number;
      momentum_score: number;
      valuation_score?: number;
      profitability_score?: number;
      growth_score?: number;
    };
    technical_reason: string;
    strategy_signal: string;
    snapshot_id: string;
    // NEW: indicator signals at the analysis level (not inside sub_scores)
    indicator_signals?: Record<string, unknown> | null;
    composite_indicator_score?: number;
    financial_metrics?: Record<string, unknown> | null;
  };
  ai_recommendation: {
    decision: string;
    reasoning: string;
    risk_level: string;
    confidence: number;
    alternatives: string[];
    // NEW actionable trading guidance
    entry_price_range?: number[] | null;
    target_price?: number | null;
    stop_loss_price?: number | null;
    position_suggestion?: string | null;
    position_ratio?: number | null;
    financial_summary?: string | null;
    trading_plan?: string | null;
    disclaimer?: string;
  };
  strategy_ai_consistency: {
    is_consistent: boolean;
    strategy_signal: string;
    ai_decision: string;
    explanation: string;
    strategy_detail: string;
    ai_detail: string;
  };
  risk_warning: {
    risk_level: string;
    data_timestamp: string;
    data_snapshot_id: string;
    disclaimer: string;
  };
  beginner_output: {
    stock_summary: {
      name: string;
      code: string;
      suggestion: string;
      reason: string;
      risk_tip: string;
      price: number | null;
      change: number | null;
      score: number;
    };
    ai_thinking: string;
    strategy_vs_ai: string;
    risk_warning: string;
    alternatives: Array<{
      code: string;
      name: string;
      score: number;
      suggestion: string;
      reason: string;
      risk_tip: string;
    }>;
  };
}

export interface RefreshResponse {
  status: string;
  snapshot_id: string;
  timestamp: string;
  market_state: string;
  stocks_analyzed: number;
}

// ── Stock Comparison Types ──────────────────────────────────────────────

export interface StockListItem {
  code: string;
  name: string;
}

export interface CompareStockResult {
  selected_stock_analysis: StockAnalysisResponse["selected_stock_analysis"];
  ai_recommendation: StockAnalysisResponse["ai_recommendation"];
  strategy_ai_consistency: StockAnalysisResponse["strategy_ai_consistency"];
  risk_warning: StockAnalysisResponse["risk_warning"];
  beginner_output: StockAnalysisResponse["beginner_output"];
}

export interface CompareStocksResponse {
  stocks: CompareStockResult[];
  timestamp: string;
  snapshot_id: string;
  total_compared: number;
}

// ── Stock Chart Types ───────────────────────────────────────────────────

export interface StockChartPoint {
  date: string;
  open: number;
  close: number;
  high: number;
  low: number;
  volume: number;
  MA5: number | null;
  MA20: number | null;
  MA60: number | null;
}

export interface StockChartResponse {
  stock_code: string;
  stock_name: string;
  chart_data: StockChartPoint[];
}

export interface FullOutputResponse {
  market_state: Record<string, unknown>;
  top_stocks: AdvisorStockItem[];
  selected_stock_analysis: StockAnalysisResponse["selected_stock_analysis"] | null;
  ai_recommendation: StockAnalysisResponse["ai_recommendation"] | null;
  risk_warning: StockAnalysisResponse["risk_warning"] | null;
  beginner_output: StockAnalysisResponse["beginner_output"] | null;
  timestamp: string;
}

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "";

const DEFAULT_TIMEOUT = 30_000;

async function fetchWithTimeout(url: string, options: RequestInit & { timeout?: number } = {}) {
  const { timeout = DEFAULT_TIMEOUT, ...fetchOptions } = options;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const res = await fetch(url, { ...fetchOptions, signal: controller.signal });
    return res;
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error(`请求超时（${timeout / 1000}秒），请稍后重试`);
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function fetchBacktest(params: BacktestParams): Promise<BacktestResult> {
  const searchParams = new URLSearchParams({
    stock_code: params.stockCode,
    start_date: params.startDate,
    end_date: params.endDate,
    fast_ma: String(params.fastMA),
    slow_ma: String(params.slowMA),
    trend_ma: String(params.trendMA),
  });

  const res = await fetchWithTimeout(`${BASE_URL}/api/backtest?${searchParams}`, {
    cache: "no-store",
    timeout: 60_000,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: "请求失败" }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }

  const data = await res.json();
  if (data.error) {
    throw new Error(data.error);
  }
  return data;
}

export async function fetchAIJudgement(request: AIJudgementRequest): Promise<AIResult> {
  const res = await fetchWithTimeout(`${BASE_URL}/api/ai-judgement`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    timeout: 120_000,
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => null);
    if (res.status === 409) {
      throw new Error("检测到回测结果已更新，请重新进行AI分析。");
    }
    throw new Error(errData?.detail || `HTTP ${res.status}`);
  }

  return res.json();
}

// ── AI Stock Advisor API calls ─────────────────────────────────────────

export async function fetchMarketOverview(
  forceRefresh = false
): Promise<MarketOverviewResponse> {
  const res = await fetchWithTimeout(
    `${BASE_URL}/api/advisor/market-overview?force_refresh=${forceRefresh}`,
    { cache: "no-store", timeout: 120_000 }
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "请求失败" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchStockAnalysis(
  stockCode: string,
  forceRefresh = false
): Promise<StockAnalysisResponse> {
  const res = await fetchWithTimeout(
    `${BASE_URL}/api/advisor/analyze-stock?stock_code=${stockCode}&force_refresh=${forceRefresh}`,
    { method: "POST", cache: "no-store", timeout: 120_000 }
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "请求失败" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchFullOutput(
  selectedStock?: string,
  forceRefresh = false
): Promise<FullOutputResponse> {
  let url = `${BASE_URL}/api/advisor/full-output?force_refresh=${forceRefresh}`;
  if (selectedStock) url += `&selected_stock=${selectedStock}`;
  const res = await fetchWithTimeout(url, { cache: "no-store", timeout: 120_000 });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "请求失败" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function refreshMarket(): Promise<RefreshResponse> {
  const res = await fetchWithTimeout(`${BASE_URL}/api/advisor/refresh`, {
    method: "POST",
    cache: "no-store",
    timeout: 120_000,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "请求失败" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchStockList(): Promise<{ stocks: StockListItem[] }> {
  const res = await fetchWithTimeout(`${BASE_URL}/api/advisor/stock-list`, {
    cache: "no-store",
    timeout: 30_000,
  });
  if (!res.ok) throw new Error("获取股票列表失败");
  return res.json();
}

export async function fetchCompareStocks(
  stockCodes: string[],
  forceRefresh = false
): Promise<CompareStocksResponse> {
  const codes = stockCodes.join(",");
  const res = await fetchWithTimeout(
    `${BASE_URL}/api/advisor/compare-stocks?stock_codes=${codes}&force_refresh=${forceRefresh}`,
    { method: "POST", cache: "no-store", timeout: 300_000 }
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "请求失败" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchStockChart(
  stockCode: string,
  days = 365
): Promise<StockChartResponse> {
  const res = await fetchWithTimeout(
    `${BASE_URL}/api/advisor/stock-chart?stock_code=${stockCode}&days=${days}`,
    { cache: "no-store", timeout: 120_000 }
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "请求失败" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ═══════════════════════════════════════════════════════════════════════
// NEW: Financial Data & Trading API Types
// ═══════════════════════════════════════════════════════════════════════

export interface FinancialMetricsData {
  pe_ttm: number | null;
  roe: number | null;
  net_profit_margin: number | null;
  gross_margin: number | null;
  revenue_growth: number | null;
  net_profit_growth: number | null;
  debt_ratio: number | null;
  current_ratio: number | null;
  eps: number | null;
  bvps: number | null;
  report_date: string;
}

export interface FinancialDataResponse {
  stock_code: string;
  financial_metrics: FinancialMetricsData | null;
  note?: string;
}

// Trading types
export interface TradingPosition {
  stock_code: string;
  stock_name: string;
  quantity: number;
  available_quantity: number;
  cost_price: number;
  current_price: number | null;
  market_value: number | null;
  profit_pct: number | null;
  profit_amount?: number | null;
}

export interface TradingAccountResponse {
  account_id: string;
  name: string;
  connected: boolean;
  total_asset: number;
  available_cash: number;
  frozen_cash: number;
  market_value: number;
  daily_profit: number | null;
  positions: TradingPosition[];
  update_time: string;
}

export interface TradingOrderResult {
  order_id: string;
  stock_code: string;
  stock_name: string;
  side: string;
  order_type: string;
  price: number | null;
  quantity: number;
  filled_quantity: number;
  status: string;
  note: string;
  reject_reason: string;
  created_at: string;
}

export interface TradingOrdersResponse {
  orders: TradingOrderResult[];
  total_count: number;
}

export interface TradingPositionsResponse {
  positions: TradingPosition[];
  total_count: number;
}

// ═══════════════════════════════════════════════════════════════════════
// NEW API Calls: Financial Data & Trading
// ═══════════════════════════════════════════════════════════════════════

export async function fetchFinancialData(
  stockCode: string,
  forceRefresh = false
): Promise<FinancialDataResponse> {
  const res = await fetchWithTimeout(
    `${BASE_URL}/api/advisor/financial-data?stock_code=${stockCode}&force_refresh=${forceRefresh}`,
    { cache: "no-store", timeout: 30_000 }
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "请求失败" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchTradingAccount(
  mode = "simulated"
): Promise<TradingAccountResponse> {
  const res = await fetchWithTimeout(
    `${BASE_URL}/api/advisor/trading/account?mode=${mode}`,
    { cache: "no-store", timeout: 30_000 }
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "请求失败" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchTradingPositions(
  mode = "simulated"
): Promise<TradingPositionsResponse> {
  const res = await fetchWithTimeout(
    `${BASE_URL}/api/advisor/trading/positions?mode=${mode}`,
    { cache: "no-store", timeout: 30_000 }
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "请求失败" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchOrderHistory(
  mode = "simulated",
  limit = 50
): Promise<TradingOrdersResponse> {
  const res = await fetchWithTimeout(
    `${BASE_URL}/api/advisor/trading/orders?mode=${mode}&limit=${limit}`,
    { cache: "no-store", timeout: 30_000 }
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "请求失败" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function placeTradingOrder(params: {
  stock_code: string;
  stock_name?: string;
  side: "buy" | "sell";
  order_type: "market" | "limit";
  quantity: number;
  price?: number | null;
  mode?: string;
}): Promise<TradingOrderResult> {
  const searchParams = new URLSearchParams({
    stock_code: params.stock_code,
    side: params.side,
    order_type: params.order_type,
    quantity: String(params.quantity),
    mode: params.mode || "simulated",
  });
  if (params.stock_name) searchParams.set("stock_name", params.stock_name);
  if (params.price != null) searchParams.set("price", String(params.price));

  const res = await fetchWithTimeout(
    `${BASE_URL}/api/advisor/trading/order?${searchParams}`,
    { method: "POST", cache: "no-store", timeout: 30_000 }
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "请求失败" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function resetTradingAccount(
  mode = "simulated",
  initialCash = 100000
): Promise<{ status: string; message: string }> {
  const res = await fetchWithTimeout(
    `${BASE_URL}/api/advisor/trading/reset?mode=${mode}&initial_cash=${initialCash}`,
    { method: "POST", cache: "no-store", timeout: 15_000 }
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "请求失败" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}
// ═══════════════════════════════════════════════════════════════════════
// NEW Types: Technical Indicators & Multi-timeframe
// ═══════════════════════════════════════════════════════════════════════

export interface IndicatorSignal {
  score: number;
  signal: string;
  value?: number;
  signal_value?: number;
  histogram?: number;
  bb_pct?: number;
  bb_width?: number;
  K?: number;
  D?: number;
  J?: number;
  atr_pct?: number;
}

export interface TechnicalIndicatorsResponse {
  stock_code: string;
  stock_name: string;
  composite_score: number;
  indicators: Record<string, IndicatorSignal>;
  timestamp: string;
}

export interface TimeframeData {
  composite_score: number;
  data_points: number;
  indicators: Record<string, IndicatorSignal> | null;
}

export interface MultiTimeframeResponse {
  stock_code: string;
  stock_name: string;
  consensus: "bullish" | "bearish" | "mixed";
  timeframes: {
    daily: TimeframeData;
    weekly: TimeframeData;
    monthly: TimeframeData;
  };
  timestamp: string;
}

// ═══════════════════════════════════════════════════════════════════════
// NEW Types: Portfolio Backtest
// ═══════════════════════════════════════════════════════════════════════

export interface PortfolioTemplate {
  name: string;
  description: string;
  stocks: string[];
  capital_strategy: string;
  max_per_stock: number;
}

export interface PortfolioTemplatesResponse {
  templates: Record<string, PortfolioTemplate>;
}

export interface PortfolioBacktestResult {
  stock_codes: string[];
  stock_names: string[];
  start_date: string;
  end_date: string;
  total_capital: number;
  capital_strategy: string;
  weights: number[];
  portfolio_metrics: Record<string, string | number>;
  per_stock_metrics: Array<Record<string, string | number>>;
  equity_curve: Array<{ date: string; equity: number }>;
  max_drawdown_pct: number;
  final_capital: number;
}

// ═══════════════════════════════════════════════════════════════════════
// NEW API Calls: Technical Indicators & Multi-timeframe
// ═══════════════════════════════════════════════════════════════════════

export async function fetchTechnicalIndicators(
  stockCode: string,
  days = 365
): Promise<TechnicalIndicatorsResponse> {
  const res = await fetchWithTimeout(
    `${BASE_URL}/api/advisor/technical-indicators?stock_code=${stockCode}&days=${days}`,
    { cache: "no-store", timeout: 120_000 }
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "请求失败" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchMultiTimeframe(
  stockCode: string,
  days = 730
): Promise<MultiTimeframeResponse> {
  const res = await fetchWithTimeout(
    `${BASE_URL}/api/advisor/multi-timeframe?stock_code=${stockCode}&days=${days}`,
    { cache: "no-store", timeout: 120_000 }
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "请求失败" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ═══════════════════════════════════════════════════════════════════════
// NEW API Calls: Portfolio Backtest
// ═══════════════════════════════════════════════════════════════════════

export async function fetchPortfolioTemplates(): Promise<PortfolioTemplatesResponse> {
  const res = await fetchWithTimeout(
    `${BASE_URL}/api/advisor/portfolio-templates`,
    { cache: "no-store", timeout: 15_000 }
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "请求失败" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function runPortfolioBacktest(params: {
  stock_codes: string[];
  capital_strategy?: string;
  total_capital?: number;
  max_per_stock?: number;
  start_date?: string;
  end_date?: string;
}): Promise<PortfolioBacktestResult> {
  const codes = params.stock_codes.join(",");
  let url = `${BASE_URL}/api/advisor/portfolio-backtest?stock_codes=${codes}`;
  if (params.capital_strategy) url += `&capital_strategy=${params.capital_strategy}`;
  if (params.total_capital) url += `&total_capital=${params.total_capital}`;
  if (params.max_per_stock) url += `&max_per_stock=${params.max_per_stock}`;
  if (params.start_date) url += `&start_date=${params.start_date}`;
  if (params.end_date) url += `&end_date=${params.end_date}`;

  const res = await fetchWithTimeout(
    url,
    { method: "POST", cache: "no-store", timeout: 300_000 }
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "请求失败" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

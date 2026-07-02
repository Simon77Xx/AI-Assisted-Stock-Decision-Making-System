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

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function fetchBacktest(params: BacktestParams): Promise<BacktestResult> {
  const searchParams = new URLSearchParams({
    stock_code: params.stockCode,
    start_date: params.startDate,
    end_date: params.endDate,
    fast_ma: String(params.fastMA),
    slow_ma: String(params.slowMA),
    trend_ma: String(params.trendMA),
  });

  const res = await fetch(`${BASE_URL}/api/backtest?${searchParams}`, {
    cache: "no-store",
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
  const res = await fetch(`${BASE_URL}/api/ai-judgement`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
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
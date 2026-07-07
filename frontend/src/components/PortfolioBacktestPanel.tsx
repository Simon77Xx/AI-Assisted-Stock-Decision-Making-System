"use client";

import { motion } from "framer-motion";
import {
  BarChart3,
  RefreshCw,
  PieChart,
  Equal,
  Sigma,
  Shield,
  TrendingUp,
  TrendingDown,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import {
  fetchPortfolioTemplates,
  runPortfolioBacktest,
  type PortfolioTemplate,
  type PortfolioTemplatesResponse,
  type PortfolioBacktestResult,
} from "@/lib/api";

const STRATEGY_LABELS: Record<string, string> = {
  equal: "等权重",
  kelly: "Kelly公式",
  risk_parity: "风险平价",
};

export function PortfolioBacktestPanel() {
  const [templates, setTemplates] = useState<Record<string, PortfolioTemplate>>({});
  const [result, setResult] = useState<PortfolioBacktestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [selectedTemplate, setSelectedTemplate] = useState<string>("conservative");
  const [customCodes, setCustomCodes] = useState("");
  const [strategy, setStrategy] = useState("equal");
  const [capital, setCapital] = useState(100_000);
  const [maxPerStock, setMaxPerStock] = useState(0.25);
  const [useCustom, setUseCustom] = useState(false);

  useEffect(() => {
    fetchPortfolioTemplates()
      .then((res) => setTemplates(res.templates))
      .catch(() => {});
  }, []);

  const handleRun = useCallback(async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      let codes: string[];
      if (useCustom) {
        codes = customCodes.split(",").map((c) => c.trim()).filter(Boolean);
      } else {
        codes = templates[selectedTemplate]?.stocks || [];
      }
      const data = await runPortfolioBacktest({
        stock_codes: codes,
        capital_strategy: strategy,
        total_capital: capital,
        max_per_stock: maxPerStock,
      });
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "组合回测失败");
    } finally {
      setLoading(false);
    }
  }, [useCustom, customCodes, templates, selectedTemplate, strategy, capital, maxPerStock]);

  const tpl = templates[selectedTemplate];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-[rgb(245,245,247)] rounded-2xl p-6 shadow-sm"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-3">
          <PieChart className="w-5 h-5 text-[rgb(0,113,227)]" />
          <div>
            <h3 className="text-sm font-semibold text-[rgb(29,29,31)]">组合回测</h3>
            <p className="text-xs text-[rgb(142,142,147)] mt-0.5">
              多股票资金管理 · Kelly公式 · 风险平价
            </p>
          </div>
        </div>
        <button
          onClick={handleRun}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-[rgb(0,113,227)] text-white text-xs font-semibold hover:bg-[rgb(0,90,200)] disabled:opacity-50 transition-all active:scale-[0.98]"
        >
          <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} />
          运行回测
        </button>
      </div>

      {/* Config */}
      <div className="bg-white rounded-xl border border-[rgb(229,229,234)] p-4 mb-4">
        <div className="flex flex-col sm:flex-row gap-3">
          {/* Mode toggle */}
          <div className="flex gap-1 bg-[rgb(229,229,234)] rounded-lg p-0.5 min-w-[150px]">
            <button
              onClick={() => setUseCustom(false)}
              className={`flex-1 py-1 px-2 text-[10px] font-semibold rounded-md transition-all ${
                !useCustom ? "bg-white text-[rgb(29,29,31)] shadow-sm" : "text-[rgb(142,142,147)]"
              }`}
            >
              模板
            </button>
            <button
              onClick={() => setUseCustom(true)}
              className={`flex-1 py-1 px-2 text-[10px] font-semibold rounded-md transition-all ${
                useCustom ? "bg-white text-[rgb(29,29,31)] shadow-sm" : "text-[rgb(142,142,147)]"
              }`}
            >
              自定义
            </button>
          </div>

          {useCustom ? (
            <input
              type="text"
              value={customCodes}
              onChange={(e) => setCustomCodes(e.target.value)}
              placeholder="股票代码，逗号分隔"
              className="flex-1 bg-[rgb(245,245,247)] rounded-lg px-3 py-2 text-xs font-medium text-[rgb(29,29,31)] border-0 outline-none focus:ring-1 focus:ring-[rgb(0,113,227)]"
            />
          ) : (
            <select
              value={selectedTemplate}
              onChange={(e) => {
                setSelectedTemplate(e.target.value);
                const t = templates[e.target.value];
                if (t) { setStrategy(t.capital_strategy); setMaxPerStock(t.max_per_stock); }
              }}
              className="flex-1 bg-[rgb(245,245,247)] rounded-lg px-3 py-2 text-xs font-medium text-[rgb(29,29,31)] border-0 outline-none focus:ring-1 focus:ring-[rgb(0,113,227)]"
            >
              {Object.entries(templates).map(([key, val]) => (
                <option key={key} value={key}>
                  {val.name} — {val.description}
                </option>
              ))}
            </select>
          )}

          {/* Strategy selector */}
          <div className="flex gap-1">
            {[
              { key: "equal", icon: Equal, label: "等权" },
              { key: "kelly", icon: Sigma, label: "Kelly" },
              { key: "risk_parity", icon: Shield, label: "风险平价" },
            ].map(({ key, icon: Icon, label }) => (
              <button
                key={key}
                onClick={() => setStrategy(key)}
                className={`p-2 rounded-lg text-[9px] font-semibold transition-all flex items-center gap-1 ${
                  strategy === key
                    ? "bg-[rgb(0,113,227)] text-white"
                    : "bg-[rgb(245,245,247)] text-[rgb(142,142,147)]"
                }`}
                title={STRATEGY_LABELS[key]}
              >
                <Icon className="w-3 h-3" />{label}
              </button>
            ))}
          </div>
        </div>

        {/* Settings row */}
        <div className="flex gap-3 mt-3">
          <div className="flex-1">
            <label className="text-[9px] text-[rgb(142,142,147)] block mb-1">初始资金</label>
            <input
              type="number"
              value={capital}
              onChange={(e) => setCapital(Math.max(0, parseInt(e.target.value) || 0))}
              className="w-full bg-[rgb(245,245,247)] rounded-lg px-3 py-2 text-xs font-medium text-[rgb(29,29,31)] border-0 outline-none focus:ring-1 focus:ring-[rgb(0,113,227)]"
            />
          </div>
          <div className="flex-1">
            <label className="text-[9px] text-[rgb(142,142,147)] block mb-1">单股上限</label>
            <select
              value={maxPerStock}
              onChange={(e) => setMaxPerStock(parseFloat(e.target.value))}
              className="w-full bg-[rgb(245,245,247)] rounded-lg px-3 py-2 text-xs font-medium text-[rgb(29,29,31)] border-0 outline-none focus:ring-1 focus:ring-[rgb(0,113,227)]"
            >
              {[0.1, 0.15, 0.2, 0.25, 0.3, 0.4].map((v) => (
                <option key={v} value={v}>{(v * 100).toFixed(0)}%</option>
              ))}
            </select>
          </div>
        </div>

        {useCustom && (
          <p className="text-[9px] text-[rgb(142,142,147)] mt-2">
            输入股票代码，用逗号分隔（如：600519,000333,300750）
          </p>
        )}
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-8">
          <RefreshCw className="w-4 h-4 animate-spin text-[rgb(0,113,227)]" />
          <span className="ml-2 text-xs text-[rgb(110,110,115)]">正在计算组合收益...</span>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-[rgb(255,59,48)]/5 border border-[rgb(255,59,48)]/15 rounded-xl p-3 mb-3 text-xs text-[rgb(255,59,48)]">
          {error}
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-4">
          {/* Portfolio metrics */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
            {Object.entries(result.portfolio_metrics).map(([key, value]) => (
              <div key={key} className="bg-white rounded-xl border border-[rgb(229,229,234)] p-3">
                <p className="text-[9px] text-[rgb(142,142,147)] mb-1">{key}</p>
                <p className="text-sm font-bold text-[rgb(29,29,31)]">{String(value)}</p>
              </div>
            ))}
          </div>

          {/* Final capital */}
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-white rounded-xl border border-[rgb(52,199,89)]/20 p-3">
              <p className="text-[10px] text-[rgb(52,199,89)] mb-1">最终资金</p>
              <p className="text-lg font-bold text-[rgb(29,29,31)]">
                ¥{result.final_capital.toLocaleString()}
              </p>
            </div>
            <div className="bg-white rounded-xl border border-[rgb(255,149,0)]/20 p-3">
              <p className="text-[10px] text-[rgb(180,95,0)] mb-1">最大回撤</p>
              <p className="text-lg font-bold text-[rgb(29,29,31)]">
                {(result.max_drawdown_pct * 100).toFixed(1)}%
              </p>
            </div>
          </div>

          {/* Weights */}
          <div className="bg-white rounded-xl border border-[rgb(229,229,234)] p-4">
            <p className="text-[10px] font-medium text-[rgb(142,142,147)] tracking-wide uppercase mb-3">
              资金分配（{STRATEGY_LABELS[result.capital_strategy] || result.capital_strategy}）
            </p>
            <div className="space-y-2">
              {result.stock_codes.map((code, i) => (
                <div key={code} className="flex items-center gap-2">
                  <span className="text-[10px] text-[rgb(142,142,147)] w-16 shrink-0">{code}</span>
                  <div className="flex-1 h-1.5 bg-[rgb(229,229,234)] rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full bg-[rgb(0,113,227)]"
                      style={{ width: `${result.weights[i] * 100}%` }}
                    />
                  </div>
                  <span className="text-[10px] font-medium text-[rgb(29,29,31)] w-12 text-right">
                    {(result.weights[i] * 100).toFixed(1)}%
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Individual stock metrics */}
          {result.per_stock_metrics.length > 0 && (
            <div className="bg-white rounded-xl border border-[rgb(229,229,234)] p-4">
              <p className="text-[10px] font-medium text-[rgb(142,142,147)] tracking-wide uppercase mb-3">
                各股表现
              </p>
              <div className="overflow-x-auto">
                <table className="w-full text-[10px]">
                  <thead>
                    <tr className="border-b border-[rgb(229,229,234)]">
                      <th className="text-left py-1 pr-2 text-[rgb(142,142,147)]">股票</th>
                      <th className="text-right py-1 px-2 text-[rgb(142,142,147)]">累计收益</th>
                      <th className="text-right py-1 px-2 text-[rgb(142,142,147)]">最大回撤</th>
                      <th className="text-right py-1 px-2 text-[rgb(142,142,147)]">胜率</th>
                      <th className="text-right py-1 pl-2 text-[rgb(142,142,147)]">交易次数</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.per_stock_metrics.map((m, i) => (
                      <tr key={i} className="border-b border-[rgb(229,229,234)] last:border-0">
                        <td className="py-1.5 pr-2 font-medium text-[rgb(29,29,31)]">
                          {String(m.stock_name || m.stock_code)}
                        </td>
                        <td className="py-1.5 px-2 text-right">{String(m.累计收益率 || "-")}</td>
                        <td className="py-1.5 px-2 text-right">{String(m.最大回撤 || "-")}</td>
                        <td className="py-1.5 px-2 text-right">{String(m.胜率 || "-")}</td>
                        <td className="py-1.5 pl-2 text-right">{String(m.交易次数 ?? "-")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Equity curve info */}
          {result.equity_curve.length > 0 && (
            <div className="bg-white rounded-xl border border-[rgb(229,229,234)] p-4">
              <p className="text-[10px] font-medium text-[rgb(142,142,147)] tracking-wide uppercase mb-3">
                权益曲线
              </p>
              <div className="h-[200px] relative">
                {/* Simple SVG equity curve */}
                <svg width="100%" height="100%" viewBox={`0 0 ${result.equity_curve.length} 200`} preserveAspectRatio="none">
                  <defs>
                    <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="rgb(0,113,227)" stopOpacity="0.15" />
                      <stop offset="100%" stopColor="rgb(0,113,227)" stopOpacity="0" />
                    </linearGradient>
                  </defs>
                  {result.equity_curve.length > 1 && (() => {
                    const values = result.equity_curve.map((d) => d.equity);
                    const maxV = Math.max(...values);
                    const minV = Math.min(...values);
                    const range = maxV - minV || 1;
                    const n = values.length;
                    const xScale = 100 / (n - 1);

                    const areaPath = values.map((v, i) => {
                      const x = i * xScale;
                      const y = 200 - ((v - minV) / range) * 180;
                      return `${i === 0 ? "M" : "L"}${x},${y}`;
                    }).join(" ") + ` L${(n - 1) * xScale},200 L0,200 Z`;

                    const linePath = values.map((v, i) => {
                      const x = i * xScale;
                      const y = 200 - ((v - minV) / range) * 180;
                      return `${i === 0 ? "M" : "L"}${x},${y}`;
                    }).join(" ");

                    return (
                      <>
                        <path d={areaPath} fill="url(#equityGrad)" />
                        <path d={linePath} fill="none" stroke="rgb(0,113,227)" strokeWidth="1.5" />
                      </>
                    );
                  })()}
                </svg>
              </div>
              <div className="flex justify-between mt-2">
                <span className="text-[9px] text-[rgb(142,142,147)]">{result.start_date}</span>
                <span className="text-[9px] text-[rgb(142,142,147)]">{result.end_date}</span>
              </div>
            </div>
          )}
        </div>
      )}
    </motion.div>
  );
}
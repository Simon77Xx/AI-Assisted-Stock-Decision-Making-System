"use client";

import { useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
} from "recharts";
import { motion } from "framer-motion";
import type { StockChartPoint } from "@/lib/api";

interface StockSeries {
  code: string;
  name: string;
  color: string;
}

interface ComparisonTrendChartProps {
  series: StockSeries[];
  /** Map of stock code -> chart data */
  dataMap: Record<string, StockChartPoint[]>;
  height?: number;
}

const STOCK_COLORS = [
  "#0071e3",
  "#ff9500",
  "#34c759",
  "#ff3b30",
  "#af52de",
  "#ff2d55",
];

function formatDate(dateStr: string) {
  const d = new Date(dateStr);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

/** Normalize all series to a common date grid aligned by index from the end. */
function alignToCommonGrid(
  dataMap: Record<string, StockChartPoint[]>,
  series: StockSeries[],
  maxPoints = 120,
): Array<Record<string, string | number | null>> {
  if (series.length === 0) return [];

  const truncated: StockChartPoint[][] = [];
  for (const s of series) {
    const d = dataMap[s.code];
    if (!d || d.length === 0) continue;
    truncated.push(d.slice(-maxPoints));
  }

  if (truncated.length === 0) return [];
  if (truncated.length === 1) {
    return truncated[0].map((p) => ({
      date: formatDate(p.date),
      [series[0].code]: p.close,
    }));
  }

  let maxLenIdx = 0;
  for (let i = 1; i < truncated.length; i++) {
    if (truncated[i].length > truncated[maxLenIdx].length) {
      maxLenIdx = i;
    }
  }

  const dates = truncated[maxLenIdx].map((p) => formatDate(p.date));

  const grid: Array<Record<string, string | number | null>> = [];
  for (let di = 0; di < dates.length; di++) {
    const row: Record<string, string | number | null> = { date: dates[di] };
    for (let si = 0; si < series.length; si++) {
      const d = truncated[si] || [];
      const offsetFromEnd = truncated[maxLenIdx].length - 1 - di;
      const siIdx = d.length - 1 - offsetFromEnd;
      row[series[si].code] = siIdx >= 0 && siIdx < d.length ? d[siIdx].close : null;
    }
    grid.push(row);
  }

  return grid;
}

// ── Custom Tooltip ────────────────────────────────────────────────────────
// Shows a vertical cursor line + a compact table of all stocks at that point.

function ComparisonTooltip({
  active,
  payload,
  label,
  series,
}: {
  active?: boolean;
  payload?: Array<{ dataKey: string | number; value: number; color: string }>;
  label?: string | number;
  series: StockSeries[];
}) {
  if (!active || !payload || payload.length === 0) return null;

  // Sort by value descending so the highest-priced stock is on top
  const sorted = [...payload].sort((a, b) => (b.value ?? 0) - (a.value ?? 0));

  return (
    <div className="bg-white/98 border border-[rgb(229,229,234)] rounded-xl shadow-lg px-3 py-2.5 text-[11px] min-w-[140px]">
      <p className="text-[10px] font-medium text-[rgb(142,142,147)] mb-2 border-b border-[rgb(229,229,234)] pb-1.5">
        {label}
      </p>
      {sorted.map((entry) => {
        const stock = series.find((s) => s.code === String(entry.dataKey));
        return (
          <div
            key={String(entry.dataKey)}
            className="flex items-center justify-between gap-3 py-0.5"
          >
            <div className="flex items-center gap-1.5">
              <span
                className="w-2 h-2 rounded-full inline-block shrink-0"
                style={{ backgroundColor: entry.color }}
              />
              <span className="text-[rgb(110,110,115)] truncate max-w-[80px]">
                {stock?.name || entry.dataKey}
              </span>
            </div>
            <span className="font-semibold text-[rgb(29,29,31)] tabular-nums">
              {entry.value.toFixed(2)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────

export function ComparisonTrendChart({
  series,
  dataMap,
  height = 350,
}: ComparisonTrendChartProps) {
  const hasData = series.length > 0 && series.some((s) => (dataMap[s.code]?.length ?? 0) > 0);

  const chartData = useMemo(
    () => alignToCommonGrid(dataMap, series),
    [dataMap, series],
  );

  if (!hasData || chartData.length === 0) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-white rounded-xl border border-[rgb(229,229,234)] p-6 flex items-center justify-center h-[250px]"
      >
        <p className="text-xs text-[rgb(142,142,147)]">
          选择股票并点击「加载趋势对比」查看叠加走势
        </p>
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      className="bg-white rounded-xl border border-[rgb(229,229,234)] p-4"
    >
      <div className="flex items-center justify-between mb-3">
        <div>
          <p className="text-[10px] font-medium text-[rgb(142,142,147)] tracking-wide uppercase">
            趋势叠加对比
          </p>
          <p className="text-[10px] text-[rgb(199,199,204)] mt-0.5">
            鼠标悬停 · 十字光标对齐各股同一时点价位
          </p>
        </div>
        {series.length > 0 && (
          <div className="flex items-center gap-2 flex-wrap justify-end">
            {series.map((s) => (
              <div
                key={s.code}
                className="flex items-center gap-1 text-[10px] text-[rgb(110,110,115)]"
              >
                <span
                  className="w-2 h-2 rounded-full inline-block shrink-0"
                  style={{ backgroundColor: s.color }}
                />
                <span>{s.name}</span>
              </div>
            ))}
          </div>
        )}
      </div>
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={chartData}
            margin={{ top: 8, right: 8, bottom: 0, left: 0 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="rgb(229,229,234)"
              vertical={false}
            />
            <XAxis
              dataKey="date"
              axisLine={false}
              tickLine={false}
              tick={{ fontSize: 10, fill: "#8e8e93" }}
              interval="preserveStartEnd"
              minTickGap={40}
            />
            <YAxis
              axisLine={false}
              tickLine={false}
              tick={{ fontSize: 10, fill: "#8e8e93" }}
              width={52}
              domain={["auto", "auto"]}
              tickFormatter={(v: number) => v.toFixed(1)}
            />
            <Tooltip
              cursor={{
                stroke: "#0071e3",
                strokeWidth: 1,
                strokeDasharray: "4 3",
                opacity: 0.6,
              }}
              content={({ active, payload, label }) => (
                <ComparisonTooltip
                  active={active}
                  payload={payload as any}
                  label={label}
                  series={series}
                />
              )}
            />
            {series.map((s, i) => (
              <Line
                key={s.code}
                type="monotone"
                dataKey={s.code}
                stroke={s.color || STOCK_COLORS[i % STOCK_COLORS.length]}
                strokeWidth={2}
                dot={false}
                name={s.code}
                connectNulls={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </motion.div>
  );
}
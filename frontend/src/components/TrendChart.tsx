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

interface TrendChartProps {
  data: StockChartPoint[];
  height?: number;
  showMA?: boolean;
  stockName?: string;
}

function formatDate(dateStr: string) {
  const d = new Date(dateStr);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

export function TrendChart({ data, height = 280, showMA = true, stockName }: TrendChartProps) {
  const chartData = useMemo(
    () =>
      data.map((d) => ({
        date: formatDate(d.date),
        close: d.close,
        MA5: d.MA5,
        MA20: d.MA20,
        MA60: d.MA60,
      })),
    [data]
  );

  if (!chartData.length) return null;

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
            {stockName ? `${stockName} 趋势图` : "价格趋势"}
          </p>
          <p className="text-[10px] text-[rgb(199,199,204)] mt-0.5">
            近 {data.length} 个交易日 · 叠加均线
          </p>
        </div>
      </div>
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <defs>
              <linearGradient id="closeGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#0071e3" stopOpacity={0.12} />
                <stop offset="100%" stopColor="#0071e3" stopOpacity={0} />
              </linearGradient>
            </defs>
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
              minTickGap={50}
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
              contentStyle={{
                backgroundColor: "rgba(255,255,255,0.96)",
                border: "1px solid rgb(229,229,234)",
                borderRadius: "10px",
                boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
                fontSize: "12px",
              }}
              formatter={(value: unknown, name: unknown) => {
                const v = typeof value === "number" ? value : 0;
                const labels: Record<string, string> = {
                  close: "收盘价",
                  MA5: "MA5",
                  MA20: "MA20",
                  MA60: "MA60",
                };
                const n = typeof name === "string" ? name : "";
                return [v.toFixed(2), labels[n] || n];
              }}
            />
            {showMA && (
              <>
                <Line
                  type="monotone"
                  dataKey="MA60"
                  stroke="#8e8e93"
                  strokeWidth={1}
                  strokeDasharray="4 4"
                  dot={false}
                  name="MA60"
                />
                <Line
                  type="monotone"
                  dataKey="MA20"
                  stroke="#0071e3"
                  strokeWidth={1.5}
                  dot={false}
                  name="MA20"
                />
                <Line
                  type="monotone"
                  dataKey="MA5"
                  stroke="#ff9500"
                  strokeWidth={1.5}
                  dot={false}
                  name="MA5"
                />
              </>
            )}
            <Line
              type="monotone"
              dataKey="close"
              stroke="#1c1c1e"
              strokeWidth={2}
              dot={false}
              fill="url(#closeGrad)"
              name="close"
            />
            <Legend
              wrapperStyle={{ fontSize: "10px", color: "#8e8e93" }}
              iconType="line"
              iconSize={12}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </motion.div>
  );
}
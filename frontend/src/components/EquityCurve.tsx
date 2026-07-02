"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { motion } from "framer-motion";
import { useMemo } from "react";

interface EquityCurveProps {
  data: Array<{
    date: string;
    strategy_cum: number;
    benchmark_cum: number;
  }>;
}

function formatDate(dateStr: string) {
  const d = new Date(dateStr);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

export function EquityCurve({ data }: EquityCurveProps) {
  const chartData = useMemo(
    () =>
      data.map((d) => ({
        date: formatDate(d.date),
        strategy: Number((d.strategy_cum - 1).toFixed(4)),
        benchmark: Number((d.benchmark_cum - 1).toFixed(4)),
      })),
    [data]
  );

  if (!chartData.length) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, delay: 0.3, ease: [0.16, 1, 0.3, 1] }}
      className="bg-white rounded-2xl border border-[rgb(229,229,234)] p-6 shadow-sm"
    >
      <h3 className="text-sm font-semibold text-[rgb(29,29,31)] mb-1">
        收益曲线
      </h3>
      <p className="text-xs text-[rgb(142,142,147)] mb-5">
        策略累计收益 vs 买入持有基准
      </p>
      <div className="h-[300px]">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData}>
            <defs>
              <linearGradient id="strategyGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#0071e3" stopOpacity={0.15} />
                <stop offset="100%" stopColor="#0071e3" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="benchGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#8e8e93" stopOpacity={0.1} />
                <stop offset="100%" stopColor="#8e8e93" stopOpacity={0} />
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
              tick={{ fontSize: 11, fill: "#8e8e93" }}
              interval="preserveStartEnd"
              minTickGap={60}
            />
            <YAxis
              axisLine={false}
              tickLine={false}
              tick={{ fontSize: 11, fill: "#8e8e93" }}
              tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
              width={48}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "rgba(255,255,255,0.95)",
                border: "1px solid rgb(229,229,234)",
                borderRadius: "12px",
                boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
                fontSize: "12px",
              }}
              formatter={(value, name) => {
                const v = typeof value === "number" ? value : 0;
                const n = typeof name === "string" ? name : "";
                return [
                  `${(v * 100).toFixed(2)}%`,
                  n === "strategy" ? "策略收益" : "买入持有",
                ];
              }}
            />
            <Area
              type="monotone"
              dataKey="benchmark"
              stroke="#8e8e93"
              strokeWidth={1.5}
              strokeDasharray="4 4"
              fill="url(#benchGrad)"
              name="benchmark"
            />
            <Area
              type="monotone"
              dataKey="strategy"
              stroke="#0071e3"
              strokeWidth={2}
              fill="url(#strategyGrad)"
              name="strategy"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </motion.div>
  );
}
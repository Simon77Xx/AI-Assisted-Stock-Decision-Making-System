"use client";

import { useMemo, useRef, useEffect, useState } from "react";
import { motion } from "framer-motion";

interface CandleData {
  date: string;
  open: number;
  close: number;
  high: number;
  low: number;
  ma5: number | null;
  ma20: number | null;
  ma60: number | null;
}

interface CandlestickChartProps {
  data: CandleData[];
}

const CANDLE_WIDTH = 0.6;
const PADDING = { top: 20, right: 16, bottom: 36, left: 52 };
const UP_COLOR = "#ff3b30";
const DOWN_COLOR = "#34c759";

function formatShortDate(dateStr: string) {
  const d = new Date(dateStr);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

export function CandlestickChart({ data }: CandlestickChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 400 });

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setDimensions({
          width: entry.contentRect.width,
          height: entry.contentRect.height,
        });
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

    const { chartData, yScale, yTicks } = useMemo(() => {
    const chartW = dimensions.width - PADDING.left - PADDING.right;
    const chartH = dimensions.height - PADDING.top - PADDING.bottom;
    const n = data.length;
    if (n === 0)
      return {
        chartData: [],
        yScale: () => 0,
        xScale: () => 0,
        yTicks: [] as number[],
      };

    let minPrice = Infinity;
    let maxPrice = -Infinity;
    for (const d of data) {
      minPrice = Math.min(minPrice, d.low, d.ma5 ?? Infinity, d.ma20 ?? Infinity, d.ma60 ?? Infinity);
      maxPrice = Math.max(maxPrice, d.high, d.ma5 ?? -Infinity, d.ma20 ?? -Infinity, d.ma60 ?? -Infinity);
    }
    const pad = (maxPrice - minPrice) * 0.08 || 1;
    const yMin = minPrice - pad;
    const yMax = maxPrice + pad;

    const candleStep = chartW / Math.max(n - 1, 1);
    const candleWidth = Math.max(3, candleStep * CANDLE_WIDTH);

    const yScaleFn = (v: number) =>
      PADDING.top + chartH * (1 - (v - yMin) / (yMax - yMin));
    const xScaleFn = (i: number) => PADDING.left + i * candleStep;

    const tickCount = 5;
    const ticks: number[] = [];
    for (let i = 0; i < tickCount; i++) {
      ticks.push(yMin + (yMax - yMin) * (i / (tickCount - 1)));
    }

    return {
      chartData: data.map((d, i) => ({
        ...d,
        x: xScaleFn(i),
        candleWidth,
      })),
      yScale: yScaleFn,
      xScale: xScaleFn,
      yTicks: ticks,
      candleStep,
    };
  }, [data, dimensions]);

  // X-axis label indices
  const xLabels = useMemo(() => {
    if (chartData.length <= 1) return [];
    const step = Math.max(1, Math.floor(chartData.length / 6));
    const labels: { index: number; date: string; x: number }[] = [];
    for (let i = 0; i < chartData.length; i += step) {
      labels.push({
        index: i,
        date: formatShortDate(chartData[i].date),
        x: chartData[i].x,
      });
    }
    // Always include last
    if (
      labels.length === 0 ||
      labels[labels.length - 1].index !== chartData.length - 1
    ) {
      labels.push({
        index: chartData.length - 1,
        date: formatShortDate(chartData[chartData.length - 1].date),
        x: chartData[chartData.length - 1].x,
      });
    }
    return labels;
  }, [chartData]);

  if (!data.length)
    return (
      <div className="bg-white rounded-2xl border border-[rgb(229,229,234)] p-6 shadow-sm h-[400px] flex items-center justify-center text-sm text-[rgb(142,142,147)]">
        暂无数据
      </div>
    );

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
      className="bg-white rounded-2xl border border-[rgb(229,229,234)] p-6 shadow-sm"
    >
      <h3 className="text-sm font-semibold text-[rgb(29,29,31)] mb-1">
        K 线图
      </h3>
      <p className="text-xs text-[rgb(142,142,147)] mb-4">
        叠加 MA5 / MA20 / MA60 均线
      </p>
      <div ref={containerRef} className="h-[400px] w-full">
        <svg width="100%" height="100%" viewBox={`0 0 ${dimensions.width} ${dimensions.height}`}>
          {/* Grid lines */}
          {yTicks.map((tick, i) => (
            <g key={i}>
              <line
                x1={PADDING.left}
                y1={yScale(tick)}
                x2={dimensions.width - PADDING.right}
                y2={yScale(tick)}
                stroke="rgb(229,229,234)"
                strokeWidth={0.5}
              />
              <text
                x={PADDING.left - 8}
                y={yScale(tick) + 4}
                textAnchor="end"
                fill="rgb(142,142,147)"
                fontSize={10}
              >
                {tick.toFixed(2)}
              </text>
            </g>
          ))}

          {/* X-axis labels */}
          {xLabels.map((label, i) => (
            <text
              key={i}
              x={label.x}
              y={dimensions.height - 8}
              textAnchor="middle"
              fill="rgb(142,142,147)"
              fontSize={10}
            >
              {label.date}
            </text>
          ))}

          {/* MA Lines */}
          {["ma5", "ma20", "ma60"].map((ma, mi) => {
            const color = ma === "ma5" ? "#ff9500" : ma === "ma20" ? "#0071e3" : "#8e8e93";
            const dash = ma === "ma60" ? "4,4" : "none";
            const width = ma === "ma5" ? 1.5 : ma === "ma20" ? 1.5 : 1;
            const points = chartData
              .filter((d) => d[ma as keyof typeof d] !== null)
              .map((d) => `${d.x},${yScale(d[ma as keyof typeof d] as number)}`)
              .join(" ");
            return points ? (
              <polyline
                key={mi}
                points={points}
                fill="none"
                stroke={color}
                strokeWidth={width}
                strokeDasharray={dash}
                opacity={0.8}
              />
            ) : null;
          })}

          {/* Candles */}
          {chartData.map((d, i) => {
            const isUp = d.close >= d.open;
            const color = isUp ? UP_COLOR : DOWN_COLOR;
            const yTop = yScale(Math.max(d.open, d.close));
            const yBottom = yScale(Math.min(d.open, d.close));
            const yHigh = yScale(d.high);
            const yLow = yScale(d.low);
            const halfW = Math.max(1, d.candleWidth / 2);

            return (
              <g key={i}>
                {/* Wick */}
                <line
                  x1={d.x}
                  y1={yHigh}
                  x2={d.x}
                  y2={yLow}
                  stroke={color}
                  strokeWidth={1}
                />
                {/* Body */}
                <rect
                  x={d.x - halfW}
                  y={yTop}
                  width={Math.max(1, d.candleWidth)}
                  height={Math.max(1, yBottom - yTop)}
                  fill={color}
                  rx={0.5}
                />
              </g>
            );
          })}
        </svg>
      </div>
    </motion.div>
  );
}

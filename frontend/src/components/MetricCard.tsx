"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/cn";

interface MetricCardProps {
  label: string;
  value: string;
  type?: "default" | "positive" | "negative";
  delay?: number;
}

export function MetricCard({
  label,
  value,
  type = "default",
  delay = 0,
}: MetricCardProps) {
  const isPercentage = label.includes("率") || label.includes("回撤");

  // 自动推断类型
  let inferredType = type;
  if (inferredType === "default" && isPercentage && value.startsWith("-")) {
    inferredType = "negative";
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        duration: 0.5,
        delay: delay * 0.08,
        ease: [0.16, 1, 0.3, 1],
      }}
      className="bg-white rounded-2xl border border-[rgb(229,229,234)] p-5 shadow-sm"
    >
      <p className="text-xs font-medium text-[rgb(142,142,147)] tracking-wide uppercase mb-1.5">
        {label}
      </p>
      <p
        className={cn(
          "text-xl font-semibold tracking-tight",
          inferredType === "positive" && "text-[rgb(52,199,89)]",
          inferredType === "negative" && "text-[rgb(255,59,48)]",
          inferredType === "default" && "text-[rgb(29,29,31)]"
        )}
      >
        {value}
      </p>
    </motion.div>
  );
}
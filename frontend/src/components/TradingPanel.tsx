"use client";

import { motion, AnimatePresence } from "framer-motion";
import {
  Wallet,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  RotateCcw,
  Plus,
  History,
  BarChart3,
  DollarSign,
  CheckCircle2,
  XCircle,
  Clock,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import {
  fetchTradingAccount,
  placeTradingOrder,
  fetchOrderHistory,
  resetTradingAccount,
  type TradingAccountResponse,
  type TradingOrderResult,
  type TradingOrdersResponse,
} from "@/lib/api";

interface TradingPanelProps {
  stockCode: string | null;
  stockName: string | null;
}

function formatTime(ts: string) {
  try {
    return ts.split(".")[0].replace("T", " ");
  } catch {
    return ts;
  }
}

function OrderStatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    filled: "bg-[rgb(52,199,89)]/10 text-[rgb(52,199,89)]",
    rejected: "bg-[rgb(255,59,48)]/10 text-[rgb(255,59,48)]",
    cancelled: "bg-[rgb(142,142,147)]/10 text-[rgb(142,142,147)]",
    pending: "bg-[rgb(255,149,0)]/10 text-[rgb(180,95,0)]",
    submitted: "bg-[rgb(0,113,227)]/10 text-[rgb(0,113,227)]",
  };
  const icons: Record<string, React.ReactNode> = {
    filled: <CheckCircle2 className="w-3 h-3" />,
    rejected: <XCircle className="w-3 h-3" />,
    cancelled: <XCircle className="w-3 h-3" />,
    pending: <Clock className="w-3 h-3" />,
    submitted: <Clock className="w-3 h-3" />,
  };
  const labels: Record<string, string> = {
    filled: "成交",
    rejected: "拒绝",
    cancelled: "撤销",
    pending: "待处理",
    submitted: "已提交",
  };

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium ${styles[status] || ""}`}>
      {icons[status] || null}
      {labels[status] || status}
    </span>
  );
}

export function TradingPanel({ stockCode, stockName }: TradingPanelProps) {
  const [account, setAccount] = useState<TradingAccountResponse | null>(null);
  const [orders, setOrders] = useState<TradingOrderResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [orderLoading, setOrderLoading] = useState(false);
  const [orderMsg, setOrderMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [activeTab, setActiveTab] = useState<"account" | "orders">("account");

  // Order form state
  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [qty, setQty] = useState(100);
  const [price, setPrice] = useState("");

  const loadAccount = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchTradingAccount("simulated");
      setAccount(data);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  const loadOrders = useCallback(async () => {
    try {
      const data = await fetchOrderHistory("simulated", 20);
      setOrders(data.orders);
    } catch {
      // ignore
    }
  }, []);

  const loadAll = useCallback(() => {
    loadAccount();
    loadOrders();
  }, [loadAccount, loadOrders]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const handleOrder = useCallback(async () => {
    if (!stockCode) return;
    setOrderLoading(true);
    setOrderMsg(null);
    try {
      const result = await placeTradingOrder({
        stock_code: stockCode,
        stock_name: stockName || "",
        side,
        order_type: price ? "limit" : "market",
        quantity: qty,
        price: price ? parseFloat(price) : null,
        mode: "simulated",
      });
      if (result.status === "filled") {
        setOrderMsg({ ok: true, text: `${side === "buy" ? "买入" : "卖出"}成功！` });
      } else {
        setOrderMsg({ ok: false, text: result.reject_reason || result.note || "订单被拒绝" });
      }
      loadAll();
    } catch (e) {
      setOrderMsg({ ok: false, text: e instanceof Error ? e.message : "下单失败" });
    } finally {
      setOrderLoading(false);
    }
  }, [stockCode, stockName, side, qty, price, loadAll]);

  const handleReset = useCallback(async () => {
    try {
      await resetTradingAccount("simulated", 100000);
      setOrderMsg({ ok: true, text: "模拟账户已重置" });
      loadAll();
    } catch {
      setOrderMsg({ ok: false, text: "重置失败" });
    }
  }, [loadAll]);

  const canPlaceOrder = stockCode && qty > 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-[rgb(245,245,247)] rounded-2xl p-6 shadow-sm"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-3">
          <Wallet className="w-5 h-5 text-[rgb(0,113,227)]" />
          <div>
            <h3 className="text-sm font-semibold text-[rgb(29,29,31)]">模拟交易</h3>
            <p className="text-xs text-[rgb(142,142,147)] mt-0.5">模拟账户 · 同花顺接口就绪</p>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={loadAll}
            disabled={loading}
            className="flex items-center gap-1 px-3 py-1.5 rounded-xl bg-white border border-[rgb(229,229,234)] text-xs font-semibold hover:bg-[rgb(245,245,247)] disabled:opacity-50 transition-all"
          >
            <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} />
            刷新
          </button>
          <button
            onClick={handleReset}
            className="flex items-center gap-1 px-3 py-1.5 rounded-xl bg-white border border-[rgb(229,229,234)] text-xs font-semibold hover:bg-[rgb(245,245,247)] transition-all"
          >
            <RotateCcw className="w-3 h-3" />
            重置
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-4 bg-[rgb(229,229,234)] rounded-lg p-0.5">
        <button
          onClick={() => setActiveTab("account")}
          className={`flex-1 py-1.5 text-xs font-semibold rounded-md transition-all ${
            activeTab === "account"
              ? "bg-white text-[rgb(29,29,31)] shadow-sm"
              : "text-[rgb(142,142,147)] hover:text-[rgb(29,29,31)]"
          }`}
        >
          账户 & 下单
        </button>
        <button
          onClick={() => setActiveTab("orders")}
          className={`flex-1 py-1.5 text-xs font-semibold rounded-md transition-all ${
            activeTab === "orders"
              ? "bg-white text-[rgb(29,29,31)] shadow-sm"
              : "text-[rgb(142,142,147)] hover:text-[rgb(29,29,31)]"
          }`}
        >
          订单历史
        </button>
      </div>

      {activeTab === "account" && (
        <div className="space-y-4">
          {/* Account Balance */}
          <div className="grid grid-cols-3 gap-2">
            <div className="bg-white rounded-xl border border-[rgb(229,229,234)] p-3">
              <p className="text-[10px] text-[rgb(142,142,147)] mb-1">总资产</p>
              <p className="text-sm font-bold text-[rgb(29,29,31)]">
                {account ? `¥${account.total_asset.toFixed(2)}` : "—"}
              </p>
            </div>
            <div className="bg-white rounded-xl border border-[rgb(229,229,234)] p-3">
              <p className="text-[10px] text-[rgb(142,142,147)] mb-1">可用资金</p>
              <p className="text-sm font-bold text-[rgb(52,199,89)]">
                {account ? `¥${account.available_cash.toFixed(2)}` : "—"}
              </p>
            </div>
            <div className="bg-white rounded-xl border border-[rgb(229,229,234)] p-3">
              <p className="text-[10px] text-[rgb(142,142,147)] mb-1">持仓市值</p>
              <p className="text-sm font-bold text-[rgb(0,113,227)]">
                {account ? `¥${account.market_value.toFixed(2)}` : "—"}
              </p>
            </div>
          </div>

          {/* Positions */}
          {account && account.positions.length > 0 && (
            <div className="bg-white rounded-xl border border-[rgb(229,229,234)] p-3">
              <p className="text-[10px] font-medium text-[rgb(142,142,147)] tracking-wide uppercase mb-2">当前持仓</p>
              <div className="space-y-1">
                {account.positions.map((p) => (
                  <div key={p.stock_code} className="flex items-center justify-between text-[10px] py-1">
                    <span className="font-medium text-[rgb(29,29,31)]">
                      {p.stock_name} <span className="text-[rgb(142,142,147)]">({p.stock_code})</span>
                    </span>
                    <span>
                      {p.quantity}股 · 成本 ¥{p.cost_price.toFixed(2)}
                      {p.profit_pct != null && (
                        <span className={p.profit_pct >= 0 ? "text-[rgb(52,199,89)] ml-1" : "text-[rgb(255,59,48)] ml-1"}>
                          {p.profit_pct >= 0 ? "+" : ""}{(p.profit_pct * 100).toFixed(1)}%
                        </span>
                      )}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Order Form */}
          <div className="bg-white rounded-xl border border-[rgb(229,229,234)] p-4">
            <p className="text-[10px] font-medium text-[rgb(142,142,147)] tracking-wide uppercase mb-3">下单</p>
            <div className="flex gap-2 mb-3">
              <button
                onClick={() => setSide("buy")}
                className={`flex-1 py-2 rounded-lg text-xs font-bold transition-all ${
                  side === "buy"
                    ? "bg-[rgb(52,199,89)] text-white"
                    : "bg-[rgb(245,245,247)] text-[rgb(142,142,147)]"
                }`}
              >
                <TrendingUp className="w-3 h-3 inline-block mr-1" />买入
              </button>
              <button
                onClick={() => setSide("sell")}
                className={`flex-1 py-2 rounded-lg text-xs font-bold transition-all ${
                  side === "sell"
                    ? "bg-[rgb(255,59,48)] text-white"
                    : "bg-[rgb(245,245,247)] text-[rgb(142,142,147)]"
                }`}
              >
                <TrendingDown className="w-3 h-3 inline-block mr-1" />卖出
              </button>
            </div>

            <div className="grid grid-cols-2 gap-2 mb-3">
              <div>
                <label className="text-[9px] text-[rgb(142,142,147)] block mb-1">股票</label>
                <div className="bg-[rgb(245,245,247)] rounded-lg px-3 py-2 text-xs text-[rgb(29,29,31)]">
                  {stockCode ? `${stockName || stockCode} (${stockCode})` : "请先选股"}
                </div>
              </div>
              <div>
                <label className="text-[9px] text-[rgb(142,142,147)] block mb-1">数量（股）</label>
                <input
                  type="number"
                  value={qty}
                  onChange={(e) => setQty(Math.max(0, parseInt(e.target.value) || 0))}
                  className="w-full bg-[rgb(245,245,247)] rounded-lg px-3 py-2 text-xs font-medium text-[rgb(29,29,31)] border-0 outline-none focus:ring-1 focus:ring-[rgb(0,113,227)]"
                  min={0}
                  step={100}
                />
              </div>
            </div>

            <div className="mb-3">
              <label className="text-[9px] text-[rgb(142,142,147)] block mb-1">
                限价（留空为市价单）
              </label>
              <input
                type="number"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                placeholder="市价"
                className="w-full bg-[rgb(245,245,247)] rounded-lg px-3 py-2 text-xs font-medium text-[rgb(29,29,31)] border-0 outline-none focus:ring-1 focus:ring-[rgb(0,113,227)]"
                min={0}
                step={0.01}
              />
            </div>

            <button
              onClick={handleOrder}
              disabled={!canPlaceOrder || orderLoading}
              className={`w-full py-2.5 rounded-xl text-xs font-bold text-white transition-all active:scale-[0.98] disabled:opacity-40 ${
                side === "buy" ? "bg-[rgb(52,199,89)] hover:bg-[rgb(45,180,80)]" : "bg-[rgb(255,59,48)] hover:bg-[rgb(230,50,40)]"
              }`}
            >
              {orderLoading ? (
                <span className="flex items-center justify-center gap-1">
                  <RefreshCw className="w-3 h-3 animate-spin" /> 处理中...
                </span>
              ) : (
                `${side === "buy" ? "买入" : "卖出"} ${qty}股`
              )}
            </button>

            {/* Order result message */}
            {orderMsg && (
              <div
                className={`mt-2 p-2 rounded-lg text-[10px] flex items-center gap-1 ${
                  orderMsg.ok
                    ? "bg-[rgb(52,199,89)]/10 text-[rgb(52,199,89)]"
                    : "bg-[rgb(255,59,48)]/10 text-[rgb(255,59,48)]"
                }`}
              >
                {orderMsg.ok ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                {orderMsg.text}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Orders Tab */}
      {activeTab === "orders" && (
        <div className="space-y-2">
          {orders.length === 0 ? (
            <div className="text-center py-8">
              <History className="w-6 h-6 text-[rgb(199,199,204)] mx-auto mb-2" />
              <p className="text-xs text-[rgb(142,142,147)]">暂无订单记录</p>
            </div>
          ) : (
            orders.map((o) => (
              <div key={o.order_id} className="bg-white rounded-xl border border-[rgb(229,229,234)] p-3">
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-[rgb(29,29,31)]">
                      {o.stock_name || o.stock_code}
                    </span>
                    <span className={`text-[10px] ${o.side === "buy" ? "text-[rgb(52,199,89)]" : "text-[rgb(255,59,48)]"}`}>
                      {o.side === "buy" ? "买入" : "卖出"}
                    </span>
                  </div>
                  <OrderStatusBadge status={o.status} />
                </div>
                <div className="text-[9px] text-[rgb(142,142,147)]">
                  {o.quantity}股{o.price ? ` @ ¥${o.price.toFixed(2)}` : " 市价"}
                  {o.filled_quantity > 0 && ` · 成交 ${o.filled_quantity}股`}
                  {o.note && ` · ${o.note}`}
                  {o.reject_reason && ` · ${o.reject_reason}`}
                </div>
                <div className="text-[9px] text-[rgb(199,199,204)] mt-0.5">{formatTime(o.created_at)}</div>
              </div>
            ))
          )}
        </div>
      )}
    </motion.div>
  );
}
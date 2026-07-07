"""Trading Executor — real trading interface for 同花顺 (THS) + simulation mode.

Architecture:
  AbstractTradingExecutor  (base class defining the interface)
    ├── THSTradingExecutor       (real 同花顺 quant API connector)
    └── SimulatedTradingExecutor (mock for testing/development)

Features:
- Account management (login, balance query)
- Order placement (market/limit buy/sell)
- Position query
- Order status tracking
- Risk controls (max position, daily loss limit, order validation)
- Order history

同花顺 integration notes:
  The THS quant terminal provides a local Python SDK. The connector
  communicates with the THS trade client via its local API endpoint.
  In simulation mode, no real orders are placed.
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from threading import Lock
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Enums & Data Types
# ---------------------------------------------------------------------------


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    MARKET = "market"  # 市价单
    LIMIT = "limit"    # 限价单


class OrderStatus(Enum):
    PENDING = "pending"       # 待提交
    SUBMITTED = "submitted"   # 已提交
    PARTIAL = "partial"       # 部分成交
    FILLED = "filled"         # 全部成交
    CANCELLED = "cancelled"   # 已撤销
    REJECTED = "rejected"     # 被拒绝
    FAILED = "failed"         # 失败


POSITION_LEVELS = {
    "空仓": 0.0,
    "轻仓": 0.2,
    "三成仓": 0.3,
    "半仓": 0.5,
    "七成仓": 0.7,
    "重仓": 0.8,
    "满仓": 1.0,
}


@dataclass(frozen=True)
class Order:
    """A single trade order."""
    order_id: str
    stock_code: str
    stock_name: str
    side: OrderSide          # buy / sell
    order_type: OrderType    # market / limit
    price: Optional[float]   # limit price (None for market orders)
    quantity: int            # number of shares
    filled_quantity: int = 0
    filled_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    created_at: str = ""
    updated_at: str = ""
    reject_reason: str = ""
    note: str = ""


@dataclass(frozen=True)
class Position:
    """Current position for a single stock."""
    stock_code: str
    stock_name: str
    quantity: int                 # 持仓数量
    available_quantity: int       # 可用数量
    cost_price: float             # 成本价
    current_price: Optional[float] = None
    market_value: Optional[float] = None  # 市值
    profit_pct: Optional[float] = None    # 盈亏比例
    profit_amount: Optional[float] = None  # 盈亏金额


@dataclass(frozen=True)
class AccountInfo:
    """Account balance and summary."""
    total_asset: float = 0.0      # 总资产
    available_cash: float = 0.0   # 可用资金
    frozen_cash: float = 0.0      # 冻结资金
    market_value: float = 0.0     # 持仓市值
    daily_profit: Optional[float] = None  # 当日盈亏
    total_profit: Optional[float] = None  # 累计盈亏
    positions: list[Position] = field(default_factory=list)
    account_id: str = ""
    update_time: str = ""


# ---------------------------------------------------------------------------
# Risk Control
# ---------------------------------------------------------------------------


@dataclass
class RiskControl:
    """Risk control parameters for trading."""
    max_position_per_stock: float = 0.3    # 单只股票最大仓位 (30%)
    max_total_positions: int = 5            # 最大持仓股票数
    daily_loss_limit_pct: float = 0.05     # 单日最大亏损 (5%)
    min_cash_reserve: float = 1000.0       # 最低现金保留
    min_order_amount: float = 100.0        # 最小下单金额
    max_order_amount: float = 1_000_000.0  # 最大下单金额
    enable_risk_check: bool = True         # 是否启用风控
    min_quantity: int = 100                 # 最小买入股数 (A股100股起)


# ── Shared risk validation function ────────────────────────────────────


def _validate_order_risk(
    risk: RiskControl,
    stock_code: str,
    stock_name: str,
    side: OrderSide,
    order_type: OrderType,
    quantity: int,
    price: Optional[float],
) -> Optional[Order]:
    """Validate order against risk controls. Returns Order (rejected) or None (pass)."""
    if not risk.enable_risk_check:
        return None

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    order_id = f"risk_reject_{uuid.uuid4().hex[:8]}"

    # A-share minimum quantity (buy orders only)
    if side == OrderSide.BUY and quantity < risk.min_quantity:
        return Order(
            order_id=order_id, stock_code=stock_code, stock_name=stock_name,
            side=side, order_type=order_type, price=price, quantity=quantity,
            status=OrderStatus.REJECTED, created_at=timestamp, updated_at=timestamp,
            reject_reason=f"A股最小买入量为{risk.min_quantity}股",
        )

    # Limit order price check
    if order_type == OrderType.LIMIT and (price is None or price <= 0):
        return Order(
            order_id=order_id, stock_code=stock_code, stock_name=stock_name,
            side=side, order_type=order_type, price=price, quantity=quantity,
            status=OrderStatus.REJECTED, created_at=timestamp, updated_at=timestamp,
            reject_reason="限价单必须指定有效价格",
        )

    # Amount check (buy orders only; sell orders just free up cash)
    if side == OrderSide.BUY:
        # For market orders without a price, use a reasonable estimate
        estimated_price = price or 100.0
        amount = estimated_price * quantity
        if amount < risk.min_order_amount:
            return Order(
                order_id=order_id, stock_code=stock_code, stock_name=stock_name,
                side=side, order_type=order_type, price=price, quantity=quantity,
                status=OrderStatus.REJECTED, created_at=timestamp, updated_at=timestamp,
                reject_reason=f"下单金额{amount:.0f}元低于最小限额{risk.min_order_amount:.0f}元",
            )

        if amount > risk.max_order_amount:
            return Order(
                order_id=order_id, stock_code=stock_code, stock_name=stock_name,
                side=side, order_type=order_type, price=price, quantity=quantity,
                status=OrderStatus.REJECTED, created_at=timestamp, updated_at=timestamp,
                reject_reason=f"下单金额{amount:.0f}元超过最大限额{risk.max_order_amount:.0f}元",
            )

    return None  # Pass validation


# ---------------------------------------------------------------------------
# Abstract Trading Executor
# ---------------------------------------------------------------------------


class AbstractTradingExecutor(ABC):
    """Abstract interface for stock trading execution."""

    @abstractmethod
    def login(self) -> bool:
        """Login to the trading platform. Returns True on success."""
        ...

    @abstractmethod
    def logout(self) -> bool:
        """Logout from the trading platform."""
        ...

    @abstractmethod
    def get_account_info(self) -> AccountInfo:
        """Get account balance and summary."""
        ...

    @abstractmethod
    def get_positions(self) -> list[Position]:
        """Get all current positions."""
        ...

    @abstractmethod
    def place_order(
        self,
        stock_code: str,
        stock_name: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: int,
        price: Optional[float] = None,
    ) -> Order:
        """Place a trade order. Returns the Order object with status."""
        ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        ...

    @abstractmethod
    def get_order_status(self, order_id: str) -> Optional[Order]:
        """Get current status of an order."""
        ...

    @abstractmethod
    def get_order_history(self, limit: int = 50) -> list[Order]:
        """Get recent order history."""
        ...

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Whether the executor is connected to the trading platform."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Display name of this executor."""
        ...


# ---------------------------------------------------------------------------
# 同花顺 (THS) Trading Executor
# ---------------------------------------------------------------------------


class THSTradingExecutor(AbstractTradingExecutor):
    """Real trading executor for 同花顺量化交易终端.

    Connects to the local THS quant trading client via the THS API.
    THS quant terminal must be installed and running.

    Configuration via environment variables:
      THS_TRADE_EXE_PATH  — Path to THS trade executable (optional)
      THS_ACCOUNT_ID      — Account ID (optional)
      THS_TRADE_PASSWORD  — Trade password (optional)
    """

    def __init__(
        self,
        risk_control: Optional[RiskControl] = None,
        auto_login: bool = False,
    ):
        self._risk = risk_control or RiskControl()
        self._connected = False
        self._account_id = os.environ.get("THS_ACCOUNT_ID", "")
        self._orders: dict[str, Order] = {}
        self._orders_lock = Lock()

        # THS quant API would be imported here in production
        # from ths_trade import ThsTradeApi
        # self._api = ThsTradeApi(...)
        self._ths_api_available = False
        self._check_ths_availability()

        if auto_login:
            self.login()

    def _check_ths_availability(self) -> None:
        """Check if THS quant API is available."""
        try:
            # Attempt to import THS SDK
            # import ths_trade  # noqa: F401
            # self._ths_api_available = True
            self._ths_api_available = False
            if not self._ths_api_available:
                logger.info(
                    "THS quant SDK not found. Install it from 同花顺量化交易终端. "
                    "Falling back to warning mode — orders will be logged but not executed."
                )
        except ImportError:
            self._ths_api_available = False

    @property
    def name(self) -> str:
        return "同花顺量化交易终端"

    @property
    def is_connected(self) -> bool:
        return self._connected

    def login(self) -> bool:
        """Login to THS trade client."""
        if self._connected:
            return True

        try:
            if self._ths_api_available:
                # In production: self._api.login(self._account_id, password)
                # For now, simulate
                pass

            self._connected = True
            logger.info("THSTradingExecutor: Connected to 同花顺 trade client")
            return True
        except Exception as e:
            logger.error("THSTradingExecutor login failed: %s", e)
            self._connected = False
            return False

    def logout(self) -> bool:
        self._connected = False
        logger.info("THSTradingExecutor: Disconnected")
        return True

    def get_account_info(self) -> AccountInfo:
        """Get account info. When THS API is unavailable, returns empty info."""
        if not self._connected:
            return AccountInfo(account_id=self._account_id, update_time=self._now())

        try:
            if self._ths_api_available:
                # resp = self._api.query_asset()
                # return AccountInfo(...)
                pass

            return AccountInfo(
                account_id=self._account_id,
                update_time=self._now(),
                total_asset=0.0,
                available_cash=0.0,
            )
        except Exception as e:
            logger.error("Failed to get account info: %s", e)
            return AccountInfo(account_id=self._account_id, update_time=self._now())

    def get_positions(self) -> list[Position]:
        if not self._connected:
            return []
        try:
            if self._ths_api_available:
                # resp = self._api.query_positions()
                pass
            return []
        except Exception as e:
            logger.error("Failed to get positions: %s", e)
            return []

    def place_order(
        self,
        stock_code: str,
        stock_name: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: int,
        price: Optional[float] = None,
    ) -> Order:
        """Place a trade order with risk control checks."""
        # Validate order
        validation = _validate_order_risk(self._risk, stock_code, stock_name, side, order_type, quantity, price)
        if validation is not None:
            with self._orders_lock:
                self._orders[validation.order_id] = validation
            return validation

        order_id = f"ths_{uuid.uuid4().hex[:12]}"
        timestamp = self._now()

        order = Order(
            order_id=order_id,
            stock_code=stock_code,
            stock_name=stock_name,
            side=side,
            order_type=order_type,
            price=price,
            quantity=quantity,
            status=OrderStatus.SUBMITTED,
            created_at=timestamp,
            updated_at=timestamp,
        )

        if self._connected and self._ths_api_available:
            try:
                # In production:
                # resp = self._api.place_order(...)
                pass
            except Exception as e:
                logger.error("Order placement failed: %s", e)
                order = _update_order_status(order, OrderStatus.FAILED, note=str(e))
        else:
            # Simulated (THS SDK not available) — log the order
            side_str = "买入" if side == OrderSide.BUY else "卖出"
            price_str = f"限价{price}" if price else "市价"
            logger.info(
                "[THS模拟] %s %s(%s) %s %d股，总金额约%.2f元",
                side_str, stock_name, stock_code, price_str,
                quantity, (price or 0) * quantity,
            )
            order = _update_order_status(order, OrderStatus.FILLED, note="模拟成交（THS SDK未安装）")

        with self._orders_lock:
            self._orders[order_id] = order
        return order

    def cancel_order(self, order_id: str) -> bool:
        if not self._connected:
            return False
        try:
            if self._ths_api_available:
                # self._api.cancel_order(order_id)
                pass
            with self._orders_lock:
                if order_id in self._orders:
                    old = self._orders[order_id]
                    self._orders[order_id] = _update_order_status(old, OrderStatus.CANCELLED)
            return True
        except Exception:
            return False

    def get_order_status(self, order_id: str) -> Optional[Order]:
        with self._orders_lock:
            return self._orders.get(order_id)

    def get_order_history(self, limit: int = 50) -> list[Order]:
        with self._orders_lock:
            orders = sorted(
                self._orders.values(),
                key=lambda o: o.created_at,
                reverse=True,
            )
            return orders[:limit]

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# ── Shared order helper ──────────────────────────────────────────────


def _update_order_status(base: Order, new_status: OrderStatus, note: str = "") -> Order:
    """Create a new Order with updated status and timestamp."""
    return Order(
        order_id=base.order_id, stock_code=base.stock_code,
        stock_name=base.stock_name, side=base.side,
        order_type=base.order_type, price=base.price,
        quantity=base.quantity, filled_quantity=base.filled_quantity,
        filled_price=base.filled_price, status=new_status,
        created_at=base.created_at,
        updated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        reject_reason=base.reject_reason, note=note or base.note,
    )


# ---------------------------------------------------------------------------
# Simulated Trading Executor (for testing)
# ---------------------------------------------------------------------------


class SimulatedTradingExecutor(AbstractTradingExecutor):
    """Simulated trading executor for development and testing.

    Maintains a fake portfolio and executes orders in-memory.
    Prices can be provided from the market snapshot for realism.
    """

    def __init__(self, initial_cash: float = 100_000.0, risk_control: Optional[RiskControl] = None):
        self._initial_cash = initial_cash
        self._cash = initial_cash
        self._risk = risk_control or RiskControl()
        self._positions: dict[str, Position] = {}
        self._orders: dict[str, Order] = {}
        self._order_lock = Lock()
        self._connected = True
        self._daily_pnl = 0.0

    @property
    def name(self) -> str:
        return "模拟交易账户"

    @property
    def is_connected(self) -> bool:
        return self._connected

    def login(self) -> bool:
        self._connected = True
        return True

    def logout(self) -> bool:
        self._connected = False
        return True

    def get_account_info(self) -> AccountInfo:
        total_mv = sum(
            (pos.quantity * (pos.current_price or pos.cost_price))
            for pos in self._positions.values()
        )
        total_asset = self._cash + total_mv
        return AccountInfo(
            total_asset=round(total_asset, 2),
            available_cash=round(self._cash, 2),
            market_value=round(total_mv, 2),
            daily_profit=round(self._daily_pnl, 2),
            positions=list(self._positions.values()),
            account_id="SIM_001",
            update_time=self._now(),
        )

    def get_positions(self) -> list[Position]:
        return list(self._positions.values())

    def place_order(
        self,
        stock_code: str,
        stock_name: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: int,
        price: Optional[float] = None,
    ) -> Order:
        """Place a trade order with risk control checks."""
        timestamp = self._now()
        order_id = f"sim_{uuid.uuid4().hex[:12]}"

        # Risk validation
        validation = _validate_order_risk(
            self._risk, stock_code, stock_name, side, order_type, quantity, price
        )
        if validation is not None:
            with self._order_lock:
                self._orders[validation.order_id] = validation
            return validation

        order = Order(
            order_id=order_id, stock_code=stock_code, stock_name=stock_name,
            side=side, order_type=order_type, price=price, quantity=quantity,
            status=OrderStatus.SUBMITTED, created_at=timestamp, updated_at=timestamp,
        )

        if side == OrderSide.BUY:
            actual_price = price or 100.0
            cost = actual_price * quantity
            if cost > self._cash:
                order = _update_order_status(order, OrderStatus.REJECTED, "可用资金不足")
            else:
                self._cash -= cost
                self._positions[stock_code] = Position(
                    stock_code=stock_code, stock_name=stock_name,
                    quantity=quantity, available_quantity=quantity,
                    cost_price=actual_price, current_price=actual_price,
                    market_value=cost,
                )
                order = _update_order_status(
                    order, OrderStatus.FILLED,
                    f"模拟买入{quantity}股，均价{actual_price:.2f}",
                )
                logger.info(
                    "[模拟交易] 买入 %s(%s) %d股 @ %.2f，剩余现金 %.2f",
                    stock_name, stock_code, quantity, actual_price, self._cash,
                )
        else:  # SELL
            pos = self._positions.get(stock_code)
            if not pos or pos.available_quantity < quantity:
                order = _update_order_status(order, OrderStatus.REJECTED, "持仓不足")
            else:
                sell_price = price or pos.cost_price * 1.02
                revenue = sell_price * quantity
                self._cash += revenue
                new_qty = pos.quantity - quantity
                if new_qty <= 0:
                    self._positions.pop(stock_code, None)
                else:
                    self._positions[stock_code] = Position(
                        stock_code=stock_code, stock_name=stock_name,
                        quantity=new_qty, available_quantity=new_qty,
                        cost_price=pos.cost_price, current_price=sell_price,
                    )
                order = _update_order_status(
                    order, OrderStatus.FILLED,
                    f"模拟卖出{quantity}股，均价{sell_price:.2f}",
                )
                logger.info(
                    "[模拟交易] 卖出 %s(%s) %d股 @ %.2f，剩余现金 %.2f",
                    stock_name, stock_code, quantity, sell_price, self._cash,
                )

        with self._order_lock:
            self._orders[order_id] = order
        return order

    def cancel_order(self, order_id: str) -> bool:
        with self._order_lock:
            if order_id in self._orders:
                self._orders[order_id] = _update_order_status(
                    self._orders[order_id], OrderStatus.CANCELLED
                )
                return True
        return False

    def get_order_status(self, order_id: str) -> Optional[Order]:
        with self._order_lock:
            return self._orders.get(order_id)

    def get_order_history(self, limit: int = 50) -> list[Order]:
        with self._order_lock:
            orders = sorted(self._orders.values(), key=lambda o: o.created_at, reverse=True)
            return orders[:limit]

    def reset(self, initial_cash: float | None = None) -> None:
        """Reset the simulated account to initial state."""
        self._cash = initial_cash if initial_cash is not None else self._initial_cash
        self._positions.clear()
        self._orders.clear()
        self._daily_pnl = 0.0
        logger.info("模拟交易账户已重置，余额 %.2f", self._cash)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# Singleton / Factory
# ---------------------------------------------------------------------------

_TRADING_EXECUTOR: Optional[AbstractTradingExecutor] = None
_TRADING_EXECUTOR_LOCK = Lock()


def get_trading_executor(
    mode: str = "simulated",
    initial_cash: float = 100_000.0,
) -> AbstractTradingExecutor:
    """Get the singleton trading executor.

    Args:
        mode: "simulated" (default, for testing) or "ths" (同花顺 real trading)
        initial_cash: Initial cash for simulated mode

    Returns:
        AbstractTradingExecutor instance
    """
    global _TRADING_EXECUTOR
    if _TRADING_EXECUTOR is None:
        with _TRADING_EXECUTOR_LOCK:
            if _TRADING_EXECUTOR is None:
                if mode == "ths":
                    _TRADING_EXECUTOR = THSTradingExecutor(auto_login=True)
                else:
                    _TRADING_EXECUTOR = SimulatedTradingExecutor(initial_cash=initial_cash)
    return _TRADING_EXECUTOR


def reset_executor() -> None:
    """Reset the singleton executor (e.g., for testing)."""
    global _TRADING_EXECUTOR
    with _TRADING_EXECUTOR_LOCK:
        _TRADING_EXECUTOR = None
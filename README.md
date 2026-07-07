# 股海秘籍 — AI 辅助选股系统

> v2.1 | AI 选股 · 多技术指标 · 多周期分析 · 组合回测 · 模拟交易

---

## 核心功能

- **双均线策略回测** — MA5/MA20 金叉死叉 + MA60 趋势过滤 + T+1 执行
- **AI 辅助选股** — 8因子评分 + 5大技术指标 + 财务数据 + AI 买卖建议（买入区间/目标价/止损位/仓位）
- **技术指标引擎** — MACD · RSI · 布林带 · KDJ · ATR，纯 pandas 实现
- **多周期分析** — 日/周/月三周期指标对比，共振判断
- **组合回测** — Kelly 公式 / 等权重 / 风险平价三种资金策略
- **模拟交易** — 内建 100 万模拟账户 + 同花顺实盘接口
- **前端可视化** — 8因子评分卡、技术指标信号、K 线趋势图、多股叠加对比、组合权益曲线
- **新手友好** — "适合关注 / 暂不建议 / 高风险观望" 三级标签
- **移动端适配** — 触控友好、响应式、iOS 安全区

---

## 快速开始

```bash
# 后端
pip install akshare pandas fastapi uvicorn pydantic httpx anthropic
cd backend && python api.py

# 前端
cd frontend && npm install && npm run dev
```

浏览器打开 `http://localhost:3000`

---

## 项目结构

```
stock_project/
├── backend/
│   ├── api.py                    # FastAPI 入口
│   ├── advisor_router.py         # 全部 API 路由（选股+指标+交易+组合）
│   ├── ai_stock_advisor.py       # 主编排服务
│   ├── ai_decision_service.py    # AI 决策（买卖点位/仓位建议）
│   ├── scoring_engine.py         # 8因子评分 + 技术指标增强
│   ├── technical_indicators.py   # MACD/RSI/布林带/KDJ/ATR
│   ├── financial_analyzer.py     # PE/PB/ROE 财务分析
│   ├── portfolio_backtest.py     # 组合回测 + 资金管理
│   ├── trading_executor.py       # 模拟交易 + 同花顺接口
│   ├── market_service.py         # 实时行情 + 快照版本控制
│   ├── backtest_engine.py        # 双均线策略回测引擎
│   ├── beginner_output.py        # 新手友好格式化
│   └── judgement/                # AI 研判模块（多模型客户端）
│
├── frontend/
│   └── src/
│       ├── app/page.tsx          # 主页面
│       ├── components/
│       │   ├── StockAnalysisPanel.tsx    # AI 深度分析（8因子+指标+财务）
│       │   ├── PortfolioBacktestPanel.tsx # 组合回测
│       │   ├── TradingPanel.tsx          # 模拟交易
│       │   └── ...                       # 市场概览/对比/趋势图/K线
│       └── lib/api.ts            # 全部类型定义 + API 调用
│
└── tests/
```

---

## 工作原理

```
akshare 实时行情 + 财务数据
      ↓
MarketDataService（5分钟缓存 + snapshot_id 版本控制）
      ↓
     ├── TechnicalIndicators → MACD/RSI/BB/KDJ/ATR 信号 → 增强趋势评分
     ├── FinancialAnalyzer → PE/PB/ROE/增长率
     ├── ScoringEngine → 8因子综合排名（0-100分）
     ├── AIDecisionService → Claude/GPT → 买入区间/目标价/止损/仓位
     ├── PortfolioBacktest → Kelly/等权/风险平价 → 组合收益
     └── Frontend Display → 评分卡 + 指标 + 趋势图 + 交易面板
```

**评分模型**：趋势强度(25%) + 量能(15%) + 波动收益(13%) + AI信心(10%) + 动量(7%) + 估值(12%) + 盈利(10%) + 成长(8%) = 100%

---

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python · FastAPI · pandas · akshare |
| AI | Claude / GPT / DeepSeek / Gemini / 豆包 / 通义千问 |
| 前端 | Next.js 16 · Tailwind CSS 4 · TypeScript · Recharts |
| 交易 | 模拟引擎（内存） + 同花顺量化交易终端 SDK |
| 数据 | akshare（新浪/东方财富源）+ parquet 本地缓存 |

---

## 免责声明

> **AI仅提供参考意见，一切交易以个人决策为准。**
> 本系统所有分析基于历史和公开数据，不构成投资建议。股市有风险，投资需谨慎。

---

## 已知问题

- 实时数据有 3-5 分钟延迟（新浪源限制）
- 股票池当前仅 18 只 A 股核心标的
- AI 分析结果不可作为交易依据
- 同花顺实盘需额外安装量化交易终端
- 财务数据依赖季报/年报，存在更新滞后

---

*股海秘籍 © 2026 · v2.1*

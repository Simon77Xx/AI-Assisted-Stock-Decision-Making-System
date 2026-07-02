# 股海秘籍 — AI 辅助选股系统

> 从"双均线回测工具"升级为"AI辅助选股决策系统"

A 股双均线趋势策略回测 + AI 辅助选股平台，支持实时市场数据、多股票评分排名、新手友好输出。

## 核心功能

| 功能 | 说明 |
|------|------|
| **双均线策略回测** | MA5/MA20 金叉死叉信号 + MA60 趋势过滤器 + T+1 执行 |
| **实时市场数据** | 通过 akshare 获取 A 股准实时行情，5 分钟 TTL 缓存 |
| **多股票评分排名** | 5 维度加权评分（趋势/量能/波动收益/AI信心/动量），Top N 排名 |
| **AI 辅助选股** | 基于市场状态 + 技术指标 + 评分的 AI 分析，输出选股建议 |
| **新手友好输出** | "适合关注/暂不建议/高风险观望"，避免专业术语堆砌 |
| **策略 vs AI 一致性** | 双均线策略信号与 AI 判断对比，输出一致/不一致及原因 |
| **风险控制** | 数据时间戳绑定、禁止绝对性预测、数据版本控制 |

## 快速开始

### 前置依赖

- Python ≥ 3.10
- Node.js ≥ 18
- npm ≥ 9

### 1. 安装依赖

```bash
# Python 依赖
pip install akshare pandas fastapi uvicorn pydantic httpx anthropic

# 前端依赖
cd frontend && npm install
```

### 2. 启动后端

```bash
cd backend
python api.py
```

后端默认运行在 `http://localhost:8000`

### 3. 启动前端（可选）

新开一个终端：

```bash
cd frontend
npm run dev
```

浏览器打开 `http://localhost:3000`

### 4. 配置 AI（可选）

在 `backend/.env` 或 `backend/.env.local` 中配置：

```env
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxx
```

支持 6 种 AI 提供商：Anthropic、OpenAI、DeepSeek、Gemini、豆包、通义千问。

## 项目结构

```
stock_project/
├── backend/                      # Python 后端
│   ├── api.py                    # FastAPI 入口（所有 API 路由）
│   ├── backtest_engine.py        # 双均线策略 + 回测 + 指标计算
│   ├── data_fetcher.py           # akshare 数据获取 + parquet 缓存
│   ├── market_service.py         # 实时市场数据层（TTL 缓存、快照版本控制）
│   ├── scoring_engine.py         # 多股票评分引擎（5 维度加权）
│   ├── ai_decision_service.py    # AI 选股决策（市场状态 + 风险判断）
│   ├── ai_stock_advisor.py       # 主编排服务（串联所有模块）
│   ├── strategy_ai_compare.py    # 策略 vs AI 一致性对比
│   ├── beginner_output.py        # 新手友好输出格式化
│   ├── advisor_router.py         # AI 选股 API 路由
│   ├── judgement/                # AI 研判模块
│   │   ├── client.py             #   多模型 AI 客户端
│   │   ├── service.py            #   业务逻辑（prompt → 解析 → 缓存）
│   │   ├── router.py             #   FastAPI 路由
│   │   └── state.py              #   回测快照存储
│   ├── cache/                    # parquet 数据缓存
│   ├── .env.example              # API Key 配置示例
│   └── .env.local                # 本地环境变量（忽略）
│
├── frontend/                     # 前端（React + Next.js）
│   ├── src/
│   │   ├── app/                  # Next.js App Router
│   │   │   ├── layout.tsx        #   根布局
│   │   │   └── page.tsx          #   主页面
│   │   ├── components/           # UI 组件
│   │   │   ├── Navbar.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   ├── MetricCard.tsx
│   │   │   ├── CandlestickChart.tsx
│   │   │   ├── EquityCurve.tsx
│   │   │   └── AIJudgementPanel.tsx
│   │   └── lib/
│   │       ├── api.ts            # API 客户端 + 类型定义
│   │       └── cn.ts             # Tailwind 工具
│   ├── package.json
│   ├── next.config.ts
│   └── tsconfig.json
│
├── tests/                        # Python 测试
│   ├── conftest.py
│   ├── test_position_state.py
│   ├── test_backtest_snapshot.py
│   └── test_abnormal_stocks.py
│
├── prompt/                       # 项目设计文档
└── README.md
```

## API 端点

### 原有回测 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/backtest` | 单股票双均线回测 |
| POST | `/api/ai-judgement` | AI 技术研判（看多/看空/中性） |
| GET | `/api/health` | 健康检查 |

### 新增 AI 选股 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/advisor/market-overview` | 市场概览 + 多股票排名 |
| POST | `/api/advisor/analyze-stock?stock_code=000001` | 单股票深度分析（评分+AI+一致性） |
| GET | `/api/advisor/full-output?selected_stock=000001` | 完整系统输出 |
| POST | `/api/advisor/refresh` | 强制刷新市场数据 |
| GET | `/api/advisor/health` | 健康检查 |

### 完整输出格式

```json
{
  "market_state": {"state": "bull", "timestamp": "...", "snapshot_id": "..."},
  "top_stocks": [
    {"stock": "000001", "score": 87.2, "reason": "上涨趋势增强；成交量放大"}
  ],
  "selected_stock_analysis": {},
  "ai_recommendation": {
    "decision": "推荐",
    "reasoning": "上涨趋势增强，成交量放大，市场情绪偏强",
    "risk_level": "Low",
    "confidence": 0.85,
    "alternatives": ["000002", "000333"]
  },
  "risk_warning": {
    "risk_level": "Low",
    "data_timestamp": "2026-07-02 14:30:00",
    "disclaimer": "以上分析仅基于历史技术指标和实时市场数据的辅助参考，不构成投资建议。"
  },
  "timestamp": "2026-07-02 14:30:00"
}
```

## 策略说明

- **双均线策略**：MA5 上穿 MA20 且处于趋势市 → 买入；MA5 下穿 MA20 → 卖出
- **趋势过滤器**：收盘价在 MA60 上方时才视为趋势市，非趋势市空仓
- **T+1 执行**：信号在 T 日收盘后生成，T+1 日开盘执行，无未来数据
- **评分模型**：`score = trend_strength * 0.35 + volume_signal * 0.2 + volatility_adjusted_return * 0.2 + ai_confidence * 0.15 + momentum_score * 0.1`
- **数据源**：akshare 前复权数据，本地 parquet 缓存
- **数据版本控制**：所有分析绑定 `snapshot_id`，禁止使用过期数据

## 技术栈

### Python 后端
- `FastAPI` + `uvicorn` — REST API
- `akshare` — A 股实时行情 + 历史数据
- `pandas` / `numpy` — 数据处理与回测
- `pydantic` — 数据模型与验证
- `httpx` / `anthropic` — AI 模型客户端

### 前端
- `Next.js 16` — React 框架
- `Tailwind CSS 4` — 样式
- `Framer Motion` — 动画
- `Recharts` — 收益曲线图表
- `Lucide React` — 图标

### 设计风格
Apple 设计语言：SF Pro 字体、大圆角卡片、毛玻璃导航、克制配色、大间距布局。

## 模块说明

### 回测引擎 (`backend/backtest_engine.py`)
- `compute_signals()` — MA 计算 + 金叉/死叉 + 趋势过滤 + T+1 延迟
- `run_backtest()` — 策略日收益率、累积收益率
- `compute_metrics()` — 累计收益、最大回撤、夏普比率、胜率

### 市场数据层 (`backend/market_service.py`)
- `MarketDataService` — 准实时行情获取 + TTL 缓存（5 分钟）
- `MarketSnapshot` — 快照数据版本控制（snapshot_id）
- 支持 18 只 A 股核心股票池（可扩展）

### 评分引擎 (`backend/scoring_engine.py`)
- 5 维度加权评分，输出 0-100 分
- 每只股票附带 plain-language 评分理由
- 支持 AI 信心分数动态更新

### AI 选股决策 (`backend/ai_decision_service.py`)
- 增强上下文：市场状态 + 股票评分 + 技术指标
- 结构化输出：决策/理由/风险等级/信心指数/替代推荐
- 禁止绝对性预测，必须使用概率性语言

### 新手输出 (`backend/beginner_output.py`)
- "适合关注 / 暂不建议 / 高风险观望" 三级决策
- 自动过滤专业术语（MA/RSI 等）
- 风险提示 + 替代推荐

## 运行测试

```bash
cd backend
python -m pytest ../tests/ -v
```

## 许可证

仅供学习参考，不构成投资建议。

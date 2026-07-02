# 股海秘籍 — 双均线趋势策略回测平台

A 股双均线趋势策略回测工具，支持参数可调回测、AI 辅助研判，拥有 Apple 风格的前端界面。

## 功能概览

- **数据获取** — 通过 akshare 获取 A 股日线数据（前复权 `qfq`），本地 parquet 缓存 + 交易日元数据校验，避免重复请求
- **双均线策略回测** — MA5 / MA20 金叉死叉信号，MA60 趋势过滤器，T+1 日执行（严格 `shift(1)` 隔离，无未来数据）
- **绩效指标** — 累计收益率、年化收益率、最大回撤、夏普比率、胜率、交易次数，并与"买入持有"基准对比
- **K 线可视化** — SVG K 线图叠加 MA5/MA20/MA60 均线
- **收益曲线** — 策略收益 vs 基准收益对比
- **AI 辅助研判** — 基于回测结果的结构化技术指标，调用多模型 AI（Claude / GPT / DeepSeek / Gemini / 豆包 / 通义千问）生成方向性判断（看多/看空/中性）

## 项目结构

```
stock_project/
├── data_fetcher.py          # 数据获取 + parquet 缓存
├── backtest_engine.py       # 双均线策略 + 回测逻辑 + 指标计算
├── app.py                   # (旧) Streamlit 前端
├── cache/                   # parquet 数据缓存
├── prompt/                  # 项目设计文档
│   ├── 股海秘籍_项目提示词.md
│   └── AI研判模块_提示词.md
│
└── frontend/                # 前端（React + Next.js + FastAPI）
    ├── api.py               # FastAPI 后端入口
    ├── judgement/           # AI 研判模块
    │   ├── client.py        #   多模型 AI 客户端（Anthropic / OpenAI / DeepSeek / Gemini / 豆包 / 通义千问）
    │   ├── service.py       #   业务逻辑（prompt → 调用 → 解析 → 兜底）
    │   ├── router.py        #   FastAPI 路由
    │   ├── state.py         #   回测快照内存存储
    │   └── __init__.py      #   模块声明
    ├── src/
    │   ├── app/             # Next.js App Router
    │   │   ├── layout.tsx   #   根布局
    │   │   └── page.tsx     #   主页面
    │   ├── components/      # UI 组件
    │   │   ├── Navbar.tsx
    │   │   ├── Sidebar.tsx
    │   │   ├── MetricCard.tsx
    │   │   ├── CandlestickChart.tsx
    │   │   ├── EquityCurve.tsx
    │   │   └── AIJudgementPanel.tsx
    │   └── lib/
    │       ├── api.ts       # API 请求 + 类型定义
    │       └── cn.ts        # Tailwind class 合并工具
    └── .env.example         # API Key 配置示例
```

## 快速开始

### 前置依赖

- Python ≥ 3.10
- Node.js ≥ 18
- npm ≥ 9

### 1. 安装依赖

```bash
# Python 依赖
pip install akshare pandas fastapi uvicorn anthropic

# 前端依赖
cd frontend && npm install
```

### 2. 启动后端

```bash
cd frontend
python api.py
```

后端默认运行在 `http://localhost:8000`

### 3. 启动前端

新开一个终端：

```bash
cd frontend
npm run dev
```

浏览器打开 `http://localhost:3000`

## 配置 AI 研判

项目支持通过环境变量切换 AI 提供商，无需修改代码：

### 环境变量说明

| 环境变量 | 说明 | 示例值 |
|---|---|---|
| `AI_PROVIDER` | AI 提供商选择 | `anthropic` / `openai` / `deepseek` / `gemini` / `doubao` / `qianwen` |
| `AI_MODEL` | 模型名称（可选，有默认值） | `claude-sonnet-4-20250514` / `gpt-4.1-mini` |
| `AI_BASE_URL` | API 地址覆盖（可选） | `https://your-proxy.com/v1/chat/completions` |
| `ANTHROPIC_API_KEY` | Anthropic 密钥 | `sk-ant-xxxxxxxxxx` |
| `OPENAI_API_KEY` | OpenAI 密钥 | `sk-xxxxxxxxxx` |
| `DEEPSEEK_API_KEY` | DeepSeek 密钥 | `sk-xxxxxxxxxx` |
| `GEMINI_API_KEY` | Gemini 密钥 | `xxxxxxxxxx` |
| `DOUBAO_API_KEY` | 豆包/火山引擎密钥 | `xxxxxxxxxx` |
| `QIANWEN_API_KEY` | 通义千问密钥 | `sk-xxxxxxxxxx` |

### 使用方式

```bash
# 选择 Anthropic Claude（默认）
export AI_PROVIDER=anthropic
export ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxx

# 切换到 OpenAI
export AI_PROVIDER=openai
export OPENAI_API_KEY=sk-xxxxxxxxxx
export AI_MODEL=gpt-4o

# 切换到 DeepSeek
export AI_PROVIDER=deepseek
export DEEPSEEK_API_KEY=sk-xxxxxxxxxx

# 切换到 Gemini
export AI_PROVIDER=gemini
export GEMINI_API_KEY=xxxxxxxxxx

# 切换到豆包
export AI_PROVIDER=doubao
export DOUBAO_API_KEY=xxxxxxxxxx

# 切换到通义千问
export AI_PROVIDER=qianwen
export QIANWEN_API_KEY=sk-xxxxxxxxxx
```

也可以直接在 `.env.local` 或 `.env` 文件中配置（后端会自动读取）。

## 策略说明

- **双均线策略**：MA5 上穿 MA20 且处于趋势市 → 买入；MA5 下穿 MA20 → 卖出
- **趋势过滤器**：收盘价在 MA60 上方时才视为趋势市，非趋势市空仓
- **T+1 执行**：信号在 T 日收盘后生成，T+1 日开盘执行，无未来数据
- **数据源**：akshare 前复权数据，本地 parquet 缓存

## 技术栈

### Python 后端
- `akshare` — A 股数据获取
- `pandas` — 数据处理与回测
- `FastAPI` + `uvicorn` — REST API
- `anthropic` — Claude API 调用（可选，可替换为 OpenAI / DeepSeek / Gemini / 豆包 / 通义千问）

### 前端
- `Next.js 16` — React 框架
- `Tailwind CSS 4` — 样式
- `Framer Motion` — 动画
- `Recharts` — 收益曲线图表
- `Lucide React` — 图标

### 设计风格
Apple 设计语言：SF Pro 字体、大圆角卡片、毛玻璃导航、克制配色、大间距布局。

## 模块说明

### 回测引擎 (`backtest_engine.py`)
- `compute_signals()` — MA 计算 + 金叉/死叉 + 趋势过滤 + T+1 延迟
- `run_backtest()` — 策略日收益率、累积收益率
- `compute_metrics()` — 累计收益、最大回撤、夏普比率、胜率

### AI 研判 (`frontend/judgement/`)
- 三层架构：路由 → 业务逻辑 → 模型客户端，职责分离
- 支持 6 种 AI 提供商：Anthropic、OpenAI、DeepSeek、Gemini、豆包、通义千问
- System prompt 严格约束输出为 JSON，枚举值 `看多/看空/中性`
- 完善的异常处理：网络超时、非 JSON 响应、API Key 未配置均有兜底响应
- 通过 `AI_PROVIDER` 环境变量切换提供商，无需修改代码

## 明确不做的事

- 不做多因子选股、财务数据分析
- 不做滑点/手续费的精细仿真
- 不做用户登录、数据库等工程化内容
- 不做实盘交易接口对接
- AI 不输出具体买卖点位、目标价、仓位建议

## 许可证

仅供学习参考，不构成投资建议。

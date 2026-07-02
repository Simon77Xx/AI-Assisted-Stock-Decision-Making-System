"""
Streamlit 前端
- 侧边栏：股票代码、时间区间、均线参数
- 主区域：K线图 + 均线 + 买卖点 + 收益曲线 + 指标卡片
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from data_fetcher import load_data
from backtest_engine import compute_signals, run_backtest, compute_metrics

# ---------- 页面配置 ----------
st.set_page_config(
    page_title="股海秘籍 - 双均线策略回测",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("股海秘籍 — 双均线趋势策略回测")

# ---------- 侧边栏 ----------
with st.sidebar:
    st.header("策略参数")

    stock_code = st.text_input("股票代码", value="000001").strip()
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("起始日期", pd.Timestamp("2023-01-01"))
    with col2:
        end_date = st.date_input("结束日期", pd.Timestamp("2024-12-31"))

    fast_ma = st.slider("快线 MA 窗口", min_value=2, max_value=30, value=5)
    slow_ma = st.slider("慢线 MA 窗口", min_value=10, max_value=120, value=20)
    trend_ma = st.slider("趋势线 MA 窗口", min_value=20, max_value=250, value=60)

    run_btn = st.button("运行回测", type="primary")

# ---------- 主区域 ----------
if run_btn:
    with st.spinner("正在获取数据并运行回测..."):
        try:
            df = load_data(stock_code, str(start_date), str(end_date))
        except Exception as e:
            st.error(f"数据获取失败: {e}")
            st.stop()

        if df.empty:
            st.warning("未获取到数据，请检查股票代码或日期范围")
            st.stop()

        # 计算信号并回测
        signals = compute_signals(df, fast_window=fast_ma, slow_window=slow_ma, trend_window=trend_ma)
        backtest = run_backtest(df, signals)
        metrics = compute_metrics(backtest)

    # ---------- 指标卡片 ----------
    st.subheader("绩效指标")
    cols = st.columns(5)
    metric_items = list(metrics.items())
    for i, (name, value) in enumerate(metric_items):
        with cols[i % 5]:
            st.metric(label=name, value=value)

    # ---------- K 线图 ----------
    st.subheader("K 线图与买卖信号")

    # 取最近一年数据展示（如果数据超过一年）
    plot_df = backtest.copy()
    if len(plot_df) > 365:
        plot_df = plot_df.tail(365).reset_index(drop=True)

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.7, 0.3],
    )

    # K 线
    fig.add_trace(
        go.Candlestick(
            x=plot_df["date"],
            open=df.loc[plot_df.index, "open"],
            high=df.loc[plot_df.index, "high"],
            low=df.loc[plot_df.index, "low"],
            close=plot_df["close"],
            name="K线",
            showlegend=False,
        ),
        row=1,
        col=1,
    )

    # 均线
    fig.add_trace(
        go.Scatter(x=plot_df["date"], y=plot_df["MA5"], line=dict(color="orange", width=1), name=f"MA{fast_ma}"),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=plot_df["date"], y=plot_df["MA20"], line=dict(color="blue", width=1), name=f"MA{slow_ma}"),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=plot_df["date"], y=plot_df["MA60"], line=dict(color="purple", width=1, dash="dot"), name=f"MA{trend_ma}"),
        row=1,
        col=1,
    )

    # 买卖点标记
    buy_signals = plot_df[plot_df["position"].diff() == 1]
    sell_signals = plot_df[plot_df["position"].diff() == -1]

    fig.add_trace(
        go.Scatter(
            x=buy_signals["date"],
            y=buy_signals["close"],
            mode="markers",
            marker=dict(symbol="triangle-up", size=12, color="red"),
            name="买入",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=sell_signals["date"],
            y=sell_signals["close"],
            mode="markers",
            marker=dict(symbol="triangle-down", size=12, color="green"),
            name="卖出",
        ),
        row=1,
        col=1,
    )

    # 收益曲线（副图）
    fig.add_trace(
        go.Scatter(
            x=plot_df["date"],
            y=plot_df["strategy_cum"],
            line=dict(color="red", width=2),
            name="策略收益",
        ),
        row=2,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=plot_df["date"],
            y=plot_df["benchmark_cum"],
            line=dict(color="gray", width=1, dash="dash"),
            name="买入持有",
        ),
        row=2,
        col=1,
    )

    # 副图添加零线
    fig.add_hline(y=1, line_color="black", line_width=0.5, row=2, col=1)

    fig.update_layout(
        height=700,
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        legend=dict(orientation="h", y=1.1),
    )
    fig.update_yaxes(title_text="价格", row=1, col=1)
    fig.update_yaxes(title_text="累计收益", row=2, col=1)

    st.plotly_chart(fig, use_container_width=True)

else:
    # 初始提示
    st.info("👈 请在左侧输入股票代码和参数，点击「运行回测」开始")
    st.markdown(
        """
    **策略说明**

    - **双均线策略**：MA5 上穿 MA20 且处于趋势市 → 买入；MA5 下穿 MA20 → 卖出
    - **趋势过滤器**：收盘价在 MA60 上方时才视为趋势市，非趋势市空仓
    - **T+1 执行**：信号在 T 日收盘后生成，T+1 日开盘执行，无未来数据
    - **数据源**：akshare 前复权数据，本地 parquet 缓存
    """
    )
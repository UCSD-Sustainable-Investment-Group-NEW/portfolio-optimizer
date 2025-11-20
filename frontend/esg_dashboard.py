import datetime as dt
from typing import List

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

from esg_optimizer import (
    asset_sharpes,
    calc_stats,
    fetch_price_history,
    fetch_risk_free_rate,
    frontier_points,
    max_sharpe_portfolio,
    optimize_esg_frontier,
)

st.set_page_config(page_title="ESG Frontier Studio", page_icon="📈", layout="wide")
# Track whether the optimizer has been launched at least once so that subsequent
# parameter tweaks automatically recompute without needing to re-press the button.
if "run_optimizer" not in st.session_state:
    st.session_state["run_optimizer"] = False

BRAND_GRADIENT = """
<style>
:root {
  --paper: #f2e7d6;
  --paper-dark: #d8c7ab;
  --forest: #0f3b2b;
  --evergreen: #1f6847;
  --leaf: #5d9b63;
  --sage: #a7c48c;
  --sun: #d9b26a;
  --ink: #22160f;
}
* { font-family: "DM Sans", "Playfair Display", "Inter", system-ui, -apple-system, sans-serif; }
body { background: radial-gradient(circle at 20% 20%, #f9f1e2, var(--paper)); color: var(--ink); }
.stApp { background: radial-gradient(circle at 70% 10%, #f7eddc, var(--paper)); }
.stApp header { background: linear-gradient(90deg, rgba(15,59,43,0.92), rgba(45,104,75,0.9)); color: #fdf7ec; border-bottom: 2px solid rgba(217,178,106,0.5); }
.stApp h1, .stApp h2, .stApp h3, .stApp h4 { color: var(--forest); letter-spacing: 0.3px; }
.st-emotion-cache-18oa0za { color: #fdf7ec !important; }
.metric-card { padding: 0.85rem 1.1rem; border-radius: 16px; background: linear-gradient(135deg, rgba(15,59,43,0.92), rgba(33,104,74,0.92)); color: #fdf7ec; border: 1px solid rgba(217,178,106,0.55); box-shadow: 0 12px 28px rgba(17,49,33,0.28); }
.metric-card .label { text-transform: uppercase; letter-spacing: 0.06em; font-size: 0.75rem; color: #f0dfc0; }
.metric-card .value { font-size: 1.45rem; font-weight: 800; }
.section-title { font-family: "Playfair Display", "DM Sans", serif; letter-spacing: 0.6px; color: var(--forest); }
.section-note { color: #4c3a29; font-size: 0.95rem; }
.chart-caption { color: #4a382a; background: rgba(217,178,106,0.14); border: 1px solid rgba(217,178,106,0.35); padding: 0.65rem 0.75rem; border-radius: 10px; box-shadow: inset 0 1px 0 rgba(255,255,255,0.6); }
.card-shell { background: linear-gradient(140deg, rgba(255,255,255,0.78), rgba(255,255,255,0.58)); border: 1px solid rgba(34,22,15,0.08); border-radius: 16px; padding: 1rem; box-shadow: 0 10px 24px rgba(17,49,33,0.14); }
.stButton>button { background: linear-gradient(90deg, var(--leaf), var(--sage)); color: var(--forest); border: 1px solid rgba(15,59,43,0.2); font-weight: 700; }
.stButton>button:hover { background: linear-gradient(90deg, var(--sage), var(--leaf)); }
.stMultiSelect [data-baseweb="tag"] { background: rgba(15,59,43,0.12); color: var(--forest); border: 1px solid rgba(15,59,43,0.25); }
.stMultiSelect [data-baseweb="tag"]:hover { background: rgba(15,59,43,0.18); }
.stSlider [role="slider"] { background: var(--leaf); }
.stSlider [class*="thumb"] { background: var(--forest); border: 2px solid #f5e8d7; }
.stSlider [class*="bar"] { background: rgba(15,59,43,0.12); }
.stSlider, .stSlider * { color: #fdf7ec !important; }
.stSlider label { color: #fdf7ec !important; font-weight: 700; }
.stTextInput>div>div>input,
.stNumberInput input,
.stDateInput input { color: var(--forest); background: rgba(255,255,255,0.78); border: 1px solid rgba(15,59,43,0.22); }
.stSelectbox, .stMultiSelect { color: var(--forest); }
.stSidebar, .sidebar-content { background: linear-gradient(180deg, rgba(15,59,43,0.95), rgba(15,59,43,0.86)); color: #f5ecda; }
.stSidebar * { color: #f5ecda; }
.stSidebar label, .stSidebar h1, .stSidebar h2, .stSidebar h3, .stSidebar h4, .stSidebar p { color: #f8f3e6 !important; font-weight: 600; letter-spacing: 0.2px; }
.stSidebar .stSlider label, .stSidebar .stNumberInput label, .stSidebar .stDateInput label, .stSidebar .stMultiSelect label { color: #f8f3e6 !important; }
.stSidebar input, .stSidebar .stTextInput>div>div>input, .stSidebar .stNumberInput input, .stSidebar .stDateInput input { background: rgba(255,255,255,0.82); color: var(--forest); border: 1px solid rgba(245,236,218,0.6); }
.stDataFrame, .stDataFrame * { color: var(--forest); }
.stMarkdown { color: var(--ink); }
.st-table { border-radius: 12px; }
</style>
"""
st.markdown(BRAND_GRADIENT, unsafe_allow_html=True)

DEFAULT_TICKERS = ["CROX", "DECK", "EME", "COST", "DE", "NVDA"]
DEFAULT_ESG = {
    "CROX": 0.62,
    "DECK": 0.63,
    "EME": 0.56,
    "COST": 0.72,
    "DE": 0.73,
    "NVDA": 0.69,
}


@st.cache_data(show_spinner=False)
def fetch_esg_scores(tickers: List[str]) -> dict:
    """Fetch ESG scores from Yahoo Finance sustainability; returns mapping ticker->score in [0,1]."""
    scores = {}
    for t in tickers:
        try:
            sustain = yf.Ticker(t).sustainability
            if sustain is None or sustain.empty:
                continue
            # Yahoo reports totalEsg on a 0-100 scale; normalize to 0-1 range.
            if "totalEsg" in sustain.index:
                val = float(sustain.loc["totalEsg"].values[0])
                if val > 1.0:
                    val = val / 100.0
                scores[t] = max(0.0, min(1.0, val))
        except Exception:
            continue
    return scores


@st.cache_data(show_spinner=False)
def load_prices(tickers: List[str], start: dt.date, end: dt.date) -> pd.DataFrame:
    return fetch_price_history(tickers, start, end)


@st.cache_data(show_spinner=False)
def load_risk_free(start: dt.date, end: dt.date) -> pd.Series:
    return fetch_risk_free_rate(start, end)


@st.cache_data(show_spinner=False)
def load_benchmark(tickers: List[str], start: dt.date, end: dt.date) -> pd.Series:
    """Download benchmark close prices, trying multiple symbols and fallbacks."""
    for tk in tickers:
        # Try specific date window, then multi-year periods, then yf.download
        attempts = [
            ("range", lambda: yf.Ticker(tk).history(start=start, end=end)),
            ("10y", lambda: yf.Ticker(tk).history(period="10y")),
            ("5y", lambda: yf.Ticker(tk).history(period="5y")),
            ("3y", lambda: yf.Ticker(tk).history(period="3y")),
            ("download", lambda: yf.download(tk, start=start, end=end, progress=False)),
            ("download-5y", lambda: yf.download(tk, period="5y", progress=False)),
        ]
        for label, fetch in attempts:
            try:
                hist = fetch()
                if hist is None or hist.empty:
                    continue
                close_col = "Adj Close" if "Adj Close" in hist.columns else "Close" if "Close" in hist.columns else None
                if close_col is None:
                    continue
                close = hist[close_col]
                close.index = pd.to_datetime(close.index)
                return close.sort_index()
            except Exception:
                continue
    # If everything failed, return an empty series
    return pd.Series(dtype=float)


def format_weights(weights: pd.Series) -> pd.DataFrame:
    df = weights.reset_index()
    df.columns = ["ticker", "weight"]
    df["weight_pct"] = (df["weight"] * 100).round(2)
    return df


def main() -> None:
    st.title("ESG Frontier Studio")
    st.caption("Pick your tickers (any on Yahoo Finance), set ESG and allocation constraints, and visualize the optimized portfolio.")

    with st.sidebar:
        st.subheader("Universe")
        custom_tickers = st.text_input(
            "Tickers (comma or space separated)",
            value="AAPL, MSFT, NVDA, AMZN, META, TSLA",
            help="Enter any Yahoo Finance tickers, e.g. AAPL, MSFT, NVDA.",
        )
        parsed = [t.strip().upper() for t in custom_tickers.replace(",", " ").split() if t.strip()]
        unique_tickers = sorted(set(parsed)) or DEFAULT_TICKERS
        preselect_n = st.slider(
            "Number of tickers to use",
            min_value=1,
            max_value=max(1, len(unique_tickers)),
            value=min(max(1, len(unique_tickers)), 6),
        )
        default_sel = unique_tickers[:preselect_n]
        tickers = st.multiselect("Select tickers", options=unique_tickers, default=default_sel)
        st.caption(f"Selected {len(tickers)} tickers")
        start_date = st.date_input("History start", value=dt.date(2019, 9, 30))
        end_date = st.date_input("History end", value=dt.date.today())
        min_alloc_pct = st.slider("Minimum allocation (%)", min_value=0.0, max_value=25.0, value=1.0, step=0.5)
        min_alloc = min_alloc_pct / 100.0
        esg_step = st.slider("Frontier ESG step", min_value=0.005, max_value=0.05, value=0.01, step=0.005)
        target_esg_input = st.number_input("Target ESG", value=0.65, step=0.01, format="%.3f")
        run_button = st.button("Run optimizer", type="primary", use_container_width=True)
        if run_button:
            st.session_state["run_optimizer"] = True

    if not tickers:
        st.info("Pick at least one ticker to get started.")
        return

    if min_alloc * len(tickers) > 1:
        st.error("Minimum allocation is too high for the number of tickers. Lower it or add more assets.")
        return

    fetched_esg = fetch_esg_scores(tickers)
    esg_defaults = [fetched_esg.get(t, DEFAULT_ESG.get(t, 0.65)) for t in tickers]
    missing_esg = [t for t in tickers if t not in fetched_esg]
    esg_frame = pd.DataFrame({"ticker": tickers, "esg_score": esg_defaults})
    st.subheader("ESG inputs")
    if missing_esg:
        st.caption(
            f"Fetched ESG where available from Yahoo Finance; enter scores for: {', '.join(missing_esg)}.",
        )
    edited_esg = st.data_editor(
        esg_frame,
        num_rows="dynamic",
        use_container_width=True,
        key="esg_editor",
        column_config={"esg_score": st.column_config.NumberColumn(format="%.3f", min_value=0.0, max_value=1.0)},
    )

    if not st.session_state["run_optimizer"]:
        st.info("Adjust inputs, then press Run optimizer to calculate weights and frontier.")
        return

    try:
        prices = load_prices(tickers, start_date, end_date)
        risk_free = load_risk_free(start_date, end_date)
    except Exception as exc:
        st.error(f"Data fetch failed: {exc}")
        return

    clean_esg = edited_esg.dropna()
    clean_esg = clean_esg[clean_esg["ticker"].isin(prices.columns)]
    clean_esg = clean_esg.drop_duplicates(subset=["ticker"])
    if clean_esg.empty or len(clean_esg) != len(prices.columns):
        st.error("Provide an ESG score for each selected ticker.")
        return

    esg_scores = clean_esg.set_index("ticker").loc[prices.columns, "esg_score"].values
    mean_excess, cov_matrix = calc_stats(prices, risk_free)

    esg_min, esg_max = esg_scores.min(), esg_scores.max()
    esg_span = esg_max - esg_min
    if esg_span < 1e-8:
        target_esg = float(esg_min)
    else:
        target_esg = float(np.clip(target_esg_input, esg_min + 1e-3, esg_max - 1e-3))

    try:
        opt = optimize_esg_frontier(mean_excess, cov_matrix, esg_scores, target_esg, min_allocation=min_alloc)
        tangency = max_sharpe_portfolio(mean_excess, cov_matrix, min_allocation=min_alloc)
    except Exception as exc:
        st.error(f"Optimization failed: {exc}")
        return

    returns_full = prices.pct_change().dropna()
    aligned_rf = risk_free.reindex(returns_full.index).ffill()
    frontier = list(frontier_points(mean_excess, cov_matrix, esg_scores, min_alloc, step=esg_step))
    frontier_df = pd.DataFrame([{"target_esg": p.target_esg, "sharpe": p.sharpe} for p in frontier])
    indiv_sharpes = asset_sharpes(mean_excess, cov_matrix, prices.columns)
    aligned_weights = opt.weights.reindex(returns_full.columns).fillna(0.0)
    portfolio_daily = (returns_full * aligned_weights).sum(axis=1)
    portfolio_excess = portfolio_daily.sub(aligned_rf, fill_value=0)

    def rolling_sharpe(excess: pd.Series, window: int) -> pd.Series:
        def _fn(x: pd.Series) -> float:
            sigma = x.std()
            if sigma == 0 or np.isnan(sigma):
                return np.nan
            return x.mean() / sigma * np.sqrt(252)
        return excess.rolling(window=window, min_periods=max(60, window // 4)).apply(_fn, raw=False)

    window_days = min(len(portfolio_excess), 252 * 5)
    portfolio_sharpe_series = rolling_sharpe(portfolio_excess, window_days)

    bench_sharpe_series = None
    bench_error = None
    bench_close = load_benchmark(["SPY", "^GSPC"], start=returns_full.index.min(), end=returns_full.index.max())
    if bench_close.empty:
        bench_error = "No benchmark data retrieved from Yahoo for SPY or ^GSPC."
    else:
        bench_returns = bench_close.pct_change().dropna()
        bench_returns = bench_returns.reindex(returns_full.index).ffill()
        bench_excess = bench_returns.sub(aligned_rf, fill_value=0)
        bench_sharpe_series = rolling_sharpe(bench_excess, window_days)

    col_metrics, col_weights = st.columns([1, 2], gap="large", vertical_alignment="top")
    with col_metrics:
        st.markdown("<div style='margin-top:6px;'><h3>Portfolio snapshot</h3></div>", unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="label">Sharpe (ESG target {target_esg:.3f})</div>
                <div class="value">{opt.sharpe:.2f}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            f"""
            <div class="metric-card" style="margin-top:0.7rem;">
                <div class="label">Tangency Sharpe</div>
                <div class="value">{tangency.sharpe:.2f}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div class='section-note' style='margin-top:0.6rem;'>"
            "Sharpe ratios are annualized. The ESG-constrained portfolio maximizes Sharpe while meeting your ESG target; "
            "Tangency Sharpe is the unconstrained benchmark."
            "</div>",
            unsafe_allow_html=True,
        )
    with col_weights:
        st.markdown("<div style='margin-top:6px;'><h3>Optimized weights</h3></div>", unsafe_allow_html=True)
        weights_df = format_weights(opt.weights)
        st.bar_chart(weights_df.set_index("ticker")["weight"])
        st.markdown(
            "<div class='chart-caption'>Bar chart shows how capital is distributed across tickers after applying the ESG and minimum allocation rules.</div>",
            unsafe_allow_html=True,
        )
        st.dataframe(
            weights_df,
            use_container_width=True,
            hide_index=True,
            column_config={"weight": st.column_config.NumberColumn(format="%.4f")},
        )

    st.divider()
    st.markdown("### Performance & ESG trade-offs", unsafe_allow_html=True)
    frontier_col, table_col = st.columns([3, 2])
    with frontier_col:
        fig, ax = plt.subplots(figsize=(8.2, 5.2))
        fig.patch.set_facecolor("none")
        ax.set_facecolor("#f7f0df")
        if not frontier_df.empty:
            ax.plot(
                frontier_df["target_esg"],
                frontier_df["sharpe"],
                linestyle="-.",
                color="#1f6847",
                linewidth=2.2,
                label="ESG frontier",
            )
        ax.scatter(esg_scores, indiv_sharpes.values, color="#d48a27", s=90, zorder=5, label="Assets")
        for esg, shp, ticker in zip(esg_scores, indiv_sharpes.values, prices.columns):
            ax.text(esg, shp + 0.05, ticker, ha="center", fontsize=9, color="#1f3d2b")
        ax.scatter([target_esg], [opt.sharpe], color="#0f3b2b", s=140, marker="*", label="Optimized")
        ax.set_xlabel("ESG score")
        ax.set_ylabel("Annualized Sharpe")
        ax.grid(True, alpha=0.25, linestyle="--", linewidth=0.8)
        ax.legend()
        st.pyplot(fig, clear_figure=True)
        st.markdown(
            "<div class='chart-caption'>Frontier traces the best achievable Sharpe at each ESG target. The star marks your optimized portfolio; orange points show individual assets.</div>",
            unsafe_allow_html=True,
        )
    with table_col:
        st.markdown("#### Asset Sharpe ratios", unsafe_allow_html=True)
        sharpe_df = indiv_sharpes.reset_index()
        sharpe_df.columns = ["ticker", "sharpe"]
        st.dataframe(
            sharpe_df,
            use_container_width=True,
            hide_index=True,
            column_config={"sharpe": st.column_config.NumberColumn(format="%.3f")},
        )
        st.markdown(
            "<div class='chart-caption'>Table ranks each ticker by standalone Sharpe (annualized), helping you interpret which names are driving the portfolio.</div>",
            unsafe_allow_html=True,
        )

    st.divider()
    st.markdown("### Rolling 5Y Sharpe vs SPY", unsafe_allow_html=True)
    sharpe_col, sharpe_note = st.columns([3, 2])
    with sharpe_col:
        sharpe_fig, sharpe_ax = plt.subplots(figsize=(8.5, 4.6))
        sharpe_fig.patch.set_facecolor("none")
        sharpe_ax.set_facecolor("#f7f0df")
        sharpe_ax.plot(
            portfolio_sharpe_series.index,
            portfolio_sharpe_series.values,
            color="#0f3b2b",
            linewidth=2.1,
            label="Optimized portfolio",
        )
        if bench_sharpe_series is not None:
            sharpe_ax.plot(
                bench_sharpe_series.index,
                bench_sharpe_series.values,
                color="#d48a27",
                linewidth=1.8,
                linestyle="--",
                label="SPY (benchmark)",
            )
        sharpe_ax.set_ylabel("Rolling annualized Sharpe")
        sharpe_ax.grid(True, alpha=0.25, linestyle="--")
        sharpe_ax.legend(loc="upper left")
        st.pyplot(sharpe_fig, clear_figure=True)
    with sharpe_note:
        caption_text = (
            f"Shows rolling Sharpe over a {window_days} trading-day window (≈5 years when data allows), "
            "using daily excess returns vs risk-free. SPY is the benchmark; if unavailable, only the portfolio is shown."
        )
        if bench_error:
            caption_text += f" Benchmark fetch note: {bench_error}"
        st.markdown(f"<div class='chart-caption'>{caption_text}</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()

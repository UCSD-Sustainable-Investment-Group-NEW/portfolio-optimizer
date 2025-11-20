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

BRAND_GRADIENT = """
<style>
*:not([class*="st-emotion-cache"]) { font-family: "DM Sans", "Inter", system-ui, -apple-system, sans-serif; }
body { background: #f7fbf4; }
.metric-card { padding: 0.75rem 1rem; border-radius: 14px; background: linear-gradient(140deg,#e9f6e2,#d9efd0); color: #2d3a2e; border: 1px solid #c4dcad; box-shadow: 0 8px 20px rgba(46,92,46,0.08); }
.metric-card .label { text-transform: uppercase; letter-spacing: 0.04em; font-size: 0.75rem; color: #6f8167; }
.metric-card .value { font-size: 1.4rem; font-weight: 700; }
.stButton>button { background: #c7e3b4; color: #2e3b2f; border: 1px solid #b7d6a0; }
.stButton>button:hover { background: #b5d7a0; }
.stApp header { background: linear-gradient(90deg, #f3f9ed, #e5f2dc); border-bottom: 1px solid #d0e3c1; }
.stApp { background: #f7fbf4; }
.stTabs [data-baseweb="tab-list"] { background: #f0f7ea; border-radius: 12px; }
.stTabs [data-baseweb="tab"] { color: #2d3a2e; }
.stTabs [aria-selected="true"] { background: #d3e6c6; }
.st-cx { color: #5b4a37; }
.brown-accent { color: #5b4a37; }
.stMultiSelect [data-baseweb="tag"] { background: #d5e9cd; color: #3e2f21; border: 1px solid #c2d7b8; }
.stMultiSelect [data-baseweb="tag"]:hover { background: #c9e0c0; }
.st-ba { color: #3e2f21 !important; }
.st-ay { background-color: #9dcf9f !important; }
.stSlider [role="slider"] { background: #8abd91; }
.stSlider [class*="thumb"] { background: #5b4a37; }
.stSlider [class*="bar"] { background: #cfe5c7; }
.stSlider, .stSlider * { color: #dde9d1 !important; }
.stSlider label { color: #dde9d1 !important; }
.stSlider [data-baseweb="slider"] div[role="slider"] { border: 2px solid #5b4a37; }
.sidebar-content, .stSidebar, .stSidebar * { color: #dce9d2; }
.stSelectbox, .stTextInput, .stNumberInput, .stDateInput, .stMultiSelect { color: #2d3a2e; }
.stTextInput>div>div>input { color: #2d3a2e; background: #d5e9cd; }
.stNumberInput input, .stDateInput input { color: #2d3a2e; background: #d5e9cd; }
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
def load_prices(tickers: List[str], start: dt.date, end: dt.date) -> pd.DataFrame:
    return fetch_price_history(tickers, start, end)


@st.cache_data(show_spinner=False)
def load_risk_free(start: dt.date, end: dt.date) -> pd.Series:
    return fetch_risk_free_rate(start, end)


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

    if not tickers:
        st.info("Pick at least one ticker to get started.")
        return

    if min_alloc * len(tickers) > 1:
        st.error("Minimum allocation is too high for the number of tickers. Lower it or add more assets.")
        return

    esg_defaults = [DEFAULT_ESG.get(t, 0.65) for t in tickers]
    esg_frame = pd.DataFrame({"ticker": tickers, "esg_score": esg_defaults})
    st.subheader("ESG inputs")
    edited_esg = st.data_editor(
        esg_frame,
        num_rows="dynamic",
        use_container_width=True,
        key="esg_editor",
        column_config={"esg_score": st.column_config.NumberColumn(format="%.3f", min_value=0.0, max_value=1.0)},
    )

    if run_button:
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
        target_esg = float(np.clip(target_esg_input, esg_min + 1e-3, esg_max - 1e-3))

        try:
            opt = optimize_esg_frontier(mean_excess, cov_matrix, esg_scores, target_esg, min_allocation=min_alloc)
            tangency = max_sharpe_portfolio(mean_excess, cov_matrix, min_allocation=min_alloc)
        except Exception as exc:
            st.error(f"Optimization failed: {exc}")
            return

        frontier = list(frontier_points(mean_excess, cov_matrix, esg_scores, min_alloc, step=esg_step))
        frontier_df = pd.DataFrame([{"target_esg": p.target_esg, "sharpe": p.sharpe} for p in frontier])
        indiv_sharpes = asset_sharpes(mean_excess, cov_matrix, prices.columns)

        col_metrics, col_weights = st.columns([1, 2])
        with col_metrics:
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
                <div class="metric-card" style="margin-top:0.5rem;">
                    <div class="label">Tangency Sharpe</div>
                    <div class="value">{tangency.sharpe:.2f}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown(
                "<div class='brown-accent' style='margin-top:0.5rem;font-size:0.95rem;'>"
                "Sharpe ratios are annualized. The ESG-constrained portfolio hits your target ESG while maximizing Sharpe under the min-allocation rule. "
                "Tangency Sharpe ignores the ESG target and shows the unconstrained optimum for comparison."
                "</div>",
                unsafe_allow_html=True,
            )
        with col_weights:
            st.subheader("Optimized weights")
            weights_df = format_weights(opt.weights)
            st.bar_chart(weights_df.set_index("ticker")["weight"])
            st.dataframe(weights_df, use_container_width=True, hide_index=True, column_config={"weight": st.column_config.NumberColumn(format="%.4f")})

        st.subheader("Efficient frontier and Sharpe profile")
        fig, ax = plt.subplots(figsize=(8, 5))
        if not frontier_df.empty:
            ax.plot(frontier_df["target_esg"], frontier_df["sharpe"], linestyle="-.", color="#8abd91", label="ESG frontier")
        ax.scatter(esg_scores, indiv_sharpes.values, color="#c08b5c", s=80, zorder=5, label="Assets")
        for esg, shp, ticker in zip(esg_scores, indiv_sharpes.values, prices.columns):
            ax.text(esg, shp + 0.05, ticker, ha="center", fontsize=9)
        ax.scatter([target_esg], [opt.sharpe], color="#9acfa2", s=120, marker="*", label="Optimized")
        ax.set_xlabel("ESG score")
        ax.set_ylabel("Annualized Sharpe")
        ax.grid(True, alpha=0.3)
        ax.legend()
        st.pyplot(fig, clear_figure=True)

        st.subheader("Asset Sharpe ratios")
        sharpe_df = indiv_sharpes.reset_index()
        sharpe_df.columns = ["ticker", "sharpe"]
        st.dataframe(sharpe_df, use_container_width=True, hide_index=True, column_config={"sharpe": st.column_config.NumberColumn(format="%.3f")})


if __name__ == "__main__":
    main()

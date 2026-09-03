"""
app.py -- NYASHA AI

Main Streamlit entry point. Wires the UI to the deterministic, already
unit-tested modules in analytics/, rules/, services/, and database/.

NOTE: This file requires `streamlit` (not installed in the build sandbox
used to develop this project -- no network access there). It has been
written carefully against the tested module APIs but has NOT been run
live. Before your demo:
    pip install -r requirements.txt
    streamlit run app.py
and fix anything that surfaces -- treat this as a strong first draft, not
a guaranteed-working final file.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
import streamlit as st

from analytics.anomaly_detection import detect_anomalies
from analytics.currency_normalisation import normalise_to_reporting_currency
from analytics.customer_analysis import analyse_customer_risk
from analytics.financial_health import calculate_financial_health
from analytics.financial_metrics import (
    liquidity_summary, profitability_summary, revenue_by_currency, working_capital_summary,
)
from analytics.forecasting import forecast_all_horizons
from analytics.validation import validate_transactions
from database.database import init_db, log_audit, log_usage
from database.seed import seed_if_needed
from rules.vat_rules import DISCLAIMER, calculate_vat_summary
from services.exchange_rates import get_supported_currencies
from services.llm_service import answer_financial_question, explain_financial_result

st.set_page_config(page_title="NYASHA AI", page_icon="💡", layout="wide")

# --------------------------------------------------------------------------- Startup
init_db()
seed_if_needed()  # rebuilds demo data if the DB is empty (Section 0A.1 -- ephemeral filesystem)

if "reporting_currency" not in st.session_state:
    st.session_state.reporting_currency = "USD"
if "language" not in st.session_state:
    st.session_state.language = "English"
if "transactions_df" not in st.session_state:
    st.session_state.transactions_df = None


# --------------------------------------------------------------------------- Sidebar / navigation
def sidebar() -> str:
    with st.sidebar:
        st.markdown("## 💡 NYASHA AI")
        st.caption("Multilingual & Multi-Currency SME Financial Intelligence Agent")

        st.session_state.language = st.selectbox(
            "🌐 Language", ["English", "Shona", "Ndebele"],
            index=["English", "Shona", "Ndebele"].index(st.session_state.language),
        )
        st.session_state.reporting_currency = st.selectbox(
            "Reporting Currency", get_supported_currencies(),
            index=get_supported_currencies().index(st.session_state.reporting_currency),
        )

        st.divider()
        page = st.radio(
            "Navigate",
            [
                "🏠 Home", "📊 Dashboard", "📁 Upload Data", "💰 Financial Analysis",
                "🔍 Anomaly Detection", "💵 Cash Flow Forecast", "👥 Customer Analysis",
                "🧾 VAT Analysis", "🤖 AI Financial Assistant", "📚 Usage History",
                "📜 Audit Trail",
            ],
            label_visibility="collapsed",
        )
        return page


# --------------------------------------------------------------------------- Data loading helpers
def load_active_dataframe() -> pd.DataFrame | None:
    """Returns the currently active, VALIDATED + currency-normalised transactions."""
    if st.session_state.transactions_df is None:
        return None
    result = validate_transactions(st.session_state.transactions_df)
    norm = normalise_to_reporting_currency(result.valid_rows, st.session_state.reporting_currency)
    return norm.df


def require_data() -> pd.DataFrame | None:
    df = load_active_dataframe()
    if df is None or df.empty:
        st.info("No transaction data loaded yet. Go to **📁 Upload Data** to load the demo dataset or upload your own.")
        return None
    return df


# --------------------------------------------------------------------------- Pages
def page_home():
    st.title("💡 NYASHA AI")
    st.subheader("From Financial Data to Smarter Decisions.")
    st.write(
        "NYASHA AI turns raw SME transaction data into financial analysis, risk detection, "
        "cash-flow forecasts, VAT summaries, and AI-explained recommendations -- with every "
        "figure computed deterministically in Python and never invented by the AI."
    )
    st.markdown("Start with **📁 Upload Data** (or load the built-in demo dataset), then explore the pages in the sidebar.")


def page_upload():
    st.title("📁 Upload Data")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Use the demo dataset")
        st.caption("Moyo Retail & Services -- 12 months, 7 currencies, deliberate anomalies for demonstration.")
        if st.button("Load demo dataset"):
            st.session_state.transactions_df = pd.read_csv("data/sample_transactions.csv")
            log_usage(user_action="Uploaded transactions", dataset="Moyo Retail & Services (demo)",
                      currency=st.session_state.reporting_currency, language=st.session_state.language)
            st.success(f"Loaded {len(st.session_state.transactions_df)} demo transactions.")

    with col2:
        st.markdown("### Upload your own")
        uploaded = st.file_uploader("CSV or Excel", type=["csv", "xlsx", "xls"])
        if uploaded is not None:
            df = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
            st.session_state.transactions_df = df
            log_usage(user_action="Uploaded transactions", dataset=uploaded.name,
                      currency=st.session_state.reporting_currency, language=st.session_state.language)
            st.success(f"Loaded {len(df)} transactions from {uploaded.name}.")

    if st.session_state.transactions_df is not None:
        st.divider()
        st.markdown("### Data Validation")
        result = validate_transactions(st.session_state.transactions_df)
        st.code(result.summary())
        with st.expander("See rows that failed validation"):
            st.dataframe(result.invalid_rows)


def page_dashboard():
    st.title("📊 Dashboard")
    df = require_data()
    if df is None:
        return

    prof = profitability_summary(df)
    liq = liquidity_summary(df)
    health = calculate_financial_health(df)

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Revenue", f"{st.session_state.reporting_currency} {prof.revenue:,.2f}")
    c2.metric("Expenses", f"{st.session_state.reporting_currency} {prof.expenses:,.2f}")
    c3.metric("Net Profit", f"{st.session_state.reporting_currency} {prof.net_profit:,.2f}",
              f"{prof.net_margin_pct}%" if prof.net_margin_pct is not None else None)
    c4.metric("Cash Balance", f"{st.session_state.reporting_currency} {liq.net_cash_flow:,.2f}")
    c5.metric("Profit Margin", f"{prof.net_margin_pct}%" if prof.net_margin_pct is not None else "N/A")
    c6.metric("Financial Health", f"{health.total_score}/100", health.rating)

    st.divider()
    st.markdown("### 💵 Revenue by currency (original amounts -- see Section 12)")
    st.bar_chart(pd.Series(revenue_by_currency(df)))


def page_financial_analysis():
    st.title("💰 Financial Analysis")
    df = require_data()
    if df is None:
        return

    prof = profitability_summary(df)
    liq = liquidity_summary(df)
    wc = working_capital_summary(df)
    health = calculate_financial_health(df)

    st.markdown("### Profitability")
    st.json(prof.__dict__)
    st.markdown("### Liquidity")
    st.json(liq.__dict__)
    st.markdown("### Working Capital")
    st.json(wc.__dict__)

    st.divider()
    st.markdown(f"### 🏥 Financial Health: {health.total_score}/100 -- **{health.rating}**")
    with st.expander("How was this score calculated?"):
        for c in health.components:
            st.write(f"**{c.name}** ({c.weight_pct:.0f}% weight): {c.component_score:.1f}/100")
            st.caption(c.explanation)

    if st.button("💡 Explain this with AI"):
        with st.spinner("Asking NYASHA AI..."):
            explanation = explain_financial_result(
                {"profitability": prof, "liquidity": liq, "health_score": health},
                language={"English": "en", "Shona": "sn", "Ndebele": "nd"}[st.session_state.language],
            )
        st.info(explanation)
        log_audit(user_action="AI explanation requested", analysis_type="financial_analysis",
                   calculation_results={"net_profit": prof.net_profit, "health_score": health.total_score})


def page_anomalies():
    st.title("🔍 Anomaly Detection")
    df = require_data()
    if df is None:
        return

    findings = detect_anomalies(df)
    if not findings:
        st.success("No unusual transactions detected in the current dataset.")
        return

    for f in findings:
        level_color = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}[f.risk_level]
        with st.expander(f"{level_color} {f.transaction_id} -- {f.risk_level} (score {f.risk_score})"):
            st.write("**Reasons:**")
            for r in f.reasons:
                st.write(f"- {r}")
            st.write(f"**Recommended action:** {f.recommended_action}")


def page_cashflow():
    st.title("💵 Cash Flow Forecast")
    df = require_data()
    if df is None:
        return

    forecasts = forecast_all_horizons(df)
    cols = st.columns(len(forecasts))
    for col, (horizon, f) in zip(cols, forecasts.items()):
        with col:
            st.metric(f"{horizon}-day", f"{f.status_emoji} {f.expected_closing_balance:,.2f}", f.status.upper())

    st.divider()
    horizon_choice = st.selectbox("View details for horizon", list(forecasts.keys()), index=2)
    f = forecasts[horizon_choice]
    st.write(f"**Starting balance:** {f.starting_balance:,.2f}")
    st.write(f"**Expected inflows:** {f.expected_inflows:,.2f}")
    st.write(f"**Expected outflows:** {f.expected_outflows:,.2f}")
    st.write(f"**Expected closing balance:** {f.expected_closing_balance:,.2f}")
    st.write(f"**Status:** {f.status_emoji} {f.status.upper()}")
    st.caption(f"Main driver: {f.main_driver}")


def page_customers():
    st.title("👥 Customer Analysis")
    df = require_data()
    if df is None:
        return

    risks = analyse_customer_risk(df)
    if not risks:
        st.info("No customer-attributed income transactions in this dataset.")
        return

    st.dataframe(pd.DataFrame([r.__dict__ for r in risks]))


def page_vat():
    st.title("🧾 VAT Analysis")
    df = require_data()
    if df is None:
        return

    vat = calculate_vat_summary(df)
    c1, c2, c3 = st.columns(3)
    c1.metric("Output VAT", f"{vat.output_vat:,.2f}")
    c2.metric("Input VAT", f"{vat.input_vat:,.2f}")
    c3.metric("Net VAT Payable", f"{vat.net_vat_payable:,.2f}")

    if vat.transactions_flagged_for_review:
        st.warning(f"{vat.transactions_missing_vat_status} transactions are missing a VAT status and need review.")
        with st.expander("See flagged transaction IDs"):
            st.write(vat.transactions_flagged_for_review)

    st.divider()
    st.caption(DISCLAIMER)


def page_ai_assistant():
    st.title("🤖 AI Financial Assistant")
    df = require_data()
    if df is None:
        return

    question = st.text_input("Ask a question about this business's finances")
    if st.button("Ask") and question:
        prof = profitability_summary(df)
        liq = liquidity_summary(df)
        health = calculate_financial_health(df)
        findings = detect_anomalies(df)[:5]
        forecasts = forecast_all_horizons(df)

        context = {
            "profitability": prof, "liquidity": liq, "health_score": health,
            "top_anomalies": findings, "cash_flow_forecast_30_day": forecasts[30],
        }
        with st.spinner("Thinking..."):
            answer = answer_financial_question(
                question, context,
                language={"English": "en", "Shona": "sn", "Ndebele": "nd"}[st.session_state.language],
            )
        st.write(answer)
        log_usage(user_action="AI inquiry", ai_inquiry=question, currency=st.session_state.reporting_currency,
                   language=st.session_state.language)


def page_usage_history():
    st.title("📚 Usage History")
    from database.database import fetch_all
    rows = fetch_all("SELECT * FROM usage_history ORDER BY id DESC LIMIT 200")
    st.dataframe(pd.DataFrame(rows))


def page_audit_trail():
    st.title("📜 Audit Trail")
    from database.database import fetch_all
    rows = fetch_all("SELECT * FROM audit_trail ORDER BY id DESC LIMIT 200")
    st.dataframe(pd.DataFrame(rows))


# --------------------------------------------------------------------------- Router
PAGES = {
    "🏠 Home": page_home,
    "📊 Dashboard": page_dashboard,
    "📁 Upload Data": page_upload,
    "💰 Financial Analysis": page_financial_analysis,
    "🔍 Anomaly Detection": page_anomalies,
    "💵 Cash Flow Forecast": page_cashflow,
    "👥 Customer Analysis": page_customers,
    "🧾 VAT Analysis": page_vat,
    "🤖 AI Financial Assistant": page_ai_assistant,
    "📚 Usage History": page_usage_history,
    "📜 Audit Trail": page_audit_trail,
}


def main():
    page = sidebar()
    PAGES[page]()


if __name__ == "__main__":
    main()

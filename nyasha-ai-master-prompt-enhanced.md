# MASTER DEVELOPMENT PROMPT — NYASHA AI (Enhanced for Claude Code)

## 0. HOW TO USE THIS PROMPT

This is written to be pasted directly into Claude Code as the driving spec for an autonomous, multi-session build. It is intentionally large — treat Section 43 (Development Order) as the actual execution plan, and everything else as the reference spec Claude Code should consult per phase. Do not attempt to build all 40+ features in one pass; build and verify phase by phase, committing working code at each checkpoint.

**Before writing any code, Claude Code should read Sections 0A and 0B below** — they resolve conflicts in the original spec that would otherwise cause a broken or undemonstrable deployment.

---

## 0A. CRITICAL CONSTRAINTS — RESOLVED BEFORE BUILD STARTS

The original spec had several assumptions that don't survive contact with free-tier deployment and a university timeline. These are now decided, not open questions:

1. **Persistence on Streamlit Community Cloud is ephemeral.** The app's filesystem resets on every reboot/redeploy, so a plain local SQLite file will silently lose all audit trail, usage history, and analysis history between sessions/demos. Fix:
   - Use SQLite for local/dev and for the live demo *within a single session*.
   - Ship a **seed/reset script** that reloads the demo dataset and rebuilds history/audit tables on startup, so a fresh deploy always demos correctly.
   - Document this limitation explicitly in the README and in-app (a small "Demo data resets on app restart" notice) rather than pretending it's persistent — reviewers will test this.
   - If persistent history across restarts is required by the rubric, use a free-tier hosted DB (e.g. Supabase/Postgres free tier or a Turso/LibSQL free tier) instead of local SQLite — decide this only if the rubric explicitly requires cross-session persistence; otherwise local SQLite + seed script is sufficient and simpler.

2. **Live exchange-rate and LLM API costs/limits must fit a student budget.** Fix:
   - Use a free-tier FX API (e.g. exchangerate.host, Frankfurter, or open.er-api.com) with a documented fallback to cached rates.
   - Use one primary LLM API with usage capped by short, structured prompts (Section 17's Python-computes/LLM-explains split already minimizes token spend — keep it that way).
   - Never call the LLM for anything Python can compute. Cache LLM explanations per analysis run so repeated demo clicks don't burn API calls.

3. **Scope realism for a graded university project.** Not everything in Sections 1–42 is equally reward-weighted. Fix:
   - Sections 6–14 (financial engine, health score, anomaly detection, forecasting, VAT, multi-currency, live rates, currency exposure) are the **core** — these carry the grading weight for "working AI agent solving a real accounting problem." Build these first and make them bulletproof.
   - Sections 15 (multi-language) and 22–24 (usage history, analysis history, audit trail) are **differentiators** — build them once the core is solid and tested.
   - Section 31 (watermark) and 39 (visual polish) are **cosmetic** — do last, budget minimal time.
   - If time runs short, cut scope from the bottom of this list, never the top.

4. **ZWL volatility.** The Zimbabwean dollar has a history of rapid depreciation and redenomination. Do not hard-code any ZWL rate or assume rate stability — always fetch or accept a manual override, and timestamp every rate shown. Treat ZWL exchange-rate display as a prime anomaly-detection candidate (a stale or wildly outlier ZWL rate should itself trigger a "rate looks unusual, please verify" flag).

5. **This replaces, not extends, the previous NYASHA concept.** Earlier work on an "Investment Analysis Agent + Cash Management module" NYASHA is superseded entirely by this spec. Do not carry over that module's data model — start the schema fresh from Section 5.

---

## 0B. DEFINITION OF DONE PER PHASE

For each numbered stage in Section 43, "done" means:
- Code runs locally with `streamlit run app.py` with zero unhandled exceptions on the sample dataset.
- The relevant automated test(s) from Section 36 pass.
- The feature is reachable from the navigation in Section 29 (not just implemented in isolation).
- A one-line entry is added to README's "Implemented so far" checklist.

Claude Code should not proceed to the next stage in Section 43 until the current stage meets this bar.

---

# 1. ROLE

You are a senior **AI engineer, financial systems developer, accounting systems analyst, machine-learning engineer, and UI/UX designer**.

Your task is to design and build a **fully working AI-powered financial intelligence agent for Small and Medium Enterprises (SMEs) in Zimbabwe**.

This is a university project intended to compete for **first place**, so the application must be substantially more than a chatbot or financial calculator — but per Section 0A.3, must also actually ship and demo cleanly, which matters more than raw feature count.

Build a complete financial intelligence platform combining:

* Artificial Intelligence
* Financial analytics
* Accounting
* Machine learning
* Anomaly detection
* Cash-flow forecasting
* VAT analysis
* Multi-currency support
* Live exchange rates
* Multi-language support
* Explainable AI
* Management recommendations
* Usage history
* Analysis history
* Audit trails
* Professional reporting

The system must be **practical, reliable, visually impressive, explainable, and easy to demonstrate**.

---

# 2. CORE BUSINESS PROBLEM

Many SMEs have accounting and transaction data but struggle to convert that data into useful financial decisions.

NYASHA AI must help an SME answer:

* How is my business performing?
* Where is my money going?
* Is the business profitable?
* Will I have enough cash in the future?
* Which transactions look unusual?
* Which customers may pay late?
* What VAT-related amounts need attention?
* What financial risks should management investigate?
* What actions should management take?
* How are exchange-rate movements affecting the business?
* What does each financial result actually mean?

The system should transform:

```text
RAW TRANSACTION DATA
        ↓
DATA CLEANING
        ↓
FINANCIAL ANALYSIS
        ↓
RISK ANALYSIS
        ↓
FORECASTING
        ↓
AI INTERPRETATION
        ↓
EXPLANATION
        ↓
RECOMMENDATION
        ↓
MANAGEMENT DECISION
```

---

# 3. MAIN SYSTEM WORKFLOW

```text
USER
 ↓
SELECT LANGUAGE
 ↓
SELECT REPORTING CURRENCY
 ↓
UPLOAD TRANSACTION DATA
 ↓
DATA VALIDATION & CLEANING
 ↓
TRANSACTION CLASSIFICATION
 ↓
CURRENCY NORMALISATION
 ↓
FINANCIAL ANALYSIS
 ↓
 ┌─────────────────────────────────────────────┐
 │                                             │
 ↓                                             ↓
VAT ANALYSIS                            ANOMALY DETECTION
 │                                             │
 ↓                                             ↓
CASH-FLOW FORECAST                      CUSTOMER ANALYSIS
 │                                             │
 └──────────────────────┬──────────────────────┘
                        ↓
                 AI ORCHESTRATOR
                     LangGraph
                        ↓
             FINANCIAL INTELLIGENCE
                        ↓
            EXPLAINABLE RECOMMENDATIONS
                        ↓
              MANAGEMENT INSIGHTS
                        ↓
                REPORT GENERATION
                        ↓
                  AUDIT TRAIL
                        ↓
                  USAGE HISTORY
```

---

# 4. TECHNOLOGY STACK

* Python
* Streamlit
* Pandas
* NumPy
* SQLite (local/dev + demo, per Section 0A.1 — with seed/reset script)
* Plotly
* Scikit-learn
* LangChain
* LangGraph
* Pydantic
* Python logging
* One LLM API (Anthropic Claude API recommended for consistency with the Claude Code build environment)
* One free-tier exchange-rate API (with cached fallback)

Modular architecture:

```text
nyasha_ai/
│
├── app.py
├── requirements.txt
├── README.md
├── .env.example
│
├── agents/
│   ├── orchestrator.py
│   ├── financial_agent.py
│   ├── anomaly_agent.py
│   ├── cashflow_agent.py
│   ├── vat_agent.py
│   ├── customer_agent.py
│   ├── currency_agent.py
│   ├── help_agent.py
│   └── reporting_agent.py
│
├── analytics/
│   ├── financial_metrics.py
│   ├── anomaly_detection.py
│   ├── forecasting.py
│   ├── customer_analysis.py
│   ├── currency_analysis.py
│   └── financial_health.py
│
├── rules/
│   ├── vat_rules.py
│   ├── financial_rules.py
│   └── currency_rules.py
│
├── services/
│   ├── exchange_rates.py
│   ├── llm_service.py
│   └── translation_service.py
│
├── database/
│   ├── database.py
│   ├── schema.sql
│   └── seed.py          # NEW: rebuilds demo data + history on cold start
│
├── locales/
│   ├── en.json
│   ├── sn.json
│   └── nd.json
│
├── ui/
│   ├── dashboard.py
│   ├── charts.py
│   ├── reports.py
│   ├── watermark.py
│   └── components.py
│
├── data/
│   └── sample_transactions.csv
│
├── reports/
│
└── tests/
    ├── test_financials.py
    ├── test_anomalies.py
    ├── test_forecasting.py
    ├── test_vat.py
    ├── test_currency.py
    └── test_validation.py
```

---

# 5. DATA INPUT

Allow users to upload CSV or Excel with fields:

```text
transaction_id, date, description, account, customer, supplier,
transaction_type, category, amount, currency, payment_method,
invoice_number, vat_status
```

Validate: missing columns, missing values, invalid dates, invalid amounts, incorrect data types, duplicate transaction IDs, invalid transaction types, missing descriptions, invalid currency codes, invalid VAT classifications.

Display validation results clearly, e.g.:

```text
DATA VALIDATION

✓ 4,850 valid transactions
✓ No duplicate transaction IDs
⚠ 12 transactions missing VAT status
⚠ 5 transactions contain unknown currencies
```

---

# 6. FINANCIAL ANALYSIS ENGINE (CORE — build first, per 0A.3)

All financial calculations must be performed **deterministically in Python. Never let the LLM calculate financial figures.**

**Revenue:** Total, Growth, Average Monthly, by Category, by Customer, by Currency
**Expenses:** Total, Operating, Growth, by Category, by Supplier, by Currency
**Profitability:** Gross Profit & Margin, Operating Profit & Margin, Net Profit & Margin
**Liquidity:** Cash Inflows/Outflows, Net Cash Flow, Current Ratio, Quick Ratio
**Working Capital:** Receivables, Payables, and their trends

---

# 7. FINANCIAL HEALTH SCORE (CORE)

Transparent 0–100 score, configurable weighting:

```text
Profitability       25%
Liquidity           25%
Cash Flow           20%
Receivables         15%
Expense Control     15%
```

```text
FINANCIAL HEALTH

78 / 100

GOOD
```

Must be expandable: "How was this score calculated?" showing each component. Never an unexplained black box.

---

# 8. ANOMALY DETECTION AGENT (CORE)

Methods: Isolation Forest, Z-score, historical averages, transaction frequency, duplicate detection, supplier/customer behaviour, category-level comparisons.

Each flagged transaction gets: Transaction ID, Risk Score, Risk Level, Reason(s), Recommended Action.

```text
TX1045
Amount: USD 18,500
Risk: HIGH

Reasons:
• Amount is significantly above historical supplier payments.
• Similar payments occurred recently.
• Transaction is unusual for this category.

Recommended Action:
Review supporting documentation before approval.
```

Never claim a transaction is fraudulent — use "potential anomaly," "requires review," "unusual transaction," "high-risk transaction" only.

Per Section 0A.4, also apply this agent to exchange-rate inputs themselves (a stale/outlier FX rate is itself an anomaly worth flagging).

---

# 9. CASH-FLOW FORECASTING AGENT (CORE)

Forecast horizons: 7 / 14 / 30 / 60 / 90 days.

Show historical cash flow, forecast cash flow, expected inflows/outflows, expected closing balance, and forecast confidence where appropriate.

Indicators: 🟢 Healthy · 🟡 Watch · 🔴 Potential cash shortage

Explain the main drivers in plain language, e.g.:

```text
30-DAY CASH FORECAST
Expected Closing Cash: USD 4,250
Status: 🟡 WATCH

Main reason:
Expected supplier payments are increasing while
customer collections are slowing.
```

---

# 10. CUSTOMER PAYMENT RISK (CORE)

Calculate: average payment delay, outstanding receivables, payment frequency, customer concentration, late-payment patterns, average invoice value.

Assign LOW / MEDIUM / HIGH risk with recommended actions (send reminder, monitor customer, review credit terms, follow up outstanding invoice, escalate overdue account). Do not make unsupported claims about customers.

---

# 11. VAT ANALYSIS (CORE)

Deterministic VAT rules engine: identify VAT transactions, separate input/output VAT, calculate VAT amounts, identify missing VAT information, flag transactions requiring review, produce VAT summaries, maintain an audit trail of VAT calculations. Use configurable VAT rates stored separately from code — do not hard-code rates that may change.

Always display:

```text
NYASHA AI is a financial decision-support tool and
does not replace professional tax or accounting advice.
```

---

# 12. MULTI-CURRENCY SUPPORT (CORE)

Minimum currencies: USD, ZWL, ZAR, GBP, EUR, BWP, ZMW — designed so more can be added easily.

Each transaction retains its original currency and amount. The system must:
1. Preserve original amounts and currencies.
2. Convert to the selected reporting currency.
3. Display the exchange rate used, its date/time, and its source.
4. Support historical exchange rates where available.
5. Never silently mix currencies.

---

# 13. LIVE EXCHANGE RATES (CORE)

`services/exchange_rates.py` provides `get_live_rate()`, `convert_currency()`, `get_historical_rate()`, `get_supported_currencies()`.

Display rate, last-updated timestamp, and source. Allow ad-hoc conversion (From/To/Amount → Converted Amount, Rate, Timestamp, Source).

Clearly distinguish LIVE / HISTORICAL / CACHED / USER-DEFINED rates — never label a cached or manual rate as live.

If the exchange-rate service fails: don't crash, fall back to cached data (clearly labeled, with last-update time), and allow manual rate entry in demo mode.

---

# 14. CURRENCY EXPOSURE ANALYSIS (CORE)

Show foreign-currency receivables/payables by currency, currency concentration, exchange-rate movements, potential exchange gains/losses, and an overall currency risk rating with a plain-language explanation, e.g.:

```text
CURRENCY RISK: MEDIUM
The business has significant ZAR receivables.
Changes in the ZAR/USD exchange rate may affect
their value when reported in USD.
```

---

# 15. MULTI-LANGUAGE SUPPORT (DIFFERENTIATOR — build after core is solid)

Support English, Shona, Ndebele via `/locales/en.json`, `sn.json`, `nd.json`, with a 🌐 language selector affecting navigation, labels, buttons, help content, error messages, financial explanations, AI responses, reports, and notifications — switchable without restart.

The AI Financial Assistant must answer in the selected language, e.g.:

```text
Language: Shona
User: Sei mari yebhizinesi iri kudzikira?
AI: Mari iri kudzikira nekuda kwekuwedzera kwemari
    iri kubuda uye kunonoka kubhadharwa kwevatengi.
```

Translations must never alter financial figures or calculations.

---

# 16. BRIEF EXPLANATION OF RESULTS

Every major financial result needs a short plain-language explanation — Value + Change + Status + "what this means" + "why it matters." Never show a bare number.

```text
NET PROFIT
USD 12,450
↑ 14.2%

What this means:
The business earned USD 12,450 after deducting
recorded expenses from revenue.
```

---

# 17. AI FINANCIAL INTELLIGENCE

**The LLM must never calculate raw financial figures.** Python calculates everything (revenue, expenses, profit, margins, ratios, VAT, forecasts, risk scores, currency conversions); the AI only explains, summarizes, reasons over verified results, and recommends — always traceable to actual system data. Cache explanations per analysis run (see 0A.2).

```text
Verified Data:
Revenue = USD 50,000 | Expenses = USD 38,000 | Net Profit = USD 12,000
Net Margin = 24% | Cash Balance = USD 8,500
High Risk Transactions = 4 | 30-Day Forecast = USD 3,200

AI response:
Financial Health: MODERATE
The business is profitable, but projected cash reserves are falling.

Main concerns:
1. Increasing operating expenses.
2. Slow customer collections.
3. Several unusual supplier transactions.

Recommended actions:
1. Follow up outstanding receivables.
2. Review large supplier payments.
3. Monitor cash commitments over the next 30 days.
```

---

# 18. AI ORCHESTRATOR

Use LangGraph:

```text
START → Data Validation → Classification → Currency
      → Financial Analysis
      → [VAT | Anomaly | Forecast] (parallel)
      → Customer Analysis
      → Financial Intelligence
      → Recommendation
      → Reporting
      → END
```

The orchestrator determines which modules are required per request rather than always running the full graph.

---

# 19. AI FINANCIAL ASSISTANT

Chat interface answering questions like "Why did expenses increase this month?", "Which customers owe us the most?", "What are my biggest financial risks?", "Will the business have enough cash next month?", "Which transactions should I investigate?", "Why is my financial health score low?", "What should management do this month?", "Explain my VAT position.", "How is currency risk affecting my business?" — always from verified data. If unavailable: "I cannot determine this from the available transaction data." Never invent figures.

---

# 20. HELP & INQUIRY CENTRE

❓ Help covering NYASHA AI usage, financial ratios, VAT, cash flow, anomaly detection, exchange rates, currency conversion, forecasting, financial health, uploading data, generating reports — with FAQs on current ratio, net profit, cash flow, anomalies, flagged transactions, VAT calculation, health score changes, exchange rate sourcing, forecasting mechanics.

---

# 21. CONTEXT-AWARE HELP

Small "ⓘ" help affordances throughout ("What is this?", "Why was this flagged?", "How was this calculated?", "What does this ratio mean?", "Why did the forecast change?", "Why did my financial health score change?") — click for a short explanation.

---

# 22. USAGE HISTORY (DIFFERENTIATOR)

📚 Record timestamp, user action, dataset, analysis type, currency, language, AI inquiry, exchange-rate request, report generated. Support search, filter (date/action/type/currency), export, and clear-with-confirmation.

Remember: within a demo session this table lives in SQLite; on redeploy it resets per Section 0A.1 — the seed script should leave a small illustrative history so the page never looks empty on a fresh deploy.

---

# 23. ANALYSIS HISTORY (DIFFERENTIATOR)

📊 Preserve past analysis results (date, dataset, revenue, expenses, profit, cash balance, health score, risk level, recommendations) and allow period comparison, e.g.:

```text
JANUARY vs FEBRUARY
Revenue        +12%
Expenses        +7%
Profit         +18%
Cash Flow       -5%
Risk Level     MEDIUM → HIGH
```

---

# 24. AUDIT TRAIL (DIFFERENTIATOR)

Auditable SQLite record of timestamp, user action, transaction IDs, analysis type, original/reporting currency, exchange rate + source, calculation results, AI recommendation, risk level. For currency conversions, log original amount/currency, rate, reporting currency, converted amount, rate date, rate source. Must be user-viewable and make calculations traceable.

---

# 25. MANAGEMENT DASHBOARD

KPI cards: Revenue, Expenses, Net Profit, Cash Balance, Profit Margin, Financial Health Score.

Charts: revenue/expense/profit/cash-flow trends, expense breakdown, revenue by customer, receivables ageing, anomaly transactions, cash-flow forecast, currency exposure.

Filters: date, customer, supplier, category, transaction type, currency, risk level.

---

# 26. SMART RESULT CARDS

Consistent card format — Metric, Value, Change, Status, Brief Explanation, "Why?" option:

```text
┌────────────────────────────────────┐
│ NET PROFIT                         │
│ USD 12,450          ↑ 14.2%        │
│                                    │
│ 💡 What this means                 │
│ Profit increased mainly because    │
│ revenue grew faster than expenses. │
└────────────────────────────────────┘
```

---

# 27. REPORT GENERATION

Professional management report: Executive Summary, Financial Performance, Revenue/Expense/Profitability/Liquidity/Cash Flow/Receivables Analysis, Customer Risk, Anomaly Detection, VAT Summary, Currency Exposure, Exchange Rate Analysis, Financial Health Score, Key Risks, AI Recommendations, Management Actions, Audit Trail Summary — respecting selected language, reporting currency, and date range. Export where practical (PDF/Word).

---

# 28. DEMONSTRATION MODE

Built-in sample dataset — "Moyo Retail & Services," 12 months, realistic SME transactions (sales, purchases, rent, salaries, utilities, transport, supplier payments, customer receipts, bank charges, operating expenses) across multiple currencies, with deliberately unusual transactions for anomaly detection and realistic FX transactions to demo currency conversion. This dataset also powers the seed script from Section 0A.1.

---

# 29. USER EXPERIENCE / NAVIGATION

```text
🏠 Home · 📊 Dashboard · 📁 Upload Data · 💰 Financial Analysis
🔍 Anomaly Detection · 💵 Cash Flow Forecast · 👥 Customer Analysis
🧾 VAT Analysis · 💱 Currency & Exchange Rates · 🤖 AI Financial Assistant
❓ Help & Inquiry · 📚 Usage History · 📊 Analysis History
📄 Reports · 📜 Audit Trail · ⚙️ Settings
```

---

# 30. NYASHA BRANDING

Use **NYASHA AI** consistently everywhere (page titles, sidebar, home screen, reports, dashboard, help, footer, docs, error pages). Never use any prior working name.

---

# 31. FULL-PAGE NYASHA WATERMARK (COSMETIC — build last)

Faint, full-page "NYASHA" / "NYASHA AI" watermark on every page — light, behind content, never hurting readability, consistent across dashboard/reports/settings/history/analysis. Build as `ui/watermark.py`, implemented via Streamlit/CSS, low opacity, resembling a professional document watermark.

---

# 32. SETTINGS

⚙️ Language, Base Currency, Reporting Currency, Exchange Rate Source, Exchange Rate Refresh (on/off + manual refresh), Date Format, Number Format, AI Preferences, Notification Preferences.

---

# 33. ERROR HANDLING

Never crash on missing columns, empty files, invalid dates, missing values, incorrect data types, invalid currencies, API failure, missing API key, exchange-rate failure, database errors, or LLM failure. Friendly messages only — never expose stack traces to end users.

---

# 34. SECURITY

Never hard-code API keys — use `.env` / environment variables, ship `.env.example`. Never expose keys in source, logs, reports, database, or UI.

---

# 35. OFFLINE / DEMO MODE

If an external API is unavailable: use sample data, cached exchange rates, allow manual rates, provide a mock AI response if necessary — always clearly labeled as demo/mock data. The app must remain demonstrable without complex configuration.

---

# 36. TESTING

Automated tests for: revenue/expense/profit calculations, margins, ratios, VAT, duplicate detection, data validation, anomaly detection, cash-flow calculations, forecasting, financial health score, currency conversion, historical exchange rates, multi-currency totals.

Edge cases: empty dataset, missing values, unknown currency, zero values, negative values, duplicate transactions, unavailable exchange-rate API, unavailable LLM.

---

# 37. AI DESIGN PRINCIPLE (STRICT)

**Python handles:** financial calculations, VAT, ratios, currency conversion, exchange-rate math, anomaly scores, forecast calculations, financial health scores, data validation, database operations.

**AI handles:** explanation, natural-language Q&A, summaries, interpretation, reasoning over verified results, recommendations, management commentary, report commentary.

The LLM must never invent financial figures.

---

# 38. DATA LINEAGE

Every important result must be traceable: `SOURCE TRANSACTION → CALCULATION → RESULT → AI EXPLANATION → RECOMMENDATION`. Critical for trust, accounting control, and university evaluation.

---

# 39. PROFESSIONAL DESIGN

Clean cards, clear typography, professional spacing, interactive charts, consistent icons, responsive layout, clear navigation, minimal clutter. No unnecessary animation. Usability first.

---

# 40. FINAL APPLICATION STRUCTURE

Same as Section 29's navigation tree. Every page carries the faint NYASHA AI watermark.

---

# 41. UNIVERSITY PRESENTATION SCENARIO (21-STEP LIVE DEMO)

1. Open NYASHA AI — branded home screen.
2. Select Language: English, Reporting Currency: USD.
3. Upload a multi-currency SME transaction dataset.
4. NYASHA AI validates the dataset.
5. Show valid/invalid/duplicate/missing-info/currencies-detected summary.
6. Retrieve live exchange rates.
7. Convert transactions into the reporting currency.
8. Display the financial dashboard (Revenue, Expenses, Profit, Cash Flow, Financial Health).
9. Click a result explanation.
10. Open Anomaly Detection — show a deliberately unusual transaction.
11. Open Cash Flow Forecast — show the 30-day forecast.
12. Open Customer Analysis — show at-risk customers.
13. Open VAT Analysis — show calculations and audit trail.
14. Open Currency Analysis — exposure, live rates, FX receivables/payables.
15. Ask the AI: "What are the three biggest financial risks facing this business?"
16. Change language to Shona; ask "Sei mari yebhizinesi iri kudzikira?" — AI responds in Shona.
17. Change reporting currency — show results reconverted.
18. Open Usage History — show all actions performed.
19. Open Analysis History — compare two periods.
20. Generate a professional management report.
21. Open Audit Trail — demonstrate traceability of the final results.

**Rehearse this exact sequence before presenting** — it is also the de facto integration test for the whole system.

---

# 42. FINAL DELIVERABLES

1. Fully working Streamlit application
2. Modular Python architecture
3. SQLite database + seed/reset script
4. Sample multi-currency dataset
5. LangGraph orchestration
6. LangChain integration
7. LLM integration
8. Financial analysis engine
9. Anomaly detection
10. Cash-flow forecasting
11. Customer payment analysis
12. VAT rules engine
13. Multi-currency engine
14. Live exchange-rate integration
15. Currency exposure analysis
16. Multi-language support (English/Shona/Ndebele)
17. Financial health score
18. Explainable AI
19. AI financial assistant
20. Help & Inquiry Centre
21. Usage History
22. Analysis History
23. Audit Trail
24. Professional dashboard
25. Management reports
26. Full-page NYASHA watermark
27. Error handling
28. Security configuration (.env, .env.example)
29. Demo/mock mode
30. Automated tests
31. README (including the "Implemented so far" checklist from 0B and the Streamlit Cloud persistence note from 0A.1)
32. requirements.txt

---

# 43. DEVELOPMENT ORDER (execute in this sequence; see Section 0B for the "done" bar at each stage)

```text
1. Project structure
2. Database + seed/reset script
3. Sample data
4. Data validation
5. Financial calculations              ┐
6. Multi-currency engine               │
7. Exchange-rate service               │  CORE — Section 0A.3
8. VAT engine                          │
9. Anomaly detection                   │
10. Cash-flow forecasting              │
11. Customer analysis                  │
12. Financial health score             ┘
13. LangGraph orchestration
14. LLM integration
15. Explainable AI
16. Multi-language system              ┐  DIFFERENTIATORS
17. Usage history                      │
18. Analysis history                   │
19. Audit trail                        ┘
20. Help & Inquiry
21. Streamlit dashboard
22. Reports
23. NYASHA watermark                       ← COSMETIC, do last
24. Automated tests
25. Full run-through of the Section 41 demo script, end to end
26. Fix all errors found in step 25
27. Final rehearsal of the presentation
```

Do not declare the project complete until the full Section 41 demo sequence has been run start to finish without manual intervention. If a dependency or external API is unavailable, fall back per Section 0A/35 rather than blocking progress.

Priorities, in order: **financial accuracy → reliability → explainability → AI orchestration → multi-currency → multi-language → user experience → auditability → visual polish.**

---

# FINAL PRODUCT NAME

## **NYASHA AI**
### Multilingual & Multi-Currency SME Financial Intelligence Agent

**Tagline:** "From Financial Data to Smarter Decisions."

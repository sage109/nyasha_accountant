# NYASHA AI
### Multilingual & Multi-Currency SME Financial Intelligence Agent
*"From Financial Data to Smarter Decisions."*

## Status

Built and tested in a sandboxed environment with **no network access** and
without `streamlit`/`langgraph`/`langchain`/`pydantic`/`anthropic` installed.
Everything that could be built and verified with just `pandas`, `numpy`,
`scikit-learn`, and the stdlib has been — this is the deterministic core the
whole system depends on for accuracy (Section 0A.3 of the master prompt).
The UI, orchestration, and live-LLM layers are wired up in code but need a
networked environment (your machine, or Claude Code with internet) to
install their dependencies and actually run.

### ✅ Implemented and tested (33/33 tests passing)

- [x] Project structure (Section 4)
- [x] SQLite schema + seed/reset script that survives ephemeral deploys (0A.1)
- [x] Sample dataset generator — "Moyo Retail & Services", 365 transactions,
      12 months, 7 currencies, deliberate anomalies + data-quality issues (Section 28)
- [x] Data validation (Section 5) — `analytics/validation.py`
- [x] Multi-currency normalisation with live/cached/manual rate labeling (12, 13)
      — `services/exchange_rates.py`, `analytics/currency_normalisation.py`
- [x] Financial calculations engine — revenue, expenses, profitability,
      liquidity, working capital (Section 6) — `analytics/financial_metrics.py`
- [x] Financial health score, fully explainable (Section 7) — `analytics/financial_health.py`
- [x] Anomaly detection — Isolation Forest + rule-based duplicate/z-score
      checks, plus FX-rate anomaly check (Section 8, 0A.4) — `analytics/anomaly_detection.py`
- [x] Cash-flow forecasting, 7/14/30/60/90-day horizons (Section 9) — `analytics/forecasting.py`
- [x] Customer payment risk (Section 10) — `analytics/customer_analysis.py`
- [x] VAT rules engine, configurable rates (Section 11) — `rules/vat_rules.py`
- [x] LLM service with a hard Python-computes/AI-explains boundary (17, 37)
      — `services/llm_service.py` (prompt logic ready; **not yet exercised
      against the live API** — test this first once you have network + a key)
- [x] Automated tests for all of the above, including edge cases (empty
      dataset, zero/negative amounts, unknown currency, missing VAT status,
      unavailable exchange-rate API) — `tests/`

### 🔧 Scaffolded, needs a networked environment to finish

- [ ] Streamlit dashboard, navigation, result cards, charts (Sections 25-26, 29)
- [ ] LangGraph orchestrator wiring the agents together (Section 18)
- [ ] Multi-language UI + locale files beyond the stub (Section 15)
- [ ] Usage history / analysis history / audit trail UI (writes already
      supported by `database/database.py` — needs Streamlit pages)
- [ ] Report generation / export (Section 27)
- [ ] NYASHA watermark component (Section 31) — cosmetic, do last per 0A.3
- [ ] Help & Inquiry Centre UI (Section 20-21)

## Running what's built so far

```bash
pip install pandas numpy scikit-learn   # already covers everything below

# Regenerate the demo dataset (optional -- one is already committed)
python3 data/generate_sample_data.py

# Seed the database
python3 database/seed.py --force

# Run the test suite
python3 -m unittest discover -s tests -v
```

## Continuing the build (Claude Code / networked environment)

1. `pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and add your `ANTHROPIC_API_KEY`.
3. Build `app.py` + `ui/` around the existing `analytics/`, `rules/`, and
   `services/` modules — they're already unit-tested, so the UI layer should
   just call into them, not reimplement any calculation.
4. Wire `agents/orchestrator.py` with LangGraph per Section 18, calling the
   same `analytics/`/`rules/` functions as the UI does.
5. Test `services/llm_service.py` against the real API before the demo —
   it's untested against a live endpoint.
6. Follow Section 41's 21-step demo script as your integration test.

## Known limitations to flag in the writeup

- Streamlit Community Cloud's filesystem is ephemeral — `database/seed.py`
  handles this, but say so explicitly in the presentation rather than let it
  surprise you live (Section 0A.1).
- Liquidity ratios and receivables/payables are computed as proxies from
  transaction categories, since a transaction feed alone doesn't carry a
  formal balance sheet or AR/AP subledger — documented inline in
  `analytics/financial_metrics.py` and `analytics/customer_analysis.py`.
- The bundled FX rate table (`services/exchange_rates.py`) is illustrative
  and will be stale by demo day, especially for ZWL — always let it attempt
  a live fetch first; only fall back for the offline rehearsal.

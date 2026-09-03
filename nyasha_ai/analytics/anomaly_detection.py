"""
analytics/anomaly_detection.py

Anomaly detection per Section 8. Combines:
  - Isolation Forest (scikit-learn) over amount + category-relative z-score
  - Rule-based duplicate detection (same supplier/customer, amount, and
    date within a short window, different transaction_id)
  - Category-level z-score outliers

Never labels anything "fraud" -- only "potential anomaly" / "requires
review" / "unusual transaction" / "high-risk transaction", per Section 8.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

RiskLevel = str  # "LOW" | "MEDIUM" | "HIGH"


@dataclass
class AnomalyFinding:
    transaction_id: str
    risk_score: float          # 0-1, higher = more unusual
    risk_level: RiskLevel
    reasons: list[str] = field(default_factory=list)
    recommended_action: str = "Review supporting documentation before approval."


def _risk_level_from_score(score: float) -> RiskLevel:
    if score >= 0.75:
        return "HIGH"
    if score >= 0.5:
        return "MEDIUM"
    return "LOW"


def _category_zscore(df: pd.DataFrame, amount_col: str) -> pd.Series:
    def z(group: pd.Series) -> pd.Series:
        std = group.std(ddof=0)
        if std == 0 or pd.isna(std):
            return pd.Series(0.0, index=group.index)
        return (group - group.mean()) / std

    return df.groupby("category")[amount_col].transform(z)


def _find_duplicates(df: pd.DataFrame, amount_col: str, window_days: int = 3) -> set[str]:
    """Flag transactions that closely resemble another transaction (same
    supplier/customer + amount) within a short date window -- a classic
    duplicate-submission pattern."""
    flagged: set[str] = set()
    key_col = df["supplier"].astype(str).where(df["supplier"].astype(str).str.strip() != "", df["customer"].astype(str))
    work = df.assign(_key=key_col).sort_values("date")

    for _, group in work[work["_key"].str.strip() != ""].groupby(["_key", amount_col]):
        if len(group) < 2:
            continue
        dates = group["date"].sort_values()
        for i in range(1, len(dates)):
            if (dates.iloc[i] - dates.iloc[i - 1]).days <= window_days:
                flagged.add(group["transaction_id"].iloc[i])
                flagged.add(group["transaction_id"].iloc[i - 1])
    return flagged


def detect_anomalies(
    df: pd.DataFrame,
    amount_col: str = "amount_reporting",
    contamination: float = 0.03,
    random_state: int = 42,
) -> list[AnomalyFinding]:
    """
    Returns one AnomalyFinding per transaction judged unusual (LOW findings
    are typically not surfaced in the UI, but are returned for completeness
    -- filter by risk_level in the caller).
    """
    work = df.dropna(subset=[amount_col]).copy()
    if work.empty or len(work) < 10:
        return []  # not enough data for a meaningful model

    work["_zscore"] = _category_zscore(work, amount_col)
    duplicate_ids = _find_duplicates(work, amount_col)

    # Isolation Forest over [amount, category z-score, transaction_type as int]
    features = pd.DataFrame({
        "amount": work[amount_col],
        "zscore": work["_zscore"],
        "is_expense": (work["transaction_type"] == "expense").astype(int),
    })
    iso = IsolationForest(contamination=contamination, random_state=random_state)
    iso.fit(features)
    raw_scores = -iso.score_samples(features)  # higher = more anomalous
    # normalise to 0-1
    lo, hi = raw_scores.min(), raw_scores.max()
    norm_scores = (raw_scores - lo) / (hi - lo) if hi > lo else np.zeros_like(raw_scores)

    findings: list[AnomalyFinding] = []
    for i, (_, row) in enumerate(work.iterrows()):
        score = float(norm_scores[i])
        reasons: list[str] = []

        if abs(row["_zscore"]) >= 3:
            reasons.append(f"Amount is significantly above historical {row['category']} transactions.")
            score = max(score, 0.8)
        elif abs(row["_zscore"]) >= 2:
            reasons.append(f"Amount is unusual for this category ({row['category']}).")
            score = max(score, 0.6)

        if row["transaction_id"] in duplicate_ids:
            reasons.append("A very similar transaction occurred within a few days -- possible duplicate.")
            score = max(score, 0.75)

        if score >= 0.5 and not reasons:
            reasons.append("Transaction pattern is statistically unusual relative to similar transactions.")

        if not reasons:
            continue  # not flagged

        level = _risk_level_from_score(score)
        action = {
            "HIGH": "Review supporting documentation before approval.",
            "MEDIUM": "Verify against supporting records; monitor for recurrence.",
            "LOW": "No action required; noted for awareness.",
        }[level]

        findings.append(AnomalyFinding(
            transaction_id=row["transaction_id"], risk_score=round(score, 3),
            risk_level=level, reasons=reasons, recommended_action=action,
        ))

    findings.sort(key=lambda f: f.risk_score, reverse=True)
    return findings


def check_rate_anomaly(rate: float, expected_range: tuple[float, float], currency: str) -> AnomalyFinding | None:
    """
    Per Section 0A.4: flag a stale/outlier exchange rate (particularly
    ZWL) as its own anomaly, since a bad FX rate silently corrupts every
    downstream figure.
    """
    low, high = expected_range
    if low <= rate <= high:
        return None
    return AnomalyFinding(
        transaction_id=f"FX-RATE-{currency}",
        risk_score=0.9,
        risk_level="HIGH",
        reasons=[f"{currency} exchange rate ({rate}) is far outside the expected range ({low}-{high})."],
        recommended_action="Verify the exchange rate manually before trusting converted figures.",
    )

"""
services/llm_service.py

Section 17 & 37 (STRICT): the LLM must NEVER calculate financial figures.
Every function in this module takes already-computed, verified numbers as
input and asks the LLM only to explain, summarise, or recommend based on
them. If you catch yourself wanting the LLM to "figure out the total" or
"estimate the margin" -- stop, that belongs in analytics/, not here.

Requires the ANTHROPIC_API_KEY environment variable (see .env.example).
This module has NOT been exercised against the live API in this sandbox
(no network) -- the prompt construction and verified-data-injection pattern
are ready to go, but test the actual API call in a networked environment
before the demo.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, is_dataclass
from typing import Any

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are the explanation and recommendation layer of NYASHA AI, \
a financial decision-support tool for Zimbabwean SMEs. You will be given VERIFIED \
financial figures that have already been calculated by deterministic Python code. \

Rules you must follow:
1. NEVER invent, estimate, or recalculate any number. Only use the figures given to you.
2. If the data needed to answer a question is not in what you were given, say: \
"I cannot determine this from the available transaction data."
3. Keep explanations short, plain-language, and specific to the numbers provided.
4. Never claim a transaction is fraudulent -- use "unusual", "potential anomaly", or \
"requires review" only.
5. Always tie recommendations back to the specific figures that motivate them.
6. If asked to respond in a language other than English, respond fully in that \
language, including all figures with their original values unchanged.
7. Always note that you are a decision-support tool, not a replacement for \
professional tax or accounting advice, when discussing VAT or tax matters."""


def _serialise(obj: Any) -> Any:
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, dict):
        return {k: _serialise(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialise(v) for v in obj]
    return obj


def _call_llm(user_prompt: str) -> str:
    """
    Thin wrapper around the Anthropic API. Isolated in its own function so
    it's the only place that needs changing if the SDK/model changes, and
    so it can be mocked in tests without touching prompt-construction logic.
    """
    try:
        import anthropic  # imported lazily -- not required for the rest of the app to load
    except ImportError as exc:
        raise RuntimeError(
            "The 'anthropic' package is not installed. Run: pip install anthropic"
        ) from exc

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key, "
            "or use demo/mock mode (Section 35)."
        )

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=MODEL,
        max_tokens=800,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


def _mock_response(reason: str) -> str:
    """Section 35: offline/demo fallback -- clearly labeled, never pretending to be a real AI response."""
    return (
        f"[DEMO MODE -- mock AI response, {reason}]\n\n"
        "The verified figures above show the business's current position. "
        "Connect a live LLM API key to get a full narrative explanation and recommendations here."
    )


def explain_financial_result(verified_data: dict[str, Any], language: str = "en") -> str:
    """
    General-purpose explainer: hands the LLM a dict of already-computed
    figures (e.g. from ProfitabilitySummary, FinancialHealthScore, etc.)
    and asks for a short management-style explanation.
    """
    payload = json.dumps(_serialise(verified_data), indent=2, default=str)
    prompt = (
        f"Language for your response: {language}\n\n"
        f"Verified financial data (already calculated -- do not recalculate anything):\n{payload}\n\n"
        "Provide: (1) a one-paragraph plain-language summary of what this means, "
        "(2) up to 3 main concerns if any, (3) up to 3 recommended management actions, "
        "each explicitly tied to a figure above."
    )
    try:
        return _call_llm(prompt)
    except RuntimeError as e:
        return _mock_response(str(e))


def answer_financial_question(question: str, verified_context: dict[str, Any], language: str = "en") -> str:
    """
    AI Financial Assistant (Section 19). `verified_context` should contain
    everything the assistant is allowed to reason over for this question --
    e.g. the current health score, profitability summary, top anomalies,
    forecast, etc. If the answer isn't derivable from verified_context, the
    system prompt instructs the model to say so rather than guess.
    """
    payload = json.dumps(_serialise(verified_context), indent=2, default=str)
    prompt = (
        f"Language for your response: {language}\n\n"
        f"Verified financial data available to you:\n{payload}\n\n"
        f"User question: {question}\n\n"
        "Answer using only the data above. If the data doesn't contain what's needed, "
        "say so explicitly rather than guessing."
    )
    try:
        return _call_llm(prompt)
    except RuntimeError as e:
        return _mock_response(str(e))

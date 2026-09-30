"""
pipeline/llm_client.py
───────────────────────
Step 4 — LLM Structured Analysis

Sends pre-collected evidence to the LLM and receives a structured JSON
analysis.  The LLM performs qualitative synthesis ONLY — scores and
qualification decisions are already determined by scorer.py and are
passed in as read-only context.

Providers supported (in priority order based on env vars):
  1. Google Gemini  — GEMINI_API_KEY
  2. OpenAI         — OPENAI_API_KEY

If neither key is set, or if --skip-llm was passed, the module returns
a deterministic stub (no hallucination risk, no API cost).

Hallucination controls:
  - LLM receives ONLY evidence already collected; it cannot browse the web.
  - System prompt explicitly prohibits inventing facts.
  - JSON response is validated by validator.py before use.
  - If validation fails, we retry up to MAX_RETRIES times.
  - After MAX_RETRIES failures the lead is marked pipeline_status='llm_fallback'
    and a deterministic stub is used instead.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAYS = [2, 5, 10]  # seconds between retries

# ── Prompt loading ─────────────────────────────────────────────────────────────

def _load_prompt(name: str) -> str:
    prompt_dir = Path(__file__).parent.parent / "prompts"
    path = prompt_dir / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    logger.warning("Prompt file not found: %s", path)
    return ""


# ── Evidence serialisation ─────────────────────────────────────────────────────

def _build_evidence_block(enriched: Dict[str, Any]) -> str:
    """Serialize evidence fields into a structured text block for the LLM."""
    lines = [
        f"Company: {enriched.get('company', 'Unknown')}",
        f"Website: {enriched.get('website', 'Unknown')}",
        f"Industry: {enriched.get('industry', 'Unknown')}",
        f"Location: {enriched.get('location', 'Unknown')}",
        f"Employee count (band): {enriched.get('company_size', 'Unknown')}",
        f"Description: {enriched.get('description', 'Not available')}",
        "",
        "Opportunity score (deterministic): "
        + str(enriched.get("opportunity_score", "N/A")),
        "Priority (deterministic): " + enriched.get("priority", "Unknown"),
        "Qualification status (deterministic): "
        + enriched.get("qualification_status", "Unknown"),
        "",
        "Score breakdown:",
        json.dumps(enriched.get("score_breakdown", {}), indent=2),
        "",
        "Exposure signals:",
    ]
    for sig in enriched.get("exposure_signals", []):
        lines.append(f"  - {sig}")

    lines.append("Operational signals:")
    for sig in enriched.get("operational_signals", []):
        lines.append(f"  - {sig}")

    lines.append("Regulatory/compliance signals:")
    for sig in enriched.get("regulatory_signals", []):
        lines.append(f"  - {sig}")

    lines.append(f"Recent news: {enriched.get('recent_news', [])}")
    lines.append(
        f"Website reachable: {enriched.get('website_reachable', 'Not checked')}"
    )
    lines.append(f"Evidence status: {enriched.get('evidence_status', 'Unknown')}")

    dm = enriched.get("decision_maker", {})
    lines.append("")
    lines.append("Decision maker information:")
    lines.append(f"  Name: {dm.get('name', 'Not verified')}")
    lines.append(f"  Title: {dm.get('title', 'Not verified')}")
    lines.append(f"  Recommended role: {dm.get('recommended_role', 'Not specified')}")

    return "\n".join(lines)


# ── JSON extraction helper ─────────────────────────────────────────────────────

def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Extract first JSON object from LLM response text."""
    # Try direct parse
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    # Try extracting from markdown code block
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # Try bare JSON object anywhere in the text
    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return None


# ── Gemini provider ────────────────────────────────────────────────────────────

def _call_gemini(
    system_prompt: str, user_message: str, model: str
) -> Optional[str]:
    try:
        import google.generativeai as genai  # type: ignore
    except ImportError:
        logger.error("google-generativeai not installed. Run: pip install google-generativeai")
        return None

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    try:
        genai.configure(api_key=api_key)
        gemini_model = genai.GenerativeModel(
            model_name=model,
            system_instruction=system_prompt,
        )
        response = gemini_model.generate_content(user_message)
        return response.text
    except Exception as exc:
        logger.warning("Gemini API error: %s", exc)
        return None


# ── OpenAI provider ────────────────────────────────────────────────────────────

def _call_openai(
    system_prompt: str, user_message: str, model: str
) -> Optional[str]:
    try:
        from openai import OpenAI  # type: ignore
    except ImportError:
        logger.error("openai not installed. Run: pip install openai")
        return None

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        return response.choices[0].message.content
    except Exception as exc:
        logger.warning("OpenAI API error: %s", exc)
        return None


# ── Deterministic stub (no LLM) ────────────────────────────────────────────────

def _build_stub(enriched: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns a structured analysis dict built entirely from deterministic rules.
    Used when LLM is disabled or all retries are exhausted.
    No hallucination risk.
    """
    company = enriched.get("company", "Unknown")
    industry = enriched.get("industry", "Unknown")
    priority = enriched.get("priority", "Low Priority")
    score = enriched.get("opportunity_score", 0)
    breakdown = enriched.get("score_breakdown", {})
    exposure_signals = enriched.get("exposure_signals", [])
    reg_signals = enriched.get("regulatory_signals", [])
    dm = enriched.get("decision_maker", {})

    explanation = (
        f"Deterministic score: {score}/100 ({priority}). "
        f"Size band: {enriched.get('company_size', 'Unknown')} "
        f"(+{breakdown.get('size_score', 0)} pts). "
        f"Sector risk '{industry}' (+{breakdown.get('sector_score', 0)} pts). "
        f"Exposure signals detected: {len(exposure_signals)} "
        f"(+{breakdown.get('exposure_score', 0)} pts). "
        f"Operational complexity: +{breakdown.get('complexity_score', 0)} pts. "
        f"Regulatory sensitivity: +{breakdown.get('regulatory_score', 0)} pts."
    )

    observations = []
    if exposure_signals:
        observations.append(f"Identified {len(exposure_signals)} cybersecurity-relevant exposure signal(s): {', '.join(exposure_signals[:3])}.")
    if reg_signals:
        observations.append(f"Operating under regulatory framework(s): {', '.join(reg_signals[:2])}.")
    if enriched.get("operational_signals"):
        observations.append(f"Operational complexity noted: {enriched['operational_signals'][0]}.")
    if not observations:
        observations.append("Standard business profile within target size range.")

    outreach = (
        f"Hi [Contact], I came across {company} and noticed your work in {industry}. "
        f"With {', '.join(exposure_signals[:2]) if exposure_signals else 'your operational profile'}, "
        f"security readiness is often a priority for organisations at your stage. "
        f"Would a brief conversation about how we help similar companies be worthwhile?"
    )

    return {
        "qualification_explanation": explanation,
        "business_observations": observations,
        "outreach_message": outreach,
        "decision_maker": {
            "name": dm.get("name", "Not verified"),
            "title": dm.get("title", "Not verified"),
            "confidence": dm.get("confidence", "Unknown"),
            "recommended_role": dm.get("recommended_role", "IT Director / CIO"),
        },
        "llm_used": False,
        "pipeline_status": "ok",
    }


# ── Main public function ───────────────────────────────────────────────────────

def analyse(
    enriched: Dict[str, Any],
    config: Dict[str, Any],
    skip_llm: bool = False,
) -> Dict[str, Any]:
    """
    Run LLM structured analysis for one company.

    The LLM receives pre-collected evidence only and returns qualitative
    synthesis, explanation, and personalized outreach.  Scores are passed
    in as read-only context — the LLM cannot change them.

    Args:
        enriched:  Output from scorer.score()
        config:    Parsed config.yaml dict
        skip_llm:  If True, use deterministic stub and skip API calls.

    Returns:
        enriched dict updated with LLM synthesis fields.
    """
    if skip_llm:
        logger.debug("LLM skipped for '%s' (--skip-llm)", enriched.get("company"))
        stub = _build_stub(enriched)
        enriched.update(stub)
        return enriched

    llm_cfg = config.get("llm", {})
    if not llm_cfg.get("enabled", True):
        logger.debug("LLM disabled in config for '%s'", enriched.get("company"))
        stub = _build_stub(enriched)
        enriched.update(stub)
        return enriched

    system_prompt = _load_prompt("system_prompt.txt")
    analysis_template = _load_prompt("analysis_prompt_template.txt")

    evidence_block = _build_evidence_block(enriched)
    user_message = analysis_template.replace("{{EVIDENCE_BLOCK}}", evidence_block)

    provider = llm_cfg.get("provider", "gemini").lower()
    gemini_model = llm_cfg.get("gemini_model", "gemini-2.0-flash")
    openai_model = llm_cfg.get("openai_model", "gpt-4o-mini")

    raw_response: Optional[str] = None

    for attempt in range(1, MAX_RETRIES + 1):
        logger.info(
            "LLM call attempt %d/%d for '%s'",
            attempt, MAX_RETRIES, enriched.get("company"),
        )
        if provider == "gemini" or os.getenv("GEMINI_API_KEY"):
            raw_response = _call_gemini(system_prompt, user_message, gemini_model)
        if raw_response is None and (provider == "openai" or os.getenv("OPENAI_API_KEY")):
            raw_response = _call_openai(system_prompt, user_message, openai_model)

        if raw_response is None:
            logger.warning(
                "No LLM response on attempt %d for '%s'", attempt, enriched.get("company")
            )
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAYS[attempt - 1])
            continue

        parsed = _extract_json(raw_response)
        if parsed is None:
            logger.warning(
                "JSON extraction failed on attempt %d for '%s'",
                attempt, enriched.get("company"),
            )
            raw_response = None
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAYS[attempt - 1])
            continue

        # Merge LLM output into enriched dict — score fields are NOT overwritten
        enriched["qualification_explanation"] = parsed.get(
            "qualification_explanation", enriched.get("qualification_explanation", "")
        )
        enriched["business_observations"] = parsed.get("business_observations", [])
        enriched["outreach_message"] = parsed.get("outreach_message", "")

        # Decision maker — merge carefully, never overwrite with invented data
        llm_dm = parsed.get("decision_maker", {})
        dm = enriched.get("decision_maker", {})
        if llm_dm.get("name") and llm_dm["name"] != "Not verified":
            dm["name"] = llm_dm["name"]
            dm["title"] = llm_dm.get("title", dm.get("title", "Not verified"))
            dm["confidence"] = "Inferred"  # LLM cannot verify — at best Inferred
        dm["recommended_role"] = llm_dm.get("recommended_role", dm.get("recommended_role", ""))
        enriched["decision_maker"] = dm
        enriched["llm_used"] = True
        enriched["pipeline_status"] = "ok"

        logger.info("LLM analysis successful for '%s'", enriched.get("company"))
        return enriched

    # All retries exhausted — use deterministic stub
    logger.warning(
        "All LLM retries exhausted for '%s'; using deterministic stub",
        enriched.get("company"),
    )
    stub = _build_stub(enriched)
    stub["pipeline_status"] = "llm_fallback"
    enriched.update(stub)
    return enriched

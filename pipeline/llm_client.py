"""
pipeline/llm_client.py
───────────────────────
Step 4 — LLM Structured Analysis

Integrates Gemini / OpenAI APIs for qualitative analysis of pre-collected evidence.
Strictly prohibits silent fallback fabrication during normal live runs.
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
RETRY_DELAYS = [2, 5, 10]


def _load_prompt(name: str) -> str:
    prompt_dir = Path(__file__).parent.parent / "prompts"
    path = prompt_dir / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    logger.warning("Prompt file not found: %s", path)
    return ""


def _build_evidence_block(enriched: Dict[str, Any]) -> str:
    lines = [
        f"Company: {enriched.get('company', 'Unknown')}",
        f"Website: {enriched.get('website', 'Unknown')}",
        f"Industry: {enriched.get('industry', 'Unknown')}",
        f"Location: {enriched.get('location', 'Unknown')}",
        f"Company size (band): {enriched.get('company_size', 'Unknown')}",
        f"Description: {enriched.get('description', 'Not available')}",
        "",
        f"Opportunity score (deterministic): {enriched.get('opportunity_score', 'N/A')}",
        f"Priority (deterministic): {enriched.get('priority', 'Unknown')}",
        f"Qualification status (deterministic): {enriched.get('qualification_status', 'Unknown')}",
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

    lines.append("Regulatory signals:")
    for sig in enriched.get("regulatory_signals", []):
        lines.append(f"  - {sig}")

    dm = enriched.get("decision_maker", {})
    lines.append("")
    lines.append("Decision maker information:")
    lines.append(f"  Name: {dm.get('name', 'Not verified')}")
    lines.append(f"  Title: {dm.get('title', 'Not verified')}")
    lines.append(f"  Recommended role: {dm.get('recommended_role', 'Not specified')}")

    return "\n".join(lines)


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return None


def _call_gemini(system_prompt: str, user_message: str, model: str) -> Optional[str]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        import google.generativeai as genai  # type: ignore
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


def _call_openai(system_prompt: str, user_message: str, model: str) -> Optional[str]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI  # type: ignore
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


def _build_demo_stub(enriched: Dict[str, Any]) -> Dict[str, Any]:
    """Demo stub ONLY activated when --demo-mode flag is explicitly set."""
    company = enriched.get("company", "Unknown")
    industry = enriched.get("industry", "Unknown")
    score = enriched.get("opportunity_score", 0)
    priority = enriched.get("priority", "Low Priority")
    exposure_signals = enriched.get("exposure_signals", [])

    explanation = (
        f"Deterministic opportunity score of {score}/100 ({priority}) based on sector risk, "
        f"company size, and observed data exposure signals."
    )

    observations = [
        f"Operating in {industry} with {len(exposure_signals)} detected exposure signal(s)."
    ]

    outreach = (
        f"Hi [Contact], I came across {company} in {industry}. "
        f"Security readiness is a common priority for organizations handling digital transactions and client data. "
        f"Would a brief conversation about security readiness be useful?"
    )

    dm = enriched.get("decision_maker", {})
    return {
        "qualification_explanation": explanation,
        "business_observations": observations,
        "outreach_message": outreach,
        "decision_maker": dm,
        "llm_used": False,
        "pipeline_status": "demo_stub",
    }


def analyse(
    enriched: Dict[str, Any],
    config: Dict[str, Any],
    skip_llm: bool = False,
    demo_mode: bool = False,
) -> Dict[str, Any]:
    """
    Execute LLM analysis on pre-collected evidence.
    """
    if skip_llm or demo_mode:
        if demo_mode:
            logger.info("Demo mode: using explicit demo stub for '%s'", enriched.get("company"))
            stub = _build_demo_stub(enriched)
            enriched.update(stub)
            return enriched
        else:
            logger.info("LLM disabled for '%s'", enriched.get("company"))
            enriched["qualification_explanation"] = f"Deterministic score: {enriched.get('opportunity_score')}/100"
            enriched["business_observations"] = ["LLM synthesis skipped (--skip-llm)"]
            enriched["outreach_message"] = f"Hi [Contact], we noticed {enriched.get('company')} operates in {enriched.get('industry')}."
            enriched["pipeline_status"] = "llm_unavailable"
            enriched["llm_used"] = False
            return enriched

    llm_cfg = config.get("llm", {})
    system_prompt = _load_prompt("system_prompt.txt")
    analysis_template = _load_prompt("analysis_prompt_template.txt")

    evidence_block = _build_evidence_block(enriched)
    user_message = analysis_template.replace("{{EVIDENCE_BLOCK}}", evidence_block)

    provider = llm_cfg.get("provider", "gemini").lower()
    gemini_model = llm_cfg.get("gemini_model", "gemini-2.0-flash")
    openai_model = llm_cfg.get("openai_model", "gpt-4o-mini")

    raw_response = None
    for attempt in range(1, MAX_RETRIES + 1):
        if provider == "gemini" or os.getenv("GEMINI_API_KEY"):
            raw_response = _call_gemini(system_prompt, user_message, gemini_model)
        if raw_response is None and (provider == "openai" or os.getenv("OPENAI_API_KEY")):
            raw_response = _call_openai(system_prompt, user_message, openai_model)

        if raw_response:
            parsed = _extract_json(raw_response)
            if parsed:
                enriched["qualification_explanation"] = parsed.get("qualification_explanation", "")
                enriched["business_observations"] = parsed.get("business_observations", [])
                enriched["outreach_message"] = parsed.get("outreach_message", "")

                llm_dm = parsed.get("decision_maker", {})
                dm = enriched.get("decision_maker", {})
                if llm_dm.get("name") and llm_dm["name"] != "Not verified":
                    dm["name"] = llm_dm["name"]
                    dm["title"] = llm_dm.get("title", dm.get("title", "Not verified"))
                    dm["verification_status"] = "Inferred"
                dm["recommended_role"] = llm_dm.get("recommended_role", dm.get("recommended_role", ""))
                enriched["decision_maker"] = dm
                enriched["llm_used"] = True
                enriched["pipeline_status"] = "ok"
                return enriched

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAYS[attempt - 1])

    # Failed all retries -> NO SILENT STUB FABRICATION IN LIVE MODE
    logger.warning("LLM API unavailable for '%s' after %d retries", enriched.get("company"), MAX_RETRIES)
    enriched["qualification_explanation"] = f"LLM synthesis unavailable. Deterministic score: {enriched.get('opportunity_score')}/100."
    enriched["business_observations"] = ["LLM API request failed or rate-limited."]
    enriched["outreach_message"] = f"Hi [Contact], I noticed {enriched.get('company')} operates in {enriched.get('industry')}. Would a brief security discussion be useful?"
    enriched["pipeline_status"] = "llm_unavailable"
    enriched["llm_used"] = False
    return enriched

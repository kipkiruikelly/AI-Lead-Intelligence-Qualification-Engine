"""
pipeline/validator.py
─────────────────────
Step 5 — Validation Gate

Validates a fully enriched and analysed company dict against the
Pydantic LeadRecord schema before writing to output.

Validation failures are logged and the record is placed in the
review queue rather than silently accepted or discarded.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

from pydantic import ValidationError

# Adjust import path when running from project root
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from schemas.lead_schema import (
    DecisionMaker,
    EvidenceStatus,
    LeadRecord,
    Priority,
    QualificationStatus,
    ScoreBreakdown,
    SizeBand,
    SourceEvidence,
)

logger = logging.getLogger(__name__)


def _coerce_record(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Coerce raw dict fields into the shapes expected by LeadRecord.
    This prevents trivial type mismatches from sending records to review.
    """
    coerced = dict(data)

    # company_size
    size_raw = str(coerced.get("company_size", "Unknown")).strip()
    valid_sizes = {e.value for e in SizeBand}
    if size_raw not in valid_sizes:
        coerced["company_size"] = "Unknown"

    # priority
    priority_raw = str(coerced.get("priority", "Low Priority")).strip()
    valid_priorities = {e.value for e in Priority}
    if priority_raw not in valid_priorities:
        coerced["priority"] = "Low Priority"

    # qualification_status
    qs_raw = str(coerced.get("qualification_status", "Needs Review")).strip()
    valid_qs = {e.value for e in QualificationStatus}
    if qs_raw not in valid_qs:
        coerced["qualification_status"] = "Needs Review"

    # score_breakdown
    sb = coerced.get("score_breakdown", {})
    if not isinstance(sb, dict):
        sb = {}
    coerced["score_breakdown"] = {
        "size_score": int(sb.get("size_score", 0)),
        "sector_score": int(sb.get("sector_score", 0)),
        "exposure_score": int(sb.get("exposure_score", 0)),
        "complexity_score": int(sb.get("complexity_score", 0)),
        "regulatory_score": int(sb.get("regulatory_score", 0)),
        "bonus_score": int(sb.get("bonus_score", 0)),
        "total": int(sb.get("total", 0)),
    }

    # opportunity_score must match breakdown total
    coerced["opportunity_score"] = coerced["score_breakdown"]["total"]

    # decision_maker
    dm = coerced.get("decision_maker", {})
    if not isinstance(dm, dict):
        dm = {}
    conf_raw = dm.get("confidence", "Unknown")
    valid_conf = {e.value for e in EvidenceStatus}
    dm["confidence"] = conf_raw if conf_raw in valid_conf else "Unknown"
    dm.setdefault("name", "Not verified")
    dm.setdefault("title", "Not verified")
    coerced["decision_maker"] = dm

    # source_evidence
    raw_ev = coerced.get("source_evidence", [])
    cleaned_ev = []
    for item in raw_ev:
        if not isinstance(item, dict):
            continue
        ev_conf = item.get("evidence_status", "Unknown")
        if ev_conf not in valid_conf:
            ev_conf = "Unknown"
        cleaned_ev.append({
            "claim": str(item.get("claim", ""))[:500],
            "url": str(item.get("url", "")),
            "evidence_status": ev_conf,
        })
    coerced["source_evidence"] = cleaned_ev

    # business_observations — must be list of strings
    obs = coerced.get("business_observations", [])
    if isinstance(obs, str):
        obs = [obs] if obs else []
    coerced["business_observations"] = [str(o) for o in obs if o]

    # exposure_signals, operational_signals, regulatory_signals
    for field in ("exposure_signals", "operational_signals", "regulatory_signals"):
        val = coerced.get(field, [])
        if isinstance(val, str):
            val = [val] if val else []
        coerced[field] = [str(s) for s in val]

    # outreach_message — strip common template artifacts
    msg = str(coerced.get("outreach_message", ""))
    msg = msg.replace("{first_name}", "[Contact]").replace("{company_name}", coerced.get("company", ""))
    coerced["outreach_message"] = msg

    # Ensure string fields exist
    for field in ("description", "qualification_explanation", "website", "location", "industry"):
        coerced.setdefault(field, "Not available")

    # Booleans
    coerced["llm_used"] = bool(coerced.get("llm_used", False))
    coerced.setdefault("pipeline_status", "ok")

    return coerced


def validate(data: Dict[str, Any]) -> Tuple[LeadRecord | None, Dict[str, Any] | None]:
    """
    Validate a single enriched company dict.

    Returns:
        (LeadRecord, None)  — validation passed
        (None, error_dict)  — validation failed; error_dict is added to review queue
    """
    try:
        coerced = _coerce_record(data)
        record = LeadRecord(**coerced)
        return record, None
    except ValidationError as exc:
        error_info = {
            "company": data.get("company", "Unknown"),
            "validation_errors": exc.errors(),
            "raw_data_keys": list(data.keys()),
        }
        logger.warning(
            "Validation failed for '%s': %d error(s)",
            data.get("company", "Unknown"),
            len(exc.errors()),
        )
        for err in exc.errors():
            logger.debug("  → %s: %s", err.get("loc"), err.get("msg"))
        return None, error_info
    except Exception as exc:
        error_info = {
            "company": data.get("company", "Unknown"),
            "validation_errors": [{"msg": str(exc)}],
            "raw_data_keys": list(data.keys()),
        }
        logger.error(
            "Unexpected validation error for '%s': %s",
            data.get("company", "Unknown"),
            exc,
        )
        return None, error_info


def validate_batch(
    records: List[Dict[str, Any]],
) -> Tuple[List[LeadRecord], List[Dict[str, Any]]]:
    """
    Validate a list of enriched dicts.

    Returns:
        (valid_records, review_queue_items)
    """
    valid: List[LeadRecord] = []
    review: List[Dict[str, Any]] = []

    for data in records:
        record, error = validate(data)
        if record is not None:
            valid.append(record)
        else:
            review.append(error)

    logger.info(
        "Validation: %d passed, %d sent to review queue",
        len(valid), len(review),
    )
    return valid, review

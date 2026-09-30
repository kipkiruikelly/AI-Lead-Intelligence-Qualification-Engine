"""
Pydantic v2 schema definitions shared across the entire pipeline.
All LLM output must validate against LeadRecord before being written.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


# ─── Enums ────────────────────────────────────────────────────────────────────

class EvidenceStatus(str, Enum):
    VERIFIED = "Verified"
    INFERRED = "Inferred"
    UNKNOWN = "Unknown"


class QualificationStatus(str, Enum):
    QUALIFIED = "Qualified"
    NEEDS_REVIEW = "Needs Review"
    DISQUALIFIED = "Disqualified"


class Priority(str, Enum):
    HIGH = "High Priority"
    MEDIUM = "Medium Priority"
    LOW = "Low Priority"


class SizeBand(str, Enum):
    SMALL = "51-200"
    MEDIUM = "201-500"
    UNKNOWN = "Unknown"


# ─── Sub-models ───────────────────────────────────────────────────────────────

class SourceEvidence(BaseModel):
    claim: str = Field(..., min_length=1)
    url: str
    evidence_status: EvidenceStatus


class DecisionMaker(BaseModel):
    name: str = Field(
        default="Not verified",
        description="Person's name or 'Not verified' — never invented",
    )
    title: str = Field(
        default="Not verified",
        description="Job title or role label",
    )
    confidence: EvidenceStatus = EvidenceStatus.UNKNOWN
    recommended_role: Optional[str] = Field(
        default=None,
        description="Recommended target role when individual is unknown",
    )


class ScoreBreakdown(BaseModel):
    """Fully deterministic — set by scorer.py, never by the LLM."""
    size_score: int = Field(ge=0, le=20)
    sector_score: int = Field(ge=0, le=25)
    exposure_score: int = Field(ge=0, le=25)
    complexity_score: int = Field(ge=0, le=10)
    regulatory_score: int = Field(ge=0, le=10)
    bonus_score: int = Field(ge=0, le=10)
    total: int = Field(ge=0, le=100)


# ─── Main lead record ─────────────────────────────────────────────────────────

class LeadRecord(BaseModel):
    # Identity
    company: str = Field(..., min_length=1)
    website: str
    industry: str
    location: str
    company_size: SizeBand

    # Research
    description: str
    exposure_signals: List[str] = Field(default_factory=list)
    operational_signals: List[str] = Field(default_factory=list)
    regulatory_signals: List[str] = Field(default_factory=list)

    # Scoring (deterministic)
    score_breakdown: ScoreBreakdown
    opportunity_score: int = Field(ge=0, le=100)
    priority: Priority
    qualification_status: QualificationStatus

    # LLM synthesis
    qualification_explanation: str
    business_observations: List[str] = Field(default_factory=list)
    outreach_message: str

    # Decision maker
    decision_maker: DecisionMaker

    # Reliability
    source_evidence: List[SourceEvidence] = Field(default_factory=list)
    pipeline_status: str = Field(
        default="ok",
        description="'ok' | 'llm_fallback' | 'needs_review'",
    )
    llm_used: bool = False
    website_reachable: Optional[bool] = None

    @field_validator("opportunity_score")
    @classmethod
    def score_matches_breakdown(cls, v: int, info) -> int:
        if "score_breakdown" in info.data:
            expected = info.data["score_breakdown"].total
            if v != expected:
                raise ValueError(
                    f"opportunity_score {v} does not match score_breakdown.total {expected}"
                )
        return v

    @field_validator("outreach_message")
    @classmethod
    def outreach_not_generic(cls, v: str) -> str:
        forbidden = [
            "we provide cybersecurity services",
            "{first_name}",
            "{company_name}",
        ]
        lower = v.lower()
        for phrase in forbidden:
            if phrase.lower() in lower:
                raise ValueError(
                    f"Outreach message contains forbidden generic phrase: '{phrase}'"
                )
        return v


class PipelineResult(BaseModel):
    """Wrapper returned by the pipeline for the full run."""
    leads: List[LeadRecord]
    review_queue: List[dict] = Field(default_factory=list)
    run_metadata: dict = Field(default_factory=dict)

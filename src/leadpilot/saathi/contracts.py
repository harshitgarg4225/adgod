"""Structured I/O contracts for every sub-agent (PRD §11).

Each sub-agent MUST return JSON conforming to its `*Output` model. Invalid output
fails the run (no free-form side effects). Only the Closer contract is exercised
by the v1 walking skeleton; the rest are defined so later phases slot in.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from leadpilot.core.enums import ConversationState, LeadScore

# ─────────────────────────── Closer (v1) ───────────────────────────

class ReplyButton(BaseModel):
    id: str
    title: str = Field(max_length=20)  # WhatsApp quick-reply title limit


class CloserReply(BaseModel):
    type: str = Field(default="text", pattern="^(text|interactive)$")
    body: str
    buttons: list[ReplyButton] | None = None


class CloserCaptured(BaseModel):
    name: str | None = None
    intent: str | None = None
    budget: str | None = None
    timeline: str | None = None
    location: str | None = None


class CloserOutput(BaseModel):
    """Closer turn output. A deterministic scope guard re-validates `reply`."""

    reply: CloserReply
    next_state: ConversationState
    captured: CloserCaptured = Field(default_factory=CloserCaptured)
    score: LeadScore | None = None
    score_reasons: list[str] = Field(default_factory=list)


# ─────────────────────────── Scout ───────────────────────────

class BriefModel(BaseModel):
    offer: str
    audience: list[str] = Field(default_factory=list)
    usp: list[str] = Field(default_factory=list)
    objections: list[str] = Field(default_factory=list)
    tone: str = ""


class AngleModel(BaseModel):
    title: str
    rationale: str
    hypothesis: str


class ScoutOutput(BaseModel):
    brief: BriefModel
    angles: list[AngleModel] = Field(min_length=1)


# ─────────────────────────── Maker ───────────────────────────

class CopyVariant(BaseModel):
    primary_text: str
    headline: str
    description: str


class ComplianceSelfCheck(BaseModel):
    passed: bool
    notes: str = ""


class MakerOutput(BaseModel):
    variants: list[CopyVariant] = Field(min_length=1)
    image_prompts: list[str] = Field(default_factory=list)
    video_script: str | None = None
    compliance_self_check: ComplianceSelfCheck


# ─────────────────────────── Buyer ───────────────────────────

class BuyerGeo(BaseModel):
    city: str
    radius_km: int


class BuyerAdSet(BaseModel):
    role: str
    geo: BuyerGeo
    age_min: int = 18
    age_max: int = 65
    gender: str | None = None
    interests: list[str] = Field(default_factory=list)
    lookalike: bool = False
    budget_paise: int


class BuyerCampaignSpec(BaseModel):
    channel: str
    objective: str


class BuyerAdSpec(BaseModel):
    ad_set_role: str
    creative_id: str


class BuyerOutput(BaseModel):
    campaigns: list[BuyerCampaignSpec] = Field(min_length=1)
    ad_sets: list[BuyerAdSet] = Field(min_length=1)
    ads: list[BuyerAdSpec] = Field(default_factory=list)


# ─────────────────────────── Optimizer ───────────────────────────

class OptimizationDecision(BaseModel):
    level: str = Field(pattern="^(CAMPAIGN|ADSET|AD)$")
    ref_id: str
    action: str = Field(pattern="^(PAUSE|SCALE|REALLOCATE|REQUEST_CREATIVE|RESUME|NO_OP)$")
    reason_code: str
    params: dict = Field(default_factory=dict)


class OptimizerOutput(BaseModel):
    decisions: list[OptimizationDecision] = Field(default_factory=list)


# ─────────────────────────── Reporter ───────────────────────────

class ReporterOutput(BaseModel):
    message: str

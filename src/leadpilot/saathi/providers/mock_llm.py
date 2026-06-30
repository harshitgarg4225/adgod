"""Deterministic mock LLM (used when MOCK_LLM=true).

Implements a real, testable Closer qualification flow plus minimal valid stubs for
the other agents — so the whole Saathi loop runs in CI without API keys. The Closer
mock is intentionally faithful to the §6.6 state machine and §11.6 contract.
"""
from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from leadpilot.saathi.contracts import (
    AngleModel,
    BriefModel,
    BuyerAdSet,
    BuyerCampaignSpec,
    BuyerGeo,
    BuyerOutput,
    CloserCaptured,
    CloserOutput,
    CloserReply,
    ComplianceSelfCheck,
    CopyVariant,
    MakerOutput,
    OptimizerOutput,
    ReporterOutput,
    ScoutOutput,
)
from leadpilot.saathi.textutil import is_junk as _is_junk

TModel = TypeVar("TModel", bound=BaseModel)


def mock_generate(response_model: type[TModel], context: dict) -> TModel:
    handler = _HANDLERS.get(response_model)
    if handler is None:  # pragma: no cover - defensive
        raise NotImplementedError(f"No mock for {response_model.__name__}")
    return handler(context)


# ─────────────────────────── Closer ───────────────────────────

def _txt(lang: str, hi: str, en: str) -> str:
    return hi if lang == "hi" else en


def _extract_name(text: str) -> str:
    """Best-effort name extraction from common Hindi/English self-introductions."""
    import re

    t = text.strip()
    m = re.search(r"(?:mera naam|my name is|naam|i am|i'm|main)\s+([A-Za-zऀ-ॿ]+)",
                  t, re.I)
    if m:
        return m.group(1).strip().title()
    # Otherwise take the first word or two, trimming trailing filler ("hai", "है").
    cleaned = re.sub(r"\b(hai|hoon|hu|है|हूँ)\b", "", t, flags=re.I).strip()
    return (cleaned.split()[0].title() if cleaned.split() else t)[:80]


def _closer(ctx: dict) -> CloserOutput:
    state = ctx.get("state", "GREET")
    captured = CloserCaptured(**(ctx.get("captured") or {}))
    user_text = (ctx.get("user_text") or "").strip()
    lang = ctx.get("language", "hi")
    biz = ctx.get("business_name", "")
    category = ctx.get("category", "business")

    # Spam/junk: one polite redirect, then hand off (PRD §6.6.2 / §6.6.3 scope).
    if state != "GREET" and _is_junk(user_text):
        turns = int(ctx.get("junk_turns", 0))
        if turns >= 1:
            return CloserOutput(
                reply=CloserReply(
                    type="text",
                    body=_txt(lang,
                              "कोई बात नहीं! हमारी टीम आपसे जल्द संपर्क करेगी। 🙏",
                              "No problem! Our team will reach out to you shortly. 🙏"),
                ),
                next_state="HANDOFF",
                captured=captured,
                score="SPAM",
                score_reasons=["incoherent_after_redirect"],
            )
        return CloserOutput(
            reply=CloserReply(
                type="text",
                body=_txt(lang,
                          f"माफ़ कीजिए, मैं सिर्फ़ {biz} की पूछताछ में मदद कर सकता/सकती हूँ। "
                          "क्या आप हमारी सेवा के बारे में जानना चाहते हैं?",
                          f"Sorry, I can only help with enquiries for {biz}. "
                          "Would you like to know about our service?"),
            ),
            next_state=state,
            captured=captured,
        )

    if state == "GREET":
        return CloserOutput(
            reply=CloserReply(
                type="text",
                body=_txt(lang,
                          f"नमस्ते! 🙏 {biz} में आपका स्वागत है। मैं आपकी मदद के लिए हूँ। "
                          "आपका नाम क्या है?",
                          f"Hello! 🙏 Welcome to {biz}. I'm here to help. "
                          "May I know your name?"),
            ),
            next_state="CAPTURE_NAME",
            captured=captured,
        )

    if state == "CAPTURE_NAME":
        captured.name = _extract_name(user_text) or captured.name
        return CloserOutput(
            reply=CloserReply(
                type="text",
                body=_txt(lang,
                          f"शुक्रिया {captured.name}! 😊 आप किस चीज़ में रुचि रखते हैं — "
                          "हमें थोड़ा बताइए आपको क्या चाहिए?",
                          f"Thanks {captured.name}! 😊 What are you looking for — "
                          "tell us a little about what you need?"),
            ),
            next_state="CAPTURE_INTENT",
            captured=captured,
        )

    if state == "CAPTURE_INTENT":
        captured.intent = user_text[:200] or captured.intent
        return CloserOutput(
            reply=CloserReply(
                type="interactive",
                body=_txt(lang,
                          "बढ़िया! आप कब तक शुरू करना चाहते हैं और आपका बजट क्या है?",
                          "Great! When are you looking to start, and what's your budget?"),
                buttons=[
                    {"id": "soon", "title": _txt(lang, "जल्दी", "Soon")[:20]},
                    {"id": "month", "title": _txt(lang, "इस महीने", "This month")[:20]},
                    {"id": "exploring", "title": _txt(lang, "देख रहे हैं", "Exploring")[:20]},
                ],
            ),
            next_state="CAPTURE_BUDGET_TIMELINE",
            captured=captured,
        )

    if state == "CAPTURE_BUDGET_TIMELINE":
        captured.budget = user_text[:120] or captured.budget
        captured.timeline = user_text[:120] or captured.timeline
        return CloserOutput(
            reply=CloserReply(
                type="text",
                body=_txt(lang,
                          "समझ गया! आप किस इलाके/शहर से हैं? ताकि हम सही जानकारी दे सकें।",
                          "Got it! Which area/city are you in? So we can guide you correctly."),
            ),
            next_state="CAPTURE_LOCATION",
            captured=captured,
        )

    if state == "CAPTURE_LOCATION":
        captured.location = user_text[:120] or captured.location
        score, reasons = _score(captured)
        if score == "HOT":
            body = _txt(lang,
                        f"शानदार {captured.name}! 🙌 हमारी टीम आपको कुछ ही देर में कॉल करेगी "
                        f"और {category} की पूरी जानकारी देगी। धन्यवाद!",
                        f"Excellent {captured.name}! 🙌 Our team will call you shortly with "
                        f"full details about our {category}. Thank you!")
        else:
            body = _txt(lang,
                        "धन्यवाद! हम आपको जल्द ही और जानकारी भेजेंगे। 🙏",
                        "Thank you! We'll send you more details soon. 🙏")
        return CloserOutput(
            reply=CloserReply(type="text", body=body),
            next_state="CLOSE",
            captured=captured,
            score=score,
            score_reasons=reasons,
        )

    # SCORE / CLOSE / HANDOFF: conversation finished — gentle close.
    return CloserOutput(
        reply=CloserReply(
            type="text",
            body=_txt(lang, "धन्यवाद! 🙏", "Thank you! 🙏"),
        ),
        next_state="CLOSE",
        captured=captured,
    )


def _score(c: CloserCaptured) -> tuple[str, list[str]]:
    have = sum(bool(x) for x in (c.name, c.intent, c.budget or c.timeline, c.location))
    if have >= 4:
        return "HOT", ["name_intent_budget_location_captured"]
    if c.name and c.intent:
        return "WARM", ["partial_signal"]
    return "COLD", ["insufficient_signal"]


# ─────────────────────────── Other agents (minimal valid stubs) ───────────────────────────

def _scout(ctx: dict) -> ScoutOutput:
    offer = ctx.get("offer", "our service")
    city = ctx.get("city", "your city")
    angles = [
        AngleModel(title=f"Angle {i + 1}",
                   rationale=f"Resonates with local {ctx.get('category','customers')} in {city}.",
                   hypothesis="Drives qualified WhatsApp enquiries from serious buyers.")
        for i in range(8)
    ]
    return ScoutOutput(
        brief=BriefModel(offer=offer, audience=["local families"], usp=["trusted", "affordable"],
                         objections=["price", "trust"], tone="warm, local"),
        angles=angles,
    )


def _maker(ctx: dict) -> MakerOutput:
    return MakerOutput(
        variants=[
            CopyVariant(primary_text="Aaj hi WhatsApp par message karein!",
                        headline="Free consultation", description="Limited slots"),
        ],
        image_prompts=["A warm, local storefront photo, bright, trustworthy"],
        video_script=None,
        compliance_self_check=ComplianceSelfCheck(passed=True, notes="ok"),
    )


def _buyer(ctx: dict) -> BuyerOutput:
    city = ctx.get("city", "Indore")
    return BuyerOutput(
        campaigns=[BuyerCampaignSpec(channel="META_CTWA", objective="OUTCOME_LEADS")],
        ad_sets=[BuyerAdSet(role="PROSPECTING", geo=BuyerGeo(city=city, radius_km=10),
                            budget_paise=35000)],
        ads=[],
    )


def _optimizer(ctx: dict) -> OptimizerOutput:
    return OptimizerOutput(decisions=[])


def _reporter(ctx: dict) -> ReporterOutput:
    spend = (ctx.get("spend_paise", 0) or 0) // 100
    enq = ctx.get("enquiries", 0)
    qual = ctx.get("qualified", 0)
    cpql = (ctx.get("cpql_paise", 0) or 0) // 100
    dec = ctx.get("decisions", 0)
    lang = ctx.get("language", "hi")
    if lang == "hi":
        msg = (f"आज का हाल 🙏\n• खर्च: ₹{spend}\n• पूछताछ: {enq}\n"
               f"• पक्के ग्राहक: {qual}\n• प्रति ग्राहक लागत: ₹{cpql}\n"
               f"• Saathi ने {dec} सुधार किए। कल और बेहतर! 🚀")
    else:
        msg = (f"Today's update 🙏\n• Spent: ₹{spend}\n• Enquiries: {enq}\n"
               f"• Qualified: {qual}\n• Cost/qualified: ₹{cpql}\n"
               f"• Saathi made {dec} optimizations. Onward! 🚀")
    return ReporterOutput(message=msg)


_HANDLERS = {
    CloserOutput: _closer,
    ScoutOutput: _scout,
    MakerOutput: _maker,
    BuyerOutput: _buyer,
    OptimizerOutput: _optimizer,
    ReporterOutput: _reporter,
}

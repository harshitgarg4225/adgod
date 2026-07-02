"""Domain enums (string-valued). DB enforces these via CHECK constraints."""
from __future__ import annotations

from enum import StrEnum


class TenantType(StrEnum):
    DIRECT = "DIRECT"
    PARTNER = "PARTNER"


class AccountPhase(StrEnum):
    SIGNED_UP = "SIGNED_UP"
    ONBOARDING = "ONBOARDING"
    RESEARCHED = "RESEARCHED"
    CREATIVE_GENERATED = "CREATIVE_GENERATED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    LAUNCHING = "LAUNCHING"
    LIVE = "LIVE"
    OPTIMIZING = "OPTIMIZING"
    FATIGUE_REFRESH = "FATIGUE_REFRESH"
    PAUSED = "PAUSED"
    CHURNED = "CHURNED"


class AutopilotLevel(StrEnum):
    MANUAL = "MANUAL"
    ASSISTED = "ASSISTED"
    FULL = "FULL"


class UserRole(StrEnum):
    OWNER = "OWNER"
    PARTNER = "PARTNER"
    ADMIN = "ADMIN"
    OPS = "OPS"


class WhatsAppMode(StrEnum):
    APP_DESTINATION = "APP_DESTINATION"
    CLOUD_API = "CLOUD_API"


class Channel(StrEnum):
    META_CTWA = "META_CTWA"
    META_LEADFORM = "META_LEADFORM"


class LeadStatus(StrEnum):
    NEW = "NEW"
    ENGAGED = "ENGAGED"
    QUALIFYING = "QUALIFYING"
    QUALIFIED_HOT = "QUALIFIED_HOT"
    QUALIFIED_WARM = "QUALIFIED_WARM"
    DISQUALIFIED_COLD = "DISQUALIFIED_COLD"
    SPAM = "SPAM"
    BOOKED = "BOOKED"
    HANDED_OFF = "HANDED_OFF"
    WON = "WON"
    LOST = "LOST"
    NO_RESPONSE = "NO_RESPONSE"


class LeadScore(StrEnum):
    HOT = "HOT"
    WARM = "WARM"
    COLD = "COLD"
    SPAM = "SPAM"


class OwnerAction(StrEnum):
    NONE = "NONE"
    CALLED = "CALLED"
    WON = "WON"
    LOST = "LOST"
    FOLLOWUP = "FOLLOWUP"


class ConversationState(StrEnum):
    GREET = "GREET"
    CAPTURE_NAME = "CAPTURE_NAME"
    CAPTURE_INTENT = "CAPTURE_INTENT"
    CAPTURE_BUDGET_TIMELINE = "CAPTURE_BUDGET_TIMELINE"
    CAPTURE_LOCATION = "CAPTURE_LOCATION"
    SCORE = "SCORE"
    BOOK = "BOOK"
    HANDOFF = "HANDOFF"
    CLOSE = "CLOSE"


class MessageDirection(StrEnum):
    IN = "IN"
    OUT = "OUT"


class MessageType(StrEnum):
    TEXT = "TEXT"
    TEMPLATE = "TEMPLATE"
    MEDIA = "MEDIA"
    INTERACTIVE = "INTERACTIVE"


class MessageStatus(StrEnum):
    QUEUED = "QUEUED"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    READ = "READ"
    FAILED = "FAILED"


class AgentName(StrEnum):
    SCOUT = "SCOUT"
    MAKER = "MAKER"
    BUYER = "BUYER"
    OPTIMIZER = "OPTIMIZER"
    CLOSER = "CLOSER"
    REPORTER = "REPORTER"
    ORCHESTRATOR = "ORCHESTRATOR"


class AgentRunStatus(StrEnum):
    OK = "OK"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"


class GuardrailType(StrEnum):
    SPEND = "SPEND"
    COMPLIANCE = "COMPLIANCE"
    SCOPE = "SCOPE"
    APPROVAL = "APPROVAL"
    ANOMALY = "ANOMALY"
    DATA = "DATA"


class OutboxStatus(StrEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    FAILED = "FAILED"
    DEAD = "DEAD"


class JobStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"


class NotificationKind(StrEnum):
    HOT_LEAD = "HOT_LEAD"
    APPROVAL = "APPROVAL"
    ANOMALY = "ANOMALY"
    BILLING = "BILLING"
    REPORT = "REPORT"
    CREATIVE_READY = "CREATIVE_READY"
    CAMPAIGN_LIVE = "CAMPAIGN_LIVE"


class CampaignStatus(StrEnum):
    DRAFT = "DRAFT"
    IN_REVIEW = "IN_REVIEW"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    ARCHIVED = "ARCHIVED"


class AdSetRole(StrEnum):
    PROSPECTING = "PROSPECTING"   # proven winners (the "SCALE" tier)
    LOOKALIKE = "LOOKALIKE"
    TESTING = "TESTING"           # 1 creative per ad set, in isolation
    RETARGETING = "RETARGETING"   # site/video viewers


class CreativeFormat(StrEnum):
    IMAGE_VERTICAL = "IMAGE_VERTICAL"
    IMAGE_SQUARE = "IMAGE_SQUARE"
    VIDEO_9_16 = "VIDEO_9_16"


class ComplianceStatus(StrEnum):
    PENDING = "PENDING"
    PASSED = "PASSED"
    FAILED = "FAILED"


class ApprovalState(StrEnum):
    DRAFT = "DRAFT"
    APPROVED_FOR_LAUNCH = "APPROVED_FOR_LAUNCH"
    REJECTED = "REJECTED"


class InsightLevel(StrEnum):
    ACCOUNT = "ACCOUNT"   # daily per-account rollup — the dashboard/month-cap source
    CAMPAIGN = "CAMPAIGN"
    ADSET = "ADSET"
    AD = "AD"


class OptimizationAction(StrEnum):
    PAUSE = "PAUSE"
    SCALE = "SCALE"
    REALLOCATE = "REALLOCATE"     # move freed budget from losers to winners
    PROMOTE = "PROMOTE"           # a test winner graduates into the prospecting tier
    REQUEST_CREATIVE = "REQUEST_CREATIVE"
    RESUME = "RESUME"
    NO_OP = "NO_OP"


class ApprovalKind(StrEnum):
    CREATIVE_BATCH = "CREATIVE_BATCH"
    BUDGET_INCREASE = "BUDGET_INCREASE"
    LAUNCH = "LAUNCH"


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class SubscriptionTier(StrEnum):
    STARTER = "STARTER"
    GROWTH = "GROWTH"
    PRO = "PRO"


class SubscriptionStatus(StrEnum):
    TRIAL = "TRIAL"
    ACTIVE = "ACTIVE"
    PAST_DUE = "PAST_DUE"
    CANCELLED = "CANCELLED"


class InvoiceStatus(StrEnum):
    DRAFT = "DRAFT"
    PAID = "PAID"
    FAILED = "FAILED"
    VOID = "VOID"


class WalletEntryType(StrEnum):
    TOPUP = "TOPUP"
    AD_SPEND = "AD_SPEND"
    REFUND = "REFUND"
    ADJUSTMENT = "ADJUSTMENT"


class TemplateCategory(StrEnum):
    MARKETING = "MARKETING"
    UTILITY = "UTILITY"
    AUTHENTICATION = "AUTHENTICATION"


class TemplateStatus(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

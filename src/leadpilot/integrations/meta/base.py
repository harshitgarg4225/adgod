"""Meta Marketing API adapter interface (PRD §10.1).

The Buyer/Optimizer depend only on this interface (the `ChannelAdapter` seam, §7.5),
so a future Google/TikTok channel slots in without core rewrites, and MOCK_META swaps
transport without touching agent code. Field names defer to live Meta docs; pin
META_GRAPH_API_VERSION at build start.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class InsightRow:
    level: str            # CAMPAIGN | ADSET | AD
    meta_id: str
    spend_paise: int
    impressions: int
    clicks: int
    ctr: float
    frequency: float
    leads: int
    raw: dict = field(default_factory=dict)


class MetaAdapter:
    # Video ads need an /advideos upload path; adapters that lack it advertise False and
    # the Buyer launches image/text ads only (instead of silently degrading video ads).
    supports_video: bool = True

    def create_campaign(
        self, *, ad_account_id: str, name: str, objective: str, status: str = "PAUSED"
    ) -> str:
        raise NotImplementedError

    def find_campaign_by_name(self, *, ad_account_id: str, name: str) -> str | None:
        """Existing campaign id with this exact name, or None. Makes launch idempotent
        against Meta itself: a crash after create but before the local row commit must
        not stack a duplicate campaign (duplicate spend) on retry."""
        raise NotImplementedError

    def list_adsets(self, *, meta_campaign_id: str) -> list[dict]:
        """[{'id', 'name'}] for the campaign — the resume path skips already-created
        ad sets by name."""
        raise NotImplementedError

    def list_ads(self, *, meta_adset_id: str) -> list[dict]:
        """[{'id', 'name'}] for the ad set — the resume path skips already-created ads
        by name (retries must not stack duplicate ads)."""
        raise NotImplementedError

    def get_ad_statuses(self, *, meta_ids: list[str]) -> dict[str, str]:
        """meta_ad_id → effective_status (ACTIVE / DISAPPROVED / WITH_ISSUES / ...).
        Meta review rejections are silent otherwise — the optimizer sweeps this so a
        rejected ad surfaces as an alert instead of a mystery zero-spend day."""
        raise NotImplementedError

    def create_adset(
        self, *, ad_account_id: str, campaign_id: str, name: str, targeting: dict,
        daily_budget_paise: int, optimization_goal: str, promoted_object: dict,
        destination_type: str | None = None, status: str = "PAUSED",
    ) -> str:
        raise NotImplementedError

    def create_creative(
        self, *, ad_account_id: str, page_id: str, message: str, headline: str,
        link_or_cta: dict, image_url: str | None = None,
    ) -> str:
        raise NotImplementedError

    def create_ad(
        self, *, ad_account_id: str, adset_id: str, creative_meta_id: str, name: str,
        status: str = "PAUSED",
    ) -> str:
        raise NotImplementedError

    def set_status(self, *, level: str, meta_id: str, status: str) -> None:
        raise NotImplementedError

    def set_adset_budget(self, *, meta_adset_id: str, daily_budget_paise: int) -> None:
        raise NotImplementedError

    def get_insights(self, *, level: str, meta_ids: list[str]) -> list[InsightRow]:
        """Today's (ad-account timezone) performance per meta id. Implementations MUST
        window to today — the optimizer treats spend as day-spend for the emergency cap."""
        raise NotImplementedError

    def get_form_leads(self, *, page_id: str, since_iso: str | None = None) -> list[dict]:
        """Instant-Form leads across the page's lead forms:
        [{'leadgen_id','created_time','field_data':[{'name','values'}]}]. Polling this with
        an owned-asset System User token needs NO app review — it is the review-free
        automatic lead path."""
        raise NotImplementedError

    def get_lead_details(self, *, leadgen_id: str) -> dict:
        """One lead's field_data (the leadgen webhook payload does not carry it)."""
        raise NotImplementedError

    def search_ad_library(self, *, query: str, country: str = "IN", limit: int = 10) -> list[dict]:
        raise NotImplementedError

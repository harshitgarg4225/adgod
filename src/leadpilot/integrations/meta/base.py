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
    def create_campaign(
        self, *, ad_account_id: str, name: str, objective: str, status: str = "PAUSED"
    ) -> str:
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
        raise NotImplementedError

    def search_ad_library(self, *, query: str, country: str = "IN", limit: int = 10) -> list[dict]:
        raise NotImplementedError

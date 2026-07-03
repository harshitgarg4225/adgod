"""Mock Meta transport — deterministic ids + synthetic insights.

Used when MOCK_META=true. Insights are derived deterministically from the meta id
(and the embedded ad-set role) so the Optimizer has realistic, varied data to act on
without any live Meta account: TESTING ad sets run hot (pause candidates), PROSPECTING
runs efficient (scale candidates).
"""
from __future__ import annotations

import hashlib
import itertools

from leadpilot.common.logging import get_logger
from leadpilot.integrations.meta.base import InsightRow, MetaAdapter

log = get_logger("meta.mock")
_counter = itertools.count(1)

# Process-local registry of created objects (for inspection in tests).
CREATED: dict[str, dict] = {}


def _seed(s: str) -> int:
    return int(hashlib.sha256(s.encode()).hexdigest()[:8], 16)


class MockMetaAdapter(MetaAdapter):
    def _new_id(self, kind: str, tag: str = "", name: str = "", parent: str = "") -> str:
        n = next(_counter)
        mid = f"{kind}_{tag}{n}" if tag else f"{kind}_{n}"
        CREATED[mid] = {"kind": kind, "status": "PAUSED", "name": name, "parent": parent}
        return mid

    def create_campaign(self, *, ad_account_id, name, objective, status="PAUSED") -> str:
        return self._new_id("camp", name=name)

    def find_campaign_by_name(self, *, ad_account_id, name) -> str | None:
        for mid, meta in CREATED.items():
            if meta.get("kind") == "camp" and meta.get("name") == name:
                return mid
        return None

    def list_adsets(self, *, meta_campaign_id) -> list[dict]:
        return [{"id": mid, "name": meta.get("name", "")}
                for mid, meta in CREATED.items()
                if meta.get("kind") == "adset" and meta.get("parent") == meta_campaign_id]

    def create_adset(
        self, *, ad_account_id, campaign_id, name, targeting, daily_budget_paise,
        optimization_goal, promoted_object, destination_type=None, status="PAUSED",
    ) -> str:
        role = (targeting or {}).get("_role", "PROSPECTING")
        return self._new_id("adset", tag=f"{role}_", name=name, parent=campaign_id)

    def create_creative(
        self, *, ad_account_id, page_id, message, headline, link_or_cta, image_url=None
    ) -> str:
        return self._new_id("crea")

    def create_ad(self, *, ad_account_id, adset_id, creative_meta_id, name, status="PAUSED") -> str:
        return self._new_id("ad", name=name, parent=adset_id)

    def set_status(self, *, level, meta_id, status) -> None:
        CREATED.setdefault(meta_id, {})["status"] = status
        log.info("meta_set_status", level=level, meta_id=meta_id, status=status)

    def set_adset_budget(self, *, meta_adset_id, daily_budget_paise) -> None:
        CREATED.setdefault(meta_adset_id, {})["budget"] = daily_budget_paise

    def get_insights(self, *, level, meta_ids) -> list[InsightRow]:
        rows: list[InsightRow] = []
        for mid in meta_ids:
            s = _seed(mid)
            hot = "TESTING" in mid  # testing ad sets perform worse (pause candidates)
            impressions = 2000 + s % 8000
            ctr = (0.6 + (s % 30) / 10.0) / 100  # 0.6%–3.6%
            clicks = max(1, int(impressions * ctr))
            # Cost-per-click in paise: hot ad sets cost more.
            cpc = (1500 + s % 2500) * (2 if hot else 1)
            spend = clicks * cpc
            leads = max(0, int(clicks * (0.05 if hot else 0.18)))
            frequency = 1.2 + (s % 40) / 10.0  # up to ~5.0 → fatigue territory
            rows.append(InsightRow(
                level=level, meta_id=mid, spend_paise=spend, impressions=impressions,
                clicks=clicks, ctr=round(ctr, 4), frequency=round(frequency, 2), leads=leads,
            ))
        return rows

    def list_ads(self, *, meta_adset_id) -> list[dict]:
        return [{"id": mid, "name": meta.get("name", "")}
                for mid, meta in CREATED.items()
                if meta.get("kind") == "ad" and meta.get("parent") == meta_adset_id]

    def get_ad_statuses(self, *, meta_ids) -> dict[str, str]:
        return {mid: "ACTIVE" for mid in meta_ids}

    def get_form_leads(self, *, page_id, since_iso=None) -> list[dict]:
        return []  # mock has no Instant Forms; the polling task no-ops cleanly

    def search_ad_library(self, *, query, country="IN", limit=10) -> list[dict]:
        return [
            {"page_name": f"Competitor {i+1}", "ad_creative_body":
             f"Best {query} in town — enquire on WhatsApp", "country": country}
            for i in range(min(limit, 3))
        ]

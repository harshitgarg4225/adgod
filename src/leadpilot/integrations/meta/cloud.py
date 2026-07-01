"""Real Meta Marketing API transport (Graph API). Used when MOCK_META=false.

Field names defer to live Meta docs (Meta deprecates ~quarterly); pin
META_GRAPH_API_VERSION. This is the executor surface the Buyer/Optimizer call through
the outbox. Auth uses the connected Business's System User token.
"""
from __future__ import annotations

import httpx

from leadpilot.common.config import settings
from leadpilot.common.http_retry import request_with_retry
from leadpilot.integrations.meta.base import InsightRow, MetaAdapter

_GRAPH = "https://graph.facebook.com"


class CloudMetaAdapter(MetaAdapter):  # pragma: no cover - requires live Meta creds
    def __init__(self, system_user_token: str | None = None) -> None:
        self._token = system_user_token or settings.meta_app_secret
        self._v = settings.meta_graph_api_version
        self._client = httpx.Client(timeout=20.0)

    @property
    def _auth_headers(self) -> dict:
        # Bearer header keeps the token out of URLs / upstream access logs (vs ?access_token=).
        return {"Authorization": f"Bearer {self._token}"}

    def _post(self, path: str, data: dict) -> dict:
        url = f"{_GRAPH}/{self._v}/{path}"
        resp = request_with_retry(
            lambda: self._client.post(url, data=data, headers=self._auth_headers)
        )
        resp.raise_for_status()
        return resp.json()

    def _get(self, path: str, params: dict) -> dict:
        url = f"{_GRAPH}/{self._v}/{path}"
        resp = request_with_retry(
            lambda: self._client.get(url, params=params, headers=self._auth_headers)
        )
        resp.raise_for_status()
        return resp.json()

    def create_campaign(self, *, ad_account_id, name, objective, status="PAUSED") -> str:
        return self._post(f"act_{ad_account_id}/campaigns", {
            "name": name, "objective": objective, "status": status,
            "special_ad_categories": "[]",
        })["id"]

    def create_adset(
        self, *, ad_account_id, campaign_id, name, targeting, daily_budget_paise,
        optimization_goal, promoted_object, destination_type=None, status="PAUSED",
    ) -> str:
        import json

        payload = {
            "name": name, "campaign_id": campaign_id,
            "daily_budget": daily_budget_paise,  # Meta expects minor units
            "billing_event": "IMPRESSIONS", "optimization_goal": optimization_goal,
            "targeting": json.dumps(targeting), "promoted_object": json.dumps(promoted_object),
            "status": status,
        }
        if destination_type:
            payload["destination_type"] = destination_type
        return self._post(f"act_{ad_account_id}/adsets", payload)["id"]

    def create_creative(
        self, *, ad_account_id, page_id, message, headline, link_or_cta, image_url=None
    ) -> str:
        import json

        object_story_spec = {
            "page_id": page_id,
            "link_data": {"message": message, "name": headline, **link_or_cta},
        }
        return self._post(f"act_{ad_account_id}/adcreatives", {
            "name": headline[:60] or "creative",
            "object_story_spec": json.dumps(object_story_spec),
        })["id"]

    def create_ad(self, *, ad_account_id, adset_id, creative_meta_id, name, status="PAUSED") -> str:
        import json

        return self._post(f"act_{ad_account_id}/ads", {
            "name": name, "adset_id": adset_id,
            "creative": json.dumps({"creative_id": creative_meta_id}), "status": status,
        })["id"]

    def set_status(self, *, level, meta_id, status) -> None:
        self._post(meta_id, {"status": status})

    def set_adset_budget(self, *, meta_adset_id, daily_budget_paise) -> None:
        self._post(meta_adset_id, {"daily_budget": daily_budget_paise})

    def get_insights(self, *, level, meta_ids) -> list[InsightRow]:
        rows: list[InsightRow] = []
        for mid in meta_ids:
            data = self._get(f"{mid}/insights", {
                "fields": "spend,impressions,clicks,ctr,frequency,actions",
            }).get("data", [])
            if not data:
                continue
            d = data[0]
            spend_paise = int(float(d.get("spend", 0)) * 100)
            leads = 0
            for a in d.get("actions", []):
                if "lead" in a.get("action_type", ""):
                    leads += int(float(a.get("value", 0)))
            rows.append(InsightRow(
                level=level, meta_id=mid, spend_paise=spend_paise,
                impressions=int(d.get("impressions", 0)), clicks=int(d.get("clicks", 0)),
                ctr=float(d.get("ctr", 0)) / 100, frequency=float(d.get("frequency", 0)),
                leads=leads, raw=d,
            ))
        return rows

    def search_ad_library(self, *, query, country="IN", limit=10) -> list[dict]:
        return self._get("ads_archive", {
            "search_terms": query, "ad_reached_countries": f"['{country}']",
            "ad_type": "ALL", "limit": limit, "fields": "ad_creative_bodies,page_name",
        }).get("data", [])

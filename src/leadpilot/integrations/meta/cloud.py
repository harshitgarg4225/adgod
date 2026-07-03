"""Real Meta Marketing API transport (Graph API). Used when MOCK_META=false.

Field names defer to live Meta docs (Meta deprecates ~quarterly); pin
META_GRAPH_API_VERSION. Auth uses the connected Business's System User token — the
factory decrypts the per-account token (or the shared founder token) and passes it in;
there is deliberately no app-secret fallback (an app secret is not an access token).
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx

from leadpilot.common.config import settings
from leadpilot.common.http_retry import request_with_retry
from leadpilot.integrations.meta.base import InsightRow, MetaAdapter

_GRAPH = "https://graph.facebook.com"
# CTWA conversions surface as messaging-conversation actions, never as "lead" actions;
# both families count as a lead for optimization (form leads + WhatsApp conversations).
_LEAD_ACTION_PREFIXES = (
    "lead",
    "onsite_conversion.lead",
    "onsite_conversion.messaging_conversation_started",
    "onsite_conversion.total_messaging_connection",
)


class CloudMetaAdapter(MetaAdapter):  # pragma: no cover - requires live Meta creds
    # No /advideos upload implemented yet — the Buyer must launch image/text ads only.
    supports_video = False

    def __init__(self, system_user_token: str) -> None:
        if not system_user_token:
            raise RuntimeError("CloudMetaAdapter requires a System User access token")
        self._token = system_user_token
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
        self._raise_with_detail(resp)
        return resp.json()

    def _get(self, path: str, params: dict) -> dict:
        url = f"{_GRAPH}/{self._v}/{path}"
        resp = request_with_retry(
            lambda: self._client.get(url, params=params, headers=self._auth_headers)
        )
        self._raise_with_detail(resp)
        return resp.json()

    def _get_paged(self, path: str, params: dict, *, max_pages: int = 10) -> list[dict]:
        """Follow Graph cursor paging; callers get the full data list."""
        out: list[dict] = []
        url = f"{_GRAPH}/{self._v}/{path}"
        for _ in range(max_pages):
            resp = request_with_retry(
                lambda u=url, p=params: self._client.get(u, params=p, headers=self._auth_headers)
            )
            self._raise_with_detail(resp)
            body = resp.json()
            out.extend(body.get("data", []))
            nxt = body.get("paging", {}).get("next")
            if not nxt:
                break
            url, params = nxt, {}  # `next` is a fully-qualified URL with the cursor baked in
        return out

    @staticmethod
    def _raise_with_detail(resp: httpx.Response) -> None:
        """Surface Graph's error message (code/subcode/user_msg) — a bare 400 is
        undebuggable at 11pm before a client launch."""
        if resp.status_code < 400:
            return
        try:
            err = resp.json().get("error", {})
            detail = (f"Graph {resp.status_code}: {err.get('message')} "
                      f"(code={err.get('code')}, subcode={err.get('error_subcode')}, "
                      f"user_msg={err.get('error_user_msg')})")
        except Exception:  # noqa: BLE001 - non-JSON error body
            detail = f"Graph {resp.status_code}: {resp.text[:300]}"
        raise httpx.HTTPStatusError(detail, request=resp.request, response=resp)

    # ── campaign / adset / creative / ad ──────────────────────────────────────

    def create_campaign(self, *, ad_account_id, name, objective, status="PAUSED") -> str:
        return self._post(f"act_{ad_account_id}/campaigns", {
            "name": name, "objective": objective, "status": status,
            "special_ad_categories": "[]",
        })["id"]

    def find_campaign_by_name(self, *, ad_account_id, name) -> str | None:
        import json

        rows = self._get_paged(f"act_{ad_account_id}/campaigns", {
            "fields": "id,name", "limit": 100,
            "filtering": json.dumps([{"field": "name", "operator": "EQUAL", "value": name}]),
        })
        return rows[0]["id"] if rows else None

    def list_adsets(self, *, meta_campaign_id) -> list[dict]:
        return self._get_paged(f"{meta_campaign_id}/adsets", {"fields": "id,name", "limit": 100})

    def list_ads(self, *, meta_adset_id) -> list[dict]:
        return self._get_paged(f"{meta_adset_id}/ads", {"fields": "id,name", "limit": 100})

    def get_ad_statuses(self, *, meta_ids) -> dict[str, str]:
        out: dict[str, str] = {}
        # Batch fetch via ?ids= (50 per call is Graph's comfortable limit).
        for i in range(0, len(meta_ids), 50):
            chunk = meta_ids[i:i + 50]
            body = self._get("", {"ids": ",".join(chunk), "fields": "effective_status"})
            for mid, obj in body.items():
                if isinstance(obj, dict) and obj.get("effective_status"):
                    out[mid] = obj["effective_status"]
        return out

    def create_adset(
        self, *, ad_account_id, campaign_id, name, targeting, daily_budget_paise,
        optimization_goal, promoted_object, destination_type=None, status="PAUSED",
    ) -> str:
        import json

        targeting = {k: v for k, v in targeting.items() if not k.startswith("_")}
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

    def _upload_image(self, *, ad_account_id: str, image_url: str) -> str | None:
        """Fetch the generated asset and upload to act/adimages → image_hash. Returns None
        (text-only ad) on any failure rather than failing the whole launch."""
        try:
            img = self._client.get(image_url, timeout=30.0)
            img.raise_for_status()
            resp = self._post_files(
                f"act_{ad_account_id}/adimages",
                files={"source": ("creative.png", img.content, "image/png")},
            )
            images = resp.get("images", {})
            first = next(iter(images.values()), {})
            return first.get("hash")
        except Exception:  # noqa: BLE001 - degrade to text ad, never abort launch
            return None

    def _post_files(self, path: str, *, files: dict) -> dict:
        url = f"{_GRAPH}/{self._v}/{path}"
        resp = request_with_retry(
            lambda: self._client.post(url, files=files, headers=self._auth_headers)
        )
        self._raise_with_detail(resp)
        return resp.json()

    def create_creative(
        self, *, ad_account_id, page_id, message, headline, link_or_cta, image_url=None
    ) -> str:
        import json

        # link_data REQUIRES a link. The pipeline passes the CTWA wa.me deep link (or a
        # page fallback) in link_or_cta; keep a hard fallback so a creative can never be
        # submitted linkless (Graph rejects it).
        link_data = {"message": message, "name": headline, **link_or_cta}
        link_data.setdefault("link", f"https://facebook.com/{page_id}")
        if image_url:
            image_hash = self._upload_image(ad_account_id=ad_account_id, image_url=image_url)
            if image_hash:
                link_data["image_hash"] = image_hash
        object_story_spec = {"page_id": page_id, "link_data": link_data}
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

    # ── insights / leads ───────────────────────────────────────────────────────

    def get_insights(self, *, level, meta_ids) -> list[InsightRow]:
        rows: list[InsightRow] = []
        for mid in meta_ids:
            # date_preset=today uses the AD ACCOUNT's timezone (IST for Indian accounts) —
            # without it Graph returns a multi-week window and the optimizer would read
            # cumulative spend as day-spend, tripping the emergency pause on day 2.
            data = self._get(f"{mid}/insights", {
                "fields": "spend,impressions,clicks,ctr,frequency,actions",
                "date_preset": "today",
            }).get("data", [])
            if not data:
                continue
            d = data[0]
            spend_paise = int(round(float(d.get("spend", 0)) * 100))
            leads = 0
            for a in d.get("actions", []):
                if str(a.get("action_type", "")).startswith(_LEAD_ACTION_PREFIXES):
                    leads += int(float(a.get("value", 0)))
            rows.append(InsightRow(
                level=level, meta_id=mid, spend_paise=spend_paise,
                impressions=int(d.get("impressions", 0)), clicks=int(d.get("clicks", 0)),
                ctr=float(d.get("ctr", 0)) / 100, frequency=float(d.get("frequency", 0)),
                leads=leads, raw=d,
            ))
        return rows

    def get_form_leads(self, *, page_id, since_iso=None) -> list[dict]:
        """Poll Instant-Form leads: page's forms → each form's leads. Owned-asset token,
        no webhook subscription, no app review."""
        since_iso = since_iso or (datetime.now(UTC) - timedelta(days=7)).isoformat()
        leads: list[dict] = []
        forms = self._get_paged(f"{page_id}/leadgen_forms", {"fields": "id,name", "limit": 50})
        for form in forms:
            rows = self._get_paged(f"{form['id']}/leads", {
                "fields": "id,created_time,field_data",
                "filtering": ('[{"field":"time_created","operator":"GREATER_THAN",'
                              f'"value":{int(datetime.fromisoformat(since_iso).timestamp())}}}]'),
                "limit": 100,
            })
            for r in rows:
                leads.append({
                    "leadgen_id": r.get("id"), "form_id": form["id"],
                    "created_time": r.get("created_time"),
                    "field_data": r.get("field_data", []),
                })
        return leads

    def get_lead_details(self, *, leadgen_id: str) -> dict:
        """Fetch one lead's field_data (the leadgen webhook payload does NOT carry it)."""
        return self._get(leadgen_id, {"fields": "id,created_time,field_data"})

    def search_ad_library(self, *, query, country="IN", limit=10) -> list[dict]:
        return self._get("ads_archive", {
            "search_terms": query, "ad_reached_countries": f"['{country}']",
            "ad_type": "ALL", "limit": limit, "fields": "ad_creative_bodies,page_name",
        }).get("data", [])

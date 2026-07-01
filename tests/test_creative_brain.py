"""Creative brain parity: UGC video variants alongside images, and website scraping that
feeds the Scout research."""
from __future__ import annotations

from sqlalchemy import select

from leadpilot.core.db import tenant_session
from leadpilot.core.models import Creative
from leadpilot.integrations.scrape import scrape_site
from leadpilot.saathi import pipeline
from leadpilot.saathi.providers.creative import get_creative_provider
from leadpilot.scripts.demo_constants import DEMO_ACCOUNT_ID, DEMO_TENANT_ID


def test_creative_provider_generates_video():
    url = get_creative_provider().generate_video(script="Namaste, join our NEET batch!")
    assert url and url.endswith(".mp4")


def test_pipeline_generates_both_image_and_video(seeded):
    with tenant_session(DEMO_TENANT_ID) as s:
        pipeline.run_research(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)
    with tenant_session(DEMO_TENANT_ID) as s:
        pipeline.run_creative(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)
    with tenant_session(DEMO_TENANT_ID) as s:
        formats = {
            c.format for c in s.scalars(
                select(Creative).where(Creative.account_id == DEMO_ACCOUNT_ID)
            ).all()
        }
    assert "IMAGE_VERTICAL" in formats
    assert "VIDEO_9_16" in formats  # UGC video variant produced per angle


def test_scrape_site_is_mock_safe():
    # In mock mode (no outbound), scraping returns "" so research still proceeds.
    assert scrape_site("https://example.com") == ""
    assert scrape_site(None) == ""

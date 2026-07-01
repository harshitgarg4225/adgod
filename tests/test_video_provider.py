"""Real fal.ai (Kling) video adapter — drives the full queue flow with a mocked transport
so the submit → poll → fetch → download path is actually covered without a live key."""
from __future__ import annotations

import httpx

from leadpilot.saathi.providers.creative import (
    MockCreativeProvider,
    fal_generate_video_bytes,
)

MODEL = "fal-ai/kling-video/v1/standard/text-to-video"


def _transport(status_sequence):
    """A MockTransport that emulates fal's queue: submit, then a scripted status sequence,
    then the result + the video download."""
    calls = {"status": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if request.method == "POST" and url.endswith(MODEL):
            return httpx.Response(200, json={
                "request_id": "req-1",
                "status_url": "https://queue.fal.run/req-1/status",
                "response_url": "https://queue.fal.run/req-1",
            })
        if url.endswith("/status"):
            i = min(calls["status"], len(status_sequence) - 1)
            calls["status"] += 1
            return httpx.Response(200, json={"status": status_sequence[i]})
        if url.endswith("/req-1"):
            return httpx.Response(200, json={"video": {"url": "https://cdn.fal.run/out.mp4"}})
        if url.endswith("out.mp4"):
            return httpx.Response(200, content=b"REAL_MP4_BYTES")
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def test_fal_video_flow_completes():
    client = httpx.Client(transport=_transport(["IN_PROGRESS", "IN_PROGRESS", "COMPLETED"]))
    data = fal_generate_video_bytes(
        "Join our NEET batch!", ratio="9:16", api_key="k", model=MODEL,
        client=client, poll_interval_s=0, sleep=lambda _s: None)
    assert data == b"REAL_MP4_BYTES"


def test_fal_video_flow_raises_on_failure():
    client = httpx.Client(transport=_transport(["FAILED"]))
    try:
        fal_generate_video_bytes("x", ratio="9:16", api_key="k", model=MODEL,
                                 client=client, sleep=lambda _s: None)
        raised = False
    except RuntimeError:
        raised = True
    assert raised


def test_fal_video_times_out():
    client = httpx.Client(transport=_transport(["IN_PROGRESS"]))
    try:
        fal_generate_video_bytes("x", ratio="9:16", api_key="k", model=MODEL, client=client,
                                 poll_timeout_s=0, poll_interval_s=0, sleep=lambda _s: None)
        raised = False
    except TimeoutError:
        raised = True
    assert raised


def test_mock_provider_still_default():
    # With no keys / mock mode, the mock provider returns a stored placeholder mp4.
    url = MockCreativeProvider().generate_video(script="hi")
    assert url.endswith(".mp4")

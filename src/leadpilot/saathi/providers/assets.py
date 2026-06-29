"""AssetStore abstraction (R2/S3) — creatives + invoice PDFs.

v1 uses a local/no-op store unless R2 is configured. Presigned URLs keep the
swap to a Mumbai (ap-south-1) bucket a config change for data residency.
"""
from __future__ import annotations

from leadpilot.common.config import settings


class AssetStore:
    def put_bytes(self, key: str, data: bytes, content_type: str) -> str:
        raise NotImplementedError

    def presigned_get(self, key: str, expires_s: int = 3600) -> str:
        raise NotImplementedError


class LocalAssetStore(AssetStore):
    """No external dependency. Returns a deterministic local URL placeholder."""

    def put_bytes(self, key: str, data: bytes, content_type: str) -> str:
        return f"{settings.app_base_url}/assets/{key}"

    def presigned_get(self, key: str, expires_s: int = 3600) -> str:
        return f"{settings.app_base_url}/assets/{key}"


class R2AssetStore(AssetStore):  # pragma: no cover - requires R2 creds
    def __init__(self) -> None:
        import boto3

        self._bucket = settings.r2_bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.r2_endpoint,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            region_name=settings.r2_region,
        )

    def put_bytes(self, key: str, data: bytes, content_type: str) -> str:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)
        return self.presigned_get(key)

    def presigned_get(self, key: str, expires_s: int = 3600) -> str:
        return self._client.generate_presigned_url(
            "get_object", Params={"Bucket": self._bucket, "Key": key}, ExpiresIn=expires_s
        )


_store: AssetStore | None = None


def get_asset_store() -> AssetStore:
    global _store
    if _store is None:
        _store = R2AssetStore() if settings.r2_endpoint else LocalAssetStore()
    return _store

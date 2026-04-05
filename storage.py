from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional

import oss2

from config import Settings

logger = logging.getLogger(__name__)


def _object_key(response_id: str, now: Optional[datetime] = None) -> str:
    dt = now or datetime.now(timezone.utc)
    ymd = dt.strftime("%Y%m%d")
    return f"reports/{ymd}/{response_id}.pdf"


def upload_pdf_with_signed_url(
    pdf_bytes: bytes,
    response_id: str,
    settings: Settings,
    *,
    max_attempts: int = 4,
    backoff_seconds: tuple[int, ...] = (5, 10, 20),
) -> str:
    if not settings.OSS_ACCESS_KEY_ID or not settings.OSS_ACCESS_KEY_SECRET:
        raise ValueError("OSS credentials not configured")

    auth = oss2.Auth(settings.OSS_ACCESS_KEY_ID, settings.OSS_ACCESS_KEY_SECRET)
    bucket = oss2.Bucket(auth, settings.OSS_ENDPOINT, settings.OSS_BUCKET_NAME)
    key = _object_key(response_id)

    last_exc: Optional[Exception] = None
    for attempt in range(max_attempts):
        try:
            bucket.put_object(key, pdf_bytes)
            url = bucket.sign_url("GET", key, settings.OSS_URL_EXPIRY_SECONDS)
            return url
        except Exception as e:
            last_exc = e
            if attempt < max_attempts - 1:
                wait = backoff_seconds[attempt] if attempt < len(backoff_seconds) else backoff_seconds[-1]
                logger.warning(
                    "storage: OSS upload failed attempt %s/%s, retrying in %ss: %s",
                    attempt + 1,
                    max_attempts,
                    wait,
                    type(e).__name__,
                    extra={"response_id": response_id},
                )
                time.sleep(wait)

    assert last_exc is not None
    raise last_exc

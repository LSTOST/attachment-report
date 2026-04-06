from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import oss2
from oss2.exceptions import NoSuchKey

from config import Settings
from report_builder import ReportData

logger = logging.getLogger(__name__)

_RESPONSE_ID_SAFE = re.compile(r"^[0-9A-Za-z_.-]+$")


def _object_key(response_id: str, now: Optional[datetime] = None) -> str:
    dt = now or datetime.now(timezone.utc)
    ymd = dt.strftime("%Y%m%d")
    return f"reports/{ymd}/{response_id}.pdf"


def _json_object_key(response_id: str, now: Optional[datetime] = None) -> str:
    dt = now or datetime.now(timezone.utc)
    ymd = dt.strftime("%Y%m%d")
    return f"reports/{ymd}/{response_id}.json"


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


def upload_report_json(
    report_data: ReportData,
    response_id: str,
    settings: Settings,
    *,
    max_attempts: int = 4,
    backoff_seconds: tuple[int, ...] = (5, 10, 20),
) -> None:
    if not settings.OSS_ACCESS_KEY_ID or not settings.OSS_ACCESS_KEY_SECRET:
        raise ValueError("OSS credentials not configured")

    auth = oss2.Auth(settings.OSS_ACCESS_KEY_ID, settings.OSS_ACCESS_KEY_SECRET)
    bucket = oss2.Bucket(auth, settings.OSS_ENDPOINT, settings.OSS_BUCKET_NAME)
    key = _json_object_key(response_id)
    body = json.dumps(asdict(report_data), ensure_ascii=False).encode("utf-8")

    last_exc: Optional[Exception] = None
    for attempt in range(max_attempts):
        try:
            bucket.put_object(key, body)
            return
        except Exception as e:
            last_exc = e
            if attempt < max_attempts - 1:
                wait = backoff_seconds[attempt] if attempt < len(backoff_seconds) else backoff_seconds[-1]
                logger.warning(
                    "storage: OSS JSON upload failed attempt %s/%s, retrying in %ss: %s",
                    attempt + 1,
                    max_attempts,
                    wait,
                    type(e).__name__,
                    extra={"response_id": response_id},
                )
                time.sleep(wait)

    assert last_exc is not None
    raise last_exc


def get_report_json(response_id: str, settings: Settings) -> dict[str, Any]:
    """从 OSS 读取已上传的报告 JSON（路径规则与 upload_report_json 一致）。"""
    if not _RESPONSE_ID_SAFE.fullmatch(response_id):
        raise ValueError("invalid response_id")
    if not settings.OSS_ACCESS_KEY_ID or not settings.OSS_ACCESS_KEY_SECRET:
        raise ValueError("OSS credentials not configured")

    auth = oss2.Auth(settings.OSS_ACCESS_KEY_ID, settings.OSS_ACCESS_KEY_SECRET)
    bucket = oss2.Bucket(auth, settings.OSS_ENDPOINT, settings.OSS_BUCKET_NAME)
    suffix = f"/{response_id}.json"

    now = datetime.now(timezone.utc)
    for i in range(400):
        dt = now - timedelta(days=i)
        ymd = dt.strftime("%Y%m%d")
        key = f"reports/{ymd}/{response_id}.json"
        try:
            raw = bucket.get_object(key).read()
            return json.loads(raw.decode("utf-8"))
        except NoSuchKey:
            continue

    for obj in oss2.ObjectIterator(bucket, prefix="reports/"):
        if obj.key.endswith(suffix):
            raw = bucket.get_object(obj.key).read()
            return json.loads(raw.decode("utf-8"))

    raise FileNotFoundError(response_id)


def get_pdf_bytes(response_id: str, settings: Settings) -> bytes:
    """从 OSS 读取已上传的报告 PDF（按 upload 时的日期路径或前缀扫描）。"""
    if not _RESPONSE_ID_SAFE.fullmatch(response_id):
        raise ValueError("invalid response_id")
    if not settings.OSS_ACCESS_KEY_ID or not settings.OSS_ACCESS_KEY_SECRET:
        raise ValueError("OSS credentials not configured")

    auth = oss2.Auth(settings.OSS_ACCESS_KEY_ID, settings.OSS_ACCESS_KEY_SECRET)
    bucket = oss2.Bucket(auth, settings.OSS_ENDPOINT, settings.OSS_BUCKET_NAME)
    suffix = f"/{response_id}.pdf"

    now = datetime.now(timezone.utc)
    for i in range(400):
        dt = now - timedelta(days=i)
        ymd = dt.strftime("%Y%m%d")
        key = f"reports/{ymd}/{response_id}.pdf"
        try:
            return bucket.get_object(key).read()
        except NoSuchKey:
            continue

    for obj in oss2.ObjectIterator(bucket, prefix="reports/"):
        if obj.key.endswith(suffix):
            return bucket.get_object(obj.key).read()

    raise FileNotFoundError(response_id)

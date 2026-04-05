from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
from typing import Any, Dict, Optional

from fastapi import BackgroundTasks, FastAPI, Header, Request
from fastapi.responses import JSONResponse

from app_logging import setup_logging
from classifier import classify_from_quiz
from config import Settings, get_settings
from models import QuizParseError, TallyWebhookPayload, parse_quiz_from_payload
from notifier import send_report_notification
from pdf_generator import render_report_pdf
from report_builder import build_report
from storage import upload_pdf_with_signed_url

setup_logging()
logger = logging.getLogger(__name__)


def verify_tally_signature(body: bytes, signature_header: Optional[str], secret: str) -> bool:
    """Tally 文档：HMAC-SHA256(secret, body)，digest 为 base64；另兼容 `sha256=<hex>` 形式。"""
    if not secret or not signature_header:
        return False
    sig = signature_header.strip()
    mac = hmac.new(secret.encode("utf-8"), body, hashlib.sha256)
    expected_b64 = base64.b64encode(mac.digest()).decode("ascii")
    if hmac.compare_digest(sig, expected_b64):
        return True
    if sig.lower().startswith("sha256="):
        hex_part = sig.split("=", 1)[1].strip()
        return hmac.compare_digest(hex_part.lower(), mac.hexdigest().lower())
    return False


def run_pipeline(payload: TallyWebhookPayload, settings: Settings) -> None:
    response_id = payload.data.responseId
    extra = {"response_id": response_id}
    try:
        quiz = parse_quiz_from_payload(payload)
        type_code, ax, av = classify_from_quiz(quiz)
        logger.info(
            "classifier: type=%s anxiety=%s avoidance=%s",
            type_code,
            ax,
            av,
            extra=extra,
        )
        report = build_report(type_code, ax, av, quiz.nickname)
        pdf_bytes = render_report_pdf(report)
        url = upload_pdf_with_signed_url(pdf_bytes, response_id, settings)
        logger.info("storage: uploaded, signed download URL generated", extra=extra)
        expiry_days = max(1, settings.OSS_URL_EXPIRY_SECONDS // 86400)
        send_report_notification(
            contact=quiz.contact,
            contact_type=quiz.contact_type,
            nickname=quiz.nickname,
            download_url=url,
            expiry_days=expiry_days,
            settings=settings,
            response_id=response_id,
        )
    except Exception:
        logger.exception("pipeline failed", extra=extra)


app = FastAPI(title="Attachment Report API")


@app.get("/health")
def health() -> Dict[str, str]:
    s = get_settings()
    return {"status": "ok", "version": s.APP_VERSION}


@app.post("/webhook/tally", response_model=None)
async def tally_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    tally_signature: Optional[str] = Header(default=None, alias="Tally-Signature"),
) -> Any:
    settings = get_settings()
    body = await request.body()

    if not verify_tally_signature(body, tally_signature, settings.TALLY_WEBHOOK_SECRET):
        return JSONResponse(status_code=400, content={"error": "invalid_signature"})

    try:
        raw = json.loads(body.decode("utf-8"))
        payload = TallyWebhookPayload.model_validate(raw)
    except Exception:
        return JSONResponse(status_code=422, content={"error": "invalid_payload"})

    try:
        parse_quiz_from_payload(payload)
    except QuizParseError as e:
        return JSONResponse(
            status_code=422,
            content={"error": "missing_required_fields", "fields": e.fields},
        )

    background_tasks.add_task(run_pipeline, payload, settings)
    return {"status": "received", "responseId": payload.data.responseId}

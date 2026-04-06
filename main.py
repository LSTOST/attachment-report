from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
import uuid
import xml.etree.ElementTree as ET
from typing import Any, Dict, Optional
from urllib.parse import quote

from fastapi import BackgroundTasks, FastAPI, Header, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from app_logging import setup_logging
from classifier import classify_from_quiz
from config import Settings, get_settings
from models import (
    QuizAnswers,
    QuizH5SubmitBody,
    QuizParseError,
    TallyWebhookPayload,
    parse_quiz_from_payload,
)
from notifier import send_report_notification
from pdf_generator import render_report_pdf
from report_builder import build_report
from storage import get_pdf_bytes, upload_pdf_with_signed_url
from wechat_pusher import send_report_link

setup_logging()
logger = logging.getLogger(__name__)


def verify_wechat_server_url(
    signature: str, timestamp: str, nonce: str, *, token: str
) -> bool:
    """微信公众平台 URL 校验：token、timestamp、nonce 字典序拼接后 SHA1，与 signature 比较。"""
    if not token:
        return False
    raw = "".join(sorted((token, timestamp, nonce)))
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()
    sig = signature.strip().lower()
    if len(sig) != len(digest):
        return False
    return hmac.compare_digest(digest, sig)


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


def _run_report_core(
    quiz: QuizAnswers,
    response_id: str,
    settings: Settings,
    wechat_openid: str,
) -> None:
    extra = {"response_id": response_id}
    try:
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
        base = (settings.H5_BASE_URL or "").strip().rstrip("/")
        wechat_download_url = (
            f"{base}/download/{response_id}" if base else f"/download/{response_id}"
        )
        send_report_notification(
            contact=quiz.contact,
            contact_type=quiz.contact_type,
            nickname=quiz.nickname,
            download_url=url,
            expiry_days=expiry_days,
            settings=settings,
            response_id=response_id,
        )
        oid = (wechat_openid or "").strip()
        if oid:
            send_report_link(oid, wechat_download_url, quiz.nickname)
    except Exception:
        logger.exception("pipeline failed", extra=extra)


def run_pipeline(payload: TallyWebhookPayload, settings: Settings) -> None:
    response_id = payload.data.responseId
    extra = {"response_id": response_id}
    try:
        quiz = parse_quiz_from_payload(payload)
    except Exception:
        logger.exception("pipeline failed", extra=extra)
        return
    _run_report_core(quiz, response_id, settings, "")


def run_h5_pipeline(
    quiz: QuizAnswers,
    response_id: str,
    settings: Settings,
    openid: str,
) -> None:
    _run_report_core(quiz, response_id, settings, openid)


def _wx_xml_local_name(tag: str) -> str:
    if tag.startswith("{") and "}" in tag:
        return tag.partition("}")[2]
    return tag


def _wx_xml_find_text(root: ET.Element, local: str) -> str:
    for el in root.iter():
        if _wx_xml_local_name(el.tag) == local:
            return (el.text or "").strip()
    return ""


def _wx_attachment_test_url(settings: Settings) -> str:
    base = (settings.H5_BASE_URL or "").strip().rstrip("/")
    return f"{base}/attachment-test" if base else "/attachment-test"


def _wx_quiz_link_reply(settings: Settings) -> str:
    url = _wx_attachment_test_url(settings)
    return f"点击开始依恋类型测试：\n{url}"


def _wx_welcome_body(settings: Settings) -> str:
    return (
        "你好！我是知我实验室 👋\n\n"
        f"{_wx_quiz_link_reply(settings)}\n\n"
        "完成后报告将自动发送到此对话。"
    )


def _wx_default_guide_body(settings: Settings) -> str:
    """非关键词文本的默认引导（与欢迎语一致，便于用户再次查看入口）。"""
    return _wx_welcome_body(settings)


WECHAT_MENU_EVENT_KEY_ATTACHMENT_TEST = "ATTACHMENT_TEST"
WECHAT_REPLY_COMING_SOON = "功能开发中，敬请期待"
WECHAT_REPLY_REPORT_PENDING = "请完成测试后等待报告自动发送"


def _wx_reply_text_xml(to_user: str, from_user: str, content: str) -> str:
    ts = int(time.time())
    return (
        "<xml>"
        f"<ToUserName><![CDATA[{to_user}]]></ToUserName>"
        f"<FromUserName><![CDATA[{from_user}]]></FromUserName>"
        f"<CreateTime>{ts}</CreateTime>"
        "<MsgType><![CDATA[text]]></MsgType>"
        f"<Content><![CDATA[{content}]]></Content>"
        "</xml>"
    )


app = FastAPI(title="Attachment Report API")


@app.get("/health")
def health() -> Dict[str, str]:
    s = get_settings()
    return {"status": "ok", "version": s.APP_VERSION}


@app.get("/download/{response_id}", response_model=None)
def download_pdf(response_id: str) -> Any:
    """经 H5 域名代理从 OSS 拉取 PDF；微信内打开可触发下载（Content-Disposition: attachment）。"""
    settings = get_settings()
    try:
        pdf_bytes = get_pdf_bytes(response_id, settings)
    except ValueError:
        return Response(status_code=400)
    except FileNotFoundError:
        return Response(status_code=404)
    # Starlette 要求 header 为 latin-1；中文名用 RFC 5987 的 filename*（微信会采用并显示中文名）
    name_cn = "依恋类型报告.pdf"
    disp = (
        'attachment; filename="attachment-report.pdf"; '
        f"filename*=UTF-8''{quote(name_cn, safe='')}"
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": disp},
    )


@app.get(
    "/wechat/callback",
    response_class=PlainTextResponse,
    response_model=None,
)
def wechat_callback_verify(
    signature: Optional[str] = None,
    timestamp: Optional[str] = None,
    nonce: Optional[str] = None,
    echostr: Optional[str] = None,
) -> Any:
    """微信服务器验证：校验 signature 通过后原样返回 echostr（text/plain）。"""
    settings = get_settings()
    if (
        signature is None
        or timestamp is None
        or nonce is None
        or echostr is None
    ):
        return Response(status_code=403, content="", media_type="text/plain")
    if not verify_wechat_server_url(
        signature, timestamp, nonce, token=settings.WECHAT_TOKEN
    ):
        return Response(status_code=403, content="", media_type="text/plain")
    return PlainTextResponse(content=echostr)


@app.post(
    "/wechat/callback",
    response_model=None,
)
async def wechat_callback_message(
    request: Request,
    signature: Optional[str] = None,
    timestamp: Optional[str] = None,
    nonce: Optional[str] = None,
) -> Any:
    """接收公众号消息（XML）：关注欢迎、菜单 CLICK、关键词与默认文本回复；其它类型返回空。"""
    settings = get_settings()
    if signature is None or timestamp is None or nonce is None:
        return Response(status_code=403, content="", media_type="text/plain")
    if not verify_wechat_server_url(
        signature, timestamp, nonce, token=settings.WECHAT_TOKEN
    ):
        return Response(status_code=403, content="", media_type="text/plain")

    raw = await request.body()
    try:
        text = raw.decode("utf-8").strip()
    except UnicodeDecodeError:
        return Response(content="", status_code=200, media_type="text/plain")

    if not text:
        return Response(content="", status_code=200, media_type="text/plain")

    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        logger.warning("wechat callback: invalid XML body")
        return Response(content="", status_code=200, media_type="text/plain")

    from_user = _wx_xml_find_text(root, "FromUserName")
    to_user = _wx_xml_find_text(root, "ToUserName")
    msg_type = _wx_xml_find_text(root, "MsgType")
    event = _wx_xml_find_text(root, "Event")
    event_key = _wx_xml_find_text(root, "EventKey")

    welcome = _wx_welcome_body(settings)

    if msg_type == "event" and event.lower() == "subscribe":
        xml = _wx_reply_text_xml(from_user, to_user, welcome)
        return Response(
            content=xml,
            media_type="application/xml; charset=utf-8",
        )

    if msg_type == "event" and event.upper() == "CLICK":
        if event_key == WECHAT_MENU_EVENT_KEY_ATTACHMENT_TEST:
            body = _wx_quiz_link_reply(settings)
        else:
            body = WECHAT_REPLY_COMING_SOON
        xml = _wx_reply_text_xml(from_user, to_user, body)
        return Response(
            content=xml,
            media_type="application/xml; charset=utf-8",
        )

    if msg_type == "text":
        raw_content = _wx_xml_find_text(root, "Content")
        text = raw_content.strip()
        if text == "报告":
            reply_body = WECHAT_REPLY_REPORT_PENDING
        elif "依恋" in text or "测试" in text:
            reply_body = _wx_quiz_link_reply(settings)
        else:
            reply_body = _wx_default_guide_body(settings)
        xml = _wx_reply_text_xml(from_user, to_user, reply_body)
        return Response(
            content=xml,
            media_type="application/xml; charset=utf-8",
        )

    return Response(content="", status_code=200, media_type="text/plain")


@app.post("/quiz/submit", response_model=None)
async def quiz_submit(
    body: QuizH5SubmitBody,
    background_tasks: BackgroundTasks,
) -> Any:
    try:
        quiz = body.to_quiz_answers()
    except QuizParseError as e:
        return JSONResponse(
            status_code=422,
            content={"error": "missing_required_fields", "fields": e.fields},
        )
    settings = get_settings()
    response_id = str(uuid.uuid4())
    openid = (body.openid or "").strip()
    background_tasks.add_task(run_h5_pipeline, quiz, response_id, settings, openid)
    return {"status": "processing"}


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

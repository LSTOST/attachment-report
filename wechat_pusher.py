from __future__ import annotations

import logging
import threading
import time
from typing import Any, Optional, Tuple

import httpx

from config import Settings, get_settings

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_cached_token: Optional[str] = None
_token_deadline: float = 0.0

TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
CUSTOM_SEND_URL = "https://api.weixin.qq.com/cgi-bin/message/custom/send"
REFRESH_SKEW_SECONDS = 120


def _fetch_token_from_api(settings: Settings) -> Tuple[Optional[str], int]:
    if not settings.WECHAT_APPID or not settings.WECHAT_APPSECRET:
        logger.error(
            "wechat_pusher: WECHAT_APPID or WECHAT_APPSECRET is not configured"
        )
        return None, 0
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(
                TOKEN_URL,
                params={
                    "grant_type": "client_credential",
                    "appid": settings.WECHAT_APPID,
                    "secret": settings.WECHAT_APPSECRET,
                },
            )
            r.raise_for_status()
            data: dict[str, Any] = r.json()
    except Exception:
        logger.exception("wechat_pusher: failed to request access_token")
        return None, 0

    if data.get("errcode"):
        logger.error(
            "wechat_pusher: token API error errcode=%s errmsg=%s",
            data.get("errcode"),
            data.get("errmsg"),
        )
        return None, 0

    token = data.get("access_token")
    if not token or not isinstance(token, str):
        logger.error("wechat_pusher: access_token missing or invalid in response")
        return None, 0

    expires_in = int(data.get("expires_in") or 7200)
    expires_in = max(60, min(expires_in, 7200))
    return token, expires_in


def get_access_token(settings: Optional[Settings] = None) -> Optional[str]:
    """返回 access_token；内存缓存，按微信返回的 expires_in（最长按 2 小时）刷新。"""
    global _cached_token, _token_deadline
    s = settings or get_settings()
    now = time.time()
    with _lock:
        if (
            _cached_token
            and now < _token_deadline - REFRESH_SKEW_SECONDS
        ):
            return _cached_token

        token, ttl = _fetch_token_from_api(s)
        if not token:
            return None
        _cached_token = token
        _token_deadline = now + ttl
        return _cached_token


def send_report_link(openid: str, response_id: str, nickname: str) -> None:
    """客服消息：文本报告链接，地址为 {H5_BASE_URL}/report/{response_id}。失败仅打 ERROR 日志，不抛异常。"""
    try:
        settings = get_settings()
        token = get_access_token(settings)
        if not token:
            logger.error(
                "wechat_pusher: skip send_report_link (no access_token) openid=%s",
                openid[:8] + "…" if len(openid) > 8 else openid,
            )
            return

        base = (settings.H5_BASE_URL or "").strip().rstrip("/")
        download_url = (
            f"{base}/report/{response_id}"
            if base
            else f"/report/{response_id}"
        )
        prefix = f"{nickname}，" if nickname and nickname != "你" else ""
        content = (
            f"{prefix}你的依恋类型报告已生成 ✨\n\n"
            f"点击查看报告：\n{download_url}\n\n"
            "—— 知我实验室"
        )
        payload = {
            "touser": openid,
            "msgtype": "text",
            "text": {"content": content},
        }
        with httpx.Client(timeout=15.0) as client:
            r = client.post(
                f"{CUSTOM_SEND_URL}?access_token={token}",
                json=payload,
            )
            r.raise_for_status()
            data: dict[str, Any] = r.json()

        errcode = data.get("errcode", 0)
        if errcode not in (0, None):
            logger.error(
                "wechat_pusher: custom message failed errcode=%s errmsg=%s openid=%s",
                errcode,
                data.get("errmsg"),
                openid[:8] + "…" if len(openid) > 8 else openid,
            )
    except Exception:
        logger.exception(
            "wechat_pusher: send_report_link failed openid=%s",
            openid[:8] + "…" if len(openid) > 8 else openid,
        )

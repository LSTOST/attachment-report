from __future__ import annotations

import logging
import time
from typing import Optional

import resend

from config import Settings

logger = logging.getLogger(__name__)

_RESEND_FROM = "onboarding@resend.dev"


def _contact_log_suffix(contact: str) -> str:
    if "@" in contact:
        parts = contact.split("@", 1)
        return f"@{parts[1]}" if len(parts) == 2 else "@?"
    return "(wechat)"


def send_report_notification(
    *,
    contact: str,
    contact_type: str,
    nickname: str,
    download_url: str,
    expiry_days: int,
    settings: Settings,
    response_id: str,
    max_attempts: int = 3,
    backoff_seconds: tuple[int, ...] = (10, 30),
) -> None:
    if contact_type == "wechat":
        logger.info(
            "notifier: wechat contact — manual follow-up required (no auto send). nickname=%s contact_hint=%s",
            nickname,
            _contact_log_suffix(contact),
            extra={"response_id": response_id},
        )
        return

    if contact_type != "email":
        logger.warning(
            "notifier: unknown contact_type=%s, skipping email",
            contact_type,
            extra={"response_id": response_id},
        )
        return

    subject = "你的依恋类型报告已生成"
    body_html = f"""\
<html><body>
<p>{nickname}，你好。</p>
<p>你的依恋类型报告已生成，请点击下方链接下载（链接在约 {expiry_days} 天内有效）：</p>
<p><a href="{download_url}">下载报告 PDF</a></p>
<p>如链接失效，请通过原渠道联系知我实验室。</p>
<p>—— 知我实验室</p>
</body></html>"""

    last_exc: Optional[Exception] = None
    for attempt in range(max_attempts):
        try:
            resend.api_key = settings.RESEND_API_KEY
            resend.Emails.send(
                {
                    "from": _RESEND_FROM,
                    "to": [contact],
                    "subject": subject,
                    "html": body_html,
                }
            )

            logger.info(
                "notifier: email sent to %s",
                _contact_log_suffix(contact),
                extra={"response_id": response_id},
            )
            return
        except Exception as e:
            last_exc = e
            if attempt < max_attempts - 1:
                wait = backoff_seconds[attempt] if attempt < len(backoff_seconds) else backoff_seconds[-1]
                logger.error(
                    "notifier: resend failed attempt %s/%s, retrying in %ss: %s",
                    attempt + 1,
                    max_attempts,
                    wait,
                    type(e).__name__,
                    extra={"response_id": response_id},
                )
                time.sleep(wait)

    assert last_exc is not None
    raise last_exc

from __future__ import annotations

import logging
import smtplib
import ssl
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Callable, Optional

from config import Settings

logger = logging.getLogger(__name__)

_SMTP_TIMEOUT = 60
_SMTP_PORT_STARTTLS = 587
_SMTP_PORT_SSL = 465


def _build_message(
    *,
    subject: str,
    body_html: str,
    mail_from: str,
    mail_to: str,
) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = mail_to
    msg.attach(MIMEText(body_html, "html", "utf-8"))
    return msg


def _send_with_starttls(host: str, user: str, password: str, msg: MIMEMultipart) -> None:
    ctx = ssl.create_default_context()
    with smtplib.SMTP(host, _SMTP_PORT_STARTTLS, timeout=_SMTP_TIMEOUT) as server:
        server.ehlo()
        server.starttls(context=ctx)
        server.ehlo()
        server.login(user, password)
        server.sendmail(user, [msg["To"]], msg.as_string())


def _send_with_ssl(host: str, user: str, password: str, msg: MIMEMultipart) -> None:
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(
        host, _SMTP_PORT_SSL, timeout=_SMTP_TIMEOUT, context=ctx
    ) as server:
        server.login(user, password)
        server.sendmail(user, [msg["To"]], msg.as_string())


def _try_smtp_strategies(
    host: str,
    user: str,
    password: str,
    msg: MIMEMultipart,
    response_id: str,
) -> None:
    strategies: list[tuple[str, Callable[[], None]]] = [
        (f"{_SMTP_PORT_STARTTLS}/STARTTLS", lambda: _send_with_starttls(host, user, password, msg)),
        (f"{_SMTP_PORT_SSL}/SSL", lambda: _send_with_ssl(host, user, password, msg)),
    ]
    last_exc: Optional[Exception] = None
    for label, send in strategies:
        try:
            send()
            logger.debug(
                "notifier: smtp succeeded via %s",
                label,
                extra={"response_id": response_id},
            )
            return
        except Exception as e:
            last_exc = e
            logger.warning(
                "notifier: smtp via %s failed (%s): %s",
                label,
                type(e).__name__,
                e,
                extra={"response_id": response_id},
            )
    assert last_exc is not None
    raise last_exc


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
            msg = _build_message(
                subject=subject,
                body_html=body_html,
                mail_from=settings.SMTP_USER,
                mail_to=contact,
            )
            _try_smtp_strategies(
                settings.SMTP_HOST,
                settings.SMTP_USER,
                settings.SMTP_PASSWORD,
                msg,
                response_id,
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
                    "notifier: smtp failed attempt %s/%s, retrying in %ss: %s",
                    attempt + 1,
                    max_attempts,
                    wait,
                    type(e).__name__,
                    extra={"response_id": response_id},
                )
                time.sleep(wait)

    assert last_exc is not None
    raise last_exc

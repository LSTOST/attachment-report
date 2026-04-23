#!/usr/bin/env python3
"""创建微信公众号自定义菜单（读取项目根目录 .env 中的 WECHAT_APPID / WECHAT_APPSECRET）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
load_dotenv(_ROOT / ".env")

from config import get_settings  # noqa: E402

TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
MENU_CREATE_URL = "https://api.weixin.qq.com/cgi-bin/menu/create"


def _menu_body() -> dict:
    return {
        "button": [
            {
                "type": "view",
                "name": "契合度",
                "url": "https://hepaima.kyx123.com",
            },
            {
                "type": "view",
                "name": "依恋测试",
                "url": "https://hepaima.kyx123.com/attachment-test",
            },
            {
                "type": "view",
                "name": "MBTI测试",
                "url": "https://peibupei.kyx123.com/",
            },
        ],
    }


def main() -> int:
    settings = get_settings()
    appid = (settings.WECHAT_APPID or "").strip()
    secret = (settings.WECHAT_APPSECRET or "").strip()
    if not appid or not secret:
        print("错误：请在 .env 中配置 WECHAT_APPID 与 WECHAT_APPSECRET", file=sys.stderr)
        return 1

    with httpx.Client(timeout=30.0) as client:
        tr = client.get(
            TOKEN_URL,
            params={
                "grant_type": "client_credential",
                "appid": appid,
                "secret": secret,
            },
        )
        tr.raise_for_status()
        token_data = tr.json()

        if token_data.get("errcode"):
            print(json.dumps(token_data, ensure_ascii=False, indent=2))
            return 1

        access_token = token_data.get("access_token")
        if not access_token or not isinstance(access_token, str):
            print(json.dumps(token_data, ensure_ascii=False, indent=2))
            return 1

        mr = client.post(
            MENU_CREATE_URL,
            params={"access_token": access_token},
            json=_menu_body(),
        )
        mr.raise_for_status()
        try:
            out = mr.json()
            print(json.dumps(out, ensure_ascii=False, indent=2))
        except json.JSONDecodeError:
            print(mr.text)
            return 1

        errcode = out.get("errcode", 0)
        if errcode not in (0, None):
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

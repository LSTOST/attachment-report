import base64
import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient


def _sign_body(body: bytes, secret: str) -> str:
    mac = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    return base64.b64encode(mac).decode("ascii")


def _full_payload():
    fields = [
        {"key": "nickname", "label": "昵称", "value": "小月"},
        {"key": "contact", "label": "联系方式", "value": "user@example.com"},
    ]
    for i in range(1, 7):
        fields.append({"key": f"A{i}", "label": f"A{i}", "value": 4})
        fields.append({"key": f"B{i}", "label": f"B{i}", "value": 3})
    return {
        "eventId": "evt-1",
        "eventType": "FORM_RESPONSE",
        "createdAt": "2024-01-15T14:00:00Z",
        "data": {
            "responseId": "resp_abc123",
            "formId": "form_x",
            "fields": fields,
        },
    }


@pytest.fixture
def client(monkeypatch):
    secret = "unit-test-secret"
    monkeypatch.setenv("TALLY_WEBHOOK_SECRET", secret)
    import main as app_main

    monkeypatch.setattr(app_main, "run_pipeline", lambda *a, **k: None)
    return TestClient(app_main.app), secret


def test_health(client):
    c, _ = client
    r = c.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["version"]


def test_webhook_ok_with_valid_signature(client):
    c, secret = client
    payload = _full_payload()
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    sig = _sign_body(body, secret)
    r = c.post(
        "/webhook/tally",
        content=body,
        headers={"Content-Type": "application/json", "Tally-Signature": sig},
    )
    assert r.status_code == 200
    assert r.json() == {"status": "received", "responseId": "resp_abc123"}


def test_webhook_invalid_signature(client):
    c, _ = client
    payload = _full_payload()
    body = json.dumps(payload).encode("utf-8")
    r = c.post(
        "/webhook/tally",
        content=body,
        headers={"Content-Type": "application/json", "Tally-Signature": "wrong"},
    )
    assert r.status_code == 400
    assert r.json()["error"] == "invalid_signature"


def test_webhook_missing_required_fields(client):
    c, secret = client
    payload = _full_payload()
    payload["data"]["fields"] = [
        {"key": "nickname", "value": "x"},
        {"key": "contact", "value": "a@b.com"},
        {"key": "A1", "value": 1},
    ]
    body = json.dumps(payload).encode("utf-8")
    sig = _sign_body(body, secret)
    r = c.post(
        "/webhook/tally",
        content=body,
        headers={"Content-Type": "application/json", "Tally-Signature": sig},
    )
    assert r.status_code == 422
    data = r.json()
    assert data["error"] == "missing_required_fields"
    assert "A2" in data["fields"]


def test_verify_tally_signature_accepts_sha256_hex_prefix():
    from main import verify_tally_signature

    body = b'{"eventId":"1"}'
    secret = "sec"
    mac = hmac.new(secret.encode("utf-8"), body, hashlib.sha256)
    assert verify_tally_signature(body, "sha256=" + mac.hexdigest(), secret)
    assert verify_tally_signature(body, base64.b64encode(mac.digest()).decode("ascii"), secret)


def _wechat_signature(token: str, timestamp: str, nonce: str) -> str:
    raw = "".join(sorted((token, timestamp, nonce)))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def test_wechat_callback_returns_echostr(client, monkeypatch):
    token = "wechat-test-token"
    monkeypatch.setenv("WECHAT_TOKEN", token)
    c, _ = client
    ts, nonce = "1700000000", "random-nonce"
    sig = _wechat_signature(token, ts, nonce)
    r = c.get(
        "/wechat/callback",
        params={
            "signature": sig,
            "timestamp": ts,
            "nonce": nonce,
            "echostr": "plain-echo-123",
        },
    )
    assert r.status_code == 200
    assert r.text == "plain-echo-123"
    assert "text/plain" in r.headers.get("content-type", "")


def test_wechat_callback_403_on_bad_signature(client, monkeypatch):
    monkeypatch.setenv("WECHAT_TOKEN", "correct-token")
    c, _ = client
    r = c.get(
        "/wechat/callback",
        params={
            "signature": "deadbeef" * 5,
            "timestamp": "1",
            "nonce": "2",
            "echostr": "x",
        },
    )
    assert r.status_code == 403
    assert r.text == ""
    assert "text/plain" in r.headers.get("content-type", "")


def test_wechat_callback_403_when_query_incomplete(client, monkeypatch):
    monkeypatch.setenv("WECHAT_TOKEN", "t")
    c, _ = client
    r = c.get("/wechat/callback", params={"signature": "a", "timestamp": "b"})
    assert r.status_code == 403

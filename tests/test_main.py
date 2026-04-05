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
    monkeypatch.setattr(app_main, "run_h5_pipeline", lambda *a, **k: None)
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


def _h5_answers():
    d = {}
    for i in range(1, 7):
        d[f"A{i}"] = 4
        d[f"B{i}"] = 3
    return d


def test_quiz_submit_returns_processing(client):
    c, _ = client
    r = c.post(
        "/quiz/submit",
        json={
            "nickname": "小月",
            "contact": "u@example.com",
            "openid": "oOPENID",
            "answers": _h5_answers(),
        },
    )
    assert r.status_code == 200
    assert r.json() == {"status": "processing"}


def test_quiz_submit_openid_empty_ok(client):
    c, _ = client
    r = c.post(
        "/quiz/submit",
        json={
            "nickname": "小月",
            "contact": "u@example.com",
            "openid": "",
            "answers": _h5_answers(),
        },
    )
    assert r.status_code == 200
    assert r.json() == {"status": "processing"}


def test_quiz_submit_validation_error(client):
    c, _ = client
    answers = _h5_answers()
    del answers["A2"]
    r = c.post(
        "/quiz/submit",
        json={
            "nickname": "x",
            "contact": "a@b.com",
            "openid": "",
            "answers": answers,
        },
    )
    assert r.status_code == 422
    body = r.json()
    assert body["error"] == "missing_required_fields"
    assert "A2" in body["fields"]


def test_wechat_post_subscribe_returns_welcome_xml(client, monkeypatch):
    monkeypatch.setenv("WECHAT_TOKEN", "wx-tok")
    monkeypatch.setenv("H5_BASE_URL", "https://h5.example.com")
    c, _ = client
    ts, nonce = "1700000002", "nonce-sub"
    sig = _wechat_signature("wx-tok", ts, nonce)
    xml_body = """<xml>
<ToUserName><![CDATA[gh_service]]></ToUserName>
<FromUserName><![CDATA[oUserOpenId]]></FromUserName>
<CreateTime>123456</CreateTime>
<MsgType><![CDATA[event]]></MsgType>
<Event><![CDATA[subscribe]]></Event>
</xml>"""
    r = c.post(
        "/wechat/callback",
        params={"signature": sig, "timestamp": ts, "nonce": nonce},
        content=xml_body.encode("utf-8"),
        headers={"Content-Type": "application/xml"},
    )
    assert r.status_code == 200
    assert "xml" in r.headers.get("content-type", "")
    assert "https://h5.example.com/attachment-test" in r.text
    assert "oUserOpenId" in r.text
    assert "gh_service" in r.text


def test_wechat_post_text_returns_welcome_xml(client, monkeypatch):
    monkeypatch.setenv("WECHAT_TOKEN", "wx-tok")
    monkeypatch.setenv("H5_BASE_URL", "https://x.com")
    c, _ = client
    ts, nonce = "1700000003", "n-text"
    sig = _wechat_signature("wx-tok", ts, nonce)
    xml_body = """<xml>
<ToUserName><![CDATA[gh]]></ToUserName>
<FromUserName><![CDATA[fromU]]></FromUserName>
<CreateTime>1</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[hi]]></Content>
</xml>"""
    r = c.post(
        "/wechat/callback",
        params={"signature": sig, "timestamp": ts, "nonce": nonce},
        content=xml_body.encode("utf-8"),
    )
    assert r.status_code == 200
    assert "https://x.com/attachment-test" in r.text


def test_wechat_post_other_event_empty_body(client, monkeypatch):
    monkeypatch.setenv("WECHAT_TOKEN", "wx-tok")
    c, _ = client
    ts, nonce = "1700000004", "n-other"
    sig = _wechat_signature("wx-tok", ts, nonce)
    xml_body = """<xml>
<ToUserName><![CDATA[gh]]></ToUserName>
<FromUserName><![CDATA[u]]></FromUserName>
<CreateTime>1</CreateTime>
<MsgType><![CDATA[event]]></MsgType>
<Event><![CDATA[CLICK]]></Event>
</xml>"""
    r = c.post(
        "/wechat/callback",
        params={"signature": sig, "timestamp": ts, "nonce": nonce},
        content=xml_body.encode("utf-8"),
    )
    assert r.status_code == 200
    assert r.text == ""


def test_wechat_post_invalid_signature_403(client, monkeypatch):
    monkeypatch.setenv("WECHAT_TOKEN", "secret")
    c, _ = client
    r = c.post(
        "/wechat/callback",
        params={"signature": "bad", "timestamp": "1", "nonce": "2"},
        content=b"<xml></xml>",
    )
    assert r.status_code == 403

import hashlib
import uuid

import pytest
from fastapi.testclient import TestClient


def _wechat_signature(token: str, timestamp: str, nonce: str) -> str:
    raw = "".join(sorted((token, timestamp, nonce)))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


@pytest.fixture
def client(monkeypatch):
    import main as app_main

    monkeypatch.setattr(app_main, "run_h5_pipeline", lambda *a, **k: None)
    return TestClient(app_main.app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["version"]


def _h5_answers():
    d = {}
    for i in range(1, 7):
        d[f"A{i}"] = 4
        d[f"B{i}"] = 3
    return d


def _assert_quiz_submit_processing(r):
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "processing"
    uuid.UUID(data["responseId"])


def test_quiz_submit_returns_processing(client):
    r = client.post(
        "/quiz/submit",
        json={"nickname": "小月", "openid": "oOPENID", "answers": _h5_answers()},
    )
    _assert_quiz_submit_processing(r)


def test_quiz_submit_openid_empty_ok(client):
    r = client.post(
        "/quiz/submit",
        json={"nickname": "小月", "openid": "", "answers": _h5_answers()},
    )
    _assert_quiz_submit_processing(r)


def test_quiz_submit_omit_openid_ok(client):
    r = client.post(
        "/quiz/submit",
        json={"nickname": "小月", "answers": _h5_answers()},
    )
    _assert_quiz_submit_processing(r)


def test_quiz_submit_lowercase_answer_keys_ok(client):
    """前端若传 a1/b6 等小写键，须与 A1/B6 等同视之，避免最后一题被判缺字段。"""
    answers = {}
    for i in range(1, 7):
        answers[f"a{i}"] = 4
        answers[f"b{i}"] = 3
    r = client.post(
        "/quiz/submit",
        json={"nickname": "小月", "openid": "", "answers": answers},
    )
    _assert_quiz_submit_processing(r)


def test_quiz_submit_float_answer_values_ok(client):
    answers = {f"A{i}": 4.0 for i in range(1, 7)} | {f"B{i}": 3.0 for i in range(1, 7)}
    r = client.post(
        "/quiz/submit",
        json={"nickname": "x", "openid": "", "answers": answers},
    )
    _assert_quiz_submit_processing(r)


def test_quiz_submit_validation_error(client):
    answers = _h5_answers()
    del answers["A2"]
    r = client.post(
        "/quiz/submit",
        json={"nickname": "x", "openid": "", "answers": answers},
    )
    assert r.status_code == 422
    body = r.json()
    assert body["error"] == "missing_required_fields"
    assert "A2" in body["fields"]


def test_wechat_callback_returns_echostr(client, monkeypatch):
    token = "wechat-test-token"
    monkeypatch.setenv("WECHAT_TOKEN", token)
    ts, nonce = "1700000000", "random-nonce"
    sig = _wechat_signature(token, ts, nonce)
    r = client.get(
        "/wechat/callback",
        params={"signature": sig, "timestamp": ts, "nonce": nonce, "echostr": "plain-echo-123"},
    )
    assert r.status_code == 200
    assert r.text == "plain-echo-123"
    assert "text/plain" in r.headers.get("content-type", "")


def test_wechat_callback_403_on_bad_signature(client, monkeypatch):
    monkeypatch.setenv("WECHAT_TOKEN", "correct-token")
    r = client.get(
        "/wechat/callback",
        params={"signature": "deadbeef" * 5, "timestamp": "1", "nonce": "2", "echostr": "x"},
    )
    assert r.status_code == 403
    assert r.text == ""
    assert "text/plain" in r.headers.get("content-type", "")


def test_wechat_callback_403_when_query_incomplete(client, monkeypatch):
    monkeypatch.setenv("WECHAT_TOKEN", "t")
    r = client.get("/wechat/callback", params={"signature": "a", "timestamp": "b"})
    assert r.status_code == 403


def test_wechat_post_subscribe_returns_welcome_xml(client, monkeypatch):
    monkeypatch.setenv("WECHAT_TOKEN", "wx-tok")
    monkeypatch.setenv("H5_BASE_URL", "https://h5.example.com")
    ts, nonce = "1700000002", "nonce-sub"
    sig = _wechat_signature("wx-tok", ts, nonce)
    xml_body = """<xml>
<ToUserName><![CDATA[gh_service]]></ToUserName>
<FromUserName><![CDATA[oUserOpenId]]></FromUserName>
<CreateTime>123456</CreateTime>
<MsgType><![CDATA[event]]></MsgType>
<Event><![CDATA[subscribe]]></Event>
</xml>"""
    r = client.post(
        "/wechat/callback",
        params={"signature": sig, "timestamp": ts, "nonce": nonce},
        content=xml_body.encode("utf-8"),
        headers={"Content-Type": "application/xml"},
    )
    assert r.status_code == 200
    assert "xml" in r.headers.get("content-type", "")
    assert "欢迎关注知我实验室" in r.text
    assert "https://hepaima.kyx123.com" in r.text
    assert "https://h5.example.com/attachment-test" in r.text
    assert "SentioLab" in r.text
    assert "oUserOpenId" in r.text
    assert "gh_service" in r.text


def test_wechat_post_text_default_reply(client, monkeypatch):
    monkeypatch.setenv("WECHAT_TOKEN", "wx-tok")
    monkeypatch.setenv("H5_BASE_URL", "https://x.com")
    ts, nonce = "1700000003", "n-text"
    sig = _wechat_signature("wx-tok", ts, nonce)
    xml_body = """<xml>
<ToUserName><![CDATA[gh]]></ToUserName>
<FromUserName><![CDATA[fromU]]></FromUserName>
<CreateTime>1</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[hi]]></Content>
</xml>"""
    r = client.post(
        "/wechat/callback",
        params={"signature": sig, "timestamp": ts, "nonce": nonce},
        content=xml_body.encode("utf-8"),
    )
    assert r.status_code == 200
    assert "SentioLab" in r.text
    assert "进行反馈" in r.text
    assert "attachment-test" not in r.text


def test_wechat_post_text_keyword_redeem_code(client, monkeypatch):
    monkeypatch.setenv("WECHAT_TOKEN", "wx-tok")
    ts, nonce = "1700000010", "n-redeem"
    sig = _wechat_signature("wx-tok", ts, nonce)
    xml_body = """<xml>
<ToUserName><![CDATA[gh]]></ToUserName>
<FromUserName><![CDATA[u]]></FromUserName>
<CreateTime>1</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[给我兑换码]]></Content>
</xml>"""
    r = client.post(
        "/wechat/callback",
        params={"signature": sig, "timestamp": ts, "nonce": nonce},
        content=xml_body.encode("utf-8"),
    )
    assert r.status_code == 200
    assert "CQV9ZL5PJPND" in r.text


def test_wechat_post_text_keyword_coupon_before_other_words(client, monkeypatch):
    """含「优惠码」与其它字时仍匹配优惠码分支。"""
    monkeypatch.setenv("WECHAT_TOKEN", "wx-tok")
    monkeypatch.setenv("H5_BASE_URL", "https://x.com")
    ts, nonce = "1700000011", "n-coupon"
    sig = _wechat_signature("wx-tok", ts, nonce)
    xml_body = """<xml>
<ToUserName><![CDATA[gh]]></ToUserName>
<FromUserName><![CDATA[u]]></FromUserName>
<CreateTime>1</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[优惠码报告]]></Content>
</xml>"""
    r = client.post(
        "/wechat/callback",
        params={"signature": sig, "timestamp": ts, "nonce": nonce},
        content=xml_body.encode("utf-8"),
    )
    assert r.status_code == 200
    assert "HP9-4TT2-QX7P" in r.text


def test_wechat_post_text_report_no_history_shows_retest_link(client, monkeypatch):
    monkeypatch.setenv("WECHAT_TOKEN", "wx-tok")
    monkeypatch.setenv("H5_BASE_URL", "https://x.com")
    ts, nonce = "1700000012", "n-report"
    sig = _wechat_signature("wx-tok", ts, nonce)
    xml_body = """<xml>
<ToUserName><![CDATA[gh]]></ToUserName>
<FromUserName><![CDATA[u]]></FromUserName>
<CreateTime>1</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[报告]]></Content>
</xml>"""
    r = client.post(
        "/wechat/callback",
        params={"signature": sig, "timestamp": ts, "nonce": nonce},
        content=xml_body.encode("utf-8"),
    )
    assert r.status_code == 200
    assert "暂时找不到你的报告记录" in r.text
    assert "https://x.com/attachment-test" in r.text


def test_wechat_post_text_report_with_stored_id(client, monkeypatch):
    import main as app_main

    monkeypatch.setenv("WECHAT_TOKEN", "wx-tok")
    monkeypatch.setenv("H5_BASE_URL", "https://x.com")
    monkeypatch.setattr(app_main, "get_latest_report", lambda oid: "resp-saved-9" if oid == "u" else None)
    ts, nonce = "1700000012b", "n-report2"
    sig = _wechat_signature("wx-tok", ts, nonce)
    xml_body = """<xml>
<ToUserName><![CDATA[gh]]></ToUserName>
<FromUserName><![CDATA[u]]></FromUserName>
<CreateTime>1</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[报告]]></Content>
</xml>"""
    r = client.post(
        "/wechat/callback",
        params={"signature": sig, "timestamp": ts, "nonce": nonce},
        content=xml_body.encode("utf-8"),
    )
    assert r.status_code == 200
    assert "找到你的报告啦" in r.text
    assert "https://x.com/report/resp-saved-9" in r.text


def test_wechat_post_text_start_returns_quiz_link(client, monkeypatch):
    monkeypatch.setenv("WECHAT_TOKEN", "wx-tok")
    monkeypatch.setenv("H5_BASE_URL", "https://x.com")
    ts, nonce = "1700000013", "n-start"
    sig = _wechat_signature("wx-tok", ts, nonce)
    xml_body = """<xml>
<ToUserName><![CDATA[gh]]></ToUserName>
<FromUserName><![CDATA[u]]></FromUserName>
<CreateTime>1</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[开始]]></Content>
</xml>"""
    r = client.post(
        "/wechat/callback",
        params={"signature": sig, "timestamp": ts, "nonce": nonce},
        content=xml_body.encode("utf-8"),
    )
    assert r.status_code == 200
    assert "点击开始依恋类型测试" in r.text
    assert "https://x.com/attachment-test" in r.text


def test_wechat_post_click_contact_us(client, monkeypatch):
    monkeypatch.setenv("WECHAT_TOKEN", "wx-tok")
    ts, nonce = "1700000014", "n-contact"
    sig = _wechat_signature("wx-tok", ts, nonce)
    xml_body = """<xml>
<ToUserName><![CDATA[gh]]></ToUserName>
<FromUserName><![CDATA[u]]></FromUserName>
<CreateTime>1</CreateTime>
<MsgType><![CDATA[event]]></MsgType>
<Event><![CDATA[CLICK]]></Event>
<EventKey><![CDATA[CONTACT_US]]></EventKey>
</xml>"""
    r = client.post(
        "/wechat/callback",
        params={"signature": sig, "timestamp": ts, "nonce": nonce},
        content=xml_body.encode("utf-8"),
    )
    assert r.status_code == 200
    assert "SentioLab" in r.text
    assert "进行反馈" in r.text


def test_wechat_post_click_contact_us_event_key_case_insensitive(client, monkeypatch):
    monkeypatch.setenv("WECHAT_TOKEN", "wx-tok")
    ts, nonce = "1700000015", "n-contact2"
    sig = _wechat_signature("wx-tok", ts, nonce)
    xml_body = """<xml>
<ToUserName><![CDATA[gh]]></ToUserName>
<FromUserName><![CDATA[u]]></FromUserName>
<CreateTime>1</CreateTime>
<MsgType><![CDATA[event]]></MsgType>
<Event><![CDATA[CLICK]]></Event>
<EventKey><![CDATA[contact_us]]></EventKey>
</xml>"""
    r = client.post(
        "/wechat/callback",
        params={"signature": sig, "timestamp": ts, "nonce": nonce},
        content=xml_body.encode("utf-8"),
    )
    assert r.status_code == 200
    assert "进行反馈" in r.text


def test_wechat_post_text_redeem_uses_xml_newlines(client, monkeypatch):
    monkeypatch.setenv("WECHAT_TOKEN", "wx-tok")
    ts, nonce = "1700000016", "n-nl"
    sig = _wechat_signature("wx-tok", ts, nonce)
    xml_body = """<xml>
<ToUserName><![CDATA[gh]]></ToUserName>
<FromUserName><![CDATA[u]]></FromUserName>
<CreateTime>1</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[兑换码]]></Content>
</xml>"""
    r = client.post(
        "/wechat/callback",
        params={"signature": sig, "timestamp": ts, "nonce": nonce},
        content=xml_body.encode("utf-8"),
    )
    assert r.status_code == 200
    assert "&#10;" in r.text
    assert "CQV9ZL5PJPND" in r.text
    assert "恭喜你" in r.text


def test_wechat_post_click_unknown_key_returns_coming_soon(client, monkeypatch):
    monkeypatch.setenv("WECHAT_TOKEN", "wx-tok")
    ts, nonce = "1700000004", "n-other"
    sig = _wechat_signature("wx-tok", ts, nonce)
    xml_body = """<xml>
<ToUserName><![CDATA[gh]]></ToUserName>
<FromUserName><![CDATA[u]]></FromUserName>
<CreateTime>1</CreateTime>
<MsgType><![CDATA[event]]></MsgType>
<Event><![CDATA[CLICK]]></Event>
<EventKey><![CDATA[OTHER_KEY]]></EventKey>
</xml>"""
    r = client.post(
        "/wechat/callback",
        params={"signature": sig, "timestamp": ts, "nonce": nonce},
        content=xml_body.encode("utf-8"),
    )
    assert r.status_code == 200
    assert "功能开发中" in r.text


def test_wechat_post_invalid_signature_403(client, monkeypatch):
    monkeypatch.setenv("WECHAT_TOKEN", "secret")
    r = client.post(
        "/wechat/callback",
        params={"signature": "bad", "timestamp": "1", "nonce": "2"},
        content=b"<xml></xml>",
    )
    assert r.status_code == 403


def test_download_pdf_ok(client, monkeypatch):
    import main as app_main

    monkeypatch.setattr(app_main, "get_pdf_bytes", lambda response_id, settings: b"%PDF-1.4 unit")
    r = client.get("/download/resp-abc123")
    assert r.status_code == 200
    assert r.content == b"%PDF-1.4 unit"
    assert r.headers.get("content-type") == "application/pdf"
    cd = r.headers.get("content-disposition", "")
    assert "attachment" in cd.lower()
    assert "filename*=utf-8''" in cd.lower()


def test_download_pdf_not_found(client, monkeypatch):
    import main as app_main

    def _raise(_rid, _s):
        raise FileNotFoundError(_rid)

    monkeypatch.setattr(app_main, "get_pdf_bytes", _raise)
    r = client.get("/download/missing-id")
    assert r.status_code == 404


def test_download_pdf_bad_request(client, monkeypatch):
    import main as app_main

    def _bad(_rid, _s):
        raise ValueError("bad id")

    monkeypatch.setattr(app_main, "get_pdf_bytes", _bad)
    r = client.get("/download/x")
    assert r.status_code == 400


def test_report_data_ok(client, monkeypatch):
    import main as app_main

    payload = {
        "type_code": "SECURE",
        "type_name_cn": "安全型",
        "anxiety_score": 3.0,
        "avoidance_score": 3.0,
        "nickname": "小月",
        "sections": {"overview": "# 标题\n正文"},
    }
    monkeypatch.setattr(app_main, "get_report_json", lambda response_id, settings: payload)
    r = client.get("/report-data/resp-abc123")
    assert r.status_code == 200
    assert r.json() == payload


def test_report_data_not_found(client, monkeypatch):
    import main as app_main

    def _missing(_rid, _s):
        raise FileNotFoundError(_rid)

    monkeypatch.setattr(app_main, "get_report_json", _missing)
    r = client.get("/report-data/missing-id")
    assert r.status_code == 404


def test_report_data_bad_request(client, monkeypatch):
    import main as app_main

    def _bad(_rid, _s):
        raise ValueError("bad id")

    monkeypatch.setattr(app_main, "get_report_json", _bad)
    r = client.get("/report-data/x")
    assert r.status_code == 400

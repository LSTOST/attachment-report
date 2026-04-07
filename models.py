from __future__ import annotations

import re
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

ANSWER_KEYS = [f"{p}{n}" for p in ("A", "B") for n in range(1, 7)]
ANSWER_KEY_PATTERN = re.compile(r"^[AB]\d$")


def _normalize_answer_key(key: str) -> str:
    """H5/表单可能传 a1、b6 等；仅 A1–A6、B1–B6 计入。"""
    return (key or "").strip().upper()


class TallyField(BaseModel):
    model_config = ConfigDict(extra="ignore")

    key: str
    label: Optional[str] = None
    value: Any = None


class TallyFormData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    responseId: str
    formId: Optional[str] = None
    fields: list[TallyField] = Field(default_factory=list)


class TallyWebhookPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    eventId: str
    eventType: str
    createdAt: str
    data: TallyFormData


class QuizAnswers(BaseModel):
    nickname: str
    contact: str
    contact_type: str
    answers: dict[str, int]


class QuizH5SubmitBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    nickname: str = ""
    contact: str = Field(default="", description="可选；空则按微信 openid 触达")
    openid: str = ""
    answers: dict[str, int] = Field(default_factory=dict)

    @field_validator("contact", mode="before")
    @classmethod
    def _contact_coerce_optional(cls, v: Any) -> str:
        if v is None:
            return ""
        if isinstance(v, str):
            return v.strip()
        return str(v).strip()

    def to_quiz_answers(self) -> QuizAnswers:
        nickname_raw = _field_value_to_str(self.nickname)
        nickname = nickname_raw if nickname_raw else "你"
        contact = _field_value_to_str(self.contact)
        if not contact:
            contact = "wechat"
            contact_type = "wechat"
        else:
            contact_type = "email" if "@" in contact else "wechat"

        answers: dict[str, int] = {}
        for key, raw in self.answers.items():
            nk = _normalize_answer_key(key)
            if not ANSWER_KEY_PATTERN.match(nk):
                continue
            try:
                answers[nk] = _field_value_to_int(raw)
            except (ValueError, TypeError) as e:
                raise QuizParseError(f"invalid answer for {nk}: {e}", [nk]) from e

        missing = [k for k in ANSWER_KEYS if k not in answers]
        if missing:
            raise QuizParseError("missing required answer keys", sorted(missing))

        out_of_range = [k for k, v in answers.items() if v < 1 or v > 7]
        if out_of_range:
            raise QuizParseError("answer values must be 1-7", sorted(out_of_range))

        return QuizAnswers(
            nickname=nickname,
            contact=contact,
            contact_type=contact_type,
            answers=answers,
        )


class QuizParseError(Exception):
    def __init__(self, message: str, fields: Optional[List[str]] = None):
        super().__init__(message)
        self.fields = fields or []


def _field_value_to_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _field_value_to_int(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("boolean not allowed")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not value.is_integer():
            raise ValueError("non-integer float")
        return int(value)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            raise ValueError("empty string")
        # 兼容 "4" / "4.0"（部分组件返回字符串浮点）
        if "." in s:
            f = float(s)
            if not f.is_integer():
                raise ValueError("non-integer in string")
            return int(f)
        return int(s)
    raise ValueError(f"cannot convert to int: {type(value)}")


def parse_quiz_from_payload(payload: TallyWebhookPayload) -> QuizAnswers:
    by_key: dict[str, Any] = {}
    for f in payload.data.fields:
        by_key[f.key] = f.value

    nickname_raw = _field_value_to_str(by_key.get("nickname"))
    nickname = nickname_raw if nickname_raw else "你"

    contact = _field_value_to_str(by_key.get("contact"))
    if not contact:
        raise QuizParseError("contact is required", ["contact"])

    contact_type = "email" if "@" in contact else "wechat"

    answers: dict[str, int] = {}
    for f in payload.data.fields:
        nk = _normalize_answer_key(f.key)
        if not ANSWER_KEY_PATTERN.match(nk):
            continue
        try:
            answers[nk] = _field_value_to_int(f.value)
        except (ValueError, TypeError) as e:
            raise QuizParseError(f"invalid answer for {nk}: {e}", [nk]) from e

    missing = [k for k in ANSWER_KEYS if k not in answers]
    if missing:
        raise QuizParseError("missing required answer keys", sorted(missing))

    out_of_range = [k for k, v in answers.items() if v < 1 or v > 7]
    if out_of_range:
        raise QuizParseError("answer values must be 1-7", sorted(out_of_range))

    return QuizAnswers(
        nickname=nickname,
        contact=contact,
        contact_type=contact_type,
        answers=answers,
    )

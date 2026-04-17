from __future__ import annotations

import re
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field

ANSWER_KEYS = [f"{p}{n}" for p in ("A", "B") for n in range(1, 7)]
ANSWER_KEY_PATTERN = re.compile(r"^[AB]\d$")


def _normalize_answer_key(key: str) -> str:
    """H5/表单可能传 a1、b6 等；仅 A1–A6、B1–B6 计入。"""
    return (key or "").strip().upper()


class QuizAnswers(BaseModel):
    nickname: str
    answers: dict[str, int]


class QuizH5SubmitBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    nickname: str = ""
    openid: str = ""
    answers: dict[str, int] = Field(default_factory=dict)

    def to_quiz_answers(self) -> QuizAnswers:
        nickname_raw = _field_value_to_str(self.nickname)
        nickname = nickname_raw if nickname_raw else "你"

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

        return QuizAnswers(nickname=nickname, answers=answers)


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



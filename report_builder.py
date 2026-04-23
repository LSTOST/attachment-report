from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from classifier import TypeCode

TYPE_DIR: dict[str, str] = {
    "SECURE": "secure",
    "ANXIOUS": "anxious",
    "AVOIDANT": "avoidant",
    "FEARFUL": "fearful",
}

TYPE_NAME_CN: dict[str, str] = {
    "SECURE": "安全型",
    "ANXIOUS": "焦虑型",
    "AVOIDANT": "回避型",
    "FEARFUL": "恐惧型",
}

SECTION_FILES = ("overview", "patterns", "conflicts", "compatibility", "exercises")


@dataclass
class ReportData:
    type_code: str
    type_name_cn: str
    anxiety_score: float
    avoidance_score: float
    nickname: str
    sections: dict[str, str]


def _content_root() -> Path:
    return Path(__file__).resolve().parent / "content"


def build_report(
    type_code: TypeCode,
    anxiety_score: float,
    avoidance_score: float,
    nickname: str,
) -> ReportData:
    sub = TYPE_DIR.get(type_code)
    if not sub:
        raise ValueError(f"unknown type_code: {type_code}")

    root = _content_root() / sub
    if not root.is_dir():
        raise FileNotFoundError(
            f"content directory missing for type {type_code}: {root} (expected markdown files under content/{sub}/)"
        )

    sections: dict[str, str] = {}

    for name in SECTION_FILES:
        path = root / f"{name}.md"
        if not path.is_file():
            raise FileNotFoundError(f"missing content file: {path}")

        sections[name] = path.read_text(encoding="utf-8")

    return ReportData(
        type_code=type_code,
        type_name_cn=TYPE_NAME_CN[type_code],
        anxiety_score=anxiety_score,
        avoidance_score=avoidance_score,
        nickname=nickname,
        sections=sections,
    )


def report_data_from_stored_dict(data: dict[str, Any]) -> ReportData:
    """从 OSS 上存储的 JSON（与 asdict(ReportData) 一致）还原为 ReportData。"""
    return ReportData(
        type_code=data["type_code"],
        type_name_cn=data["type_name_cn"],
        anxiety_score=float(data["anxiety_score"]),
        avoidance_score=float(data["avoidance_score"]),
        nickname=data["nickname"],
        sections=dict(data["sections"]),
    )

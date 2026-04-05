from pathlib import Path

import pytest

import report_builder
from report_builder import build_report


@pytest.mark.parametrize("code", ["SECURE", "ANXIOUS", "AVOIDANT", "FEARFUL"])
def test_build_report_all_types(code: str):
    r = build_report(code, 3.0, 3.0, "测试")
    assert r.type_code == code
    assert r.nickname == "测试"
    for name in ("overview", "patterns", "conflicts", "compatibility", "exercises"):
        assert name in r.sections
        assert "<" in r.sections[name]


def test_unknown_type_raises():
    with pytest.raises(ValueError, match="unknown type_code"):
        build_report("UNKNOWN", 1.0, 1.0, "x")  # type: ignore[arg-type]


def test_missing_content_file_raises(monkeypatch, tmp_path: Path):
    (tmp_path / "secure").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(report_builder, "_content_root", lambda: tmp_path)
    with pytest.raises(FileNotFoundError) as e:
        build_report("SECURE", 1.0, 1.0, "x")
    assert "overview.md" in str(e.value)

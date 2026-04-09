from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape

from report_builder import SECTION_FILES, ReportData

# PDF 内各章节首行 H1：{type_name_cn}依恋 • {章节名}：
SECTION_PDF_H1_LABEL: dict[str, str] = {
    "overview": "深度解读",
    "patterns": "关系模式",
    "conflicts": "内在冲突",
    "compatibility": "相处与匹配",
    "exercises": "练习建议",
}

PDF_DOCUMENT_TITLE = "依恋报告 • 深度解读"


def _rewrite_section_h1_for_pdf(md: str, type_name_cn: str, section_key: str) -> str:
    label = SECTION_PDF_H1_LABEL[section_key]
    new_h1 = f"# {type_name_cn}依恋 • {label}："
    lines = md.splitlines()
    if lines and lines[0].lstrip().startswith("#"):
        lines[0] = new_h1
        return "\n".join(lines)
    return f"{new_h1}\n\n{md}"


def _base_dir() -> Path:
    return Path(__file__).resolve().parent


def _resolve_noto_fonts(static_dir: Path) -> tuple[Path, Path, str]:
    bundled_regular = static_dir / "fonts" / "NotoSansSC-Regular.otf"
    bundled_bold = static_dir / "fonts" / "NotoSansSC-Bold.otf"
    if bundled_regular.is_file() and bundled_bold.is_file():
        return bundled_regular, bundled_bold, "opentype"
    sys_regular = Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
    sys_bold = Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc")
    if sys_regular.is_file() and sys_bold.is_file():
        return sys_regular, sys_bold, "truetype"
    raise FileNotFoundError(
        "Chinese font files missing: place NotoSansSC-Regular.otf and "
        "NotoSansSC-Bold.otf under static/fonts/, or install fonts-noto-cjk "
        "(Debian: /usr/share/fonts/opentype/noto/NotoSansCJK-*.ttc)."
    )


def _report_with_html_sections(report: ReportData) -> ReportData:
    md = markdown.Markdown(extensions=["nl2br", "sane_lists"])
    html_sections: dict[str, str] = {}
    for name in SECTION_FILES:
        md.reset()
        raw = _rewrite_section_h1_for_pdf(
            report.sections[name], report.type_name_cn, name
        )
        html_sections[name] = md.convert(raw)
    return replace(report, sections=html_sections)


def render_report_pdf(report: ReportData) -> bytes:
    from weasyprint import HTML

    templates_dir = _base_dir() / "templates"
    static_dir = _base_dir() / "static"

    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("report.html")

    font_regular, font_bold, font_format = _resolve_noto_fonts(static_dir)

    font_url_regular = font_regular.as_uri()
    font_url_bold = font_bold.as_uri()

    qrcode_path = static_dir / "qrcode.png"
    qrcode_url = qrcode_path.as_uri() if qrcode_path.is_file() else None

    report_html = _report_with_html_sections(report)
    html_str = template.render(
        report=report_html,
        pdf_document_title=PDF_DOCUMENT_TITLE,
        qrcode_url=qrcode_url,
        font_url_regular=font_url_regular,
        font_url_bold=font_url_bold,
        font_format=font_format,
    )

    html = HTML(string=html_str, base_url=str(static_dir))
    return html.write_pdf()

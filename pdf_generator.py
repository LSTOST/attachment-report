from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape

from report_builder import SECTION_FILES, ReportData


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
        html_sections[name] = md.convert(report.sections[name])
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

    report_html = _report_with_html_sections(report)
    html_str = template.render(
        report=report_html,
        font_url_regular=font_url_regular,
        font_url_bold=font_url_bold,
        font_format=font_format,
    )

    html = HTML(string=html_str, base_url=str(static_dir))
    return html.write_pdf()

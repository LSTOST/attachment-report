from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from report_builder import ReportData


def _base_dir() -> Path:
    return Path(__file__).resolve().parent


def render_report_pdf(report: ReportData) -> bytes:
    from weasyprint import HTML

    templates_dir = _base_dir() / "templates"
    static_dir = _base_dir() / "static"

    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("report.html")

    font_regular = static_dir / "fonts" / "NotoSansSC-Regular.otf"
    font_bold = static_dir / "fonts" / "NotoSansSC-Bold.otf"
    if not font_regular.is_file() or not font_bold.is_file():
        raise FileNotFoundError(
            "Chinese font files missing under static/fonts/ "
            "(NotoSansSC-Regular.otf, NotoSansSC-Bold.otf). "
            "Run Docker build or download per implementation_spec."
        )

    font_url_regular = font_regular.as_uri()
    font_url_bold = font_bold.as_uri()

    html_str = template.render(
        report=report,
        font_url_regular=font_url_regular,
        font_url_bold=font_url_bold,
    )

    html = HTML(string=html_str, base_url=str(static_dir))
    return html.write_pdf()

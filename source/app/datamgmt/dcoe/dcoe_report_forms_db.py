#  OhCR / DCOE fillable report forms

from __future__ import annotations

import datetime
import json
from pathlib import Path

from app import app


def _forms_path() -> Path:
    return Path(app.root_path) / "resources" / "dcoe" / "report_forms.json"


def load_report_forms_config() -> dict:
    with _forms_path().open(encoding="utf-8") as handle:
        return json.load(handle)


def get_report_form_schema(template_key: str | None) -> dict:
    config = load_report_forms_config()
    forms = config.get("forms", {})
    if template_key and template_key in forms:
        schema = dict(forms[template_key])
    else:
        schema = {
            "title": "OhCR/DCOE Report",
            "tlp": config.get("default_tlp", "AMBER+STRICT"),
            "sections": [
                {
                    "id": "body",
                    "label": "Report Content",
                    "fields": [
                        {
                            "id": "body",
                            "label": "Content",
                            "type": "textarea",
                            "rows": 12,
                            "placeholder": "Enter report content",
                        }
                    ],
                }
            ],
        }
    schema["template_key"] = template_key
    return schema


def _empty_field_value(field: dict):
    if field.get("type") == "checkbox":
        return False
    return ""


def _empty_section_instance(section: dict) -> dict:
    return {field["id"]: _empty_field_value(field) for field in section.get("fields", [])}


def _section_instances(form_data: dict, section: dict) -> list[dict]:
    sections_data = form_data.get("_sections") or {}
    instances = sections_data.get(section["id"])
    if isinstance(instances, list) and instances:
        return instances
    return [_empty_section_instance(section)]


def empty_form_data(schema: dict) -> dict:
    data: dict = {"_sections": {}}
    for section in schema.get("sections", []):
        if section.get("repeatable"):
            min_count = max(1, int(section.get("min_instances", 1)))
            data["_sections"][section["id"]] = [_empty_section_instance(section) for _ in range(min_count)]
        else:
            for field in section.get("fields", []):
                data[field["id"]] = _empty_field_value(field)
    return data


def default_form_data(schema: dict, *, case_name: str, customer_name: str, author: str) -> dict:
    data = empty_form_data(schema)
    data["_case_name"] = case_name or ""
    data["_customer"] = customer_name or ""
    data["_author"] = author or ""
    data["_report_date"] = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    return data


def _format_field_value(field: dict, value) -> str:
    field_type = field.get("type", "text")
    if field_type == "checkbox":
        return "Yes" if value else "No"
    text = str(value or "").strip()
    return text if text else "—"


def _append_field_lines(lines: list[str], field: dict, value) -> None:
    field_type = field.get("type", "text")
    label = field.get("label", field["id"])
    if field_type == "textarea":
        lines.append(f"### {label}")
        text = str(value or "").strip()
        lines.append(text if text else "_Not provided_")
        lines.append("")
    elif field_type == "checkbox":
        lines.append(f"- **{label}:** {_format_field_value(field, value)}")
    else:
        lines.append(f"- **{label}:** {_format_field_value(field, value)}")


def compile_form_to_markdown(schema: dict, form_data: dict) -> str:
    title = schema.get("title") or "OhCR/DCOE Report"
    tlp = schema.get("tlp") or "AMBER+STRICT"
    lines = [
        f"# {title}",
        "",
        f"**TLP:** {tlp}",
        f"**Date:** {form_data.get('_report_date', datetime.datetime.utcnow().strftime('%Y-%m-%d'))}",
        f"**Case:** {form_data.get('_case_name', '—')}",
        f"**Author:** {form_data.get('_author', '—')}",
    ]

    customer = form_data.get("_customer", "").strip()
    if customer:
        lines.append(f"**Customer:** {customer}")

    if schema.get("warning"):
        lines.extend(["", f"> **{schema['warning']}**"])

    lines.append("")

    for section in schema.get("sections", []):
        if section.get("repeatable"):
            instances = _section_instances(form_data, section)
            base_label = section.get("label", "Section")
            for idx, instance in enumerate(instances, 1):
                label = f"{base_label} ({idx})" if len(instances) > 1 else base_label
                lines.append(f"## {label}")
                lines.append("")
                for field in section.get("fields", []):
                    _append_field_lines(lines, field, instance.get(field["id"]))
                lines.append("")
        else:
            lines.append(f"## {section.get('label', 'Section')}")
            lines.append("")
            for field in section.get("fields", []):
                _append_field_lines(lines, field, form_data.get(field["id"]))
            lines.append("")

    return "\n".join(lines).strip() + "\n"


def compile_form_to_html(schema: dict, form_data: dict) -> str:
    """Readable HTML preview without requiring markdown knowledge."""
    markdown = compile_form_to_markdown(schema, form_data)
    lines = markdown.splitlines()
    html_parts = ['<div class="dcoe-report-preview-doc">']

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# "):
            html_parts.append(f'<h2 class="dcoe-rpt-title">{stripped[2:]}</h2>')
        elif stripped.startswith("## "):
            html_parts.append(f'<h4 class="dcoe-rpt-section">{stripped[3:]}</h4>')
        elif stripped.startswith("### "):
            html_parts.append(f'<h6 class="dcoe-rpt-field">{stripped[4:]}</h6>')
        elif stripped.startswith("> **"):
            html_parts.append(f'<div class="alert alert-warning py-2">{stripped[4:-2]}</div>')
        elif stripped.startswith("- **"):
            html_parts.append(f'<p class="dcoe-rpt-line">{stripped}</p>')
        elif stripped == "_Not provided_":
            html_parts.append('<p class="text-muted font-italic">Not provided</p>')
        else:
            safe = stripped.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            html_parts.append(f"<p>{safe}</p>")

    html_parts.append("</div>")
    return "\n".join(html_parts)

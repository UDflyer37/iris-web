#  OhCR / DCOE IRIS report template seeding (Manage > Report Templates)

from __future__ import annotations

import datetime
import re
from pathlib import Path

from app import app, db
from app.models import CaseTemplateReport, Languages, ReportType

REPORT_FILE_PREFIX = "dcoe_"
REPORT_TYPE_INVESTIGATION = "Investigation"


def _resources_dir() -> Path:
    return Path(app.root_path) / "resources" / "dcoe"


def _escape_jinja_literals(text: str) -> str:
    """Prevent note content from breaking Jinja rendering."""
    return text.replace("{{", "{ {").replace("}}", "} }")


def build_report_markdown(
    *,
    title: str,
    template_key: str,
    body: str,
    mop_ids: list[str] | None = None,
    roles: list[str] | None = None,
    frequency: str | None = None,
) -> str:
    mop_line = ", ".join(mop_ids) if mop_ids else "—"
    role_line = ", ".join(roles) if roles else "—"
    safe_body = _escape_jinja_literals(body.strip())

    return f"""# {title}

> **OhCR/DCOE** — MOP {mop_line} | Roles: {role_line} | {frequency or "as needed"}
>
> Use **Report Workspace** (sidebar) to fill in this report with guided sections.
> Direct download from Manage → Report Templates exports this placeholder only.

---

{safe_body}
"""


def _report_filename(template_key: str) -> str:
    safe_key = re.sub(r"[^a-z0-9_]+", "_", template_key.lower())
    return f"{REPORT_FILE_PREFIX}{safe_key}.md"


def _get_language_id() -> int:
    language = Languages.query.filter(Languages.code == "EN").first()
    if not language:
        language = Languages.query.order_by(Languages.id.asc()).first()
    if not language:
        raise RuntimeError("No languages configured in IRIS")
    return language.id


def _get_report_type_id() -> int:
    report_type = ReportType.query.filter(ReportType.name == REPORT_TYPE_INVESTIGATION).first()
    if not report_type:
        report_type = ReportType.query.order_by(ReportType.id.asc()).first()
    if not report_type:
        raise RuntimeError("No report types configured in IRIS")
    return report_type.id


def upsert_report_template_record(
    *,
    title: str,
    template_key: str,
    description: str,
    filename: str,
    created_by_user_id: int,
    naming_format: str | None = None,
) -> tuple[CaseTemplateReport, str]:
    language_id = _get_language_id()
    report_type_id = _get_report_type_id()
    naming = naming_format or f"OhCR-{template_key}-%case_name%-%date%"

    existing = CaseTemplateReport.query.filter(CaseTemplateReport.name == title).first()
    if existing:
        changed = False
        if existing.description != description:
            existing.description = description
            changed = True
        if existing.internal_reference != filename:
            existing.internal_reference = filename
            changed = True
        if existing.naming_format != naming:
            existing.naming_format = naming
            changed = True
        if existing.language_id != language_id:
            existing.language_id = language_id
            changed = True
        if existing.report_type_id != report_type_id:
            existing.report_type_id = report_type_id
            changed = True
        if changed:
            db.session.commit()
            return existing, "updated"
        return existing, "unchanged"

    record = CaseTemplateReport(
        name=title,
        description=description,
        internal_reference=filename,
        naming_format=naming,
        created_by_user_id=created_by_user_id,
        date_created=datetime.datetime.utcnow(),
        language_id=language_id,
        report_type_id=report_type_id,
    )
    db.session.add(record)
    db.session.commit()
    return record, "created"


def bootstrap_dcoe_report_templates(
    reporting_data: dict,
    note_templates: dict,
    created_by_user_id: int,
) -> tuple[int, int, int, dict[str, int]]:
    """
    Write .md templates to TEMPLATES_PATH and register them in CaseTemplateReport.
    Returns created, updated, unchanged counts and key -> report_id map.
    """
    templates_path = Path(app.config["TEMPLATES_PATH"])
    templates_path.mkdir(parents=True, exist_ok=True)

    note_content = note_templates.get("templates", {})
    created = updated = unchanged = 0
    key_to_report_id: dict[str, int] = {}

    for entry in reporting_data.get("templates", []):
        key = entry.get("key")
        if not key or key == "reporting_catalog":
            continue

        title = entry["title"]
        body = ""
        if key in note_content:
            body = note_content[key].get("content", "")
        elif entry.get("description"):
            body = entry["description"]

        markdown = build_report_markdown(
            title=title,
            template_key=key,
            body=body,
            mop_ids=entry.get("mop_ids"),
            roles=entry.get("roles"),
            frequency=entry.get("frequency"),
        )

        filename = _report_filename(key)
        file_path = templates_path / filename
        file_path.write_text(markdown, encoding="utf-8")

        description = entry.get("description") or f"OhCR/DCOE — MOP {', '.join(entry.get('mop_ids', []))}"
        record, state = upsert_report_template_record(
            title=title,
            template_key=key,
            description=description,
            filename=filename,
            created_by_user_id=created_by_user_id,
        )
        key_to_report_id[key] = record.id

        if state == "created":
            created += 1
        elif state == "updated":
            updated += 1
        else:
            unchanged += 1

    return created, updated, unchanged, key_to_report_id

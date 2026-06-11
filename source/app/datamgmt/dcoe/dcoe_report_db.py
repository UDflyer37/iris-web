#  OhCR / DCOE report workspace — preview, edit, download, task attachment

from __future__ import annotations

import datetime
import json
import os
import re
import tempfile
import uuid
from pathlib import Path

from flask_login import current_user
from sqlalchemy.orm.attributes import flag_modified

from app import app, db
from app.datamgmt.case.case_db import get_case
from app.datamgmt.case.case_tasks_db import add_comment_to_task, get_task
from app.datamgmt.manage.manage_attribute_db import get_default_custom_attributes
from app.datamgmt.dcoe.dcoe_report_forms_db import (
    compile_form_to_html,
    compile_form_to_markdown,
    default_form_data,
    get_report_form_schema,
)
from app.iris_engine.reporter.reporter import IrisMakeMdReport, IrisReportMaker
from app.models import CaseTemplateReport, CaseTasks, Comments
from app.models.authorization import User

DRAFTS_KEY = "dcoe_report_drafts"
REPORT_FILE_PREFIX = "dcoe_"


def _now_iso() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


def _drafts_container(case) -> dict:
    attrs = case.custom_attributes or {}
    container = attrs.get(DRAFTS_KEY)
    if not isinstance(container, dict):
        container = {"drafts": []}
    container.setdefault("drafts", [])
    return container


def list_report_drafts(case) -> list[dict]:
    return list(_drafts_container(case).get("drafts", []))


def get_report_draft(case, draft_id: str) -> dict | None:
    for draft in list_report_drafts(case):
        if draft.get("id") == draft_id:
            return draft
    return None


def save_drafts_container(case, container: dict) -> None:
    attrs = dict(case.custom_attributes or {})
    attrs[DRAFTS_KEY] = container
    case.custom_attributes = attrs
    flag_modified(case, "custom_attributes")
    db.session.commit()


def resolve_template_by_key(template_key: str) -> CaseTemplateReport | None:
    if not template_key:
        return None
    filename = f"{REPORT_FILE_PREFIX}{template_key}.md"
    return CaseTemplateReport.query.filter(
        CaseTemplateReport.internal_reference == filename
    ).first()


def resolve_template_key_from_tags(task_tags: str | None) -> str | None:
    if not task_tags:
        return None
    for tag in task_tags.split(","):
        tag = tag.strip()
        if tag.startswith("report-template-"):
            return tag.replace("report-template-", "", 1)
    return None


def _template_key_from_reference(internal_reference: str | None) -> str | None:
    if not internal_reference:
        return None
    match = re.match(rf"{REPORT_FILE_PREFIX}(.+)\.md$", internal_reference)
    return match.group(1) if match else None


_CATEGORY_LABELS = {
    "daily": "Daily reports",
    "as_needed": "As needed",
    "per_incident": "Per incident / hunt",
    "per_finding": "Per finding",
    "end_of_mission": "End of mission",
    "reference": "Reference",
}


def _load_reporting_catalog() -> dict[str, dict]:
    catalog_path = Path(app.root_path) / "resources" / "dcoe" / "reporting_templates.json"
    if not catalog_path.exists():
        return {}
    with catalog_path.open(encoding="utf-8") as handle:
        config = json.load(handle)
    return {
        entry["key"]: entry
        for entry in config.get("templates", [])
        if entry.get("key")
    }


def list_investigation_templates(*, include_reference: bool = False) -> list[dict]:
    from app.models import Languages, ReportType

    catalog = _load_reporting_catalog()
    reports = CaseTemplateReport.query.join(
        CaseTemplateReport.report_type
    ).join(
        CaseTemplateReport.language
    ).filter(
        ReportType.name == "Investigation"
    ).order_by(CaseTemplateReport.name).all()

    rows = []
    for report in reports:
        template_key = _template_key_from_reference(report.internal_reference)
        if not template_key:
            continue
        meta = catalog.get(template_key, {})
        if meta.get("frequency") == "reference" and not include_reference:
            continue
        frequency = meta.get("frequency", "as_needed")
        rows.append({
            "id": report.id,
            "name": report.name,
            "description": meta.get("description") or report.description or "",
            "language": report.language.name if report.language else "",
            "template_key": template_key,
            "frequency": frequency,
            "category": frequency,
            "category_label": _CATEGORY_LABELS.get(frequency, "Other reports"),
            "roles": meta.get("roles", []),
            "mop_ids": meta.get("mop_ids", []),
        })
    return rows


def build_case_report_context(
    caseid: int,
    doc_type: str = "Investigation",
    user_name: str | None = None,
) -> dict:
    maker = IrisMakeMdReport(tempfile.gettempdir(), 0, caseid)
    case_info = maker.get_case_info(doc_type)
    if case_info is None:
        raise ValueError("Unable to build report context for case")
    case_info["doc_id"] = IrisReportMaker.get_docid()
    if user_name:
        case_info["user"] = user_name
    else:
        case_info["user"] = current_user.name if current_user.is_authenticated else "System"
    case_info["date"] = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    return case_info


def _case_header_context(case, user_login: str) -> dict:
    customer_name = ""
    if case.client:
        customer_name = case.client.name or ""
    return {
        "case_name": case.name or "",
        "customer_name": customer_name,
        "author": user_login,
    }


def create_report_draft(
    case,
    *,
    report_template_id: int,
    task_id: int | None,
    user_login: str,
) -> dict:
    report = CaseTemplateReport.query.filter(CaseTemplateReport.id == report_template_id).first()
    if not report:
        raise ValueError("Report template not found")

    template_key = _template_key_from_reference(report.internal_reference)
    header = _case_header_context(case, user_login)
    schema = get_report_form_schema(template_key)
    form_data = default_form_data(
        schema,
        case_name=header["case_name"],
        customer_name=header["customer_name"],
        author=header["author"],
    )
    content = compile_form_to_markdown(schema, form_data)

    title = _draft_title(case, report, template_key, task_id)

    draft = {
        "id": f"draft-{uuid.uuid4().hex[:12]}",
        "report_template_id": report_template_id,
        "report_template_key": template_key,
        "report_template_name": report.name,
        "task_id": task_id,
        "title": title,
        "content": content,
        "form_data": form_data,
        "form_schema_key": template_key,
        "status": "draft",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "created_by": user_login,
        "updated_by": user_login,
        "attached_at": None,
        "download_filename": None,
    }

    container = _drafts_container(case)
    container["drafts"].insert(0, draft)
    save_drafts_container(case, container)
    return draft


def update_report_draft(
    case,
    draft_id: str,
    *,
    form_data: dict | None = None,
    content: str | None = None,
    user_login: str,
) -> dict:
    container = _drafts_container(case)
    for draft in container["drafts"]:
        if draft.get("id") != draft_id:
            continue
        schema = get_report_form_schema(draft.get("form_schema_key") or draft.get("report_template_key"))
        if form_data is not None:
            merged = dict(draft.get("form_data") or {})
            merged.update(form_data)
            draft["form_data"] = merged
            draft["content"] = compile_form_to_markdown(schema, merged)
        elif content is not None:
            draft["content"] = content
        draft["updated_at"] = _now_iso()
        draft["updated_by"] = user_login
        save_drafts_container(case, container)
        return draft
    raise ValueError("Draft not found")


def draft_preview_html(draft: dict) -> str:
    schema = get_report_form_schema(draft.get("form_schema_key") or draft.get("report_template_key"))
    form_data = draft.get("form_data") or {}
    return compile_form_to_html(schema, form_data)


def delete_report_draft(case, draft_id: str) -> None:
    container = _drafts_container(case)
    container["drafts"] = [d for d in container["drafts"] if d.get("id") != draft_id]
    save_drafts_container(case, container)


def _set_nested_custom_attribute(task: CaseTasks, tab: str, field: str, value) -> None:
    attrs = task.custom_attributes or get_default_custom_attributes("task")
    tab_data = dict(attrs.get(tab, {}))
    tab_data[field] = value
    attrs[tab] = tab_data
    task.custom_attributes = attrs
    flag_modified(task, "custom_attributes")


def attach_draft_to_task(case, draft_id: str, task_id: int, user_id: int) -> dict:
    draft = get_report_draft(case, draft_id)
    if not draft:
        raise ValueError("Draft not found")

    task = get_task(task_id, case.case_id)
    if not task:
        raise ValueError("Task not found for this case")

    workspace_url = f"/case/dcoe/reports?cid={case.case_id}&task_id={task_id}&draft_id={draft_id}"

    _set_nested_custom_attribute(task, "METL Tracking", "Evidence link", workspace_url)
    _set_nested_custom_attribute(
        task,
        "METL Tracking",
        "Report template",
        draft.get("report_template_name") or draft.get("report_template_key") or "",
    )
    if draft.get("report_template_key"):
        mop_match = re.search(r"mop-([\d.]+)", task.task_tags or "")
        if mop_match:
            _set_nested_custom_attribute(task, "METL Tracking", "MOP ID", mop_match.group(1))
    db.session.commit()

    comment = Comments(
        comment_text=(
            f"OhCR/DCOE report draft attached: **{draft.get('title')}**\n\n"
            f"[Open in Report Workspace]({workspace_url})"
        ),
        comment_case_id=case.case_id,
        comment_user_id=user_id,
        comment_date=datetime.datetime.utcnow(),
        comment_update_date=datetime.datetime.utcnow(),
    )
    db.session.add(comment)
    db.session.commit()
    add_comment_to_task(task.id, comment.comment_id)

    container = _drafts_container(case)
    for entry in container["drafts"]:
        if entry.get("id") == draft_id:
            entry["task_id"] = task_id
            entry["status"] = "attached"
            entry["attached_at"] = _now_iso()
            entry["updated_at"] = _now_iso()
            break
    save_drafts_container(case, container)

    db.session.commit()
    return {
        "draft": get_report_draft(case, draft_id),
        "task_id": task_id,
        "workspace_url": workspace_url,
    }


def draft_download_path(draft: dict, case_name: str) -> tuple[str, str]:
    safe_case = re.sub(r"[^\w\-]+", "_", case_name or "case")[:40]
    date_stamp = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    filename = f"OhCR-{safe_case}-{draft.get('report_template_key', 'report')}-{date_stamp}.md"
    tmp = tempfile.mkstemp(suffix=".md", prefix="dcoe_report_")
    os.close(tmp[0])
    with open(tmp[1], "w", encoding="utf-8") as handle:
        handle.write(draft.get("content") or "")
    return tmp[1], filename


def workspace_payload(case, caseid: int) -> dict:
    drafts = list_report_drafts(case)
    templates = list_investigation_templates()
    tasks = CaseTasks.query.filter(CaseTasks.task_case_id == caseid).order_by(CaseTasks.id).all()

    from app.datamgmt.dcoe.dcoe_ops_db import compute_task_report_status, get_mission_progress

    task_rows = []
    for task in tasks:
        linked_drafts = [d for d in drafts if d.get("task_id") == task.id]
        status, template_key, is_report_task = compute_task_report_status(
            task_tags=task.task_tags,
            linked_drafts=linked_drafts,
        )
        task_rows.append({
            "task_id": task.id,
            "task_title": task.task_title,
            "task_tags": task.task_tags,
            "report_template_key": template_key,
            "report_status": status,
            "is_report_task": is_report_task,
            "linked_drafts": linked_drafts,
        })

    return {
        "templates": templates,
        "drafts": drafts,
        "tasks": task_rows,
        "editor_mode": "form",
        "progress": get_mission_progress(case),
        "help_steps": [
            "Open a METL task below, or pick a report type and click Start new report",
            "Fill in the boxes on the left — preview updates on the right automatically",
            "Link to a task with Attach, or work directly from the task's Reports section",
        ],
    }


def get_form_schema_payload(template_key: str | None) -> dict:
    return get_report_form_schema(template_key)


def _draft_title(case, report, template_key: str | None, task_id: int | None) -> str:
    title = report.name
    if task_id:
        same_task_type = [
            d for d in list_report_drafts(case)
            if d.get("task_id") == task_id and d.get("report_template_key") == template_key
        ]
        suffix = f" — Task #{task_id}"
        if len(same_task_type) >= 1:
            title = f"{report.name} ({len(same_task_type) + 1}){suffix}"
        else:
            title = f"{report.name}{suffix}"
    return title


def list_task_report_drafts(case, task_id: int) -> list[dict]:
    return [d for d in list_report_drafts(case) if d.get("task_id") == task_id]


def _draft_download_url(case_id: int, draft_id: str, export_format: str = "docx") -> str:
    return f"/case/dcoe/reports/drafts/{draft_id}/download?cid={case_id}&format={export_format}"


def _draft_entry_payload(case, draft: dict) -> dict:
    template_key = draft.get("form_schema_key") or draft.get("report_template_key")
    return {
        "draft": draft,
        "schema": get_form_schema_payload(template_key),
        "preview_html": draft_preview_html(draft),
        "download_url": _draft_download_url(case.case_id, draft["id"], "docx"),
    }


def create_task_report_draft(
    case,
    task_id: int,
    *,
    report_template_id: int | None = None,
    template_key: str | None = None,
    user_login: str,
) -> dict:
    task = get_task(task_id, case.case_id)
    if not task:
        raise ValueError("Task not found for this case")

    if not report_template_id and template_key:
        report = resolve_template_by_key(template_key)
        if report:
            report_template_id = report.id

    if not report_template_id:
        default_key = resolve_template_key_from_tags(task.task_tags)
        if default_key:
            report = resolve_template_by_key(default_key)
            if report:
                report_template_id = report.id

    if not report_template_id:
        raise ValueError("Report template is required")

    draft = create_report_draft(
        case,
        report_template_id=int(report_template_id),
        task_id=task_id,
        user_login=user_login,
    )
    return draft


def save_task_report_draft(
    case,
    task_id: int,
    draft_id: str,
    form_data: dict,
    user_login: str,
    user_id: int,
) -> dict:
    draft = get_report_draft(case, draft_id)
    if not draft or draft.get("task_id") != task_id:
        raise ValueError("Report draft not found for this task")

    draft = update_report_draft(
        case,
        draft_id,
        form_data=form_data,
        user_login=user_login,
    )
    if draft.get("status") != "attached":
        attach_draft_to_task(case, draft_id, task_id, user_id)
        draft = get_report_draft(case, draft_id) or draft
    else:
        _sync_task_report_evidence_link(case, task_id)
    return draft


def _clear_task_report_evidence_link(case, task_id: int) -> None:
    task = get_task(task_id, case.case_id)
    if not task:
        return
    _set_nested_custom_attribute(task, "METL Tracking", "Evidence link", "")
    db.session.commit()


def delete_task_report_draft(case, task_id: int, draft_id: str) -> None:
    draft = get_report_draft(case, draft_id)
    if not draft or draft.get("task_id") != task_id:
        raise ValueError("Report draft not found for this task")
    delete_report_draft(case, draft_id)
    remaining = list_task_report_drafts(case, task_id)
    if remaining:
        _sync_task_report_evidence_link(case, task_id, primary_draft_id=remaining[0]["id"])
    else:
        _clear_task_report_evidence_link(case, task_id)


def _sync_task_report_evidence_link(case, task_id: int, primary_draft_id: str | None = None) -> None:
    task = get_task(task_id, case.case_id)
    if not task:
        return
    workspace_url = f"/case/dcoe/reports?cid={case.case_id}&task_id={task_id}"
    if primary_draft_id:
        workspace_url += f"&draft_id={primary_draft_id}"
    _set_nested_custom_attribute(task, "METL Tracking", "Evidence link", workspace_url)
    db.session.commit()


def task_reports_list_payload(case, task_id: int) -> dict:
    task = get_task(task_id, case.case_id)
    if not task:
        raise ValueError("Task not found for this case")

    default_template_key = resolve_template_key_from_tags(task.task_tags)
    drafts = list_task_report_drafts(case, task_id)
    workspace_url = f"/case/dcoe/reports?cid={case.case_id}&task_id={task_id}"

    suggested = None
    if default_template_key:
        suggested = next(
            (row for row in list_investigation_templates() if row["template_key"] == default_template_key),
            None,
        )

    return {
        "task_id": task_id,
        "task_title": task.task_title,
        "default_template_key": default_template_key,
        "suggested_template": suggested,
        "templates": list_investigation_templates(),
        "reports": [_draft_entry_payload(case, draft) for draft in drafts],
        "report_count": len(drafts),
        "workspace_url": workspace_url,
        "help_steps": [
            "Pick a report type (or use Suggested if shown) and click Add report",
            "Fill in the boxes — use + Add on log sections for multiple entries",
            "Download when done — your work auto-saves to this task",
        ],
    }

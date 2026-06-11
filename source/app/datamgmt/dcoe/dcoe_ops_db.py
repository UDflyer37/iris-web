#  OhCR / DCOE operational UX — shared context for tasks, reports, and team guidance

from __future__ import annotations

import json
from pathlib import Path

from app import app
from app.datamgmt.case.case_db import get_case_tags
from app.datamgmt.dcoe.dcoe_report_db import list_report_drafts, resolve_template_key_from_tags


def _role_dashboards_path() -> Path:
    return Path(app.root_path) / "resources" / "dcoe" / "role_dashboards.json"


def load_role_dashboards() -> dict:
    with _role_dashboards_path().open(encoding="utf-8") as handle:
        return json.load(handle)


def is_dcoe_mission_case(case) -> bool:
    tags = get_case_tags(case.case_id) if case else []
    markers = {"ohcr", "dcoe", "mission", "cyber-shield", "metl"}
    return any((tag or "").lower() in markers or tag.lower().startswith("ohcr") for tag in tags)


def resolve_user_role(user) -> dict | None:
    if not user or not getattr(user, "is_authenticated", False) or not user.is_authenticated:
        return None
    config = load_role_dashboards()
    roles = config.get("roles", {})
    login = (getattr(user, "user", None) or "").lower()

    for role_key, role in roles.items():
        if (role.get("user_login") or "").lower() == login:
            return {"key": role_key, **role}

    try:
        from app.models.authorization import Group, UserGroup

        group_rows = (
            Group.query.join(UserGroup, UserGroup.group_id == Group.group_id)
            .filter(UserGroup.user_id == user.id)
            .with_entities(Group.group_name)
            .all()
        )
        group_names = {row.group_name for row in group_rows}
        for role_key, role in roles.items():
            if role.get("group") in group_names:
                return {"key": role_key, **role}
    except Exception:
        pass

    return None


def _form_has_content(form_data: dict) -> bool:
    if not form_data:
        return False
    for key, value in form_data.items():
        if key.startswith("_"):
            continue
        if isinstance(value, bool):
            if value:
                return True
        elif str(value or "").strip():
            return True
    sections = form_data.get("_sections") or {}
    for instances in sections.values():
        if not isinstance(instances, list):
            continue
        for instance in instances:
            if not isinstance(instance, dict):
                continue
            for val in instance.values():
                if isinstance(val, bool) and val:
                    return True
                if str(val or "").strip():
                    return True
    return False


def _task_evidence_link(task_custom_attrs: dict | None) -> str:
    if not task_custom_attrs:
        return ""
    metl = task_custom_attrs.get("METL Tracking") or {}
    return (metl.get("Evidence link") or "").strip()


def compute_task_report_status(
    *,
    task_tags: str | None,
    linked_drafts: list[dict] | None,
) -> tuple[str, str | None, bool]:
    """Return (status, template_key, is_report_task) for a single task."""
    linked = linked_drafts or []
    template_key = resolve_template_key_from_tags(task_tags)
    has_content = any(_form_has_content(d.get("form_data")) for d in linked)

    if linked:
        if any(d.get("status") == "attached" for d in linked):
            status = "attached"
        elif has_content:
            status = "in_progress"
        else:
            status = "draft"
    elif template_key:
        status = "needed"
    else:
        status = "optional"

    tags = task_tags or ""
    is_report_task = bool(
        template_key
        or "tm-checklist-report" in tags
        or linked
    )
    return status, template_key, is_report_task


def enrich_tasks_with_dcoe(case, tasks: list[dict]) -> list[dict]:
    drafts = list_report_drafts(case)
    by_task: dict[int, list] = {}
    for draft in drafts:
        tid = draft.get("task_id")
        if tid:
            by_task.setdefault(tid, []).append(draft)

    enriched = []
    for task in tasks:
        row = dict(task)
        tid = row.get("task_id")
        linked = by_task.get(tid, [])
        status, template_key, is_report_task = compute_task_report_status(
            task_tags=row.get("task_tags"),
            linked_drafts=linked,
        )

        row["dcoe_report_count"] = len(linked)
        row["dcoe_report_template_key"] = template_key
        row["dcoe_report_status"] = status
        row["dcoe_is_report_task"] = is_report_task
        enriched.append(row)

    return enriched


def get_mission_progress(case) -> dict:
    drafts = list_report_drafts(case)
    report_drafts = [d for d in drafts if d.get("task_id")]
    attached = sum(1 for d in report_drafts if d.get("status") == "attached")
    filled = sum(1 for d in report_drafts if _form_has_content(d.get("form_data")))

    needed = in_progress = 0
    try:
        from app.datamgmt.case.case_tasks_db import get_tasks_with_assignees

        for row in enrich_tasks_with_dcoe(case, get_tasks_with_assignees(case.case_id)):
            if row.get("dcoe_report_status") == "needed":
                needed += 1
            elif row.get("dcoe_report_status") in ("draft", "in_progress"):
                in_progress += 1
    except Exception:
        pass

    network_coverage_pct = None
    try:
        from app.datamgmt.dcoe.dcoe_network_db import (
            compute_network_coverage,
            get_topology,
            list_assets_for_network,
        )

        net_cov = compute_network_coverage(
            case.case_id,
            get_topology(case),
            list_assets_for_network(case.case_id),
        )
        network_coverage_pct = net_cov.get("coverage_pct")
    except Exception:
        pass

    return {
        "total_drafts": len(drafts),
        "task_linked": len(report_drafts),
        "attached": attached,
        "filled": filled,
        "needed": needed,
        "in_progress": in_progress,
        "network_coverage_pct": network_coverage_pct,
    }


def get_dcoe_ops_context(case, user) -> dict | None:
    if not case or not is_dcoe_mission_case(case):
        return None

    role = resolve_user_role(user)
    progress = get_mission_progress(case)
    cid = case.case_id

    filter_chips = [
        {"id": "all", "label": "All tasks", "filter": "tag", "tag": ""},
        {
            "id": "my_role",
            "label": "My role",
            "filter": "tag",
            "tag": "",
            "regex": False,
            "disabled": True,
        },
        {"id": "reports", "label": "Report MOPs", "filter": "tag", "tag": "tm-checklist-report"},
        {"id": "needs_report", "label": "Needs report", "filter": "status", "status": "needed"},
        {"id": "in_progress", "label": "In progress", "filter": "status", "status": "in_progress|draft"},
        {"id": "moe", "label": "MOE gates", "filter": "tag", "tag": "tm-checklist-moe"},
        {"id": "sitrep", "label": "SitRep 7.2.1", "filter": "tag", "tag": "mop-7.2.1"},
        {"id": "lead", "label": "TM lead", "filter": "tag", "tag": "leader-tm"},
    ]

    if role:
        primary_tags = role.get("metl_tags", {}).get("primary", [])
        also_assigned = role.get("metl_tags", {}).get("also_assigned", [])
        role_tags = list(dict.fromkeys(primary_tags + also_assigned))
        if role_tags:
            filter_chips[1]["tag"] = "|".join(role_tags)
            filter_chips[1]["regex"] = len(role_tags) > 1
            filter_chips[1]["disabled"] = False

    quick_links = [
        {"label": "METL Tasks", "url": f"/case/tasks?cid={cid}", "icon": "fa-list-check"},
        {"label": "Report Workspace", "url": f"/case/dcoe/reports?cid={cid}", "icon": "fa-file-pen"},
        {"label": "Network Map", "url": f"/case/dcoe/network?cid={cid}", "icon": "fa-diagram-project"},
        {"label": "Alerts", "url": f"/alerts?cid={cid}", "icon": "fa-bell"},
        {"label": "Operator Guides", "url": f"/case/notes?cid={cid}", "icon": "fa-book"},
    ]

    workflow = []
    if role and role.get("daily_workflow"):
        workflow = role.get("daily_workflow", {}).get("start_of_shift", [])[:4]

    return {
        "is_mission": True,
        "role_key": role.get("key") if role else None,
        "role_title": role.get("title") if role else "Team member",
        "role_sop": role.get("sop_role", "") if role else "",
        "filter_chips": filter_chips,
        "quick_links": quick_links,
        "workflow_tips": workflow,
        "progress": progress,
        "glossary": {
            "TLP": "Traffic Light Protocol — controls who may receive information",
            "METL": "Mission Essential Task List — required actions for the exercise",
            "NETO": "Network Operations center — customer network team",
            "MOE": "Measure of Effectiveness — validation gates",
            "SitRep": "Situation Report — daily status to leadership/NETO",
        },
    }

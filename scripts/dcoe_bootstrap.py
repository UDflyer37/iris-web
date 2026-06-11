#!/usr/bin/env python3
#  OhCR / DCOE IRIS bootstrap
#  Seeds organisations, role groups, local users, METL case templates, and note templates.
#
#  Usage (from repository root, IRIS app running or DB reachable):
#    python3 scripts/dcoe_bootstrap.py
#    DCOE_BOOTSTRAP_PASSWORD='YourPassword' python3 scripts/dcoe_bootstrap.py
#    python3 scripts/dcoe_bootstrap.py --dry-run
#
#  Inside the app container:
#    docker exec -it iriswebapp_app python3 /iriswebapp/scripts/dcoe_bootstrap.py

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if (SCRIPT_DIR.parent / "app").is_dir():
    SOURCE_ROOT = SCRIPT_DIR.parent
else:
    SOURCE_ROOT = SCRIPT_DIR.parent / "source"
RESOURCES_DIR = SOURCE_ROOT / "app" / "resources" / "dcoe"

if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))


def load_json(name: str) -> dict:
    path = RESOURCES_DIR / name
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def permission_mask(permission_names: list[str]) -> int:
    from app.models.authorization import Permissions

    mask = 0
    for name in permission_names:
        if name not in Permissions._member_names_:
            raise ValueError(f"Unknown permission: {name}")
        mask |= Permissions[name].value
    return mask


ROLE_LOGIN_MAP = {
    "TM": "dcoe-tm",
    "DTM": "dcoe-dtm",
    "KM": "dcoe-km",
    "RMA": "dcoe-rma",
    "NETAD": "dcoe-netad",
    "DF": "dcoe-df",
    "INT": "dcoe-int",
    "END": "dcoe-end",
    "ASA": "dcoe-asa",
    "SIEM": "dcoe-siem",
    "SYSAD": "dcoe-sysad",
}

ALL_TEAM_LOGINS = list(ROLE_LOGIN_MAP.values())


def build_mop_report_map(reporting_data: dict) -> dict:
    mop_map = {}
    for template in reporting_data.get("templates", []):
        for mop_id in template.get("mop_ids", []):
            mop_map[mop_id] = template
    return mop_map


def resolve_task_assignees(leader: str, analyst: str) -> list[str]:
    logins = []
    leader = (leader or "").strip()
    analyst = (analyst or "").strip()

    if leader and leader in ROLE_LOGIN_MAP:
        logins.append(ROLE_LOGIN_MAP[leader])

    if analyst == "ALL":
        for login in ALL_TEAM_LOGINS:
            if login not in logins:
                logins.append(login)
    elif analyst and analyst in ROLE_LOGIN_MAP:
        login = ROLE_LOGIN_MAP[analyst]
        if login not in logins:
            logins.append(login)

    if not logins:
        logins.append(ROLE_LOGIN_MAP["TM"])
    return logins


def metl_task_to_template_task(entry: dict, mop_report_map: dict | None = None) -> dict:
    leader = entry.get("leader") or "—"
    analyst = entry.get("analyst") or "—"
    evidence = entry.get("evidence_type", "")
    comments = entry.get("comments", "")
    leader_code = leader if leader != "—" else ""
    analyst_code = analyst if analyst not in ("—", "") else ""

    description = (
        f"METL {entry['mop_id']} | {entry['core_task']} / {entry['category']}\n"
        f"Leader: {leader} | Analyst: {analyst} | Evidence: {evidence}\n\n"
        f"{entry['description']}"
    )
    if comments:
        description += f"\n\nSOP note: {comments}"

    report_template = None
    if mop_report_map:
        report_template = mop_report_map.get(entry["mop_id"])
    if report_template:
        note_ref = report_template.get("note_ref") or "11 - Reporting Template Library"
        description += (
            f"\n\n**Report deliverable:** Copy `{report_template['title']}` "
            f"from `{note_ref}` and save your completed version with date/MOP in the title."
        )

    tags = [
        "metl",
        "ohcr",
        "dcoe",
        f"mop-{entry['mop_id']}",
        evidence.lower(),
        f"cat-{entry['category'].lower().replace(' ', '-')}",
    ]
    if leader_code:
        tags.append(f"leader-{leader_code.lower().replace('/', '-')}")
    if analyst_code:
        tags.append(f"analyst-{analyst_code.lower().replace('/', '-').replace('+', '')}")

    if evidence == "Report":
        tags.append("tm-checklist-report")
    elif evidence == "MOE":
        tags.append("tm-checklist-moe")

    if report_template:
        tags.append(f"report-template-{report_template['key']}")

    return {
        "title": f"[{entry['mop_id']}] {entry['description'][:120]}",
        "description": description,
        "tags": tags,
        "assignee_logins": resolve_task_assignees(leader_code, analyst_code),
        "report_template_key": report_template["key"] if report_template else None,
    }


def build_note_directories(note_data: dict) -> list[dict]:
    templates = note_data["templates"]
    directories = []

    for directory in note_data["note_directories"]:
        notes = []
        for template_key in directory["notes"]:
            template = templates[template_key]
            notes.append({
                "title": template["title"],
                "content": template["content"],
            })
        directories.append({
            "title": directory["title"],
            "notes": notes,
        })

    return directories


def render_role_operator_note(role_code: str, role: dict) -> str:
    lines = [
        f"TLP:AMBER+STRICT",
        "",
        f"# {role['title']} ({role_code}) — IRIS Operator Guide",
        "",
        f"**Login:** `{role['user_login']}`  |  **Group:** `{role['group']}`",
        f"**SOP role:** {role['sop_role']}",
        "",
        "## Your responsibilities",
    ]
    for item in role["responsibilities"]:
        lines.append(f"- {item}")

    metl = role["metl_tags"]
    lines.extend([
        "",
        "## METL task filters (Mission case → Tasks → Tags column)",
        f"- Primary: `{', '.join(metl['primary'])}`",
    ])
    if metl.get("reporting"):
        lines.append(f"- Reporting: `{', '.join(metl['reporting'])}`")
    if metl.get("also_assigned"):
        lines.append(f"- Also assigned: `{', '.join(metl['also_assigned'])}`")

    lines.extend(["", "## Your note workspaces"])
    for entry in role["note_directories"]:
        lines.append(f"- **{entry['path']}** — {entry['use']}")

    lines.extend(["", "## Alert saved filters (Alerts → Filters → Saved filters)"])
    for entry in role.get("alert_filters", []):
        lines.append(f"- **{entry['name']}** — {entry['when']}")
    for entry in role.get("private_alert_filters", []):
        lines.append(f"- **{entry['name']}** (your private filter) — {entry['description']}")

    lines.extend(["", "## IRIS tools for this role"])
    for entry in role["iris_tools"]:
        lines.append(f"- **{entry['tool']}** — {entry['use']}")

    workflow = role["daily_workflow"]
    for phase, label in [
        ("start_of_shift", "Start of shift"),
        ("during_ops", "During operations"),
        ("end_of_shift", "End of shift"),
    ]:
        lines.extend(["", f"## {label}"])
        for step in workflow[phase]:
            lines.append(f"- {step}")

    lines.extend([
        "",
        "## Reporting deliverables",
    ])
    for item in role["reporting_deliverables"]:
        lines.append(f"- {item}")

    lines.extend([
        "",
        "## Coordinate with",
        ", ".join(role["coordinates_with"]),
        "",
        "---",
        "Bookmark this note. Full reference: `source/app/resources/dcoe/role_operator_guides.md`",
    ])
    return "\n".join(lines)


def build_responsibility_matrix_note(dashboards: dict) -> dict:
    lines = [
        "TLP:AMBER+STRICT",
        "",
        "# OhCR/DCOE Team Responsibility Matrix",
        "",
        "Each team member: log in with your account → open this directory → read **your** operator guide.",
        "",
        "| Role | Login | Primary METL tag | Key reporting |",
        "|------|-------|------------------|---------------|",
    ]
    role_order = ["TM", "DTM", "KM", "RMA", "NETAD", "DF", "INT", "END", "ASA", "SIEM", "SYSAD"]
    for role_code in role_order:
        role = dashboards["roles"][role_code]
        primary_tag = role["metl_tags"]["primary"][0]
        reporting = role["reporting_deliverables"][0]
        lines.append(
            f"| {role['title']} | `{role['user_login']}` | `{primary_tag}` | {reporting} |"
        )

    lines.extend([
        "",
        "## Shared rules",
        "- All evidence and findings go in IRIS — not email or chat",
        "- KM authors SitReps; TM approves MOP 7.2.1",
        "- NETO tickets start at **1001** in `01 - Authority and NETO Access`",
        "- Child investigations use case template **OhCR-DCOE-INCIDENT**",
        "",
        "## Quick navigation",
        "- **Alerts:** `/alerts` — use saved filters listed in your role guide",
        "- **Dashboard:** `/dashboard` — your assigned tasks and cases",
        "- **Mission case Tasks:** filter Tags column per your role guide",
    ])
    return {
        "title": "START HERE — Team Responsibility Matrix",
        "content": "\n".join(lines),
    }


def build_role_guide_directory(dashboards: dict) -> dict:
    role_order = ["TM", "DTM", "KM", "RMA", "NETAD", "DF", "INT", "END", "ASA", "SIEM", "SYSAD"]
    notes = [build_responsibility_matrix_note(dashboards)]
    for role_code in role_order:
        role = dashboards["roles"][role_code]
        notes.append({
            "title": f"Operator Guide — {role['title']} ({role_code})",
            "content": render_role_operator_note(role_code, role),
        })
    return {
        "title": dashboards["mission_case_note_directory"],
        "notes": notes,
    }


def build_mission_case_template(
    metl_data: dict,
    note_data: dict,
    dashboards_data: dict,
    reporting_data: dict,
) -> dict:
    mop_report_map = build_mop_report_map(reporting_data)
    tasks = [
        metl_task_to_template_task(entry, mop_report_map)
        for entry in metl_data["tasks"]
    ]
    directories = [build_role_guide_directory(dashboards_data)]
    directories.extend(build_note_directories(note_data))

    return {
        "name": "OhCR-DCOE-MISSION-MASTER",
        "display_name": "OhCR/DCOE Mission Master Case",
        "description": (
            "Master response mission case for OhCR and DCOE operations. "
            "Contains the full METL checklist (Rev1a), per-role operator guides, "
            "reporting note templates, and NETO tracker structure per OhCR SOP 303 Rev12g."
        ),
        "author": "OhCR/DCOE Bootstrap",
        "title_prefix": "[MISSION]",
        "summary": (
            "\n\n## OhCR/DCOE Mission Case\n"
            "TLP:AMBER+STRICT — Internal system of record (DFIR-IRIS).\n\n"
            "**Every team member:** open `10 - Operator Guides (Read First)` and read your role guide.\n\n"
            "Reporting templates: `11 - Reporting Template Library`.\n\n"
            "Network map: sidebar **Network Topology** (linked to case assets).\n\n"
            "Team Manager: METL Evidence Index + filter `tm-checklist-report`.\n\n"
            "Knowledge Manager: daily SitReps in `07 - Daily SitRep`.\n"
        ),
        "tags": ["ohcr", "dcoe", "mission", "metl", "cyber-shield"],
        "classification": None,
        "tasks": tasks,
        "note_directories": directories,
    }


def my_assigned_alerts_filter_data(user_id: int) -> dict:
    return {
        "alert_title": "",
        "alert_description": "",
        "alert_source": "",
        "alert_tags": "",
        "alert_status_id": "",
        "alert_severity_id": "",
        "alert_classification_id": "",
        "alert_customer_id": "",
        "source_start_date": "",
        "source_end_date": "",
        "creation_start_date": "",
        "creation_end_date": "",
        "alert_assets": "",
        "alert_iocs": "",
        "alert_ids": "",
        "source_reference": "",
        "case_id": "",
        "alert_owner_id": str(user_id),
        "alert_resolution_id": "",
        "custom_conditions": "",
    }


def get_or_create_organisation(org_name: str, org_description: str):
    from app.models import get_or_create
    from app.models.authorization import Organisation
    from app import db

    return get_or_create(db.session, Organisation, org_name=org_name, org_description=org_description)


def get_or_create_group(group_def: dict, permission_sets: dict):
    from app import db
    from app.models.authorization import CaseAccessLevel, Group

    group_name = group_def["group_name"]
    group = Group.query.filter(Group.group_name == group_name).first()

    perm_mask = permission_mask(permission_sets[group_def["permission_set"]])
    auto_follow = group_def.get("auto_follow", True)

    if not group:
        group = Group(
            group_name=group_name,
            group_description=group_def["group_description"],
            group_auto_follow=auto_follow,
            group_auto_follow_access_level=CaseAccessLevel.full_access.value,
            group_permissions=perm_mask,
        )
        db.session.add(group)
        db.session.commit()
        return group, True

    changed = False
    if group.group_permissions != perm_mask:
        group.group_permissions = perm_mask
        changed = True
    if group.group_auto_follow != auto_follow:
        group.group_auto_follow = auto_follow
        changed = True
    if group.group_description != group_def["group_description"]:
        group.group_description = group_def["group_description"]
        changed = True

    if changed:
        db.session.commit()

    return group, False


def get_or_create_case_template(template_dict: dict, created_by_user_id: int):
    from app import db
    from app.datamgmt.manage.manage_case_templates_db import validate_case_template
    from app.models import CaseTemplate

    existing = CaseTemplate.query.filter(CaseTemplate.name == template_dict["name"]).first()
    if existing:
        payload = dict(template_dict)
        if not payload.get("classification"):
            payload.pop("classification", None)

        error = validate_case_template(payload, update=True)
        if error:
            raise RuntimeError(f"Invalid case template {template_dict['name']}: {error}")

        sync_fields = [
            "display_name",
            "description",
            "title_prefix",
            "summary",
            "tags",
            "tasks",
            "note_directories",
        ]
        changed = False
        for field in sync_fields:
            if field in payload and getattr(existing, field) != payload[field]:
                setattr(existing, field, payload[field])
                changed = True

        if changed:
            db.session.commit()
            return existing, "updated"

        return existing, "unchanged"

    payload = dict(template_dict)
    if not payload.get("classification"):
        payload.pop("classification", None)

    error = validate_case_template(payload, update=False)
    if error:
        raise RuntimeError(f"Invalid case template {template_dict['name']}: {error}")

    payload["created_by_user_id"] = created_by_user_id
    template = CaseTemplate(**payload)
    db.session.add(template)
    db.session.commit()
    return template, "created"


def merge_custom_attribute_fields(object_type: str, display_name: str, tab_name: str, fields: dict):
    from sqlalchemy.orm.attributes import flag_modified

    from app import db
    from app.models import CustomAttribute

    attribute = CustomAttribute.query.filter(
        CustomAttribute.attribute_for == object_type,
        CustomAttribute.attribute_display_name == display_name,
    ).first()

    if not attribute:
        return False

    content = attribute.attribute_content or {}
    content[tab_name] = fields
    attribute.attribute_content = content
    flag_modified(attribute, "attribute_content")
    db.session.commit()
    return True


def bootstrap_custom_attributes():
    case_fields = {
        "OhCR/DCOE Mission": {
            "Mission designation": {
                "type": "input_string",
                "mandatory": False,
                "value": "OhCR/DCOE",
            },
            "OPORD reference": {
                "type": "input_string",
                "mandatory": False,
                "value": "",
            },
            "NETO organization": {
                "type": "input_string",
                "mandatory": False,
                "value": "",
            },
            "NETO ticket counter": {
                "type": "input_string",
                "mandatory": False,
                "value": "1001",
            },
            "TLP marking": {
                "type": "input_string",
                "mandatory": False,
                "value": "AMBER+STRICT",
            },
            "Network topology view": {
                "type": "input_string",
                "mandatory": False,
                "value": "/case/dcoe/network",
            },
        }
    }

    task_fields = {
        "METL Tracking": {
            "MOP ID": {
                "type": "input_string",
                "mandatory": False,
                "value": "",
            },
            "Evidence type": {
                "type": "input_string",
                "mandatory": False,
                "value": "",
            },
            "Leader role": {
                "type": "input_string",
                "mandatory": False,
                "value": "",
            },
            "Analyst role": {
                "type": "input_string",
                "mandatory": False,
                "value": "",
            },
            "Evidence link": {
                "type": "input_string",
                "mandatory": False,
                "value": "",
            },
            "Report template": {
                "type": "input_string",
                "mandatory": False,
                "value": "",
            },
            "NETO ticket number": {
                "type": "input_string",
                "mandatory": False,
                "value": "",
            },
            "TM validated": {
                "type": "input_checkbox",
                "mandatory": False,
                "value": False,
            },
        }
    }

    merge_custom_attribute_fields("case", "Cases", "OhCR/DCOE Mission", case_fields["OhCR/DCOE Mission"])
    merge_custom_attribute_fields("task", "Tasks", "METL Tracking", task_fields["METL Tracking"])


def bootstrap_users(roles_data: dict, password: str, dry_run: bool) -> dict:
    from app.datamgmt.manage.manage_groups_db import get_group_by_name
    from app.datamgmt.manage.manage_users_db import add_user_to_group, add_user_to_organisation, create_user, get_user
    from app.models.authorization import Organisation, User

    results = {"created": [], "existing": []}

    org_map = {
        org.org_name: org
        for org in Organisation.query.filter(
            Organisation.org_name.in_([o["org_name"] for o in roles_data["organisations"]])
        ).all()
    }

    for user_def in roles_data["users"]:
        login = user_def["user_login"]
        existing = get_user(login, "user")

        if existing:
            results["existing"].append(login)
            user = existing
            if dry_run:
                continue
        elif dry_run:
            results["created"].append(login)
            continue
        else:
            user_password = None if user_def.get("is_service_account") else password
            user = create_user(
                user_name=user_def["user_name"],
                user_login=login,
                user_password=user_password,
                user_email=user_def["user_email"],
                user_active=True,
                user_is_service_account=user_def.get("is_service_account", False),
            )
            results["created"].append(login)

        for org_name in user_def.get("organisations", []):
            org = org_map.get(org_name)
            if org:
                add_user_to_organisation(user.id, org.org_id)

        for group_name in user_def["groups"]:
            group = get_group_by_name(group_name)
            if group:
                add_user_to_group(user.id, group.group_id)

    return results


def bootstrap_saved_filters(created_by_user_id: int) -> tuple[int, int]:
    from app import db
    from app.models import SavedFilter

    filters_data = load_json("saved_filters.json")
    created = 0
    existing = 0

    for entry in filters_data["filters"]:
        found = SavedFilter.query.filter(
            SavedFilter.filter_name == entry["filter_name"],
            SavedFilter.filter_type == filters_data["filter_type"],
        ).first()

        if found:
            existing += 1
            continue

        saved_filter = SavedFilter(
            filter_name=entry["filter_name"],
            filter_description=entry.get("filter_description", ""),
            filter_data=entry["filter_data"],
            filter_is_private=entry.get("filter_is_private", False),
            filter_type=filters_data["filter_type"],
            created_by=created_by_user_id,
        )
        db.session.add(saved_filter)
        created += 1

    db.session.commit()
    return created, existing


def bootstrap_user_role_filters(dashboards_data: dict) -> tuple[int, int]:
    from app import db
    from app.datamgmt.manage.manage_users_db import get_user
    from app.models import SavedFilter

    created = 0
    existing = 0

    for role in dashboards_data["roles"].values():
        user = get_user(role["user_login"], "user")
        if not user:
            continue

        for entry in role.get("private_alert_filters", []):
            found = SavedFilter.query.filter(
                SavedFilter.filter_name == entry["name"],
                SavedFilter.filter_type == "alerts",
                SavedFilter.created_by == user.id,
            ).first()

            if found:
                existing += 1
                continue

            saved_filter = SavedFilter(
                filter_name=entry["name"],
                filter_description=entry.get("description", ""),
                filter_data=my_assigned_alerts_filter_data(user.id),
                filter_is_private=True,
                filter_type="alerts",
                created_by=user.id,
            )
            db.session.add(saved_filter)
            created += 1

    db.session.commit()
    return created, existing


def bootstrap(dry_run: bool = False) -> int:
    from app import app, db
    from app.models.authorization import User

    with app.app_context():
        password = os.environ.get("DCOE_BOOTSTRAP_PASSWORD")
        if not password:
            password = secrets.token_urlsafe(12)
            generated_password = password
        else:
            generated_password = None

        metl_data = load_json("metl_tasks.json")
        note_data = load_json("note_templates.json")
        roles_data = load_json("roles.json")
        dashboards_data = load_json("role_dashboards.json")
        reporting_data = load_json("reporting_templates.json")
        incident_template = load_json("incident_case_template.json")
        filters_data = load_json("saved_filters.json")
        mission_template = build_mission_case_template(
            metl_data, note_data, dashboards_data, reporting_data
        )

        admin = User.query.filter(User.user == app.config.get("IRIS_ADM_USERNAME", "administrator")).first()
        if not admin:
            admin = User.query.order_by(User.id.asc()).first()
        if not admin:
            print("ERROR: No admin user found. Start IRIS once so post_init creates administrator.")
            return 1

        print("OhCR/DCOE IRIS Bootstrap")
        print(f"  Resources: {RESOURCES_DIR}")
        print(f"  METL tasks: {metl_data['task_count']} ({metl_data['report_mop_count']} Report MOPs)")
        print(f"  Note directories: {len(note_data['note_directories']) + 1} (includes operator guides)")
        print(f"  Role operator guides: {len(dashboards_data['roles'])}")
        print(f"  Alert saved filters: {len(filters_data['filters'])}")
        print(f"  Dry run: {dry_run}")

        if dry_run:
            print("\n[DRY RUN] Would create/update:")
            print(f"  Organisations: {[o['org_name'] for o in roles_data['organisations']]}")
            print(f"  Groups: {len(roles_data['groups'])}")
            print(f"  Users: {len(roles_data['users'])}")
            print(f"  Case templates: {mission_template['name']}, {incident_template['name']}")
            print(f"  Saved filters: {len(filters_data['filters'])} shared alert presets")
            print(f"  Per-user filters: {len(dashboards_data['roles'])} private 'My Assigned Alerts'")
            return 0

        for org_def in roles_data["organisations"]:
            org = get_or_create_organisation(org_def["org_name"], org_def["org_description"])
            print(f"  Organisation ready: {org.org_name}")

        for group_def in roles_data["groups"]:
            group, created = get_or_create_group(group_def, roles_data["permission_sets"])
            action = "created" if created else "updated"
            print(f"  Group {action}: {group.group_name}")

        user_results = bootstrap_users(roles_data, password, dry_run=False)
        print(f"  Users created: {', '.join(user_results['created']) or '(none)'}")
        if user_results["existing"]:
            print(f"  Users already present: {', '.join(user_results['existing'])}")

        mission, mission_state = get_or_create_case_template(mission_template, admin.id)
        incident, incident_state = get_or_create_case_template(incident_template, admin.id)
        print(
            f"  Case template {mission_state}: "
            f"{mission.name} ({len(mission_template['tasks'])} tasks, "
            f"{len(mission_template['note_directories'])} note directories)"
        )
        print(f"  Case template {incident_state}: {incident.name}")

        bootstrap_custom_attributes()
        print("  Custom attributes updated: Cases (OhCR/DCOE Mission), Tasks (METL Tracking)")

        tm_user = User.query.filter(User.user == "dcoe-tm").first() or admin
        filters_created, filters_existing = bootstrap_saved_filters(tm_user.id)
        print(f"  Shared alert filters: {filters_created} created, {filters_existing} already present")

        role_filters_created, role_filters_existing = bootstrap_user_role_filters(dashboards_data)
        print(
            f"  Per-user role filters: {role_filters_created} created, "
            f"{role_filters_existing} already present"
        )

        siem_user = User.query.filter(User.user == "dcoe-siem-api").first()
        if siem_user and siem_user.api_key:
            print(f"  SIEM API key (dcoe-siem-api): {siem_user.api_key}")

        db.session.commit()

        print("\nBootstrap complete.")
        print("\nNext steps:")
        print("  1. Each team member logs in with their dcoe-* account")
        print("  2. TM: Manage > Customers — create NETO/customer entry")
        print("  3. TM: Manage > Cases — new case from 'OhCR-DCOE-MISSION-MASTER'")
        print("  4. ALL: Mission case > 10 - Operator Guides — read your role guide")
        print("  5. Use Alerts saved filters + private 'OhCR-DCOE: My Assigned Alerts'")
        print("  6. Mission case Tasks — filter Tags per your role guide")
        print("  7. Reference: source/app/resources/dcoe/role_operator_guides.md")
        print("  8. SIEM feeder: copy dcoe_siem_feeder.example.json → dcoe_siem_feeder.json")

        if generated_password:
            print("\nLocal account password (all non-service users):")
            print(f"  >>> {generated_password} <<<")
            print("Set DCOE_BOOTSTRAP_PASSWORD to use a fixed password on re-run.")

        if user_results["created"]:
            print("\nLocal accounts:")
            for login in user_results["created"]:
                print(f"  - {login}")

        return 0


def main():
    parser = argparse.ArgumentParser(description="Bootstrap OhCR/DCOE IRIS configuration")
    parser.add_argument("--dry-run", action="store_true", help="Show planned changes without writing to DB")
    args = parser.parse_args()
    return bootstrap(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())

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


def metl_task_to_template_task(entry: dict) -> dict:
    leader = entry.get("leader") or "—"
    analyst = entry.get("analyst") or "—"
    evidence = entry.get("evidence_type", "")
    comments = entry.get("comments", "")

    description = (
        f"METL {entry['mop_id']} | {entry['core_task']} / {entry['category']}\n"
        f"Leader: {leader} | Analyst: {analyst} | Evidence: {evidence}\n\n"
        f"{entry['description']}"
    )
    if comments:
        description += f"\n\nSOP note: {comments}"

    tags = [
        "metl",
        "ohcr",
        "dcoe",
        f"mop-{entry['mop_id']}",
        evidence.lower(),
        f"cat-{entry['category'].lower().replace(' ', '-')}",
    ]
    if leader:
        tags.append(f"leader-{leader.lower().replace('/', '-')}")
    if analyst:
        tags.append(f"analyst-{analyst.lower().replace('/', '-').replace('+', '')}")

    if evidence == "Report":
        tags.append("tm-checklist-report")
    elif evidence == "MOE":
        tags.append("tm-checklist-moe")

    return {
        "title": f"[{entry['mop_id']}] {entry['description'][:120]}",
        "description": description,
        "tags": tags,
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


def build_mission_case_template(metl_data: dict, note_data: dict) -> dict:
    tasks = [metl_task_to_template_task(entry) for entry in metl_data["tasks"]]

    return {
        "name": "OhCR-DCOE-MISSION-MASTER",
        "display_name": "OhCR/DCOE Mission Master Case",
        "description": (
            "Master response mission case for OhCR and DCOE operations. "
            "Contains the full METL checklist (Rev1a), reporting note templates, "
            "and NETO tracker structure per OhCR SOP 303 Rev12g."
        ),
        "author": "OhCR/DCOE Bootstrap",
        "title_prefix": "[MISSION]",
        "summary": (
            "\n\n## OhCR/DCOE Mission Case\n"
            "TLP:AMBER+STRICT — Internal system of record (DFIR-IRIS).\n\n"
            "Team Manager: use **METL Evidence Index** notes and filter tasks tagged "
            "`tm-checklist-report` for daily reporting compliance.\n\n"
            "Knowledge Manager: draft daily SitReps in `07 - Daily SitRep`.\n"
        ),
        "tags": ["ohcr", "dcoe", "mission", "metl", "cyber-shield"],
        "classification": None,
        "tasks": tasks,
        "note_directories": build_note_directories(note_data),
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
        return existing, False

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
    return template, True


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
                is_service_account=user_def.get("is_service_account", False),
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
        incident_template = load_json("incident_case_template.json")
        filters_data = load_json("saved_filters.json")
        mission_template = build_mission_case_template(metl_data, note_data)

        admin = User.query.filter(User.user == app.config.get("IRIS_ADM_USERNAME", "administrator")).first()
        if not admin:
            admin = User.query.order_by(User.id.asc()).first()
        if not admin:
            print("ERROR: No admin user found. Start IRIS once so post_init creates administrator.")
            return 1

        print("OhCR/DCOE IRIS Bootstrap")
        print(f"  Resources: {RESOURCES_DIR}")
        print(f"  METL tasks: {metl_data['task_count']} ({metl_data['report_mop_count']} Report MOPs)")
        print(f"  Note directories: {len(note_data['note_directories'])}")
        print(f"  Alert saved filters: {len(filters_data['filters'])}")
        print(f"  Dry run: {dry_run}")

        if dry_run:
            print("\n[DRY RUN] Would create/update:")
            print(f"  Organisations: {[o['org_name'] for o in roles_data['organisations']]}")
            print(f"  Groups: {len(roles_data['groups'])}")
            print(f"  Users: {len(roles_data['users'])}")
            print(f"  Case templates: {mission_template['name']}, {incident_template['name']}")
            print(f"  Saved filters: {len(filters_data['filters'])} alert presets")
            return 0

        for org_def in roles_data["organisations"]:
            org, _ = get_or_create_organisation(org_def["org_name"], org_def["org_description"])
            print(f"  Organisation ready: {org.org_name}")

        for group_def in roles_data["groups"]:
            group, created = get_or_create_group(group_def, roles_data["permission_sets"])
            action = "created" if created else "updated"
            print(f"  Group {action}: {group.group_name}")

        user_results = bootstrap_users(roles_data, password, dry_run=False)
        print(f"  Users created: {', '.join(user_results['created']) or '(none)'}")
        if user_results["existing"]:
            print(f"  Users already present: {', '.join(user_results['existing'])}")

        mission, mission_created = get_or_create_case_template(mission_template, admin.id)
        incident, incident_created = get_or_create_case_template(incident_template, admin.id)
        print(
            f"  Case template {'created' if mission_created else 'exists'}: "
            f"{mission.name} ({len(mission_template['tasks'])} tasks, "
            f"{len(mission_template['note_directories'])} note directories)"
        )
        print(
            f"  Case template {'created' if incident_created else 'exists'}: {incident.name}"
        )

        bootstrap_custom_attributes()
        print("  Custom attributes updated: Cases (OhCR/DCOE Mission), Tasks (METL Tracking)")

        tm_user = User.query.filter(User.user == "dcoe-tm").first() or admin
        filters_created, filters_existing = bootstrap_saved_filters(tm_user.id)
        print(f"  Saved filters: {filters_created} created, {filters_existing} already present")

        siem_user = User.query.filter(User.user == "dcoe-siem-api").first()
        if siem_user and siem_user.api_key:
            print(f"  SIEM API key (dcoe-siem-api): {siem_user.api_key}")

        db.session.commit()

        print("\nBootstrap complete.")
        print("\nNext steps:")
        print("  1. Log in as dcoe-tm (Team Manager)")
        print("  2. Manage > Customers — create your NETO/customer entry")
        print("  3. Manage > Cases — new case from template 'OhCR-DCOE-MISSION-MASTER'")
        print("  4. Alerts — use saved filter 'OhCR-DCOE: Open Alert Queue'")
        print("  5. Mission case Tasks — filter Tags column: tm-checklist-report")
        print("  6. TM guide: source/app/resources/dcoe/tm_dashboard.md")
        print("  7. SIEM feeder: copy dcoe_siem_feeder.example.json → dcoe_siem_feeder.json")

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

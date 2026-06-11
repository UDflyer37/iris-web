#!/usr/bin/env python3
"""Backfill METL Tracking custom attributes on tasks from the mission case template."""
import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("IRIS_BOOTSTRAP_MODE", "1")

SCRIPT_DIR = Path(__file__).resolve().parent
SOURCE_ROOT = SCRIPT_DIR.parent if (SCRIPT_DIR.parent / "app").is_dir() else SCRIPT_DIR.parent / "source"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

TEMPLATE_NAME = "OhCR-DCOE-MISSION-MASTER"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_id", type=int)
    args = parser.parse_args()

    from sqlalchemy.orm.attributes import flag_modified

    from app import app, db
    from app.datamgmt.manage.manage_attribute_db import get_default_custom_attributes
    from app.models import CaseTemplate, CaseTasks

    with app.app_context():
        template = CaseTemplate.query.filter_by(name=TEMPLATE_NAME).first()
        if not template:
            print("Template not found", file=sys.stderr)
            return 1

        by_title = {entry["title"]: entry for entry in (template.tasks or [])}
        tasks = CaseTasks.query.filter_by(task_case_id=args.case_id).all()
        updated = 0
        for task in tasks:
            spec = by_title.get(task.task_title)
            if not spec or not spec.get("metl_attributes"):
                continue
            attrs = task.custom_attributes or get_default_custom_attributes("task")
            metl = dict(attrs.get("METL Tracking", {}))
            for key, value in spec["metl_attributes"].items():
                if not metl.get(key) and value not in ("", False, None):
                    metl[key] = value
            attrs["METL Tracking"] = metl
            task.custom_attributes = attrs
            flag_modified(task, "custom_attributes")
            updated += 1

        db.session.commit()
        print(f"Updated METL attributes on {updated}/{len(tasks)} tasks for case {args.case_id}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

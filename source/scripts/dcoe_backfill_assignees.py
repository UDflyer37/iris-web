#!/usr/bin/env python3
"""Backfill METL task assignees on an existing case from OhCR-DCOE-MISSION-MASTER."""
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
    parser.add_argument("case_id", type=int, help="Case ID to update")
    args = parser.parse_args()

    from app import app, db
    from app.models import CaseTemplate, CaseTasks, TaskAssignee
    from app.models.authorization import User

    with app.app_context():
        template = CaseTemplate.query.filter_by(name=TEMPLATE_NAME).first()
        if not template:
            print(f"Template not found: {TEMPLATE_NAME}", file=sys.stderr)
            return 1

        by_title = {entry["title"]: entry for entry in (template.tasks or [])}
        tasks = CaseTasks.query.filter_by(task_case_id=args.case_id).all()
        if not tasks:
            print(f"No tasks on case {args.case_id}", file=sys.stderr)
            return 1

        updated = 0
        for task in tasks:
            spec = by_title.get(task.task_title)
            if not spec or not spec.get("assignee_logins"):
                continue

            user_ids = []
            for login in spec["assignee_logins"]:
                user = User.query.filter_by(user=login).first()
                if user and user.id not in user_ids:
                    user_ids.append(user.id)
            if not user_ids:
                continue

            TaskAssignee.query.filter_by(task_id=task.id).delete()
            for user_id in user_ids:
                db.session.add(TaskAssignee(task_id=task.id, user_id=user_id))
            updated += 1

        db.session.commit()

        with_assignees = sum(
            1
            for task in tasks
            if TaskAssignee.query.filter_by(task_id=task.id).count()
        )
        print(
            f"Backfilled {updated} tasks on case {args.case_id}; "
            f"{with_assignees}/{len(tasks)} tasks now have assignees."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

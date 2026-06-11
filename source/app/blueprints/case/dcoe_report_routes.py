#  OhCR / DCOE report workspace routes

import os

from flask import Blueprint, redirect, render_template, request, send_file, url_for
from flask_login import current_user
from flask_wtf import FlaskForm

from app.datamgmt.case.case_db import get_case
from app.datamgmt.dcoe.dcoe_report_db import (
    attach_draft_to_task,
    create_report_draft,
    delete_report_draft,
    draft_preview_html,
    get_form_schema_payload,
    get_report_draft,
    resolve_template_by_key,
    resolve_template_key_from_tags,
    create_task_report_draft,
    delete_task_report_draft,
    save_task_report_draft,
    task_reports_list_payload,
    update_report_draft,
    workspace_payload,
)
from app.datamgmt.dcoe.dcoe_report_export_db import draft_export_path, list_export_formats
from app.datamgmt.case.case_tasks_db import get_task
from app.iris_engine.utils.tracker import track_activity
from app.models.authorization import CaseAccessLevel
from app.util import FileRemover, ac_api_case_requires, ac_case_requires, response_error, response_success

dcoe_report_blueprint = Blueprint(
    "dcoe_reports",
    __name__,
    template_folder="templates",
)

file_remover = FileRemover()


@dcoe_report_blueprint.route("/case/dcoe/reports", methods=["GET"])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def dcoe_reports_page(caseid, url_redir):
    if url_redir:
        return redirect(url_for("dcoe_reports.dcoe_reports_page", cid=caseid, redirect=True))

    from app.datamgmt.dcoe.dcoe_ops_db import get_dcoe_ops_context

    case = get_case(caseid)
    form = FlaskForm()
    dcoe_ops = get_dcoe_ops_context(case, current_user)
    return render_template("dcoe_reports.html", case=case, form=form, dcoe_ops=dcoe_ops, page="dcoe_reports")


@dcoe_report_blueprint.route("/case/dcoe/reports/workspace", methods=["GET"])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def dcoe_reports_workspace(caseid):
    case = get_case(caseid)
    return response_success("", data=workspace_payload(case, caseid))


@dcoe_report_blueprint.route("/case/dcoe/reports/forms/<template_key>", methods=["GET"])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def dcoe_reports_form_schema(caseid, template_key):
    return response_success("", data={"schema": get_form_schema_payload(template_key)})


@dcoe_report_blueprint.route("/case/dcoe/reports/drafts", methods=["POST"])
@ac_api_case_requires(CaseAccessLevel.full_access)
def dcoe_reports_create_draft(caseid):
    case = get_case(caseid)
    payload = request.get_json(silent=True) or {}

    report_template_id = payload.get("report_template_id")
    task_id = payload.get("task_id")
    template_key = payload.get("template_key")

    if not report_template_id and template_key:
        report = resolve_template_by_key(template_key)
        if report:
            report_template_id = report.id

    if not report_template_id and task_id:
        task = get_task(task_id, caseid)
        if task:
            key = resolve_template_key_from_tags(task.task_tags)
            report = resolve_template_by_key(key) if key else None
            if report:
                report_template_id = report.id

    if not report_template_id:
        return response_error("Report template is required")

    try:
        draft = create_report_draft(
            case,
            report_template_id=int(report_template_id),
            task_id=int(task_id) if task_id else None,
            user_login=current_user.user,
        )
    except ValueError as exc:
        return response_error(str(exc))

    track_activity(f"created OhCR/DCOE report draft '{draft.get('title')}'", caseid=caseid)
    return response_success("Draft created", data={
        "draft": draft,
        "preview_html": draft_preview_html(draft),
        "schema": get_form_schema_payload(draft.get("form_schema_key") or draft.get("report_template_key")),
        **workspace_payload(case, caseid),
    })


@dcoe_report_blueprint.route("/case/dcoe/reports/drafts/<draft_id>", methods=["GET"])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def dcoe_reports_get_draft(caseid, draft_id):
    case = get_case(caseid)
    draft = get_report_draft(case, draft_id)
    if not draft:
        return response_error("Draft not found", status=404)
    return response_success("", data={
        "draft": draft,
        "preview_html": draft_preview_html(draft),
        "schema": get_form_schema_payload(draft.get("form_schema_key") or draft.get("report_template_key")),
    })


@dcoe_report_blueprint.route("/case/dcoe/reports/drafts/<draft_id>", methods=["PUT"])
@ac_api_case_requires(CaseAccessLevel.full_access)
def dcoe_reports_save_draft(caseid, draft_id):
    case = get_case(caseid)
    payload = request.get_json(silent=True) or {}
    form_data = payload.get("form_data")
    content = payload.get("content")
    if form_data is None and content is None:
        return response_error("form_data is required")

    try:
        draft = update_report_draft(
            case,
            draft_id,
            form_data=form_data,
            content=content if form_data is None else None,
            user_login=current_user.user,
        )
    except ValueError as exc:
        return response_error(str(exc))

    track_activity("updated OhCR/DCOE report draft", caseid=caseid)
    return response_success("Draft saved", data={
        "draft": draft,
        "preview_html": draft_preview_html(draft),
    })


@dcoe_report_blueprint.route("/case/dcoe/reports/drafts/<draft_id>", methods=["DELETE"])
@ac_api_case_requires(CaseAccessLevel.full_access)
def dcoe_reports_delete_draft(caseid, draft_id):
    case = get_case(caseid)
    if not get_report_draft(case, draft_id):
        return response_error("Draft not found", status=404)
    delete_report_draft(case, draft_id)
    track_activity("deleted OhCR/DCOE report draft", caseid=caseid)
    return response_success("Draft deleted", data=workspace_payload(case, caseid))


@dcoe_report_blueprint.route("/case/dcoe/reports/drafts/<draft_id>/attach", methods=["POST"])
@ac_api_case_requires(CaseAccessLevel.full_access)
def dcoe_reports_attach_draft(caseid, draft_id):
    case = get_case(caseid)
    payload = request.get_json(silent=True) or {}
    task_id = payload.get("task_id")
    if not task_id:
        return response_error("task_id is required")

    try:
        result = attach_draft_to_task(case, draft_id, int(task_id), current_user.id)
    except ValueError as exc:
        return response_error(str(exc))

    track_activity(f"attached report draft to task #{task_id}", caseid=caseid)
    return response_success("Report attached to task", data=result)


@dcoe_report_blueprint.route("/case/dcoe/reports/tasks/<int:task_id>", methods=["GET"])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def dcoe_task_reports_list(caseid, task_id):
    case = get_case(caseid)
    try:
        payload = task_reports_list_payload(case, task_id)
    except ValueError as exc:
        return response_error(str(exc), status=404)
    return response_success("", data=payload)


@dcoe_report_blueprint.route("/case/dcoe/reports/tasks/<int:task_id>/drafts", methods=["POST"])
@ac_api_case_requires(CaseAccessLevel.full_access)
def dcoe_task_report_create(caseid, task_id):
    case = get_case(caseid)
    payload = request.get_json(silent=True) or {}
    report_template_id = payload.get("report_template_id")
    template_key = payload.get("template_key")

    if not report_template_id and template_key:
        report = resolve_template_by_key(template_key)
        if report:
            report_template_id = report.id

    try:
        draft = create_task_report_draft(
            case,
            task_id,
            report_template_id=int(report_template_id) if report_template_id else None,
            template_key=template_key,
            user_login=current_user.user,
        )
    except ValueError as exc:
        return response_error(str(exc))

    track_activity(f"added report to task #{task_id}", caseid=caseid)
    payload = task_reports_list_payload(case, task_id)
    payload["active_draft_id"] = draft["id"]
    return response_success("Report created", data=payload)


@dcoe_report_blueprint.route("/case/dcoe/reports/tasks/<int:task_id>/drafts/<draft_id>", methods=["PUT"])
@ac_api_case_requires(CaseAccessLevel.full_access)
def dcoe_task_report_save(caseid, task_id, draft_id):
    case = get_case(caseid)
    payload = request.get_json(silent=True) or {}
    form_data = payload.get("form_data")
    if form_data is None:
        return response_error("form_data is required")

    try:
        draft = save_task_report_draft(
            case,
            task_id,
            draft_id,
            form_data,
            current_user.user,
            current_user.id,
        )
    except ValueError as exc:
        return response_error(str(exc))

    track_activity(f"updated report for task #{task_id}", caseid=caseid)
    return response_success("Report saved", data={
        "draft": draft,
        "preview_html": draft_preview_html(draft),
        "workspace_url": f"/case/dcoe/reports?cid={caseid}&draft_id={draft['id']}&task_id={task_id}",
        "download_url": f"/case/dcoe/reports/drafts/{draft['id']}/download?cid={caseid}",
    })


@dcoe_report_blueprint.route("/case/dcoe/reports/tasks/<int:task_id>/drafts/<draft_id>", methods=["DELETE"])
@ac_api_case_requires(CaseAccessLevel.full_access)
def dcoe_task_report_delete(caseid, task_id, draft_id):
    case = get_case(caseid)
    try:
        delete_task_report_draft(case, task_id, draft_id)
    except ValueError as exc:
        return response_error(str(exc))

    track_activity(f"removed report from task #{task_id}", caseid=caseid)
    return response_success("Report removed", data=task_reports_list_payload(case, task_id))


@dcoe_report_blueprint.route("/case/dcoe/reports/export-formats", methods=["GET"])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def dcoe_reports_export_formats(caseid):
    return response_success("", data={"formats": list_export_formats()})


@dcoe_report_blueprint.route("/case/dcoe/reports/drafts/<draft_id>/download", methods=["GET"])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def dcoe_reports_download_draft(caseid, draft_id):
    case = get_case(caseid)
    draft = get_report_draft(case, draft_id)
    if not draft:
        return response_error("Draft not found", status=404)

    export_format = request.args.get("format", "docx")

    try:
        fpath, filename, mime, tmp_dir = draft_export_path(draft, case.name, export_format)
    except (OSError, ValueError) as exc:
        return response_error(f"Unable to prepare download: {exc}")

    track_activity(
        f"downloaded OhCR/DCOE report '{draft.get('title')}' as {export_format}",
        caseid=caseid,
    )
    resp = send_file(fpath, as_attachment=True, download_name=filename, mimetype=mime)
    file_remover.cleanup_once_done(resp, tmp_dir)
    return resp

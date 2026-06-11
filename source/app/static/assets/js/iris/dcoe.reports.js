/* OhCR/DCOE report workspace — fillable sections (no markdown editing) */

let dcoeActiveDraftId = null;
let dcoeActiveSchema = null;
let dcoeWorkspace = { templates: [], drafts: [], tasks: [] };
let dcoeReportSaveTimer = null;
let dcoeWsTaskFilter = "all";

function dcoeReportSetStatus(text, kind) {
    const badge = $("#dcoe-report-status");
    badge.text(text);
    badge.removeClass("badge-warning badge-success badge-danger");
    if (kind === "saving") badge.addClass("badge-warning");
    else if (kind === "saved") badge.addClass("badge-success");
    else if (kind === "error") badge.addClass("badge-danger");
}

function dcoeReportCollectFormData() {
    return dcoeFormCollect("#dcoe-report-form-panel");
}

function dcoeReportRenderForm(schema, formData) {
    dcoeActiveSchema = schema;
    dcoeFormRender("#dcoe-report-form-panel", schema, formData, () => {
        dcoeReportSetStatus("Unsaved changes", "saving");
        clearTimeout(dcoeReportSaveTimer);
        dcoeReportSaveTimer = setTimeout(() => dcoeReportSaveDraft(false), 900);
    });
}

function dcoeReportRenderPreview(html) {
    dcoeFormRenderPreview("#dcoe-report-preview", html);
}

function dcoeReportPopulateSelectors() {
    dcoeFormPopulateTemplateSelect("#dcoe-report-template-select", dcoeWorkspace.templates);

    const taskSelect = $("#dcoe-report-task-select");
    taskSelect.find("option:not(:first)").remove();
    dcoeWorkspace.tasks.forEach((task) => {
        const linked = (task.linked_drafts || []).length;
        const suffix = linked ? ` (${linked} report${linked > 1 ? "s" : ""})` : "";
        const keyAttr = task.report_template_key ? ` data-key="${task.report_template_key}"` : "";
        taskSelect.append(
            `<option value="${task.task_id}"${keyAttr}>#${task.task_id} — ${task.task_title}${suffix}</option>`
        );
    });
}

function dcoeReportRenderDraftList() {
    const list = $("#dcoe-report-list");
    list.empty();
    if (!dcoeWorkspace.drafts.length) {
        list.append('<p class="text-muted mb-0">No saved reports yet.</p>');
        return;
    }
    dcoeWorkspace.drafts.forEach((draft) => {
        const item = $(`
            <div class="dcoe-report-item ${draft.id === dcoeActiveDraftId ? "active" : ""}" data-draft-id="${draft.id}">
                <strong>${draft.title || "Report"}</strong>
                <small>${draft.status || "draft"} · ${(draft.updated_at || draft.created_at || "").slice(0, 10)}</small>
            </div>
        `);
        item.on("click", () => dcoeReportLoadDraft(draft.id));
        list.append(item);
    });
}

function dcoeReportTaskMatchesFilter(task) {
    const q = ($("#dcoe-ws-task-search").val() || "").toLowerCase().trim();
    if (q) {
        const hay = `#${task.task_id} ${task.task_title || ""} ${task.task_tags || ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
    }
    if (dcoeWsTaskFilter === "reports") {
        return !!(task.report_template_key || (task.task_tags || "").includes("tm-checklist-report"));
    }
    if (dcoeWsTaskFilter === "has_draft") {
        return (task.linked_drafts || []).length > 0;
    }
    if (dcoeWsTaskFilter === "needed") {
        return task.report_status === "needed"
            || !!(task.report_template_key && !(task.linked_drafts || []).length);
    }
    if (dcoeWsTaskFilter === "in_progress") {
        return task.report_status === "in_progress" || task.report_status === "draft";
    }
    return true;
}

function dcoeReportRenderTaskList() {
    const list = $("#dcoe-task-report-list");
    list.empty();
    const tasks = (dcoeWorkspace.tasks || []).filter(dcoeReportTaskMatchesFilter);
    if (!tasks.length) {
        list.append('<p class="text-muted mb-0">No tasks match this filter.</p>');
        return;
    }
    tasks.forEach((task) => {
        const statusText = typeof dcoeWorkspaceTaskStatusLabel === "function"
            ? dcoeWorkspaceTaskStatusLabel(task)
            : (task.report_template_key ? "Report needed" : "Optional");
        const statusBadge = typeof dcoeWorkspaceTaskStatusBadge === "function"
            ? dcoeWorkspaceTaskStatusBadge(task)
            : "";
        const item = $(`
            <div class="dcoe-task-report-item" data-task-id="${task.task_id}">
                <div class="d-flex justify-content-between align-items-start">
                    <strong>#${task.task_id} ${task.task_title || ""}</strong>
                    ${statusBadge}
                </div>
                <small class="text-muted d-block">${statusText}</small>
            </div>
        `);
        item.on("click", () => dcoeReportOpenTask(task.task_id));
        list.append(item);
    });
}

function dcoeReportOpenTask(taskId) {
    get_raw_request_api(`/case/dcoe/reports/tasks/${taskId}` + case_param()).done((response) => {
        if (response.status !== "success") {
            notify_error(response.message || "Unable to open task reports");
            return;
        }
        const data = response.data;
        $("#dcoe-report-task-select").val(String(taskId));
        if (data.reports && data.reports.length) {
            const draft = data.reports[0].draft;
            dcoeReportLoadDraft(draft.id);
            return;
        }
        if (data.suggested_template) {
            $("#dcoe-report-template-select").val(String(data.suggested_template.id));
            dcoeReportCreateDraft(taskId);
            return;
        }
        dcoeReportSetStatus("Pick report type → Start new report");
        notify_success("Select a report type above, then click Start new report");
        $("#dcoe-report-task-select").val(String(taskId));
    });
}

function dcoeReportEnableActions(enabled) {
    $("#dcoe-report-save, #dcoe-report-attach, #dcoe-report-download, #dcoe-report-delete").prop("disabled", !enabled);
}

function dcoeReportLoadDraft(draftId) {
    get_raw_request_api(`/case/dcoe/reports/drafts/${encodeURIComponent(draftId)}` + case_param()).done((response) => {
        if (response.status !== "success") {
            notify_error(response.message || "Unable to load report");
            return;
        }
        const draft = response.data.draft;
        dcoeActiveDraftId = draft.id;
        dcoeReportRenderForm(response.data.schema, draft.form_data || {});
        dcoeReportRenderPreview(response.data.preview_html);
        $("#dcoe-report-draft-title").text(draft.title || "Report");
        $("#dcoe-report-draft-meta").text(`${draft.report_template_name || ""} · ${draft.status || "draft"}`);
        if (draft.task_id) $("#dcoe-report-task-select").val(String(draft.task_id));
        dcoeReportEnableActions(true);
        dcoeReportUpdateDownloadButton("#dcoe-report-download", draft.id);
        dcoeReportRenderDraftList();
        dcoeReportSetStatus("Loaded");
    });
}

function dcoeReportLoadWorkspace(openDraftId, openTaskId, templateId) {
    dcoeReportSetStatus("Loading…", "saving");
    get_raw_request_api("/case/dcoe/reports/workspace" + case_param()).done((response) => {
        if (response.status !== "success") {
            dcoeReportSetStatus("Error", "error");
            notify_error(response.message || "Unable to load workspace");
            return;
        }
        dcoeWorkspace = response.data;
        dcoeReportPopulateSelectors();
        dcoeFormRenderHelpSteps("#dcoe-report-help", response.data.help_steps);
        dcoeReportRenderDraftList();
        dcoeReportRenderTaskList();
        if (typeof dcoeRefreshOpsBar === "function" && response.data.progress) {
            dcoeRefreshOpsBar({ progress: response.data.progress });
        }

        if (templateId) $("#dcoe-report-template-select").val(String(templateId));

        if (openDraftId) {
            dcoeReportLoadDraft(openDraftId);
        } else if (openTaskId) {
            dcoeReportOpenTask(openTaskId);
        } else if (templateId) {
            const existing = (dcoeWorkspace.drafts || []).find(
                (d) => String(d.report_template_id) === String(templateId)
            );
            if (existing) {
                dcoeReportLoadDraft(existing.id);
            } else {
                dcoeReportCreateDraft();
            }
        } else {
            dcoeReportSetStatus("Ready");
        }
    });
}

function dcoeReportCreateDraft(taskId) {
    const templateId = $("#dcoe-report-template-select").val();
    const selectedTaskId = taskId || $("#dcoe-report-task-select").val() || null;
    if (!templateId) {
        notify_error("Select a report type first");
        return;
    }
    dcoeReportSetStatus("Creating…", "saving");
    post_request_api(
        "/case/dcoe/reports/drafts",
        JSON.stringify({
            report_template_id: parseInt(templateId, 10),
            task_id: selectedTaskId ? parseInt(selectedTaskId, 10) : null,
            csrf_token: $("#csrf_token").val(),
        })
    ).done((response) => {
        if (response.status !== "success") {
            dcoeReportSetStatus("Error", "error");
            notify_error(response.message || "Unable to create report");
            return;
        }
        dcoeWorkspace.drafts = response.data.drafts || [];
        dcoeWorkspace.tasks = response.data.tasks || [];
        dcoeReportRenderDraftList();
        dcoeReportRenderTaskList();
        const draft = response.data.draft;
        dcoeActiveDraftId = draft.id;
        dcoeReportRenderForm(response.data.schema, draft.form_data || {});
        dcoeReportRenderPreview(response.data.preview_html);
        $("#dcoe-report-draft-title").text(draft.title || "Report");
        dcoeReportEnableActions(true);
        dcoeReportUpdateDownloadButton("#dcoe-report-download", draft.id);
        dcoeReportRenderDraftList();
        notify_success("Report started — fill in the sections");
    });
}

function dcoeReportStartForTask(taskId, templateKey) {
    $("#dcoe-report-task-select").val(String(taskId));
    const template = dcoeWorkspace.templates.find((row) => row.template_key === templateKey);
    if (template) $("#dcoe-report-template-select").val(String(template.id));
    const existing = (dcoeWorkspace.drafts || []).find((draft) => draft.task_id === taskId);
    if (existing) {
        dcoeReportLoadDraft(existing.id);
        return;
    }
    dcoeReportCreateDraft(taskId);
}

function dcoeReportSaveDraft(showToast) {
    if (!dcoeActiveDraftId) return;
    const formData = dcoeReportCollectFormData();
    dcoeReportSetStatus("Saving…", "saving");
    $.ajax({
        url: `/case/dcoe/reports/drafts/${encodeURIComponent(dcoeActiveDraftId)}` + case_param(),
        type: "PUT",
        contentType: "application/json",
        data: JSON.stringify({ form_data: formData, csrf_token: $("#csrf_token").val() }),
        success: (response) => {
            if (response.status === "success") {
                dcoeReportSetStatus("Saved", "saved");
                if (showToast) notify_success("Report saved");
                dcoeReportRenderPreview(response.data.preview_html);
                const idx = dcoeWorkspace.drafts.findIndex((d) => d.id === dcoeActiveDraftId);
                if (idx >= 0) dcoeWorkspace.drafts[idx] = response.data.draft;
                dcoeReportRenderDraftList();
            } else {
                dcoeReportSetStatus("Save failed", "error");
                notify_error(response.message || "Save failed");
            }
        },
        error: (jqXHR) => {
            dcoeReportSetStatus("Save failed", "error");
            ajax_notify_error(jqXHR, "save report");
        },
    });
}

function dcoeReportAttachToTask() {
    if (!dcoeActiveDraftId) return;
    const taskId = $("#dcoe-report-task-select").val();
    if (!taskId) {
        notify_error("Select a METL task to attach this report");
        return;
    }
    dcoeReportSaveDraft(false);
    post_request_api(
        `/case/dcoe/reports/drafts/${encodeURIComponent(dcoeActiveDraftId)}/attach`,
        JSON.stringify({ task_id: parseInt(taskId, 10), csrf_token: $("#csrf_token").val() })
    ).done((response) => {
        if (response.status === "success") {
            notify_success("Report attached to task");
            if (typeof get_tasks === "function") get_tasks();
            dcoeReportLoadWorkspace(dcoeActiveDraftId);
        } else {
            notify_error(response.message || "Attach failed");
        }
    });
}

function dcoeReportDownloadDraft() {
    if (!dcoeActiveDraftId) return;
    const formData = dcoeReportCollectFormData();
    dcoeReportSetStatus("Preparing export…", "saving");
    $.ajax({
        url: `/case/dcoe/reports/drafts/${encodeURIComponent(dcoeActiveDraftId)}` + case_param(),
        type: "PUT",
        contentType: "application/json",
        data: JSON.stringify({ form_data: formData, csrf_token: $("#csrf_token").val() }),
        success: (response) => {
            if (response.status === "success") {
                dcoeReportOpenDownload(dcoeActiveDraftId, "#dcoe-report-export-format");
                dcoeReportSetStatus("Export started", "saved");
                if (typeof dcoeShowExportGuidance === "function") dcoeShowExportGuidance();
            } else {
                notify_error(response.message || "Save failed before export");
            }
        },
        error: (jqXHR) => {
            dcoeReportSetStatus("Export failed", "error");
            ajax_notify_error(jqXHR, "export report");
        },
    });
}

function dcoeReportDeleteDraft() {
    if (!dcoeActiveDraftId) return;
    do_deletion_prompt("Delete this report draft?").then((confirmed) => {
        if (!confirmed) return;
        $.ajax({
            url: `/case/dcoe/reports/drafts/${encodeURIComponent(dcoeActiveDraftId)}` + case_param(),
            type: "DELETE",
            success: (response) => {
                if (response.status === "success") {
                    dcoeActiveDraftId = null;
                    dcoeReportEnableActions(false);
                    dcoeReportRenderForm(null, {});
                    dcoeReportRenderPreview("");
                    dcoeWorkspace = response.data;
                    dcoeReportRenderDraftList();
                    dcoeReportRenderTaskList();
                    notify_success("Report deleted");
                } else {
                    notify_error(response.message || "Delete failed");
                }
            },
        });
    });
}

function open_report_workspace() {
    let reportId = null;
    const picker = $("#select_report");
    if (picker.length) {
        try {
            if (typeof picker.selectpicker === "function") {
                reportId = picker.selectpicker("val");
            }
        } catch (e) { /* ignore */ }
        if (!reportId) {
            reportId = picker.val();
        }
    }

    let cid = null;
    if (typeof case_param === "function") {
        const match = case_param().match(/cid=(\d+)/);
        if (match) cid = match[1];
    }
    if (!cid) {
        const urlMatch = window.location.search.match(/[?&]cid=(\d+)/);
        if (urlMatch) cid = urlMatch[1];
    }

    let url = "/case/dcoe/reports";
    if (cid) url += "?cid=" + cid;
    if (reportId) url += (url.indexOf("?") >= 0 ? "&" : "?") + "template_id=" + reportId;
    window.location.href = url;
    return false;
}

$(document).ready(function () {
    dcoeReportPopulateExportFormats("#dcoe-report-export-format");
    const params = new URLSearchParams(window.location.search);
    dcoeReportLoadWorkspace(
        params.get("draft_id"),
        params.get("task_id"),
        params.get("template_id")
    );

    $("#dcoe-report-new-draft").on("click", () => dcoeReportCreateDraft());
    $("#dcoe-report-save").on("click", () => dcoeReportSaveDraft(true));
    $("#dcoe-report-attach").on("click", dcoeReportAttachToTask);
    $("#dcoe-report-download").on("click", dcoeReportDownloadDraft);
    $("#dcoe-report-delete").on("click", dcoeReportDeleteDraft);
    $("#dcoe-report-refresh").on("click", () => dcoeReportLoadWorkspace(dcoeActiveDraftId));
    $("#dcoe-report-task-select").on("change", function () {
        const key = $(this).find("option:selected").data("key");
        if (!key) return;
        const template = dcoeWorkspace.templates.find((row) => row.template_key === key);
        if (template) $("#dcoe-report-template-select").val(String(template.id));
    });
    $("#dcoe-ws-task-search").on("input", () => dcoeReportRenderTaskList());
    $(".dcoe-ws-task-filter").on("click", function () {
        dcoeWsTaskFilter = $(this).data("filter") || "all";
        $(".dcoe-ws-task-filter").removeClass("btn-primary").addClass("btn-outline-secondary");
        $(this).removeClass("btn-outline-secondary").addClass("btn-primary");
        dcoeReportRenderTaskList();
    });
});

/* OhCR/DCOE reports embedded in task modal — all tasks can have reports */

let dcoeTaskReportTaskId = null;
let dcoeTaskReportActiveDraftId = null;
let dcoeTaskReportSaveTimer = null;
let dcoeTaskReportData = { reports: [], templates: [], default_template_key: null };

function dcoeTaskReportSetStatus(text, kind) {
    const badge = $("#dcoe-task-report-status");
    badge.text(text);
    badge.removeClass("badge-warning badge-success badge-danger badge-light");
    if (kind === "saving") badge.addClass("badge-warning");
    else if (kind === "saved") badge.addClass("badge-success");
    else if (kind === "error") badge.addClass("badge-danger");
    else badge.addClass("badge-light");
}

function dcoeTaskReportHide() {
    $("#dcoe-task-report-panel").hide();
    dcoeTaskReportTaskId = null;
    dcoeTaskReportActiveDraftId = null;
    dcoeTaskReportData = { reports: [], templates: [], default_template_key: null };
    clearTimeout(dcoeTaskReportSaveTimer);
}

function dcoeTaskReportFindEntry(draftId) {
    return (dcoeTaskReportData.reports || []).find((row) => row.draft.id === draftId);
}

function dcoeTaskReportRenderTabs() {
    const tabs = $("#dcoe-task-report-tabs");
    tabs.empty();
    const reports = dcoeTaskReportData.reports || [];
    if (!reports.length) {
        tabs.append('<span class="text-muted small">No reports on this task yet.</span>');
        $("#dcoe-task-report-remove").prop("disabled", true);
        return;
    }

    reports.forEach((entry) => {
        const draft = entry.draft;
        const btn = $(`<button type="button" class="btn btn-sm mr-1 mb-1 dcoe-task-report-tab
            ${draft.id === dcoeTaskReportActiveDraftId ? "btn-primary" : "btn-outline-secondary"}"
            data-draft-id="${draft.id}">${draft.title || draft.report_template_name || "Report"}</button>`);
        btn.on("click", () => dcoeTaskReportSelectDraft(draft.id));
        tabs.append(btn);
    });
    $("#dcoe-task-report-remove").prop("disabled", !dcoeTaskReportActiveDraftId);
}

function dcoeTaskReportPopulateAddSelect() {
    dcoeFormPopulateTemplateSelect(
        "#dcoe-task-report-add-select",
        dcoeTaskReportData.templates,
        dcoeTaskReportData.default_template_key
    );
}

function dcoeTaskReportUpdateSuggestedButton() {
    const btn = $("#dcoe-task-report-suggested");
    const suggested = dcoeTaskReportData.suggested_template;
    if (suggested) {
        btn.show().off("click").on("click", () => {
            $("#dcoe-task-report-add-select").val(String(suggested.id));
            dcoeTaskReportAdd();
        }).html(`<i class="fa fa-magic"></i> Add suggested: ${suggested.name}`);
    } else {
        btn.hide();
    }
}

function dcoeTaskReportSelectDraft(draftId) {
    const entry = dcoeTaskReportFindEntry(draftId);
    if (!entry) return;
    dcoeTaskReportActiveDraftId = draftId;
    $("#dcoe-task-report-title").text(entry.draft.title || entry.draft.report_template_name || "Report");
    dcoeFormRender("#dcoe-task-report-form", entry.schema, entry.draft.form_data || {}, () => {
        dcoeTaskReportSetStatus("Unsaved changes", "saving");
        clearTimeout(dcoeTaskReportSaveTimer);
        dcoeTaskReportSaveTimer = setTimeout(() => dcoeTaskReportSave(false), 900);
    });
    dcoeFormRenderPreview("#dcoe-task-report-preview", entry.preview_html);
    dcoeReportUpdateDownloadButton("#dcoe-task-report-download", draftId);
    dcoeTaskReportRenderTabs();
    dcoeTaskReportSetStatus("Ready — auto-saves");
}

function dcoeTaskReportApplyPayload(data, preferredDraftId) {
    dcoeTaskReportData = data;
    dcoeTaskReportPopulateAddSelect();
    dcoeTaskReportUpdateSuggestedButton();
    dcoeFormRenderHelpSteps("#dcoe-task-report-help", data.help_steps);
    const ws = $("#dcoe-task-report-workspace");
    ws.attr("href", data.workspace_url || "#").removeAttr("target");

    const reports = data.reports || [];
    dcoeTaskReportRenderTabs();

    if (!reports.length) {
        dcoeTaskReportActiveDraftId = null;
        $("#dcoe-task-report-form").html(
            '<p class="text-muted mb-0">Choose a report type above and click <strong>Add report</strong>. No markdown needed — just fill in the boxes.</p>'
        );
        dcoeFormRenderPreview("#dcoe-task-report-preview", "");
        $("#dcoe-task-report-download").prop("disabled", true);
        $("#dcoe-task-report-export-format").prop("disabled", true);
        dcoeTaskReportSetStatus("Ready to add");
        return;
    }

    const activeId = preferredDraftId || dcoeTaskReportActiveDraftId || reports[0].draft.id;
    dcoeTaskReportSelectDraft(activeId);
}

function dcoeTaskReportExportAfterSave() {
    if (!dcoeTaskReportTaskId || !dcoeTaskReportActiveDraftId) return;
    const formData = dcoeFormCollect("#dcoe-task-report-form");
    dcoeTaskReportSetStatus("Preparing export…", "saving");
    $.ajax({
        url: `/case/dcoe/reports/tasks/${dcoeTaskReportTaskId}/drafts/${encodeURIComponent(dcoeTaskReportActiveDraftId)}` + case_param(),
        type: "PUT",
        contentType: "application/json",
        data: JSON.stringify({ form_data: formData, csrf_token: $("#csrf_token").val() }),
        success: (response) => {
            if (response.status === "success") {
                dcoeReportOpenDownload(dcoeTaskReportActiveDraftId, "#dcoe-task-report-export-format");
                dcoeTaskReportSetStatus("Export started", "saved");
                if (typeof dcoeShowExportGuidance === "function") dcoeShowExportGuidance();
            } else {
                notify_error(response.message || "Save failed before export");
            }
        },
        error: (jqXHR) => ajax_notify_error(jqXHR, "export report"),
    });
}

function dcoeTaskReportSave(showToast) {
    if (!dcoeTaskReportTaskId || !dcoeTaskReportActiveDraftId) return;
    const formData = dcoeFormCollect("#dcoe-task-report-form");
    dcoeTaskReportSetStatus("Saving…", "saving");
    $.ajax({
        url: `/case/dcoe/reports/tasks/${dcoeTaskReportTaskId}/drafts/${encodeURIComponent(dcoeTaskReportActiveDraftId)}` + case_param(),
        type: "PUT",
        contentType: "application/json",
        data: JSON.stringify({ form_data: formData, csrf_token: $("#csrf_token").val() }),
        success: (response) => {
            if (response.status === "success") {
                const entry = dcoeTaskReportFindEntry(dcoeTaskReportActiveDraftId);
                if (entry) {
                    entry.draft = response.data.draft;
                    entry.preview_html = response.data.preview_html;
                }
                dcoeTaskReportSetStatus("Saved", "saved");
                dcoeFormRenderPreview("#dcoe-task-report-preview", response.data.preview_html);
                if (showToast) notify_success("Report saved");
                if (typeof get_tasks === "function") get_tasks();
            } else {
                dcoeTaskReportSetStatus("Save failed", "error");
                notify_error(response.message || "Save failed");
            }
        },
        error: (jqXHR) => {
            dcoeTaskReportSetStatus("Save failed", "error");
            ajax_notify_error(jqXHR, "save task report");
        },
    });
}

function dcoeTaskReportAdd() {
    if (!dcoeTaskReportTaskId) return;
    const templateId = $("#dcoe-task-report-add-select").val();
    if (!templateId) {
        notify_error("Select a report type first");
        return;
    }
    dcoeTaskReportSetStatus("Adding…", "saving");
    post_request_api(
        `/case/dcoe/reports/tasks/${dcoeTaskReportTaskId}/drafts`,
        JSON.stringify({
            report_template_id: parseInt(templateId, 10),
            csrf_token: $("#csrf_token").val(),
        }),
        true
    ).done((response) => {
        if (response.status !== "success") {
            dcoeTaskReportSetStatus("Error", "error");
            notify_error(response.message || "Unable to add report");
            return;
        }
        dcoeTaskReportApplyPayload(response.data, response.data.active_draft_id);
        notify_success("Report added — fill in the sections below");
    });
}

function dcoeTaskReportRemove() {
    if (!dcoeTaskReportTaskId || !dcoeTaskReportActiveDraftId) return;
    do_deletion_prompt("Remove this report from the task?").then((confirmed) => {
        if (!confirmed) return;
        $.ajax({
            url: `/case/dcoe/reports/tasks/${dcoeTaskReportTaskId}/drafts/${encodeURIComponent(dcoeTaskReportActiveDraftId)}` + case_param(),
            type: "DELETE",
            success: (response) => {
                if (response.status === "success") {
                    dcoeTaskReportActiveDraftId = null;
                    dcoeTaskReportApplyPayload(response.data);
                    notify_success("Report removed");
                } else {
                    notify_error(response.message || "Remove failed");
                }
            },
            error: (jqXHR) => ajax_notify_error(jqXHR, "remove task report"),
        });
    });
}

function dcoeTaskReportLoad(taskId) {
    if (!taskId) {
        dcoeTaskReportHide();
        return;
    }

    dcoeTaskReportTaskId = taskId;
    dcoeTaskReportSetStatus("Loading…", "saving");
    $("#dcoe-task-report-panel").show();
    dcoeReportPopulateExportFormats("#dcoe-task-report-export-format");

    get_raw_request_api(`/case/dcoe/reports/tasks/${taskId}` + case_param()).done((response) => {
        if (response.status !== "success") {
            dcoeTaskReportSetStatus("Unavailable", "error");
            $("#dcoe-task-report-form").html(
                `<p class="text-muted mb-0">${response.message || "Reports unavailable."}</p>`
            );
            return;
        }
        dcoeTaskReportApplyPayload(response.data);
        const hasReports = (response.data.reports || []).length > 0;
        const isReportMop = !!response.data.default_template_key;
        if (hasReports || isReportMop) {
            $("#dcoe-toggle-task-desc").show();
            if (hasReports || isReportMop) {
                $(".md_description_field").hide();
                $("#dcoe-toggle-task-desc").text("Show task description");
            }
            const panel = document.getElementById("dcoe-task-report-panel");
            if (panel) {
                panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
            }
        }
    });
}

$(document).on("click", "#dcoe-toggle-task-desc", function () {
    const visible = $(".md_description_field").is(":visible");
    $(".md_description_field").toggle(!visible);
    $(this).text(visible ? "Show task description" : "Hide description — focus on report");
});

function dcoeTaskReportInitHandlers() {
    // Modal content is loaded dynamically — use delegation so buttons always work
    $(document).off("click.dcoeTaskReport", "#dcoe-task-report-add").on("click.dcoeTaskReport", "#dcoe-task-report-add", (e) => {
        e.preventDefault();
        dcoeTaskReportAdd();
    });
    $(document).off("click.dcoeTaskReport", "#dcoe-task-report-remove").on("click.dcoeTaskReport", "#dcoe-task-report-remove", (e) => {
        e.preventDefault();
        dcoeTaskReportRemove();
    });
    $(document).off("click.dcoeTaskReport", "#dcoe-task-report-download").on("click.dcoeTaskReport", "#dcoe-task-report-download", (e) => {
        e.preventDefault();
        if (!dcoeTaskReportActiveDraftId) return;
        dcoeTaskReportExportAfterSave();
    });
}

$(document).ready(function () {
    dcoeTaskReportInitHandlers();
    dcoeReportPopulateExportFormats("#dcoe-task-report-export-format");
});

/* OhCR/DCOE shared operational UX — filters, guidance, team context */

let dcoeActiveTaskTagFilter = "";
let dcoeActiveTaskTagRegex = false;
let dcoeActiveReportStatusFilter = "";
let dcoeActiveFilterChipId = "all";

const DCOE_TASK_TAG_COLUMN = 6;
const DCOE_TASK_STATUS_COLUMN = 5;

function dcoeReportStatusBadge(row) {
    const count = row.dcoe_report_count || 0;
    const status = row.dcoe_report_status || "optional";
    const labels = {
        needed: '<span class="badge badge-warning">Report needed</span>',
        draft: '<span class="badge badge-secondary">Draft</span>',
        in_progress: '<span class="badge badge-info">In progress</span>',
        attached: '<span class="badge badge-success">Complete</span>',
        optional: count
            ? `<span class="badge badge-light">${count} report(s)</span>`
            : '<span class="badge badge-light">—</span>',
    };
    return labels[status] || labels.optional;
}

function dcoeWorkspaceTaskStatusLabel(task) {
    const status = task.report_status || "optional";
    const linked = (task.linked_drafts || []).length;
    const labels = {
        needed: "Report needed — click to start",
        draft: `${linked} draft — continue filling in`,
        in_progress: `${linked} in progress`,
        attached: `${linked} complete`,
        optional: linked ? `${linked} optional report(s)` : "Optional — add reports",
    };
    return labels[status] || labels.optional;
}

function dcoeWorkspaceTaskStatusBadge(task) {
    const status = task.report_status || "optional";
    const badges = {
        needed: '<span class="badge badge-warning badge-sm">Needed</span>',
        draft: '<span class="badge badge-secondary badge-sm">Draft</span>',
        in_progress: '<span class="badge badge-info badge-sm">In progress</span>',
        attached: '<span class="badge badge-success badge-sm">Complete</span>',
        optional: "",
    };
    return badges[status] || "";
}

function dcoeTaskActionButtons(row) {
    const cid = typeof case_param === "function" ? case_param().match(/cid=(\d+)/) : null;
    const caseId = cid ? cid[1] : "";
    let html = "";
    if (row.dcoe_is_report_task || row.dcoe_report_count) {
        html += ` <a href="javascript:void(0);" onclick="edit_task(${row.task_id});return false;" class="btn btn-xs btn-outline-primary py-0" title="Fill in report">Reports</a>`;
        if (caseId) {
            html += ` <a href="/case/dcoe/reports?cid=${caseId}&task_id=${row.task_id}" class="btn btn-xs btn-outline-info py-0" title="Open in workspace">Workspace</a>`;
        }
    } else {
        html += ` <a href="javascript:void(0);" onclick="edit_task(${row.task_id});return false;" class="btn btn-xs btn-light py-0" title="Add optional report">+ Report</a>`;
    }
    return html;
}

function dcoeShowExportGuidance() {
    notify_success(
        "Export ready. Evidence link saved on the task. Mark the task Done when NETO has received their copy."
    );
    if (typeof get_tasks === "function") {
        get_tasks();
    }
}

function dcoeHighlightFilterChip(chipId) {
    dcoeActiveFilterChipId = chipId || "all";
    $(".dcoe-task-filter-chip").removeClass("btn-primary").addClass("btn-outline-secondary");
    if (chipId && chipId !== "all") {
        $(`.dcoe-task-filter-chip[data-chip-id="${chipId}"]`)
            .removeClass("btn-outline-secondary")
            .addClass("btn-primary");
    } else {
        $('.dcoe-task-filter-chip[data-chip-id="all"]')
            .removeClass("btn-outline-secondary")
            .addClass("btn-primary");
    }
}

function dcoeApplyTaskTableFilter(tag, chipId, options) {
    if (typeof Table === "undefined" || !Table) return;
    const opts = options || {};
    dcoeActiveTaskTagFilter = tag || "";
    dcoeActiveTaskTagRegex = !!opts.regex;
    dcoeActiveReportStatusFilter = "";
    dcoeHighlightFilterChip(chipId || (tag ? null : "all"));
    Table.column(DCOE_TASK_TAG_COLUMN).search(dcoeActiveTaskTagFilter, dcoeActiveTaskTagRegex, false);
    Table.column(DCOE_TASK_STATUS_COLUMN).search("");
    Table.draw();
}

function dcoeApplyTaskStatusFilter(statusPattern, chipId) {
    if (typeof Table === "undefined" || !Table) return;
    dcoeActiveTaskTagFilter = "";
    dcoeActiveTaskTagRegex = false;
    dcoeActiveReportStatusFilter = statusPattern || "";
    dcoeHighlightFilterChip(chipId);
    Table.column(DCOE_TASK_TAG_COLUMN).search("", false, false);
    Table.column(DCOE_TASK_STATUS_COLUMN).search(dcoeActiveReportStatusFilter, true, false);
    Table.draw();
}

function dcoeClearTaskFilters() {
    dcoeApplyTaskTableFilter("", "all");
}

function dcoeRefreshOpsBar(ops) {
    if (!ops || !$("#dcoe-ops-bar").length) return;

    if (ops.role_title) {
        $("#dcoe-ops-role-title").text(ops.role_title);
    }
    if (ops.progress) {
        const p = ops.progress;
        $("#dcoe-ops-progress-needed").text(p.needed || 0);
        $("#dcoe-ops-progress-filled").text(p.filled || 0);
        $("#dcoe-ops-progress-attached").text(p.attached || 0);
        $("#dcoe-ops-progress-inprogress").text(p.in_progress || 0);
        if (p.network_coverage_pct != null) {
            $("#dcoe-ops-progress-network").text(p.network_coverage_pct);
        }
    }
    if (ops.workflow_tips && ops.workflow_tips.length) {
        $("#dcoe-ops-workflow").text(ops.workflow_tips.join(" → "));
    }
}

function dcoeInitTaskFilters() {
    dcoeHighlightFilterChip("all");
}

$(document).ready(function () {
    $(document).on("click", ".dcoe-task-filter-chip:not(:disabled)", function () {
        const chipId = $(this).data("chip-id");
        const filterType = $(this).data("filter") || "tag";
        if (filterType === "status") {
            dcoeApplyTaskStatusFilter($(this).data("status") || "", chipId);
            return;
        }
        dcoeApplyTaskTableFilter($(this).data("tag") || "", chipId, {
            regex: !!$(this).data("regex"),
        });
    });
    $(document).on("click", "#dcoe-task-filter-clear", function () {
        dcoeClearTaskFilters();
    });
    if ($("#dcoe-task-filters").length) {
        dcoeInitTaskFilters();
    }
});

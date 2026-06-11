/* Shared OhCR/DCOE fillable report form helpers */

function dcoeFormEmptyInstance(section) {
    const instance = {};
    (section.fields || []).forEach((field) => {
        instance[field.id] = field.type === "checkbox" ? false : "";
    });
    return instance;
}

function dcoeFormSectionInstances(formData, section) {
    const sections = (formData && formData._sections) || {};
    const instances = sections[section.id];
    if (Array.isArray(instances) && instances.length) {
        return instances;
    }
    return [dcoeFormEmptyInstance(section)];
}

function dcoeFormFieldInput(field, value, attrs) {
    const uid = [
        attrs.panelKey,
        attrs.sectionId || "s",
        attrs.instanceIndex != null ? attrs.instanceIndex : "x",
        field.id,
    ].join("-");
    let input;

    if (field.type === "textarea") {
        input = $(`<textarea class="form-control form-control-sm" rows="${field.rows || 3}"></textarea>`);
        input.val(value || "");
    } else if (field.type === "select") {
        input = $('<select class="form-control form-control-sm"></select>');
        input.append('<option value="">— Select —</option>');
        (field.options || []).forEach((opt) => {
            input.append(`<option value="${opt}">${opt}</option>`);
        });
        input.val(value || "");
    } else if (field.type === "checkbox") {
        input = $(`<div class="custom-control custom-checkbox">
            <input type="checkbox" class="custom-control-input" id="fld-${uid}">
            <label class="custom-control-label" for="fld-${uid}">${field.label}</label>
        </div>`);
        input.find("input").prop("checked", !!value);
        return input.find("input")
            .attr("data-field-id", field.id)
            .attr("data-field-type", "checkbox")
            .attr("data-section-id", attrs.sectionId || "")
            .attr("data-instance-index", attrs.instanceIndex != null ? attrs.instanceIndex : "")
            .closest(".custom-control");
    } else {
        input = $('<input type="text" class="form-control form-control-sm" />');
        input.val(value || "");
        if (field.placeholder) input.attr("placeholder", field.placeholder);
    }

    input.attr("data-field-id", field.id);
    input.attr("data-field-type", field.type || "text");
    if (attrs.sectionId) input.attr("data-section-id", attrs.sectionId);
    if (attrs.instanceIndex != null) input.attr("data-instance-index", attrs.instanceIndex);
    return input;
}

function dcoeFormCollect(panelSelector) {
    const data = { _sections: {} };
    $(panelSelector).find("[data-field-id]").each(function () {
        const fieldId = $(this).data("field-id");
        const type = $(this).data("field-type");
        const sectionId = $(this).data("section-id");
        const instanceIndex = $(this).data("instance-index");
        let value;
        if (type === "checkbox") {
            value = $(this).is(":checked");
        } else {
            value = $(this).val();
        }

        if (sectionId !== undefined && sectionId !== "" && instanceIndex !== undefined && instanceIndex !== "") {
            const idx = parseInt(instanceIndex, 10);
            if (!data._sections[sectionId]) data._sections[sectionId] = [];
            while (data._sections[sectionId].length <= idx) {
                data._sections[sectionId].push({});
            }
            data._sections[sectionId][idx][fieldId] = value;
        } else {
            data[fieldId] = value;
        }
    });
    return data;
}

function dcoeFormRenderInstanceFields(section, instanceData, instanceIndex, panelKey, block) {
    const attrs = { panelKey, sectionId: section.id, instanceIndex };
    (section.fields || []).forEach((field) => {
        const wrap = $('<div class="dcoe-form-field"></div>');
        if (field.type !== "checkbox") {
            wrap.append(`<label>${field.label}</label>`);
        }
        wrap.append(dcoeFormFieldInput(field, instanceData[field.id], attrs));
        block.append(wrap);
    });
}

function dcoeFormRender(panelSelector, schema, formData, onChange) {
    const panel = $(panelSelector);
    const panelKey = panelSelector.replace(/[^a-z0-9]/gi, "") || "form";
    panel.empty();
    if (!schema || !schema.sections) {
        panel.html('<p class="text-muted mb-0">No form available for this report.</p>');
        return;
    }

    if (schema.warning) {
        panel.append(`<div class="alert alert-warning py-2 mb-3">${schema.warning}</div>`);
    }

    const triggerChange = () => {
        if (typeof onChange === "function") onChange();
    };

    schema.sections.forEach((section) => {
        const block = $(`<div class="dcoe-form-section" data-section-block="${section.id}"></div>`);
        const header = $(`<div class="d-flex align-items-center mb-2"><h5 class="mb-0">${section.label}</h5></div>`);
        block.append(header);

        if (section.repeatable) {
            const minInstances = Math.max(1, section.min_instances || 1);
            const instancesWrap = $(`<div class="dcoe-repeatable-instances" data-repeatable-section="${section.id}"></div>`);
            const instances = dcoeFormSectionInstances(formData, section);

            instances.forEach((instanceData, idx) => {
                const instBlock = $(`<div class="dcoe-repeatable-instance border rounded p-2 mb-2" data-instance-index="${idx}"></div>`);
                const instHeader = $(`<div class="d-flex align-items-center mb-2">
                    <small class="text-muted font-weight-bold">${section.label} #${idx + 1}</small>
                </div>`);
                if (instances.length > minInstances) {
                    instHeader.append(
                        `<button type="button" class="btn btn-xs btn-outline-danger ml-auto py-0 dcoe-remove-instance"
                            data-section-id="${section.id}" data-instance-index="${idx}" title="Remove">
                            <i class="fa fa-times"></i>
                        </button>`
                    );
                }
                instBlock.append(instHeader);
                dcoeFormRenderInstanceFields(section, instanceData, idx, panelKey, instBlock);
                instancesWrap.append(instBlock);
            });

            const addBtn = $(`<button type="button" class="btn btn-xs btn-outline-primary dcoe-add-instance"
                data-section-id="${section.id}"><i class="fa fa-plus"></i> Add ${section.label}</button>`);
            block.append(instancesWrap);
            block.append(addBtn);
        } else {
            dcoeFormRenderInstanceFields(section, formData || {}, null, panelKey, block);
        }

        panel.append(block);
    });

    panel.find(".dcoe-add-instance").on("click", function () {
        const sectionId = $(this).data("section-id");
        const section = schema.sections.find((row) => row.id === sectionId);
        if (!section) return;
        const current = dcoeFormCollect(panelSelector);
        if (!current._sections) current._sections = {};
        if (!current._sections[sectionId]) current._sections[sectionId] = [];
        current._sections[sectionId].push(dcoeFormEmptyInstance(section));
        dcoeFormRender(panelSelector, schema, current, onChange);
        triggerChange();
    });

    panel.find(".dcoe-remove-instance").on("click", function () {
        const sectionId = $(this).data("section-id");
        const removeIdx = parseInt($(this).data("instance-index"), 10);
        const section = schema.sections.find((row) => row.id === sectionId);
        if (!section) return;
        const minInstances = Math.max(1, section.min_instances || 1);
        const current = dcoeFormCollect(panelSelector);
        const instances = (current._sections && current._sections[sectionId]) || [];
        if (instances.length <= minInstances) return;
        instances.splice(removeIdx, 1);
        current._sections[sectionId] = instances;
        dcoeFormRender(panelSelector, schema, current, onChange);
        triggerChange();
    });

    panel.find("input, textarea, select").on("input change", triggerChange);
}

function dcoeFormRenderPreview(previewSelector, html) {
    $(previewSelector).html(html || '<p class="text-muted mb-0">Preview will appear here.</p>');
}

function dcoeTaskHasReportTemplate(tags) {
    if (!tags) return false;
    return tags.split(",").some((tag) => tag.trim().startsWith("report-template-"));
}

function dcoeTaskDefaultTemplateKey(tags) {
    if (!tags) return null;
    for (const tag of tags.split(",")) {
        const trimmed = tag.trim();
        if (trimmed.startsWith("report-template-")) {
            return trimmed.replace("report-template-", "");
        }
    }
    return null;
}

function dcoeFormPopulateTemplateSelect(selectSelector, templates, preferredKey) {
    const select = $(selectSelector);
    select.empty();
    const grouped = {};
    (templates || []).forEach((template) => {
        const label = template.category_label || "Reports";
        if (!grouped[label]) grouped[label] = [];
        grouped[label].push(template);
    });

    Object.keys(grouped).sort().forEach((categoryLabel) => {
        const group = $(`<optgroup label="${categoryLabel}"></optgroup>`);
        grouped[categoryLabel].forEach((template) => {
            const hint = template.description ? ` — ${template.description}` : "";
            group.append(
                `<option value="${template.id}" data-key="${template.template_key || ""}" title="${template.description || ""}">${template.name}${hint.length > 60 ? "" : hint}</option>`
            );
        });
        select.append(group);
    });

    if (preferredKey) {
        const match = (templates || []).find((row) => row.template_key === preferredKey);
        if (match) select.val(String(match.id));
    } else if (templates && templates.length) {
        select.val(String(templates[0].id));
    }
}

const DCOE_EXPORT_FORMATS = [
    { id: "docx", label: "Word (.docx) — for NETO" },
    { id: "html", label: "Web page (.html) — print to PDF" },
    { id: "md", label: "Markdown (.md)" },
    { id: "txt", label: "Plain text (.txt) — for email" },
];

function dcoeReportPopulateExportFormats(selectSelector) {
    const select = $(selectSelector);
    if (!select.length) return;
    select.empty();
    DCOE_EXPORT_FORMATS.forEach((fmt) => {
        select.append(`<option value="${fmt.id}">${fmt.label}</option>`);
    });
}

function dcoeReportOpenDownload(draftId, formatSelector) {
    const format = $(formatSelector).val() || "docx";
    const url = `/case/dcoe/reports/drafts/${encodeURIComponent(draftId)}/download` + case_param() + `&format=${format}`;
    window.open(url, "_blank");
}

function dcoeReportUpdateDownloadButton(buttonSelector, draftId) {
    $(buttonSelector).prop("disabled", !draftId);
    $("#dcoe-task-report-export-format, #dcoe-report-export-format").prop("disabled", !draftId);
}

function dcoeFormRenderHelpSteps(containerSelector, steps) {
    const container = $(containerSelector);
    container.empty();
    if (!steps || !steps.length) {
        container.hide();
        return;
    }
    const list = $('<ol class="mb-0 pl-3 small"></ol>');
    steps.forEach((step) => list.append(`<li>${step}</li>`));
    container.append(list).show();
}

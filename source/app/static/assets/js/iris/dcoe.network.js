/* OhCR/DCOE interactive network topology */

const DCOE_ZONE_COLORS = {
    perimeter: "#ff7f7f",
    dmz: "#ffd700",
    internal: "#97C2FC",
    server: "#7be141",
    endpoint: "#cdaaff",
    cloud: "#87ceeb",
    unknown: "#cccccc",
};

let dcoeTopology = { nodes: [], edges: [] };
let dcoeAssets = [];
let dcoeIocs = [];
let dcoeNetwork = null;
let dcoeSelected = { kind: null, id: null };
let dcoeDragAssetId = null;

function dcoeNewId(prefix) {
    return `${prefix}-${Math.random().toString(16).slice(2, 10)}`;
}

function dcoeAssetsById() {
    const map = {};
    dcoeAssets.forEach((asset) => { map[asset.asset_id] = asset; });
    return map;
}

function dcoeLoadNetwork() {
    get_raw_request_api("/case/dcoe/network/data" + case_param())
        .done((response) => {
            if (response.status !== "success") {
                notify_error(response.message || "Unable to load network topology");
                return;
            }
            dcoeTopology = response.data.topology || { nodes: [], edges: [] };
            dcoeAssets = response.data.assets || [];
            dcoeIocs = response.data.iocs || [];
            dcoePopulateAssetPalette();
            dcoePopulateAssetSelects();
            dcoePopulateIocPicker();
            dcoeRenderNetwork(response.data.vis);
            $("#dcoe-open-iocs").attr("href", "/case/ioc" + case_param());
        });
}

function dcoePopulateAssetPalette() {
    const list = $("#dcoe-asset-list");
    list.empty();
    dcoeAssets.forEach((asset) => {
        const onDiagram = dcoeTopology.nodes.some((node) => node.asset_id === asset.asset_id);
        const chip = $(`
            <div class="dcoe-asset-chip" draggable="true" data-asset-id="${asset.asset_id}">
                <strong>${asset.asset_name || "Asset"}</strong>
                <small>${asset.asset_ip || "no IP"} · ${asset.asset_type || "type unknown"}</small>
                <small>${onDiagram ? "On diagram" : "Not placed"}</small>
                <button type="button" class="btn btn-xs btn-link p-0 dcoe-place-asset">Place on diagram</button>
            </div>
        `);
        chip.on("dragstart", (event) => {
            dcoeDragAssetId = asset.asset_id;
            event.originalEvent.dataTransfer.setData("text/plain", String(asset.asset_id));
        });
        chip.find(".dcoe-place-asset").on("click", () => dcoePlaceAsset(asset.asset_id));
        list.append(chip);
    });
}

function dcoePopulateAssetSelects() {
    const assetSelect = $("#dcoe-node-asset");
    const edgeFrom = $("#dcoe-edge-from");
    const edgeTo = $("#dcoe-edge-to");
    assetSelect.find("option:not(:first)").remove();
    edgeFrom.empty();
    edgeTo.empty();

    dcoeTopology.nodes.forEach((node) => {
        edgeFrom.append(`<option value="${node.id}">${node.label}</option>`);
        edgeTo.append(`<option value="${node.id}">${node.label}</option>`);
    });

    dcoeAssets.forEach((asset) => {
        const label = `${asset.asset_name || "Asset"} (${asset.asset_ip || asset.asset_id})`;
        assetSelect.append(`<option value="${asset.asset_id}">${label}</option>`);
    });
}

function dcoePopulateIocPicker() {
    const picker = $("#dcoe-ioc-picker");
    picker.find("option:not(:first)").remove();
    dcoeIocs.forEach((ioc) => {
        picker.append(`<option value="${ioc.ioc_id}">${ioc.ioc_value} (${ioc.ioc_type || "IOC"})</option>`);
    });
}

function dcoeRenderNetwork(visData) {
    const container = document.getElementById("dcoe-network-container");
    const data = {
        nodes: new vis.DataSet(visData.nodes || []),
        edges: new vis.DataSet(visData.edges || []),
    };

    const options = {
        nodes: {
            shape: "box",
            margin: 12,
            font: { multi: true, size: 12 },
            borderWidth: 2,
        },
        edges: {
            smooth: { type: "dynamic" },
            font: { align: "middle", size: 11 },
            color: { color: "#5c6bc0" },
        },
        physics: { enabled: false },
        interaction: {
            dragNodes: true,
            dragView: true,
            navigationButtons: true,
            hover: true,
            multiselect: false,
        },
    };

    dcoeNetwork = new vis.Network(container, data, options);

    dcoeNetwork.on("click", (params) => {
        if (params.nodes.length) {
            dcoeSelectItem("node", params.nodes[0]);
        } else if (params.edges.length) {
            dcoeSelectItem("edge", params.edges[0]);
        } else {
            dcoeClearSelection();
        }
    });

    dcoeNetwork.on("dragEnd", (params) => {
        params.nodes.forEach((nodeId) => {
            const position = dcoeNetwork.getPositions([nodeId])[nodeId];
            const node = dcoeFindNode(nodeId);
            if (node && position) {
                node.x = position.x;
                node.y = position.y;
            }
        });
    });

    container.addEventListener("dragover", (event) => {
        event.preventDefault();
        container.classList.add("dcoe-drop-active");
    });
    container.addEventListener("dragleave", () => container.classList.remove("dcoe-drop-active"));
    container.addEventListener("drop", (event) => {
        event.preventDefault();
        container.classList.remove("dcoe-drop-active");
        const assetId = parseInt(event.dataTransfer.getData("text/plain") || dcoeDragAssetId, 10);
        if (!assetId) {
            return;
        }
        const rect = container.getBoundingClientRect();
        const domPos = { x: event.clientX - rect.left, y: event.clientY - rect.top };
        const canvasPos = dcoeNetwork.DOMtoCanvas(domPos);
        dcoePlaceAsset(assetId, canvasPos.x, canvasPos.y);
    });
}

function dcoePlaceAsset(assetId, x, y) {
    const asset = dcoeAssets.find((entry) => entry.asset_id === assetId);
    if (!asset) {
        return;
    }
    const existing = dcoeTopology.nodes.find((node) => node.asset_id === assetId);
    if (existing) {
        notify_error("Asset already on diagram");
        dcoeSelectItem("node", existing.id);
        return;
    }
    const node = {
        id: `asset-${asset.asset_id}`,
        label: asset.asset_name || asset.asset_ip || `Asset ${asset.asset_id}`,
        group: "internal",
        color: DCOE_ZONE_COLORS.internal,
        asset_id: asset.asset_id,
        asset_uuid: asset.asset_uuid,
        asset_ip: asset.asset_ip,
        asset_type: asset.asset_type,
        services: (asset.linked_iocs && asset.linked_iocs.length) ? [] : [{ port: "", protocol: "tcp", service: asset.asset_type || "", state: "unknown" }],
        ioc_ids: (asset.linked_iocs || []).map((ioc) => ioc.ioc_id),
        x: x || 120 + dcoeTopology.nodes.length * 25,
        y: y || 120 + dcoeTopology.nodes.length * 25,
        comments: [],
    };
    dcoeTopology.nodes.push(node);
    dcoeSaveNetwork(true);
}

function dcoeFindNode(nodeId) {
    return dcoeTopology.nodes.find((entry) => entry.id === nodeId);
}

function dcoeFindEdge(edgeId) {
    return dcoeTopology.edges.find((entry) => entry.id === edgeId);
}

function dcoeSelectItem(kind, id) {
    dcoeSelected = { kind, id };
    $("#dcoe-panel-empty").hide();
    $("#dcoe-panel-content").show();

    if (kind === "node") {
        const node = dcoeFindNode(id);
        if (!node) {
            return;
        }
        $("#dcoe-panel-title").text(`Node: ${node.label}`);
        $("#dcoe-node-fields").show();
        $("#dcoe-edge-fields").hide();
        $("#dcoe-node-label").val(node.label || "");
        $("#dcoe-node-ip").val(node.asset_ip || "");
        $("#dcoe-node-zone").val(node.group || "unknown");
        $("#dcoe-node-asset").val(node.asset_id || "");
        $("#dcoe-push-asset-comment").toggle(!!node.asset_id);
        dcoeRenderServices(node.services || []);
        dcoeRenderNodeIocs(node);
        dcoeRenderComments(node.comments || []);
    } else {
        const edge = dcoeFindEdge(id);
        if (!edge) {
            return;
        }
        $("#dcoe-panel-title").text(`Connection: ${edge.label || edge.id}`);
        $("#dcoe-node-fields").hide();
        $("#dcoe-edge-fields").show();
        $("#dcoe-edge-label").val(edge.label || "");
        $("#dcoe-edge-protocol").val(edge.protocol || "");
        $("#dcoe-edge-port").val(edge.port || "");
        $("#dcoe-push-asset-comment").hide();
        dcoeRenderComments(edge.comments || []);
    }
}

function dcoeClearSelection() {
    dcoeSelected = { kind: null, id: null };
    $("#dcoe-panel-empty").show();
    $("#dcoe-panel-content").hide();
}

function dcoeRenderComments(comments) {
    const list = $("#dcoe-comments-list");
    list.empty();
    if (!comments.length) {
        list.append('<small class="text-muted">No comments yet.</small>');
        return;
    }
    comments.forEach((comment) => {
        list.append(
            `<div class="border rounded p-2 mb-2"><strong>${comment.author_name || comment.author || "User"}</strong>` +
            `<small class="text-muted d-block">${comment.created_at || ""}</small>${comment.text}</div>`
        );
    });
}

function dcoeRenderServices(services) {
    const list = $("#dcoe-services-list");
    list.empty();
    services.forEach((service, index) => {
        list.append(`
            <div class="dcoe-service-row" data-index="${index}">
                <input class="form-control form-control-sm" style="width:28%" placeholder="port" value="${service.port || ""}" data-field="port" />
                <input class="form-control form-control-sm" style="width:22%" placeholder="tcp" value="${service.protocol || "tcp"}" data-field="protocol" />
                <input class="form-control form-control-sm" style="width:30%" placeholder="service" value="${service.service || ""}" data-field="service" />
                <input class="form-control form-control-sm" style="width:20%" placeholder="state" value="${service.state || ""}" data-field="state" />
            </div>
        `);
    });
}

function dcoeReadServicesFromDom() {
    const services = [];
    $("#dcoe-services-list .dcoe-service-row").each(function () {
        const row = $(this);
        services.push({
            port: row.find('[data-field="port"]').val(),
            protocol: row.find('[data-field="protocol"]').val() || "tcp",
            service: row.find('[data-field="service"]').val(),
            state: row.find('[data-field="state"]').val() || "unknown",
        });
    });
    return services;
}

function dcoeRenderNodeIocs(node) {
    const list = $("#dcoe-ioc-list");
    list.empty();
    const asset = dcoeAssets.find((entry) => entry.asset_id === node.asset_id);
    const linked = [];
    (node.ioc_ids || []).forEach((iocId) => {
        const fromAsset = asset && (asset.linked_iocs || []).find((ioc) => ioc.ioc_id === iocId);
        const fromCase = dcoeIocs.find((ioc) => ioc.ioc_id === iocId);
        const ioc = fromAsset || fromCase;
        if (ioc) {
            linked.push(ioc);
            list.append(
                `<a class="dcoe-ioc-link" href="/case/ioc${case_param()}" target="_blank">` +
                `${ioc.ioc_value} (${ioc.ioc_type || "IOC"})</a>`
            );
        }
    });
    if (!linked.length) {
        list.append('<small class="text-muted">No IOCs linked.</small>');
    }
}

function dcoeApplyInspectorChanges() {
    if (!dcoeSelected.kind) {
        return;
    }
    if (dcoeSelected.kind === "node") {
        const node = dcoeFindNode(dcoeSelected.id);
        if (!node) {
            return;
        }
        node.label = $("#dcoe-node-label").val();
        node.asset_ip = $("#dcoe-node-ip").val();
        node.group = $("#dcoe-node-zone").val();
        node.color = DCOE_ZONE_COLORS[node.group] || DCOE_ZONE_COLORS.unknown;
        node.services = dcoeReadServicesFromDom();

        const assetId = $("#dcoe-node-asset").val();
        if (assetId) {
            const asset = dcoeAssets.find((entry) => String(entry.asset_id) === String(assetId));
            if (asset) {
                node.asset_id = asset.asset_id;
                node.asset_uuid = asset.asset_uuid;
                node.asset_ip = node.asset_ip || asset.asset_ip;
                node.asset_type = asset.asset_type;
                if (!node.ioc_ids || !node.ioc_ids.length) {
                    node.ioc_ids = (asset.linked_iocs || []).map((ioc) => ioc.ioc_id);
                }
            }
        }
    } else {
        const edge = dcoeFindEdge(dcoeSelected.id);
        if (edge) {
            edge.label = $("#dcoe-edge-label").val();
            edge.protocol = $("#dcoe-edge-protocol").val();
            edge.port = $("#dcoe-edge-port").val();
        }
    }
}

function dcoeAddComment(pushToAsset) {
    if (!dcoeSelected.kind) {
        return;
    }
    const text = $("#dcoe-comment-input").val().trim();
    if (!text) {
        return;
    }
    const comment = {
        id: dcoeNewId("comment"),
        author: "",
        author_name: "",
        text,
        created_at: new Date().toISOString(),
    };

    if (dcoeSelected.kind === "node") {
        const node = dcoeFindNode(dcoeSelected.id);
        node.comments = node.comments || [];
        node.comments.push(comment);
        if (pushToAsset && node.asset_id) {
            post_request_api(
                `/case/assets/${node.asset_id}/comments/add`,
                JSON.stringify({ comment_text: text, csrf_token: $("#csrf_token").val() })
            );
        }
    } else {
        const edge = dcoeFindEdge(dcoeSelected.id);
        edge.comments = edge.comments || [];
        edge.comments.push(comment);
    }

    $("#dcoe-comment-input").val("");
    dcoeApplyInspectorChanges();
    dcoeSaveNetwork(false);
}

function dcoeSaveNetwork(reload) {
    dcoeApplyInspectorChanges();
    $.ajax({
        url: "/case/dcoe/network/data" + case_param(),
        type: "PUT",
        contentType: "application/json",
        data: JSON.stringify({ topology: dcoeTopology, csrf_token: $("#csrf_token").val() }),
        success: (response) => {
            if (response.status === "success") {
                notify_success("Network topology saved");
                if (reload) {
                    dcoeLoadNetwork();
                } else {
                    dcoeTopology = response.data.topology;
                    dcoeRenderNetwork(response.data.vis);
                    dcoePopulateAssetPalette();
                    if (dcoeSelected.id) {
                        dcoeSelectItem(dcoeSelected.kind, dcoeSelected.id);
                    }
                }
            } else {
                notify_error(response.message || "Save failed");
            }
        },
        error: (jqXHR) => ajax_notify_error(jqXHR, "/case/dcoe/network/data"),
    });
}

function dcoeConnectEdge() {
    const from = $("#dcoe-edge-from").val();
    const to = $("#dcoe-edge-to").val();
    if (!from || !to || from === to) {
        notify_error("Select two different nodes");
        return;
    }
    dcoeTopology.edges.push({
        id: dcoeNewId("edge"),
        from,
        to,
        label: "",
        protocol: "tcp",
        port: "",
        comments: [],
    });
    dcoeSaveNetwork(true);
}

function dcoeDeleteSelection() {
    if (!dcoeSelected.kind) {
        return;
    }
    if (dcoeSelected.kind === "node") {
        dcoeTopology.nodes = dcoeTopology.nodes.filter((node) => node.id !== dcoeSelected.id);
        dcoeTopology.edges = dcoeTopology.edges.filter(
            (edge) => edge.from !== dcoeSelected.id && edge.to !== dcoeSelected.id
        );
    } else {
        dcoeTopology.edges = dcoeTopology.edges.filter((edge) => edge.id !== dcoeSelected.id);
    }
    dcoeClearSelection();
    dcoeSaveNetwork(true);
}

function dcoeImportAllAssets() {
    post_request_api(
        "/case/dcoe/network/import-assets",
        JSON.stringify({ csrf_token: $("#csrf_token").val() })
    ).done((response) => {
        if (response.status === "success") {
            notify_success("Imported all case assets");
            dcoeLoadNetwork();
        } else {
            notify_error(response.message || "Import failed");
        }
    });
}

function dcoeExportTopology() {
    get_raw_request_api("/case/dcoe/network/export" + case_param()).done((response) => {
        if (response.status !== "success") {
            notify_error(response.message || "Export failed");
            return;
        }
        const blob = new Blob([JSON.stringify(response.data, null, 2)], { type: "application/json" });
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = `dcoe-network-topology${case_param().replace("?", "-")}.json`;
        link.click();
    });
}

function dcoeImportTopologyFile(file) {
    const reader = new FileReader();
    reader.onload = (event) => {
        try {
            const payload = JSON.parse(event.target.result);
            post_request_api(
                "/case/dcoe/network/import",
                JSON.stringify({ ...payload, csrf_token: $("#csrf_token").val() })
            ).done((response) => {
                if (response.status === "success") {
                    notify_success("Topology imported");
                    dcoeLoadNetwork();
                } else {
                    notify_error(response.message || "Import failed");
                }
            });
        } catch (error) {
            notify_error("Invalid JSON file");
        }
    };
    reader.readAsText(file);
}

$(document).ready(function () {
    dcoeLoadNetwork();

    $("#dcoe-network-save").on("click", () => dcoeSaveNetwork(true));
    $("#dcoe-network-import-all").on("click", dcoeImportAllAssets);
    $("#dcoe-network-export").on("click", dcoeExportTopology);
    $("#dcoe-network-import-file").on("change", function () {
        if (this.files && this.files[0]) {
            dcoeImportTopologyFile(this.files[0]);
        }
    });
    $("#dcoe-connect-edge").on("click", dcoeConnectEdge);
    $("#dcoe-delete-selection").on("click", dcoeDeleteSelection);
    $("#dcoe-add-comment").on("click", () => dcoeAddComment(false));
    $("#dcoe-push-asset-comment").on("click", () => dcoeAddComment(true));
    $("#dcoe-add-service").on("click", () => {
        if (!dcoeSelected.kind || dcoeSelected.kind !== "node") {
            return;
        }
        const node = dcoeFindNode(dcoeSelected.id);
        node.services = node.services || [];
        node.services.push({ port: "", protocol: "tcp", service: "", state: "open" });
        dcoeRenderServices(node.services);
    });
    $("#dcoe-ioc-picker").on("change", function () {
        const iocId = parseInt($(this).val(), 10);
        if (!iocId || dcoeSelected.kind !== "node") {
            return;
        }
        const node = dcoeFindNode(dcoeSelected.id);
        node.ioc_ids = node.ioc_ids || [];
        if (!node.ioc_ids.includes(iocId)) {
            node.ioc_ids.push(iocId);
        }
        $(this).val("");
        dcoeSaveNetwork(false);
    });
    $("#dcoe-node-label, #dcoe-node-ip, #dcoe-node-zone, #dcoe-node-asset, #dcoe-edge-label, #dcoe-edge-protocol, #dcoe-edge-port")
        .on("change", () => { dcoeApplyInspectorChanges(); dcoeSaveNetwork(false); });
    $("#dcoe-services-list").on("change", "input", () => { dcoeApplyInspectorChanges(); dcoeSaveNetwork(false); });
});

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
let dcoeNetwork = null;
let dcoeSelected = { kind: null, id: null };

function dcoeNewId(prefix) {
    return `${prefix}-${Math.random().toString(16).slice(2, 10)}`;
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
            dcoePopulateAssetSelects();
            dcoeRenderNetwork(response.data.vis);
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

function dcoeRenderNetwork(visData) {
    const container = document.getElementById("dcoe-network-container");
    const data = {
        nodes: new vis.DataSet(visData.nodes || []),
        edges: new vis.DataSet(visData.edges || []),
    };

    const options = {
        nodes: {
            shape: "box",
            margin: 10,
            font: { multi: false },
        },
        edges: {
            smooth: { type: "continuous", roundness: 0.4 },
            font: { align: "middle" },
        },
        physics: {
            enabled: false,
        },
        interaction: {
            dragNodes: true,
            dragView: true,
            navigationButtons: true,
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
        if (!params.nodes.length) {
            return;
        }
        const nodeId = params.nodes[0];
        const position = dcoeNetwork.getPositions([nodeId])[nodeId];
        const node = dcoeTopology.nodes.find((entry) => entry.id === nodeId);
        if (node && position) {
            node.x = position.x;
            node.y = position.y;
        }
    });
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
        $("#dcoe-node-label").val(node.label || "");
        $("#dcoe-node-zone").val(node.group || "unknown");
        $("#dcoe-node-asset").val(node.asset_id || "");
        $("#dcoe-asset-link-group").toggle(!!node.asset_id);
        if (node.asset_id) {
            $("#dcoe-open-asset").attr("href", `/case/assets${case_param()}`);
        }
        $("#dcoe-push-asset-comment").toggle(!!node.asset_id);
        dcoeRenderComments(node.comments || []);
    } else {
        const edge = dcoeFindEdge(id);
        if (!edge) {
            return;
        }
        $("#dcoe-panel-title").text(`Edge: ${edge.label || edge.id}`);
        $("#dcoe-node-label").val(edge.label || "");
        $("#dcoe-node-zone").closest(".form-group").hide();
        $("#dcoe-node-asset").closest(".form-group").hide();
        $("#dcoe-asset-link-group").hide();
        $("#dcoe-push-asset-comment").hide();
        dcoeRenderComments(edge.comments || []);
    }
}

function dcoeClearSelection() {
    dcoeSelected = { kind: null, id: null };
    $("#dcoe-panel-empty").show();
    $("#dcoe-panel-content").hide();
    $("#dcoe-node-zone").closest(".form-group").show();
    $("#dcoe-node-asset").closest(".form-group").show();
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
            `<div class="border rounded p-2 mb-2"><strong>${comment.author_name || comment.author}</strong>` +
            `<small class="text-muted d-block">${comment.created_at || ""}</small>${comment.text}</div>`
        );
    });
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
        node.group = $("#dcoe-node-zone").val();
        node.color = DCOE_ZONE_COLORS[node.group] || DCOE_ZONE_COLORS.unknown;
        const assetId = $("#dcoe-node-asset").val();
        if (assetId) {
            const asset = dcoeAssets.find((entry) => String(entry.asset_id) === String(assetId));
            if (asset) {
                node.asset_id = asset.asset_id;
                node.asset_uuid = asset.asset_uuid;
                node.asset_ip = asset.asset_ip;
                node.asset_type = asset.asset_type;
                if (!node.label) {
                    node.label = asset.asset_name || `Asset ${asset.asset_id}`;
                }
            }
        } else {
            node.asset_id = null;
            node.asset_uuid = null;
            node.asset_ip = null;
            node.asset_type = null;
        }
    } else {
        const edge = dcoeFindEdge(dcoeSelected.id);
        if (edge) {
            edge.label = $("#dcoe-node-label").val();
        }
    }
    dcoeSaveNetwork(false);
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
    dcoeSaveNetwork(false);
}

function dcoeSaveNetwork(reload) {
    $.ajax({
        url: "/case/dcoe/network/data" + case_param(),
        type: "PUT",
        contentType: "application/json",
        data: JSON.stringify({
            topology: dcoeTopology,
            csrf_token: $("#csrf_token").val(),
        }),
        success: (response) => {
            if (response.status === "success") {
                notify_success("Network topology saved");
                if (reload) {
                    dcoeLoadNetwork();
                } else if (response.data && response.data.vis) {
                    dcoeRenderNetwork(response.data.vis);
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

function dcoeAddNode() {
    const label = prompt("Node label:", "New device");
    if (label === null) {
        return;
    }
    const node = {
        id: dcoeNewId("node"),
        label: label || "New device",
        group: "internal",
        color: DCOE_ZONE_COLORS.internal,
        x: 120 + dcoeTopology.nodes.length * 30,
        y: 120 + dcoeTopology.nodes.length * 20,
        comments: [],
    };
    dcoeTopology.nodes.push(node);
    dcoePopulateAssetSelects();
    dcoeSaveNetwork(true);
}

function dcoeAddEdge() {
    const from = $("#dcoe-edge-from").val();
    const to = $("#dcoe-edge-to").val();
    const label = $("#dcoe-edge-label").val();
    if (!from || !to || from === to) {
        notify_error("Select two different nodes for an edge");
        return;
    }
    dcoeTopology.edges.push({
        id: dcoeNewId("edge"),
        from,
        to,
        label: label || "",
        comments: [],
    });
    $("#dcoe-edge-label").val("");
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

function dcoeImportAssets() {
    post_request_api(
        "/case/dcoe/network/import-assets",
        JSON.stringify({ csrf_token: $("#csrf_token").val() })
    ).done((response) => {
        if (response.status === "success") {
            notify_success("Imported case assets into topology");
            dcoeLoadNetwork();
        } else {
            notify_error(response.message || "Import failed");
        }
    });
}

$(document).ready(function () {
    dcoeLoadNetwork();

    $("#dcoe-network-save").on("click", () => {
        dcoeApplyInspectorChanges();
        dcoeSaveNetwork(true);
    });
    $("#dcoe-network-import").on("click", dcoeImportAssets);
    $("#dcoe-network-add-node").on("click", dcoeAddNode);
    $("#dcoe-add-edge").on("click", dcoeAddEdge);
    $("#dcoe-delete-selection").on("click", dcoeDeleteSelection);
    $("#dcoe-add-comment").on("click", () => dcoeAddComment(false));
    $("#dcoe-push-asset-comment").on("click", () => dcoeAddComment(true));
    $("#dcoe-node-label, #dcoe-node-zone, #dcoe-node-asset").on("change", dcoeApplyInspectorChanges);
});

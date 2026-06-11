/* OhCR/DCOE interactive network topology — drag/drop, components, asset creation */

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
let dcoeAssetTypes = [];
let dcoeComponents = [];
let dcoeNetworkMeta = {
    coverage: {},
    current_user: {},
    zone_legend: [],
    service_presets: [],
    component_categories: [],
};
let dcoeAssetFilter = "all";
let dcoeComponentFilter = "all";
let dcoeNetwork = null;
let dcoeVisNodes = null;
let dcoeVisEdges = null;
let dcoeSelected = { kind: null, id: null };
let dcoeDragPayload = null;
let dcoeConnectMode = false;
let dcoeConnectSource = null;
let dcoeSaveTimer = null;
let dcoeSaving = false;

function dcoeNewId(prefix) {
    return `${prefix}-${Math.random().toString(16).slice(2, 10)}`;
}

function dcoeSetStatus(text, state) {
    const pill = $("#dcoe-save-status");
    pill.text(text);
    pill.removeClass("saving error");
    if (state) {
        pill.addClass(state);
    }
}

function dcoeScheduleSave(syncAssets) {
    dcoeSetStatus("Unsaved changes…", "saving");
    clearTimeout(dcoeSaveTimer);
    dcoeSaveTimer = setTimeout(() => dcoeSaveNetwork(false, !!syncAssets), 700);
}

function dcoeAssetsById() {
    const map = {};
    dcoeAssets.forEach((asset) => { map[asset.asset_id] = asset; });
    return map;
}

function dcoeFindNode(nodeId) {
    return dcoeTopology.nodes.find((entry) => entry.id === nodeId);
}

function dcoeFindEdge(edgeId) {
    return dcoeTopology.edges.find((entry) => entry.id === edgeId);
}

function dcoeGuessZone(assetType, assetTags) {
    const text = `${assetType || ""} ${assetTags || ""}`.toLowerCase();
    if (/firewall|\bfw\b|perimeter|router/.test(text)) return "perimeter";
    if (/dmz/.test(text)) return "dmz";
    if (/server|\bdc\b|domain/.test(text)) return "server";
    if (/workstation|endpoint|laptop|desktop/.test(text)) return "endpoint";
    if (/cloud/.test(text)) return "cloud";
    return "internal";
}

function dcoeApplyData(responseData) {
    dcoeTopology = responseData.topology || { nodes: [], edges: [] };
    dcoeAssets = responseData.assets || [];
    dcoeIocs = responseData.iocs || [];
    dcoeAssetTypes = responseData.asset_types || [];
    dcoeComponents = responseData.components || [];
    dcoeNetworkMeta.coverage = responseData.coverage || {};
    dcoeNetworkMeta.current_user = responseData.current_user || {};
    dcoeNetworkMeta.zone_legend = responseData.zone_legend || [];
    dcoeNetworkMeta.service_presets = responseData.service_presets || [];
    dcoeNetworkMeta.component_categories = responseData.component_categories || [];
}

function dcoeCompromiseBadge(asset) {
    if (!asset || asset.asset_compromise_status_id == null) return "";
    const id = asset.asset_compromise_status_id;
    if (id === 1) return '<span class="badge badge-danger">Compromised</span>';
    if (id === 2) return '<span class="badge badge-success">Clean</span>';
    if (id === 0) return '<span class="badge badge-warning">TBD</span>';
    return '<span class="badge badge-light">Unknown</span>';
}

function dcoePopulateComponentFilters() {
    const wrap = $("#dcoe-component-filters");
    wrap.empty();
    const cats = ["all"].concat(dcoeNetworkMeta.component_categories || []);
    cats.forEach((cat) => {
        const btn = $(`<button type="button" class="btn btn-xs btn-outline-secondary mr-1 mb-1 dcoe-component-filter" data-filter="${cat}">${cat === "all" ? "All" : cat}</button>`);
        if (cat === "all") btn.removeClass("btn-outline-secondary").addClass("btn-primary");
        wrap.append(btn);
    });
}

function dcoePopulateServicePresets() {
    const select = $("#dcoe-service-preset");
    select.find("option:not(:first)").remove();
    (dcoeNetworkMeta.service_presets || []).forEach((preset, index) => {
        select.append(`<option value="${index}">${preset.label}</option>`);
    });
}

function dcoeFocusNode(nodeId) {
    if (!dcoeNetwork || !nodeId) return;
    dcoeNetwork.selectNodes([nodeId]);
    dcoeNetwork.focus(nodeId, { scale: 1.1, animation: true });
}

function dcoeRenderCoverageDashboard() {
    const cov = dcoeNetworkMeta.coverage || {};
    const pct = cov.coverage_pct || 0;
    let pctLabel = `${pct}%`;
    if (cov.moe_met) {
        pctLabel += ' <span class="badge badge-success">MOE met</span>';
    }
    $("#dcoe-coverage-pct").html(pctLabel);
    $("#dcoe-coverage-counts").text(
        ` — ${cov.mapped_assets || 0} / ${cov.total_assets || 0} assets on map` +
        (cov.unmapped_assets ? ` · ${cov.unmapped_assets} unmapped` : "")
    );
    const fill = $("#dcoe-coverage-fill");
    fill.css("width", `${Math.min(pct, 100)}%`);
    fill.removeClass("warn low");
    if (pct < 50) fill.addClass("low");
    else if (pct < (cov.moe_target_pct || 95)) fill.addClass("warn");
    const updated = cov.updated_by
        ? `Last saved by ${cov.updated_by}${cov.updated_at ? " · " + (cov.updated_at || "").slice(0, 16).replace("T", " ") : ""}`
        : "Not saved yet";
    $("#dcoe-coverage-updated").text(updated);

    const legend = $("#dcoe-zone-legend");
    legend.empty();
    (dcoeNetworkMeta.zone_legend || []).forEach((zone) => {
        const count = (cov.zones || {})[zone.id] || 0;
        legend.append(
            `<span><span class="dcoe-zone-swatch" style="background:${zone.color}"></span>` +
            `${zone.label}${count ? ` (${count})` : ""}</span>`
        );
    });

    const unmappedCount = cov.unmapped_assets || 0;
    $("#dcoe-unmapped-count").text(unmappedCount);

    const banner = $("#dcoe-unmapped-banner");
    const unmapped = $("#dcoe-unmapped-list");
    unmapped.empty();
    const list = cov.unmapped_list || [];
    if (!unmappedCount || !list.length) {
        banner.hide();
    } else {
        banner.show();
        list.forEach((asset) => {
            unmapped.append(`
                <div class="dcoe-unmapped-item">
                    <span>${asset.asset_name}${asset.asset_ip ? " · " + asset.asset_ip : ""}</span>
                    <button type="button" class="btn btn-xs btn-outline-primary dcoe-place-unmapped" data-asset-id="${asset.asset_id}">Place</button>
                </div>
            `);
        });
    }
}

function dcoeRefreshNetworkMeta(responseData) {
    dcoeApplyData(responseData);
    dcoePopulateComponentFilters();
    dcoePopulateServicePresets();
    dcoeRenderCoverageDashboard();
    if (typeof dcoeRefreshOpsBar === "function" && responseData.coverage) {
        dcoeRefreshOpsBar({
            progress: {
                network_coverage_pct: responseData.coverage.coverage_pct,
            },
        });
    }
}

function dcoeLoadNetwork() {
    dcoeSetStatus("Loading…", "saving");
    get_raw_request_api("/case/dcoe/network/data" + case_param())
        .done((response) => {
            if (response.status !== "success") {
                dcoeSetStatus("Load failed", "error");
                notify_error(response.message || "Unable to load network topology");
                return;
            }
            dcoeApplyData(response.data);
            dcoePopulateComponentFilters();
            dcoePopulateComponentPalette();
            dcoePopulateAssetPalette();
            dcoePopulateAssetSelects();
            dcoePopulateIocPicker();
            dcoePopulateAssetTypeSelects();
            dcoePopulateServicePresets();
            dcoeRenderNetwork(response.data.vis, true);
            dcoeRenderCoverageDashboard();
            $("#dcoe-open-assets").attr("href", "/case/assets" + case_param());
            dcoeSetStatus("Ready");
        });
}

function dcoePopulateComponentPalette() {
    const list = $("#dcoe-component-list");
    list.empty();
    const filtered = dcoeComponents.filter((component) => {
        if (dcoeComponentFilter === "all") return true;
        return component.category === dcoeComponentFilter;
    });
    if (!filtered.length) {
        list.append('<p class="text-muted small mb-0">No components in this category.</p>');
        return;
    }
    let lastCategory = null;
    filtered.forEach((component) => {
        if (component.category && component.category !== lastCategory && dcoeComponentFilter === "all") {
            list.append(`<div class="dcoe-category-heading">${component.category}</div>`);
            lastCategory = component.category;
        }
        const chip = $(`
            <div class="dcoe-chip dcoe-component-chip" draggable="true" data-component-key="${component.key}">
                <span class="dcoe-comp-icon"><i class="fa-solid ${component.icon || "fa-circle-nodes"}"></i></span>
                <div class="dcoe-chip-body">
                    <strong>${component.label}</strong>
                    <small>${component.zone_label || component.group} · ${component.description || "Drag to canvas"}</small>
                </div>
                <button type="button" class="btn btn-xs btn-outline-primary ml-1 dcoe-add-component-btn" title="Place at center">+</button>
            </div>
        `);
        chip.on("dragstart", (event) => {
            dcoeDragPayload = { type: "component", key: component.key, label: component.label };
            event.originalEvent.dataTransfer.setData("text/plain", `component:${component.key}`);
        });
        chip.find(".dcoe-add-component-btn").on("click", (event) => {
            event.preventDefault();
            event.stopPropagation();
            dcoeAddComponentAtCenter(component.key, component.label);
        });
        list.append(chip);
    });
}

function dcoeAddComponentAtCenter(componentKey, label) {
    if (!dcoeNetwork) return;
    const container = document.getElementById("dcoe-network-container");
    const rect = container.getBoundingClientRect();
    const canvasPos = dcoeNetwork.DOMtoCanvas({ x: rect.width / 2, y: rect.height / 2 });
    dcoeAddComponent(componentKey, canvasPos.x, canvasPos.y, label);
}

function dcoeAssetMatchesFilter(asset, onDiagram) {
    if (dcoeAssetFilter === "placed" && !onDiagram) return false;
    if (dcoeAssetFilter === "unplaced" && onDiagram) return false;
    if (dcoeAssetFilter === "compromised" && asset.asset_compromise_status_id !== 1) return false;
    return true;
}

function dcoePopulateAssetPalette() {
    const query = ($("#dcoe-asset-search").val() || "").toLowerCase();
    const list = $("#dcoe-asset-list");
    list.empty();
    const visible = dcoeAssets.filter((asset) => {
        const onDiagram = dcoeTopology.nodes.some((node) => node.asset_id === asset.asset_id);
        if (!dcoeAssetMatchesFilter(asset, onDiagram)) return false;
        if (!query) return true;
        const hay = `${asset.asset_name} ${asset.asset_ip} ${asset.asset_type} ${asset.asset_tags || ""} ${asset.compromise_label || ""}`.toLowerCase();
        return hay.includes(query);
    });
    $("#dcoe-asset-count").text(`${visible.length} / ${dcoeAssets.length}`);
    if (!visible.length) {
        list.append('<p class="text-muted small mb-0">No assets match this filter.</p>');
        return;
    }
    visible.forEach((asset) => {
        const onDiagram = dcoeTopology.nodes.some((node) => node.asset_id === asset.asset_id);
        const node = dcoeTopology.nodes.find((entry) => entry.asset_id === asset.asset_id);
        const zone = asset.suggested_zone || "internal";
        const chip = $(`
            <div class="dcoe-chip dcoe-asset-chip ${onDiagram ? "on-diagram" : ""}" draggable="true" data-asset-id="${asset.asset_id}">
                <strong>${asset.asset_name || "Asset"}</strong>
                <small>${asset.asset_ip || "no IP"} · ${asset.asset_type || "unknown"} · ${zone} zone</small>
                <div class="dcoe-asset-badges">
                    ${dcoeCompromiseBadge(asset)}
                    ${asset.ioc_count ? `<span class="badge badge-info">${asset.ioc_count} IOC</span>` : ""}
                    <span class="badge badge-light">${onDiagram ? "On map" : "Not placed"}</span>
                </div>
                <div class="mt-1">
                    <button type="button" class="btn btn-xs btn-link p-0 dcoe-place-asset">${onDiagram ? "Focus" : "Place"}</button>
                </div>
            </div>
        `);
        chip.on("dragstart", (event) => {
            dcoeDragPayload = { type: "asset", assetId: asset.asset_id };
            event.originalEvent.dataTransfer.setData("text/plain", `asset:${asset.asset_id}`);
        });
        chip.find(".dcoe-place-asset").on("click", () => {
            if (onDiagram && node) {
                dcoeSelectItem("node", node.id);
                dcoeFocusNode(node.id);
            } else {
                dcoePlaceAsset(asset.asset_id);
            }
        });
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

function dcoePopulateAssetTypeSelects() {
    const select = $("#dcoe-new-asset-type");
    select.empty();
    dcoeAssetTypes.forEach((entry) => {
        select.append(`<option value="${entry.id}">${entry.name}</option>`);
    });
}

function dcoePopulateIocPicker() {
    const picker = $("#dcoe-ioc-picker");
    picker.find("option:not(:first)").remove();
    dcoeIocs.forEach((ioc) => {
        picker.append(`<option value="${ioc.ioc_id}">${ioc.ioc_value} (${ioc.ioc_type || "IOC"})</option>`);
    });
}

function dcoeBuildVisOptions() {
    return {
        nodes: {
            shape: "box",
            margin: 12,
            font: { multi: true, size: 12 },
            borderWidth: 2,
            shadow: { enabled: true, size: 6, x: 2, y: 2 },
        },
        edges: {
            smooth: { type: "dynamic" },
            font: { align: "middle", size: 11 },
            color: { color: "#5c6bc0", highlight: "#3949ab" },
            width: 2,
        },
        physics: { enabled: false },
        interaction: {
            dragNodes: true,
            dragView: true,
            zoomView: true,
            navigationButtons: true,
            hover: true,
            multiselect: false,
            keyboard: { enabled: true, bindToWindow: false },
        },
        layout: { improvedLayout: false },
    };
}

function dcoeRenderNetwork(visData, recreate) {
    const container = document.getElementById("dcoe-network-container");
    const nodes = visData.nodes || [];
    const edges = visData.edges || [];

    if (!dcoeNetwork || recreate) {
        dcoeVisNodes = new vis.DataSet(nodes);
        dcoeVisEdges = new vis.DataSet(edges);
        dcoeNetwork = new vis.Network(container, { nodes: dcoeVisNodes, edges: dcoeVisEdges }, dcoeBuildVisOptions());
        dcoeBindNetworkEvents(container);
    } else {
        dcoeVisNodes.clear();
        dcoeVisEdges.clear();
        dcoeVisNodes.add(nodes);
        dcoeVisEdges.add(edges);
    }
}

function dcoeBindNetworkEvents(container) {
    dcoeNetwork.on("click", (params) => {
        if (dcoeConnectMode) {
            dcoeHandleConnectClick(params);
            return;
        }
        if (params.nodes.length) {
            dcoeSelectItem("node", params.nodes[0]);
        } else if (params.edges.length) {
            dcoeSelectItem("edge", params.edges[0]);
        } else {
            dcoeClearSelection();
        }
    });

    dcoeNetwork.on("doubleClick", (params) => {
        if (params.nodes.length) {
            dcoeSelectItem("node", params.nodes[0]);
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
        dcoeScheduleSave(false);
    });

    container.addEventListener("dragover", (event) => {
        event.preventDefault();
        container.classList.add("dcoe-drop-active");
    });
    container.addEventListener("dragleave", () => container.classList.remove("dcoe-drop-active"));
    container.addEventListener("drop", (event) => {
        event.preventDefault();
        container.classList.remove("dcoe-drop-active");
        const rect = container.getBoundingClientRect();
        const domPos = { x: event.clientX - rect.left, y: event.clientY - rect.top };
        const canvasPos = dcoeNetwork.DOMtoCanvas(domPos);
        const raw = event.dataTransfer.getData("text/plain") || "";
        if (raw.startsWith("asset:")) {
            dcoePlaceAsset(parseInt(raw.split(":")[1], 10), canvasPos.x, canvasPos.y);
        } else if (raw.startsWith("component:")) {
            dcoeAddComponent(raw.split(":")[1], canvasPos.x, canvasPos.y);
        } else if (dcoeDragPayload) {
            if (dcoeDragPayload.type === "asset") {
                dcoePlaceAsset(dcoeDragPayload.assetId, canvasPos.x, canvasPos.y);
            } else if (dcoeDragPayload.type === "component") {
                dcoeAddComponent(dcoeDragPayload.key, canvasPos.x, canvasPos.y, dcoeDragPayload.label);
            }
        }
        dcoeDragPayload = null;
    });
}

function dcoeHandleConnectClick(params) {
    if (!params.nodes.length) {
        return;
    }
    const nodeId = params.nodes[0];
    if (!dcoeConnectSource) {
        dcoeConnectSource = nodeId;
        dcoeSetStatus(`Connect: pick target for ${nodeId}`, "saving");
        return;
    }
    if (dcoeConnectSource === nodeId) {
        dcoeConnectSource = null;
        dcoeSetStatus("Connect mode — pick first node", "saving");
        return;
    }
    dcoeTopology.edges.push({
        id: dcoeNewId("edge"),
        from: dcoeConnectSource,
        to: nodeId,
        label: "",
        protocol: "tcp",
        port: "",
        traffic_type: "allowed",
        bandwidth: "",
        comments: [],
    });
    dcoeConnectSource = null;
    dcoeRefreshVis();
    dcoeScheduleSave(false);
    dcoeSetStatus("Connection added", "saving");
}

function dcoeRefreshVis() {
    const assetsById = dcoeAssetsById();
    const vis = dcoeTopologyToVisLocal(dcoeTopology, assetsById);
    dcoeRenderNetwork(vis, false);
    dcoePopulateAssetPalette();
    dcoePopulateAssetSelects();
}

function dcoeTopologyToVisLocal(topology, assetsById) {
    const nodes = (topology.nodes || []).map((entry) => {
        const assetId = entry.asset_id;
        const linked = assetId && assetsById[assetId] ? assetsById[assetId].linked_iocs : [];
        const lines = [entry.label || entry.id];
        if (entry.role) lines.push(entry.role);
        if (entry.hostname && entry.hostname !== entry.asset_ip) lines.push(entry.hostname);
        if (entry.asset_ip) lines.push(entry.asset_ip);
        if (entry.criticality === "critical" || entry.criticality === "high") {
            lines.push(`! ${entry.criticality.toUpperCase()}`);
        }
        const services = entry.services || [];
        const openServices = services.filter((svc) => svc.port).map((svc) => `${svc.port}/${svc.protocol || "tcp"}`);
        if (openServices.length) lines.push(openServices.slice(0, 4).join(", "));
        const iocCount = Math.max((entry.ioc_ids || []).length, linked.length);
        if (iocCount) lines.push(`IOCs: ${iocCount}`);
        let shape = "box";
        if (entry.component_type === "firewall" || entry.component_type === "router") shape = "diamond";
        if (entry.component_type === "cloud_service") shape = "ellipse";
        let borderColor = "#546e7a";
        let borderWidth = 2;
        const asset = entry.asset_id ? assetsById[entry.asset_id] : null;
        if (asset) {
            if (asset.asset_compromise_status_id === 1) {
                borderColor = "#c62828";
                borderWidth = 3;
            } else if (asset.asset_compromise_status_id === 2) {
                borderColor = "#2e7d32";
                borderWidth = 3;
            }
            const analysis = (asset.analysis_status || "").toLowerCase();
            if (analysis && analysis.includes("progress")) {
                borderColor = "#ef6c00";
            }
        }
        return {
            id: entry.id,
            label: lines.join("\n"),
            x: entry.x,
            y: entry.y,
            color: {
                background: entry.color || DCOE_ZONE_COLORS[entry.group] || DCOE_ZONE_COLORS.unknown,
                border: borderColor,
            },
            borderWidth,
            shape,
            font: { multi: true, size: 12 },
            title: entry.label,
        };
    });
    const edges = (topology.edges || []).map((entry) => {
        const labelParts = [];
        if (entry.protocol) labelParts.push(String(entry.protocol).toUpperCase());
        if (entry.port) labelParts.push(String(entry.port));
        if (entry.label) labelParts.push(entry.label);
        if (entry.traffic_type && entry.traffic_type !== "unknown") {
            labelParts.push(entry.traffic_type);
        }
        const edgeColor = entry.traffic_type === "blocked" ? "#c62828"
            : entry.traffic_type === "monitored" ? "#ef6c00" : "#5c6bc0";
        return {
            id: entry.id,
            from: entry.from,
            to: entry.to,
            label: labelParts.join(" / "),
            arrows: "to",
            color: { color: edgeColor, highlight: edgeColor },
            dashes: entry.traffic_type === "blocked",
        };
    });
    return { nodes, edges };
}

function dcoePlaceAsset(assetId, x, y) {
    const asset = dcoeAssets.find((entry) => entry.asset_id === assetId);
    if (!asset) return;
    const existing = dcoeTopology.nodes.find((node) => node.asset_id === assetId);
    if (existing) {
        notify_error("Asset already on diagram");
        dcoeSelectItem("node", existing.id);
        if (x !== undefined && y !== undefined && dcoeNetwork) {
            dcoeNetwork.moveNode(existing.id, x, y);
            existing.x = x;
            existing.y = y;
            dcoeScheduleSave(false);
        }
        return;
    }
    const zone = dcoeGuessZone(asset.asset_type, asset.asset_tags);
    const node = {
        id: `asset-${asset.asset_id}`,
        label: asset.asset_name || asset.asset_ip || `Asset ${asset.asset_id}`,
        group: zone,
        color: DCOE_ZONE_COLORS[zone] || DCOE_ZONE_COLORS.internal,
        asset_id: asset.asset_id,
        asset_uuid: asset.asset_uuid,
        asset_ip: asset.asset_ip,
        asset_type: asset.asset_type,
        services: (asset.linked_iocs && asset.linked_iocs.length) ? [] : [{ port: "", protocol: "tcp", service: asset.asset_type || "", state: "unknown" }],
        ioc_ids: (asset.linked_iocs || []).map((ioc) => ioc.ioc_id),
        x: x !== undefined ? x : 120 + dcoeTopology.nodes.length * 30,
        y: y !== undefined ? y : 120 + dcoeTopology.nodes.length * 30,
        comments: [],
        hostname: asset.asset_name || "",
        role: asset.asset_type || "",
        criticality: asset.asset_compromise_status_id === 1 ? "high" : "medium",
        notes: "",
        component_type: null,
    };
    dcoeTopology.nodes.push(node);
    dcoeRefreshVis();
    dcoeSelectItem("node", node.id);
    dcoeScheduleSave(false);
}

function dcoeAddComponent(componentKey, x, y, label) {
    post_request_api(
        "/case/dcoe/network/components" + case_param(),
        JSON.stringify({
            component_key: componentKey,
            label: label || undefined,
            x,
            y,
            csrf_token: $("#csrf_token").val(),
        })
    ).done((response) => {
        if (response.status === "success") {
            dcoeRefreshNetworkMeta(response.data);
            dcoePopulateComponentPalette();
            dcoePopulateAssetPalette();
            dcoePopulateAssetSelects();
            dcoeRenderNetwork(response.data.vis, false);
            const created = (response.data.topology.nodes || []).slice(-1)[0];
            if (created) dcoeSelectItem("node", created.id);
            dcoeSetStatus("Component added");
        } else {
            notify_error(response.message || "Unable to add component");
        }
    });
}

function dcoeSelectItem(kind, id) {
    dcoeSelected = { kind, id };
    $("#dcoe-panel-empty").hide();
    $("#dcoe-panel-content").show();

    if (kind === "node") {
        const node = dcoeFindNode(id);
        if (!node) return;
        $("#dcoe-panel-title").text(`Node: ${node.label}`);
        $("#dcoe-node-fields").show();
        $("#dcoe-edge-fields").hide();
        $("#dcoe-node-label").val(node.label || "");
        $("#dcoe-node-hostname").val(node.hostname || "");
        $("#dcoe-node-ip").val(node.asset_ip || "");
        $("#dcoe-node-role").val(node.role || "");
        $("#dcoe-node-criticality").val(node.criticality || "medium");
        $("#dcoe-node-zone").val(node.group || "unknown");
        $("#dcoe-node-asset").val(node.asset_id || "");
        $("#dcoe-node-notes").val(node.notes || "");
        $("#dcoe-promote-node").toggle(!node.asset_id);
        $("#dcoe-sync-asset").toggle(!!node.asset_id);
        $("#dcoe-push-asset-comment").toggle(!!node.asset_id);
        dcoeRenderNodeMeta(node);
        dcoeRenderServices(node.services || []);
        dcoeRenderNodeIocs(node);
        dcoeRenderComments(node.comments || []);
    } else {
        const edge = dcoeFindEdge(id);
        if (!edge) return;
        $("#dcoe-panel-title").text(`Connection: ${edge.label || edge.id}`);
        $("#dcoe-node-fields").hide();
        $("#dcoe-edge-fields").show();
        $("#dcoe-edge-label").val(edge.label || "");
        $("#dcoe-edge-traffic").val(edge.traffic_type || "allowed");
        $("#dcoe-edge-protocol").val(edge.protocol || "");
        $("#dcoe-edge-port").val(edge.port || "");
        $("#dcoe-edge-bandwidth").val(edge.bandwidth || "");
        $("#dcoe-push-asset-comment").hide();
        dcoeRenderComments(edge.comments || []);
    }
}

function dcoeRenderNodeMeta(node) {
    const meta = $("#dcoe-node-meta");
    const asset = dcoeAssets.find((entry) => entry.asset_id === node.asset_id);
    const component = dcoeComponents.find((entry) => entry.key === node.component_type);
    let html = `<div><strong>ID:</strong> ${node.id}</div>`;
    if (component) {
        html += `<div class="mt-1"><span class="badge badge-info">${component.label}</span> <span class="badge badge-light">${component.category || "Component"}</span></div>`;
    }
    if (asset) {
        html += `<div class="mt-1">${dcoeCompromiseBadge(asset)}`;
        if (asset.analysis_status) html += ` <span class="badge badge-secondary">${asset.analysis_status}</span>`;
        html += ` <a href="/case/assets${case_param()}" class="small">Asset #${asset.asset_id}</a></div>`;
    } else {
        html += '<div class="mt-1"><span class="badge badge-secondary">Diagram-only</span></div>';
    }
    if (node.x != null && node.y != null) {
        html += `<div class="text-muted mt-1">Position: ${Math.round(node.x)}, ${Math.round(node.y)}</div>`;
    }
    meta.html(html);
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
                <input class="form-control form-control-sm" style="width:24%" placeholder="port" value="${service.port || ""}" data-field="port" />
                <input class="form-control form-control-sm" style="width:18%" placeholder="tcp" value="${service.protocol || "tcp"}" data-field="protocol" />
                <input class="form-control form-control-sm" style="width:26%" placeholder="service" value="${service.service || ""}" data-field="service" />
                <input class="form-control form-control-sm" style="width:18%" placeholder="state" value="${service.state || ""}" data-field="state" />
                <button type="button" class="btn btn-xs btn-outline-danger btn-remove-row" title="Remove">&times;</button>
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
    (node.ioc_ids || []).forEach((iocId) => {
        const fromAsset = asset && (asset.linked_iocs || []).find((ioc) => ioc.ioc_id === iocId);
        const fromCase = dcoeIocs.find((ioc) => ioc.ioc_id === iocId);
        const ioc = fromAsset || fromCase;
        if (ioc) {
            list.append(`
                <div class="dcoe-ioc-item">
                    <a class="dcoe-ioc-link" href="/case/ioc${case_param()}" target="_blank">${ioc.ioc_value} (${ioc.ioc_type || "IOC"})</a>
                    <button type="button" class="btn btn-xs btn-outline-danger dcoe-remove-ioc" data-ioc-id="${iocId}">&times;</button>
                </div>
            `);
        }
    });
    if (!list.children().length) {
        list.append('<small class="text-muted">No IOCs linked.</small>');
    }
}

function dcoeApplyInspectorChanges() {
    if (!dcoeSelected.kind) return;
    if (dcoeSelected.kind === "node") {
        const node = dcoeFindNode(dcoeSelected.id);
        if (!node) return;
        node.label = $("#dcoe-node-label").val();
        node.hostname = $("#dcoe-node-hostname").val();
        node.asset_ip = $("#dcoe-node-ip").val();
        node.role = $("#dcoe-node-role").val();
        node.criticality = $("#dcoe-node-criticality").val() || "medium";
        node.notes = $("#dcoe-node-notes").val();
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
        } else {
            node.asset_id = null;
            node.asset_uuid = null;
        }
    } else {
        const edge = dcoeFindEdge(dcoeSelected.id);
        if (edge) {
            edge.label = $("#dcoe-edge-label").val();
            edge.traffic_type = $("#dcoe-edge-traffic").val() || "allowed";
            edge.protocol = $("#dcoe-edge-protocol").val();
            edge.port = $("#dcoe-edge-port").val();
            edge.bandwidth = $("#dcoe-edge-bandwidth").val();
        }
    }
}

function dcoeSaveNetwork(reload, syncAssets) {
    if (dcoeSaving) return;
    dcoeApplyInspectorChanges();
    dcoeSaving = true;
    dcoeSetStatus("Saving…", "saving");
    $.ajax({
        url: "/case/dcoe/network/data" + case_param(),
        type: "PUT",
        contentType: "application/json",
        data: JSON.stringify({
            topology: dcoeTopology,
            sync_assets: !!syncAssets,
            csrf_token: $("#csrf_token").val(),
        }),
        success: (response) => {
            dcoeSaving = false;
            if (response.status === "success") {
                dcoeRefreshNetworkMeta(response.data);
                if (reload) {
                    dcoePopulateComponentPalette();
                    dcoePopulateAssetPalette();
                    dcoePopulateAssetSelects();
                    dcoeRenderNetwork(response.data.vis, false);
                } else {
                    dcoeTopology = response.data.topology;
                    dcoeRenderNetwork(response.data.vis, false);
                    dcoePopulateAssetPalette();
                }
                if (dcoeSelected.id) dcoeSelectItem(dcoeSelected.kind, dcoeSelected.id);
                dcoeSetStatus("Saved");
            } else {
                dcoeSetStatus("Save failed", "error");
                notify_error(response.message || "Save failed");
            }
        },
        error: (jqXHR) => {
            dcoeSaving = false;
            dcoeSetStatus("Save failed", "error");
            ajax_notify_error(jqXHR, "/case/dcoe/network/data");
        },
    });
}

function dcoeOpenNewAssetModal(nodeId, x, y, defaults) {
    $("#dcoe-new-asset-node-id").val(nodeId || "");
    $("#dcoe-new-asset-x").val(x !== undefined ? x : "");
    $("#dcoe-new-asset-y").val(y !== undefined ? y : "");
    $("#dcoe-new-asset-name").val((defaults && defaults.name) || "");
    $("#dcoe-new-asset-ip").val((defaults && defaults.ip) || "");
    $("#dcoe-new-asset-description").val((defaults && defaults.description) || "");
    if (defaults && defaults.zone) $("#dcoe-new-asset-zone").val(defaults.zone);
    $("#dcoe-modal-new-asset").modal("show");
    setTimeout(() => $("#dcoe-new-asset-name").trigger("focus"), 250);
}

function dcoeSubmitNewAsset() {
    const payload = {
        asset_name: $("#dcoe-new-asset-name").val().trim(),
        asset_type_id: parseInt($("#dcoe-new-asset-type").val(), 10),
        asset_ip: $("#dcoe-new-asset-ip").val().trim(),
        asset_description: $("#dcoe-new-asset-description").val().trim(),
        zone: $("#dcoe-new-asset-zone").val(),
        node_id: $("#dcoe-new-asset-node-id").val() || undefined,
        csrf_token: $("#csrf_token").val(),
    };
    const x = $("#dcoe-new-asset-x").val();
    const y = $("#dcoe-new-asset-y").val();
    if (x !== "") payload.x = parseFloat(x);
    if (y !== "") payload.y = parseFloat(y);
    if (!payload.asset_name) {
        notify_error("Asset name is required");
        return;
    }
    post_request_api("/case/dcoe/network/assets" + case_param(), JSON.stringify(payload)).done((response) => {
        if (response.status === "success") {
            $("#dcoe-modal-new-asset").modal("hide");
            dcoeRefreshNetworkMeta(response.data);
            dcoePopulateComponentPalette();
            dcoePopulateAssetPalette();
            dcoePopulateAssetSelects();
            dcoeRenderNetwork(response.data.vis, false);
            if (response.data.created_node) dcoeSelectItem("node", response.data.created_node.id);
            notify_success("Asset created on diagram");
            dcoeSetStatus("Asset created");
        } else {
            notify_error(response.message || "Unable to create asset");
        }
    });
}

function dcoePromoteSelectedNode() {
    if (dcoeSelected.kind !== "node") return;
    const node = dcoeFindNode(dcoeSelected.id);
    if (!node || node.asset_id) return;
    post_request_api(
        `/case/dcoe/network/nodes/${encodeURIComponent(node.id)}/promote` + case_param(),
        JSON.stringify({
            asset_name: $("#dcoe-node-label").val().trim() || node.label,
            csrf_token: $("#csrf_token").val(),
        })
    ).done((response) => {
        if (response.status === "success") {
            dcoeRefreshNetworkMeta(response.data);
            dcoePopulateAssetPalette();
            dcoePopulateAssetSelects();
            dcoeRenderNetwork(response.data.vis, false);
            dcoeSelectItem("node", node.id);
            notify_success("Node promoted to case asset");
        } else {
            notify_error(response.message || "Promote failed");
        }
    });
}

function dcoeAddComment(pushToAsset) {
    if (!dcoeSelected.kind) return;
    const text = $("#dcoe-comment-input").val().trim();
    if (!text) return;
    const user = dcoeNetworkMeta.current_user || {};
    const comment = {
        id: dcoeNewId("comment"),
        author: user.login || "",
        author_name: user.name || user.login || "Operator",
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
    dcoeScheduleSave(false);
    dcoeRenderComments(
        dcoeSelected.kind === "node"
            ? dcoeFindNode(dcoeSelected.id).comments
            : dcoeFindEdge(dcoeSelected.id).comments
    );
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
        traffic_type: "allowed",
        bandwidth: "",
        comments: [],
    });
    dcoeRefreshVis();
    dcoeScheduleSave(false);
}

function dcoeDeleteSelection() {
    if (!dcoeSelected.kind) return;
    if (dcoeSelected.kind === "node") {
        dcoeTopology.nodes = dcoeTopology.nodes.filter((node) => node.id !== dcoeSelected.id);
        dcoeTopology.edges = dcoeTopology.edges.filter(
            (edge) => edge.from !== dcoeSelected.id && edge.to !== dcoeSelected.id
        );
    } else {
        dcoeTopology.edges = dcoeTopology.edges.filter((edge) => edge.id !== dcoeSelected.id);
    }
    dcoeClearSelection();
    dcoeRefreshVis();
    dcoeScheduleSave(false);
}

function dcoeImportAllAssets() {
    post_request_api(
        "/case/dcoe/network/import-assets" + case_param(),
        JSON.stringify({ csrf_token: $("#csrf_token").val() })
    ).done((response) => {
        if (response.status === "success") {
            dcoeRefreshNetworkMeta(response.data);
            dcoePopulateAssetPalette();
            dcoePopulateAssetSelects();
            dcoeRenderNetwork(response.data.vis, false);
            notify_success("Imported all case assets");
            dcoeSetStatus("Assets imported");
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

function dcoeImportTopologyFile(file, merge) {
    const reader = new FileReader();
    reader.onload = (event) => {
        try {
            const payload = JSON.parse(event.target.result);
            const doImport = () => {
                post_request_api(
                    "/case/dcoe/network/import" + case_param(),
                    JSON.stringify({ ...payload, merge: !!merge, csrf_token: $("#csrf_token").val() })
                ).done((response) => {
                    if (response.status === "success") {
                        dcoeRefreshNetworkMeta(response.data);
                        dcoePopulateComponentPalette();
                        dcoePopulateAssetPalette();
                        dcoePopulateAssetSelects();
                        dcoeRenderNetwork(response.data.vis, true);
                        notify_success(merge ? "Topology merged" : "Topology imported");
                    } else {
                        notify_error(response.message || "Import failed");
                    }
                });
            };
            if (merge) {
                doImport();
                return;
            }
            do_deletion_prompt("Replace the entire diagram with this file? Existing layout will be lost.").then((confirmed) => {
                if (confirmed) doImport();
            });
        } catch (error) {
            notify_error("Invalid JSON file");
        }
    };
    reader.readAsText(file);
}

function dcoeExportPngSnapshot() {
    const canvas = document.querySelector("#dcoe-network-container canvas");
    if (!canvas) {
        notify_error("Diagram not ready — wait for load, then try again");
        return;
    }
    const link = document.createElement("a");
    link.download = `network-map${case_param().replace("?", "-")}.png`;
    link.href = canvas.toDataURL("image/png");
    link.click();
    notify_success("PNG snapshot downloaded — attach to SitRep or evidence");
}

function dcoeUpdateNetworkMapReport() {
    dcoeSetStatus("Updating report…", "saving");
    post_request_api(
        "/case/dcoe/network/report-draft" + case_param(),
        JSON.stringify({ csrf_token: $("#csrf_token").val() })
    ).done((response) => {
        if (response.status !== "success") {
            dcoeSetStatus("Report failed", "error");
            notify_error(response.message || "Unable to update report");
            return;
        }
        dcoeSetStatus("Report updated");
        notify_success(
            response.data.created
                ? "Network Map Status report created from live topology"
                : "Network Map Status report refreshed with current coverage"
        );
        if (response.data.workspace_url) {
            window.location.href = response.data.workspace_url;
        }
    });
}

function dcoeToggleConnectMode() {
    dcoeConnectMode = !dcoeConnectMode;
    dcoeConnectSource = null;
    $("#dcoe-mode-connect").toggleClass("dcoe-mode-active btn-primary", dcoeConnectMode).toggleClass("btn-light", !dcoeConnectMode);
    dcoeSetStatus(dcoeConnectMode ? "Connect mode — click first node" : "Ready", dcoeConnectMode ? "saving" : null);
}

$(document).ready(function () {
    dcoeLoadNetwork();

    $("#dcoe-network-save").on("click", () => dcoeSaveNetwork(true, true));
    $("#dcoe-network-import-all").on("click", dcoeImportAllAssets);
    $("#dcoe-network-export").on("click", dcoeExportTopology);
    $("#dcoe-network-import-file").on("change", function () {
        if (this.files && this.files[0]) dcoeImportTopologyFile(this.files[0], false);
        $(this).val("");
    });
    $("#dcoe-network-import-merge-file").on("change", function () {
        if (this.files && this.files[0]) dcoeImportTopologyFile(this.files[0], true);
        $(this).val("");
    });
    $("#dcoe-network-update-report").on("click", dcoeUpdateNetworkMapReport);
    $("#dcoe-network-snapshot").on("click", dcoeExportPngSnapshot);
    $(document).on("click", ".dcoe-place-unmapped", function () {
        dcoePlaceAsset(parseInt($(this).data("asset-id"), 10));
    });
    $("#dcoe-connect-edge").on("click", dcoeConnectEdge);
    $("#dcoe-delete-selection").on("click", dcoeDeleteSelection);
    $("#dcoe-add-comment").on("click", () => dcoeAddComment(false));
    $("#dcoe-push-asset-comment").on("click", () => dcoeAddComment(true));
    $("#dcoe-mode-connect").on("click", dcoeToggleConnectMode);
    $("#dcoe-fit-view").on("click", () => dcoeNetwork && dcoeNetwork.fit({ animation: true }));
    $("#dcoe-new-asset").on("click", () => dcoeOpenNewAssetModal(null, 160, 160));
    $("#dcoe-submit-new-asset").on("click", dcoeSubmitNewAsset);
    $("#dcoe-promote-node").on("click", dcoePromoteSelectedNode);
    $("#dcoe-sync-asset").on("click", () => dcoeSaveNetwork(true, true));
    $("#dcoe-asset-search").on("input", dcoePopulateAssetPalette);
    $(document).on("click", ".dcoe-asset-filter", function () {
        dcoeAssetFilter = $(this).data("filter") || "all";
        $(".dcoe-asset-filter").removeClass("btn-primary").addClass("btn-outline-secondary");
        $(this).removeClass("btn-outline-secondary").addClass("btn-primary");
        dcoePopulateAssetPalette();
    });
    $(document).on("click", ".dcoe-component-filter", function () {
        dcoeComponentFilter = $(this).data("filter") || "all";
        $(".dcoe-component-filter").removeClass("btn-primary").addClass("btn-outline-secondary");
        $(this).removeClass("btn-outline-secondary").addClass("btn-primary");
        dcoePopulateComponentPalette();
    });
    $("#dcoe-focus-node").on("click", () => {
        if (dcoeSelected.kind === "node") dcoeFocusNode(dcoeSelected.id);
    });
    $("#dcoe-service-preset").on("change", function () {
        const idx = $(this).val();
        if (idx === "" || dcoeSelected.kind !== "node") return;
        const preset = (dcoeNetworkMeta.service_presets || [])[parseInt(idx, 10)];
        if (!preset) return;
        const node = dcoeFindNode(dcoeSelected.id);
        node.services = node.services || [];
        node.services.push({
            port: preset.port,
            protocol: preset.protocol,
            service: preset.service,
            state: preset.state,
        });
        dcoeRenderServices(node.services);
        dcoeApplyInspectorChanges();
        dcoeScheduleSave(false);
        $(this).val("");
    });
    $("#dcoe-services-list").on("click", ".btn-remove-row", function () {
        $(this).closest(".dcoe-service-row").remove();
        dcoeApplyInspectorChanges();
        dcoeRefreshVis();
        dcoeScheduleSave(false);
    });
    $("#dcoe-ioc-list").on("click", ".dcoe-remove-ioc", function () {
        if (dcoeSelected.kind !== "node") return;
        const iocId = parseInt($(this).data("ioc-id"), 10);
        const node = dcoeFindNode(dcoeSelected.id);
        node.ioc_ids = (node.ioc_ids || []).filter((id) => id !== iocId);
        dcoeRenderNodeIocs(node);
        dcoeScheduleSave(true);
    });

    $("#dcoe-add-service").on("click", () => {
        if (!dcoeSelected.kind || dcoeSelected.kind !== "node") return;
        const node = dcoeFindNode(dcoeSelected.id);
        node.services = node.services || [];
        node.services.push({ port: "", protocol: "tcp", service: "", state: "open" });
        dcoeRenderServices(node.services);
        dcoeScheduleSave(false);
    });

    $("#dcoe-ioc-picker").on("change", function () {
        const iocId = parseInt($(this).val(), 10);
        if (!iocId || dcoeSelected.kind !== "node") return;
        const node = dcoeFindNode(dcoeSelected.id);
        node.ioc_ids = node.ioc_ids || [];
        if (!node.ioc_ids.includes(iocId)) node.ioc_ids.push(iocId);
        $(this).val("");
        dcoeRenderNodeIocs(node);
        dcoeScheduleSave(false);
    });

    $("#dcoe-node-label, #dcoe-node-hostname, #dcoe-node-ip, #dcoe-node-role, #dcoe-node-criticality, #dcoe-node-notes, #dcoe-node-zone, #dcoe-node-asset, #dcoe-edge-label, #dcoe-edge-traffic, #dcoe-edge-protocol, #dcoe-edge-port, #dcoe-edge-bandwidth")
        .on("change input", () => {
            dcoeApplyInspectorChanges();
            dcoeRefreshVis();
            dcoeScheduleSave(false);
        });
    $("#dcoe-services-list").on("change input", "input", () => {
        dcoeApplyInspectorChanges();
        dcoeScheduleSave(false);
    });
});

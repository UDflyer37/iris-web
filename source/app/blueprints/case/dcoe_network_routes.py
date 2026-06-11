#  OhCR / DCOE interactive network topology

from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import current_user
from flask_wtf import FlaskForm

from app.datamgmt.case.case_db import get_case
from app.datamgmt.dcoe.dcoe_network_db import (
    get_topology,
    import_assets_to_topology,
    list_assets_for_network,
    save_topology,
    topology_to_vis,
)
from app.iris_engine.utils.tracker import track_activity
from app.models.authorization import CaseAccessLevel
from app.util import ac_api_case_requires, ac_case_requires, response_error, response_success

dcoe_network_blueprint = Blueprint(
    "dcoe_network",
    __name__,
    template_folder="templates",
)


@dcoe_network_blueprint.route("/case/dcoe/network", methods=["GET"])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def dcoe_network_page(caseid, url_redir):
    if url_redir:
        return redirect(url_for("dcoe_network.dcoe_network_page", cid=caseid, redirect=True))

    case = get_case(caseid)
    form = FlaskForm()
    return render_template("dcoe_network.html", case=case, form=form)


@dcoe_network_blueprint.route("/case/dcoe/network/data", methods=["GET"])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def dcoe_network_data(caseid):
    case = get_case(caseid)
    topology = get_topology(case)
    return response_success(
        "",
        data={
            "topology": topology,
            "vis": topology_to_vis(topology),
            "assets": list_assets_for_network(caseid),
        },
    )


@dcoe_network_blueprint.route("/case/dcoe/network/data", methods=["PUT"])
@ac_api_case_requires(CaseAccessLevel.full_access)
def dcoe_network_save(caseid):
    case = get_case(caseid)
    payload = request.get_json(silent=True) or {}
    topology = payload.get("topology")
    if not isinstance(topology, dict):
        return response_error("Invalid topology payload")

    topology = save_topology(case, topology, current_user.user)
    track_activity("updated OhCR/DCOE network topology", caseid=caseid)
    return response_success("Topology saved", data={"topology": topology, "vis": topology_to_vis(topology)})


@dcoe_network_blueprint.route("/case/dcoe/network/import-assets", methods=["POST"])
@ac_api_case_requires(CaseAccessLevel.full_access)
def dcoe_network_import_assets(caseid):
    case = get_case(caseid)
    payload = request.get_json(silent=True) or {}
    asset_ids = payload.get("asset_ids")

    assets = list_assets_for_network(caseid)
    if asset_ids:
        wanted = {int(asset_id) for asset_id in asset_ids}
        assets = [asset for asset in assets if asset["asset_id"] in wanted]

    topology = get_topology(case)
    topology = import_assets_to_topology(topology, assets, current_user.user)
    topology = save_topology(case, topology, current_user.user)
    track_activity("imported assets into OhCR/DCOE network topology", caseid=caseid)
    return response_success(
        "Assets imported",
        data={"topology": topology, "vis": topology_to_vis(topology)},
    )

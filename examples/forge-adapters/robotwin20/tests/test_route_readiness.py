from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from robotwin20_adapter import (
    ROUTE_CHECKS,
    ROUTE_PHASES,
    ROUTE_READINESS_PROFILE_SCHEMA_VERSION,
    ROUTE_REQUEST_SCHEMA_VERSION,
    RouteReadinessClient,
    RouteReadinessError,
    RouteReadinessEvaluationAdapter,
    RouteReadinessProfileError,
    build_route_readiness_client,
    load_route_readiness_profile,
    route_geometry_digest,
    validate_route_request,
)
from robotwin20_adapter.process_worker import JsonlProcessWorkerClient, ProcessWorkerConfig
from robotwin20_adapter.route_readiness import project_route_evidence

WORKER = Path(__file__).parents[1] / "runtime" / "robotwin_route_readiness_worker.py"


def _pose(z: float = 0.8) -> dict:
    return {
        "frame_id": "world",
        "position_m": [0.0, 0.0, z],
        "orientation_xyzw": [0.0, 0.0, 0.0, 1.0],
    }


def _request(tmp_path: Path) -> dict:
    phases = []
    z_by_phase = {
        "approach": 0.8, "contact": 0.8, "close": 0.8, "lift": 0.8,
        "transport": 0.8, "descent": 0.7, "release": 0.7, "retreat": 0.8,
    }
    for phase in ROUTE_PHASES:
        phases.append({
            "phase": phase,
            "waypoints": [_pose(z_by_phase[phase])],
            "gripper_state": "open" if phase in {"approach", "retreat"} else "contact" if phase == "contact" else "closed" if phase in {"close", "lift", "transport", "descent"} else "released",
        })
    return {
        "schema_version": ROUTE_REQUEST_SCHEMA_VERSION,
        "request_id": "request-route-1",
        "observation_ref": "observation://blocks_ranking_rgb-0-1/head_camera",
        "observation_frame_id": "head_camera",
        "scene_revision": "blocks_ranking_rgb-0-1",
        "frame_id": "world",
        "calibration_ref": "artifact://blocks/calibration",
        "calibration_sha256": "c" * 64,
        "calibration_revision": "calibration-1",
        "candidate_set_ref": "candidate-set://blocks_ranking_rgb-0-1/head_camera",
        "workspace_bounds_m": {
            "frame_id": "world",
            "x_min_m": -0.5, "x_max_m": 0.5, "y_min_m": -0.5, "y_max_m": 0.5, "z_min_m": 0.5, "z_max_m": 1.2,
            "provenance_ref": "artifact://blocks/workspace",
        },
        "joint_limits_ref": "artifact://blocks/joint-limits",
        "stop_policy_ref": "artifact://blocks/stop-policy",
        "motion_capabilities": [
            {
                "arm_id": "left",
                "artifact_ref": "artifact://blocks/motion-capability-left",
                "sha256": "1" * 64,
                "validation_ref": "artifact://blocks/motion-capability-left-validation",
                "validation_sha256": "2" * 64,
            },
            {
                "arm_id": "right",
                "artifact_ref": "artifact://blocks/motion-capability-right",
                "sha256": "3" * 64,
                "validation_ref": "artifact://blocks/motion-capability-right-validation",
                "validation_sha256": "4" * 64,
            },
        ],
        "controller_qualification": {
            "qualification_id": "qualification-1",
            "artifact_ref": "artifact://qualification/final",
            "sha256": "5" * 64,
            "plan_ref": "artifact://qualification/plan",
            "plan_sha256": "6" * 64,
            "evidence_ref": "artifact://qualification/evidence",
            "evidence_sha256": "7" * 64,
            "validation_ref": "artifact://qualification/validation",
            "validation_sha256": "8" * 64,
        },
        "collision_world": {
            "artifact_ref": "artifact://blocks/collision-world",
            "sha256": "9" * 64,
            "scene_revision": "blocks_ranking_rgb-0-1",
            "world_revision": 1,
            "world_digest": "a" * 64,
            "coverage": "complete",
            "target_entity_ref": "entity://red-block",
            "obstacle_entity_refs": ["entity://green-block", "entity://blue-block"],
        },
        "candidates": [{
            "candidate_ref": "candidate://red-block/1",
            "entity_ref": "entity://red-block",
            "provenance": ["artifact://blocks/points/red"],
            "execution_grasp": {
                "contact_center_pose": _pose(),
                "robot_target_pose": _pose(),
                "robot_target_frame": "robotwin_gripper",
                "robot_target_round_trip_residual_m": 0.0,
                "ingress_direction": {
                    "frame_id": "world", "vector": [0.0, 0.0, -1.0],
                    "provenance_ref": "artifact://blocks/grasp-adaptation",
                },
                "support_clear_direction": {
                    "frame_id": "world", "vector": [0.0, 0.0, 1.0],
                    "provenance_ref": "artifact://blocks/support-normal",
                },
                "adaptation_provenance_ref": "artifact://blocks/grasp-adaptation",
            },
            "attached_object": {
                "geometry_ref": "artifact://blocks/geometry/red",
                "geometry_sha256": "a" * 64,
                "object_frame_id": "red-block",
                "half_extents_m": [0.02, 0.02, 0.02],
                "object_T_robot_target": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
                "transform_provenance_ref": "artifact://blocks/object-t-robot-target",
            },
            "placement_target": {
                "target_ref": "destination://blocks/red-slot",
                "target_object_pose": _pose(0.7),
                "release_robot_target_pose": _pose(0.7),
                "provenance_ref": "artifact://blocks/placement-target",
            },
            "route": phases,
        }],
    }


def test_valid_route_request_is_deterministically_bound(tmp_path: Path):
    request = _request(tmp_path)
    validate_route_request(request)
    assert route_geometry_digest(request) == route_geometry_digest(request)


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda r: r["candidates"][0]["route"].reverse(), "phases"),
        (lambda r: r["candidates"][0]["attached_object"].update(geometry_sha256="bad"), "SHA-256"),
        (lambda r: r["workspace_bounds_m"].update(frame_id="wrist"), "share a frame"),
        (lambda r: r["candidates"][0]["route"][0]["waypoints"][0].update(position_m=[0, 0, 2]), "workspace"),
        (lambda r: r["candidates"][0]["route"][0]["waypoints"][0].update(unknown_speed=0), "fields"),
        (lambda r: r["candidates"][0]["placement_target"]["release_robot_target_pose"].update(position_m=[0.1, 0, 0.7]), "release RoboTwin target"),
        (lambda r: r["candidates"][0]["route"][6].update(gripper_state="closed"), "gripper state"),
        (lambda r: r["motion_capabilities"].pop(), "both arms"),
        (lambda r: r["motion_capabilities"][1].update(arm_id="left"), "arm binding"),
        (lambda r: r["controller_qualification"].update(sha256="bad"), "SHA-256"),
        (lambda r: r["controller_qualification"].pop("validation_ref"), "qualification binding"),
    ],
)
def test_route_request_fails_closed(tmp_path: Path, mutate, message: str):
    request = _request(tmp_path)
    mutate(request)
    with pytest.raises(RouteReadinessError, match=message):
        validate_route_request(request)


def test_route_evidence_never_authorizes_motion(tmp_path: Path):
    request = _request(tmp_path)
    candidate = request["candidates"][0]
    evidence = project_route_evidence(
        request,
        candidate,
        capability_status={check: "unavailable" for check in ROUTE_CHECKS},
        evidence_ref="artifact://route/evidence-1",
    )
    assert evidence["motion_authorized"] is False
    assert evidence["world_change_started"] is False
    assert set(evidence["checks"]) == set(ROUTE_CHECKS)


def test_external_worker_records_unavailable_evidence_without_motion(tmp_path: Path):
    config = ProcessWorkerConfig(
        command=(sys.executable, str(WORKER), "--artifact-root", str(tmp_path), "--worker-id", "route-readiness-test/v1"),
        cwd=WORKER.parent,
        environment={"PYTHONPATH": str(Path(__file__).parents[1] / "src") + ":" + str(WORKER.parent)},
        startup_timeout_s=2,
        request_timeout_s=2,
        shutdown_timeout_s=2,
    )
    client = JsonlProcessWorkerClient(config)
    try:
        request = _request(tmp_path)
        response = client.request(request)
        assert response["status"] == "unavailable"
        assert response["provider_available"] is False
        assert response["motion_authorized"] is False
        artifact = next((tmp_path / "simulation-route-readiness").glob("*.json"), None)
        assert artifact is not None
        evidence = json.loads(artifact.read_text(encoding="utf-8"))
        assert all(status == "unavailable" for status in evidence["checks"].values())
    finally:
        client.release()


def test_route_readiness_profile_loader_rejects_duplicate_keys(tmp_path):
    profile_path = tmp_path / "duplicate.yaml"
    profile_path.write_text(
        "schema_version: paos-robotwin20-route-readiness/v1\n"
        "schema_version: overwritten\n",
        encoding="utf-8",
    )

    with pytest.raises(RouteReadinessProfileError, match="duplicate YAML keys"):
        load_route_readiness_profile(profile_path.resolve())


def test_profile_owned_route_client_preserves_unavailable_boundary(tmp_path: Path):
    profile_path = tmp_path / "route-readiness.yaml"
    value = {
        "schema_version": ROUTE_READINESS_PROFILE_SCHEMA_VERSION,
        "worker_id": "route-readiness-test/v1",
        "artifact_root": str(tmp_path),
        "worker": {
            "python": sys.executable,
            "script": str(WORKER),
            "cwd": str(WORKER.parent),
            "startup_timeout_s": 2,
            "request_timeout_s": 2,
            "shutdown_timeout_s": 2,
            "environment": {
                "PYTHONUNBUFFERED": "1",
                "PYTHONPATH": f"{Path(__file__).parents[1] / 'src'}:{WORKER.parent}",
            },
            "arguments": [
                "--artifact-root", str(tmp_path),
                "--worker-id", "route-readiness-test/v1",
            ],
        },
    }
    import yaml

    profile_path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")
    loaded = load_route_readiness_profile(profile_path)
    client = build_route_readiness_client(loaded)
    try:
        response = client.evaluate(_request(tmp_path))
        assert response["status"] == "unavailable"
        assert response["motion_authorized"] is False
    finally:
        client.release()


def test_route_readiness_evaluation_adapter_projects_unavailable_worker_result(tmp_path: Path):
    request = _request(tmp_path)
    option = {
        "candidate_ref": request["candidates"][0]["candidate_ref"],
        "task_id": "task-1", "revision_id": "revision-1", "node_id": "prepare-red",
        "node_digest": "a" * 64, "observation_ref": request["observation_ref"],
        "scene_revision": request["scene_revision"], "observation_frame_id": request["observation_frame_id"],
        "frame_id": request["frame_id"], "calibration_ref": request["calibration_ref"],
        "candidate_set_ref": request["candidate_set_ref"], "arm_ids": ["left"],
        "option_id": "option-1",
    }

    class FakeClient:
        def evaluate(self, value):
            return {"status": "unavailable", "route_evidence": [project_route_evidence(
                value,
                value["candidates"][0],
                capability_status={check: "unavailable" for check in ROUTE_CHECKS},
                evidence_ref="artifact://route-readiness/item",
            )]}

    projected = RouteReadinessEvaluationAdapter(FakeClient()).evaluate(request, option)
    assert projected["schema_version"] == "paos-robotwin20-route-evaluation/v1"
    assert projected["status"] == "unavailable"
    assert projected["code"] == "provider_unavailable"
    assert projected["motion_authorized"] is False


def test_route_readiness_client_rejects_tampered_candidate_evidence(tmp_path: Path):
    request = _request(tmp_path)
    evidence = project_route_evidence(
        request,
        request["candidates"][0],
        capability_status={check: "unavailable" for check in ROUTE_CHECKS},
        evidence_ref="artifact://route-readiness/item",
    )
    evidence["scene_revision"] = "stale"

    class FakeProcessClient:
        def request(self, _value):
            return {
                "request_id": request["request_id"],
                "schema_version": "paos-robotwin20-simulation-route-readiness/v2",
                "worker_id": "worker-1",
                "status": "unavailable",
                "provider_available": False,
                "motion_authorized": False,
                "world_change_started": False,
                "route_evidence": [evidence],
            }

    with pytest.raises(RouteReadinessProfileError, match="identity"):
        RouteReadinessClient(FakeProcessClient(), worker_id="worker-1").evaluate(request)


def test_route_readiness_client_rejects_top_level_world_change(tmp_path: Path):
    request = _request(tmp_path)

    class FakeProcessClient:
        def request(self, _value):
            return {
                "request_id": request["request_id"],
                "schema_version": "paos-robotwin20-simulation-route-readiness/v2",
                "worker_id": "worker-1",
                "status": "unavailable",
                "provider_available": False,
                "motion_authorized": False,
                "world_change_started": True,
                "route_evidence": [],
            }

    with pytest.raises(RouteReadinessProfileError, match="world-change"):
        RouteReadinessClient(FakeProcessClient(), worker_id="worker-1").evaluate(request)

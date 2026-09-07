"""Independent, explicitly authorized RoboTwin simulation evidence producer.

This worker is the *external probe* paired with ``route_evidence``.  Unlike
the verifier, it is allowed to step one RoboTwin scene, but only after an
approval record and a producer/profile binding have been checked.  It never
creates a PAOS Gateway invocation, calls Dora, or talks to hardware.

The worker executes one candidate route at a time.  Every planner segment is
checked against the robot joint limits, every simulator step is monitored for
timeouts/stop requests and contacts, and immutable before/after/scope
artifacts are written below the configured artifact root.  Any missing or
ambiguous input returns ``unavailable`` rather than a partial pass.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import time
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from robotwin_capability_controller import (
    CapabilityBoundedDriveController,
    ControllerCommandError,
    ControllerLimits,
)
from robotwin_curobo_world_port import CuroboWorldPortError, apply_collision_world
from worker_protocol import serve

from robotwin20_adapter.controller_qualification import (
    ControllerQualification,
    ControllerQualificationError,
    ControllerQualificationEvidence,
    ControllerQualificationPlan,
    ControllerQualificationValidation,
    controller_qualification_digest,
    validate_controller_qualification_result_package,
)
from robotwin20_adapter.dual_arm_state import (
    DualArmStateError,
    build_dual_arm_state,
    build_peer_arm_sphere_projection,
    hold_drift,
    validate_dual_arm_state,
)
from robotwin20_adapter.motion_capabilities import (
    MotionCapabilityDocument,
    MotionCapabilityValidation,
    motion_capability_digest,
)
from robotwin20_adapter.route_readiness import (
    ROUTE_PHASES,
    route_geometry_digest,
    validate_route_request,
)

SCHEMA_VERSION = "paos-robotwin20-simulation-probe/v1"
APPROVAL_SCHEMA_VERSION = "paos-robotwin20-simulation-probe-approval/v4"
_STATE_FIELDS = ("scene_revision", "observation_ref", "frame_id", "candidate_set_ref")
_GRIPPER_VALUES = {"open": 1.0, "contact": 1.0, "closed": 0.0, "released": 1.0}
_SAFE_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


class SimulationProbeError(ValueError):
    """The probe request or runtime result is unsafe or incomplete."""


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _artifact_path(root: Path, ref: str, *, create_parent: bool = False) -> Path:
    if not isinstance(ref, str) or not ref.startswith("artifact://"):
        raise SimulationProbeError("probe artifact_ref is invalid")
    parts = ref.removeprefix("artifact://").split("/")
    if len(parts) < 2 or any(not part or part in {".", ".."} for part in parts):
        raise SimulationProbeError("probe artifact_ref is invalid")
    path = root.joinpath(*parts)
    if not path.suffix:
        path = path.with_suffix(".json")
    if create_parent:
        path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise SimulationProbeError("probe artifact path is unsafe")
    resolved_root = root.resolve()
    resolved = path.resolve()
    if resolved_root not in resolved.parents and resolved != resolved_root:
        raise SimulationProbeError("probe artifact path escapes artifact root")
    return resolved


def _artifact_record(root: Path, ref: str, payload: bytes) -> dict[str, str]:
    path = _artifact_path(root, ref, create_parent=True)
    if path.exists():
        if path.is_symlink() or path.read_bytes() != payload:
            raise SimulationProbeError("probe artifact is immutable and divergent")
    else:
        with path.open("xb") as stream:
            stream.write(payload)
        path.chmod(0o600)
    return {"artifact_ref": ref, "sha256": _sha_bytes(payload)}


def _json_artifact(root: Path, ref: str, value: Mapping[str, Any]) -> dict[str, str]:
    return _artifact_record(
        root,
        ref,
        (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"),
    )


def _candidate_token(candidate_ref: str) -> str:
    token = candidate_ref.removeprefix("candidate://").replace("/", "-")
    if _SAFE_TOKEN.fullmatch(token) is None:
        raise SimulationProbeError("probe candidate_ref cannot form a safe artifact identity")
    return token


def _load_json_artifact(root: Path, ref: str) -> Mapping[str, Any]:
    path = _artifact_path(root, ref)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SimulationProbeError("probe JSON artifact is invalid") from exc
    if not isinstance(value, Mapping):
        raise SimulationProbeError("probe JSON artifact must be an object")
    return value


def _validate_route_input_artifacts(
    root: Path, request: Mapping[str, Any], candidate: Mapping[str, Any]
) -> Mapping[str, Any]:
    """Re-check adapter materializations before any simulator world change."""
    attached = candidate["attached_object"]
    geometry = _load_json_artifact(root, attached["geometry_ref"])
    if geometry.get("schema_version") != "paos-robotwin20-object-geometry/v1":
        raise SimulationProbeError("attached geometry artifact schema is unsupported")
    if geometry.get("entity_ref") != candidate["entity_ref"] or geometry.get("scene_revision") != request["scene_revision"]:
        raise SimulationProbeError("attached geometry artifact identity is invalid")
    if geometry.get("frame_id") != attached["object_frame_id"] or geometry.get("shape") != "box":
        raise SimulationProbeError("attached geometry artifact frame or shape is invalid")
    try:
        half_extents = [float(item) for item in geometry["half_extents_m"]]
    except (KeyError, TypeError, ValueError) as exc:
        raise SimulationProbeError("attached geometry half extents are invalid") from exc
    if half_extents != [float(item) for item in attached["half_extents_m"]]:
        raise SimulationProbeError("attached geometry half extents are not bound to request")
    transform = _load_json_artifact(root, attached["transform_provenance_ref"])
    if transform.get("schema_version") != "paos-robotwin20-object-robot-target-transform/v1":
        raise SimulationProbeError("object_T_robot_target provenance schema is unsupported")
    if transform.get("entity_ref") != candidate["entity_ref"] or transform.get("scene_revision") != request["scene_revision"]:
        raise SimulationProbeError("object_T_robot_target provenance identity is invalid")
    if transform.get("object_T_robot_target") != attached["object_T_robot_target"]:
        raise SimulationProbeError("object_T_robot_target is not bound to provenance artifact")
    placement = candidate["placement_target"]
    target = _load_json_artifact(root, placement["provenance_ref"])
    if target.get("schema_version") != "paos-robotwin20-placement-target/v1":
        raise SimulationProbeError("placement target artifact schema is unsupported")
    if target.get("entity_ref") != candidate["entity_ref"] or target.get("scene_revision") != request["scene_revision"]:
        raise SimulationProbeError("placement target artifact identity is invalid")
    if target.get("target_ref") != placement["target_ref"] or target.get("frame_id") != request["frame_id"]:
        raise SimulationProbeError("placement target artifact binding is invalid")
    return {"geometry": geometry, "transform": transform, "placement": target}


def _validate_runtime_route_input_binding(
    task: Any, candidate: Mapping[str, Any], artifacts: Mapping[str, Any]
) -> None:
    import numpy as np

    actor = _actor_for_entity(task, candidate["entity_ref"])
    actual = np.asarray(actor.get_pose().to_transformation_matrix(), dtype=np.float64)
    expected_flat = artifacts["transform"].get("world_T_object")
    if not isinstance(expected_flat, list) or len(expected_flat) != 16:
        raise SimulationProbeError("object_T_robot_target provenance initial object pose is invalid")
    expected = np.asarray(expected_flat, dtype=np.float64).reshape(4, 4)
    if not np.isfinite(actual).all() or not np.isfinite(expected).all() or not np.allclose(actual, expected, atol=1e-5):
        raise SimulationProbeError("runtime object pose does not match route input evidence")


def _orientation_error_rad(before: list[float], after: list[float]) -> float:
    import numpy as np
    import transforms3d as t3d

    left = np.asarray(before, dtype=np.float64)
    right = np.asarray(after, dtype=np.float64)
    left = left / np.linalg.norm(left)
    right = right / np.linalg.norm(right)
    rotation = t3d.quaternions.quat2mat(left) @ t3d.quaternions.quat2mat(right).T
    cosine = max(-1.0, min(1.0, (float(np.trace(rotation)) - 1.0) / 2.0))
    return float(math.acos(cosine))


def _capture_dual_arm_state(task: Any, scene_revision: str) -> dict[str, Any]:
    """Capture the stabilized provider state used by sequential route planning."""
    import numpy as np

    def arm_payload(entity: Any, gripper: Any) -> dict[str, Any]:
        qpos = [float(item) for item in entity.get_qpos()[:7]]
        joints = list(entity.get_active_joints())[:7]
        targets: list[float] = []
        for joint in joints:
            value = joint.get_drive_target()
            value = value[0] if isinstance(value, (list, tuple, np.ndarray)) else value
            targets.append(float(value))
        links: list[dict[str, Any]] = []
        for link in entity.get_links():
            pose = link.get_pose()
            links.append({
                "link_id": f"placeholder:{link.get_name()}",
                "link_name": str(link.get_name()),
                "pose_wxyz": [*map(float, pose.p), *map(float, pose.q)],
            })
        # build_dual_arm_state assigns the arm-qualified identity; remove the
        # temporary value only after preserving the provider link name.
        return {"qpos": qpos, "drive_target": targets, "gripper": float(gripper), "links": links}

    left = arm_payload(task.robot.left_entity, task.robot.get_left_gripper_val())
    right = arm_payload(task.robot.right_entity, task.robot.get_right_gripper_val())
    left["links"] = [{**item, "link_id": f"left:{item['link_name']}"} for item in left["links"]]
    right["links"] = [{**item, "link_id": f"right:{item['link_name']}"} for item in right["links"]]
    return build_dual_arm_state(
        scene_revision=scene_revision,
        state_revision=f"{scene_revision}:stabilized",
        frame_id="world",
        left=left,
        right=right,
        held_arm_policy="hold",
        provenance_refs=[f"artifact://simulation-probe/{scene_revision}/dual-arm-state"],
    )


def _capture_peer_projection(task: Any, state: Mapping[str, Any], selected_arm: str) -> dict[str, Any]:
    """Project the held arm using Curobo's native collision-sphere model.

    RoboTwin's SAPIEN links are mesh/convex geometry and cannot be represented
    safely by the old single-box extraction.  Curobo already owns a sphere
    approximation for the same robot model, so use that model at the captured
    hold qpos and transform its centers into the shared world frame.
    """
    import numpy as np
    import torch
    import transforms3d.quaternions as tquat

    peer_arm = "right" if selected_arm == "left" else "left"
    planner = task.robot.right_planner if peer_arm == "right" else task.robot.left_planner
    kinematics = getattr(getattr(planner, "motion_gen", None), "kinematics", None)
    get_spheres = getattr(kinematics, "get_robot_as_spheres", None)
    if not callable(get_spheres):
        raise SimulationProbeError("peer arm collision sphere model is unavailable")
    entity = task.robot.right_entity if peer_arm == "right" else task.robot.left_entity
    qpos = np.asarray(entity.get_qpos()[:7], dtype=np.float32).reshape(1, -1)
    tensor_args = getattr(planner.motion_gen, "tensor_args", None)
    device = getattr(tensor_args, "device", "cpu")
    try:
        sphere_batches = get_spheres(torch.as_tensor(qpos, device=device), filter_valid=True)
    except Exception as exc:
        raise SimulationProbeError("peer arm collision sphere model failed") from exc
    if not sphere_batches or not sphere_batches[0]:
        raise SimulationProbeError("peer arm collision sphere model is empty")
    base = planner.robot_origion_pose
    base_rotation = np.asarray(tquat.quat2mat(list(base.q)), dtype=np.float64)
    base_position = np.asarray(base.p, dtype=np.float64)
    spheres: list[dict[str, Any]] = []
    for sphere in sphere_batches[0]:
        pose = getattr(sphere, "pose", None)
        radius = getattr(sphere, "radius", None)
        if pose is None or radius is None or len(pose) < 3:
            raise SimulationProbeError("peer arm collision sphere record is invalid")
        center = base_position + base_rotation @ np.asarray(pose[:3], dtype=np.float64)
        spheres.append({"center_m": [*map(float, center)], "radius_m": float(radius)})
    try:
        return build_peer_arm_sphere_projection(
            scene_revision=state["scene_revision"],
            state_revision=state["state_revision"],
            frame_id=state["frame_id"],
            selected_arm=selected_arm,
            spheres=spheres,
            source_ref=state["provenance_refs"][0],
        )
    except DualArmStateError as exc:
        raise SimulationProbeError("peer arm projection is invalid") from exc


def _validate_approval(
    root: Path,
    ref: str,
    *,
    producer_id: str,
    producer_profile_sha256: str,
    request: Mapping[str, Any],
    candidate_ref: str,
    profile: Mapping[str, Any],
) -> dict[str, Any]:
    approval = _load_json_artifact(root, ref)
    required = {
        "schema_version", "decision", "motion_authorized", "producer_id",
        "producer_profile_sha256", "task_name", "scene_revision", "embodiment_binding",
        "request_id", "candidate_ref", "route_geometry_digest", "reviewer_id", "reviewed_at",
        "calibration_sha256", "joint_limits_sha256", "stop_policy_sha256",
        "route_request_sha256", "source_manifest_ref", "source_manifest_sha256",
        "runtime_profile_sha256",
        "object_robot_target_transform_sha256", "placement_target_sha256",
        "controller_qualification_ref", "controller_qualification_sha256",
        "simulation_probe_worker_sha256",
    }
    if set(approval) != required or approval["schema_version"] != APPROVAL_SCHEMA_VERSION:
        raise SimulationProbeError("probe approval record fields are invalid")
    if approval["decision"] != "approved_independent_simulation_probe" or approval["motion_authorized"] is not True:
        raise SimulationProbeError("probe approval does not authorize simulation probe")
    if approval["producer_id"] != producer_id or approval["producer_profile_sha256"] != producer_profile_sha256:
        raise SimulationProbeError("probe approval producer binding is invalid")
    if approval["simulation_probe_worker_sha256"] != _sha_bytes(Path(__file__).read_bytes()):
        raise SimulationProbeError("probe approval worker source binding is invalid")
    if approval["task_name"] != profile["task_name"] or approval["scene_revision"] != request["scene_revision"]:
        raise SimulationProbeError("probe approval scene binding is invalid")
    if (
        approval["request_id"] != request["request_id"]
        or approval["candidate_ref"] != candidate_ref
        or approval["route_geometry_digest"] != route_geometry_digest(request)
        or approval["controller_qualification_ref"]
        != request["controller_qualification"]["artifact_ref"]
        or approval["controller_qualification_sha256"]
        != request["controller_qualification"]["sha256"]
    ):
        raise SimulationProbeError("probe approval route binding is invalid")
    if approval["embodiment_binding"] != profile["embodiment_binding"]:
        raise SimulationProbeError("probe approval embodiment binding is invalid")
    if approval["runtime_profile_sha256"] != profile["runtime_profile_sha256"]:
        raise SimulationProbeError("probe approval runtime profile binding is invalid")
    request_digest = _sha_bytes(
        (json.dumps(request, sort_keys=True, separators=(",", ":")) + "\n").encode()
    )
    if approval["route_request_sha256"] != request_digest:
        raise SimulationProbeError("probe approval route request digest binding is invalid")
    for digest_field, ref_field in (
        ("calibration_sha256", "calibration_ref"),
        ("joint_limits_sha256", "joint_limits_ref"),
        ("stop_policy_sha256", "stop_policy_ref"),
    ):
        expected_digest = approval[digest_field]
        if (
            not isinstance(expected_digest, str)
            or len(expected_digest) != 64
            or any(char not in "0123456789abcdef" for char in expected_digest)
            or expected_digest
            != _sha_bytes(_artifact_path(root, request[ref_field]).read_bytes())
        ):
            raise SimulationProbeError(f"probe approval {ref_field} digest binding is invalid")
    selected = next(
        (item for item in request["candidates"] if item["candidate_ref"] == candidate_ref),
        None,
    )
    if selected is None:
        raise SimulationProbeError("probe approval candidate binding is invalid")
    for digest_field, ref_value in (
        (
            "object_robot_target_transform_sha256",
            selected["attached_object"]["transform_provenance_ref"],
        ),
        ("placement_target_sha256", selected["placement_target"]["provenance_ref"]),
        ("source_manifest_sha256", approval["source_manifest_ref"]),
    ):
        expected_digest = approval[digest_field]
        if (
            not isinstance(expected_digest, str)
            or len(expected_digest) != 64
            or any(char not in "0123456789abcdef" for char in expected_digest)
            or expected_digest != _sha_bytes(_artifact_path(root, ref_value).read_bytes())
        ):
            raise SimulationProbeError(f"probe approval {digest_field} binding is invalid")
    manifest = _load_json_artifact(root, approval["source_manifest_ref"])
    if (
        manifest.get("schema_version") != "paos-robotwin20-route-source-manifest/v4"
        or manifest.get("request_id") != request["request_id"]
        or manifest.get("candidate_ref") != candidate_ref
        or manifest.get("scene_revision") != request["scene_revision"]
        or manifest.get("route_geometry_digest") != route_geometry_digest(request)
        or manifest.get("route_request", {}).get("sha256") != approval["route_request_sha256"]
        or manifest.get("runtime_profile_sha256") != approval["runtime_profile_sha256"]
        or manifest.get("simulation_probe_worker_sha256")
        != approval["simulation_probe_worker_sha256"]
        or manifest.get("object_robot_target_transform", {}).get("sha256")
        != approval["object_robot_target_transform_sha256"]
        or manifest.get("placement_target", {}).get("sha256") != approval["placement_target_sha256"]
        or manifest.get("motion_capabilities") != request["motion_capabilities"]
        or manifest.get("controller_qualification")
        != request["controller_qualification"]
        or manifest.get("motion_authorized") is not False
    ):
        raise SimulationProbeError("probe approval source manifest binding is invalid")
    if not isinstance(approval["reviewer_id"], str) or not approval["reviewer_id"].strip():
        raise SimulationProbeError("probe approval reviewer is missing")
    if not isinstance(approval["reviewed_at"], str) or not approval["reviewed_at"].strip():
        raise SimulationProbeError("probe approval timestamp is missing")
    try:
        parsed = datetime.fromisoformat(approval["reviewed_at"])
    except ValueError as exc:
        raise SimulationProbeError("probe approval timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise SimulationProbeError("probe approval timestamp must include timezone")
    return dict(approval)


def _route_pose(pose_value: Mapping[str, Any], route_frame_id: str) -> list[float]:
    import numpy as np
    import transforms3d as t3d

    if pose_value.get("frame_id") != route_frame_id:
        raise SimulationProbeError("route pose frame binding is invalid")
    q = np.asarray(pose_value["orientation_xyzw"], dtype=np.float64)
    norm = float(np.linalg.norm(q))
    if norm <= 1e-9 or not math.isfinite(norm):
        raise SimulationProbeError("candidate orientation is degenerate")
    q = q / norm
    position = np.asarray(pose_value["position_m"], dtype=np.float64)
    if position.shape != (3,) or not bool(np.isfinite(position).all()):
        raise SimulationProbeError("route pose position is invalid")
    q_wxyz = t3d.quaternions.mat2quat(
        t3d.quaternions.quat2mat([q[3], q[0], q[1], q[2]])
    )
    return position.tolist() + q_wxyz.tolist()


def _contact_state(
    task: Any,
    *,
    phase: str,
    step: int,
    attached: bool = False,
) -> list[dict[str, Any]]:
    link_identity: dict[int, str] = {}
    by_name: dict[str, list[str]] = {}
    entities = []
    for arm_id in ("left", "right"):
        entity = getattr(task.robot, f"{arm_id}_entity", None)
        if entity is not None and callable(getattr(entity, "get_links", None)):
            entities.append((arm_id, entity))
    for arm_id, entity in entities:
        for link in entity.get_links():
            qualified = f"{arm_id}:{link.get_name()}"
            link_identity[id(link)] = qualified
            for attribute in ("entity", "component"):
                owner = getattr(link, attribute, None)
                if owner is not None:
                    link_identity[id(owner)] = qualified
            getter = getattr(link, "get_entity", None)
            if callable(getter):
                owner = getter()
                if owner is not None:
                    link_identity[id(owner)] = qualified
            by_name.setdefault(str(link.get_name()), []).append(qualified)

    def body_name(body: Any) -> str:
        for candidate in (body, getattr(body, "entity", None)):
            if candidate is None:
                continue
            qualified = link_identity.get(id(candidate))
            if qualified is not None:
                return qualified
        raw_entity = getattr(body, "entity", None)
        raw = str(getattr(raw_entity, "name", getattr(body, "name", "")))
        candidates = by_name.get(raw, [])
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            return f"ambiguous:{raw}"
        return raw

    records: list[dict[str, Any]] = []
    for contact in task.scene.get_contacts():
        left = body_name(contact.bodies[0])
        right = body_name(contact.bodies[1])
        impulses: list[float] = []
        for point in contact.points:
            try:
                vector = [float(item) for item in point.impulse]
            except (AttributeError, TypeError, ValueError) as exc:
                raise SimulationProbeError("simulator contact impulse is unavailable") from exc
            if len(vector) != 3 or any(not math.isfinite(item) for item in vector):
                raise SimulationProbeError("simulator contact impulse is invalid")
            impulses.append(math.sqrt(sum(item * item for item in vector)))
        max_impulse = max(impulses, default=0.0)
        records.append(
            {
                "phase": phase,
                "step": step,
                "pair": sorted((left, right)),
                "body_roles": [
                    "robot_link" if ":" in left and not left.startswith("ambiguous:") else left,
                    "robot_link" if ":" in right and not right.startswith("ambiguous:") else right,
                ],
                "point_count": len(impulses),
                "max_impulse_ns": max_impulse,
                "active_contact": max_impulse > 1e-6,
                "attached_object_active": attached,
            }
        )
    return records


def _snapshot(
    task: Any,
    request: Mapping[str, Any],
    candidate: Mapping[str, Any],
    dual_arm_state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    actors: dict[str, Any] = {}
    for actor in task.scene.get_all_actors():
        pose = actor.get_pose()
        actors[str(actor.get_name())] = {"position_m": pose.p.tolist(), "orientation_wxyz": pose.q.tolist()}
    robot = task.robot
    state = {
        "actors": actors,
        "left_qpos": robot.left_entity.get_qpos().tolist(),
        "right_qpos": robot.right_entity.get_qpos().tolist(),
        "left_gripper": float(robot.get_left_gripper_val()),
        "right_gripper": float(robot.get_right_gripper_val()),
        "contacts": _contact_state(task, phase="snapshot", step=0),
    }
    encoded = json.dumps(state, sort_keys=True, separators=(",", ":")).encode("utf-8")
    target = _actor_for_entity(task, candidate["entity_ref"])
    target_pose = target.get_pose()
    snapshot = {
        **{key: request[key] for key in _STATE_FIELDS},
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "state_digest": _sha_bytes(encoded),
        "target_entity_ref": candidate["entity_ref"],
        "target_actor": str(target.get_name()),
        "target_pose": {
            "position_m": target_pose.p.tolist(),
            "orientation_wxyz": target_pose.q.tolist(),
        },
        "robot_grippers": {
            "left": float(robot.get_left_gripper_val()),
            "right": float(robot.get_right_gripper_val()),
        },
    }
    if dual_arm_state is not None:
        snapshot["dual_arm_state"] = dict(dual_arm_state)
    return snapshot


def _actor_for_entity(task: Any, entity_ref: str) -> Any:
    mapping = {
        "entity://block-red-1": "block1",
        "entity://block-green-1": "block2",
        "entity://block-blue-1": "block3",
    }
    name = mapping.get(entity_ref)
    if name is None or not hasattr(task, name):
        raise SimulationProbeError("probe entity is not supported by task profile")
    return getattr(task, name)


def _label_probe_actors(task: Any) -> None:
    """Give task entities stable identities before collecting contact evidence.

    RoboTwin's block task names every block ``box``.  Contact traces using that
    name cannot prove that the requested entity, rather than another block,
    touched the gripper or support surface.  Renaming the probe-local actors is
    metadata-only and does not alter geometry or dynamics.
    """
    for entity_ref, attribute in (
        ("entity://block-red-1", "block1"),
        ("entity://block-green-1", "block2"),
        ("entity://block-blue-1", "block3"),
    ):
        actor = getattr(task, attribute, None)
        set_name = getattr(actor, "set_name", None)
        if actor is None or not callable(set_name):
            raise SimulationProbeError("probe actor identity cannot be made unique")
        set_name(entity_ref.removeprefix("entity://"))


def _joint_limits(planner: Any) -> list[list[float]]:
    try:
        kinematics = planner.motion_gen.robot_cfg.kinematics
        limits = getattr(kinematics, "joint_limits", None)
        if limits is None:
            limits = kinematics.kinematics_config.joint_limits
        tensor = limits.position
        values = tensor.detach().cpu().tolist()
    except Exception as exc:
        raise SimulationProbeError("planner joint limits are unavailable") from exc
    if not isinstance(values, list) or len(values) != 2 or any(len(row) != 7 for row in values):
        raise SimulationProbeError("planner joint limits have unexpected shape")
    converted = [[float(item) for item in row] for row in values]
    if any(not math.isfinite(item) for row in converted for item in row) or any(
        low >= high for low, high in zip(converted[0], converted[1])
    ):
        raise SimulationProbeError("planner joint limits are invalid")
    return converted


def _validate_trajectory(
    result: Mapping[str, Any],
    limits: list[list[float]],
) -> None:
    import numpy as np

    if result.get("status") != "Success":
        raise SimulationProbeError("planner route segment failed")
    source_positions = np.asarray(result.get("position"))
    source_velocities = np.asarray(result.get("velocity"))
    if not np.issubdtype(source_positions.dtype, np.floating) or not np.issubdtype(
        source_velocities.dtype, np.floating
    ):
        raise SimulationProbeError("planner trajectory dtype is not floating point")
    positions = source_positions.astype(np.float64, copy=False)
    velocities = source_velocities.astype(np.float64, copy=False)
    if positions.ndim != 2 or positions.shape[1] != 7 or velocities.shape != positions.shape:
        raise SimulationProbeError("planner trajectory shape is invalid")
    if not np.isfinite(positions).all() or not np.isfinite(velocities).all():
        raise SimulationProbeError("planner trajectory contains non-finite values")
    low, high = np.asarray(limits[0]), np.asarray(limits[1])
    if bool((positions < low - 1e-5).any()) or bool((positions > high + 1e-5).any()):
        raise SimulationProbeError("planner trajectory exceeds joint limits")


def _validate_request_policies(
    root: Path,
    request: Mapping[str, Any],
    *,
    max_duration_s: float,
    robot_identity: str,
) -> dict[str, Any]:
    joint = _load_json_artifact(root, request["joint_limits_ref"])
    stop = _load_json_artifact(root, request["stop_policy_ref"])
    if set(joint) != {
        "schema_version", "planner_profile", "joint_count",
        "require_runtime_position_limits",
    } or joint["schema_version"] != "paos-robotwin20-joint-limit-policy/v2":
        raise SimulationProbeError("joint-limit policy fields are invalid")
    if (
        joint["planner_profile"] != "curobo"
        or joint["joint_count"] != 7
        or joint["require_runtime_position_limits"] is not True
    ):
        raise SimulationProbeError("joint-limit policy is invalid")
    if set(stop) != {
        "schema_version", "max_duration_s", "stop_file_required",
        "poll_each_step", "failure_recovery",
    } or stop["schema_version"] != "paos-robotwin20-stop-policy/v1":
        raise SimulationProbeError("stop policy fields are invalid")
    if (
        isinstance(stop["max_duration_s"], bool)
        or not isinstance(stop["max_duration_s"], (int, float))
        or not math.isclose(float(stop["max_duration_s"]), max_duration_s, abs_tol=1e-9)
        or stop["stop_file_required"] is not True
        or stop["poll_each_step"] is not True
        or stop["failure_recovery"] != "reset_simulation"
    ):
        raise SimulationProbeError("stop policy is invalid")
    validated_arms: set[str] = set()
    capabilities: dict[str, MotionCapabilityDocument] = {}
    for binding in request["motion_capabilities"]:
        capability_payload = _load_json_artifact(root, binding["artifact_ref"])
        validation_payload = _load_json_artifact(root, binding["validation_ref"])
        try:
            capability = MotionCapabilityDocument.model_validate(capability_payload)
            validation = MotionCapabilityValidation.model_validate(validation_payload)
        except ValueError as exc:
            raise SimulationProbeError("motion capability artifact is invalid") from exc
        capability_path = _artifact_path(root, binding["artifact_ref"])
        validation_path = _artifact_path(root, binding["validation_ref"])
        if (
            capability.robot_identity != robot_identity
            or capability.arm_id != binding["arm_id"]
            or _sha_bytes(capability_path.read_bytes()) != binding["sha256"]
            or motion_capability_digest(capability) != binding["sha256"]
            or _sha_bytes(validation_path.read_bytes()) != binding["validation_sha256"]
            or validation.capability_sha256 != binding["sha256"]
        ):
            raise SimulationProbeError("motion capability binding is invalid")
        validated_arms.add(capability.arm_id)
        capabilities[capability.arm_id] = capability
    if validated_arms != {"left", "right"}:
        raise SimulationProbeError("motion capability arm coverage is invalid")
    qualification_binding = request["controller_qualification"]
    try:
        qualification = ControllerQualification.model_validate(
            _load_json_artifact(root, qualification_binding["artifact_ref"])
        )
        plan = ControllerQualificationPlan.model_validate(
            _load_json_artifact(root, qualification_binding["plan_ref"])
        )
        evidence = ControllerQualificationEvidence.model_validate(
            _load_json_artifact(root, qualification_binding["evidence_ref"])
        )
        qualification_validation = ControllerQualificationValidation.model_validate(
            _load_json_artifact(root, qualification_binding["validation_ref"])
        )
        validate_controller_qualification_result_package(
            qualification=qualification,
            plan=plan,
            evidence=evidence,
            validation=qualification_validation,
            qualification_file_sha256=_sha_bytes(
                _artifact_path(root, qualification_binding["artifact_ref"]).read_bytes()
            ),
            plan_file_sha256=_sha_bytes(
                _artifact_path(root, qualification_binding["plan_ref"]).read_bytes()
            ),
            evidence_file_sha256=_sha_bytes(
                _artifact_path(root, qualification_binding["evidence_ref"]).read_bytes()
            ),
            validation_file_sha256=_sha_bytes(
                _artifact_path(root, qualification_binding["validation_ref"]).read_bytes()
            ),
        )
    except (ValueError, ControllerQualificationError) as exc:
        raise SimulationProbeError("controller qualification package is invalid") from exc
    if qualification_binding != {
        "qualification_id": qualification.qualification_id,
        "artifact_ref": qualification_binding["artifact_ref"],
        "sha256": controller_qualification_digest(qualification),
        "plan_ref": qualification.plan_ref,
        "plan_sha256": qualification.plan_sha256,
        "evidence_ref": qualification.evidence_ref,
        "evidence_sha256": qualification.evidence_sha256,
        "validation_ref": qualification.validation_ref,
        "validation_sha256": qualification.validation_sha256,
    }:
        raise SimulationProbeError("controller qualification route binding is invalid")
    plan_bindings = {
        item.arm_id: item.model_dump(mode="json") for item in plan.capability_bindings
    }
    route_bindings = {
        item["arm_id"]: dict(item) for item in request["motion_capabilities"]
    }
    if plan_bindings != route_bindings:
        raise SimulationProbeError("controller qualification capability binding drifted")
    for capability in capabilities.values():
        provider = capability.provider
        identity = qualification.identity
        if (
            identity.robot_identity != capability.robot_identity
            or identity.simulator_id != provider.simulator_id
            or identity.simulator_version != provider.simulator_version
            or identity.controller_id != provider.controller_id
            or identity.controller_version != provider.controller_version
            or identity.runtime_python_version != provider.runtime_python_version
            or identity.robotwin_git_revision != provider.robotwin_git_revision
        ):
            raise SimulationProbeError("controller qualification provider identity drifted")
    return {
        "joint_limit_policy": dict(joint),
        "stop_policy": dict(stop),
        "controller_qualification": qualification_binding,
        "motion_capability_documents": capabilities,
        "execution_input_digests": {
            request["joint_limits_ref"]: _sha_bytes(
                _artifact_path(root, request["joint_limits_ref"]).read_bytes()
            ),
            request["stop_policy_ref"]: _sha_bytes(
                _artifact_path(root, request["stop_policy_ref"]).read_bytes()
            ),
            **{
                item[field]: item[digest_field]
                for item in request["motion_capabilities"]
                for field, digest_field in (
                    ("artifact_ref", "sha256"),
                    ("validation_ref", "validation_sha256"),
                )
            },
            qualification_binding["artifact_ref"]: qualification_binding["sha256"],
            qualification_binding["plan_ref"]: qualification_binding["plan_sha256"],
            qualification_binding["evidence_ref"]: qualification_binding["evidence_sha256"],
            qualification_binding["validation_ref"]: qualification_binding[
                "validation_sha256"
            ],
        },
    }


def _build_route_controllers(
    task: Any,
    capabilities: Mapping[str, MotionCapabilityDocument],
) -> dict[str, CapabilityBoundedDriveController]:
    _guard_controller_source_binding(capabilities)
    controllers: dict[str, CapabilityBoundedDriveController] = {}
    for arm_id in ("left", "right"):
        capability = capabilities.get(arm_id)
        if capability is None:
            raise SimulationProbeError("route controller capability coverage is incomplete")
        controllers[arm_id] = CapabilityBoundedDriveController(
            ControllerLimits(
                joint_order=capability.joint_order,
                position_lower_rad=capability.limits.position_lower_rad,
                position_upper_rad=capability.limits.position_upper_rad,
                velocity_lower_radps=capability.limits.velocity_lower_radps,
                velocity_upper_radps=capability.limits.velocity_upper_radps,
            ),
            lambda q, dq, selected_arm=arm_id: task.robot.set_arm_joints(
                q, dq, selected_arm
            ),
        )
    return controllers


def _controller_source_path() -> Path:
    module = sys.modules.get(CapabilityBoundedDriveController.__module__)
    module_path = Path(getattr(module, "__file__", "")) if module is not None else None
    if (
        module_path is None
        or not module_path.is_absolute()
        or not module_path.is_file()
        or module_path.is_symlink()
    ):
        raise SimulationProbeError("qualified controller source is unavailable")
    return module_path


def _guard_controller_source_digest(expected_digest: str) -> None:
    if _sha_bytes(_controller_source_path().read_bytes()) != expected_digest:
        raise SimulationProbeError("qualified controller source digest drifted")


def _guard_controller_source_binding(
    capabilities: Mapping[str, MotionCapabilityDocument],
) -> str:
    """Bind the controller imported by this worker to the qualified source.

    Qualification is meaningful only for the exact provider controller that
    will receive route commands.  A changed module, stale import, or a
    capability that still describes RoboTwin's unqualified native drive
    target must therefore fail before the first simulator step.
    """
    source_digest = _sha_bytes(_controller_source_path().read_bytes())
    expected_version = f"source-{source_digest[:16]}"
    for capability in capabilities.values():
        if capability.provider.controller_id != "paos-robotwin-capability-bounded-drive-target":
            raise SimulationProbeError("route controller is not the qualified bounded provider")
        controller_sources = [
            item for item in capability.sources if item.role == "controller_source"
        ]
        if len(controller_sources) != 1:
            raise SimulationProbeError("qualified controller source binding is incomplete")
        source = controller_sources[0]
        if source.sha256 != source_digest or capability.provider.controller_version != expected_version:
            raise SimulationProbeError("qualified controller source digest drifted")
    return source_digest


def _guard_execution_inputs(root: Path, bindings: Mapping[str, str]) -> None:
    for reference, expected_digest in bindings.items():
        if _sha_bytes(_artifact_path(root, reference).read_bytes()) != expected_digest:
            raise SimulationProbeError("simulation execution input digest drifted")


def _step_bounded_controller(
    task: Any,
    controller: CapabilityBoundedDriveController,
    execution_state: dict[str, Any],
) -> None:
    controller.before_step()
    try:
        task.scene.step()
    except Exception:
        controller.dropped_step()
        raise
    controller.after_step()
    held_arm = execution_state.get("held_arm")
    initial = execution_state.get("dual_arm_state")
    if held_arm and isinstance(initial, Mapping):
        try:
            current = _capture_dual_arm_state(task, initial["scene_revision"])
            drift = hold_drift(initial, current, arm_id=held_arm)
        except (DualArmStateError, KeyError) as exc:
            raise SimulationProbeError("held arm state could not be measured") from exc
        execution_state["held_arm_drift"] = drift
        if not drift["drive_target_unchanged"]:
            raise SimulationProbeError("held arm drive target drifted")


def _validate_world_pose(
    pose: list[float], bounds: Mapping[str, Any], half_extents: list[float]
) -> None:
    conservative_extent = max(half_extents)
    for axis, coordinate in zip("xyz", pose[:3]):
        if (
            coordinate - conservative_extent < float(bounds[f"{axis}_min_m"])
            or coordinate + conservative_extent > float(bounds[f"{axis}_max_m"])
        ):
            raise SimulationProbeError("world-frame route waypoint or attached object exceeds workspace bounds")


def _robot_link_names(task: Any) -> set[str]:
    names: set[str] = set()
    try:
        for entity in (task.robot.left_entity, task.robot.right_entity):
            names.update(str(link.get_name()) for link in entity.get_links())
    except Exception as exc:
        raise SimulationProbeError("robot link identities are unavailable") from exc
    if not names:
        raise SimulationProbeError("robot link identities are empty")
    return names


def _evaluate_contacts(task: Any, actor: Any, trace: list[dict[str, Any]]) -> dict[str, Any]:
    target = str(actor.get_name())
    grippers = {
        f"{arm}:{name}"
        for arm, entity in (("left", task.robot.left_entity), ("right", task.robot.right_entity))
        for name in task.robot.gripper_name
        if any(str(link.get_name()) == str(name) for link in entity.get_links())
    }
    robot_links = {
        f"{arm}:{link_name}"
        for arm, entity in (("left", task.robot.left_entity), ("right", task.robot.right_entity))
        for link_name in (str(link.get_name()) for link in entity.get_links())
    }
    unexpected: list[dict[str, Any]] = []
    target_gripper_phases: set[str] = set()
    target_support_phases: set[str] = set()
    for record in trace:
        pair = set(record["pair"])
        robot_members = pair & robot_links
        if record["active_contact"] and target in pair and pair & grippers:
            target_gripper_phases.add(record["phase"])
        if record["active_contact"] and target in pair and "table" in pair:
            target_support_phases.add(record["phase"])
        other = pair - robot_links
        if (
            record["active_contact"]
            and record["attached_object_active"]
            and robot_members
            and other
            and target not in other
        ):
            unexpected.append(record)
    grasp_contact = bool(target_gripper_phases & {"contact", "close", "lift"})
    placed_support = bool(target_support_phases & {"release", "retreat"})
    status = "pass" if grasp_contact and placed_support and not unexpected else "fail"
    return {
        "schema_version": "paos-robotwin20-contact-dynamics/v1",
        "status": status,
        "target_actor": target,
        "sample_count": len(trace),
        "target_gripper_contact_phases": sorted(target_gripper_phases),
        "target_support_contact_phases": sorted(target_support_phases),
        "required_events": {
            "grasp_contact_observed": grasp_contact,
            "placed_support_contact_observed": placed_support,
        },
        "unexpected_robot_environment_contacts": unexpected,
        "trace": trace,
    }


def _attach_object_to_planner(
    task: Any, planner: Any, actor: Any, half_extents: list[float], arm: str
) -> dict[str, Any]:
    """Attach the observed object geometry to Curobo's dedicated attached link."""
    try:
        import numpy as np
        import torch
        from curobo.geom.types import Cuboid
        from curobo.types.robot import JointState

        base_pose = np.asarray(list(planner.robot_origion_pose.p) + list(planner.robot_origion_pose.q), dtype=np.float64)
        object_pose = np.asarray(list(actor.get_pose().p) + list(actor.get_pose().q), dtype=np.float64)
        base_position, base_quaternion = planner._trans_from_world_to_base(base_pose, object_pose)
        obstacle = Cuboid(
            name="probe_attached_object",
            pose=list(base_position) + list(base_quaternion),
            dims=[2.0 * float(item) for item in half_extents],
        )
        entity = task.robot.left_entity if arm == "left" else task.robot.right_entity
        qpos = entity.get_qpos()
        joint_state = JointState.from_position(
            torch.tensor(qpos[:7], dtype=torch.float32, device="cuda").reshape(1, -1),
            joint_names=planner.active_joints_name,
        )
        surface_sphere_radius_m = 0.001
        link_name = "attached_object"
        if not planner.motion_gen.attach_external_objects_to_robot(
            joint_state,
            [obstacle],
            surface_sphere_radius=surface_sphere_radius_m,
            link_name=link_name,
        ):
            raise SimulationProbeError("planner rejected attached object geometry")
        return {
            "status": "attached",
            "planner_link_name": link_name,
            "object_name": obstacle.name,
            "object_dimensions_m": [2.0 * float(item) for item in half_extents],
            "surface_sphere_radius_m": surface_sphere_radius_m,
            "active_route_phases": ["lift", "transport", "descent", "release"],
        }
    except SimulationProbeError:
        raise
    except Exception as exc:
        raise SimulationProbeError("attached object geometry could not be added to planner") from exc


def _execute_segment(
    task: Any,
    arm: str,
    result: Mapping[str, Any],
    *,
    phase: str,
    deadline: float,
    stop_file: Path | None,
    contacts: list[dict[str, Any]],
    execution_state: dict[str, Any],
) -> None:
    import numpy as np

    positions = result["position"]
    velocities = result["velocity"]
    velocities = np.asarray(velocities, dtype=np.float64)
    ee = task.robot.get_left_ee_pose if arm == "left" else task.robot.get_right_ee_pose
    timestep = float(task.scene.get_timestep())
    if not math.isfinite(timestep) or timestep <= 0:
        raise SimulationProbeError("simulator timestep is invalid")
    previous_position = np.asarray(ee()[:3], dtype=np.float64)
    controller = execution_state["_controllers"][arm]
    for index in range(len(positions)):
        if time.monotonic() >= deadline:
            raise TimeoutError("simulation probe exceeded max duration")
        if stop_file is not None and stop_file.exists():
            for item in execution_state["_controllers"].values():
                item.stop()
            raise InterruptedError("simulation probe stop requested")
        _guard_execution_inputs(
            execution_state["_artifact_root"],
            execution_state["_execution_input_digests"],
        )
        _guard_controller_source_digest(execution_state["_controller_source_sha256"])
        controller.command(positions[index], velocities[index])
        execution_state["world_change_started"] = True
        execution_state["phase"] = phase
        _step_bounded_controller(task, controller, execution_state)
        execution_state["simulator_steps"] += 1
        current_position = np.asarray(ee()[:3], dtype=np.float64)
        displacement = current_position - previous_position
        linear_speed = float(np.linalg.norm(displacement) / timestep)
        if not math.isfinite(linear_speed):
            raise SimulationProbeError("simulator reported a non-finite end-effector speed")
        execution_state["max_observed_linear_speed_mps"] = max(
            execution_state.get("max_observed_linear_speed_mps", 0.0), linear_speed
        )
        previous_position = current_position
        contacts.extend(
            _contact_state(
                task,
                phase=phase,
                step=execution_state["simulator_steps"],
                attached=bool(execution_state["planner_object_attached"]),
            )
        )


def _set_gripper(
    task: Any,
    arm: str,
    value: float,
    *,
    phase: str,
    deadline: float,
    stop_file: Path | None,
    contacts: list[dict[str, Any]],
    execution_state: dict[str, Any],
) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SimulationProbeError("gripper command must be a finite normalized number")
    normalized_value = float(value)
    if not math.isfinite(normalized_value) or not 0.0 <= normalized_value <= 1.0:
        raise SimulationProbeError("gripper command is outside provider normalized bounds")
    controller = execution_state["_controllers"][arm]
    entity = task.robot.left_entity if arm == "left" else task.robot.right_entity
    for _ in range(20):
        if time.monotonic() >= deadline:
            raise TimeoutError("simulation probe exceeded max duration")
        if stop_file is not None and stop_file.exists():
            for item in execution_state["_controllers"].values():
                item.stop()
            raise InterruptedError("simulation probe stop requested")
        _guard_execution_inputs(
            execution_state["_artifact_root"],
            execution_state["_execution_input_digests"],
        )
        _guard_controller_source_digest(execution_state["_controller_source_sha256"])
        current_position = [float(item) for item in entity.get_qpos()[:7]]
        controller.command(current_position, [0.0] * len(current_position))
        task.robot.set_gripper(normalized_value, arm)
        execution_state["world_change_started"] = True
        execution_state["phase"] = phase
        _step_bounded_controller(task, controller, execution_state)
        execution_state["simulator_steps"] += 1
        contacts.extend(
            _contact_state(
                task,
                phase=phase,
                step=execution_state["simulator_steps"],
                attached=bool(execution_state["planner_object_attached"]),
            )
        )


def _run_candidate(
    task: Any,
    request: Mapping[str, Any],
    candidate: Mapping[str, Any],
    policies: Mapping[str, Any],
    *,
    deadline: float,
    stop_file: Path | None,
    execution_state: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], str]:
    import numpy as np

    actor = _actor_for_entity(task, candidate["entity_ref"])
    before_actor = np.asarray(actor.get_pose().p, dtype=np.float64).copy()
    route_records: list[dict[str, Any]] = []
    contact_trace: list[dict[str, Any]] = []
    execution_state["contact_trace"] = contact_trace
    arm_results: dict[str, tuple[list[list[float]], Any]] = {}
    arm_attempts: list[dict[str, Any]] = []
    execution_state["arm_selection_attempts"] = arm_attempts
    for arm in ("left", "right"):
        planner = task.robot.left_planner if arm == "left" else task.robot.right_planner
        limits = _joint_limits(planner)
        try:
            pose = _route_pose(
                candidate["execution_grasp"]["robot_target_pose"], request["frame_id"]
            )
            fn = task.robot.left_plan_path if arm == "left" else task.robot.right_plan_path
            result = fn(pose)
            _validate_trajectory(result, limits)
            arm_results[arm] = (limits, result)
            arm_attempts.append({"arm": arm, "status": "pass"})
        except Exception as exc:
            arm_attempts.append(
                {"arm": arm, "status": "fail", "error": type(exc).__name__, "detail": str(exc)}
            )
            continue
    if not arm_results:
        raise SimulationProbeError("no arm can plan candidate route")
    arm = next(iter(arm_results))
    execution_state["held_arm"] = "right" if arm == "left" else "left"
    planner = task.robot.left_planner if arm == "left" else task.robot.right_planner
    execution_state["_planner"] = planner
    limits = _joint_limits(planner)
    fn = task.robot.left_plan_path if arm == "left" else task.robot.right_plan_path
    task.need_plan = True
    half_extents = [float(item) for item in candidate["attached_object"]["half_extents_m"]]
    attached_model: dict[str, Any] | None = None
    detached = False
    for phase in candidate["route"]:
        phase_name = phase["phase"]
        execution_state["phase"] = phase_name
        world_waypoints = []
        for waypoint in phase["waypoints"]:
            world_pose = _route_pose(waypoint, request["frame_id"])
            _validate_world_pose(world_pose, request["workspace_bounds_m"], half_extents)
            world_waypoints.append(world_pose)
        planned_segments = []
        for route_waypoint, waypoint in zip(phase["waypoints"], world_waypoints):
            result = fn(waypoint)
            _validate_trajectory(result, limits)
            planned_segments.append(
                {
                    "route_waypoint": route_waypoint,
                    "world_pose_pq_wxyz": waypoint,
                    "position": np.asarray(result["position"], dtype=np.float64).tolist(),
                    "velocity": np.asarray(result["velocity"], dtype=np.float64).tolist(),
                }
            )
            _execute_segment(
                task,
                arm,
                result,
                phase=phase_name,
                deadline=deadline,
                stop_file=stop_file,
                contacts=contact_trace,
                execution_state=execution_state,
            )
        _set_gripper(
            task,
            arm,
            _GRIPPER_VALUES[phase["gripper_state"]],
            phase=phase_name,
            deadline=deadline,
            stop_file=stop_file,
            contacts=contact_trace,
            execution_state=execution_state,
        )
        if phase_name == "lift":
            lift_z = float(actor.get_pose().p[2])
            if not math.isfinite(lift_z) or lift_z - float(before_actor[2]) < 0.01:
                raise SimulationProbeError("attached object did not lift with the gripper")
            execution_state["object_lifted"] = True
        elif phase_name in {"transport", "descent"} and not execution_state.get("object_lifted"):
            raise SimulationProbeError("attached route advanced without verified object lift")
        if phase_name == "close":
            attached_model = _attach_object_to_planner(
                task,
                planner,
                actor,
                half_extents,
                arm,
            )
            execution_state["planner_object_attached"] = True
        elif phase_name == "release":
            try:
                planner.motion_gen.detach_object_from_robot()
                detached = True
                execution_state["planner_object_attached"] = False
            except Exception as exc:
                raise SimulationProbeError("planner could not detach object after release") from exc
        route_records.append(
            {
                "phase": phase_name,
                "arm": arm,
                "waypoint_count": len(world_waypoints),
                "trajectory_steps": sum(len(item["position"]) for item in planned_segments),
                "segments": planned_segments,
            }
        )
    after_actor = np.asarray(actor.get_pose().p, dtype=np.float64).copy()
    if not np.isfinite(after_actor).all() or float(np.linalg.norm(after_actor - before_actor)) < 1e-4:
        raise SimulationProbeError("simulation route did not change target actor state")
    gripper_open = task.robot.get_left_gripper_val() if arm == "left" else task.robot.get_right_gripper_val()
    if float(gripper_open) < 0.8:
        raise SimulationProbeError("simulation route did not release target actor")
    trajectory = {
        "schema_version": "paos-robotwin20-simulation-trajectory/v1",
        "request_id": request["request_id"],
        "candidate_ref": candidate["candidate_ref"],
        "scene_revision": request["scene_revision"],
        "arm": arm,
        "arm_selection_attempts": arm_attempts,
        "held_arm": execution_state.get("held_arm"),
        "held_arm_policy": execution_state.get("dual_arm_state", {}).get("held_arm_policy"),
        "held_arm_drift": execution_state.get("held_arm_drift"),
        "phases": route_records,
        "contact_samples": len(contact_trace),
    }
    joint_limits = {
        "schema_version": "paos-robotwin20-joint-limits/v1",
        "planner_profile": "curobo",
        "arm": arm,
        "joint_limits": limits,
        "source_policy": policies["joint_limit_policy"],
        "max_observed_linear_speed_mps": execution_state.get(
            "max_observed_linear_speed_mps", 0.0
        ),
    }
    contact_dynamics = _evaluate_contacts(task, actor, contact_trace)
    collision = {
        "schema_version": "paos-robotwin20-attached-collision/v1",
        "collision_scope": "curobo_attached_object_and_sapien_robot_environment_contacts",
        "target_actor": str(actor.get_name()),
        "sample_count": len(contact_trace),
        "planner_attached_model": attached_model,
        "planner_detached_after_release": detached,
        "collision_world_update": execution_state.get("collision_world_receipt"),
        "peer_arm_projection": execution_state.get("peer_arm_projection"),
        "unexpected_robot_environment_contacts": contact_dynamics[
            "unexpected_robot_environment_contacts"
        ],
        "status": (
            "pass"
            if attached_model is not None
            and detached
            and not contact_dynamics["unexpected_robot_environment_contacts"]
            else "fail"
        ),
    }
    if collision["status"] != "pass":
        raise SimulationProbeError("unexpected simulator contact during attached route")
    if contact_dynamics["status"] != "pass":
        raise SimulationProbeError("required grasp/place contact dynamics were not observed")
    return trajectory, joint_limits, collision, contact_dynamics, arm


def _recover_candidate_failure(
    *,
    backend: Any,
    task: Any,
    runtime_seed: int,
    artifact_root: Path,
    prefix: str,
    profile: Mapping[str, Any],
    producer_binding: Mapping[str, str],
    request: Mapping[str, Any],
    candidate: Mapping[str, Any],
    before_ref: Mapping[str, str] | None,
    execution_state: dict[str, Any],
    error: Exception,
) -> dict[str, Any]:
    """Detach, snapshot, and reset after any post-step probe failure."""
    planner = execution_state.pop("_planner", None)
    controller_stop_status = "not_initialized"
    controllers = execution_state.pop("_controllers", {})
    if controllers:
        controller_stop_status = "stopped"
        try:
            for controller in controllers.values():
                controller.stop()
        except ControllerCommandError:
            controller_stop_status = "stop_failed"
    detach_status = "not_attached"
    if execution_state["planner_object_attached"] and planner is not None:
        try:
            planner.motion_gen.detach_object_from_robot()
            detach_status = "detached_after_failure"
            execution_state["planner_object_attached"] = False
        except Exception:
            detach_status = "detach_failed"

    reconciliation_required = bool(execution_state["world_change_started"])
    after_failure_ref = None
    snapshot_error = None
    reset_status = "not_required"
    if execution_state["world_change_started"]:
        try:
            after_state = _capture_dual_arm_state(task, request["scene_revision"])
            after_failure = _snapshot(task, request, candidate, after_state)
            after_failure_ref = _json_artifact(
                artifact_root, prefix + "/after-failure-snapshot", after_failure
            )
        except Exception as snapshot_exc:
            snapshot_error = {
                "error": type(snapshot_exc).__name__,
                "detail": str(snapshot_exc),
            }
        reset_status = "failed"
        try:
            backend.reset(seed=runtime_seed)
            reset_status = "completed"
            reconciliation_required = False
        except Exception:
            reset_status = "failed"
    failure_ref = _json_artifact(
        artifact_root,
        prefix + "/failure",
        {
            "schema_version": "paos-robotwin20-simulation-probe-failure/v1",
            "request_id": request["request_id"],
            "candidate_ref": candidate["candidate_ref"],
            "scene_revision": request["scene_revision"],
            "error": type(error).__name__,
            "error_detail": str(error),
            "failed_phase": execution_state["phase"],
            "simulator_steps": execution_state["simulator_steps"],
            "linear_speed_violation": execution_state.get("linear_speed_violation"),
            "controller": execution_state.get("controller"),
            "arm_selection_attempts": execution_state.get("arm_selection_attempts", []),
            "contact_trace": execution_state.get("contact_trace", []),
            "planner_detach_status": detach_status,
            "simulation_reset_status": reset_status,
            "controller_stop_status": controller_stop_status,
            "before_snapshot": dict(before_ref) if before_ref is not None else None,
            "after_failure_snapshot": after_failure_ref,
            "after_failure_snapshot_error": snapshot_error,
        },
    )
    return {
        "request_id": request["request_id"],
        "schema_version": SCHEMA_VERSION,
        "status": "unavailable",
        "provider_available": True,
        "worker_id": profile["worker_id"],
        "producer_binding": dict(producer_binding),
        "motion_authorized": True,
        "world_change_started": execution_state["world_change_started"],
        "world_change_completed": False,
        "reconciliation_required": reconciliation_required,
        "failure_evidence": failure_ref,
        "error": type(error).__name__,
        "error_detail": str(error),
    }


def _finalize_candidate_success(
    *,
    task: Any,
    artifact_root: Path,
    approval_ref: str,
    worker_id: str,
    prefix: str,
    producer_binding: Mapping[str, str],
    request: Mapping[str, Any],
    candidate: Mapping[str, Any],
    before: Mapping[str, Any],
    before_ref: Mapping[str, str],
    trajectory: Mapping[str, Any],
    limits: Mapping[str, Any],
    collision: Mapping[str, Any],
    contact_dynamics: Mapping[str, Any],
    selected_arm: str,
    policies: Mapping[str, Any],
    placement_artifact: Mapping[str, Any],
    execution_state: dict[str, Any],
) -> dict[str, Any]:
    """Persist a complete success bundle; callers recover if any write fails."""
    import numpy as np

    execution_state["phase"] = "finalizing"
    execution_state.pop("_planner", None)
    after_state = _capture_dual_arm_state(task, request["scene_revision"])
    after = _snapshot(task, request, candidate, after_state)
    if before["state_digest"] == after["state_digest"]:
        raise SimulationProbeError("simulation probe before/after state did not change")
    trajectory_ref = _json_artifact(artifact_root, prefix + "/trajectory", trajectory)
    limits_ref = _json_artifact(artifact_root, prefix + "/joint-limits", limits)
    collision_ref = _json_artifact(artifact_root, prefix + "/attached-collision", collision)
    contact_ref = _json_artifact(
        artifact_root, prefix + "/contact-dynamics", contact_dynamics
    )
    stop_ref = _json_artifact(
        artifact_root,
        prefix + "/stop-control",
        {
            "schema_version": "paos-robotwin20-stop-control/v1",
            "status": "pass",
            "deadline_enforced": True,
            "stop_file_configured": True,
            "stop_file_polled_each_step": True,
            "stop_requested": False,
            "simulator_steps": execution_state["simulator_steps"],
            "scope": "worker_local_simulation_route",
            "source_policy": policies["stop_policy"],
        },
    )
    after_ref = _json_artifact(artifact_root, prefix + "/after-snapshot", after)
    displacement = float(
        np.linalg.norm(
            np.asarray(after["target_pose"]["position_m"], dtype=np.float64)
            - np.asarray(before["target_pose"]["position_m"], dtype=np.float64)
        )
    )
    selected_gripper = float(after["robot_grippers"][selected_arm])
    observed_outcome = {
        "schema_version": "paos-robotwin20-observed-route-outcome/v2",
        "after_snapshot_ref": after_ref["artifact_ref"],
        "target_displacement_m": displacement,
        "target_pose_changed": displacement >= 1e-4,
        "selected_arm": selected_arm,
        "selected_gripper_value": selected_gripper,
        "selected_gripper_open": selected_gripper >= 0.8,
    }
    tolerance = placement_artifact.get("semantic_tolerance")
    if not isinstance(tolerance, Mapping) or set(tolerance) != {"target_position_m", "target_orientation_rad"}:
        raise SimulationProbeError("placement semantic tolerance is unavailable")
    target_pose = placement_artifact.get("world_T_object_target")
    if not isinstance(target_pose, list) or len(target_pose) != 16:
        raise SimulationProbeError("placement target pose is unavailable")
    target_matrix = [target_pose[index : index + 4] for index in range(0, 16, 4)]
    actual_position = after["target_pose"]["position_m"]
    actual_orientation = after["target_pose"]["orientation_wxyz"]
    target_position = [float(target_matrix[index][3]) for index in range(3)]
    import numpy as np
    import transforms3d as t3d

    target_orientation = [
        float(item)
        for item in t3d.quaternions.mat2quat(
            np.asarray([row[:3] for row in target_matrix[:3]], dtype=float)
        )
    ]
    position_error = math.sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(actual_position, target_position)))
    orientation_error = _orientation_error_rad(actual_orientation, target_orientation)
    if position_error > float(tolerance["target_position_m"]) or orientation_error > float(tolerance["target_orientation_rad"]):
        raise SimulationProbeError("after-state semantic placement verification failed")
    observed_outcome.update(
        {
            "target_position_error_m": position_error,
            "target_orientation_error_rad": orientation_error,
            "semantic_verdict": "satisfied",
        }
    )
    outcome_ref = _json_artifact(
        artifact_root, prefix + "/observed-outcome", observed_outcome
    )
    evidence = {
        "schema_version": "paos-robotwin20-simulation-route-evidence/v2",
        "request_id": request["request_id"],
        "candidate_ref": candidate["candidate_ref"],
        "entity_ref": candidate["entity_ref"],
        "observation_ref": request["observation_ref"],
        "scene_revision": request["scene_revision"],
        "frame_id": request["frame_id"],
        "calibration_ref": request["calibration_ref"],
        "candidate_set_ref": request["candidate_set_ref"],
        "route_geometry_digest": route_geometry_digest(request),
        "planner": {
            "status": "pass",
            "planner_id": "robotwin20-curobo/v1",
            "trajectory": trajectory_ref,
            "joint_limits": limits_ref,
            "route_phase_order": list(ROUTE_PHASES),
        },
        "scopes": {
            "attached_object_collision": {
                "status": "pass",
                "evidence": collision_ref,
                "method": "curobo-attached-object-plus-sapien-contact/v1",
            },
            "complete_transport_descent_retreat": {
                "status": "pass",
                "evidence": trajectory_ref,
                "method": "curobo-segmented-route/v1",
            },
            "contact_dynamics": {
                "status": "pass",
                "evidence": contact_ref,
                "method": "sapien-phase-contact-impulse-trace/v1",
            },
            "workspace_and_joint_limits": {
                "status": "pass",
                "evidence": limits_ref,
                "method": "world-waypoint-plus-curobo-position-joint-speed-and-sapien-linear-speed/v1",
            },
            "stop_control": {
                "status": "pass",
                "evidence": stop_ref,
                "method": "worker-local-deadline-stop-file/v1",
            },
        },
        "before_snapshot": dict(before_ref),
        "after_snapshot": after_ref,
        "observed_outcome": observed_outcome,
        "observed_outcome_artifact": outcome_ref,
        "producer_binding": dict(producer_binding),
        "probe_execution": {
            "simulation_only": True,
            "motion_authorized": True,
            "world_change_started": True,
            "world_change_completed": True,
            "authorization": {
                "artifact_ref": approval_ref,
                "sha256": _sha_bytes(_artifact_path(artifact_root, approval_ref).read_bytes()),
            },
        },
    }
    return {
        "request_id": request["request_id"],
        "schema_version": SCHEMA_VERSION,
        "status": "available",
        "provider_available": True,
        "worker_id": worker_id,
        "producer_binding": evidence["producer_binding"],
        "motion_authorized": True,
        "world_change_started": True,
        "world_change_completed": True,
        "reconciliation_required": False,
        "external_evidence": evidence,
    }


def _handle_factory(profile: Mapping[str, Any], artifact_root: Path, *, producer_id: str, producer_profile_sha256: str, approval_ref: str, max_duration_s: float, stop_file: Path | None):
    from robotwin_backend import RoboTwinRuntimeProfile, RoboTwinSensorBackend, load_runtime_profile

    runtime_profile = load_runtime_profile(Path(profile["runtime_profile"]).resolve())
    backend = RoboTwinSensorBackend(
        RoboTwinRuntimeProfile(
            runtime_root=Path(profile["runtime_root"]),
            artifact_root=artifact_root,
            task_name=runtime_profile["task_name"],
            task_config=runtime_profile["task_config"],
            embodiment=runtime_profile["embodiment"],
        )
    )
    request_consumed = False

    def handle(message: Mapping[str, Any]) -> Mapping[str, Any]:
        nonlocal request_consumed
        if set(message) != {"request_id", "route_request", "candidate_ref", "calibration_ref"}:
            raise SimulationProbeError("simulation probe request fields are invalid")
        request = message["route_request"]
        validate_route_request(request)
        if message["request_id"] != request["request_id"] or message["calibration_ref"] != request["calibration_ref"]:
            raise SimulationProbeError("simulation probe request identity is invalid")
        if request["scene_revision"] != f"{runtime_profile['task_name']}-{runtime_profile['seed']}-1":
            raise SimulationProbeError("simulation probe scene revision is invalid")
        candidate = next((item for item in request["candidates"] if item["candidate_ref"] == message["candidate_ref"]), None)
        if candidate is None:
            raise SimulationProbeError("simulation probe candidate is not in request")
        producer_binding = {
            "producer_id": producer_id,
            "profile_sha256": producer_profile_sha256,
            "evidence_mode": "independent_simulation_probe",
        }
        if request_consumed:
            return {
                "request_id": request["request_id"],
                "schema_version": SCHEMA_VERSION,
                "status": "unavailable",
                "provider_available": True,
                "worker_id": profile["worker_id"],
                "producer_binding": producer_binding,
                "motion_authorized": False,
                "world_change_started": False,
                "world_change_completed": False,
                "reconciliation_required": False,
                "failure_evidence": None,
                "error": "SimulationProbeError",
                "error_detail": "simulation probe worker is single-use",
            }
        try:
            _validate_approval(
                artifact_root,
                approval_ref,
                producer_id=producer_id,
                producer_profile_sha256=producer_profile_sha256,
                request=request,
                candidate_ref=candidate["candidate_ref"],
                profile=profile,
            )
            geometry_ref = candidate["attached_object"]["geometry_ref"]
            geometry_path = _artifact_path(artifact_root, geometry_ref)
            if _sha_bytes(geometry_path.read_bytes()) != candidate["attached_object"]["geometry_sha256"]:
                raise SimulationProbeError("attached geometry artifact digest mismatch")
            route_input_artifacts = _validate_route_input_artifacts(
                artifact_root, request, candidate
            )
            policies = _validate_request_policies(
                artifact_root,
                request,
                max_duration_s=max_duration_s,
                robot_identity=profile["embodiment_binding"]["robot_identity"],
            )
            policies["execution_input_digests"][approval_ref] = _sha_bytes(
                _artifact_path(artifact_root, approval_ref).read_bytes()
            )
        except Exception as exc:
            return {
                "request_id": request["request_id"],
                "schema_version": SCHEMA_VERSION,
                "status": "unavailable",
                "provider_available": True,
                "worker_id": profile["worker_id"],
                "producer_binding": producer_binding,
                "motion_authorized": False,
                "world_change_started": False,
                "world_change_completed": False,
                "reconciliation_required": False,
                "failure_evidence": None,
                "error": type(exc).__name__,
                "error_detail": str(exc),
            }
        if stop_file is None:
            raise SimulationProbeError("simulation probe stop control is not configured")
        if stop_file.exists():
            return {
                "request_id": request["request_id"],
                "schema_version": SCHEMA_VERSION,
                "status": "unavailable",
                "provider_available": True,
                "worker_id": profile["worker_id"],
                "producer_binding": producer_binding,
                "motion_authorized": True,
                "world_change_started": False,
                "world_change_completed": False,
                "reconciliation_required": False,
                "error": "InterruptedError",
                "error_detail": "simulation probe stop requested before world change",
            }
        request_consumed = True
        execution_state: dict[str, Any] = {
            "world_change_started": False,
            "simulator_steps": 0,
            "phase": "scene_initialization",
            "planner_object_attached": False,
            "object_lifted": False,
        }
        prefix = (
            f"artifact://simulation-probe/{request['request_id']}/"
            f"{_candidate_token(candidate['candidate_ref'])}"
        )
        task = None
        before_ref = None
        try:
            # Scene initialization/reset itself mutates the isolated simulator,
            # even before a robot-control step.  Mark it before invoking the
            # backend so partial reset failures cannot masquerade as no-change.
            execution_state["world_change_started"] = True
            backend.reset(seed=runtime_profile["seed"])
            task = backend._task
            if task is None or not hasattr(task, "robot"):
                raise SimulationProbeError("RoboTwin simulation task is unavailable")
            if backend.snapshot().get("scene_revision") != request["scene_revision"]:
                raise SimulationProbeError("simulation backend revision binding is invalid")
            planning_state = _capture_dual_arm_state(task, request["scene_revision"])
            validate_dual_arm_state(planning_state)
            execution_state["dual_arm_state"] = planning_state
            execution_state["held_arm"] = "left"
            # Curobo exposes two independent single-arm planners in RoboTwin.
            # Label them before adding the opposite arm as a static obstacle so
            # a projection can never be silently applied to the wrong planner.
            task.robot.left_planner.arm_id = "left"
            task.robot.right_planner.arm_id = "right"
            execution_state["_controllers"] = _build_route_controllers(
                task, policies["motion_capability_documents"]
            )
            execution_state["_controller_source_sha256"] = (
                _guard_controller_source_binding(
                    policies["motion_capability_documents"]
                )
            )
            execution_state["_artifact_root"] = artifact_root
            execution_state["_execution_input_digests"] = policies[
                "execution_input_digests"
            ]
            collision_binding = request["collision_world"]
            collision_path = _artifact_path(artifact_root, collision_binding["artifact_ref"])
            collision_bytes = collision_path.read_bytes()
            collision_artifact = json.loads(collision_bytes.decode("utf-8"))
            if _sha_bytes(collision_bytes) != collision_binding["sha256"]:
                raise SimulationProbeError("collision world artifact digest mismatch")
            if collision_artifact.get("world_digest") != collision_binding["world_digest"]:
                raise SimulationProbeError("collision world digest binding is invalid")
            try:
                peer_projections = {
                    arm_id: _capture_peer_projection(task, planning_state, arm_id)
                    for arm_id in ("left", "right")
                }
                execution_state["peer_arm_projection"] = peer_projections
                execution_state["collision_world_receipt"] = apply_collision_world(
                    {"left": task.robot.left_planner, "right": task.robot.right_planner},
                    collision_artifact,
                    peer_projections=peer_projections,
                )
            except CuroboWorldPortError as exc:
                raise SimulationProbeError(str(exc)) from exc
            _label_probe_actors(task)
            _validate_runtime_route_input_binding(task, candidate, route_input_artifacts)
            start = time.monotonic()
            before = _snapshot(task, request, candidate, planning_state)
            deadline = start + max_duration_s
            # Persist the immutable pre-route state before any simulator step so a
            # failure can always be reconciled against the exact starting scene.
            before_ref = _json_artifact(artifact_root, prefix + "/before-snapshot", before)
            execution_state["phase"] = "preflight"
        except Exception as exc:
            return _recover_candidate_failure(
                backend=backend,
                task=task,
                runtime_seed=runtime_profile["seed"],
                artifact_root=artifact_root,
                prefix=prefix,
                profile=profile,
                producer_binding=producer_binding,
                request=request,
                candidate=candidate,
                before_ref=before_ref,
                execution_state=execution_state,
                error=exc,
            )
        try:
            trajectory, limits, collision, contact_dynamics, selected_arm = _run_candidate(
                task,
                request,
                candidate,
                policies,
                deadline=deadline,
                stop_file=stop_file,
                execution_state=execution_state,
            )
        except Exception as exc:
            return _recover_candidate_failure(
                backend=backend,
                task=task,
                runtime_seed=runtime_profile["seed"],
                artifact_root=artifact_root,
                prefix=prefix,
                profile=profile,
                producer_binding=producer_binding,
                request=request,
                candidate=candidate,
                before_ref=before_ref,
                execution_state=execution_state,
                error=exc,
            )
        try:
            return _finalize_candidate_success(
                task=task,
                artifact_root=artifact_root,
                approval_ref=approval_ref,
                worker_id=profile["worker_id"],
                prefix=prefix,
                producer_binding=producer_binding,
                request=request,
                candidate=candidate,
                before=before,
                before_ref=before_ref,
                trajectory=trajectory,
                limits=limits,
                collision=collision,
                contact_dynamics=contact_dynamics,
                selected_arm=selected_arm,
                policies=policies,
                execution_state=execution_state,
                placement_artifact=route_input_artifacts["placement"],
            )
        except Exception as exc:
            return _recover_candidate_failure(
                backend=backend,
                task=task,
                runtime_seed=runtime_profile["seed"],
                artifact_root=artifact_root,
                prefix=prefix,
                profile=profile,
                producer_binding=producer_binding,
                request=request,
                candidate=candidate,
                before_ref=before_ref,
                execution_state=execution_state,
                error=exc,
            )

    return backend, handle


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--runtime-profile", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--worker-id", required=True)
    parser.add_argument("--producer-id", required=True)
    parser.add_argument("--producer-profile-sha256", required=True)
    parser.add_argument("--approval-ref", required=True)
    parser.add_argument("--max-duration-s", type=float, default=300.0)
    parser.add_argument("--stop-file", type=Path)
    args = parser.parse_args()
    if not args.runtime_root.is_absolute() or not args.runtime_root.is_dir() or args.runtime_root.is_symlink():
        raise SystemExit("runtime root must be an absolute directory")
    if not args.artifact_root.is_absolute() or not args.artifact_root.is_dir() or args.artifact_root.is_symlink():
        raise SystemExit("artifact root must be an absolute directory")
    if len(args.producer_profile_sha256) != 64 or any(c not in "0123456789abcdef" for c in args.producer_profile_sha256):
        raise SystemExit("producer profile digest must be lowercase SHA-256")
    from robotwin_backend import load_runtime_profile

    runtime_profile = load_runtime_profile(args.runtime_profile.resolve())
    profile = {
        "worker_id": args.worker_id,
        "runtime_root": str(args.runtime_root.resolve()),
        "runtime_profile": str(args.runtime_profile.resolve()),
        "runtime_profile_sha256": _sha_bytes(args.runtime_profile.resolve().read_bytes()),
        "task_name": runtime_profile["task_name"],
        "scene_revision": f"{runtime_profile['task_name']}-{runtime_profile['seed']}-1",
        "embodiment_binding": {key: runtime_profile[key] for key in ("robot_identity", "gripper_identity", "embodiment_topology", "planner_profile")},
    }
    resolved_stop = args.stop_file.resolve() if args.stop_file else None
    if (
        resolved_stop is None
        or args.stop_file.is_symlink()
        or args.artifact_root.resolve() not in resolved_stop.parents
        or not resolved_stop.parent.is_dir()
    ):
        raise SystemExit("stop file must be a non-symlink path below artifact root")
    state: dict[str, Any] = {}

    def load() -> None:
        # Keep third-party runtime output off the JSONL protocol stream while
        # making the expensive import/backend construction observable as load.
        with redirect_stdout(sys.stderr):
            backend, handler = _handle_factory(
                profile,
                args.artifact_root.resolve(),
                producer_id=args.producer_id,
                producer_profile_sha256=args.producer_profile_sha256,
                approval_ref=args.approval_ref,
                max_duration_s=args.max_duration_s,
                stop_file=resolved_stop,
            )
        state["backend"] = backend
        state["handle"] = handler

    def handle(message: Mapping[str, Any]) -> Mapping[str, Any]:
        handler = state.get("handle")
        if not callable(handler):
            raise SimulationProbeError("simulation probe worker is not loaded")
        with redirect_stdout(sys.stderr):
            return handler(message)

    try:
        return serve("robotwin20-simulation-probe", load, handle, schema_version=SCHEMA_VERSION)
    finally:
        backend = state.get("backend")
        if backend is not None:
            backend.close()


if __name__ == "__main__":
    raise SystemExit(main())

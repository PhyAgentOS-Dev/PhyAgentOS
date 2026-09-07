"""Provider-owned state and peer-arm projection for sequential dual-arm plans.

The PAOS planning layer only consumes references to these values.  This module
does not call a planner or a simulator; it normalizes provider observations so
the RoboTwin runtime can keep the non-selected arm fixed and include its
collision geometry in the selected arm's world.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

DUAL_ARM_STATE_SCHEMA_VERSION = "paos-robotwin20-dual-arm-state/v1"
PEER_ARM_PROJECTION_SCHEMA_VERSION = "paos-robotwin20-peer-arm-projection/v1"
PEER_ARM_SPHERE_PROJECTION_SCHEMA_VERSION = "paos-robotwin20-peer-arm-projection/v2"


class DualArmStateError(ValueError):
    """A dual-arm state or peer projection is not usable for planning."""


def qualified_link_id(arm_id: str, link_name: str) -> str:
    if arm_id not in {"left", "right"} or not isinstance(link_name, str) or not link_name:
        raise DualArmStateError("arm-qualified link identity is invalid")
    return f"{arm_id}:{link_name}"


def _finite_vector(value: Any, length: int, label: str) -> list[float]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) != length:
        raise DualArmStateError(f"{label} must contain {length} numbers")
    result = [float(item) for item in value]
    if any(not math.isfinite(item) for item in result):
        raise DualArmStateError(f"{label} contains non-finite values")
    return result


def _arm_state(value: Mapping[str, Any], arm_id: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {"qpos", "drive_target", "gripper", "links"}:
        raise DualArmStateError(f"{arm_id} state fields are invalid")
    qpos = _finite_vector(value["qpos"], 7, f"{arm_id}.qpos")
    drive_target = _finite_vector(value["drive_target"], 7, f"{arm_id}.drive_target")
    gripper = float(value["gripper"])
    if not math.isfinite(gripper):
        raise DualArmStateError(f"{arm_id}.gripper is invalid")
    links = value["links"]
    if not isinstance(links, list) or not links:
        raise DualArmStateError(f"{arm_id}.links must be non-empty")
    normalized_links: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in links:
        if not isinstance(item, Mapping) or set(item) != {"link_id", "link_name", "pose_wxyz"}:
            raise DualArmStateError(f"{arm_id} link fields are invalid")
        link_name = item["link_name"]
        link_id = qualified_link_id(arm_id, link_name)
        if item["link_id"] != link_id or link_id in seen:
            raise DualArmStateError(f"{arm_id} link identity is invalid")
        seen.add(link_id)
        pose = _finite_vector(item["pose_wxyz"], 7, f"{link_id}.pose_wxyz")
        normalized_links.append({"link_id": link_id, "link_name": link_name, "pose_wxyz": pose})
    return {"qpos": qpos, "drive_target": drive_target, "gripper": gripper, "links": normalized_links}


def build_dual_arm_state(
    *,
    scene_revision: str,
    state_revision: str,
    frame_id: str,
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    held_arm_policy: str = "hold",
    selected_arm: str | None = None,
    provenance_refs: Sequence[str] = (),
) -> dict[str, Any]:
    if not isinstance(scene_revision, str) or not scene_revision:
        raise DualArmStateError("scene_revision is required")
    if not isinstance(state_revision, str) or not state_revision:
        raise DualArmStateError("state_revision is required")
    if frame_id != "world":
        raise DualArmStateError("dual-arm state frame must be world")
    if held_arm_policy not in {"hold", "park", "static_projection"}:
        raise DualArmStateError("held_arm_policy is unsupported")
    if selected_arm not in {None, "left", "right"}:
        raise DualArmStateError("selected_arm is invalid")
    refs = list(provenance_refs)
    if any(not isinstance(item, str) or not item.startswith("artifact://") for item in refs):
        raise DualArmStateError("state provenance_refs are invalid")
    return {
        "schema_version": DUAL_ARM_STATE_SCHEMA_VERSION,
        "scene_revision": scene_revision,
        "state_revision": state_revision,
        "frame_id": frame_id,
        "left": _arm_state(left, "left"),
        "right": _arm_state(right, "right"),
        "selected_arm": selected_arm,
        "held_arm_policy": held_arm_policy,
        "provenance_refs": refs,
        "motion_authorized": False,
    }


def validate_dual_arm_state(value: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "schema_version", "scene_revision", "state_revision", "frame_id",
        "left", "right", "selected_arm", "held_arm_policy", "provenance_refs",
        "motion_authorized",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise DualArmStateError("dual-arm state fields are invalid")
    if value["schema_version"] != DUAL_ARM_STATE_SCHEMA_VERSION or value["motion_authorized"] is not False:
        raise DualArmStateError("dual-arm state schema or authority is invalid")
    return build_dual_arm_state(
        scene_revision=value["scene_revision"], state_revision=value["state_revision"],
        frame_id=value["frame_id"], left=value["left"], right=value["right"],
        held_arm_policy=value["held_arm_policy"], selected_arm=value["selected_arm"],
        provenance_refs=value["provenance_refs"],
    )


def hold_drift(
    initial: Mapping[str, Any], current: Mapping[str, Any], *, arm_id: str
) -> dict[str, float | bool]:
    """Compare a held arm against its bound state; tolerance is caller-owned."""
    validate_dual_arm_state(initial)
    validate_dual_arm_state(current)
    if initial["scene_revision"] != current["scene_revision"] or initial["frame_id"] != current["frame_id"]:
        raise DualArmStateError("held-arm state revision or frame differs")
    if arm_id not in {"left", "right"}:
        raise DualArmStateError("held arm is invalid")
    before, after = initial[arm_id], current[arm_id]
    qpos_delta = max(abs(a - b) for a, b in zip(before["qpos"], after["qpos"]))
    target_delta = max(abs(a - b) for a, b in zip(before["drive_target"], after["drive_target"]))
    return {"arm_id": arm_id, "max_qpos_delta_rad": qpos_delta, "max_drive_target_delta_rad": target_delta,
            "drive_target_unchanged": target_delta == 0.0}


def build_peer_arm_projection(
    *, scene_revision: str, state_revision: str, frame_id: str,
    selected_arm: str, links: Sequence[Mapping[str, Any]], source_ref: str,
) -> dict[str, Any]:
    """Build cuboid projections for the peer arm from provider link geometry."""
    if selected_arm not in {"left", "right"}:
        raise DualArmStateError("selected_arm is invalid")
    if not isinstance(source_ref, str) or not source_ref.startswith("artifact://"):
        raise DualArmStateError("peer projection source_ref is invalid")
    obstacles: list[dict[str, Any]] = []
    for item in links:
        if not isinstance(item, Mapping) or set(item) != {"arm_id", "link_name", "half_extents_m", "pose_wxyz"}:
            raise DualArmStateError("peer link projection fields are invalid")
        arm_id = item["arm_id"]
        if arm_id not in {"left", "right"} or arm_id == selected_arm:
            raise DualArmStateError("peer projection arm binding is invalid")
        link_id = qualified_link_id(arm_id, item["link_name"])
        extents = _finite_vector(item["half_extents_m"], 3, f"{link_id}.half_extents_m")
        if any(size <= 0 for size in extents):
            raise DualArmStateError("peer link half extents must be positive")
        pose = _finite_vector(item["pose_wxyz"], 7, f"{link_id}.pose_wxyz")
        obstacles.append({
            "entity_ref": f"arm://{link_id}", "link_id": link_id, "shape": "cuboid",
            "half_extents_m": extents, "pose_wxyz": pose, "provenance_ref": source_ref,
        })
    if not obstacles:
        raise DualArmStateError("peer projection is empty")
    return {
        "schema_version": PEER_ARM_PROJECTION_SCHEMA_VERSION,
        "scene_revision": scene_revision, "state_revision": state_revision,
        "frame_id": frame_id, "selected_arm": selected_arm,
        "obstacles": obstacles, "source_ref": source_ref, "motion_authorized": False,
    }


def validate_peer_arm_projection(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {
        "schema_version", "scene_revision", "state_revision", "frame_id", "selected_arm",
        "obstacles", "source_ref", "motion_authorized",
    }:
        raise DualArmStateError("peer projection fields are invalid")
    if value["schema_version"] != PEER_ARM_PROJECTION_SCHEMA_VERSION or value["motion_authorized"] is not False:
        raise DualArmStateError("peer projection schema or authority is invalid")
    return build_peer_arm_projection(
        scene_revision=value["scene_revision"], state_revision=value["state_revision"],
        frame_id=value["frame_id"], selected_arm=value["selected_arm"],
        links=[
            {
                "arm_id": item["link_id"].split(":", 1)[0],
                "link_name": item["link_id"].split(":", 1)[1],
                "half_extents_m": item["half_extents_m"],
                "pose_wxyz": item["pose_wxyz"],
            }
            for item in value["obstacles"]
        ],
        source_ref=value["source_ref"],
    )


def build_peer_arm_sphere_projection(
    *, scene_revision: str, state_revision: str, frame_id: str,
    selected_arm: str, spheres: Sequence[Mapping[str, Any]], source_ref: str,
) -> dict[str, Any]:
    """Build a peer projection from Curobo's native robot collision spheres.

    Sphere centers are expressed in the declared frame.  The provider must
    perform any planner-base to world transform before calling this function;
    this protocol deliberately does not guess a transform or approximate a
    mesh as a box.
    """
    if selected_arm not in {"left", "right"}:
        raise DualArmStateError("selected_arm is invalid")
    if frame_id != "world":
        raise DualArmStateError("peer sphere projection frame must be world")
    if not isinstance(source_ref, str) or not source_ref.startswith("artifact://"):
        raise DualArmStateError("peer projection source_ref is invalid")
    peer_arm = "right" if selected_arm == "left" else "left"
    obstacles: list[dict[str, Any]] = []
    for index, item in enumerate(spheres):
        if not isinstance(item, Mapping) or set(item) != {"center_m", "radius_m"}:
            raise DualArmStateError("peer sphere fields are invalid")
        center = _finite_vector(item["center_m"], 3, f"{peer_arm}.sphere[{index}].center_m")
        radius = float(item["radius_m"])
        if not math.isfinite(radius) or radius <= 0:
            raise DualArmStateError("peer sphere radius must be positive")
        link_id = qualified_link_id(peer_arm, f"curobo_sphere_{index}")
        obstacles.append({
            "entity_ref": f"arm://{link_id}", "link_id": link_id,
            "shape": "sphere", "radius_m": radius,
            "center_m": center, "pose_wxyz": [*center, 1.0, 0.0, 0.0, 0.0],
            "provenance_ref": source_ref,
        })
    if not obstacles:
        raise DualArmStateError("peer sphere projection is empty")
    return {
        "schema_version": PEER_ARM_SPHERE_PROJECTION_SCHEMA_VERSION,
        "scene_revision": scene_revision, "state_revision": state_revision,
        "frame_id": frame_id, "selected_arm": selected_arm,
        "obstacles": obstacles, "source_ref": source_ref,
        "motion_authorized": False,
    }


def validate_peer_arm_sphere_projection(value: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "schema_version", "scene_revision", "state_revision", "frame_id",
        "selected_arm", "obstacles", "source_ref", "motion_authorized",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise DualArmStateError("peer sphere projection fields are invalid")
    if value["schema_version"] != PEER_ARM_SPHERE_PROJECTION_SCHEMA_VERSION:
        raise DualArmStateError("peer sphere projection schema is invalid")
    if value["motion_authorized"] is not False:
        raise DualArmStateError("peer sphere projection authority is invalid")
    if value["selected_arm"] not in {"left", "right"}:
        raise DualArmStateError("selected_arm is invalid")
    peer_arm = "right" if value["selected_arm"] == "left" else "left"
    spheres = []
    for index, item in enumerate(value["obstacles"]):
        if not isinstance(item, Mapping) or set(item) != {
            "entity_ref", "link_id", "shape", "radius_m", "center_m",
            "pose_wxyz", "provenance_ref",
        } or item["shape"] != "sphere":
            raise DualArmStateError("peer sphere obstacle shape is invalid")
        link_id = item.get("link_id")
        expected_link_id = qualified_link_id(peer_arm, f"curobo_sphere_{index}")
        if link_id != expected_link_id or item["entity_ref"] != f"arm://{expected_link_id}":
            raise DualArmStateError("peer sphere link identity is invalid")
        if item["provenance_ref"] != value["source_ref"]:
            raise DualArmStateError("peer sphere provenance is invalid")
        center = _finite_vector(item["center_m"], 3, f"{link_id}.center_m")
        if _finite_vector(item["pose_wxyz"], 7, f"{link_id}.pose_wxyz") != [
            *center, 1.0, 0.0, 0.0, 0.0,
        ]:
            raise DualArmStateError("peer sphere pose is invalid")
        spheres.append({"center_m": item.get("center_m"), "radius_m": item.get("radius_m")})
    return build_peer_arm_sphere_projection(
        scene_revision=value["scene_revision"], state_revision=value["state_revision"],
        frame_id=value["frame_id"], selected_arm=value["selected_arm"],
        spheres=spheres, source_ref=value["source_ref"],
    )


__all__ = [
    "DUAL_ARM_STATE_SCHEMA_VERSION", "PEER_ARM_PROJECTION_SCHEMA_VERSION",
    "DualArmStateError", "build_dual_arm_state", "validate_dual_arm_state", "hold_drift",
    "qualified_link_id", "build_peer_arm_projection", "validate_peer_arm_projection",
    "PEER_ARM_SPHERE_PROJECTION_SCHEMA_VERSION", "build_peer_arm_sphere_projection",
    "validate_peer_arm_sphere_projection",
]

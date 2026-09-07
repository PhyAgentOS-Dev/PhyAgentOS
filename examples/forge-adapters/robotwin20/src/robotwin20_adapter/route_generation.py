"""Adapter-owned execution-grasp adaptation and route-template generation.

Inputs are already expressed in the profile's route frame. The module performs
only deterministic geometry; it does not call a planner, simulator, Gateway, or
actuator and it never grants task-success or motion authority.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from .route_readiness import RouteReadinessError, validate_route_request


class RouteGenerationError(ValueError):
    """An execution candidate or route template is incomplete or unsafe."""


def _finite(value: Any, label: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise RouteGenerationError(f"{label} must be a finite number")
    result = float(value)
    if positive and result <= 0:
        raise RouteGenerationError(f"{label} must be positive")
    return result


def _pose(value: Any, frame_id: str, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {
        "frame_id", "position_m", "orientation_xyzw",
    }:
        raise RouteGenerationError(f"{label} fields are invalid")
    if value["frame_id"] != frame_id:
        raise RouteGenerationError(f"{label} frame binding is invalid")
    position = value["position_m"]
    orientation = value["orientation_xyzw"]
    if not isinstance(position, list) or len(position) != 3 or any(
        isinstance(item, bool) or not isinstance(item, (int, float))
        or not math.isfinite(float(item)) for item in position
    ):
        raise RouteGenerationError(f"{label}.position_m is invalid")
    if not isinstance(orientation, list) or len(orientation) != 4 or any(
        isinstance(item, bool) or not isinstance(item, (int, float))
        or not math.isfinite(float(item)) for item in orientation
    ):
        raise RouteGenerationError(f"{label}.orientation_xyzw is invalid")
    if abs(math.sqrt(sum(float(item) ** 2 for item in orientation)) - 1.0) > 1e-3:
        raise RouteGenerationError(f"{label}.orientation_xyzw must be normalized")
    return {
        "frame_id": frame_id,
        "position_m": [float(item) for item in position],
        "orientation_xyzw": [float(item) for item in orientation],
    }


def _direction(value: Any, frame_id: str, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {"frame_id", "vector", "provenance_ref"}:
        raise RouteGenerationError(f"{label} fields are invalid")
    if value["frame_id"] != frame_id:
        raise RouteGenerationError(f"{label} frame binding is invalid")
    vector = value["vector"]
    if not isinstance(vector, list) or len(vector) != 3 or any(
        isinstance(item, bool) or not isinstance(item, (int, float))
        or not math.isfinite(float(item)) for item in vector
    ):
        raise RouteGenerationError(f"{label}.vector is invalid")
    if abs(math.sqrt(sum(float(item) ** 2 for item in vector)) - 1.0) > 1e-3:
        raise RouteGenerationError(f"{label}.vector must be normalized")
    provenance = value["provenance_ref"]
    if not isinstance(provenance, str) or not provenance.startswith("artifact://"):
        raise RouteGenerationError(f"{label}.provenance_ref is invalid")
    return {
        "frame_id": frame_id,
        "vector": [float(item) for item in vector],
        "provenance_ref": provenance,
    }


def _matrix(value: Any, label: str) -> list[list[float]]:
    if not isinstance(value, list) or len(value) != 16 or any(
        isinstance(item, bool) or not isinstance(item, (int, float))
        or not math.isfinite(float(item)) for item in value
    ):
        raise RouteGenerationError(f"{label} must contain 16 finite numbers")
    matrix = [[float(value[row * 4 + col]) for col in range(4)] for row in range(4)]
    if any(abs(actual - expected) > 1e-6 for actual, expected in zip(matrix[3], (0, 0, 0, 1))):
        raise RouteGenerationError(f"{label} homogeneous row is invalid")
    return matrix


def _multiply(left: list[list[float]], right: list[list[float]]) -> list[list[float]]:
    return [
        [sum(left[row][index] * right[index][col] for index in range(4)) for col in range(4)]
        for row in range(4)
    ]


def _quat_to_rotation(quaternion: list[float]) -> list[list[float]]:
    x, y, z, w = quaternion
    return [
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ]


def _rotation_to_quat(rotation: list[list[float]]) -> list[float]:
    trace = rotation[0][0] + rotation[1][1] + rotation[2][2]
    if trace > 0:
        scale = math.sqrt(trace + 1.0) * 2
        w = 0.25 * scale
        x = (rotation[2][1] - rotation[1][2]) / scale
        y = (rotation[0][2] - rotation[2][0]) / scale
        z = (rotation[1][0] - rotation[0][1]) / scale
    else:
        axis = max(range(3), key=lambda index: rotation[index][index])
        if axis == 0:
            scale = math.sqrt(1 + rotation[0][0] - rotation[1][1] - rotation[2][2]) * 2
            x, y, z, w = 0.25 * scale, (rotation[0][1] + rotation[1][0]) / scale, (rotation[0][2] + rotation[2][0]) / scale, (rotation[2][1] - rotation[1][2]) / scale
        elif axis == 1:
            scale = math.sqrt(1 + rotation[1][1] - rotation[0][0] - rotation[2][2]) * 2
            x, y, z, w = (rotation[0][1] + rotation[1][0]) / scale, 0.25 * scale, (rotation[1][2] + rotation[2][1]) / scale, (rotation[0][2] - rotation[2][0]) / scale
        else:
            scale = math.sqrt(1 + rotation[2][2] - rotation[0][0] - rotation[1][1]) * 2
            x, y, z, w = (rotation[0][2] + rotation[2][0]) / scale, (rotation[1][2] + rotation[2][1]) / scale, 0.25 * scale, (rotation[1][0] - rotation[0][1]) / scale
    norm = math.sqrt(x * x + y * y + z * z + w * w)
    return [x / norm, y / norm, z / norm, w / norm]


def _pose_matrix(pose: Mapping[str, Any]) -> list[list[float]]:
    rotation = _quat_to_rotation(list(pose["orientation_xyzw"]))
    return [
        [*rotation[0], pose["position_m"][0]],
        [*rotation[1], pose["position_m"][1]],
        [*rotation[2], pose["position_m"][2]],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _matrix_pose(matrix: list[list[float]], template: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "frame_id": template["frame_id"],
        "position_m": [matrix[index][3] for index in range(3)],
        "orientation_xyzw": _rotation_to_quat([row[:3] for row in matrix[:3]]),
    }


def _offset(
    pose: Mapping[str, Any], distance: float, direction: Mapping[str, Any]
) -> dict[str, Any]:
    result = deepcopy(dict(pose))
    result["position_m"] = [
        float(position) + distance * float(axis)
        for position, axis in zip(result["position_m"], direction["vector"])
    ]
    return result


def validate_route_policy(value: Any, frame_id: str) -> dict[str, Any]:
    """Validate profile-owned route-template geometry in its declared frame."""

    required = {
        "approach_clearance_m",
        "lift_clearance_m",
        "transport_clearance_m",
        "descent_clearance_m",
        "retreat_distance_m",
        "retreat_direction",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise RouteGenerationError("route_policy fields are invalid")
    normalized = {
        name: _finite(value[name], f"route_policy.{name}", positive=True)
        for name in required - {"retreat_direction"}
    }
    normalized["retreat_direction"] = _direction(
        value["retreat_direction"], frame_id, "route_policy.retreat_direction"
    )
    return normalized


def generate_route_request(
    base_request: Mapping[str, Any],
    proposal_candidate: Mapping[str, Any],
    execution_grasp: Mapping[str, Any],
    attached_object: Mapping[str, Any],
    placement_target: Mapping[str, Any],
    route_policy: Mapping[str, Any],
) -> dict[str, Any]:
    """Generate one v6 route request from explicit adapter-owned projections."""

    required_base = {
        "schema_version", "request_id", "observation_ref", "observation_frame_id",
        "scene_revision", "frame_id", "calibration_ref", "calibration_sha256",
        "calibration_revision", "candidate_set_ref", "candidates", "workspace_bounds_m",
        "joint_limits_ref", "stop_policy_ref", "motion_capabilities",
        "controller_qualification", "collision_world",
    }
    if not isinstance(base_request, Mapping) or set(base_request) != required_base:
        raise RouteGenerationError("route generation base request fields are invalid")
    if base_request["candidates"] != []:
        raise RouteGenerationError("route generation base request candidates must be empty")
    route_frame = base_request["frame_id"]
    if not isinstance(route_frame, str) or not route_frame:
        raise RouteGenerationError("route generation frame_id is invalid")
    if not isinstance(proposal_candidate, Mapping) or set(proposal_candidate) != {
        "candidate_ref",
        "entity_ref",
        "provenance",
        "observation_ref",
        "observation_frame_id",
        "scene_revision",
        "calibration_ref",
        "candidate_set_ref",
    }:
        raise RouteGenerationError("proposal candidate fields are invalid")
    for field in (
        "observation_ref",
        "observation_frame_id",
        "scene_revision",
        "calibration_ref",
        "candidate_set_ref",
    ):
        if proposal_candidate[field] != base_request[field]:
            raise RouteGenerationError(f"proposal candidate {field} is not bound to request")
    provenance = proposal_candidate["provenance"]
    if not isinstance(provenance, list) or not provenance or any(
        not isinstance(ref, str) or not ref.startswith("artifact://") for ref in provenance
    ):
        raise RouteGenerationError("proposal candidate provenance is invalid")
    candidate_ref = proposal_candidate["candidate_ref"]
    entity_ref = proposal_candidate["entity_ref"]
    if not isinstance(candidate_ref, str) or not candidate_ref.startswith("candidate://"):
        raise RouteGenerationError("proposal candidate_ref is invalid")
    if not isinstance(entity_ref, str) or not entity_ref.startswith("entity://"):
        raise RouteGenerationError("proposal entity_ref is invalid")

    if not isinstance(execution_grasp, Mapping) or set(execution_grasp) != {
        "contact_center_pose", "robot_target_pose", "robot_target_frame",
        "robot_target_round_trip_residual_m", "ingress_direction",
        "support_clear_direction", "adaptation_provenance_ref",
    }:
        raise RouteGenerationError("execution_grasp fields are invalid")
    contact_center = _pose(
        execution_grasp["contact_center_pose"], route_frame, "contact_center_pose"
    )
    robot_target = _pose(
        execution_grasp["robot_target_pose"], route_frame, "robot_target_pose"
    )
    if execution_grasp["robot_target_frame"] != "robotwin_gripper":
        raise RouteGenerationError("execution_grasp robot target frame is unsupported")
    round_trip_residual = _finite(
        execution_grasp["robot_target_round_trip_residual_m"],
        "robot_target_round_trip_residual_m",
    )
    if round_trip_residual < 0 or round_trip_residual > 1e-8:
        raise RouteGenerationError("execution_grasp robot target round-trip is invalid")
    ingress = _direction(execution_grasp["ingress_direction"], route_frame, "ingress_direction")
    support_clear = _direction(
        execution_grasp["support_clear_direction"], route_frame, "support_clear_direction"
    )
    adaptation_ref = execution_grasp["adaptation_provenance_ref"]
    if not isinstance(adaptation_ref, str) or not adaptation_ref.startswith("artifact://"):
        raise RouteGenerationError("execution_grasp adaptation provenance is invalid")

    if not isinstance(attached_object, Mapping) or set(attached_object) != {
        "geometry_ref", "geometry_sha256", "object_frame_id", "half_extents_m",
        "object_T_robot_target", "transform_provenance_ref",
    }:
        raise RouteGenerationError("attached_object fields are invalid")
    object_t_robot_target = _matrix(
        attached_object["object_T_robot_target"], "attached_object.object_T_robot_target"
    )
    transform_ref = attached_object["transform_provenance_ref"]
    if not isinstance(transform_ref, str) or not transform_ref.startswith("artifact://"):
        raise RouteGenerationError("attached_object transform provenance is invalid")

    if not isinstance(placement_target, Mapping) or set(placement_target) != {
        "target_ref", "target_object_pose", "provenance_ref",
    }:
        raise RouteGenerationError("placement_target fields are invalid")
    target_object = _pose(
        placement_target["target_object_pose"], route_frame, "placement_target.target_object_pose"
    )
    target_ref = placement_target["target_ref"]
    target_provenance = placement_target["provenance_ref"]
    if not isinstance(target_ref, str) or not target_ref.startswith("destination://"):
        raise RouteGenerationError("placement_target.target_ref is invalid")
    if not isinstance(target_provenance, str) or not target_provenance.startswith("artifact://"):
        raise RouteGenerationError("placement_target.provenance_ref is invalid")

    policy = validate_route_policy(route_policy, route_frame)
    distances = {key: value for key, value in policy.items() if key != "retreat_direction"}
    retreat_direction = policy["retreat_direction"]

    release_robot_target = _matrix_pose(
        _multiply(_pose_matrix(target_object), object_t_robot_target), target_object
    )
    approach = _offset(robot_target, -distances["approach_clearance_m"], ingress)
    lift = _offset(robot_target, distances["lift_clearance_m"], support_clear)
    transport = _offset(
        release_robot_target, distances["transport_clearance_m"], support_clear
    )
    descent = _offset(
        release_robot_target, distances["descent_clearance_m"], support_clear
    )
    retreat = _offset(
        release_robot_target, distances["retreat_distance_m"], retreat_direction
    )
    route = [
        {"phase": "approach", "waypoints": [approach], "gripper_state": "open"},
        {"phase": "contact", "waypoints": [robot_target], "gripper_state": "contact"},
        {"phase": "close", "waypoints": [robot_target], "gripper_state": "closed"},
        {"phase": "lift", "waypoints": [lift], "gripper_state": "closed"},
        {"phase": "transport", "waypoints": [lift, transport], "gripper_state": "closed"},
        {"phase": "descent", "waypoints": [descent, release_robot_target], "gripper_state": "closed"},
        {"phase": "release", "waypoints": [release_robot_target], "gripper_state": "released"},
        {"phase": "retreat", "waypoints": [retreat], "gripper_state": "open"},
    ]
    candidate = {
        "candidate_ref": candidate_ref,
        "entity_ref": entity_ref,
        "provenance": deepcopy(provenance),
        "execution_grasp": {
            "contact_center_pose": contact_center,
            "robot_target_pose": robot_target,
            "robot_target_frame": "robotwin_gripper",
            "robot_target_round_trip_residual_m": round_trip_residual,
            "ingress_direction": ingress,
            "support_clear_direction": support_clear,
            "adaptation_provenance_ref": adaptation_ref,
        },
        "attached_object": deepcopy(dict(attached_object)),
        "placement_target": {
            "target_ref": target_ref,
            "target_object_pose": target_object,
            "release_robot_target_pose": release_robot_target,
            "provenance_ref": target_provenance,
        },
        "route": route,
    }
    output = deepcopy(dict(base_request))
    output["candidates"] = [candidate]
    try:
        validate_route_request(output)
    except RouteReadinessError as exc:
        raise RouteGenerationError(str(exc)) from exc
    return output


__all__ = ["RouteGenerationError", "generate_route_request", "validate_route_policy"]

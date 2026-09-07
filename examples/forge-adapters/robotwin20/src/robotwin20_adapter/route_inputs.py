"""Validated adapter projections for a complete RoboTwin pick-place route.

The benchmark worker owns simulator/task introspection.  This module consumes
its no-motion scene facts and derives route inputs without importing RoboTwin,
SAPIEN, a planner, or PAOS control-plane state.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from typing import Any

ROUTE_SCENE_FACTS_SCHEMA_VERSION = "paos-robotwin20-route-scene-facts/v1"
ROUTE_INPUT_PROFILE_SCHEMA_VERSION = "paos-robotwin20-route-input-profile/v3"
OBJECT_GEOMETRY_SCHEMA_VERSION = "paos-robotwin20-object-geometry/v1"
OBJECT_ROBOT_TARGET_TRANSFORM_SCHEMA_VERSION = "paos-robotwin20-object-robot-target-transform/v1"
PLACEMENT_TARGET_SCHEMA_VERSION = "paos-robotwin20-placement-target/v1"


class RouteInputError(ValueError):
    """Route input evidence is malformed, stale, or geometrically invalid."""


def canonical_json(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256_json(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _finite_vector(value: Any, length: int, label: str) -> list[float]:
    if not isinstance(value, list) or len(value) != length or any(
        isinstance(item, bool)
        or not isinstance(item, (int, float))
        or not math.isfinite(float(item))
        for item in value
    ):
        raise RouteInputError(f"{label} must contain {length} finite numbers")
    return [float(item) for item in value]


def _matrix(value: Any, label: str) -> list[list[float]]:
    flat = _finite_vector(value, 16, label)
    matrix = [flat[index : index + 4] for index in range(0, 16, 4)]
    if any(abs(actual - expected) > 1e-6 for actual, expected in zip(matrix[3], (0, 0, 0, 1))):
        raise RouteInputError(f"{label} homogeneous row is invalid")
    rotation = [row[:3] for row in matrix[:3]]
    for row in rotation:
        if abs(sum(item * item for item in row) - 1.0) > 1e-3:
            raise RouteInputError(f"{label} rotation is invalid")
    for left, right in ((rotation[0], rotation[1]), (rotation[0], rotation[2]), (rotation[1], rotation[2])):
        if abs(sum(a * b for a, b in zip(left, right))) > 1e-3:
            raise RouteInputError(f"{label} rotation is invalid")
    determinant = (
        rotation[0][0] * (rotation[1][1] * rotation[2][2] - rotation[1][2] * rotation[2][1])
        - rotation[0][1] * (rotation[1][0] * rotation[2][2] - rotation[1][2] * rotation[2][0])
        + rotation[0][2] * (rotation[1][0] * rotation[2][1] - rotation[1][1] * rotation[2][0])
    )
    if abs(determinant - 1.0) > 1e-3:
        raise RouteInputError(f"{label} rotation is invalid")
    return matrix


def _flatten(value: list[list[float]]) -> list[float]:
    return [item for row in value for item in row]


def _multiply(left: list[list[float]], right: list[list[float]]) -> list[list[float]]:
    return [
        [sum(left[row][index] * right[index][column] for index in range(4)) for column in range(4)]
        for row in range(4)
    ]


def _inverse_rigid(value: list[list[float]]) -> list[list[float]]:
    rotation = [row[:3] for row in value[:3]]
    transpose = [[rotation[column][row] for column in range(3)] for row in range(3)]
    translation = [value[row][3] for row in range(3)]
    inverse_translation = [
        -sum(transpose[row][column] * translation[column] for column in range(3))
        for row in range(3)
    ]
    return [
        [*transpose[0], inverse_translation[0]],
        [*transpose[1], inverse_translation[1]],
        [*transpose[2], inverse_translation[2]],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _matrix_from_xyzw_pose(pose: Mapping[str, Any]) -> list[list[float]]:
    position = _finite_vector(pose.get("position_m"), 3, "TCP position")
    x, y, z, w = _finite_vector(pose.get("orientation_xyzw"), 4, "TCP orientation")
    norm = math.sqrt(x * x + y * y + z * z + w * w)
    if norm <= 1e-9:
        raise RouteInputError("TCP orientation is degenerate")
    x, y, z, w = (item / norm for item in (x, y, z, w))
    return [
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w), position[0]],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w), position[1]],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y), position[2]],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _rotation_to_xyzw(rotation: list[list[float]]) -> list[float]:
    trace = sum(rotation[index][index] for index in range(3))
    if trace > 0:
        scale = math.sqrt(trace + 1.0) * 2
        result = [
            (rotation[2][1] - rotation[1][2]) / scale,
            (rotation[0][2] - rotation[2][0]) / scale,
            (rotation[1][0] - rotation[0][1]) / scale,
            0.25 * scale,
        ]
    else:
        axis = max(range(3), key=lambda index: rotation[index][index])
        if axis == 0:
            scale = math.sqrt(1 + rotation[0][0] - rotation[1][1] - rotation[2][2]) * 2
            result = [0.25 * scale, (rotation[0][1] + rotation[1][0]) / scale, (rotation[0][2] + rotation[2][0]) / scale, (rotation[2][1] - rotation[1][2]) / scale]
        elif axis == 1:
            scale = math.sqrt(1 + rotation[1][1] - rotation[0][0] - rotation[2][2]) * 2
            result = [(rotation[0][1] + rotation[1][0]) / scale, 0.25 * scale, (rotation[1][2] + rotation[2][1]) / scale, (rotation[0][2] - rotation[2][0]) / scale]
        else:
            scale = math.sqrt(1 + rotation[2][2] - rotation[0][0] - rotation[1][1]) * 2
            result = [(rotation[0][2] + rotation[2][0]) / scale, (rotation[1][2] + rotation[2][1]) / scale, 0.25 * scale, (rotation[1][0] - rotation[0][1]) / scale]
    norm = math.sqrt(sum(item * item for item in result))
    return [item / norm for item in result]


def validate_scene_facts(value: Any) -> dict[str, Any]:
    required = {
        "schema_version", "task_name", "seed", "scene_revision", "observation_ref",
        "observation_frame_id", "route_frame_id", "calibration_ref", "task_definition",
        "captured_at", "robot_control_steps", "motion_authorized", "coverage", "objects",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise RouteInputError("route scene facts fields are invalid")
    if value["schema_version"] != ROUTE_SCENE_FACTS_SCHEMA_VERSION:
        raise RouteInputError("route scene facts schema is unsupported")
    if value["route_frame_id"] != "world" or value["motion_authorized"] is not False or value["robot_control_steps"] != 0:
        raise RouteInputError("route scene facts motion/frame boundary is invalid")
    if value["coverage"] not in {"complete", "partial", "unknown"}:
        raise RouteInputError("route scene facts coverage is invalid")
    revision = value["scene_revision"]
    frame = value["observation_frame_id"]
    if value["observation_ref"] != f"observation://{revision}/{frame}":
        raise RouteInputError("route scene facts observation binding is invalid")
    if revision != f"{value['task_name']}-{value['seed']}-1":
        raise RouteInputError("route scene facts revision binding is invalid")
    if not isinstance(value["calibration_ref"], str) or not value["calibration_ref"].startswith("artifact://"):
        raise RouteInputError("route scene facts calibration_ref is invalid")
    task_definition = value["task_definition"]
    if not isinstance(task_definition, Mapping) or set(task_definition) != {"relative_path", "sha256"}:
        raise RouteInputError("route scene facts task definition is invalid")
    if not isinstance(task_definition["relative_path"], str) or task_definition["relative_path"].startswith("/"):
        raise RouteInputError("route scene facts task path is invalid")
    digest = task_definition["sha256"]
    if not isinstance(digest, str) or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise RouteInputError("route scene facts task digest is invalid")
    if not isinstance(value["captured_at"], str) or not value["captured_at"].strip():
        raise RouteInputError("route scene facts timestamp is invalid")
    objects = value["objects"]
    if not isinstance(objects, list) or len(objects) != 3:
        raise RouteInputError("route scene facts must contain three blocks")
    seen: set[str] = set()
    for item in objects:
        expected = {
            "entity_ref", "actor_name", "object_frame_id", "world_T_object",
            "world_T_functional_point", "world_T_functional_target", "world_T_object_target",
            "half_extents_m", "target_ref", "functional_point_id",
        }
        if not isinstance(item, Mapping) or set(item) != expected:
            raise RouteInputError("route scene object fields are invalid")
        entity_ref = item["entity_ref"]
        if not isinstance(entity_ref, str) or not entity_ref.startswith("entity://") or entity_ref in seen:
            raise RouteInputError("route scene entity identity is invalid")
        seen.add(entity_ref)
        if item["functional_point_id"] != 0:
            raise RouteInputError("route scene functional point is unsupported")
        for field in ("world_T_object", "world_T_functional_point", "world_T_functional_target", "world_T_object_target"):
            _matrix(item[field], f"route scene object {field}")
        half_extents = _finite_vector(item["half_extents_m"], 3, "route scene object half_extents_m")
        if any(item <= 0 for item in half_extents):
            raise RouteInputError("route scene object half extents must be positive")
        if not isinstance(item["target_ref"], str) or not item["target_ref"].startswith("destination://"):
            raise RouteInputError("route scene target_ref is invalid")
        expected_target = _multiply(
            _matrix(item["world_T_functional_target"], "functional target"),
            _inverse_rigid(
                _multiply(
                    _inverse_rigid(_matrix(item["world_T_object"], "world object")),
                    _matrix(item["world_T_functional_point"], "world functional point"),
                )
            ),
        )
        actual_target = _matrix(item["world_T_object_target"], "world object target")
        if any(abs(expected_target[row][column] - actual_target[row][column]) > 1e-5 for row in range(4) for column in range(4)):
            raise RouteInputError("route scene object target derivation is inconsistent")
    return dict(value)


def derive_bound_route_inputs(
    scene_facts: Mapping[str, Any],
    *,
    entity_ref: str,
    execution_grasp: Mapping[str, Any],
    scene_facts_ref: str,
    geometry_ref: str,
    transform_ref: str,
    placement_ref: str,
    semantic_tolerance: Mapping[str, Any] | None = None,
    contact_shell_tolerance_m: float = 0.0,
) -> dict[str, Any]:
    """Derive geometry, object-to-RoboTwin-target, and placement records."""

    facts = validate_scene_facts(scene_facts)
    if any(not isinstance(ref, str) or not ref.startswith("artifact://") for ref in (scene_facts_ref, geometry_ref, transform_ref, placement_ref)):
        raise RouteInputError("route input provenance refs are invalid")
    matches = [item for item in facts["objects"] if item["entity_ref"] == entity_ref]
    if len(matches) != 1:
        raise RouteInputError("route input entity is absent or ambiguous")
    item = matches[0]
    contact = execution_grasp.get("contact_center_pose")
    robot_target = execution_grasp.get("robot_target_pose")
    if not isinstance(contact, Mapping) or contact.get("frame_id") != facts["route_frame_id"]:
        raise RouteInputError("route input execution grasp frame is invalid")
    if not isinstance(robot_target, Mapping) or robot_target.get("frame_id") != facts["route_frame_id"]:
        raise RouteInputError("route input RoboTwin target frame is invalid")
    if execution_grasp.get("robot_target_frame") != "robotwin_gripper":
        raise RouteInputError("route input RoboTwin target identity is invalid")
    world_object = _matrix(item["world_T_object"], "world_T_object")
    world_contact = _matrix_from_xyzw_pose(contact)
    world_robot_target = _matrix_from_xyzw_pose(robot_target)
    object_robot_target = _multiply(_inverse_rigid(world_object), world_robot_target)
    reconstructed = _multiply(world_object, object_robot_target)
    residual = max(abs(reconstructed[row][column] - world_robot_target[row][column]) for row in range(4) for column in range(4))
    if residual > 1e-6:
        raise RouteInputError("object_T_robot_target reconstruction residual is too large")
    if (
        isinstance(contact_shell_tolerance_m, bool)
        or not isinstance(contact_shell_tolerance_m, (int, float))
        or not math.isfinite(float(contact_shell_tolerance_m))
        or float(contact_shell_tolerance_m) < 0
    ):
        raise RouteInputError("contact shell tolerance is invalid")
    object_contact = _multiply(_inverse_rigid(world_object), world_contact)
    contact_translation = [object_contact[index][3] for index in range(3)]
    if any(
        abs(value) > float(extent) + float(contact_shell_tolerance_m)
        for value, extent in zip(contact_translation, item["half_extents_m"])
    ):
        raise RouteInputError("canonical contact center does not intersect the object contact shell")
    geometry = {
        "schema_version": OBJECT_GEOMETRY_SCHEMA_VERSION,
        "entity_ref": entity_ref,
        "scene_revision": facts["scene_revision"],
        "frame_id": item["object_frame_id"],
        "shape": "box",
        "half_extents_m": item["half_extents_m"],
        "source_scene_facts_ref": scene_facts_ref,
        "source": "sapien_collision_shape",
    }
    transform = {
        "schema_version": OBJECT_ROBOT_TARGET_TRANSFORM_SCHEMA_VERSION,
        "entity_ref": entity_ref,
        "scene_revision": facts["scene_revision"],
        "route_frame_id": facts["route_frame_id"],
        "world_T_object": _flatten(world_object),
        "world_T_contact_center": _flatten(world_contact),
        "object_T_contact_center": _flatten(object_contact),
        "world_T_robot_target": _flatten(world_robot_target),
        "object_T_robot_target": _flatten(object_robot_target),
        "max_reconstruction_residual": residual,
        "contact_shell_tolerance_m": float(contact_shell_tolerance_m),
        "contact_center_inside_contact_shell": True,
        "robot_target_frame": "robotwin_gripper",
        "robot_target_round_trip_residual_m": float(
            execution_grasp["robot_target_round_trip_residual_m"]
        ),
        "source_scene_facts_ref": scene_facts_ref,
        "grasp_adaptation_ref": execution_grasp["adaptation_provenance_ref"],
    }
    target_matrix = _matrix(item["world_T_object_target"], "world_T_object_target")
    placement = {
        "schema_version": PLACEMENT_TARGET_SCHEMA_VERSION,
        "target_ref": item["target_ref"],
        "entity_ref": entity_ref,
        "scene_revision": facts["scene_revision"],
        "frame_id": facts["route_frame_id"],
        "world_T_object_target": _flatten(target_matrix),
        "source_scene_facts_ref": scene_facts_ref,
        "source_task_definition": facts["task_definition"],
        "functional_point_id": item["functional_point_id"],
    }
    if semantic_tolerance is not None:
        if set(semantic_tolerance) != {"target_position_m", "target_orientation_rad"}:
            raise RouteInputError("semantic tolerance fields are invalid")
        tolerances = _finite_vector(
            [semantic_tolerance["target_position_m"], semantic_tolerance["target_orientation_rad"]],
            2,
            "semantic tolerance",
        )
        if any(value <= 0 for value in tolerances):
            raise RouteInputError("semantic tolerances must be positive")
        placement["semantic_tolerance"] = {
            "target_position_m": tolerances[0],
            "target_orientation_rad": tolerances[1],
        }
    target_pose = {
        "frame_id": facts["route_frame_id"],
        "position_m": [target_matrix[index][3] for index in range(3)],
        "orientation_xyzw": _rotation_to_xyzw([row[:3] for row in target_matrix[:3]]),
    }
    return {
        "geometry_artifact": geometry,
        "transform_artifact": transform,
        "placement_artifact": placement,
        "attached_object": {
            "geometry_ref": geometry_ref,
            "geometry_sha256": sha256_json(geometry),
            "object_frame_id": item["object_frame_id"],
            "half_extents_m": item["half_extents_m"],
            "object_T_robot_target": _flatten(object_robot_target),
            "transform_provenance_ref": transform_ref,
        },
        "placement_target": {
            "target_ref": item["target_ref"],
            "target_object_pose": target_pose,
            "provenance_ref": placement_ref,
        },
    }


__all__ = [
    "OBJECT_GEOMETRY_SCHEMA_VERSION",
    "OBJECT_ROBOT_TARGET_TRANSFORM_SCHEMA_VERSION",
    "PLACEMENT_TARGET_SCHEMA_VERSION",
    "ROUTE_INPUT_PROFILE_SCHEMA_VERSION",
    "ROUTE_SCENE_FACTS_SCHEMA_VERSION",
    "RouteInputError",
    "canonical_json",
    "derive_bound_route_inputs",
    "sha256_json",
    "validate_scene_facts",
]

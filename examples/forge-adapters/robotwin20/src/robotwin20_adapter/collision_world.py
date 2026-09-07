"""Provider-owned collision-world projection for RoboTwin route planning.

The module is deliberately independent of Curobo and SAPIEN.  It turns the
validated benchmark scene facts into a provider-neutral artifact that the
runtime planner may consume during ``manipulation.prepare``.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from typing import Any

from .route_inputs import validate_scene_facts

SCENE_COLLISION_WORLD_SCHEMA_VERSION = "paos-robotwin20-collision-world/v1"


class CollisionWorldError(ValueError):
    """Collision-world source facts or projection bindings are invalid."""


def _artifact_ref(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.startswith("artifact://") or len(value) <= len("artifact://"):
        raise CollisionWorldError(f"{label} must be an artifact:// reference")
    return value


def _matrix(value: Any, label: str) -> list[list[float]]:
    if not isinstance(value, list) or len(value) != 16:
        raise CollisionWorldError(f"{label} must contain 16 numbers")
    if any(isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(float(item)) for item in value):
        raise CollisionWorldError(f"{label} must contain finite numbers")
    matrix = [list(map(float, value[index:index + 4])) for index in range(0, 16, 4)]
    if any(abs(matrix[3][index] - expected) > 1e-6 for index, expected in enumerate((0.0, 0.0, 0.0, 1.0))):
        raise CollisionWorldError(f"{label} homogeneous row is invalid")
    return matrix


def _rotation_to_xyzw(rotation: list[list[float]]) -> list[float]:
    trace = sum(rotation[index][index] for index in range(3))
    if trace > 0.0:
        scale = math.sqrt(trace + 1.0) * 2.0
        result = [
            (rotation[2][1] - rotation[1][2]) / scale,
            (rotation[0][2] - rotation[2][0]) / scale,
            (rotation[1][0] - rotation[0][1]) / scale,
            0.25 * scale,
        ]
    else:
        axis = max(range(3), key=lambda index: rotation[index][index])
        if axis == 0:
            scale = math.sqrt(max(1e-12, 1.0 + rotation[0][0] - rotation[1][1] - rotation[2][2])) * 2.0
            result = [0.25 * scale, (rotation[0][1] + rotation[1][0]) / scale, (rotation[0][2] + rotation[2][0]) / scale, (rotation[2][1] - rotation[1][2]) / scale]
        elif axis == 1:
            scale = math.sqrt(max(1e-12, 1.0 + rotation[1][1] - rotation[0][0] - rotation[2][2])) * 2.0
            result = [(rotation[0][1] + rotation[1][0]) / scale, 0.25 * scale, (rotation[1][2] + rotation[2][1]) / scale, (rotation[0][2] - rotation[2][0]) / scale]
        else:
            scale = math.sqrt(max(1e-12, 1.0 + rotation[2][2] - rotation[0][0] - rotation[1][1])) * 2.0
            result = [(rotation[0][2] + rotation[2][0]) / scale, (rotation[1][2] + rotation[2][1]) / scale, 0.25 * scale, (rotation[1][0] - rotation[0][1]) / scale]
    norm = math.sqrt(sum(item * item for item in result))
    if not math.isfinite(norm) or norm <= 1e-9:
        raise CollisionWorldError("world_T_entity rotation is degenerate")
    return [item / norm for item in result]


def _pose_from_matrix(value: Any, frame_id: str) -> dict[str, Any]:
    matrix = _matrix(value, "world_T_entity")
    return {
        "frame_id": frame_id,
        "position_m": [matrix[index][3] for index in range(3)],
        "orientation_xyzw": _rotation_to_xyzw([row[:3] for row in matrix[:3]]),
    }


def _canonical(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def collision_world_digest(value: Mapping[str, Any]) -> str:
    payload = dict(value)
    payload.pop("world_digest", None)
    return hashlib.sha256(_canonical(payload)).hexdigest()


def build_collision_world(
    scene_facts: Mapping[str, Any],
    *,
    target_entity_ref: str,
    source_scene_facts_ref: str,
    geometry_refs: Mapping[str, str],
    calibration_ref: str,
    world_revision: int = 1,
    coverage: str | None = None,
    planner_provider: str = "curobo",
    planner_profile: str = "franka-panda",
    cache_capacity: int | None = None,
) -> dict[str, Any]:
    """Project non-target benchmark objects into a static cuboid world."""

    facts = validate_scene_facts(scene_facts)
    _artifact_ref(source_scene_facts_ref, "source_scene_facts_ref")
    _artifact_ref(calibration_ref, "calibration_ref")
    if not isinstance(target_entity_ref, str) or not target_entity_ref.startswith("entity://"):
        raise CollisionWorldError("target_entity_ref is invalid")
    if not isinstance(world_revision, int) or isinstance(world_revision, bool) or world_revision < 1:
        raise CollisionWorldError("world_revision must be a positive integer")
    resolved_coverage = coverage if coverage is not None else facts.get("coverage", "unknown")
    if resolved_coverage not in {"complete", "partial", "unknown"}:
        raise CollisionWorldError("coverage must be complete, partial, or unknown")
    if resolved_coverage != "complete":
        raise CollisionWorldError("collision world requires complete scene coverage")
    objects = facts["objects"]
    entities = {item["entity_ref"]: item for item in objects}
    if target_entity_ref not in entities:
        raise CollisionWorldError("target entity is absent from scene facts")
    if not isinstance(geometry_refs, Mapping):
        raise CollisionWorldError("geometry_refs must map entity refs to artifact refs")
    obstacles: list[dict[str, Any]] = []
    for entity_ref, item in entities.items():
        if entity_ref == target_entity_ref:
            continue
        geometry_ref = _artifact_ref(geometry_refs.get(entity_ref), f"geometry_refs[{entity_ref}]")
        half_extents = item["half_extents_m"]
        if len(half_extents) != 3 or any(float(size) <= 0 or not math.isfinite(float(size)) for size in half_extents):
            raise CollisionWorldError("collision obstacle dimensions are invalid")
        obstacles.append({
            "entity_ref": entity_ref,
            "geometry_ref": geometry_ref,
            "shape": "cuboid",
            "half_extents_m": [float(size) for size in half_extents],
            "world_T_entity": _pose_from_matrix(item["world_T_object"], facts["route_frame_id"]),
            "state": "static",
            "provenance": [source_scene_facts_ref, geometry_ref],
        })
    resolved_cache_capacity = len(obstacles) if cache_capacity is None else cache_capacity
    if (
        not isinstance(resolved_cache_capacity, int)
        or isinstance(resolved_cache_capacity, bool)
        or resolved_cache_capacity < 1
    ):
        raise CollisionWorldError("cache_capacity must be a positive integer")
    if len(obstacles) > resolved_cache_capacity:
        raise CollisionWorldError("collision world exceeds planner cache capacity")
    result: dict[str, Any] = {
        "schema_version": SCENE_COLLISION_WORLD_SCHEMA_VERSION,
        "scene_revision": facts["scene_revision"],
        "world_revision": world_revision,
        "route_frame_id": facts["route_frame_id"],
        "pose_convention": "position_m + orientation_xyzw",
        "source_scene_facts_ref": source_scene_facts_ref,
        "source_scene_facts_sha256": hashlib.sha256(_canonical(facts)).hexdigest(),
        "calibration_ref": calibration_ref,
        "planner_provider": planner_provider,
        "planner_profile": planner_profile,
        "coverage": resolved_coverage,
        "obstacles": obstacles,
        "excluded_entities": [target_entity_ref],
        "target_entity_ref": target_entity_ref,
        "obstacle_count": len(obstacles),
        "cache_capacity": resolved_cache_capacity,
        "motion_authorized": False,
    }
    result["world_digest"] = collision_world_digest(result)
    return result


def validate_collision_world(value: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "schema_version", "scene_revision", "world_revision", "route_frame_id",
        "pose_convention", "source_scene_facts_ref", "source_scene_facts_sha256",
        "calibration_ref", "planner_provider", "planner_profile", "coverage",
        "obstacles", "excluded_entities", "target_entity_ref", "obstacle_count",
        "cache_capacity", "motion_authorized", "world_digest",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise CollisionWorldError("collision world fields are invalid")
    if value["schema_version"] != SCENE_COLLISION_WORLD_SCHEMA_VERSION:
        raise CollisionWorldError("collision world schema is unsupported")
    if value["pose_convention"] != "position_m + orientation_xyzw" or value["route_frame_id"] != "world":
        raise CollisionWorldError("collision world frame convention is invalid")
    if value["coverage"] != "complete" or value["motion_authorized"] is not False:
        raise CollisionWorldError("collision world coverage or motion boundary is invalid")
    _artifact_ref(value["source_scene_facts_ref"], "source_scene_facts_ref")
    _artifact_ref(value["calibration_ref"], "calibration_ref")
    if not isinstance(value["obstacles"], list) or value["obstacle_count"] != len(value["obstacles"]):
        raise CollisionWorldError("collision world obstacle count is invalid")
    excluded = value["excluded_entities"]
    if not isinstance(excluded, list) or excluded != [value["target_entity_ref"]]:
        raise CollisionWorldError("collision world target exclusion is invalid")
    seen: set[str] = set()
    for obstacle in value["obstacles"]:
        if not isinstance(obstacle, Mapping) or set(obstacle) != {
            "entity_ref", "geometry_ref", "shape", "half_extents_m", "world_T_entity", "state", "provenance",
        }:
            raise CollisionWorldError("collision obstacle fields are invalid")
        entity_ref = obstacle["entity_ref"]
        if not isinstance(entity_ref, str) or not entity_ref.startswith("entity://") or entity_ref in seen or entity_ref == value["target_entity_ref"]:
            raise CollisionWorldError("collision obstacle entity binding is invalid")
        seen.add(entity_ref)
        if obstacle["shape"] != "cuboid" or obstacle["state"] != "static":
            raise CollisionWorldError("collision obstacle shape/state is invalid")
        _artifact_ref(obstacle["geometry_ref"], "collision obstacle geometry_ref")
        if not isinstance(obstacle["provenance"], list) or any(not isinstance(item, str) or not item.startswith("artifact://") for item in obstacle["provenance"]):
            raise CollisionWorldError("collision obstacle provenance is invalid")
        extents = obstacle["half_extents_m"]
        if not isinstance(extents, list) or len(extents) != 3 or any(not isinstance(item, (int, float)) or isinstance(item, bool) or not math.isfinite(float(item)) or float(item) <= 0 for item in extents):
            raise CollisionWorldError("collision obstacle dimensions are invalid")
        pose = obstacle["world_T_entity"]
        if not isinstance(pose, Mapping) or set(pose) != {"frame_id", "position_m", "orientation_xyzw"} or pose["frame_id"] != value["route_frame_id"]:
            raise CollisionWorldError("collision obstacle pose is invalid")
        if len(pose["position_m"]) != 3 or len(pose["orientation_xyzw"]) != 4:
            raise CollisionWorldError("collision obstacle pose dimensions are invalid")
        quaternion = [float(item) for item in pose["orientation_xyzw"]]
        if any(not math.isfinite(item) for item in quaternion) or abs(math.sqrt(sum(item * item for item in quaternion)) - 1.0) > 1e-3:
            raise CollisionWorldError("collision obstacle quaternion is invalid")
    if value["cache_capacity"] < len(value["obstacles"]):
        raise CollisionWorldError("collision world cache capacity is insufficient")
    if value["world_digest"] != collision_world_digest(value):
        raise CollisionWorldError("collision world digest does not match contents")
    return dict(value)


__all__ = [
    "SCENE_COLLISION_WORLD_SCHEMA_VERSION",
    "CollisionWorldError",
    "build_collision_world",
    "collision_world_digest",
    "validate_collision_world",
]

"""Strict no-motion contract for complete route-readiness evaluation.

The adapter owns route geometry and frame conversion. A readiness provider may
evaluate IK, collision, limits, contact feasibility, and stop control, but it
does not decide task success and never grants motion authority.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Mapping

from .perception_profile import (
    PerceptionProfileError,
    _absolute_path,
    _read_unique_yaml,
    _worker_config,
)
from .process_worker import JsonlProcessWorkerClient

ROUTE_REQUEST_SCHEMA_VERSION = "paos-robotwin20-route-request/v7"
SIMULATION_ROUTE_READINESS_SCHEMA_VERSION = "paos-robotwin20-simulation-route-readiness/v2"
ROUTE_READINESS_PROFILE_SCHEMA_VERSION = "paos-robotwin20-route-readiness/v1"
ROUTE_PHASES = (
    "approach", "contact", "close", "lift", "transport", "descent", "release", "retreat",
)
ROUTE_CHECKS = (
    "attached_object_collision",
    "complete_transport_descent_retreat",
    "contact_dynamics",
    "workspace_and_joint_limits",
    "stop_control",
)


class RouteReadinessError(ValueError):
    """A route request or evidence record is malformed or unsafe."""


class RouteReadinessProfileError(RouteReadinessError):
    """A route-readiness worker profile is incomplete or unsafe."""


def _ref(value: Any, label: str, prefix: str | None = None) -> str:
    if not isinstance(value, str) or not value.strip() or (prefix and not value.startswith(prefix)):
        raise RouteReadinessError(f"{label} is invalid")
    return value


def _sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(
        char not in "0123456789abcdef" for char in value
    ):
        raise RouteReadinessError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _finite_vector(value: Any, length: int, label: str) -> tuple[float, ...]:
    if not isinstance(value, list) or len(value) != length:
        raise RouteReadinessError(f"{label} must be an array of length {length}")
    if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in value):
        raise RouteReadinessError(f"{label} must contain finite numbers")
    result = tuple(float(item) for item in value)
    if any(not math.isfinite(item) for item in result):
        raise RouteReadinessError(f"{label} must contain finite numbers")
    return result


def _pose(value: Any, frame_id: str, label: str) -> tuple[float, ...]:
    if not isinstance(value, Mapping) or set(value) != {
        "frame_id", "position_m", "orientation_xyzw",
    }:
        raise RouteReadinessError(f"{label} fields are invalid")
    if value["frame_id"] != frame_id:
        raise RouteReadinessError(f"{label} frame binding is invalid")
    position = _finite_vector(value["position_m"], 3, f"{label}.position_m")
    quaternion = _finite_vector(value["orientation_xyzw"], 4, f"{label}.orientation_xyzw")
    if abs(math.sqrt(sum(item * item for item in quaternion)) - 1.0) > 1e-3:
        raise RouteReadinessError(f"{label}.orientation_xyzw must be normalized")
    return position


def _quat_rotation(quaternion: tuple[float, ...]) -> list[list[float]]:
    x, y, z, w = quaternion
    return [
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ]


def _pose_matrix(value: Mapping[str, Any]) -> list[list[float]]:
    rotation = _quat_rotation(tuple(float(item) for item in value["orientation_xyzw"]))
    return [
        [*rotation[0], float(value["position_m"][0])],
        [*rotation[1], float(value["position_m"][1])],
        [*rotation[2], float(value["position_m"][2])],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _multiply(left: list[list[float]], right: list[list[float]]) -> list[list[float]]:
    return [
        [sum(left[row][index] * right[index][col] for index in range(4)) for col in range(4)]
        for row in range(4)
    ]


def _pose_matches_matrix(value: Mapping[str, Any], matrix: list[list[float]]) -> bool:
    if any(abs(float(value["position_m"][index]) - matrix[index][3]) > 1e-6 for index in range(3)):
        return False
    expected = matrix[:3]
    actual = _quat_rotation(tuple(float(item) for item in value["orientation_xyzw"]))
    return all(abs(actual[row][col] - expected[row][col]) <= 1e-5 for row in range(3) for col in range(3))


def _poses_match(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return left["frame_id"] == right["frame_id"] and (
        all(abs(float(a) - float(b)) <= 1e-6 for a, b in zip(left["position_m"], right["position_m"]))
        and all(abs(float(a) - float(b)) <= 1e-5 for a, b in zip(left["orientation_xyzw"], right["orientation_xyzw"]))
    )


def _direction(value: Any, frame_id: str, label: str) -> tuple[float, ...]:
    if not isinstance(value, Mapping) or set(value) != {
        "frame_id", "vector", "provenance_ref",
    }:
        raise RouteReadinessError(f"{label} fields are invalid")
    if value["frame_id"] != frame_id:
        raise RouteReadinessError(f"{label} frame binding is invalid")
    vector = _finite_vector(value["vector"], 3, f"{label}.vector")
    if abs(math.sqrt(sum(item * item for item in vector)) - 1.0) > 1e-3:
        raise RouteReadinessError(f"{label}.vector must be normalized")
    _ref(value["provenance_ref"], f"{label}.provenance_ref", "artifact://")
    return vector


def _transform(value: Any, label: str) -> None:
    matrix = _finite_vector(value, 16, label)
    if any(
        abs(matrix[index] - expected) > 1e-6
        for index, expected in zip((12, 13, 14, 15), (0.0, 0.0, 0.0, 1.0))
    ):
        raise RouteReadinessError(f"{label} homogeneous row is invalid")
    rows = [matrix[0:3], matrix[4:7], matrix[8:11]]
    for row in rows:
        if abs(sum(item * item for item in row) - 1.0) > 1e-3:
            raise RouteReadinessError(f"{label} rotation is invalid")
    for left, right in ((rows[0], rows[1]), (rows[0], rows[2]), (rows[1], rows[2])):
        if abs(sum(a * b for a, b in zip(left, right))) > 1e-3:
            raise RouteReadinessError(f"{label} rotation is invalid")
    determinant = (
        rows[0][0] * (rows[1][1] * rows[2][2] - rows[1][2] * rows[2][1])
        - rows[0][1] * (rows[1][0] * rows[2][2] - rows[1][2] * rows[2][0])
        + rows[0][2] * (rows[1][0] * rows[2][1] - rows[1][1] * rows[2][0])
    )
    if determinant <= 0:
        raise RouteReadinessError(f"{label} rotation is invalid")


def _workspace(value: Any, route_frame_id: str) -> Mapping[str, Any]:
    expected = {
        "frame_id", "x_min_m", "x_max_m", "y_min_m", "y_max_m", "z_min_m",
        "z_max_m", "provenance_ref",
    }
    if not isinstance(value, Mapping) or set(value) != expected:
        raise RouteReadinessError("workspace_bounds_m fields are invalid")
    if value["frame_id"] != route_frame_id:
        raise RouteReadinessError("workspace bounds and route must share a frame")
    _ref(value["provenance_ref"], "workspace_bounds_m.provenance_ref", "artifact://")
    for axis in "xyz":
        low, high = value[f"{axis}_min_m"], value[f"{axis}_max_m"]
        if any(
            isinstance(item, bool) or not isinstance(item, (int, float))
            or not math.isfinite(float(item)) for item in (low, high)
        ) or float(low) >= float(high):
            raise RouteReadinessError("workspace bounds are invalid")
    return value


def validate_route_request(request: Mapping[str, Any]) -> None:
    """Validate one complete adapter-owned route template before planner use."""

    required = {
        "schema_version", "request_id", "observation_ref", "observation_frame_id",
        "scene_revision", "frame_id", "calibration_ref", "calibration_sha256",
        "calibration_revision", "candidate_set_ref", "candidates", "workspace_bounds_m",
        "joint_limits_ref", "stop_policy_ref", "motion_capabilities",
        "controller_qualification", "collision_world",
    }
    if not isinstance(request, Mapping) or set(request) != required:
        raise RouteReadinessError("route readiness request fields are invalid")
    if request["schema_version"] != ROUTE_REQUEST_SCHEMA_VERSION:
        raise RouteReadinessError("route readiness request schema_version is unsupported")
    _ref(request["request_id"], "request_id")
    revision = _ref(request["scene_revision"], "scene_revision")
    observation_frame = _ref(request["observation_frame_id"], "observation_frame_id")
    route_frame = _ref(request["frame_id"], "frame_id")
    if request["observation_ref"] != f"observation://{revision}/{observation_frame}":
        raise RouteReadinessError("observation identity is invalid")
    if request["candidate_set_ref"] != f"candidate-set://{revision}/{observation_frame}":
        raise RouteReadinessError("candidate-set identity is invalid")
    _ref(request["calibration_ref"], "calibration_ref", "artifact://")
    _sha(request["calibration_sha256"], "calibration_sha256")
    _ref(request["calibration_revision"], "calibration_revision")
    _ref(request["joint_limits_ref"], "joint_limits_ref", "artifact://")
    _ref(request["stop_policy_ref"], "stop_policy_ref", "artifact://")
    collision_world = request["collision_world"]
    if not isinstance(collision_world, Mapping) or set(collision_world) != {
        "artifact_ref", "sha256", "scene_revision", "world_revision", "world_digest",
        "coverage", "target_entity_ref", "obstacle_entity_refs",
    }:
        raise RouteReadinessError("route collision world binding fields are invalid")
    _ref(collision_world["artifact_ref"], "collision world artifact_ref", "artifact://")
    _sha(collision_world["sha256"], "collision world sha256")
    _sha(collision_world["world_digest"], "collision world digest")
    if (
        collision_world["scene_revision"] != revision
        or collision_world["coverage"] != "complete"
        or not isinstance(collision_world["world_revision"], int)
        or isinstance(collision_world["world_revision"], bool)
        or collision_world["world_revision"] < 1
        or not isinstance(collision_world["target_entity_ref"], str)
        or not collision_world["target_entity_ref"].startswith("entity://")
    ):
        raise RouteReadinessError("route collision world binding is stale or incomplete")
    obstacle_refs = collision_world["obstacle_entity_refs"]
    if (
        not isinstance(obstacle_refs, list)
        or len(obstacle_refs) != len(set(obstacle_refs))
        or collision_world["target_entity_ref"] in obstacle_refs
        or any(not isinstance(item, str) or not item.startswith("entity://") for item in obstacle_refs)
    ):
        raise RouteReadinessError("route collision world obstacle binding is invalid")
    capabilities = request["motion_capabilities"]
    if not isinstance(capabilities, list) or len(capabilities) != 2:
        raise RouteReadinessError("route motion capabilities must bind both arms")
    seen_arms: set[str] = set()
    seen_refs: set[str] = set()
    for capability in capabilities:
        if not isinstance(capability, Mapping) or set(capability) != {
            "arm_id", "artifact_ref", "sha256", "validation_ref", "validation_sha256",
        }:
            raise RouteReadinessError("route motion capability binding fields are invalid")
        arm_id = capability["arm_id"]
        if arm_id not in {"left", "right"} or arm_id in seen_arms:
            raise RouteReadinessError("route motion capability arm binding is invalid")
        artifact_ref = _ref(
            capability["artifact_ref"], "motion capability artifact_ref", "artifact://"
        )
        validation_ref = _ref(
            capability["validation_ref"], "motion capability validation_ref", "artifact://"
        )
        if artifact_ref in seen_refs or validation_ref in seen_refs or artifact_ref == validation_ref:
            raise RouteReadinessError("route motion capability references are duplicated")
        _sha(capability["sha256"], "motion capability sha256")
        _sha(capability["validation_sha256"], "motion capability validation sha256")
        seen_arms.add(arm_id)
        seen_refs.update((artifact_ref, validation_ref))
    if seen_arms != {"left", "right"}:
        raise RouteReadinessError("route motion capabilities must bind both arms")
    qualification = request["controller_qualification"]
    if not isinstance(qualification, Mapping) or set(qualification) != {
        "qualification_id",
        "artifact_ref",
        "sha256",
        "plan_ref",
        "plan_sha256",
        "evidence_ref",
        "evidence_sha256",
        "validation_ref",
        "validation_sha256",
    }:
        raise RouteReadinessError("route controller qualification binding fields are invalid")
    _ref(qualification["qualification_id"], "controller qualification id")
    for field in ("artifact_ref", "plan_ref", "evidence_ref", "validation_ref"):
        reference = _ref(
            qualification[field], f"controller qualification {field}", "artifact://"
        )
        if reference in seen_refs:
            raise RouteReadinessError("route qualification references are duplicated")
        seen_refs.add(reference)
    for field in ("sha256", "plan_sha256", "evidence_sha256", "validation_sha256"):
        _sha(qualification[field], f"controller qualification {field}")
    bounds = _workspace(request["workspace_bounds_m"], route_frame)

    candidates = request["candidates"]
    if not isinstance(candidates, list) or not candidates:
        raise RouteReadinessError("route readiness candidates are empty")
    seen: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, Mapping) or set(candidate) != {
            "candidate_ref", "entity_ref", "provenance", "execution_grasp",
            "attached_object", "placement_target", "route",
        }:
            raise RouteReadinessError("route candidate fields are invalid")
        candidate_ref = _ref(candidate["candidate_ref"], "candidate_ref", "candidate://")
        if candidate_ref in seen:
            raise RouteReadinessError("route candidate identity is duplicated")
        seen.add(candidate_ref)
        _ref(candidate["entity_ref"], "entity_ref", "entity://")
        if candidate["entity_ref"] != collision_world["target_entity_ref"]:
            raise RouteReadinessError("route candidate target differs from collision world")
        provenance = candidate["provenance"]
        if not isinstance(provenance, list) or not provenance or any(
            not isinstance(item, str) or not item.startswith("artifact://") for item in provenance
        ):
            raise RouteReadinessError("route candidate provenance is invalid")

        grasp = candidate["execution_grasp"]
        if not isinstance(grasp, Mapping) or set(grasp) != {
            "contact_center_pose", "robot_target_pose", "robot_target_frame",
            "robot_target_round_trip_residual_m", "ingress_direction",
            "support_clear_direction", "adaptation_provenance_ref",
        }:
            raise RouteReadinessError("execution_grasp fields are invalid")
        if grasp["robot_target_frame"] != "robotwin_gripper":
            raise RouteReadinessError("execution_grasp.robot_target_frame is unsupported")
        residual = grasp["robot_target_round_trip_residual_m"]
        if isinstance(residual, bool) or not isinstance(residual, (int, float)) or not math.isfinite(float(residual)) or float(residual) > 1e-8:
            raise RouteReadinessError("execution_grasp RoboTwin target round-trip is invalid")
        _pose(grasp["contact_center_pose"], route_frame, "execution_grasp.contact_center_pose")
        _pose(grasp["robot_target_pose"], route_frame, "execution_grasp.robot_target_pose")
        _direction(grasp["ingress_direction"], route_frame, "execution_grasp.ingress_direction")
        _direction(
            grasp["support_clear_direction"], route_frame,
            "execution_grasp.support_clear_direction",
        )
        _ref(
            grasp["adaptation_provenance_ref"],
            "execution_grasp.adaptation_provenance_ref", "artifact://",
        )

        attached = candidate["attached_object"]
        if not isinstance(attached, Mapping) or set(attached) != {
            "geometry_ref", "geometry_sha256", "object_frame_id", "half_extents_m",
            "object_T_robot_target", "transform_provenance_ref",
        }:
            raise RouteReadinessError("attached object fields are invalid")
        _ref(attached["geometry_ref"], "attached_object.geometry_ref", "artifact://")
        _sha(attached["geometry_sha256"], "attached_object.geometry_sha256")
        _ref(attached["object_frame_id"], "attached_object.object_frame_id")
        half_extents = _finite_vector(
            attached["half_extents_m"], 3, "attached_object.half_extents_m"
        )
        if any(value <= 0 for value in half_extents):
            raise RouteReadinessError("attached object half extents must be positive")
        _transform(attached["object_T_robot_target"], "attached_object.object_T_robot_target")
        _ref(
            attached["transform_provenance_ref"],
            "attached_object.transform_provenance_ref", "artifact://",
        )

        placement = candidate["placement_target"]
        if not isinstance(placement, Mapping) or set(placement) != {
            "target_ref", "target_object_pose", "release_robot_target_pose", "provenance_ref",
        }:
            raise RouteReadinessError("placement_target fields are invalid")
        _ref(placement["target_ref"], "placement_target.target_ref", "destination://")
        target_pose = placement["target_object_pose"]
        release_pose = placement["release_robot_target_pose"]
        _pose(target_pose, route_frame, "placement_target.target_object_pose")
        _pose(release_pose, route_frame, "placement_target.release_robot_target_pose")
        transform = [
            [float(attached["object_T_robot_target"][row * 4 + col]) for col in range(4)]
            for row in range(4)
        ]
        if not _pose_matches_matrix(release_pose, _multiply(_pose_matrix(target_pose), transform)):
            raise RouteReadinessError("release RoboTwin target pose is inconsistent with object_T_robot_target")
        _ref(placement["provenance_ref"], "placement_target.provenance_ref", "artifact://")

        route = candidate["route"]
        if not isinstance(route, list) or [
            item.get("phase") for item in route if isinstance(item, Mapping)
        ] != list(ROUTE_PHASES):
            raise RouteReadinessError("route phases must be complete and ordered")
        expected_gripper = {
            "approach": "open", "contact": "contact", "close": "closed", "lift": "closed",
            "transport": "closed", "descent": "closed", "release": "released", "retreat": "open",
        }
        for item in route:
            if not isinstance(item, Mapping) or set(item) != {
                "phase", "waypoints", "gripper_state",
            }:
                raise RouteReadinessError("route phase fields are invalid")
            if item["gripper_state"] != expected_gripper[item["phase"]]:
                raise RouteReadinessError("route gripper state is inconsistent with phase")
            waypoints = item["waypoints"]
            if not isinstance(waypoints, list) or not waypoints:
                raise RouteReadinessError("route phase must contain waypoints")
            for index, waypoint in enumerate(waypoints):
                position = _pose(
                    waypoint, route_frame, f"route.{item['phase']}.waypoints[{index}]"
                )
                conservative_extent = max(half_extents)
                for axis, coordinate in zip("xyz", position):
                    if (
                        coordinate - conservative_extent < float(bounds[f"{axis}_min_m"])
                        or coordinate + conservative_extent > float(bounds[f"{axis}_max_m"])
                    ):
                        raise RouteReadinessError(
                            "route waypoint or attached object exceeds workspace bounds"
                        )
        by_phase = {item["phase"]: item for item in route}
        if not _poses_match(by_phase["contact"]["waypoints"][0], by_phase["close"]["waypoints"][0]):
            raise RouteReadinessError("contact and close waypoints are inconsistent")
        if not _poses_match(by_phase["lift"]["waypoints"][0], by_phase["transport"]["waypoints"][0]):
            raise RouteReadinessError("lift and transport waypoints are inconsistent")
        if not _poses_match(by_phase["descent"]["waypoints"][-1], release_pose):
            raise RouteReadinessError("descent does not terminate at release RoboTwin target pose")
        if not _poses_match(by_phase["release"]["waypoints"][0], release_pose):
            raise RouteReadinessError("release waypoint is not bound to release RoboTwin target pose")


def route_geometry_digest(request: Mapping[str, Any]) -> str:
    validate_route_request(request)
    payload = json.dumps(request, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class RouteReadinessEvaluationAdapter:
    """Adapt the worker contract to the selector's independent result schema.

    The worker owns only bounded route evidence.  This adapter performs no
    planning and never upgrades unavailable evidence to a passing result.
    """

    def __init__(self, client: "RouteReadinessClient") -> None:
        if not callable(getattr(client, "evaluate", None)):
            raise TypeError("route readiness client must expose evaluate(request)")
        self.client = client

    def evaluate(
        self, request: Mapping[str, Any], option: Mapping[str, Any]
    ) -> dict[str, Any]:
        validate_route_request(request)
        if not isinstance(option, Mapping) or not isinstance(option.get("candidate_ref"), str):
            raise RouteReadinessProfileError("route evaluation option is invalid")
        candidate_ref = option["candidate_ref"]
        candidate = next(
            (item for item in request["candidates"] if item["candidate_ref"] == candidate_ref),
            None,
        )
        if candidate is None:
            raise RouteReadinessProfileError("route evaluation option is not bound to request")
        response = self.client.evaluate(request)
        evidence = response.get("route_evidence") if isinstance(response, Mapping) else None
        item = next(
            (
                value for value in evidence or ()
                if isinstance(value, Mapping) and value.get("candidate_ref") == candidate_ref
            ),
            None,
        )
        if not isinstance(item, Mapping):
            raise RouteReadinessProfileError("route evaluation evidence is missing candidate")
        checks = item.get("checks")
        if not isinstance(checks, Mapping) or set(checks) != set(ROUTE_CHECKS):
            raise RouteReadinessProfileError("route evaluation evidence checks are invalid")
        if any(value not in {"pass", "fail", "unavailable"} for value in checks.values()):
            raise RouteReadinessProfileError("route evaluation evidence check status is invalid")
        status = "pass" if all(value == "pass" for value in checks.values()) else (
            "unavailable" if response.get("status") == "unavailable" else "fail"
        )
        if status == "unavailable" and any(value != "unavailable" for value in checks.values()):
            raise RouteReadinessProfileError("unavailable route evidence has inconsistent checks")
        evidence_refs = item.get("evidence")
        if not isinstance(evidence_refs, list) or not evidence_refs or any(
            not isinstance(ref, str) or not ref.startswith("artifact://")
            for ref in evidence_refs
        ):
            raise RouteReadinessProfileError("route evaluation evidence refs are invalid")
        code = "ok" if status == "pass" else (
            "provider_unavailable" if status == "unavailable" else "route_rejected"
        )
        owner = "readiness" if status == "pass" else "infrastructure" if status == "unavailable" else "readiness"
        positions = [
            waypoint["position_m"]
            for phase in candidate["route"]
            for waypoint in phase["waypoints"]
        ]
        route_length = sum(
            math.dist(previous, current)
            for previous, current in zip(positions, positions[1:])
        )
        return {
            "schema_version": "paos-robotwin20-route-evaluation/v1",
            "request_id": request["request_id"],
            "task_id": option.get("task_id"),
            "revision_id": option.get("revision_id"),
            "node_id": option.get("node_id"),
            "node_digest": option.get("node_digest"),
            "candidate_ref": candidate_ref,
            "entity_ref": candidate["entity_ref"],
            "observation_ref": option.get("observation_ref", request["observation_ref"]),
            "scene_revision": option.get("scene_revision", request["scene_revision"]),
            "observation_frame_id": option.get("observation_frame_id", request["observation_frame_id"]),
            "frame_id": option.get("frame_id", request["frame_id"]),
            "calibration_ref": option.get("calibration_ref", request["calibration_ref"]),
            "candidate_set_ref": option.get("candidate_set_ref", request["candidate_set_ref"]),
            "arm_ids": list(option.get("arm_ids", ())),
            "option_id": option.get("option_id"),
            "status": status,
            "checks": dict(checks),
            "phase": "none",
            "code": code,
            "owner": owner,
            "detail": "route evidence accepted" if status == "pass" else "route readiness unavailable" if status == "unavailable" else "route evidence rejected",
            "route_geometry_digest": route_geometry_digest(request),
            "evidence_refs": list(evidence_refs),
            "motion_authorized": False,
            "world_change_started": False,
            "metrics": {"route_length_m": route_length, "min_joint_speed_margin_radps": 0.0},
        }


class RouteReadinessClient:
    """Profile-owned bounded JSONL client for an external no-motion worker."""

    def __init__(self, client: JsonlProcessWorkerClient, *, worker_id: str) -> None:
        if not isinstance(worker_id, str) or not worker_id.strip():
            raise RouteReadinessProfileError("route readiness worker_id must be non-empty")
        self.client = client
        self.worker_id = worker_id

    def evaluate(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        validate_route_request(request)
        response = self.client.request(dict(request))
        if response.get("request_id") != request["request_id"]:
            raise RouteReadinessProfileError("route readiness response identity mismatch")
        if response.get("schema_version") != SIMULATION_ROUTE_READINESS_SCHEMA_VERSION:
            raise RouteReadinessProfileError("route readiness response schema mismatch")
        if response.get("worker_id") != self.worker_id:
            raise RouteReadinessProfileError("route readiness worker identity mismatch")
        if response.get("motion_authorized") is not False:
            raise RouteReadinessProfileError("route readiness worker is not no-motion")
        if response.get("world_change_started") is not False:
            raise RouteReadinessProfileError("route readiness worker world-change state is invalid")
        if response.get("status") != "unavailable" or response.get("provider_available") is not False:
            raise RouteReadinessProfileError(
                "route readiness worker must remain unavailable until capabilities exist"
            )
        evidence = response.get("route_evidence")
        if not isinstance(evidence, list) or len(evidence) != len(request["candidates"]):
            raise RouteReadinessProfileError("route readiness evidence cardinality is invalid")
        expected = {
            candidate["candidate_ref"]: candidate["entity_ref"]
            for candidate in request["candidates"]
        }
        seen: set[str] = set()
        geometry_digest = route_geometry_digest(request)
        for item in evidence:
            candidate_ref = item.get("candidate_ref") if isinstance(item, Mapping) else None
            if candidate_ref not in expected or candidate_ref in seen:
                raise RouteReadinessProfileError("route readiness evidence candidate is unbound")
            seen.add(candidate_ref)
            if (
                item.get("entity_ref") != expected[candidate_ref]
                or item.get("request_id") != request["request_id"]
                or item.get("candidate_set_ref") != request["candidate_set_ref"]
                or item.get("observation_ref") != request["observation_ref"]
                or item.get("scene_revision") != request["scene_revision"]
                or item.get("frame_id") != request["frame_id"]
                or item.get("calibration_ref") != request["calibration_ref"]
                or item.get("calibration_sha256") != request["calibration_sha256"]
                or item.get("calibration_revision") != request["calibration_revision"]
                or item.get("route_geometry_digest") != geometry_digest
                or item.get("task_success_authorized") is not False
                or item.get("motion_authorized") is not False
                or item.get("world_change_started") is not False
                or not isinstance(item.get("checks"), Mapping)
                or set(item["checks"]) != set(ROUTE_CHECKS)
                or any(value != "unavailable" for value in item["checks"].values())
            ):
                raise RouteReadinessProfileError("route readiness evidence identity is invalid")
        return dict(response)

    def release(self) -> None:
        self.client.release()


def load_route_readiness_profile(path: str | os.PathLike[str]) -> dict[str, Any]:
    profile_path = Path(path).expanduser()
    if not profile_path.is_absolute() or not profile_path.is_file() or profile_path.is_symlink():
        raise RouteReadinessProfileError(
            "route readiness profile must be an existing absolute regular file"
        )
    return _read_unique_yaml(
        profile_path,
        error_type=RouteReadinessProfileError,
        label="route readiness profile",
    )


def build_route_readiness_client(
    profile: Mapping[str, Any], *, environ: Mapping[str, str] | None = None
) -> RouteReadinessClient:
    required = {"schema_version", "worker_id", "artifact_root", "worker"}
    if not isinstance(profile, Mapping) or set(profile) != required:
        raise RouteReadinessProfileError("route readiness profile fields are invalid")
    if profile.get("schema_version") != ROUTE_READINESS_PROFILE_SCHEMA_VERSION:
        raise RouteReadinessProfileError("route readiness profile schema_version is unsupported")
    variables = dict(os.environ if environ is None else environ)
    worker_id = profile.get("worker_id")
    if not isinstance(worker_id, str) or not worker_id.strip():
        raise RouteReadinessProfileError("route readiness worker_id is invalid")
    try:
        artifact_root = _absolute_path(
            profile.get("artifact_root"), variables, "route artifact_root", must_be_directory=True
        )
        worker_config = _worker_config(profile.get("worker"), variables, "route worker")
    except PerceptionProfileError as exc:
        raise RouteReadinessProfileError(str(exc)) from exc
    arguments = worker_config.command
    if "--artifact-root" not in arguments or str(artifact_root) not in arguments:
        raise RouteReadinessProfileError("route worker must bind the configured artifact_root")
    if "--worker-id" not in arguments or worker_id not in arguments:
        raise RouteReadinessProfileError("route worker must bind the configured worker_id")
    return RouteReadinessClient(JsonlProcessWorkerClient(worker_config), worker_id=worker_id)


def project_route_evidence(
    request: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    capability_status: Mapping[str, str],
    evidence_ref: str,
) -> dict[str, Any]:
    """Project readiness evidence without task verdict or motion authority."""

    validate_route_request(request)
    if candidate not in request["candidates"]:
        raise RouteReadinessError("route candidate is not bound to request")
    if not isinstance(capability_status, Mapping) or set(capability_status) != set(ROUTE_CHECKS):
        raise RouteReadinessError("route capability status fields are invalid")
    if any(status not in {"pass", "fail", "unavailable"} for status in capability_status.values()):
        raise RouteReadinessError("route capability status is invalid")
    _ref(evidence_ref, "evidence_ref", "artifact://")
    return {
        "schema_version": SIMULATION_ROUTE_READINESS_SCHEMA_VERSION,
        "request_id": request["request_id"],
        "candidate_ref": candidate["candidate_ref"],
        "entity_ref": candidate["entity_ref"],
        "candidate_set_ref": request["candidate_set_ref"],
        "observation_ref": request["observation_ref"],
        "scene_revision": request["scene_revision"],
        "frame_id": request["frame_id"],
        "calibration_ref": request["calibration_ref"],
        "calibration_sha256": request["calibration_sha256"],
        "calibration_revision": request["calibration_revision"],
        "checks": dict(capability_status),
        "route_geometry_digest": route_geometry_digest(request),
        "evidence": [evidence_ref],
        "task_success_authorized": False,
        "motion_authorized": False,
        "world_change_started": False,
    }


__all__ = [
    "ROUTE_CHECKS", "ROUTE_PHASES", "ROUTE_READINESS_PROFILE_SCHEMA_VERSION",
    "ROUTE_REQUEST_SCHEMA_VERSION", "SIMULATION_ROUTE_READINESS_SCHEMA_VERSION",
    "RouteReadinessClient", "RouteReadinessEvaluationAdapter", "RouteReadinessError", "RouteReadinessProfileError",
    "build_route_readiness_client", "load_route_readiness_profile", "project_route_evidence",
    "route_geometry_digest", "validate_route_request",
]

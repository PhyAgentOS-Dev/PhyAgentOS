"""No-motion benchmark scene-fact producer for complete route materialization."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from robotwin_backend import RoboTwinRuntimeProfile, RoboTwinSensorBackend, load_runtime_profile

from robotwin20_adapter.route_inputs import ROUTE_SCENE_FACTS_SCHEMA_VERSION, validate_scene_facts


class RouteInputWorkerError(RuntimeError):
    pass


_ENTITIES = (
    ("entity://block-red-1", "block1", "red-slot"),
    ("entity://block-green-1", "block2", "green-slot"),
    ("entity://block-blue-1", "block3", "blue-slot"),
)


def _matrix(pose: Any) -> list[list[float]]:
    matrix = pose.to_transformation_matrix()
    return [[float(matrix[row][column]) for column in range(4)] for row in range(4)]


def _flatten(matrix: list[list[float]]) -> list[float]:
    return [item for row in matrix for item in row]


def _multiply(left: list[list[float]], right: list[list[float]]) -> list[list[float]]:
    return [[sum(left[row][i] * right[i][column] for i in range(4)) for column in range(4)] for row in range(4)]


def _inverse_rigid(value: list[list[float]]) -> list[list[float]]:
    rotation = [row[:3] for row in value[:3]]
    transpose = [[rotation[column][row] for column in range(3)] for row in range(3)]
    translation = [value[row][3] for row in range(3)]
    inverse_translation = [-sum(transpose[row][column] * translation[column] for column in range(3)) for row in range(3)]
    return [[*transpose[0], inverse_translation[0]], [*transpose[1], inverse_translation[1]], [*transpose[2], inverse_translation[2]], [0.0, 0.0, 0.0, 1.0]]


def _pose_from_pq_wxyz(value: Any) -> Any:
    import sapien

    if not isinstance(value, (list, tuple)) or len(value) != 7 or any(
        isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(float(item)) for item in value
    ):
        raise RouteInputWorkerError("benchmark functional target pose is invalid")
    return sapien.Pose([float(item) for item in value[:3]], [float(item) for item in value[3:]])


def _half_extents(actor: Any) -> list[float]:
    components = getattr(actor.actor, "components", None)
    if not isinstance(components, list):
        raise RouteInputWorkerError("actor physics components are unavailable")
    shapes = []
    for component in components:
        getter = getattr(component, "get_collision_shapes", None)
        if callable(getter):
            shapes.extend(getter())
    if len(shapes) != 1 or not callable(getattr(shapes[0], "get_half_size", None)):
        raise RouteInputWorkerError("actor must expose one box collision shape")
    values = [float(item) for item in shapes[0].get_half_size()]
    if len(values) != 3 or any(not math.isfinite(item) or item <= 0 for item in values):
        raise RouteInputWorkerError("actor collision half extents are invalid")
    local_pose = shapes[0].get_local_pose()
    local_matrix = _matrix(local_pose)
    identity = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
    if any(abs(local_matrix[row][column] - identity[row][column]) > 1e-6 for row in range(4) for column in range(4)):
        raise RouteInputWorkerError("non-identity collision-shape pose is unsupported")
    return values


def capture_scene_facts(
    *, runtime_root: Path, runtime_profile: Path, artifact_root: Path, calibration_ref: str
) -> dict[str, Any]:
    profile = load_runtime_profile(runtime_profile)
    task_file = runtime_root / "envs" / f"{profile['task_name']}.py"
    if not task_file.is_file() or task_file.is_symlink():
        raise RouteInputWorkerError("benchmark task definition is unavailable")
    backend = RoboTwinSensorBackend(
        RoboTwinRuntimeProfile(
            runtime_root=runtime_root,
            artifact_root=artifact_root,
            task_name=profile["task_name"],
            task_config=profile["task_config"],
            embodiment=profile["embodiment"],
        )
    )
    try:
        backend.reset(seed=profile["seed"])
        task = backend._task
        if task is None or backend.snapshot().get("scene_revision") != f"{profile['task_name']}-{profile['seed']}-1":
            raise RouteInputWorkerError("benchmark scene revision is unavailable")
        objects = []
        for entity_ref, actor_attribute, target_token in _ENTITIES:
            actor = getattr(task, actor_attribute, None)
            target_value = getattr(task, f"{actor_attribute}_target_pose", None)
            if actor is None or not callable(getattr(actor, "get_functional_point", None)):
                raise RouteInputWorkerError("benchmark actor binding is unavailable")
            world_object = _matrix(actor.get_pose())
            world_functional = _matrix(actor.get_functional_point(0, "pose"))
            world_functional_target = _matrix(_pose_from_pq_wxyz(target_value))
            object_functional = _multiply(_inverse_rigid(world_object), world_functional)
            world_object_target = _multiply(world_functional_target, _inverse_rigid(object_functional))
            objects.append(
                {
                    "entity_ref": entity_ref,
                    "actor_name": actor_attribute,
                    "object_frame_id": entity_ref.removeprefix("entity://"),
                    "world_T_object": _flatten(world_object),
                    "world_T_functional_point": _flatten(world_functional),
                    "world_T_functional_target": _flatten(world_functional_target),
                    "world_T_object_target": _flatten(world_object_target),
                    "half_extents_m": _half_extents(actor),
                    "target_ref": f"destination://blocks-ranking-rgb/{target_token}",
                    "functional_point_id": 0,
                }
            )
        value = {
            "schema_version": ROUTE_SCENE_FACTS_SCHEMA_VERSION,
            "task_name": profile["task_name"],
            "seed": profile["seed"],
            "scene_revision": f"{profile['task_name']}-{profile['seed']}-1",
            "observation_ref": f"observation://{profile['task_name']}-{profile['seed']}-1/head_camera",
            "observation_frame_id": "head_camera",
            "route_frame_id": "world",
            "calibration_ref": calibration_ref,
            "task_definition": {
                "relative_path": str(task_file.relative_to(runtime_root)),
                "sha256": hashlib.sha256(task_file.read_bytes()).hexdigest(),
            },
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "robot_control_steps": 0,
            "motion_authorized": False,
            "coverage": "complete",
            "objects": objects,
        }
        validate_scene_facts(value)
        return value
    finally:
        backend.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--runtime-profile", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--calibration-ref", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for path, label, directory in (
        (args.runtime_root, "runtime root", True),
        (args.runtime_profile, "runtime profile", False),
        (args.artifact_root, "artifact root", True),
    ):
        if not path.is_absolute() or path.is_symlink() or (not path.is_dir() if directory else not path.is_file()):
            raise SystemExit(f"{label} must be an absolute {'directory' if directory else 'file'}")
    if not args.output.is_absolute() or args.output.exists() or args.output.is_symlink():
        raise SystemExit("output must be a new absolute file")
    value = capture_scene_facts(
        runtime_root=args.runtime_root.resolve(),
        runtime_profile=args.runtime_profile.resolve(),
        artifact_root=args.artifact_root.resolve(),
        calibration_ref=args.calibration_ref,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, separators=(",", ":"))
        stream.write("\n")
    args.output.chmod(0o600)
    print(json.dumps({"status": "completed", "output": str(args.output), "motion_authorized": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

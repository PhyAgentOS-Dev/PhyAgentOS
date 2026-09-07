"""RoboTwin-only bridge from PAOS collision-world artifacts to Curobo."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from robotwin20_adapter.collision_world import validate_collision_world


class CuroboWorldPortError(RuntimeError):
    """The provider could not apply a collision world to all planners."""


def _obb_capacity(motion_gen: Any) -> int:
    """Return the provider-reported OBB cache capacity (zero when unavailable)."""

    cache = getattr(motion_gen, "collision_cache", None)
    if isinstance(cache, Mapping):
        value = cache.get("obb")
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    checker = getattr(motion_gen, "world_coll_checker", None)
    tensors = getattr(checker, "_cube_tensor_list", None)
    if tensors:
        try:
            return int(tensors[0].shape[1])
        except (AttributeError, IndexError, TypeError, ValueError):
            return 0
    return 0


def _rebuild_motion_generators(
    planner: Any, world: Any, cache_capacity: int
) -> tuple[Any, Any]:
    """Build warmed MotionGen instances using RoboTwin's native planner settings."""

    from curobo.wrap.reacher.motion_gen import MotionGen, MotionGenConfig
    from envs import _GLOBAL_CONFIGS as CONFIGS

    yml_path = getattr(planner, "yml_path", None)
    if not yml_path:
        raise CuroboWorldPortError("planner does not expose its RoboTwin robot config")
    existing = planner.motion_gen
    common: dict[str, Any] = {
        "interpolation_dt": 1 / 250,
        "num_trajopt_seeds": 1,
        "collision_cache": {"obb": cache_capacity},
        "use_cuda_graph": bool(getattr(existing, "use_cuda_graph", True)),
    }
    tensor_args = getattr(existing, "tensor_args", None)
    if tensor_args is not None:
        common["tensor_args"] = tensor_args
    config = MotionGenConfig.load_from_robot_config(yml_path, world, **common)
    rebuilt = MotionGen(config)
    rebuilt.warmup()

    batch_common = dict(common)
    batch_common["num_graph_seeds"] = 1
    batch_config = MotionGenConfig.load_from_robot_config(yml_path, world, **batch_common)
    rebuilt_batch = MotionGen(batch_config)
    rebuilt_batch.warmup(batch=CONFIGS.ROTATE_NUM)
    return rebuilt, rebuilt_batch


def _world_pose_for_planner(planner: Any, pose: Mapping[str, Any]) -> list[float]:
    import numpy as np

    quaternion = pose["orientation_xyzw"]
    world_pose = np.asarray(
        [*pose["position_m"], quaternion[3], quaternion[0], quaternion[1], quaternion[2]],
        dtype=np.float64,
    )
    base_pose = np.asarray(
        [*planner.robot_origion_pose.p, *planner.robot_origion_pose.q], dtype=np.float64
    )
    position, rotation = planner._trans_from_world_to_base(base_pose, world_pose)
    return [*map(float, position), *map(float, rotation)]


def _world_config(planner: Any, artifact: Mapping[str, Any]) -> Any:
    from curobo.geom.types import Cuboid, WorldConfig

    base_world = getattr(planner, "_paos_collision_base_world", None)
    if base_world is None:
        base_world = planner.motion_gen.world_model.clone()
        planner._paos_collision_base_world = base_world.clone()
    cuboids = list(base_world.cuboid)
    names = {item.name for item in cuboids}
    for obstacle in artifact["obstacles"]:
        name = str(obstacle["entity_ref"]).removeprefix("entity://")
        if name in names:
            raise CuroboWorldPortError(f"collision obstacle duplicates planner object: {name}")
        cuboids.append(
            Cuboid(
                name=name,
                dims=[2.0 * float(value) for value in obstacle["half_extents_m"]],
                pose=_world_pose_for_planner(planner, obstacle["world_T_entity"]),
            )
        )
    return WorldConfig(cuboid=cuboids)


def apply_collision_world(
    planners: Mapping[str, Any] | Sequence[Any], artifact: Mapping[str, Any]
) -> dict[str, Any]:
    """Apply one artifact to both arm planners and their batch planners.

    The function performs no scene stepping and returns a provider receipt.  A
    partial update is reported as an error instead of being treated as ready.
    """

    if isinstance(planners, Mapping):
        selected = [planners.get("left"), planners.get("right")]
    else:
        selected = list(planners)
    if len(selected) != 2 or any(item is None for item in selected):
        raise CuroboWorldPortError("both arm planners are required")
    try:
        world_artifact = validate_collision_world(artifact)
    except ValueError as exc:
        raise CuroboWorldPortError("collision world artifact is invalid") from exc
    prepared = []
    for planner in selected:
        motion_gen = getattr(planner, "motion_gen", None)
        batch = getattr(planner, "motion_gen_batch", None)
        if motion_gen is None or batch is None or not callable(getattr(motion_gen, "update_world", None)) or not callable(getattr(batch, "update_world", None)):
            raise CuroboWorldPortError("planner does not expose motion_gen and motion_gen_batch update_world")
        world = _world_config(planner, world_artifact)
        required_capacity = len(world.cuboid)
        prepared.append(
            (
                planner,
                motion_gen,
                batch,
                world,
                required_capacity,
                motion_gen.world_model.clone(),
                batch.world_model.clone(),
            )
        )
    rebuild_required = any(
        min(_obb_capacity(motion_gen), _obb_capacity(batch)) < required_capacity
        for _, motion_gen, batch, _, required_capacity, _, _ in prepared
    )
    receipts = []
    applied = []
    original_refs = [(planner, motion_gen, batch) for planner, motion_gen, batch, *_ in prepared]
    try:
        if rebuild_required:
            replacements = []
            for planner, motion_gen, batch, world, required_capacity, _, _ in prepared:
                cache_capacity = max(required_capacity, int(world_artifact["cache_capacity"]))
                rebuilt, rebuilt_batch = _rebuild_motion_generators(
                    planner, world, cache_capacity
                )
                replacements.append((planner, rebuilt, rebuilt_batch))
            for planner, rebuilt, rebuilt_batch in replacements:
                planner.motion_gen = rebuilt
                planner.motion_gen_batch = rebuilt_batch
        else:
            for planner, motion_gen, batch, world, _, old_world, old_batch_world in prepared:
                motion_gen.update_world(world)
                applied.append((motion_gen, old_world))
                batch.update_world(world)
                applied.append((batch, old_batch_world))
        for planner, *_ in prepared:
            receipts.append({
                "planner": id(planner),
                "world_revision": world_artifact["world_revision"],
                "world_digest": world_artifact["world_digest"],
                "operation": "rebuild_motion_gen" if rebuild_required else "update_world",
            })
    except Exception as exc:
        for motion_gen, previous_world in reversed(applied):
            try:
                motion_gen.update_world(previous_world)
            except Exception:
                pass
        if rebuild_required:
            for planner, motion_gen, batch in original_refs:
                planner.motion_gen = motion_gen
                planner.motion_gen_batch = batch
        raise CuroboWorldPortError("collision world update failed and was rolled back") from exc
    return {
        "schema_version": "paos-robotwin20-curobo-world-update/v1",
        "scene_revision": world_artifact["scene_revision"],
        "world_revision": world_artifact["world_revision"],
        "world_digest": world_artifact["world_digest"],
        "arm_receipts": receipts,
        "motion_authorized": False,
    }


__all__ = ["CuroboWorldPortError", "apply_collision_world"]

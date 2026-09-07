from __future__ import annotations

from copy import deepcopy

import pytest

from robotwin20_adapter.route_inputs import (
    OBJECT_GEOMETRY_SCHEMA_VERSION,
    OBJECT_ROBOT_TARGET_TRANSFORM_SCHEMA_VERSION,
    ROUTE_SCENE_FACTS_SCHEMA_VERSION,
    RouteInputError,
    derive_bound_route_inputs,
    validate_scene_facts,
)


def _identity(x=0.0, y=0.0, z=0.0):
    return [1, 0, 0, x, 0, 1, 0, y, 0, 0, 1, z, 0, 0, 0, 1]


def _facts():
    objects = []
    for color, x in (("red", -0.1), ("green", 0.0), ("blue", 0.1)):
        objects.append(
            {
                "entity_ref": f"entity://block-{color}-1",
                "actor_name": f"block-{color}",
                "object_frame_id": f"block-{color}-1",
                "world_T_object": _identity(x, 0.0, 0.76),
                "world_T_functional_point": _identity(x, 0.0, 0.74),
                "world_T_functional_target": _identity(x, -0.1, 0.74),
                "world_T_object_target": _identity(x, -0.1, 0.76),
                "half_extents_m": [0.02, 0.02, 0.02],
                "target_ref": f"destination://blocks-ranking-rgb/{color}-slot",
                "functional_point_id": 0,
            }
        )
    return {
        "schema_version": ROUTE_SCENE_FACTS_SCHEMA_VERSION,
        "task_name": "blocks_ranking_rgb",
        "seed": 0,
        "scene_revision": "blocks_ranking_rgb-0-1",
        "observation_ref": "observation://blocks_ranking_rgb-0-1/head_camera",
        "observation_frame_id": "head_camera",
        "route_frame_id": "world",
        "calibration_ref": "artifact://capture/calibration",
        "task_definition": {"relative_path": "envs/blocks_ranking_rgb.py", "sha256": "a" * 64},
        "captured_at": "2026-09-05T00:00:00+00:00",
        "robot_control_steps": 0,
        "motion_authorized": False,
        "coverage": "complete",
        "objects": objects,
    }


def _grasp():
    return {
        "contact_center_pose": {
            "frame_id": "world",
            "position_m": [0.01, 0.01, 0.77],
            "orientation_xyzw": [0.0, 0.0, 0.0, 1.0],
        },
        "robot_target_pose": {
            "frame_id": "world",
            "position_m": [0.01, 0.01, 0.65],
            "orientation_xyzw": [2 ** -0.5, 0.0, 2 ** -0.5, 0.0],
        },
        "robot_target_frame": "robotwin_gripper",
        "robot_target_round_trip_residual_m": 0.0,
        "adaptation_provenance_ref": "artifact://route/adaptation",
    }


def test_route_inputs_derive_non_identity_measured_object_robot_target_and_placement():
    facts = _facts()
    value = derive_bound_route_inputs(
        facts,
        entity_ref="entity://block-green-1",
        execution_grasp=_grasp(),
        scene_facts_ref="artifact://route/scene-facts",
        geometry_ref="artifact://route/geometry",
        transform_ref="artifact://route/object-t-robot-target",
        placement_ref="artifact://route/placement",
        semantic_tolerance={"target_position_m": 0.04, "target_orientation_rad": 0.35},
        contact_shell_tolerance_m=0.015,
    )
    assert value["geometry_artifact"]["schema_version"] == OBJECT_GEOMETRY_SCHEMA_VERSION
    assert value["transform_artifact"]["schema_version"] == OBJECT_ROBOT_TARGET_TRANSFORM_SCHEMA_VERSION
    assert value["attached_object"]["object_T_robot_target"] != _identity()
    assert value["transform_artifact"]["max_reconstruction_residual"] < 1e-9
    assert value["transform_artifact"]["contact_center_inside_contact_shell"] is True
    assert value["placement_target"]["target_object_pose"]["position_m"] == [0.0, -0.1, 0.76]
    assert value["placement_artifact"]["semantic_tolerance"]["target_position_m"] == 0.04


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda value: value.update(motion_authorized=True), "motion/frame"),
        (lambda value: value.update(robot_control_steps=1), "motion/frame"),
        (lambda value: value.update(scene_revision="stale"), "observation binding"),
        (lambda value: value["objects"][0].update(world_T_object_target=_identity()), "target derivation"),
    ],
)
def test_scene_facts_fail_closed(mutate, message):
    value = deepcopy(_facts())
    mutate(value)
    with pytest.raises(RouteInputError, match=message):
        validate_scene_facts(value)


def test_route_inputs_reject_unbound_entity_and_tolerance():
    with pytest.raises(RouteInputError, match="absent"):
        derive_bound_route_inputs(
            _facts(),
            entity_ref="entity://missing",
            execution_grasp=_grasp(),
            scene_facts_ref="artifact://route/scene-facts",
            geometry_ref="artifact://route/geometry",
            transform_ref="artifact://route/object-t-robot-target",
            placement_ref="artifact://route/placement",
        )

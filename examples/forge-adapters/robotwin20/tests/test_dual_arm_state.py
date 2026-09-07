import copy

import pytest

from robotwin20_adapter.dual_arm_state import (
    DualArmStateError,
    build_dual_arm_state,
    build_peer_arm_projection,
    build_peer_arm_sphere_projection,
    hold_drift,
    validate_dual_arm_state,
    validate_peer_arm_projection,
    validate_peer_arm_sphere_projection,
)


def _arm(prefix):
    return {
        "qpos": [0.0] * 7,
        "drive_target": [0.0] * 7,
        "gripper": 1.0,
        "links": [
            {"link_id": f"{prefix}:panda_hand", "link_name": "panda_hand", "pose_wxyz": [0, 0, 0, 1, 0, 0, 0]},
        ],
    }


def _state():
    return build_dual_arm_state(
        scene_revision="blocks_ranking_rgb-0-1",
        state_revision="blocks_ranking_rgb-0-1:stabilized",
        frame_id="world",
        left=_arm("left"), right=_arm("right"),
        held_arm_policy="hold",
        provenance_refs=["artifact://scene/dual-arm-state"],
    )


def test_state_has_qualified_links_and_is_provider_only():
    state = _state()
    assert state["left"]["links"][0]["link_id"] == "left:panda_hand"
    assert state["motion_authorized"] is False
    assert validate_dual_arm_state(state) == state


def test_hold_drift_reports_target_change():
    before = _state()
    after = copy.deepcopy(before)
    after["right"]["qpos"][0] = 0.02
    after["right"]["drive_target"][0] = 0.01
    drift = hold_drift(before, after, arm_id="right")
    assert drift["max_qpos_delta_rad"] == 0.02
    assert drift["drive_target_unchanged"] is False


def test_peer_projection_is_bound_to_selected_arm_and_peer_identity():
    projection = build_peer_arm_projection(
        scene_revision="scene", state_revision="state", frame_id="world",
        selected_arm="right",
        links=[{"arm_id": "left", "link_name": "panda_hand", "half_extents_m": [0.1, 0.1, 0.1], "pose_wxyz": [0, 0, 0, 1, 0, 0, 0]}],
        source_ref="artifact://scene/dual-arm-state",
    )
    assert projection["obstacles"][0]["entity_ref"] == "arm://left:panda_hand"
    assert validate_peer_arm_projection(projection) == projection


def test_invalid_peer_and_state_inputs_fail_closed():
    with pytest.raises(DualArmStateError, match="peer projection is empty"):
        build_peer_arm_projection(
            scene_revision="scene", state_revision="state", frame_id="world",
            selected_arm="left", links=[], source_ref="artifact://scene/state",
        )
    invalid = _state()
    invalid["right"]["links"][0]["link_id"] = "left:panda_hand"
    with pytest.raises(DualArmStateError, match="link identity"):
        validate_dual_arm_state(invalid)


def test_curobo_sphere_projection_preserves_native_geometry_and_world_frame():
    projection = build_peer_arm_sphere_projection(
        scene_revision="scene", state_revision="state", frame_id="world",
        selected_arm="right",
        spheres=[
            {"center_m": [0.1, 0.2, 0.3], "radius_m": 0.04},
            {"center_m": [0.4, 0.5, 0.6], "radius_m": 0.02},
        ],
        source_ref="artifact://scene/dual-arm-state",
    )
    assert projection["schema_version"] == "paos-robotwin20-peer-arm-projection/v2"
    assert projection["obstacles"][0]["shape"] == "sphere"
    assert projection["obstacles"][0]["link_id"] == "left:curobo_sphere_0"
    assert validate_peer_arm_sphere_projection(projection) == projection


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"spheres": []}, "empty"),
        ({"frame_id": "left_base"}, "frame must be world"),
        ({"spheres": [{"center_m": [0, 0, 0], "radius_m": float("nan")}]}, "positive"),
    ],
)
def test_curobo_sphere_projection_rejects_unusable_provider_geometry(kwargs, message):
    values = {
        "scene_revision": "scene", "state_revision": "state", "frame_id": "world",
        "selected_arm": "left", "spheres": [{"center_m": [0, 0, 0], "radius_m": 0.02}],
        "source_ref": "artifact://scene/dual-arm-state",
    }
    values.update(kwargs)
    with pytest.raises(DualArmStateError, match=message):
        build_peer_arm_sphere_projection(**values)


def test_curobo_sphere_projection_rejects_state_identity_drift():
    projection = build_peer_arm_sphere_projection(
        scene_revision="scene", state_revision="state", frame_id="world",
        selected_arm="right", spheres=[{"center_m": [0, 0, 0], "radius_m": 0.02}],
        source_ref="artifact://scene/dual-arm-state",
    )
    projection["obstacles"][0]["link_id"] = "right:curobo_sphere_0"
    with pytest.raises(DualArmStateError, match="link identity"):
        validate_peer_arm_sphere_projection(projection)


def test_hold_drift_rejects_scene_revision_drift():
    before = _state()
    after = _state()
    after["scene_revision"] = "scene-new"
    with pytest.raises(DualArmStateError, match="revision or frame"):
        hold_drift(before, after, arm_id="left")

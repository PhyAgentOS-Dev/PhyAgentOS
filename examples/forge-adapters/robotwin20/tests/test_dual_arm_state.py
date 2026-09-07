import copy

import pytest

from robotwin20_adapter.dual_arm_state import (
    DualArmStateError,
    build_dual_arm_state,
    build_peer_arm_projection,
    hold_drift,
    validate_dual_arm_state,
    validate_peer_arm_projection,
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

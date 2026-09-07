import sys
from types import ModuleType, SimpleNamespace

import pytest
from robotwin_curobo_world_port import CuroboWorldPortError, apply_collision_world
from test_route_inputs import _facts

from robotwin20_adapter.collision_world import build_collision_world, collision_world_digest


class FakeWorld:
    def __init__(self, cuboid=None):
        self.cuboid = list(cuboid or [])
        self.objects = self.cuboid

    def clone(self):
        return FakeWorld(list(self.cuboid))


class FakeCuboid:
    def __init__(self, *, name, dims, pose):
        self.name = name
        self.dims = dims
        self.pose = pose


class FakeMotionGen:
    def __init__(self, fail=False, capacity=8):
        self.world_model = FakeWorld([FakeCuboid(name="table", dims=[1, 1, 1], pose=[0] * 7)])
        self.fail = fail
        self.collision_cache = {"obb": capacity}
        self.updates = []

    def update_world(self, world):
        if self.fail:
            raise RuntimeError("provider update failed")
        self.world_model = world
        self.updates.append(world)


class FakePlanner:
    def __init__(self, capacity=8, arm_id=None):
        self.arm_id = arm_id
        self.robot_origion_pose = SimpleNamespace(p=[0, 0, 0], q=[1, 0, 0, 0])
        self.motion_gen = FakeMotionGen(capacity=capacity)
        self.motion_gen_batch = FakeMotionGen(capacity=capacity)

    def _trans_from_world_to_base(self, _, world_pose):
        return world_pose[:3], world_pose[3:]


@pytest.fixture(autouse=True)
def fake_curobo(monkeypatch):
    module = ModuleType("curobo.geom.types")
    module.Cuboid = FakeCuboid
    module.WorldConfig = FakeWorld
    monkeypatch.setitem(sys.modules, "curobo.geom.types", module)


def _artifact():
    facts = _facts()
    return build_collision_world(
        facts,
        target_entity_ref="entity://block-green-1",
        source_scene_facts_ref="artifact://scene/facts",
        geometry_refs={
            item["entity_ref"]: f"artifact://geometry/{item['actor_name']}"
            for item in facts["objects"]
        },
        calibration_ref=facts["calibration_ref"],
    )


def test_port_updates_both_motion_generators_for_both_arms_without_motion():
    planners = {"left": FakePlanner(), "right": FakePlanner()}
    receipt = apply_collision_world(planners, _artifact())
    assert len(receipt["arm_receipts"]) == 2
    assert receipt["motion_authorized"] is False
    for planner in planners.values():
        assert len(planner.motion_gen.updates) == 1
        assert len(planner.motion_gen_batch.updates) == 1
        assert {item.name for item in planner.motion_gen.world_model.objects} == {
            "table", "block-red-1", "block-blue-1",
        }


def test_port_replaces_previous_provider_obstacles_on_world_revision():
    planners = {"left": FakePlanner(), "right": FakePlanner()}
    first = _artifact()
    second = dict(first)
    second["world_revision"] = 2
    second["world_digest"] = collision_world_digest(second)
    apply_collision_world(planners, first)
    receipt = apply_collision_world(planners, second)
    assert receipt["arm_receipts"][0]["operation"] == "update_world"
    for planner in planners.values():
        assert [item.name for item in planner.motion_gen.world_model.objects] == [
            "table", "block-red-1", "block-blue-1"
        ]


def test_port_requires_both_arms_and_rolls_back_partial_update():
    with pytest.raises(CuroboWorldPortError, match="both arm planners"):
        apply_collision_world({"left": FakePlanner()}, _artifact())

    left = FakePlanner()
    right = FakePlanner()
    right.motion_gen.fail = True
    with pytest.raises(CuroboWorldPortError, match="rolled back"):
        apply_collision_world({"left": left, "right": right}, _artifact())
    assert [item.name for item in left.motion_gen.world_model.objects] == ["table"]
    assert [item.name for item in left.motion_gen_batch.world_model.objects] == ["table"]


def test_port_rebuilds_when_provider_cache_is_too_small(monkeypatch):
    rebuilt = []

    def fake_rebuild(planner, world, capacity):
        rebuilt.append((planner, len(world.cuboid), capacity))
        motion_gen = FakeMotionGen(capacity=capacity)
        batch = FakeMotionGen(capacity=capacity)
        motion_gen.world_model = world
        batch.world_model = world
        return motion_gen, batch

    monkeypatch.setattr("robotwin_curobo_world_port._rebuild_motion_generators", fake_rebuild)
    planners = {"left": FakePlanner(capacity=1), "right": FakePlanner(capacity=1)}
    receipt = apply_collision_world(planners, _artifact())
    assert receipt["arm_receipts"][0]["operation"] == "rebuild_motion_gen"
    assert len(rebuilt) == 2
    assert all(item[1:] == (3, 3) for item in rebuilt)
    for planner in planners.values():
        assert len(planner.motion_gen.world_model.objects) == 3
        assert planner.motion_gen.collision_cache["obb"] == 3


def test_rebuild_failure_keeps_original_both_arm_references(monkeypatch):
    planners = {"left": FakePlanner(capacity=1), "right": FakePlanner(capacity=1)}
    original = {
        side: (planner.motion_gen, planner.motion_gen_batch)
        for side, planner in planners.items()
    }
    calls = []

    def fail_on_right(planner, world, capacity):
        calls.append(planner)
        if planner is planners["right"]:
            raise RuntimeError("warmup failed")
        return FakeMotionGen(capacity=capacity), FakeMotionGen(capacity=capacity)

    monkeypatch.setattr("robotwin_curobo_world_port._rebuild_motion_generators", fail_on_right)
    with pytest.raises(CuroboWorldPortError, match="rolled back"):
        apply_collision_world(planners, _artifact())
    assert len(calls) == 2
    for side, planner in planners.items():
        assert (planner.motion_gen, planner.motion_gen_batch) == original[side]


def test_port_projects_peer_arm_geometry_into_each_selected_arm_world():
    planners = {"left": FakePlanner(arm_id="left"), "right": FakePlanner(arm_id="right")}
    peer = {
        arm: {
            "schema_version": "paos-robotwin20-peer-arm-projection/v1",
            "scene_revision": _artifact()["scene_revision"],
            "state_revision": "scene:stabilized",
            "frame_id": "world",
            "selected_arm": arm,
            "obstacles": [{
                "entity_ref": "arm://" + ("right" if arm == "left" else "left") + ":panda_hand",
                "link_id": ("right" if arm == "left" else "left") + ":panda_hand",
                "shape": "cuboid", "half_extents_m": [0.1, 0.1, 0.1],
                "pose_wxyz": [0, 0, 0, 1, 0, 0, 0],
                "provenance_ref": "artifact://scene/state",
            }],
            "source_ref": "artifact://scene/state",
            "motion_authorized": False,
        }
        for arm in ("left", "right")
    }
    receipt = apply_collision_world(planners, _artifact(), peer_projections=peer)
    assert receipt["motion_authorized"] is False
    for planner in planners.values():
        assert len(planner.motion_gen.world_model.objects) == 4
        assert any(item.name.startswith("peer-") for item in planner.motion_gen.world_model.objects)


def test_port_rejects_missing_peer_projection_for_labeled_planner():
    planners = {"left": FakePlanner(arm_id="left"), "right": FakePlanner(arm_id="right")}
    with pytest.raises(CuroboWorldPortError, match="peer arm projection is invalid"):
        apply_collision_world(planners, _artifact(), peer_projections={"left": {}})

import copy

import pytest
from test_route_inputs import _facts

from robotwin20_adapter.collision_world import (
    CollisionWorldError,
    build_collision_world,
    collision_world_digest,
    validate_collision_world,
)


def _refs(facts):
    return {item["entity_ref"]: f"artifact://geometry/{item['actor_name']}" for item in facts["objects"]}


def test_builder_projects_non_target_objects_and_binds_scene():
    facts = _facts()
    value = build_collision_world(
        facts,
        target_entity_ref="entity://block-green-1",
        source_scene_facts_ref="artifact://scene/facts",
        geometry_refs=_refs(facts),
        calibration_ref=facts["calibration_ref"],
    )
    assert value["coverage"] == "complete"
    assert value["target_entity_ref"] == "entity://block-green-1"
    assert value["obstacle_count"] == 2
    assert {item["entity_ref"] for item in value["obstacles"]} == {
        "entity://block-red-1", "entity://block-blue-1",
    }
    assert value["motion_authorized"] is False
    assert validate_collision_world(value) == value


def test_builder_rejects_unknown_coverage_and_missing_geometry():
    facts = _facts()
    with pytest.raises(CollisionWorldError, match="complete scene coverage"):
        build_collision_world(
            {**facts, "coverage": "partial"},
            target_entity_ref="entity://block-green-1",
            source_scene_facts_ref="artifact://scene/facts",
            geometry_refs=_refs(facts),
            calibration_ref=facts["calibration_ref"],
        )
    refs = _refs(facts)
    refs.pop("entity://block-red-1")
    with pytest.raises(CollisionWorldError, match="geometry_refs"):
        build_collision_world(
            facts,
            target_entity_ref="entity://block-green-1",
            source_scene_facts_ref="artifact://scene/facts",
            geometry_refs=refs,
            calibration_ref=facts["calibration_ref"],
        )


def test_validation_rejects_target_in_static_obstacles_and_digest_drift():
    facts = _facts()
    value = build_collision_world(
        facts,
        target_entity_ref="entity://block-green-1",
        source_scene_facts_ref="artifact://scene/facts",
        geometry_refs=_refs(facts),
        calibration_ref=facts["calibration_ref"],
    )
    duplicate = copy.deepcopy(value)
    duplicate["obstacles"][0]["entity_ref"] = duplicate["target_entity_ref"]
    duplicate["world_digest"] = collision_world_digest(duplicate)
    with pytest.raises(CollisionWorldError, match="entity binding"):
        validate_collision_world(duplicate)
    drifted = copy.deepcopy(value)
    drifted["world_revision"] = 2
    with pytest.raises(CollisionWorldError, match="digest"):
        validate_collision_world(drifted)

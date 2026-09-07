#!/usr/bin/env python3
"""Materialize one reviewable v5 route without authorizing simulation motion."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Mapping

import yaml

from robotwin20_adapter.arm_candidates import ArmPlanningError, load_arm_planning_profile
from robotwin20_adapter.controller_qualification import (
    ControllerQualification,
    ControllerQualificationError,
    ControllerQualificationEvidence,
    ControllerQualificationPlan,
    ControllerQualificationValidation,
    validate_controller_qualification_result_package,
)
from robotwin20_adapter.collision_world import build_collision_world
from robotwin20_adapter.grasp_adaptation import (
    GRASP_ADAPTATION_PROFILE_SCHEMA_VERSION,
    adapt_grasp_candidate,
)
from robotwin20_adapter.motion_capabilities import (
    MotionCapabilityDocument,
    MotionCapabilityValidation,
    canonical_motion_capability,
    motion_capability_digest,
)
from robotwin20_adapter.perception_profile import _read_unique_yaml
from robotwin20_adapter.route_generation import generate_route_request
from robotwin20_adapter.route_inputs import (
    ROUTE_INPUT_PROFILE_SCHEMA_VERSION,
    canonical_json,
    derive_bound_route_inputs,
    validate_scene_facts,
)
from robotwin20_adapter.route_readiness import (
    ROUTE_REQUEST_SCHEMA_VERSION,
    route_geometry_digest,
    validate_route_request,
)

_REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


class MaterializationError(RuntimeError):
    pass


def _load_json(path: Path, label: str) -> Mapping[str, Any]:
    if not path.is_absolute() or not path.is_file() or path.is_symlink():
        raise MaterializationError(f"{label} must be an absolute regular file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MaterializationError(f"{label} is invalid JSON") from exc
    if not isinstance(value, Mapping):
        raise MaterializationError(f"{label} must contain an object")
    return value


def _load_controller_qualification(
    args: argparse.Namespace,
) -> tuple[
    ControllerQualification,
    ControllerQualificationPlan,
    ControllerQualificationEvidence,
    ControllerQualificationValidation,
    dict[str, str],
]:
    inputs = {
        "qualification": args.controller_qualification,
        "plan": args.controller_qualification_plan,
        "evidence": args.controller_qualification_evidence,
        "validation": args.controller_qualification_validation,
    }
    values = {name: _load_json(path, name.replace("_", " ")) for name, path in inputs.items()}
    try:
        qualification = ControllerQualification.model_validate(values["qualification"])
        plan = ControllerQualificationPlan.model_validate(values["plan"])
        evidence = ControllerQualificationEvidence.model_validate(values["evidence"])
        validation = ControllerQualificationValidation.model_validate(values["validation"])
    except ValueError as exc:
        raise MaterializationError("controller qualification package is invalid") from exc
    digests = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in inputs.items()}
    try:
        validate_controller_qualification_result_package(
            qualification=qualification,
            plan=plan,
            evidence=evidence,
            validation=validation,
            qualification_file_sha256=digests["qualification"],
            plan_file_sha256=digests["plan"],
            evidence_file_sha256=digests["evidence"],
            validation_file_sha256=digests["validation"],
        )
    except ControllerQualificationError as exc:
        raise MaterializationError("controller qualification package is not approved") from exc
    return qualification, plan, evidence, validation, digests


def _load_profile(path: Path) -> Mapping[str, Any]:
    if not path.is_absolute() or not path.is_file() or path.is_symlink():
        raise MaterializationError("route input profile must be an absolute regular file")
    class _UniqueKeyLoader(yaml.SafeLoader):
        pass

    def construct_mapping(loader, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if key in result:
                raise MaterializationError("route input profile contains duplicate YAML keys")
            result[key] = loader.construct_object(value_node, deep=deep)
        return result

    _UniqueKeyLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping
    )
    try:
        value = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise MaterializationError("route input profile is invalid YAML") from exc
    required = {
        "schema_version", "route_frame_id", "calibration_revision", "workspace_bounds_m",
        "grasp_adaptation", "route_policy", "joint_limit_policy", "stop_policy",
        "semantic_tolerance",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise MaterializationError("route input profile fields are invalid")
    if value["schema_version"] != ROUTE_INPUT_PROFILE_SCHEMA_VERSION or value["route_frame_id"] != "world":
        raise MaterializationError("route input profile schema/frame is unsupported")
    workspace = value["workspace_bounds_m"]
    if not isinstance(workspace, Mapping) or set(workspace) != {
        "frame_id", "x_min_m", "x_max_m", "y_min_m", "y_max_m", "z_min_m", "z_max_m"
    } or workspace["frame_id"] != "world":
        raise MaterializationError("route input workspace is invalid")
    adaptation = value["grasp_adaptation"]
    if not isinstance(adaptation, Mapping) or set(adaptation) != {
        "extrinsic_semantics", "provider_T_contact_center", "support_clear_direction",
        "provider_transform_source",
        "contact_shell_tolerance_m", "robot_target_frame",
        "robot_target_reference_distance_m", "robot_gripper_bias_m",
        "robot_delta_matrix",
    }:
        raise MaterializationError("route input grasp adaptation fields are invalid")
    route_policy = value["route_policy"]
    if not isinstance(route_policy, Mapping) or set(route_policy) != {
        "approach_clearance_m", "lift_clearance_m", "transport_clearance_m",
        "descent_clearance_m", "retreat_distance_m", "retreat_direction",
    }:
        raise MaterializationError("route input route policy fields are invalid")
    joint_policy = value["joint_limit_policy"]
    if not isinstance(joint_policy, Mapping) or set(joint_policy) != {
        "schema_version", "planner_profile", "joint_count", "require_runtime_position_limits",
    }:
        raise MaterializationError("route input joint-limit policy fields are invalid")
    tolerance = value["semantic_tolerance"]
    if not isinstance(tolerance, Mapping) or set(tolerance) != {"target_position_m", "target_orientation_rad"}:
        raise MaterializationError("route input semantic tolerance is invalid")
    return value


def _load_runtime_identity(path: Path) -> Mapping[str, str]:
    """Load the benchmark runtime identity used to cross-bind capability artifacts."""
    if not path.is_absolute() or not path.is_file() or path.is_symlink():
        raise MaterializationError("runtime profile must be an absolute regular file")
    value = _read_unique_yaml(
        path,
        error_type=MaterializationError,
        label="runtime profile",
    )
    expected = {
        "schema_version",
        "task_name",
        "task_config",
        "embodiment",
        "sensor_ref",
        "seed",
        "robot_identity",
        "gripper_identity",
        "embodiment_topology",
        "planner_profile",
    }
    required_identity = {
        "task_name",
        "robot_identity",
        "gripper_identity",
        "embodiment_topology",
        "planner_profile",
    }
    if set(value) != expected or any(
        not isinstance(value[key], str) or not value[key].strip()
        for key in required_identity
    ):
        raise MaterializationError("runtime profile identity fields are invalid")
    embodiment = value["embodiment"]
    if (
        value["schema_version"] != "paos-robotwin20-runtime-profile/v1"
        or not isinstance(embodiment, list)
        or len(embodiment) != 3
        or embodiment[:2] != [value["robot_identity"], value["robot_identity"]]
    ):
        raise MaterializationError("runtime profile embodiment binding is invalid")
    return {key: value[key] for key in required_identity}


def _validate_transform_attestation(
    path: Path, source_root: Path, configured_transform: Any
) -> Mapping[str, Any]:
    value = _load_json(path, "grasp transform attestation")
    required = {
        "schema_version", "provider", "upstream_repository", "upstream_commit",
        "origin_frame", "target_frame", "units", "provider_T_contact_center",
        "source_chain",
        "model_executed", "hardware_io_performed", "motion_authorized",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise MaterializationError("grasp transform attestation fields are invalid")
    if (
        value["schema_version"] != "paos-robotwin20-grasp-transform-attestation/v2"
        or value["provider"] != "graspgen"
        or value["origin_frame"] != "gripper_base_link"
        or value["target_frame"] != "canonical_contact_center"
        or value["units"] != "m"
        or value["provider_T_contact_center"] != configured_transform
        or value["model_executed"] is not False
        or value["hardware_io_performed"] is not False
        or value["motion_authorized"] is not False
    ):
        raise MaterializationError("grasp transform attestation semantics are invalid")
    if not source_root.is_absolute() or not source_root.is_dir() or source_root.is_symlink():
        raise MaterializationError("GraspGen source root must be an absolute checkout")
    try:
        commit = subprocess.run(
            ["git", "-C", str(source_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise MaterializationError("GraspGen source commit is unavailable") from exc
    if commit != value["upstream_commit"]:
        raise MaterializationError("GraspGen source commit does not match attestation")
    chain = value["source_chain"]
    if not isinstance(chain, list) or not chain:
        raise MaterializationError("grasp transform source chain is empty")
    seen: set[str] = set()
    for item in chain:
        if not isinstance(item, Mapping) or set(item) != {"path", "sha256"}:
            raise MaterializationError("grasp transform source chain entry is invalid")
        relative = item["path"]
        if not isinstance(relative, str) or relative.startswith("/") or relative in seen:
            raise MaterializationError("grasp transform source path is invalid")
        seen.add(relative)
        source = (source_root / relative).resolve()
        if source_root.resolve() not in source.parents or not source.is_file() or source.is_symlink():
            raise MaterializationError("grasp transform source file is unavailable")
        if hashlib.sha256(source.read_bytes()).hexdigest() != item["sha256"]:
            raise MaterializationError("grasp transform source digest mismatch")
    return value


def _artifact_path(root: Path, ref: str, suffix: str = ".json") -> Path:
    if not isinstance(ref, str) or not ref.startswith("artifact://"):
        raise MaterializationError("artifact reference is invalid")
    parts = ref.removeprefix("artifact://").split("/")
    if len(parts) < 2 or any(not part or part in {".", ".."} for part in parts):
        raise MaterializationError("artifact reference is invalid")
    path = root.joinpath(*parts)
    if not path.suffix:
        path = path.with_suffix(suffix)
    resolved = path.resolve()
    if root.resolve() not in resolved.parents:
        raise MaterializationError("artifact reference escapes output root")
    return resolved


def _write_bytes(path: Path, payload: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        raise MaterializationError(f"output artifact already exists: {path}")
    with path.open("xb") as stream:
        stream.write(payload)
    path.chmod(0o600)
    return hashlib.sha256(payload).hexdigest()


def _write_json(root: Path, ref: str, value: Mapping[str, Any]) -> str:
    return _write_bytes(_artifact_path(root, ref), canonical_json(value))


def _copy_source_artifact(source_root: Path, output_root: Path, ref: str, suffix: str) -> str:
    source = _artifact_path(source_root, ref, suffix)
    if not source.is_file() or source.is_symlink():
        raise MaterializationError(f"source artifact is unavailable: {ref}")
    target = _artifact_path(output_root, ref, suffix)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        raise MaterializationError(f"output artifact already exists: {ref}")
    with source.open("rb") as reader, target.open("xb") as writer:
        shutil.copyfileobj(reader, writer)
    target.chmod(0o600)
    return hashlib.sha256(target.read_bytes()).hexdigest()


def materialize(args: argparse.Namespace) -> dict[str, Any]:
    if _REQUEST_ID.fullmatch(args.request_id) is None:
        raise MaterializationError("request_id is invalid")
    output_root = args.artifact_root
    if not output_root.is_absolute() or not output_root.is_dir() or output_root.is_symlink():
        raise MaterializationError("artifact_root must be an absolute directory")
    if any(output_root.iterdir()):
        raise MaterializationError("artifact_root must be empty for an immutable run")
    source_root = args.source_capture_root
    if not source_root.is_absolute() or not source_root.is_dir() or source_root.is_symlink():
        raise MaterializationError("source_capture_root must be an absolute directory")
    if (
        not args.runtime_profile.is_absolute()
        or not args.runtime_profile.is_file()
        or args.runtime_profile.is_symlink()
    ):
        raise MaterializationError("runtime_profile must be an absolute regular file")
    if (
        not args.simulation_probe_worker.is_absolute()
        or not args.simulation_probe_worker.is_file()
        or args.simulation_probe_worker.is_symlink()
    ):
        raise MaterializationError("simulation_probe_worker must be an absolute regular file")
    simulation_probe_worker_sha256 = hashlib.sha256(
        args.simulation_probe_worker.read_bytes()
    ).hexdigest()

    facts = validate_scene_facts(_load_json(args.scene_facts, "scene facts"))
    profile = _load_profile(args.route_input_profile)
    runtime_identity = _load_runtime_identity(args.runtime_profile)
    qualification, qualification_plan, _, _, qualification_digests = (
        _load_controller_qualification(args)
    )
    try:
        arm_profile = load_arm_planning_profile(args.arm_planning_profile)
    except ArmPlanningError as exc:
        raise MaterializationError("arm planning profile is invalid") from exc
    if arm_profile["embodiment_id"] != runtime_identity["robot_identity"]:
        raise MaterializationError("arm planning and runtime embodiment identities differ")
    arm_profiles = {item["arm_id"]: item for item in arm_profile["arms"]}
    if set(arm_profiles) != {"left", "right"}:
        raise MaterializationError("arm planning profile must bind left and right arms")
    transform_attestation = _validate_transform_attestation(
        args.grasp_transform_attestation,
        args.graspgen_source_root,
        profile["grasp_adaptation"]["provider_T_contact_center"],
    )
    grasp_bundle = _load_json(args.grasp_results, "grasp results")
    request_binding = grasp_bundle.get("request")
    result = grasp_bundle.get("result")
    if not isinstance(request_binding, Mapping) or not isinstance(result, Mapping):
        raise MaterializationError("grasp results request/result binding is invalid")
    candidates = result.get("candidates")
    if not isinstance(candidates, list):
        raise MaterializationError("grasp results candidates are invalid")
    matches = [item for item in candidates if isinstance(item, Mapping) and item.get("candidate_ref") == args.candidate_ref]
    if len(matches) != 1:
        raise MaterializationError("candidate_ref is absent or ambiguous")
    proposal = dict(matches[0])
    if proposal.get("entity_ref") != args.entity_ref:
        raise MaterializationError("candidate entity binding is invalid")
    for field in ("observation_ref", "scene_revision", "frame_id", "calibration_ref"):
        expected = facts["observation_frame_id"] if field == "frame_id" else facts[field]
        if request_binding.get(field) != expected:
            raise MaterializationError(f"grasp request {field} is not bound to scene facts")

    prefix = f"artifact://route-inputs/{args.request_id}"
    refs = {
        name: f"{prefix}/{name}"
        for name in (
            "scene-facts", "source-manifest", "grasp-adaptation", "candidate-proposal",
            "object-geometry", "object-t-robot-target", "placement-target", "workspace",
            "joint-limits", "stop-policy", "semantic-tolerance", "route-request",
            "provider-transform-attestation", "collision-world",
        )
    }
    qualification_bindings = {
        item.arm_id: item.model_dump(mode="json")
        for item in qualification_plan.capability_bindings
    }
    for arm_id, arm in arm_profiles.items():
        approved_binding = qualification_bindings[arm_id]
        if arm["motion_capabilities_ref"] != approved_binding["artifact_ref"]:
            raise MaterializationError(
                "arm planning capability reference does not match controller qualification"
            )
        refs[f"{arm_id}-motion-capability"] = approved_binding["artifact_ref"]
        refs[f"{arm_id}-motion-capability-validation"] = approved_binding[
            "validation_ref"
        ]
    qualification_ref = (
        f"artifact://controller-qualification/{qualification.qualification_id}/qualification"
    )
    capability_bindings = []
    loaded_capabilities: dict[str, MotionCapabilityDocument] = {}
    capability_payloads: dict[str, tuple[bytes, bytes]] = {}
    for arm_id in ("left", "right"):
        capability_path = getattr(args, f"{arm_id}_motion_capability")
        validation_path = getattr(args, f"{arm_id}_motion_capability_validation")
        capability_value = _load_json(capability_path, f"{arm_id} motion capability")
        validation_value = _load_json(
            validation_path, f"{arm_id} motion capability validation"
        )
        try:
            capability = MotionCapabilityDocument.model_validate(capability_value)
            validation = MotionCapabilityValidation.model_validate(validation_value)
        except ValueError as exc:
            raise MaterializationError(f"{arm_id} motion capability binding is invalid") from exc
        capability_digest = motion_capability_digest(capability)
        if (
            capability.robot_identity != runtime_identity["robot_identity"]
            or capability.arm_id != arm_id
            or capability.provider.planner_id != runtime_identity["planner_profile"]
            or len(capability.joint_order) != profile["joint_limit_policy"]["joint_count"]
            or validation.capability_sha256 != capability_digest
            or validation.status != "validated_planner_constraints"
            or validation.independent_execution_qualification is not False
            or validation.controller_enforced is not False
        ):
            raise MaterializationError(f"{arm_id} motion capability semantics are invalid")
        capability_ref = refs[f"{arm_id}-motion-capability"]
        validation_ref = refs[f"{arm_id}-motion-capability-validation"]
        capability_payload = canonical_motion_capability(capability)
        validation_payload = canonical_json(validation.model_dump(mode="json"))
        capability_file_digest = hashlib.sha256(capability_payload).hexdigest()
        validation_file_digest = hashlib.sha256(validation_payload).hexdigest()
        capability_bindings.append({
            "arm_id": arm_id,
            "artifact_ref": capability_ref,
            "sha256": capability_file_digest,
            "validation_ref": validation_ref,
            "validation_sha256": validation_file_digest,
        })
        loaded_capabilities[arm_id] = capability
        capability_payloads[arm_id] = (capability_payload, validation_payload)
    if qualification_bindings != {
        item["arm_id"]: item for item in capability_bindings
    }:
        raise MaterializationError(
            "route motion capabilities do not match controller qualification"
        )
    qualification_identity = qualification.identity
    for capability in loaded_capabilities.values():
        provider = capability.provider
        if (
            qualification_identity.robot_identity != runtime_identity["robot_identity"]
            or qualification_identity.robot_identity != capability.robot_identity
            or qualification_identity.simulator_id != provider.simulator_id
            or qualification_identity.simulator_version != provider.simulator_version
            or qualification_identity.controller_id != provider.controller_id
            or qualification_identity.controller_version != provider.controller_version
            or qualification_identity.runtime_python_version
            != provider.runtime_python_version
            or qualification_identity.robotwin_git_revision
            != provider.robotwin_git_revision
        ):
            raise MaterializationError("controller qualification runtime identity is invalid")

    facts_digest = _write_json(output_root, refs["scene-facts"], facts)
    calibration_ref = facts["calibration_ref"]
    calibration_digest = _copy_source_artifact(source_root, output_root, calibration_ref, ".json")
    for provenance_ref in proposal.get("provenance", []):
        _copy_source_artifact(source_root, output_root, provenance_ref, ".npy")

    workspace_artifact = {
        "schema_version": "paos-robotwin20-workspace-bounds/v1",
        "scene_revision": facts["scene_revision"],
        **dict(profile["workspace_bounds_m"]),
        "source_profile_sha256": hashlib.sha256(args.route_input_profile.read_bytes()).hexdigest(),
    }
    _write_json(output_root, refs["workspace"], workspace_artifact)
    _write_json(output_root, refs["joint-limits"], profile["joint_limit_policy"])
    _write_json(output_root, refs["stop-policy"], profile["stop_policy"])
    _write_json(output_root, refs["semantic-tolerance"], profile["semantic_tolerance"])
    collision_geometry_refs = {
        item["entity_ref"]: f"{prefix}/collision-geometry-{item['actor_name']}"
        for item in facts["objects"]
    }
    for item in facts["objects"]:
        _write_json(
            output_root,
            collision_geometry_refs[item["entity_ref"]],
            {
                "schema_version": "paos-robotwin20-object-geometry/v1",
                "entity_ref": item["entity_ref"],
                "scene_revision": facts["scene_revision"],
                "frame_id": item["object_frame_id"],
                "shape": "box",
                "half_extents_m": item["half_extents_m"],
                "source_scene_facts_ref": refs["scene-facts"],
                "source": "sapien_collision_shape",
            },
        )
    collision_world = build_collision_world(
        facts,
        target_entity_ref=args.entity_ref,
        source_scene_facts_ref=refs["scene-facts"],
        geometry_refs=collision_geometry_refs,
        calibration_ref=facts["calibration_ref"],
    )
    collision_world_sha256 = _write_json(
        output_root, refs["collision-world"], collision_world
    )
    for arm_id, (capability_payload, validation_payload) in capability_payloads.items():
        _write_bytes(
            _artifact_path(output_root, refs[f"{arm_id}-motion-capability"]),
            capability_payload,
        )
        _write_bytes(
            _artifact_path(output_root, refs[f"{arm_id}-motion-capability-validation"]),
            validation_payload,
        )
    for reference, source, digest in (
        (qualification.plan_ref, args.controller_qualification_plan, qualification_digests["plan"]),
        (qualification.evidence_ref, args.controller_qualification_evidence, qualification_digests["evidence"]),
        (qualification.validation_ref, args.controller_qualification_validation, qualification_digests["validation"]),
        (qualification_ref, args.controller_qualification, qualification_digests["qualification"]),
    ):
        if _write_bytes(_artifact_path(output_root, reference), source.read_bytes()) != digest:
            raise MaterializationError("controller qualification copy digest mismatch")
    qualification_binding = {
        "qualification_id": qualification.qualification_id,
        "artifact_ref": qualification_ref,
        "sha256": qualification_digests["qualification"],
        "plan_ref": qualification.plan_ref,
        "plan_sha256": qualification.plan_sha256,
        "evidence_ref": qualification.evidence_ref,
        "evidence_sha256": qualification.evidence_sha256,
        "validation_ref": qualification.validation_ref,
        "validation_sha256": qualification.validation_sha256,
    }
    transform_attestation_digest = _write_json(
        output_root, refs["provider-transform-attestation"], transform_attestation
    )

    base_request = {
        "schema_version": ROUTE_REQUEST_SCHEMA_VERSION,
        "request_id": args.request_id,
        "observation_ref": facts["observation_ref"],
        "observation_frame_id": facts["observation_frame_id"],
        "scene_revision": facts["scene_revision"],
        "frame_id": facts["route_frame_id"],
        "calibration_ref": calibration_ref,
        "calibration_sha256": calibration_digest,
        "calibration_revision": profile["calibration_revision"],
        "candidate_set_ref": f"candidate-set://{facts['scene_revision']}/{facts['observation_frame_id']}",
        "workspace_bounds_m": {**dict(profile["workspace_bounds_m"]), "provenance_ref": refs["workspace"]},
        "joint_limits_ref": refs["joint-limits"],
        "stop_policy_ref": refs["stop-policy"],
        "motion_capabilities": capability_bindings,
        "controller_qualification": qualification_binding,
        "collision_world": {
            "artifact_ref": refs["collision-world"],
            "sha256": collision_world_sha256,
            "scene_revision": collision_world["scene_revision"],
            "world_revision": collision_world["world_revision"],
            "world_digest": collision_world["world_digest"],
            "coverage": collision_world["coverage"],
            "target_entity_ref": collision_world["target_entity_ref"],
            "obstacle_entity_refs": [
                item["entity_ref"] for item in collision_world["obstacles"]
            ],
        },
        "candidates": [],
    }
    adaptation_config = {
        "schema_version": GRASP_ADAPTATION_PROFILE_SCHEMA_VERSION,
        "extrinsic_semantics": profile["grasp_adaptation"]["extrinsic_semantics"],
        "provider_T_contact_center": profile["grasp_adaptation"][
            "provider_T_contact_center"
        ],
        "robot_target_frame": profile["grasp_adaptation"]["robot_target_frame"],
        "robot_target_reference_distance_m": profile["grasp_adaptation"][
            "robot_target_reference_distance_m"
        ],
        "robot_gripper_bias_m": profile["grasp_adaptation"]["robot_gripper_bias_m"],
        "robot_delta_matrix": profile["grasp_adaptation"]["robot_delta_matrix"],
        "adaptation_provenance_ref": refs["grasp-adaptation"],
        "support_clear_direction": {
            "frame_id": "world",
            "vector": profile["grasp_adaptation"]["support_clear_direction"],
            "provenance_ref": refs["workspace"],
        },
    }
    adaptation_artifact = {
        **adaptation_config,
        "scene_revision": facts["scene_revision"],
        "calibration_ref": calibration_ref,
        "calibration_sha256": calibration_digest,
        "source_profile_sha256": hashlib.sha256(args.route_input_profile.read_bytes()).hexdigest(),
        "provider_transform_source": {
            **dict(profile["grasp_adaptation"]["provider_transform_source"]),
            "attestation_ref": refs["provider-transform-attestation"],
            "attestation_sha256": transform_attestation_digest,
        },
    }
    _write_json(output_root, refs["grasp-adaptation"], adaptation_artifact)
    candidate_artifact = {
        "schema_version": "paos-grasp-proposal-candidate/v1",
        "observation_ref": facts["observation_ref"],
        "scene_revision": facts["scene_revision"],
        "calibration_ref": calibration_ref,
        "candidate": proposal,
        "source_bundle_sha256": hashlib.sha256(args.grasp_results.read_bytes()).hexdigest(),
    }
    _write_json(output_root, refs["candidate-proposal"], candidate_artifact)
    execution_grasp = adapt_grasp_candidate(
        proposal,
        _artifact_path(output_root, calibration_ref).read_bytes(),
        base_request,
        adaptation_config,
    )
    derived = derive_bound_route_inputs(
        facts,
        entity_ref=args.entity_ref,
        execution_grasp=execution_grasp,
        scene_facts_ref=refs["scene-facts"],
        geometry_ref=refs["object-geometry"],
        transform_ref=refs["object-t-robot-target"],
        placement_ref=refs["placement-target"],
        semantic_tolerance=profile["semantic_tolerance"],
        contact_shell_tolerance_m=profile["grasp_adaptation"]["contact_shell_tolerance_m"],
    )
    geometry_digest = _write_json(output_root, refs["object-geometry"], derived["geometry_artifact"])
    transform_digest = _write_json(
        output_root, refs["object-t-robot-target"], derived["transform_artifact"]
    )
    placement_digest = _write_json(output_root, refs["placement-target"], derived["placement_artifact"])

    proposal_binding = {
        "candidate_ref": proposal["candidate_ref"],
        "entity_ref": proposal["entity_ref"],
        "provenance": [*proposal["provenance"], refs["candidate-proposal"]],
        "observation_ref": facts["observation_ref"],
        "observation_frame_id": facts["observation_frame_id"],
        "scene_revision": facts["scene_revision"],
        "calibration_ref": calibration_ref,
        "candidate_set_ref": base_request["candidate_set_ref"],
    }
    policy = {
        key: value for key, value in profile["route_policy"].items() if key != "retreat_direction"
    }
    policy["retreat_direction"] = {
        "frame_id": "world",
        "vector": profile["route_policy"]["retreat_direction"],
        "provenance_ref": refs["workspace"],
    }
    route_request = generate_route_request(
        base_request,
        proposal_binding,
        execution_grasp,
        derived["attached_object"],
        derived["placement_target"],
        policy,
    )
    validate_route_request(route_request)
    route_digest = route_geometry_digest(route_request)
    route_sha256 = _write_json(output_root, refs["route-request"], route_request)
    _write_bytes(output_root / "route_request.json", canonical_json(route_request))
    source_manifest = {
        "schema_version": "paos-robotwin20-route-source-manifest/v4",
        "request_id": args.request_id,
        "scene_revision": facts["scene_revision"],
        "candidate_ref": args.candidate_ref,
        "entity_ref": args.entity_ref,
        "scene_facts": {"artifact_ref": refs["scene-facts"], "sha256": facts_digest},
        "calibration": {"artifact_ref": calibration_ref, "sha256": calibration_digest},
        "grasp_results_sha256": hashlib.sha256(args.grasp_results.read_bytes()).hexdigest(),
        "route_input_profile_sha256": hashlib.sha256(args.route_input_profile.read_bytes()).hexdigest(),
        "runtime_profile_sha256": hashlib.sha256(args.runtime_profile.read_bytes()).hexdigest(),
        "simulation_probe_worker_sha256": simulation_probe_worker_sha256,
        "route_request": {"artifact_ref": refs["route-request"], "sha256": route_sha256},
        "object_geometry": {"artifact_ref": refs["object-geometry"], "sha256": geometry_digest},
        "object_robot_target_transform": {
            "artifact_ref": refs["object-t-robot-target"], "sha256": transform_digest
        },
        "placement_target": {"artifact_ref": refs["placement-target"], "sha256": placement_digest},
        "provider_transform_attestation": {
            "artifact_ref": refs["provider-transform-attestation"],
            "sha256": transform_attestation_digest,
        },
        "motion_capabilities": capability_bindings,
        "controller_qualification": qualification_binding,
        "collision_world": {
            "artifact_ref": refs["collision-world"],
            "sha256": collision_world_sha256,
            "world_digest": collision_world["world_digest"],
        },
        "route_geometry_digest": route_digest,
        "motion_authorized": False,
    }
    manifest_digest = _write_json(output_root, refs["source-manifest"], source_manifest)
    review = {
        "schema_version": "paos-robotwin20-simulation-probe-review-request/v3",
        "decision": "pending_human_review",
        "motion_authorized": False,
        "request_id": args.request_id,
        "candidate_ref": args.candidate_ref,
        "entity_ref": args.entity_ref,
        "scene_revision": facts["scene_revision"],
        "route_geometry_digest": route_digest,
        "route_request_sha256": route_sha256,
        "source_manifest_ref": refs["source-manifest"],
        "source_manifest_sha256": manifest_digest,
        "producer_profile_sha256": hashlib.sha256(args.simulation_probe_profile.read_bytes()).hexdigest(),
        "runtime_profile_sha256": hashlib.sha256(args.runtime_profile.read_bytes()).hexdigest(),
        "simulation_probe_worker_sha256": simulation_probe_worker_sha256,
        "object_robot_target_transform_sha256": transform_digest,
        "placement_target_sha256": placement_digest,
        "calibration_sha256": calibration_digest,
        "joint_limits_sha256": hashlib.sha256(
            _artifact_path(output_root, refs["joint-limits"]).read_bytes()
        ).hexdigest(),
        "stop_policy_sha256": hashlib.sha256(
            _artifact_path(output_root, refs["stop-policy"]).read_bytes()
        ).hexdigest(),
        "controller_qualification_ref": qualification_ref,
        "controller_qualification_sha256": qualification_digests["qualification"],
        "required_decision": "approved_independent_simulation_probe",
        "required_reviewer": "human",
        "simulation_only": True,
    }
    _write_bytes(output_root / "human_review_request.json", canonical_json(review))
    return review


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene-facts", type=Path, required=True)
    parser.add_argument("--source-capture-root", type=Path, required=True)
    parser.add_argument("--grasp-results", type=Path, required=True)
    parser.add_argument("--route-input-profile", type=Path, required=True)
    parser.add_argument("--grasp-transform-attestation", type=Path, required=True)
    parser.add_argument("--graspgen-source-root", type=Path, required=True)
    parser.add_argument("--simulation-probe-profile", type=Path, required=True)
    parser.add_argument("--simulation-probe-worker", type=Path, required=True)
    parser.add_argument("--runtime-profile", type=Path, required=True)
    parser.add_argument("--arm-planning-profile", type=Path, required=True)
    parser.add_argument("--left-motion-capability", type=Path, required=True)
    parser.add_argument("--right-motion-capability", type=Path, required=True)
    parser.add_argument("--left-motion-capability-validation", type=Path, required=True)
    parser.add_argument("--right-motion-capability-validation", type=Path, required=True)
    parser.add_argument("--controller-qualification", type=Path, required=True)
    parser.add_argument("--controller-qualification-plan", type=Path, required=True)
    parser.add_argument("--controller-qualification-evidence", type=Path, required=True)
    parser.add_argument("--controller-qualification-validation", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--candidate-ref", required=True)
    parser.add_argument("--entity-ref", required=True)
    parser.add_argument("--request-id", required=True)
    args = parser.parse_args()
    review = materialize(args)
    print(json.dumps({"status": "awaiting_human_review", "artifact_root": str(args.artifact_root), **review}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

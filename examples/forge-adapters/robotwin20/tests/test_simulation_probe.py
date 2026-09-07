from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import pytest
import robotwin_simulation_probe_worker as probe_worker
import yaml
from robotwin_capability_controller import (
    CapabilityBoundedDriveController,
    ControllerLimits,
)
from robotwin_simulation_probe_worker import (
    APPROVAL_SCHEMA_VERSION,
    SimulationProbeError,
    _artifact_record,
    _execute_segment,
    _guard_controller_source_binding,
    _handle_factory,
    _joint_limits,
    _label_probe_actors,
    _recover_candidate_failure,
    _set_gripper,
    _validate_approval,
    _validate_request_policies,
    _validate_route_input_artifacts,
)
from test_route_readiness import _request as _route_request

from robotwin20_adapter import (
    SIMULATION_PROBE_PROFILE_SCHEMA_VERSION,
    ControllerQualification,
    ControllerQualificationEvidence,
    ControllerQualificationPlan,
    ControllerQualificationValidation,
    MotionCapabilityDocument,
    MotionCapabilityValidation,
    QualificationCapabilityBinding,
    QualificationIdentity,
    QualificationTestEvidence,
    QualificationTestSpec,
    SimulationProbeClient,
    SimulationProbeProfileError,
    build_simulation_probe_client,
    canonical_controller_qualification,
    canonical_motion_capability,
    load_simulation_probe_profile,
    motion_capability_digest,
)

QUALIFICATION_TEST_IDS = (
    "nominal_position_command",
    "nominal_velocity_command",
    "over_limit_velocity_command",
    "contact_load",
    "dropped_step",
    "stop_path",
    "error_path",
    "reset_path",
)


def _profile() -> dict[str, object]:
    return {
        "task_name": "blocks_ranking_rgb",
        "scene_revision": "blocks_ranking_rgb-0-1",
        "runtime_profile_sha256": "b" * 64,
        "embodiment_binding": {
            "robot_identity": "franka-panda",
            "gripper_identity": "panda-gripper",
            "embodiment_topology": "two-single-arm",
            "planner_profile": "curobo",
        },
    }


def _materialize_motion_capabilities(
    root: Path, request: dict[str, object]
) -> dict[str, MotionCapabilityDocument]:
    checks = (
        "source_digests",
        "runtime_identity",
        "joint_order",
        "per_joint_limits",
        "planner_timing",
        "simulator_timing",
        "drive_semantics",
        "no_controller_enforcement_claim",
    )
    source_roles = (
        "robot_description",
        "embodiment_profile",
        "planner_profile",
        "planner_source",
        "simulator_source",
        "controller_source",
    )
    capabilities = {}
    for binding in request["motion_capabilities"]:
        arm_id = binding["arm_id"]
        capability = MotionCapabilityDocument.model_validate(
            {
                "robot_identity": "franka-panda",
                "arm_id": arm_id,
                "provider": {
                    "robotwin_git_revision": "a" * 40,
                    "simulator_version": "3.0.0b1",
                    "planner_version": "0.7.8",
                    "controller_version": "source-0123456789abcdef",
                    "runtime_python_version": "3.10.0",
                },
                "joint_order": [f"panda_joint{index}" for index in range(1, 8)],
                "limits": {
                    "position_lower_rad": [-2.0] * 7,
                    "position_upper_rad": [2.0] * 7,
                    "velocity_lower_radps": [-2.175] * 7,
                    "velocity_upper_radps": [2.175] * 7,
                    "acceleration_radps2": [15.0] * 7,
                    "jerk_radps3": [500.0] * 7,
                    "effort_nm": [12.0] * 7,
                },
                "enforcement": {
                    "joint_position": "planner_constrained",
                    "joint_velocity": "planner_constrained",
                    "joint_acceleration": "planner_constrained",
                    "joint_jerk": "planner_constrained",
                    "cartesian_velocity": "unknown",
                    "joint_effort": "unknown",
                    "drive_position_target": True,
                    "drive_velocity_target": True,
                    "drive_force_limit_bound": False,
                },
                "timing": {
                    "planner_dt_s": 0.004,
                    "simulator_default_dt_s": 0.004,
                    "controller_dt_s": None,
                },
                "sources": [
                    {
                        "role": role,
                        "relative_path": f"provider/{role}",
                        "sha256": f"{index + 5:x}" * 64,
                    }
                    for index, role in enumerate(source_roles)
                ],
            }
        )
        capability_sha256 = motion_capability_digest(capability)
        capability_record = _artifact_record(
            root,
            binding["artifact_ref"],
            canonical_motion_capability(capability),
        )
        validation = MotionCapabilityValidation(
            capability_sha256=capability_sha256,
            verifier_id="paos-source-validator/v1",
            verified_at="2026-09-06T08:00:00+00:00",
            status="validated_planner_constraints",
            checks=checks,
        )
        validation_record = _artifact_record(
            root,
            binding["validation_ref"],
            (
                json.dumps(
                    validation.model_dump(mode="json"),
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            ).encode(),
        )
        binding["sha256"] = capability_record["sha256"]
        binding["validation_sha256"] = validation_record["sha256"]
        capabilities[arm_id] = capability
    return capabilities


def _materialize_controller_qualification(
    root: Path,
    request: dict[str, object],
    capabilities: dict[str, MotionCapabilityDocument],
) -> None:
    provider = capabilities["left"].provider
    identity = QualificationIdentity(
        robot_identity="franka-panda",
        arm_ids=("left", "right"),
        simulator_id=provider.simulator_id,
        simulator_version=provider.simulator_version,
        controller_id=provider.controller_id,
        controller_version=provider.controller_version,
        runtime_python_version=provider.runtime_python_version,
        robotwin_git_revision=provider.robotwin_git_revision,
    )
    binding = request["controller_qualification"]
    capability_bindings = tuple(
        QualificationCapabilityBinding.model_validate(item)
        for item in request["motion_capabilities"]
    )
    tests = tuple(
        QualificationTestSpec(
            test_id=test_id,
            command_family=(
                "position_drive_target"
                if test_id == "nominal_position_command"
                else "velocity_drive_target"
            ),
            arm_ids=("left", "right"),
        )
        for test_id in QUALIFICATION_TEST_IDS
    )
    plan = ControllerQualificationPlan(
        qualification_id=binding["qualification_id"],
        producer_id="qualification-producer/v1",
        created_at="2026-09-06T08:00:00+00:00",
        identity=identity,
        capability_bindings=capability_bindings,
        source_manifest_ref="artifact://qualification/source-manifest",
        source_manifest_sha256="9" * 64,
        command_families=("position_drive_target", "velocity_drive_target"),
        tests=tests,
        required_signals=(
            "commanded_joint_position",
            "commanded_joint_velocity",
            "observed_joint_position",
            "observed_joint_velocity",
            "observed_tcp_pose",
            "derived_tcp_velocity",
            "contacts",
            "controller_status",
            "simulator_step_and_time",
            "stop_error_reset_status",
        ),
    )
    plan_record = _artifact_record(
        root, binding["plan_ref"], canonical_controller_qualification(plan)
    )
    evidence = ControllerQualificationEvidence(
        qualification_id=plan.qualification_id,
        producer_id=plan.producer_id,
        plan_ref=binding["plan_ref"],
        plan_sha256=plan_record["sha256"],
        approval_ref="artifact://qualification/approval",
        approval_sha256="a" * 64,
        identity=identity,
        status="passed",
        tests=tuple(
            QualificationTestEvidence(
                test_id=spec.test_id,
                command_family=spec.command_family,
                outcome="pass",
                evidence_ref=f"artifact://qualification/traces/{spec.test_id}",
                evidence_sha256="b" * 64,
                observed_max_joint_velocity_radps=1.0,
                controller_status="ready",
            )
            for spec in tests
        ),
        world_change_started=True,
        world_change_completed=True,
        reset_completed=True,
        outcome_known=True,
        started_at="2026-09-06T08:01:00+00:00",
        finished_at="2026-09-06T08:02:00+00:00",
    )
    evidence_record = _artifact_record(
        root, binding["evidence_ref"], canonical_controller_qualification(evidence)
    )
    validation = ControllerQualificationValidation(
        qualification_id=plan.qualification_id,
        evidence_ref=binding["evidence_ref"],
        evidence_sha256=evidence_record["sha256"],
        validator_id="independent-validator/v1",
        producer_id=plan.producer_id,
        validated_at="2026-09-06T08:03:00+00:00",
        status="validated_pass",
        checks=("identity", "all_tests", "controller_enforcement", "reset"),
        controller_enforced=True,
    )
    validation_record = _artifact_record(
        root, binding["validation_ref"], canonical_controller_qualification(validation)
    )
    qualification = ControllerQualification(
        qualification_id=plan.qualification_id,
        plan_ref=binding["plan_ref"],
        plan_sha256=plan_record["sha256"],
        evidence_ref=binding["evidence_ref"],
        evidence_sha256=evidence_record["sha256"],
        validation_ref=binding["validation_ref"],
        validation_sha256=validation_record["sha256"],
        identity=identity,
        status="approved_pass",
        reviewer_id="human-reviewer",
        reviewed_at="2026-09-06T08:04:00+00:00",
        independent_execution_qualification=True,
        controller_enforced=True,
    )
    qualification_record = _artifact_record(
        root, binding["artifact_ref"], canonical_controller_qualification(qualification)
    )
    binding.update(
        sha256=qualification_record["sha256"],
        plan_sha256=plan_record["sha256"],
        evidence_sha256=evidence_record["sha256"],
        validation_sha256=validation_record["sha256"],
    )


def _approval(root: Path, request: dict[str, object]) -> str:
    from robotwin20_adapter.route_readiness import route_geometry_digest

    inputs = {
        request["calibration_ref"]: b"{}\n",
        request["joint_limits_ref"]: b'{"policy":"joint-limits"}\n',
        request["stop_policy_ref"]: b'{"policy":"stop"}\n',
    }
    digests = {
        ref: _artifact_record(root, ref, payload)["sha256"]
        for ref, payload in inputs.items()
    }
    transform_ref = request["candidates"][0]["attached_object"]["transform_provenance_ref"]
    placement_ref = request["candidates"][0]["placement_target"]["provenance_ref"]
    transform_digest = _artifact_record(
        root,
        transform_ref,
        b'{"object_T_robot_target":[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]}\n',
    )["sha256"]
    placement_digest = _artifact_record(root, placement_ref, b'{"schema_version":"paos-robotwin20-placement-target/v1"}\n')["sha256"]
    route_digest = route_geometry_digest(request)
    route_sha256 = hashlib.sha256((json.dumps(request, sort_keys=True, separators=(",", ":")) + "\n").encode()).hexdigest()
    manifest = {
        "schema_version": "paos-robotwin20-route-source-manifest/v4",
        "request_id": request["request_id"],
        "candidate_ref": request["candidates"][0]["candidate_ref"],
        "scene_revision": request["scene_revision"],
        "route_geometry_digest": route_digest,
        "route_request": {"sha256": route_sha256},
        "runtime_profile_sha256": "b" * 64,
        "simulation_probe_worker_sha256": hashlib.sha256(
            Path(probe_worker.__file__).read_bytes()
        ).hexdigest(),
        "object_robot_target_transform": {"sha256": transform_digest},
        "placement_target": {"sha256": placement_digest},
        "motion_capabilities": request["motion_capabilities"],
        "controller_qualification": request["controller_qualification"],
        "motion_authorized": False,
    }
    manifest_record = _artifact_record(root, "artifact://probe/source-manifest.json", (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode())
    value = {
        "schema_version": APPROVAL_SCHEMA_VERSION,
        "decision": "approved_independent_simulation_probe",
        "motion_authorized": True,
        "producer_id": "robotwin20-independent-probe/v1",
        "producer_profile_sha256": "a" * 64,
        "task_name": "blocks_ranking_rgb",
        "scene_revision": "blocks_ranking_rgb-0-1",
        "request_id": request["request_id"],
        "candidate_ref": request["candidates"][0]["candidate_ref"],
        "route_geometry_digest": route_geometry_digest(request),
        "calibration_sha256": digests[request["calibration_ref"]],
        "joint_limits_sha256": digests[request["joint_limits_ref"]],
        "stop_policy_sha256": digests[request["stop_policy_ref"]],
        "embodiment_binding": _profile()["embodiment_binding"],
        "reviewer_id": "reviewer-1",
        "reviewed_at": "2026-09-05T00:00:00+00:00",
        "route_request_sha256": route_sha256,
        "source_manifest_ref": manifest_record["artifact_ref"],
        "source_manifest_sha256": manifest_record["sha256"],
        "runtime_profile_sha256": "b" * 64,
        "object_robot_target_transform_sha256": transform_digest,
        "placement_target_sha256": placement_digest,
        "controller_qualification_ref": request["controller_qualification"][
            "artifact_ref"
        ],
        "controller_qualification_sha256": request["controller_qualification"]["sha256"],
        "simulation_probe_worker_sha256": hashlib.sha256(
            Path(probe_worker.__file__).read_bytes()
        ).hexdigest(),
    }
    record = _artifact_record(
        root,
        "artifact://probe/approval.json",
        (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode(),
    )
    return record["artifact_ref"]


def test_approval_record_is_strictly_bound(tmp_path: Path):
    request = _route_request(tmp_path)
    ref = _approval(tmp_path, request)
    result = _validate_approval(
        tmp_path,
        ref,
        producer_id="robotwin20-independent-probe/v1",
        producer_profile_sha256="a" * 64,
        request=request,
        candidate_ref=request["candidates"][0]["candidate_ref"],
        profile=_profile(),
    )
    assert result["motion_authorized"] is True


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda value: value.update(motion_authorized=False), "does not authorize"),
        (lambda value: value.update(producer_id="other"), "producer binding"),
        (lambda value: value.update(scene_revision="other-scene"), "scene binding"),
        (lambda value: value.update(calibration_sha256="0" * 64), "calibration_ref digest"),
        (lambda value: value.update(simulation_probe_worker_sha256="0" * 64), "worker source binding"),
        (lambda value: value.update(reviewed_at="2026-09-05T00:00:00"), "timezone"),
    ],
)
def test_approval_mutation_fails_closed(tmp_path: Path, mutate, message: str):
    request = _route_request(tmp_path)
    ref = _approval(tmp_path, request)
    path = tmp_path / "probe" / "approval.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    mutate(value)
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    with pytest.raises(SimulationProbeError, match=message):
        _validate_approval(
            tmp_path,
            ref,
            producer_id="robotwin20-independent-probe/v1",
            producer_profile_sha256="a" * 64,
            request=request,
            candidate_ref=request["candidates"][0]["candidate_ref"],
            profile=_profile(),
        )


def test_artifact_writer_is_immutable(tmp_path: Path):
    payload = b"immutable\n"
    first = _artifact_record(tmp_path, "artifact://probe/result", payload)
    assert first["sha256"] == hashlib.sha256(payload).hexdigest()
    assert _artifact_record(tmp_path, "artifact://probe/result", payload) == first
    with pytest.raises(SimulationProbeError, match="immutable"):
        _artifact_record(tmp_path, "artifact://probe/result", b"different\n")


def test_route_input_artifacts_are_content_bound(tmp_path: Path):
    request = _route_request(tmp_path)
    candidate = request["candidates"][0]
    geometry = {
        "schema_version": "paos-robotwin20-object-geometry/v1",
        "entity_ref": candidate["entity_ref"],
        "scene_revision": request["scene_revision"],
        "frame_id": candidate["attached_object"]["object_frame_id"],
        "shape": "box",
        "half_extents_m": candidate["attached_object"]["half_extents_m"],
    }
    transform = {
        "schema_version": "paos-robotwin20-object-robot-target-transform/v1",
        "entity_ref": candidate["entity_ref"],
        "scene_revision": request["scene_revision"],
        "object_T_robot_target": candidate["attached_object"]["object_T_robot_target"],
    }
    placement = {
        "schema_version": "paos-robotwin20-placement-target/v1",
        "entity_ref": candidate["entity_ref"],
        "scene_revision": request["scene_revision"],
        "target_ref": candidate["placement_target"]["target_ref"],
        "frame_id": request["frame_id"],
    }
    for ref, value in (
        (candidate["attached_object"]["geometry_ref"], geometry),
        (candidate["attached_object"]["transform_provenance_ref"], transform),
        (candidate["placement_target"]["provenance_ref"], placement),
    ):
        _artifact_record(tmp_path, ref, (json.dumps(value) + "\n").encode())
    result = _validate_route_input_artifacts(tmp_path, request, candidate)
    assert result["placement"] == placement
    transform["object_T_robot_target"] = [0.0] * 16
    (tmp_path / "blocks" / "object-t-robot-target.json").write_text(
        json.dumps(transform), encoding="utf-8"
    )
    with pytest.raises(SimulationProbeError, match="not bound"):
        _validate_route_input_artifacts(tmp_path, request, candidate)


def test_request_policies_accept_approved_controller_qualification(
    tmp_path: Path,
):
    request = _route_request(tmp_path)
    joint_ref = request["joint_limits_ref"]
    stop_ref = request["stop_policy_ref"]
    _artifact_record(
        tmp_path,
        joint_ref,
        (json.dumps({
            "schema_version": "paos-robotwin20-joint-limit-policy/v2",
            "planner_profile": "curobo",
            "joint_count": 7,
            "require_runtime_position_limits": True,
        }, sort_keys=True, separators=(",", ":")) + "\n").encode(),
    )
    _artifact_record(
        tmp_path,
        stop_ref,
        (json.dumps({
            "schema_version": "paos-robotwin20-stop-policy/v1",
            "max_duration_s": 12,
            "stop_file_required": True,
            "poll_each_step": True,
            "failure_recovery": "reset_simulation",
        }, sort_keys=True, separators=(",", ":")) + "\n").encode(),
    )
    capabilities = _materialize_motion_capabilities(tmp_path, request)
    _materialize_controller_qualification(tmp_path, request, capabilities)
    policies = _validate_request_policies(
        tmp_path,
        request,
        max_duration_s=12,
        robot_identity="franka-panda",
    )
    assert policies["controller_qualification"]["qualification_id"] == "qualification-1"


def test_request_policies_reject_tampered_controller_qualification(tmp_path: Path):
    request = _route_request(tmp_path)
    for ref, payload in (
        (
            request["joint_limits_ref"],
            {
                "schema_version": "paos-robotwin20-joint-limit-policy/v2",
                "planner_profile": "curobo",
                "joint_count": 7,
                "require_runtime_position_limits": True,
            },
        ),
        (
            request["stop_policy_ref"],
            {
                "schema_version": "paos-robotwin20-stop-policy/v1",
                "max_duration_s": 12,
                "stop_file_required": True,
                "poll_each_step": True,
                "failure_recovery": "reset_simulation",
            },
        ),
    ):
        _artifact_record(
            tmp_path,
            ref,
            (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode(),
        )
    capabilities = _materialize_motion_capabilities(tmp_path, request)
    _materialize_controller_qualification(tmp_path, request, capabilities)

    with pytest.raises(SimulationProbeError, match="binding is invalid"):
        _validate_request_policies(
            tmp_path,
            request,
            max_duration_s=12,
            robot_identity="other-robot",
        )

    capability_path = tmp_path / "blocks" / "motion-capability-left.json"
    capability_payload = capability_path.read_bytes()
    capability_path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(SimulationProbeError, match="artifact is invalid"):
        _validate_request_policies(
            tmp_path,
            request,
            max_duration_s=12,
            robot_identity="franka-panda",
        )
    capability_path.write_bytes(capability_payload)
    qualification_path = tmp_path / "qualification" / "final.json"
    value = json.loads(qualification_path.read_text(encoding="utf-8"))
    value["reviewer_id"] = "tampered-reviewer"
    qualification_path.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(SimulationProbeError, match="qualification route binding is invalid"):
        _validate_request_policies(
            tmp_path,
            request,
            max_duration_s=12,
            robot_identity="franka-panda",
        )


def test_request_policies_reject_tampered_or_wrong_robot_capability(tmp_path: Path):
    request = _route_request(tmp_path)
    for ref, payload in (
        (
            request["joint_limits_ref"],
            {
                "schema_version": "paos-robotwin20-joint-limit-policy/v2",
                "planner_profile": "curobo",
                "joint_count": 7,
                "require_runtime_position_limits": True,
            },
        ),
        (
            request["stop_policy_ref"],
            {
                "schema_version": "paos-robotwin20-stop-policy/v1",
                "max_duration_s": 12,
                "stop_file_required": True,
                "poll_each_step": True,
                "failure_recovery": "reset_simulation",
            },
        ),
    ):
        _artifact_record(
            tmp_path,
            ref,
            (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode(),
        )


def test_route_controller_requires_the_exact_qualified_provider_source(tmp_path: Path):
    request = _route_request(tmp_path)
    capabilities = _materialize_motion_capabilities(tmp_path, request)

    with pytest.raises(SimulationProbeError, match="qualified bounded provider"):
        _guard_controller_source_binding(capabilities)

    module_digest = hashlib.sha256(Path(probe_worker.__file__).with_name(
        "robotwin_capability_controller.py"
    ).read_bytes()).hexdigest()
    qualified = {}
    for arm_id, capability in capabilities.items():
        value = capability.model_dump(mode="json")
        value["provider"]["controller_id"] = (
            "paos-robotwin-capability-bounded-drive-target"
        )
        value["provider"]["controller_version"] = f"source-{module_digest[:16]}"
        for source in value["sources"]:
            if source["role"] == "controller_source":
                source["sha256"] = module_digest
        qualified[arm_id] = MotionCapabilityDocument.model_validate(value)
    _guard_controller_source_binding(qualified)

    qualified["left"] = MotionCapabilityDocument.model_validate(
        qualified["left"].model_dump(mode="json")
        | {"provider": qualified["left"].provider.model_copy(
            update={"controller_version": "source-0000000000000000"}
        ).model_dump(mode="json")}
    )
    with pytest.raises(SimulationProbeError, match="source digest drifted"):
        _guard_controller_source_binding(qualified)

def test_execute_segment_passes_planner_velocity_through_bounded_controller(tmp_path: Path):
    np = pytest.importorskip("numpy")

    class Robot:
        def __init__(self):
            self.commands = []
            self.ee = np.zeros(3, dtype=np.float64)

        def get_left_ee_pose(self):
            return np.concatenate([self.ee, np.zeros(3)])

        def set_arm_joints(self, position, velocity, arm):
            self.commands.append((np.asarray(position), np.asarray(velocity), arm))

    class Scene:
        def get_timestep(self):
            return 0.004

        def step(self):
            pass

        def get_contacts(self):
            return []

    class Task:
        def __init__(self):
            self.robot = Robot()
            self.scene = Scene()

    task = Task()
    controller = CapabilityBoundedDriveController(
        ControllerLimits(
            joint_order=tuple(f"joint-{index}" for index in range(7)),
            position_lower_rad=(-2.0,) * 7,
            position_upper_rad=(2.0,) * 7,
            velocity_lower_radps=(-1.0,) * 7,
            velocity_upper_radps=(1.0,) * 7,
        ),
        lambda q, dq: task.robot.set_arm_joints(q, dq, "left"),
    )
    execution_state = {
        "planner_object_attached": False,
        "simulator_steps": 0,
        "_controllers": {"left": controller},
        "_artifact_root": tmp_path,
        "_execution_input_digests": {},
        "_controller_source_sha256": hashlib.sha256(
            Path(probe_worker.__file__).with_name("robotwin_capability_controller.py").read_bytes()
        ).hexdigest(),
    }
    _execute_segment(
        task,
        "left",
        {
            "position": np.asarray([[0.0] * 7], dtype=np.float32),
            "velocity": np.asarray([[0.8] * 7], dtype=np.float32),
        },
        phase="approach",
        deadline=time.monotonic() + 1.0,
        stop_file=None,
        contacts=[],
        execution_state=execution_state,
    )
    assert len(task.robot.commands) == 1
    position, velocity, arm = task.robot.commands[0]
    assert arm == "left"
    assert np.allclose(position, 0.0)
    assert np.allclose(velocity, 0.8)
    assert execution_state["simulator_steps"] == 1
    assert controller.counters["settled_steps"] == 1


def test_gripper_step_uses_bounded_arm_hold_and_rejects_invalid_target(tmp_path: Path):
    np = pytest.importorskip("numpy")

    class Entity:
        def get_qpos(self):
            return np.zeros(9, dtype=np.float64)

    class Robot:
        left_entity = Entity()
        right_entity = Entity()

        def __init__(self):
            self.arm_commands = []
            self.gripper_commands = []

        def set_arm_joints(self, position, velocity, arm):
            self.arm_commands.append((list(position), list(velocity), arm))

        def set_gripper(self, value, arm):
            self.gripper_commands.append((value, arm))

    class Scene:
        def step(self):
            pass

        def get_contacts(self):
            return []

    class Task:
        def __init__(self):
            self.robot = Robot()
            self.scene = Scene()

    task = Task()
    controller = CapabilityBoundedDriveController(
        ControllerLimits(
            joint_order=tuple(f"joint-{index}" for index in range(7)),
            position_lower_rad=(-2.0,) * 7,
            position_upper_rad=(2.0,) * 7,
            velocity_lower_radps=(-1.0,) * 7,
            velocity_upper_radps=(1.0,) * 7,
        ),
        lambda q, dq: task.robot.set_arm_joints(q, dq, "left"),
    )
    state = {
        "planner_object_attached": False,
        "simulator_steps": 0,
        "_controllers": {"left": controller},
        "_artifact_root": tmp_path,
        "_execution_input_digests": {},
        "_controller_source_sha256": hashlib.sha256(
            Path(probe_worker.__file__).with_name("robotwin_capability_controller.py").read_bytes()
        ).hexdigest(),
    }
    _set_gripper(
        task,
        "left",
        1.0,
        phase="release",
        deadline=time.monotonic() + 1.0,
        stop_file=None,
        contacts=[],
        execution_state=state,
    )
    assert len(task.robot.arm_commands) == 20
    assert len(task.robot.gripper_commands) == 20
    assert controller.counters["settled_steps"] == 20
    with pytest.raises(SimulationProbeError, match="normalized bounds"):
        _set_gripper(
            task,
            "left",
            1.1,
            phase="release",
            deadline=time.monotonic() + 1.0,
            stop_file=None,
            contacts=[],
            execution_state=state,
        )

def test_post_step_failure_is_snapshotted_and_reset(tmp_path: Path, monkeypatch):
    class Controller:
        def __init__(self):
            self.stopped = False

        def stop(self):
            self.stopped = True

    class MotionGen:
        def __init__(self):
            self.detached = False

        def detach_object_from_robot(self):
            self.detached = True

    class Planner:
        motion_gen = MotionGen()

    class Backend:
        def __init__(self):
            self.reset_count = 0

        def reset(self, *, seed):
            assert seed == 0
            self.reset_count += 1

    backend = Backend()
    request = _route_request(tmp_path)
    candidate = request["candidates"][0]
    before_ref = {"artifact_ref": "artifact://probe/before", "sha256": "a" * 64}
    monkeypatch.setattr(
        probe_worker,
        "_snapshot",
        lambda task, route_request, route_candidate: {
            "scene_revision": route_request["scene_revision"],
            "candidate_ref": route_candidate["candidate_ref"],
            "state_digest": "b" * 64,
        },
    )
    controller = Controller()
    execution_state = {
        "_planner": Planner(),
        "_controllers": {"left": controller},
        "planner_object_attached": True,
        "world_change_started": True,
        "phase": "finalizing",
        "simulator_steps": 9,
        "contact_trace": [],
    }
    response = _recover_candidate_failure(
        backend=backend,
        task=object(),
        runtime_seed=0,
        artifact_root=tmp_path,
        prefix="artifact://probe/request/candidate",
        profile={"worker_id": "probe-test/v1"},
        producer_binding={
            "producer_id": "producer-test/v1",
            "profile_sha256": "c" * 64,
            "evidence_mode": "independent_simulation_probe",
        },
        request=request,
        candidate=candidate,
        before_ref=before_ref,
        execution_state=execution_state,
        error=RuntimeError("final evidence write failed"),
    )
    assert response["status"] == "unavailable"
    assert response["reconciliation_required"] is False
    assert response["failure_evidence"]["artifact_ref"].endswith("/failure")
    assert backend.reset_count == 1
    assert execution_state["planner_object_attached"] is False
    failure = json.loads((tmp_path / "probe/request/candidate/failure.json").read_text())
    assert failure["failed_phase"] == "finalizing"
    assert failure["simulation_reset_status"] == "completed"
    assert failure["controller_stop_status"] == "stopped"
    assert controller.stopped is True
    assert failure["linear_speed_violation"] is None

    no_step_state = {
        "planner_object_attached": False,
        "world_change_started": False,
        "phase": "preflight",
        "simulator_steps": 0,
        "arm_selection_attempts": [
            {"arm": "left", "status": "fail", "detail": "joint-speed limit"}
        ],
    }
    no_step_response = _recover_candidate_failure(
        backend=backend,
        task=object(),
        runtime_seed=0,
        artifact_root=tmp_path,
        prefix="artifact://probe/request/no-step-candidate",
        profile={"worker_id": "probe-test/v1"},
        producer_binding={
            "producer_id": "producer-test/v1",
            "profile_sha256": "c" * 64,
            "evidence_mode": "independent_simulation_probe",
        },
        request=request,
        candidate=candidate,
        before_ref=before_ref,
        execution_state=no_step_state,
        error=SimulationProbeError("no arm can plan candidate route"),
    )
    assert no_step_response["world_change_started"] is False
    assert no_step_response["failure_evidence"]["artifact_ref"].endswith("/failure")
    assert backend.reset_count == 1
    no_step_failure = json.loads(
        (tmp_path / "probe/request/no-step-candidate/failure.json").read_text()
    )
    assert no_step_failure["simulation_reset_status"] == "not_required"
    assert no_step_failure["arm_selection_attempts"][0]["arm"] == "left"


def test_probe_actor_labels_are_unique_and_fail_closed():
    class Actor:
        def __init__(self):
            self.name = "box"

        def set_name(self, name):
            self.name = name

    class Task:
        block1 = Actor()
        block2 = Actor()
        block3 = Actor()

    task = Task()
    _label_probe_actors(task)
    assert [task.block1.name, task.block2.name, task.block3.name] == [
        "block-red-1", "block-green-1", "block-blue-1"
    ]

    class BrokenTask:
        block1 = object()
        block2 = Actor()
        block3 = Actor()

    with pytest.raises(SimulationProbeError, match="identity"):
        _label_probe_actors(BrokenTask())


@pytest.mark.parametrize(
    "values",
    [
        [[float("nan")] * 7, [1.0] * 7],
        [[-1.0, -1.0, -1.0, -1.0, -1.0, -1.0, 2.0], [1.0] * 7],
    ],
)
def test_planner_joint_limits_reject_non_finite_or_inverted_values(values):
    class Tensor:
        def detach(self):
            return self

        def cpu(self):
            return self

        def tolist(self):
            return values

    class Limits:
        position = Tensor()

    class Kinematics:
        joint_limits = Limits()

    class RobotConfig:
        kinematics = Kinematics()

    class MotionGen:
        robot_cfg = RobotConfig()

    class Planner:
        motion_gen = MotionGen()

    with pytest.raises(SimulationProbeError, match="joint limits are invalid"):
        _joint_limits(Planner())


def test_worker_factory_does_not_advance_scene_revision_before_request(
    tmp_path: Path, monkeypatch
):
    import types

    class RuntimeProfile:
        def __init__(self, **values):
            self.values = values

    class Backend:
        def __init__(self, profile):
            self.profile = profile
            self.reset_count = 0
            self._task = None

        def reset(self, *, seed):
            self.reset_count += 1

    module = types.SimpleNamespace(
        RoboTwinRuntimeProfile=RuntimeProfile,
        RoboTwinSensorBackend=Backend,
        load_runtime_profile=lambda path: {
            "task_name": "blocks_ranking_rgb",
            "task_config": "demo_clean",
            "embodiment": ("franka-panda", "franka-panda", 0.8),
            "seed": 0,
        },
    )
    monkeypatch.setitem(sys.modules, "robotwin_backend", module)
    profile = _profile()
    profile.update(
        worker_id="probe-test/v1",
        runtime_root=str(tmp_path),
        runtime_profile=str(tmp_path / "runtime.yaml"),
    )
    backend, _ = _handle_factory(
        profile,
        tmp_path,
        producer_id="producer-test/v1",
        producer_profile_sha256="a" * 64,
        approval_ref="artifact://probe/approval.json",
        max_duration_s=1,
        stop_file=tmp_path / "control" / "stop",
    )
    assert backend.reset_count == 0
    assert backend._task is None


def test_worker_is_single_use_after_an_authorized_attempt(tmp_path: Path, monkeypatch):
    import types

    class RuntimeProfile:
        def __init__(self, **values):
            self.values = values

    class Task:
        robot = object()

    class Backend:
        def __init__(self, profile):
            self.profile = profile
            self.reset_count = 0
            self._task = None

        def reset(self, *, seed):
            assert seed == 0
            self.reset_count += 1
            self._task = Task()

        def snapshot(self):
            return {"scene_revision": "blocks_ranking_rgb-0-1"}

    module = types.SimpleNamespace(
        RoboTwinRuntimeProfile=RuntimeProfile,
        RoboTwinSensorBackend=Backend,
        load_runtime_profile=lambda path: {
            "task_name": "blocks_ranking_rgb",
            "task_config": "demo_clean",
            "embodiment": ("franka-panda", "franka-panda", 0.8),
            "seed": 0,
        },
    )
    monkeypatch.setitem(sys.modules, "robotwin_backend", module)
    monkeypatch.setattr(probe_worker, "_validate_approval", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        probe_worker,
        "_validate_request_policies",
        lambda *args, **kwargs: {
            "joint_limit_policy": {},
            "stop_policy": {},
            "motion_capability_documents": {},
            "execution_input_digests": {},
        },
    )
    monkeypatch.setattr(probe_worker, "_build_route_controllers", lambda *args: {})
    monkeypatch.setattr(probe_worker, "_load_json_artifact", lambda *args: {})
    monkeypatch.setattr(
        probe_worker,
        "_validate_route_input_artifacts",
        lambda *args: {
            "world_T_object_target": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
            "semantic_tolerance": {"target_position_m": 0.04, "target_orientation_rad": 0.35},
        },
    )
    monkeypatch.setattr(probe_worker, "_label_probe_actors", lambda task: None)
    monkeypatch.setattr(
        probe_worker,
        "_snapshot",
        lambda task, request, candidate: {
            "scene_revision": request["scene_revision"],
            "state_digest": "d" * 64,
        },
    )

    def reject_candidate(*args, **kwargs):
        raise SimulationProbeError("planned rejection")

    monkeypatch.setattr(probe_worker, "_run_candidate", reject_candidate)
    request = _route_request(tmp_path)
    geometry = _artifact_record(
        tmp_path,
        request["candidates"][0]["attached_object"]["geometry_ref"],
        b"geometry\n",
    )
    request["candidates"][0]["attached_object"]["geometry_sha256"] = geometry["sha256"]
    profile = _profile()
    profile.update(
        worker_id="probe-test/v1",
        runtime_root=str(tmp_path),
        runtime_profile=str(tmp_path / "runtime.yaml"),
    )
    backend, handle = _handle_factory(
        profile,
        tmp_path,
        producer_id="producer-test/v1",
        producer_profile_sha256="a" * 64,
        approval_ref="artifact://probe/approval.json",
        max_duration_s=1,
        stop_file=tmp_path / "control" / "stop",
    )
    _artifact_record(tmp_path, "artifact://probe/approval.json", b"approval\n")
    (tmp_path / "control").mkdir()
    message = {
        "request_id": request["request_id"],
        "route_request": request,
        "candidate_ref": request["candidates"][0]["candidate_ref"],
        "calibration_ref": request["calibration_ref"],
    }
    first = handle(message)
    assert first["status"] == "unavailable"
    assert first["world_change_started"] is True
    assert backend.reset_count == 2
    second = handle(message)
    assert second["motion_authorized"] is False
    assert second["error_detail"] == "simulation probe worker is single-use"
    assert backend.reset_count == 2


def test_profile_loader_and_builder_bind_every_worker_argument(tmp_path: Path, monkeypatch):
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    runtime_profile = runtime_root / "profile.yaml"
    runtime_profile.write_text("task_name: blocks_ranking_rgb\n", encoding="utf-8")
    stop_file = artifact_root / "control" / "stop"
    stop_file.parent.mkdir()
    profile_path = tmp_path / "simulation-probe.yaml"
    script = Path(__file__).parents[1] / "runtime" / "robotwin_simulation_probe_worker.py"
    profile = {
        "schema_version": SIMULATION_PROBE_PROFILE_SCHEMA_VERSION,
        "worker_id": "probe-test/v1",
        "producer_id": "producer-test/v1",
        "producer_profile_sha256": "${PROBE_PROFILE_SHA256}",
        "runtime_root": str(runtime_root),
        "runtime_profile": str(runtime_profile),
        "artifact_root": str(artifact_root),
        "approval_ref": "artifact://probe/approval.json",
        "max_duration_s": 12,
        "stop_file": str(stop_file),
        "worker": {
            "python": "/usr/bin/python3",
            "script": str(script),
            "cwd": str(script.parent),
            "startup_timeout_s": 2,
            "request_timeout_s": 2,
            "shutdown_timeout_s": 2,
            "environment": {"PYTHONUNBUFFERED": "1"},
            "arguments": [
                "--runtime-root", str(runtime_root), "--runtime-profile", str(runtime_profile),
                "--artifact-root", str(artifact_root), "--worker-id", "probe-test/v1",
                "--producer-id", "producer-test/v1", "--producer-profile-sha256", "${PROBE_PROFILE_SHA256}",
                "--approval-ref", "artifact://probe/approval.json", "--max-duration-s", "12",
                "--stop-file", str(stop_file),
            ],
        },
    }
    profile_path.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")
    monkeypatch.setenv("PROBE_PROFILE_SHA256", hashlib.sha256(profile_path.read_bytes()).hexdigest())
    loaded = load_simulation_probe_profile(profile_path)
    client = build_simulation_probe_client(loaded)
    assert isinstance(client, SimulationProbeClient)
    client.release()


def test_profile_builder_rejects_incomplete_profile(tmp_path: Path):
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(SimulationProbeProfileError, match="fields are invalid"):
        build_simulation_probe_client(load_simulation_probe_profile(profile_path))


def test_profile_loader_rejects_duplicate_yaml_keys(tmp_path: Path):
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(
        "schema_version: paos-robotwin20-simulation-probe-profile/v1\n"
        "schema_version: duplicate\n",
        encoding="utf-8",
    )
    with pytest.raises(SimulationProbeProfileError, match="duplicate"):
        load_simulation_probe_profile(profile_path)


class _ResponseClient:
    def __init__(self, response: dict[str, object]):
        self.response = response

    def request(self, payload):
        return self.response

    def release(self):
        return None


def _client_response(request: dict[str, object], *, started: bool = False) -> dict[str, object]:
    return {
        "request_id": request["request_id"],
        "schema_version": "paos-robotwin20-simulation-probe/v1",
        "status": "unavailable",
        "provider_available": True,
        "worker_id": "probe-test/v1",
        "producer_binding": {
            "producer_id": "producer-test/v1",
            "profile_sha256": "a" * 64,
            "evidence_mode": "independent_simulation_probe",
        },
        "motion_authorized": True,
        "world_change_started": started,
        "world_change_completed": False,
        # A completed simulator reset clears reconciliation even after a
        # world-changing attempt; the worker reports that state explicitly.
        "reconciliation_required": False,
        "failure_evidence": {"artifact_ref": "artifact://probe/failure", "sha256": "b" * 64} if started else None,
    }


def test_client_accepts_bounded_unavailable_stop_before_world_change(tmp_path: Path):
    request = _route_request(tmp_path)
    client = SimulationProbeClient(
        _ResponseClient(_client_response(request)),
        worker_id="probe-test/v1",
        producer_binding={
            "producer_id": "producer-test/v1",
            "profile_sha256": "a" * 64,
            "evidence_mode": "independent_simulation_probe",
        },
    )
    response = client.probe(request, candidate_ref=request["candidates"][0]["candidate_ref"])
    assert response["status"] == "unavailable"
    assert response["world_change_started"] is False


def test_client_accepts_unauthorized_preflight_failure(tmp_path: Path):
    request = _route_request(tmp_path)
    response = _client_response(request)
    response["motion_authorized"] = False
    client = SimulationProbeClient(
        _ResponseClient(response),
        worker_id="probe-test/v1",
        producer_binding={
            "producer_id": "producer-test/v1",
            "profile_sha256": "a" * 64,
            "evidence_mode": "independent_simulation_probe",
        },
    )
    assert client.probe(
        request, candidate_ref=request["candidates"][0]["candidate_ref"]
    )["status"] == "unavailable"


def test_client_rejects_non_boolean_failure_reconciliation(tmp_path: Path):
    request = _route_request(tmp_path)
    response = _client_response(request, started=True)
    response["reconciliation_required"] = "false"
    client = SimulationProbeClient(
        _ResponseClient(response),
        worker_id="probe-test/v1",
        producer_binding={
            "producer_id": "producer-test/v1",
            "profile_sha256": "a" * 64,
            "evidence_mode": "independent_simulation_probe",
        },
    )
    with pytest.raises(SimulationProbeProfileError, match="reconciliation"):
        client.probe(request, candidate_ref=request["candidates"][0]["candidate_ref"])


def test_client_rejects_reconciliation_without_world_change(tmp_path: Path):
    request = _route_request(tmp_path)
    response = _client_response(request, started=False)
    response["reconciliation_required"] = True
    client = SimulationProbeClient(
        _ResponseClient(response),
        worker_id="probe-test/v1",
        producer_binding={
            "producer_id": "producer-test/v1",
            "profile_sha256": "a" * 64,
            "evidence_mode": "independent_simulation_probe",
        },
    )
    with pytest.raises(SimulationProbeProfileError, match="reconciliation"):
        client.probe(request, candidate_ref=request["candidates"][0]["candidate_ref"])


def test_contact_trace_qualifies_duplicate_arm_link_names():
    class Link:
        def __init__(self, name):
            self._name = name

        def get_name(self):
            return self._name

    class Entity:
        def __init__(self):
            self.link = Link("panda_leftfinger")

        def get_links(self):
            return [self.link]

    class Body:
        def __init__(self, entity):
            self.entity = entity

    class Point:
        impulse = [0.0, 0.0, 0.02]

    class Contact:
        def __init__(self, left, right):
            self.bodies = [Body(left), Body(right)]
            self.points = [Point()]

    class Scene:
        def __init__(self, robot):
            self.robot = robot

        def get_contacts(self):
            return [Contact(self.robot.left_entity.link, type("Table", (), {"name": "table"})())]

    class Robot:
        left_entity = Entity()
        right_entity = Entity()

    class Task:
        robot = Robot()
        scene = Scene(robot)

    trace = probe_worker._contact_state(Task(), phase="approach", step=1)
    assert trace[0]["pair"] == ["left:panda_leftfinger", "table"]
    assert trace[0]["active_contact"] is True

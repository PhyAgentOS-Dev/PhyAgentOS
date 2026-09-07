# Changelog

All notable changes to PhyAgentOS are documented here. Categories follow Keep a Changelog.

## [v6.8.11] - 2026-09-07

Replaced the failed SAPIEN single-box peer-arm extraction with a provider-owned Curobo collision-sphere projection. The held peer arm is evaluated at its captured qpos, transformed through the shared world frame, and loaded into each selected-arm planner as conservative enclosing OBBs because the vendored collision checker does not install `WorldConfig.sphere`. Real no-motion validation loaded 61 peer obstacles plus table and two blocks into each planner.

用 provider-owned Curobo collision-sphere 投影替代失败的 SAPIEN 单 box 机械臂投影。未选中臂按捕获的 hold qpos 求碰撞球，经共享 world frame 转换，并因 vendored collision checker 不会装载 `WorldConfig.sphere` 而以保守包围 OBB 加载到每个选中臂 planner。真实 no-motion 验证确认每侧加载 61 个 peer 障碍以及 table 和两个方块。

Files: `dual_arm_state.py:L17,L197-L287`, `robotwin_simulation_probe_worker.py:L240-L289`, `robotwin_curobo_world_port.py:L9-L13,L121-L156,L166-L211`, tests, and `DUAL_ARM_PLANNING_EXECUTION_PLAN.md:L222-L234`.

Validation: focused `51 passed`; full relevant suite `776 passed, 1 skipped`; real Curobo no-motion load `64 active OBB per arm`, Ruff, compileall, and `git diff --check` passed. New route package `/home/yanxu/robotwin20-runtime/artifacts/paos-route-v6.8.11-20260907T2200Z/` remains pending human review with route digest `f66bd11a5d1f941ed9c93facd6476e1eee07163ec1df6a2d377a7c3cbb3379c0`, source-manifest digest `542ea4aac6cfbed491e9f8fdf70eff9a06873c69c7cd9d6632776fdad23d8f7e`, and worker digest `c47601e14f3b632481babdbf8eb22e4c1cd3445aaea46ed9d88bd92a7603df96`. No simulation step, Gateway, Dora, Action, or hardware motion ran in v6.8.11.

## [v6.8.10] - 2026-09-07

Ran the human-approved v6.8.9 simulation-only probe once. It failed closed during scene initialization with `peer arm collision geometry is unavailable`, before any simulator/control step. Evidence showed that SAPIEN Franka links expose mesh/convex geometry while the old provider projection required a single box; candidate, speed, TCP, route geometry, and OBB cache were not implicated.

执行了一次经人工批准的 v6.8.9 simulation-only probe。它在任何 simulator/control step 前，于 scene initialization 因 `peer arm collision geometry is unavailable` fail-closed。证据表明 SAPIEN Franka link 提供 mesh/convex geometry，而旧 provider projection 强制要求单 box；问题与 candidate、速度、TCP、route geometry 或 OBB cache 无关。

Artifacts: `/home/yanxu/robotwin20-runtime/artifacts/paos-route-v6.8.9-20260907T2015Z/probe/result.json` and the bound failure/snapshot records. No Gateway, Dora, Action, or hardware path was used.

## [v6.8.9] - 2026-09-07

Materialized and independently validated a fresh no-motion `blocks_ranking_rgb` sequential dual-arm route package. It binds the latest simulation-probe worker, both-arm MotionCapability documents, controller qualification, and a complete non-target collision world. The package remains pending exact human simulation-only approval; no simulator step, Gateway, Dora, Action, or hardware motion ran.

重新物化并独立校验了新的 no-motion `blocks_ranking_rgb` 顺序双臂 route package。它绑定最新 simulation-probe worker、双臂 MotionCapability、controller qualification 和完整非目标物体碰撞世界。package 仍等待精确人工 simulation-only 审批；未执行 simulator step、Gateway、Dora、Action 或硬件动作。

Artifact root: `/home/yanxu/robotwin20-runtime/artifacts/paos-route-v6.8.9-20260907T2015Z/`; route digest `ba6153412ef675b4a1b7cd750f7ea02316cd10ad989873ccf1ef0c596aa09923`; source-manifest digest `b707f0836d973fb57c3e362e4488d6e93e85bf5d8a3f5c6b8e4c7cb1284815dc`; worker sha256 `7c7b1bfb6ba2c93419c5a34bec7165415e151bfc81aa65c2fba8fa5271de6d5d`.

Validation: route-request and collision-world validators passed; focused dual-arm/collision/qualification/probe suite `49 passed`; `git diff --check` passed.

## [v6.8.8] - 2026-09-07

Documented the cross-benchmark reuse boundary for single-arm Franka providers. PAOS Core, planning, Skill, capability, and lifecycle contracts are reusable; RoboTwin runtime, route readiness, probe, and collision-world code still require explicit single-arm topology branches.

记录跨 benchmark 单臂 Franka provider 的代码复用边界。PAOS Core、planning、Skill、capability 和生命周期协议可复用；RoboTwin runtime、route readiness、probe 与 collision-world 仍需显式单臂 topology 分支。

Files: `docs/forge/DUAL_ARM_PLANNING_EXECUTION_PLAN.md:L420-L458`.

Validation: documentation-only change; `git diff --check` passed and no simulation or motion was run.

## [v6.8.7] - 2026-09-07

Clarified that the current RoboTwin integration supports sequential dual-arm execution only: one arm is driven at a time and the peer arm is held/parked and projected as a static obstacle. Simultaneous synchronized bimanual motion is not implemented.

明确当前 RoboTwin 集成仅支持顺序双臂执行：一次只驱动一只机械臂，另一只机械臂保持/停放并作为静态障碍投影。同时同步双臂运动尚未实现。

Files: `docs/forge/DUAL_ARM_PLANNING_EXECUTION_PLAN.md:L61-L63`.

Validation: documentation-only change; `git diff --check` passed and no simulation or motion was run.

## [v6.8.6] - 2026-09-07

Implemented provider-owned dual-arm planning state, qualified arm/link contact identity, held-arm drift checks, and peer-arm static collision projection for sequential RoboTwin planning. Curobo remains behind the adapter port; synchronized atomic dual-arm execution is still not claimed.

实现 provider-owned 双臂规划状态、qualified arm/link 接触归因、未选中臂漂移检查和顺序 RoboTwin 规划的另一臂静态碰撞投影。Curobo 仍封装在 adapter port 后；本轮不宣称同步原子双臂执行。

Files: `examples/forge-adapters/robotwin20/src/robotwin20_adapter/dual_arm_state.py:L1-L200`, `examples/forge-adapters/robotwin20/runtime/robotwin_curobo_world_port.py:L82-L238`, `examples/forge-adapters/robotwin20/runtime/robotwin_simulation_probe_worker.py:L426-L500,L853-L910,L1692-L1740`.

Validation: RoboTwin adapter `289 passed, 1 skipped`; focused dual-arm/route/probe `40 passed`; Ruff, compileall, and `git diff --check` passed. New simulation motion was not run; prior approval is invalid after worker changes.

## [v6.8.5] - 2026-09-07

Clarified that true dual-arm planning is not the concatenation of two independent Curobo plans. The design now distinguishes static other-arm projection, sequential bimanual execution, and synchronized atomic bimanual execution, with geometry, trajectory, and execution-layer collision checks. The current RoboTwin path remains limited to sequential execution with explicit hold/park semantics.

明确真正的双臂联合规划不是两个独立 Curobo 结果的拼接。设计现在区分另一只机械臂静态投影、顺序双臂执行和同步原子双臂执行，并定义几何层、轨迹层和执行层防碰撞检查。当前 RoboTwin 路径仍限制为带显式 hold/park 语义的顺序执行。

Files: `docs/forge/DUAL_ARM_PLANNING_EXECUTION_PLAN.md:L61-L121`, `changelog/2026-09_part3.md:L3-L20`.

Validation: `git diff --check` passed; no runtime code or simulation motion was changed or executed.

## [v6.8.4] - 2026-09-07

Recorded the PAOS-compatible dual-arm planning protocol and corrected the earlier overclaim that an ambiguous `panda_leftfinger ↔ table` contact proved an unselected-left-arm collision. The document defines reset/stabilization state, qualified contact identity, provider-owned inter-arm projection, route admission, semantic verification, and replanning.

记录 PAOS 兼容的双臂规划协议，并纠正此前将无法区分机械臂的 `panda_leftfinger ↔ table` 接触直接归因于未选中左臂的问题。文档定义 reset/stabilization 状态、qualified contact identity、provider-owned 跨臂投影、路线准入、语义验收和重规划。

Files: `docs/forge/DUAL_ARM_PLANNING_EXECUTION_PLAN.md:L1-L58,L123-L286`, `changelog/2026-09_part3.md:L17-L31`.

Validation: documentation review and `git diff --check` passed; no runtime or motion changes were made.

## [v6.8.3] - 2026-09-07

Materialized the exact human-approved simulation-only probe package and ran one independent RoboTwin20 probe. The provider executed 1174 simulator steps but returned `unavailable` at retreat because the unselected left arm contacted the table; failure evidence, contact trace, and stop/reset records were persisted. This is a real route-safety failure, not a candidate or speed-tuning success, and no Gateway, Dora, Action, or hardware path was used.

物化了与人工批准精确绑定的 simulation-only probe package，并运行一次独立 RoboTwin20 probe。provider 实际执行 1174 个 simulator steps，但在 retreat 阶段因未选中的左臂接触 table 返回 `unavailable`；失败 evidence、接触轨迹和 stop/reset 记录均已保存。这是路线安全失败，不是更换候选或调速成功；未调用 Gateway、Dora、Action 或 hardware。

Artifacts: approval `/home/yanxu/robotwin20-runtime/artifacts/paos-route-v6.8.2-20260907T1515Z/route/probe/approval.json` (sha256 `a1529ddd1286863f2be390a8ccf192931515df7aefcf3a3654a997b0c00e5fdf`); failure `artifact://simulation-probe/franka-blocks-green0-collision-v682-20260907/block-green-1-0/failure`.

Validation: approval materialization passed; probe returned expected exit code 2 with `status=unavailable`; focused route/probe suite `52 passed`. Six-dimension review recorded in `changelog/2026-09_part3.md`; architecture and maintainability remain partial until an explicit park/back-to-origin subtask or equivalent unselected-arm state is admitted.

## [v6.8.2] - 2026-09-07

Materialized and independently validated a fresh route-request/v7 package for the provider collision-world probe. The package binds a complete table+red+blue world, real GraspGen candidate-0, dual-Franka capabilities, and q4 qualification; it remains pending exact human simulation-only approval and no simulation step was run.

为 provider collision-world probe 物化并独立校验了新的 route-request/v7 package。package 绑定完整 table+red+blue 世界、真实 GraspGen candidate-0、双 Franka capability 和 q4 qualification；当前仍等待精确人工 simulation-only 审核，未执行任何仿真 step。

Artifact root: `/home/yanxu/robotwin20-runtime/artifacts/paos-route-v6.8.2-20260907T1515Z/route/`; route digest `ada0e733dbbe2e59145ef00c89bb33f3841bf379ab15dee94cb3ef31551455d1`; source-manifest digest `96f1e24087f76f8ced9cf1ab68c4fba4704f659683274882a5a7e513b85fc308`.

Validation: route and collision-world validators passed; `motion_authorized=false`; no scene.step, benchmark, Gateway, Dora, Action, or hardware ran.

## [v6.8.1] - 2026-09-07

Integrated the provider-owned RoboTwin/Curobo collision world and fixed the concrete OBB cache-capacity failure. The runtime now updates both arms when capacity is available or rebuilds warmed MotionGen instances from the existing RoboTwin profile when it is not; the swap is no-motion and fail-closed. Collision-world capacity is derived from obstacle count rather than a fixed constant.

接入 provider-owned RoboTwin/Curobo 碰撞世界并修复已复现的 OBB cache 容量问题。runtime 在容量足够时更新双臂，容量不足时按现有 RoboTwin profile 重建并 warmup MotionGen，切换过程无动作且 fail-closed；碰撞世界容量由障碍数量推导，不再使用固定常量。

Files: `examples/forge-adapters/robotwin20/src/robotwin20_adapter/collision_world.py`, `examples/forge-adapters/robotwin20/runtime/robotwin_curobo_world_port.py`, `examples/forge-adapters/robotwin20/runtime/robotwin_simulation_probe_worker.py`, route v7 files, and collision-world tests.

Validation: full module suite `759 passed, 1 skipped`; real RoboTwin20/Curobo no-motion probe loaded table+red+blue for dual Franka and rebuilt both arms with capacity 3; Ruff, compileall, and `git diff --check` passed. Six-dimension review passed, including Anti-OverDefense. No Gateway, Dora, Action, hardware, or benchmark motion was run.

## [v6.7.4] - 2026-09-07

Reviewed the diagnosis that observed entities were missing from the RoboTwin/Curobo planning world. Five-dimension review found no blocker after clarifying unknown-space coverage, phase-scoped target exclusion, synchronized dual-MotionGen updates, and Coordinator-owned replanning. Recorded the provider-owned `SceneCollisionWorld` contract and fail-closed gates; no runtime motion or execution surface was changed.

复核已观测实体未进入 RoboTwin/Curobo 规划碰撞世界的诊断。五维审核在补充未知空间覆盖、阶段化目标排除、双 MotionGen 同步更新和 Coordinator 负责重规划后未发现阻塞项。已记录 provider-owned `SceneCollisionWorld` 协议及 fail-closed 门禁；未修改运行时动作或执行面。

Files: `docs/forge/PAOS_STATE_FILE_ARCHITECTURE_DIAGNOSIS.md:L1373-L1431`, `docs/forge/ROBOTWIN_ADAPTER_REFACTOR_DIAGNOSIS.md:L574-L649`, `docs/forge/PLANNING_MODULE_DESIGN.md:L211-L224`.

Validation: `git diff --check` passed; read-only document consistency checks passed. No `scene.step`, benchmark, Gateway, Dora, Action, or hardware was run.

## [v6.7.1] - 2026-09-07

Materialized a fresh immutable RoboTwin/Franka simulation-only route package from the v6.7 sources. The package binds q4 controller qualification, both-arm MotionCapability artifacts, runtime, GraspGen provenance, placement/geometry artifacts, and current worker/controller source digests. No simulation step, benchmark, Gateway, Dora, Action, or hardware motion was executed; the package remains pending fresh human approval.

使用 v6.7 当前源码生成新的不可覆盖 RoboTwin/Franka simulation-only route package，绑定 q4 controller qualification、双臂 MotionCapability、runtime、GraspGen provenance、放置/几何 artifact 及当前 worker/controller source digest。未执行仿真 step、benchmark、Gateway、Dora、Action 或硬件动作；package 仍等待新的人工审批。

Artifacts: `/home/yanxu/robotwin20-runtime/artifacts/paos-route-v6.7.1-20260907T0020Z/`; route digest `5dc2abfb6b23c322f12816c86e1762d36dde5da47dfd17b996e7eb112a6a0808`; source-manifest digest `73aed005d1e07c3a11ba50785ee29cb0bb356217bae6c99b55d087f8abcedd2e`.

Validation: no-motion digest check passed; focused route/approval/probe `64 passed`; full `750 passed, 1 skipped`; `git diff --check` passed. Fresh `I_REVIEWED_AND_APPROVE_SIMULATION_ONLY` is still required before any probe.

## [v6.7.0] - 2026-09-07

Bound the RoboTwin simulation probe to the exact provider controller qualified by the immutable MotionCapability artifacts. Every trajectory step now settles through the bounded controller, controller source/version digests are rechecked before execution, and stale approvals, source drift, input drift, invalid commands, and recovery failures remain fail-closed. This change does not authorize benchmark, Gateway, Dora, Action, or hardware motion.

将 RoboTwin simulation probe 绑定到 MotionCapability artifact 资格化的精确 provider controller。每个轨迹 step 都经过 bounded controller 结算，并在执行前重新校验 controller 源码/版本摘要；旧审批、源码漂移、输入漂移、非法命令和恢复失败均保持 fail-closed。本变更不授权 benchmark、Gateway、Dora、Action 或硬件动作。

Validation: focused `67 passed`; full `750 passed, 1 skipped`; Ruff, compileall, and `git diff --check` passed. Existing route artifacts remain diagnostic-only until fresh materialization and human simulation-only approval.

## [v6.1.0] - 2026-09-06

Implemented the first, no-motion milestone of RoboTwin/SAPIEN controller qualification. The provider-owned adapter now separates a qualification plan, source manifest, human review request, no-motion validation, scoped approval, execution evidence, independent validation, and final qualification. Cross-artifact identity/digest checks and atomic staging publication prevent partial or drifted packages. Qualification approval is scoped only to isolated qualification motion; benchmark, hardware, and PAOS motion remain unauthorized.

实现 RoboTwin/SAPIEN controller qualification 的第一阶段无动作闭环。adapter 现在分离 qualification plan、source manifest、人工审核请求、无动作验证、隔离审批、执行证据、独立验证和最终资格记录；跨 artifact identity/digest 校验与 staging 原子发布防止半包和漂移。qualification approval 仅适用于隔离资格测试，benchmark、硬件和 PAOS 动作仍未授权。

### 文件变更详情 / Detailed changes

- 新增 `examples/forge-adapters/robotwin20/src/robotwin20_adapter/controller_qualification.py`：严格定义五类 qualification contract、测试矩阵、证据范围、双臂 capability binding 和跨 artifact validator。
- Added `examples/forge-adapters/robotwin20/src/robotwin20_adapter/controller_qualification.py`: strict qualification contracts, test matrix, evidence scope, dual-arm capability bindings, and cross-artifact validation.
- 新增 `examples/forge-adapters/robotwin20/scripts/materialize_controller_qualification_plan.py`、`verify_controller_qualification_plan.py`、`validate_controller_qualification.py`、`approve_controller_qualification_plan.py`：生成、独立校验和人工审批隔离 qualification 包；不加载场景、不调用 `scene.step()`。
- Added `materialize_controller_qualification_plan.py`, `verify_controller_qualification_plan.py`, `validate_controller_qualification.py`, and `approve_controller_qualification_plan.py`: materialize, independently verify, validate, and human-approve an isolated qualification package without loading a scene or calling `scene.step()`.
- 新增 `examples/forge-adapters/robotwin20/tests/test_controller_qualification.py`：覆盖 schema、完整测试矩阵、digest/identity drift、权限隔离、错误审批和 CLI 路径。
- Added `examples/forge-adapters/robotwin20/tests/test_controller_qualification.py`: covered schemas, complete test matrix, digest/identity drift, authority isolation, invalid approval, and CLI paths.
- 新增 `docs/forge/ROBOTWIN_CONTROLLER_QUALIFICATION_EXECUTION_PLAN.md`：记录大步门禁、PAOS 所有权、实际 artifact 和五维验收结论。
- Added `docs/forge/ROBOTWIN_CONTROLLER_QUALIFICATION_EXECUTION_PLAN.md`: documented milestone gates, PAOS ownership, real artifacts, and five-dimension acceptance.

### 五维验收 / Five-Dimension Review

- 架构集成：通过；qualification 留在 RoboTwin adapter，不创建第二套 PAOS lifecycle/store/execution plane。
- Architecture integration: pass; qualification remains in the RoboTwin adapter without a second PAOS lifecycle, store, or execution plane.
- 失败路径：通过；缺失/重复矩阵、digest mismatch、identity drift、错误审批短语和不完整绑定均 fail-closed。
- Failure paths: pass; incomplete/duplicate matrices, digest mismatch, identity drift, wrong approval phrase, and incomplete bindings fail closed.
- 权威边界：通过；隔离 qualification motion 与 benchmark/hardware/PAOS motion 明确分离。
- Authority boundaries: pass; isolated qualification motion is explicitly separated from benchmark, hardware, and PAOS motion.
- 配置与 provenance：通过；双臂 capability、validation、manifest、plan 和 review request 交叉绑定，无硬编码速度事实。
- Configuration and provenance: pass; dual-arm capability, validation, manifest, plan, and review request are cross-bound with no hard-coded speed facts.
- 可维护性：通过；contract、materializer、verifier、approval CLI 和测试分层，便于替换 provider。
- Maintainability: pass; contracts, materializer, verifier, approval CLI, and tests are layered for provider replacement.

### 验证 / Validation

- Focused qualification suite: `10 passed`。
- Combined core/Skill/adapter regression: `728 passed, 1 skipped`。
- Ruff、compileall、`git diff --check`：通过。
- Real no-motion package: `/home/yanxu/robotwin20-runtime/artifacts/paos-controller-qualification-plan-20260906T1630Z/`。
- No-motion validation digest: `2d977c2ec9ae179fa7ad9ae37b82367e2ddf84b9d3daded96ea2841f69af497e`。
- 未启动 qualification motion、benchmark、Gateway、Dora、Action 或硬件。
- No qualification motion, benchmark, Gateway, Dora, Action, or hardware was started.

### Git 提交 / Git Commit

- Commit: `17bef6f`
- Branch: `feature/long-horizon-workflow`

## [v6.0.0] - 2026-09-06

Implemented the RoboTwin provider-owned `MotionCapability` v2 artifact and bound both Franka arms into route-request/v5. The artifact is derived from the selected RoboTwin checkout and runtime interpreter, records per-joint URDF limits, CuRobo derivatives, timing, identity, source digests, and explicit enforcement semantics. Independent validation proves source/planner agreement only; it does not create controller qualification or motion authority.

实现 RoboTwin provider-owned `MotionCapability` v2，并将 Franka 左右臂绑定到 route-request/v5。artifact 从选定 RoboTwin checkout 和 runtime interpreter 导出逐关节 URDF 限制、CuRobo 导数限制、时间语义、provider identity、source digest 和执行语义。独立验证只证明来源/planner 一致性，不生成 controller qualification 或动作权威。

### 文件变更详情 / Detailed changes

- 新增 `examples/forge-adapters/robotwin20/src/robotwin20_adapter/motion_capabilities.py`：实现 provider source extraction、canonical digest、runtime identity、joint-order/timing/drive semantics 校验及 no-motion validation record。
- Added `examples/forge-adapters/robotwin20/src/robotwin20_adapter/motion_capabilities.py`: provider-source extraction, canonical digesting, runtime identity, joint-order/timing/drive-semantics validation, and a no-motion validation record.
- 新增 `examples/forge-adapters/robotwin20/scripts/materialize_motion_capability.py`、`verify_motion_capability.py`：提供可复现的两阶段 artifact 物化与独立重验证 CLI。
- Added `examples/forge-adapters/robotwin20/scripts/materialize_motion_capability.py` and `verify_motion_capability.py`: reproducible two-stage materialization and independent revalidation CLIs.
- 修改 `PhyAgentOS/forge/manipulation.py`、`arm_candidates.py`、`manipulation-planning.yaml`：将 arm capability opaque reference 命名为 `motion_capabilities_ref`，不新增 PAOS Core 速度事实源。
- Modified `PhyAgentOS/forge/manipulation.py`, `arm_candidates.py`, and `manipulation-planning.yaml`: renamed the arm capability opaque reference to `motion_capabilities_ref` without adding a PAOS Core speed fact source.
- 修改 `route_readiness.py`、`route_generation.py`、`materialize_complete_route.py`、`robotwin_simulation_probe_worker.py`：route-request/v5 和 source-manifest/v3 绑定左右 capability/validation digest；worker 在 world change 前拒绝缺少独立 controller qualification 的路线。
- Modified `route_readiness.py`, `route_generation.py`, `materialize_complete_route.py`, and `robotwin_simulation_probe_worker.py`: route-request/v5 and source-manifest/v3 bind both capability/validation digests; the worker rejects before world change when independent controller qualification is absent.
- 删除旧的 `controller_capabilities.py` 及其测试，避免形成与 MotionCapability 并行的第二份速度配置/事实源；同步 PAOS 诊断、规划、开发者和 adapter 文档。
- Removed the legacy `controller_capabilities.py` and its tests to avoid a parallel speed configuration/fact source; synchronized PAOS diagnosis, planning, developer, and adapter documentation.

### 五维验收 / Five-Dimension Review

- 架构集成：通过；artifact 属于 RoboTwin adapter，Planning 只消费 opaque reference，Gateway/Action/SQLite 生命周期未改变。
- Architecture integration: pass; the artifact belongs to the RoboTwin adapter, Planning consumes only an opaque reference, and Gateway/Action/SQLite lifecycle is unchanged.
- 失败路径：通过；来源篡改、joint order/timing 歧义、digest 漂移、错误本体和缺少资格均 fail-closed。
- Failure paths: pass; source tampering, joint-order/timing ambiguity, digest drift, wrong embodiment, and missing qualification fail closed.
- 权威边界：通过；当前 SAPIEN 结论是 `planner_constrained`，Cartesian/effort enforcement unknown，validation 和 artifact 都固定 `motion_authorized=false`。
- Authority boundaries: pass; current SAPIEN results are `planner_constrained`, Cartesian/effort enforcement is unknown, and both validation and capability artifacts fix `motion_authorized=false`.
- 配置与 provenance：通过；两臂 artifact/validation digest、RoboTwin git revision、runtime versions 和 source paths 均绑定；旧 approval 不复用。
- Configuration and provenance: pass; both arm artifact/validation digests, RoboTwin git revision, runtime versions, and source paths are bound; old approvals are not reused.
- 可维护性：通过；解析、验证、物化、route gate 分层，未来硬件 controller 只能通过独立 provider qualification 接入。
- Maintainability: pass; extraction, validation, materialization, and route gating are layered, and future hardware controllers require independent provider qualification.

### 验证 / Validation

- Adapter/core/Skill combined regression: `718 passed, 1 skipped`。
- Ruff、compileall、`git diff --check`：通过。
- Real RoboTwin Franka source validation (no scene/no motion): left/right both `validated_planner_constraints`; planner/simulator default timestep `0.004 s`; controller period `null`。
- New route package (no motion): route schema `paos-robotwin20-route-request/v5`, manifest `v3`, route digest `bf52b56e3d258789cb58f7cfc2fa7b7ec382771dedf3665a0762f0aba017ecae`, source manifest digest `5d62573d7d70649020ff6bcb8421b572d6d5a080c42787ff909942a23d45888a`。
- Simulation worker gate: `controller-enforced motion capability qualification is unavailable`; rejected before world change, `motion_authorized=false`。
- 未启动 Gateway、Dora、Action、真实仿真动作或硬件；未生成新的 motion approval。
- No Gateway, Dora, Action, real simulation motion, or hardware was started; no motion approval was generated.

### Git 提交 / Git Commit

- Commit: `992d0de`
- Branch: `feature/long-horizon-workflow`

## [v5.10.3] - 2026-09-06

回写 v5.10.2 速度限制架构变更的 Git 提交信息。Recorded the v5.10.2 real speed-limit architecture commit metadata.

- Commit: `891dfea`
- Branch: `feature/long-horizon-workflow`

## [v5.10.2] - 2026-09-06

撤销 RoboTwin 抓取放置 route 中所有无 provider 来源的硬编码速度行为：route v4、route-input profile v3 和 joint-limit policy v2 不再携带统一 `0.20 m/s`、`1.0 rad/s`、execution scale 或自制 retiming；删除伪 speed-controller 层。当前 simulation probe 在缺少 provider-owned motion capability 时于 world change 前 fail-closed，末端速度只作为诊断 evidence。新增真实速度限制架构文档。

Removed every provider-unbacked hard-coded speed behavior from the RoboTwin pick-place route: route v4, route-input profile v3, and joint-limit policy v2 no longer carry global `0.20 m/s`, `1.0 rad/s`, execution scaling, or custom retiming, and the pseudo speed-controller layer was deleted. The simulation probe now fails closed before world change while provider-owned motion capability is absent; end-effector speed remains diagnostic evidence only. Added the real speed-limit architecture document.

### 文件变更详情 / Detailed changes

- `route_readiness.py:L25-L84`、`route_generation.py:L31-L56,L143-L148`、`grasp_adaptation.py:L201-L208,L309-L333`、`route_inputs.py:L16-L20,L205-L216,L312-L316`：删除 pose 速度字段并升级严格 schema。
- `route-inputs.yaml:L1-L52`、`materialize_complete_route.py:L82-L112,L308-L323,L352-L362`：删除无来源速度配置、scale、controller 伪绑定与 retiming。
- `robotwin_simulation_probe_worker.py:L422-L482,L598-L645,L745-L822`：删除补偿和 threshold gate；缺 provider capability 时 pre-motion fail-closed，保留 finite diagnostic measurement。
- 删除 `runtime/trajectory_controller.py:L1-L179` 与 `tests/test_trajectory_controller.py:L1-L126`。
- 新增 `docs/forge/REAL_SPEED_LIMITS_ARCHITECTURE.md:L1-L301`，同步 planning/developer/adapter 文档与回归测试。

### 五维审查 / Five-Dimension Review

架构集成、失败路径、权威边界、配置/provenance 和可维护性通过；未启动仿真动作、Gateway、Dora、Action 或硬件。Architecture integration, failure paths, authority boundaries, configuration/provenance, and maintainability pass; no simulation motion, Gateway, Dora, Action, or hardware was started.

### 验证 / Validation

`717 passed, 1 skipped`; Ruff、compileall、`git diff --check` passed。

### Git 提交 / Git Commit

- Commit: `891dfea`
- Branch: `feature/long-horizon-workflow`

## [v5.10.0] - 2026-09-06

复用既有 `CapabilitySnapshot/ArmCapability`，为左右臂增加 adapter-owned controller capability artifact 引用，并新增严格的 RoboTwin controller capability 文档模型。RoboTwin Franka 仿真使用 SAPIEN/URDF 与 CuRobo/MPlib，未接入 Franka SDK；当前 `0.20 m/s` 明确为 measured diagnostic threshold，不是 PAOS 或 Franka 全局硬限制。

Reused the existing `CapabilitySnapshot/ArmCapability` contracts with adapter-owned controller-capability artifact references for both arms, and added a strict RoboTwin controller-capability document model. RoboTwin Franka simulation uses SAPIEN/URDF with CuRobo/MPlib and does not use the Franka SDK; the current `0.20 m/s` value is explicitly a measured diagnostic threshold, not a PAOS or Franka global hard limit.

### 文件变更详情 / Detailed changes

- `PhyAgentOS/forge/manipulation.py:L90-L121`：增加可选、严格校验的 `controller_capabilities_ref`。
- `examples/forge-adapters/robotwin20/src/robotwin20_adapter/arm_candidates.py:L98-L167`、`profiles/robotwin20/manipulation-planning.yaml:L6-L25`：绑定每个 arm 的 controller capability artifact。
- `examples/forge-adapters/robotwin20/src/robotwin20_adapter/controller_capabilities.py:L1-L147`：新增来源、执行语义、qualification 和 digest 校验。
- `docs/forge/PLANNING_MODULE_DESIGN.md:L27-L55`、`MANIPULATION_DAG_DEVELOPER_GUIDE.md:L101-L123`、两份诊断/审查文档：记录 RoboTwin/Franka SDK 证据及 PAOS 分层。

### 五维审查 / Five-Dimension Review

架构集成、失败路径、权威边界、配置/provenance 和可维护性通过；未启动 Gateway、Dora、仿真动作或硬件。Architecture integration, failure paths, authority boundaries, configuration/provenance, and maintainability pass; no Gateway, Dora, simulation motion, or hardware was started.

### 验证 / Validation

`734 passed, 1 skipped`; Ruff、compileall、`git diff --check` passed。

## [v5.9.2] - 2026-09-06

为 adapter-local speed controller 增加独立 `ControllerQualification` 资格协议。`hard_bounded` 必须绑定已批准、独立、限速匹配且有 artifact provenance 的资格证据；缺失、待审核、超限或 identity 漂移均 fail-closed。当前 RoboTwin/SAPIEN drive-target backend 仍不具备 hard-limit 资格。

Added an independent `ControllerQualification` contract for the adapter-local speed controller. `hard_bounded` now requires approved, independent, limit-matching qualification evidence with artifact provenance; missing, pending, over-limit, or identity-drifted evidence fails closed. The current RoboTwin/SAPIEN drive-target backend remains unqualified for hard limits.

### 文件变更详情 / Detailed changes

- `examples/forge-adapters/robotwin20/runtime/trajectory_controller.py:L18-L151`：新增 qualification contract 并强制 hard-mode 校验。
- `examples/forge-adapters/robotwin20/tests/test_trajectory_controller.py:L13-L73`：覆盖资格缺失、批准、漂移和 pending review。
- `changelog/2026-09_part3.md`、两份 PAOS 诊断/实现审查文档：记录 qualification 门禁和五维审查。

### 五维审查 / Five-Dimension Review

架构集成、失败路径、权威边界、配置/provenance 和可维护性均通过；当前 backend 仍不可进入 hard-bounded simulation probe。Architecture integration, failure paths, authority boundaries, configuration/provenance, and maintainability pass; the current backend remains ineligible for a hard-bounded simulation probe.

### 验证 / Validation

`40 passed` focused; combined regression `725 passed, 1 skipped`; Ruff、compileall、`git diff --check` passed.

## [v5.9.0] - 2026-09-06

在 RoboTwin adapter 内新增 provider-local `SpeedBoundedExecutionController` seam，明确区分 `hard_bounded` 与 `diagnostic_measured_guard`。当前 SAPIEN drive-target backend 在 world change 前拒绝 hard mode；diagnostic mode 仅记录实测 Cartesian 速度并在超限时 fail-closed。Planning、Skill、Gateway、Experience 未承载仿真器实现。

Added a provider-local `SpeedBoundedExecutionController` seam in the RoboTwin adapter, explicitly distinguishing `hard_bounded` from `diagnostic_measured_guard`. The current SAPIEN drive-target backend rejects hard mode before world change; diagnostic mode only records measured Cartesian speed and fails closed on violations. Planning, Skill, Gateway, and Experience carry no simulator implementation.

### 文件变更详情 / Detailed changes

- `examples/forge-adapters/robotwin20/runtime/trajectory_controller.py:L1-L125`：controller capability、模式、预检、policy binding 和 violation contract。
- `examples/forge-adapters/robotwin20/runtime/robotwin_simulation_probe_worker.py:L29-L39,L546-L635,L782-L824,L1018-L1032`：接入 measured-speed controller seam 并记录 controller provenance。
- `examples/forge-adapters/robotwin20/tests/test_trajectory_controller.py:L1-L87`、`test_simulation_probe.py:L389-L417`：覆盖 hard-mode 拒绝、速度、输入、policy 漂移和 evidence 失败路径。
- `examples/forge-adapters/robotwin20/profiles/robotwin20/route-inputs.yaml:L47-L57`、`scripts/materialize_complete_route.py:L105-L118`：绑定 execution controller profile。
- `docs/forge/PAOS_STATE_FILE_ARCHITECTURE_DIAGNOSIS.md:L1176-L1192`、`docs/forge/STATE_FILE_IMPLEMENTATION_REVIEW_20260903.md:L1173-L1189`：记录五维审查与 qualification gate。

### 五维审查 / Five-Dimension Review

架构集成、失败路径、权威边界、配置和可维护性均通过；当前后端仍不具备 hard Cartesian 限速资格，不得进入新的完整 route probe。Architecture integration, failure paths, authority boundaries, configuration, and maintainability pass; the current backend remains unqualified for hard Cartesian limiting, so no new complete-route probe is authorized.

### 验证 / Validation

`38 passed` focused; combined regression `723 passed, 1 skipped`; Ruff、compileall、`git diff --check` passed.

## [v5.8.0] - 2026-09-06

根据 v7-v10 仿真证据撤回不能证明 Cartesian 速度受控的 position-subdivision 执行调参；`execution_velocity_scale` 恢复为 `0.25` advisory 值，measured-speed `0.20 m/s` fail-closed 门禁和 uniform retiming 保持不变。同步 profile、materializer、simulation worker 与回归测试；保留历史负证据，未生成新 route 或启动新的 probe/Gateway/Dora/Action/硬件。

Based on v7-v10 simulation evidence, removed position-subdivision execution tuning that cannot prove bounded Cartesian speed; restored `execution_velocity_scale` to the `0.25` advisory value while retaining the measured-speed `0.20 m/s` fail-closed gate and uniform retiming. Synchronized the profile, materializer, simulation worker, and regression tests; historical negative evidence is preserved, with no new route or probe/Gateway/Dora/Action/hardware started.

### 文件变更详情 / Detailed changes

- `examples/forge-adapters/robotwin20/profiles/robotwin20/route-inputs.yaml:L47-L49`：移除 subdivision，恢复 scale `0.25` 并标记 advisory。
- `examples/forge-adapters/robotwin20/runtime/robotwin_simulation_probe_worker.py:L546-L633,L750-L811,L939-L950`：删除 subdivision 校验/插值/乘法预算，恢复单一 planner sample 执行。
- `examples/forge-adapters/robotwin20/scripts/materialize_complete_route.py:L105-L112`、`examples/forge-adapters/robotwin20/tests/test_simulation_probe.py:L220-L469`：同步 schema 与测试，移除无证据调参分支。
- `docs/forge/PAOS_STATE_FILE_ARCHITECTURE_DIAGNOSIS.md:L1157-L1173`、`docs/forge/STATE_FILE_IMPLEMENTATION_REVIEW_20260903.md:L1158-L1174`：记录根因、回滚范围和后续门禁。

### 五维审查 / Five-Dimension Review

架构集成、失败路径、权威边界、配置和可维护性均通过；该回滚不授予任何生产动作权限。Architecture integration, failure paths, authority boundaries, configuration, and maintainability pass; the rollback grants no production motion authority.

### 验证 / Validation

`31 passed`; combined regression `716 passed, 1 skipped`; Ruff、compileall、`git diff --check` passed.

## [v5.7.10] - 2026-09-06

回写 v5.7.9 simulation probe evidence 修复提交哈希 `f4222d1`；实现与安全边界不变。

Recorded commit hash `f4222d1` for the v5.7.9 simulation-probe evidence fix; implementation and safety boundaries are unchanged.

### Git 提交 / Git Commit

- Commit: `f4222d1`
- Branch: `feature/long-horizon-workflow`

## [v5.7.9] - 2026-09-06

修正 independent simulation probe 的已执行步数 evidence 低报：`scene.step()` 后立即计入 `simulator_steps`，并新增命令级 execution velocity scale、线速度违规和 failure artifact 回归。全量组合回归 `716 passed, 1 skipped`；Ruff、compileall、`git diff --check` 通过。v7 route 仍等待新的 simulation-only approval，未启动 probe、Gateway、Dora、Action 或硬件。

Corrected under-counted executed-step evidence in the independent simulation probe by incrementing `simulator_steps` immediately after `scene.step()`, and added command-level execution-velocity-scale, linear-speed-violation, and failure-artifact regressions. Full combined regression: `716 passed, 1 skipped`; Ruff, compileall, and `git diff --check` pass. The v7 route still awaits fresh simulation-only approval; no probe, Gateway, Dora, Action, or hardware was started.

### 文件变更详情 / Detailed changes

- `examples/forge-adapters/robotwin20/runtime/robotwin_simulation_probe_worker.py:L779-L799`：修正 failure step 计数，保持 `0.20 m/s` gate 不变。
- `examples/forge-adapters/robotwin20/tests/test_simulation_probe.py:L263-L297,L357-L468,L470-L535`：覆盖非法 scale、命令缩放、违规字段和 artifact 持久化。
- `docs/forge/PAOS_STATE_FILE_ARCHITECTURE_DIAGNOSIS.md:L1047-L1051`、`docs/forge/STATE_FILE_IMPLEMENTATION_REVIEW_20260903.md:L1063-L1066`：记录证据计数边界。

### 五维验收 / Five-Dimension Review

架构集成、失败路径、权威边界、配置和可维护性均通过；该修复仅限 adapter-owned simulation probe evidence，不授予生产动作权威。

Architecture integration, failure paths, authority boundaries, configuration, and maintainability pass; the fix is limited to adapter-owned simulation-probe evidence and grants no production motion authority.

### Git 提交 / Git Commit

- Commit: `f4222d1`
- Branch: `feature/long-horizon-workflow`

## [v5.7.7] - 2026-09-05

回写 v5.7.6 simulation-only probe 记录的提交哈希 `d5aa0de`；无实现、证据或安全边界变化。

Recorded commit hash `d5aa0de` for the v5.7.6 simulation-only probe; no implementation, evidence, or safety-boundary changes.

### Git 提交 / Git Commit

- Commit: pending
- Branch: `feature/long-horizon-workflow`

## [v5.7.6] - 2026-09-05

针对 reviewer `yanxu` 批准的 v3 route package，完成一次独立 simulation-only probe。审批与 route/source-manifest digest 严格绑定；RoboTwin20 Python 3.10 worker 在 contact 阶段因超过 profile 的 `0.2 m/s` simulator waypoint linear-speed limit 返回 `unavailable`，保存 before/after snapshot、contact trace、failure artifact 和 reset 状态。该负结果未被解释为 readiness 或任务成功，Gateway/Dora/Action/硬件仍未启用。

Ran one independent simulation-only probe for reviewer-approved v3 route package with strict route/source-manifest digest binding. The RoboTwin20 Python 3.10 worker returned `unavailable` in the contact phase because the trajectory exceeded the profile `0.2 m/s` simulator waypoint linear-speed limit, preserving before/after snapshots, contact trace, failure artifact, and reset status. The negative result is not readiness or task success; Gateway, Dora, Action, and hardware remain disabled.

### 文件变更详情 / Detailed changes

- `docs/forge/PAOS_STATE_FILE_ARCHITECTURE_DIAGNOSIS.md:L980-L1026`：修正规划模块历史状态并记录 v3 probe 的审批、失败证据和下一门禁。
- `docs/forge/STATE_FILE_IMPLEMENTATION_REVIEW_20260903.md:L984-L1045`：新增 simulation-only probe 的审批边界、负结果和五维审查。
- `/home/yanxu/robotwin20-sim-probe-20260905T230500Z/`：保存审批、probe response、before/after snapshot、contact trace 和 failure artifact。

### 五维验收 / Five-Dimension Review

探针边界的架构集成、失败路径、权威边界、配置/provenance 和可维护性均通过；但完整路线、attached-object collision、真实 lift、接触动力学和语义放置仍未证明，必须生成新 route 并重新审批。

Architecture integration, failure paths, authority boundaries, configuration/provenance, and maintainability pass for the probe boundary. Complete route, attached-object collision, physical lift, contact dynamics, and semantic placement remain unproven; a new route and approval are required.

### Git 提交 / Git Commit

- Commit: pending
- Branch: `feature/long-horizon-workflow`

## [v5.7.3] - 2026-09-05

修正规划模块历史验收章节的状态漂移，并新增 no-motion 全链路接入验收：PlanGraph 持久化、AgentLoop dispatch、动态 Tool admission、失败结算、重规划以及 Experience replay/审核/promotion 均得到验证。组合回归 `709 passed, 1 skipped`；未调用 Gateway、Dora 或硬件。

Corrected stale planning-module historical status and added a no-motion end-to-end integration acceptance covering PlanGraph persistence, AgentLoop dispatch, dynamic Tool admission, failed settlement, replanning, and Experience replay/review/promotion. Combined regression: `709 passed, 1 skipped`; no Gateway, Dora, or hardware was called.

### 文件变更详情 / Detailed changes

- `docs/forge/STATE_FILE_IMPLEMENTATION_REVIEW_20260903.md:L958-L986`：将历史 32.5 节的过时待办改为已完成状态，保留真实 readiness/simulation evidence 为当前门禁。
- `docs/forge/PAOS_STATE_FILE_ARCHITECTURE_DIAGNOSIS.md:L966-L968`：增加历史状态说明和当前下一步边界。
- `tests/test_planning_end_to_end.py:L1-L246`：新增 no-motion 规划集成验收，覆盖 Coordinator、dispatch、admission、settlement、replan 和 Experience promotion。

### 五维验收 / Five-Dimension Review

架构集成、失败路径、权威边界、配置 provenance、可维护性均通过；测试使用独立 no-motion 夹具，不构成真实运动或 readiness 证据。

Architecture integration, failure paths, authority boundaries, configuration/provenance, and maintainability all pass; the test uses an isolated no-motion fixture and is not evidence of real motion or readiness.

### Git 提交 / Git Commit

- Commit: `f244751`
- Branch: `feature/long-horizon-workflow`

## [v5.7.1] - 2026-09-05

规划模块最终收口审查通过：未发现 Blocker/Major；全量组合回归 `708 passed, 1 skipped`，核心/Skill/adapter 回归 `205 passed`，Ruff、compileall、`git diff --check` 通过。真实 Gateway/Dora/Action、仿真运动和 benchmark evidence 仍按 PAOS 门禁后置。

The final planning-module closeout review passed with no Blocker/Major findings. Full combined regression: `708 passed, 1 skipped`; core/Skill/adapter regression: `205 passed`; Ruff, compileall, and `git diff --check` passed. Real Gateway/Dora/Action, simulation motion, and benchmark evidence remain deferred behind PAOS gates.

### Git 提交 / Git Commit

- Commit: `aadc833`
- Branch: `feature/long-horizon-workflow`

## [v5.7.0] - 2026-09-05

规划模块已完成 AgentLoop 的只读 `agent_composed` dispatch bridge 与 Experience 的 review-gated workflow-policy candidate ledger。`forge_plan_activate` 只接受可信 `AdmissionContext` provider，`forge_plan_ready` 暴露 ready semantic nodes；Registry guard 在现有 Forge Query/Action/Session wrapper 前执行 fail-closed admission。候选按 base/proposed policy digest 聚合，必须有独立 replay receipt、不同 episode 支持和人工审核，promotion 还必须由 Skill Runtime callback 返回 `artifact://` receipt。组合回归 `707 passed, 1 skipped`，未启动 Gateway、Dora、Action、仿真动作或硬件。

The planning module now has a read-only `agent_composed` dispatch bridge in AgentLoop and a review-gated workflow-policy candidate ledger in Experience. `forge_plan_activate` accepts only a trusted `AdmissionContext` provider and `forge_plan_ready` exposes ready semantic nodes; the registry guard performs fail-closed admission before existing Forge Query/Action/Session wrappers. Candidates aggregate by base/proposed policy digests and require independent replay receipts, distinct episode support, and human review; promotion additionally requires a Skill Runtime callback returning an `artifact://` receipt. Combined regression: `707 passed, 1 skipped`; no Gateway, Dora, Action, simulation motion, or hardware was started.

### 文件变更详情 / Detailed changes

- `PhyAgentOS/agent/planning_dispatch.py:L1-L244`、`PhyAgentOS/agent/tools/planning.py:L1-L112`：新增只读 AgentLoop dispatch 与可信上下文激活工具。
- `PhyAgentOS/agent/loop.py:L145-L208,L260-L314`、`PhyAgentOS/agent/tools/registry.py:L17-L79`：接入可选 admission guard，不接管 Tool 执行。
- `PhyAgentOS/planning/contracts.py:L327-L383`、`PhyAgentOS/agent/experience/{policy_candidates.py,store.py,coordinator.py}`：新增候选/replay 协议、SQLite ledger、审核与 callback-gated promotion。
- `tests/test_planning_dispatch.py:L1-L170`、`tests/test_workflow_policy_candidates.py:L1-L75`：覆盖 dispatch 和演化门禁。

### Git 提交 / Git Commit

- Commit: `aadc833`
- Branch: `feature/long-horizon-workflow`

## [v5.6.0] - 2026-09-05

规划模块已接入 PAOS 任务生命周期边界：`AgentTaskCoordinator` 接收并持久化具体 `PlanGraph` 的 artifact/ref 与 digest；Query、Action、Session 可携带完整规划归因；`ReplanDelta` 通过 coordinator 生成新 revision；DecisionTrace 以脱敏引用进入 Experience outcome。planning 专项 15 passed，组合 core/Skill 回归 457 passed，RoboTwin adapter 233 passed, 1 skipped。未启动 Gateway、Dora、Action、仿真动作或硬件。

The planning module is now connected to PAOS lifecycle boundaries: `AgentTaskCoordinator` accepts and persists concrete `PlanGraph` artifact/ref and digests; Query, Action, and Session calls can carry complete planning attribution; `ReplanDelta` is adapted into a new revision through the coordinator; DecisionTrace enters the Experience outcome as a redacted reference. Focused planning suite: 15 passed; combined core/Skill regression: 457 passed; RoboTwin adapter: 233 passed, 1 skipped. No Gateway, Dora, Action, simulation motion, or hardware was started.

Remaining by design: real Gateway/Dora/Action motion and benchmark evidence; these are outside the pure planning/Experience integration and remain separately gated.

### Git 提交 / Git Commit

- Commit: `619c1b2`
- Branch: `feature/long-horizon-workflow`

## [v5.5.5] - 2026-09-05

抓取放置 Skill 增加 `baseline` / `agent_composed` 双模式。旧 `LongHorizonWorkflow` 保留为确定性 replay projection；新 bridge 接收 Agent 语义子任务，编译为带 `verify` join 的 PAOS PlanGraph，并按 capability 暴露多个 Tool 候选，通过 planning admission 校验证据、scene、资源和 ToolSpec digest。未执行 Tool、未写 SQLite、未创建 revision、未授权动作。Skill 回归 `270 passed`。

The pick-place Skill now exposes `baseline` / `agent_composed` modes. The existing `LongHorizonWorkflow` remains the deterministic replay projection; the new bridge accepts Agent semantic subtasks, compiles a PAOS PlanGraph with a `verify` join, exposes multiple Tool candidates by capability, and delegates evidence, scene, resource, and ToolSpec-digest checks to planning admission. It executes no Tool, writes no SQLite, creates no revision, and grants no motion authority. Skill regression: `270 passed`.

### 文件变更详情 / Detailed changes

- `examples/forge-skills/pick-place-workflow/src/pick_place_workflow/agent_planning.py:L1-L216`：新增语义子任务编译、双模式切换、动态 Tool 候选与 admission bridge。
- `examples/forge-skills/pick-place-workflow/tests/test_agent_planning.py:L1-L126`：覆盖多实体并行 DAG、verify join、失败路径、Tool 替代和 mode switch。
- `examples/forge-skills/pick-place-workflow/README.md:L43-L89`、`SKILL.md:L128-L143`、`docs/forge/PLANNING_MODULE_DESIGN.md:L104-L124`：同步动态规划和演化边界。

### 五维审查 / Five-Dimension Review

架构集成、失败路径、权威边界、配置、可维护性均通过；旧 reducer 仍为 baseline，Gateway/SQLite/adapter/readiness/Verifier 权威未迁移。未启动 Gateway、Dora、Action、仿真动作或硬件。

Architecture integration, failure paths, authority boundaries, configuration, and maintainability all pass; the legacy reducer remains the baseline and Gateway/SQLite/adapter/readiness/Verifier ownership is unchanged. No Gateway, Dora, Action, simulation motion, or hardware was started.

### Git 提交 / Git Commit

- Commit: `f6d1b7d`
- Branch: `feature/long-horizon-workflow`

## [v5.5.4] - 2026-09-05

新增 PAOS 纯规划模块 `PhyAgentOS/planning`，引入任务级语义 PlanGraph、动态 Tool admission、节点结算、传递重规划、DecisionTrace 和 review-gated WorkflowPolicyCandidate；不接管 Gateway、SQLite、动作执行或物理真值。PlanRevision/ToolExecutionRecord 增加可选但全量校验的 DAG/node binding。设计基准见 `docs/forge/PLANNING_MODULE_DESIGN.md`，开发者指南同步说明 Skill WorkflowDag 仅为 baseline projection。

Added the pure PAOS planning module `PhyAgentOS/planning` with semantic task PlanGraph, dynamic Tool admission, node settlement, transitive replanning, DecisionTrace, and review-gated WorkflowPolicyCandidate; it owns no Gateway, SQLite, motion execution, or physical truth. PlanRevision/ToolExecutionRecord now support optional but all-or-nothing DAG/node bindings. See `docs/forge/PLANNING_MODULE_DESIGN.md`; the developer guide now treats Skill WorkflowDag as a baseline projection only.

### 文件变更详情 / Detailed changes

- `PhyAgentOS/planning/{contracts,dag,admission,settlement,replan,trace,policy}.py:L1-L316`：纯协议和计算，覆盖 digest、依赖/cycle、ready set、evidence/scene/resource/capability/precondition admission、unknown/stale/cancelled settlement、replan delta、trace 和 policy 校验。
- `PhyAgentOS/forge/task.py:L83-L197`：PlanRevision 与 ToolExecutionRecord 绑定 artifact graph/node/obligation/trace digest；SQLite 仍为生命周期事实源。
- `docs/forge/PLANNING_MODULE_DESIGN.md:L1-L118`、`docs/forge/MANIPULATION_DAG_DEVELOPER_GUIDE.md:L10-L216`：记录所有权、失败语义、演化边界和迁移阶段。
- `tests/test_planning_module.py:L1-L267`：逐项纯函数、失败路径、生命周期绑定和纯模块边界回归。

### 五维审查 / Five-Dimension Review

架构集成、失败路径、权威边界、配置、可维护性均通过；未启动 Gateway、Dora、Action、仿真动作或硬件。规划模块只产生结构准入结果，永不产生 motion authority。

Architecture integration, failure paths, authority boundaries, configuration, and maintainability all pass; no Gateway, Dora, Action, simulation motion, or hardware was started. The planning module produces structural admission results only and never grants motion authority.

### 验证 / Validation

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_planning_module.py` → `8 passed`
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -p pytest_asyncio.plugin -q tests` → `180 passed`
- `python -m ruff check PhyAgentOS/planning PhyAgentOS/forge/task.py PhyAgentOS/forge/__init__.py tests/test_planning_module.py`、`compileall`、`git diff --check` → 通过。

### Git 提交 / Git Commit

- Commit: `f95c53d`
- Branch: `feature/long-horizon-workflow`

## [v5.5.2] - 2026-09-06

完成双臂能力 Query 的 canonical DAG 接入复验：固定七节点
`observe → capabilities → understand → propose → prepare → acquire → place`，所有后续步骤
强制复用同一个 capability snapshot；同步升级 DAG/reducer、Skill manifest 与 Python 包版本，并
修正文档和旧 Runtime fixture。组合回归 `670 passed, 1 skipped`；未启动 Gateway、Dora、Action、
仿真运动或硬件。

Completed the acceptance re-review for the dual-arm capability Query canonical-DAG integration: the
seven-node order `observe → capabilities → understand → propose → prepare → acquire → place` is fixed,
all downstream steps must reuse one capability snapshot, protocol/Skill/package versions are bumped, and
documentation plus old-Runtime fixtures are synchronized. Combined regression: `670 passed, 1 skipped`;
no Gateway, Dora, Action, simulation motion, or hardware was started.

### 文件变更详情 / Detailed changes

- `examples/forge-skills/pick-place-workflow/src/pick_place_workflow/long_horizon.py:L15-L17,L173-L236,L560-L585`：新增 canonical `capabilities` 节点、传播并校验 `capability_snapshot_ref`，升级 DAG/reducer 版本。
- `examples/forge-skills/pick-place-workflow/tests/test_long_horizon.py:L25-L311`：更新七节点顺序、terminal response、恢复和绑定漂移回归。
- `examples/forge-skills/pick-place-workflow/skill.yaml:L1-L16`、`pyproject.toml:L1-L6`、`tests/test_binding_freeze.py:L58-L103`、`tests/test_runtime_install_discovery.py:L34-L100`、`tests/test_task_binding_activation.py:L68-L154`、`tests/test_grasp_propose.py:L261-L265`、`tests/test_runtime_controller.py:L73-L76`：统一 Skill `0.10.0` 并验证旧 Runtime fail-closed。
- `examples/forge-skills/pick-place-workflow/README.md:L3-L58`、`SKILL.md:L26-L50,L113-L120`、`docs/forge/MANIPULATION_DAG_DEVELOPER_GUIDE.md:L47-L58`、`docs/user_development_guide/README.md:L25-L30`、`README_en.md:L25-L31`：同步七 Tool 顺序和无动作边界。
- `docs/forge/STATE_FILE_IMPLEMENTATION_REVIEW_20260903.md:L902-L933`、`docs/forge/PAOS_STATE_FILE_ARCHITECTURE_DIAGNOSIS.md:L939-L959`、`examples/forge-skills/pick-place-workflow/CHANGELOG.md:L3-L22`：记录五维验收和剩余 readiness/atomic route 门禁。

### 五维审查 / Five-Dimension Review

架构集成、失败路径、权威边界、配置、可维护性均通过；atomic bimanual executor、真实 readiness/人工审批、完整 transport/descent/release/retreat 与语义闭环仍未实现。

Architecture integration, failure paths, authority boundaries, configuration, and maintainability all pass; an atomic bimanual executor, real readiness/human approval, complete transport/descent/release/retreat, and the semantic loop remain unimplemented.

### 验证 / Validation

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=.:examples/forge-adapters/robotwin20/src:examples/forge-adapters/robotwin20/runtime:examples/forge-skills/pick-place-workflow/src python -m pytest -p pytest_asyncio.plugin -q tests examples/forge-skills/pick-place-workflow/tests examples/forge-adapters/robotwin20/tests` → `670 passed, 1 skipped`
- `python -m ruff check ...`、`python -m compileall -q ...`、`git diff --check` → 通过。
- 未启动 Gateway、Dora、Action、仿真运动或硬件；`motion_authorized=false` 边界保持不变。

## [v5.5.1] - 2026-09-05

完成 PAOS 双臂扩展协议收口：`object.acquire/place` 现在强制绑定 capability snapshot 与 arm assignment；新增只读 `manipulation.capabilities` Query、Skill manifest/contract/Fake Gateway 接入和严格失败关闭。组合回归 `669 passed, 1 skipped`；未启动任何动作、仿真运动或硬件。

Completed the PAOS dual-arm extension contract closeout: `object.acquire/place` now require capability-snapshot and arm-assignment bindings; the read-only `manipulation.capabilities` Query is integrated with the Skill manifest, contract, and Fake Gateway with strict fail-closed behavior. Combined regression: `669 passed, 1 skipped`; no action, simulation motion, or hardware was started.

### 文件变更详情 / Detailed changes

- `PhyAgentOS/forge/manipulation.py:L29-L380`：新增冻结的资源需求、能力快照、assignment、协调组和 digest。
- `PhyAgentOS/forge/capability_runtime/manipulation_capabilities.py:L23-L105`：新增 provider-neutral capability Query。
- `examples/forge-skills/pick-place-workflow/src/pick_place_workflow/long_horizon.py:L191-L225,L440-L473,L552-L610`：DAG action binding 强制 capability/assignment refs。
- `examples/forge-skills/pick-place-workflow/src/pick_place_workflow/object_acquire.py:L95-L225,L300-L425`、`object_place.py:L40-L270,L340-L501`：同步 Action schema/校验。
- `examples/forge-skills/pick-place-workflow/src/pick_place_workflow/fake_gateway.py:L14-L24,L285-L430`、`contracts/manipulation.capabilities.tool.yaml`、`skill.yaml`：完成 discovery/query wiring。
- `docs/forge/MANIPULATION_DAG_DEVELOPER_GUIDE.md`、`docs/forge/PAOS_STATE_FILE_ARCHITECTURE_DIAGNOSIS.md`、`changelog/2026-09_part3.md`：更新架构边界和五维审查。

### 五维审查 / Five-Dimension Review

架构集成、失败路径、权威边界、配置、可维护性均通过；atomic bimanual executor、真实 readiness/approval 与完整语义闭环仍未实现。

Architecture integration, failure paths, authority boundaries, configuration, and maintainability all pass; an atomic bimanual executor, real readiness/approval, and the complete semantic loop remain unimplemented.

### 验证 / Validation

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=.:examples/forge-adapters/robotwin20/src:examples/forge-adapters/robotwin20/runtime:examples/forge-skills/pick-place-workflow/src python -m pytest -p pytest_asyncio.plugin -q tests examples/forge-skills/pick-place-workflow/tests examples/forge-adapters/robotwin20/tests` → `669 passed, 1 skipped`
- Ruff、compileall、`git diff --check`：通过。

### Git 提交 / Git Commit

- Commit: `c60f58c`
- Branch: `feature/long-horizon-workflow`

## [v5.4.4] - 2026-09-05

完成 RoboTwin/Curobo 250 Hz 轨迹语义修复：route profile 现在显式声明并绑定 uniform time-dilation retiming，保持 1.0 rad/s PAOS 策略、不修改 Franka URDF 限幅，并保留 endpoint/dtype/速度证据。PAOS 环境安装 NumPy 2.5.2；adapter `228 passed, 1 skipped`，根仓库 `168 passed`。新的 v6 package 仍为 `pending_human_review`、`motion_authorized=false`；右臂八阶段 no-motion planner 通过，左臂不可用，未运行仿真动作、Gateway、Dora 或硬件。

Completed the RoboTwin/Curobo 250 Hz trajectory-semantics repair: the route profile now explicitly declares and binds uniform time-dilation retiming, preserving the 1.0 rad/s PAOS policy without changing Franka URDF limits, with endpoint/dtype/speed evidence retained. NumPy 2.5.2 is installed in the PAOS environment; adapter `228 passed, 1 skipped`, root `168 passed`. The new v6 package remains `pending_human_review` and `motion_authorized=false`; all eight right-arm no-motion planner phases pass while the left arm is unavailable, and no simulation motion, Gateway, Dora, or hardware was run.

### 文件变更详情 / Detailed changes

- `examples/forge-adapters/robotwin20/runtime/robotwin_simulation_probe_worker.py:L422-L535,L542-L603,L829-L891`：增加 profile-owned retiming、dtype/endpoint/速度校验，并把 retiming evidence 写入 trajectory。
- `examples/forge-adapters/robotwin20/profiles/robotwin20/route-inputs.yaml:L40-L51`：声明 250 Hz、0.95 safety margin、20,000 sample 上限。
- `examples/forge-adapters/robotwin20/tests/test_simulation_probe.py:L11-L340`：增加 retiming 单位、端点、速度、dtype、预算和失败路径测试。
- `examples/forge-adapters/robotwin20/README.md:L441-L451`、`docs/forge/PAOS_STATE_FILE_ARCHITECTURE_DIAGNOSIS.md:L881-L904`、`changelog/2026-09_part3.md:L186-L235`：更新 v6 evidence、五维审查和 readiness 门禁。

### 关键 Diff / Key Diff

```text
Before: Curobo samples above the profile-owned 1.0 rad/s policy were rejected, with no route passing continuous preflight.
After:  bounded profile-owned resampling at RoboTwin's 250 Hz cadence preserves endpoints and verifies retimed speed; v6 right-arm eight-phase planner preflight passes without simulator steps.
```

### 验证 / Validation

- `/home/yanxu/miniconda3/envs/paos/bin/python -m pytest ...` → adapter `228 passed, 1 skipped`; root `168 passed`; focused `62 passed`。
- `ruff`、`compileall`、`git diff --check` 通过。
- v6 preflight：`status=available`、右臂全阶段通过、左臂 `unavailable`、`robot_control_steps=0`、`simulator_steps=0`。
- 仍需 fresh human approval；未启动 simulation probe、Gateway、Dora、Action 或硬件。

### Git 提交 / Git Commit

- Commit: pending
- Branch: `feature/long-horizon-workflow`

## [v5.4.3] - 2026-09-05

完成 GraspGen depth 到 RoboTwin planner-frame 的 PAOS adapter 修复。`provider_T_contact_center`
先重建 canonical contact center，再由 Franka profile 派生 `robot_target_pose`；route、probe 和
approval 改用 `object_T_robot_target`，旧的混合 TCP 契约 fail-closed。新的 v3 package 保持
`pending_human_review` 与 `motion_authorized=false`。

Completed the PAOS adapter repair for GraspGen depth and the RoboTwin planner frame. The adapter first
reconstructs the canonical contact center with `provider_T_contact_center`, then derives `robot_target_pose`
from the Franka profile; route, probe, and approval now use `object_T_robot_target`, while mixed legacy TCP
contracts fail closed. The new v3 package remains `pending_human_review` with `motion_authorized=false`.

### 文件变更详情 / Detailed changes

- `examples/forge-adapters/robotwin20/src/robotwin20_adapter/grasp_adaptation.py:L193-L340`：分离 provider depth、canonical contact、RoboTwin standard target 和 planner round-trip。
- `examples/forge-adapters/robotwin20/src/robotwin20_adapter/route_generation.py:L194-L359`、`route_readiness.py:L241-L352`、`route_inputs.py:L1-L390`：升级 v3 route 与对象变换契约。
- `examples/forge-adapters/robotwin20/runtime/robotwin_simulation_probe_worker.py:L37-L270,L477-L730`、`scripts/approve_simulation_probe.py:L15-L145`：同步 v3 approval/artifact digest 绑定。
- `examples/forge-adapters/robotwin20/profiles/robotwin20/route-inputs.yaml`、`graspgen-tool-transform.json`、`README.md`：声明 profile 与使用边界。
- `docs/forge/PAOS_STATE_FILE_ARCHITECTURE_DIAGNOSIS.md:L900-L934`、`changelog/2026-09_part3.md:L125-L205`：记录诊断、证据和人工审批门禁。
- `tests/test_grasp_adaptation.py`、`test_route_inputs.py`、`test_route_generation.py`、`test_route_readiness.py`、`test_simulation_probe.py`、`test_approve_simulation_probe.py`：增加 frame round-trip、旧契约拒绝和 digest 绑定回归。

### 验证 / Validation

- 专项 `69 passed`；完整 adapter（正确加载 pick-place 与 pytest-asyncio，排除 NumPy provider collection）`212 passed, 2 skipped`。
- `ruff`、`compileall`、`git diff --check` 通过；RoboTwin20 Python 3.10 no-motion preflight 仅产生 preliminary evidence，`prepared_candidates=[]`、`collision=unavailable`、零 simulator step。
- 未启动 Gateway、Dora、Action、硬件或 simulation probe；v4 approval 不可复用，当前等待新的人工审批。

### Git 提交 / Git Commit

- Commit: pending
- Branch: `feature/long-horizon-workflow`

## [v5.2.1] - 2026-09-05

回写 v5.2.0 PAOS-first 操作规划重构实现提交 `514e044`。实现、十一项 Major 修复、五维验收、测试结果与
后续真实 readiness 门禁均未改变；`.codegraph/`、`.cursor/` 保持未跟踪且未提交。

Recorded v5.2.0 PAOS-first manipulation-planning implementation commit `514e044`. The implementation,
eleven Major fixes, five-dimension acceptance, test results, and subsequent real-readiness gate are unchanged;
`.codegraph/` and `.cursor/` remain untracked and uncommitted.

### 文件变更详情 / Detailed changes

- `changelog/2026-09_part2.md:L2996-L3037` 与 `changelog/2026-09_part3.md:L62-L101`：回写 v5.2.0
  implementation commit `514e044`、校正最终实现行号，并新增 v5.2.1 双语维护记录。
- `changelog/2026-09_part2.md:L2996-L3037` and `changelog/2026-09_part3.md:L62-L101`: record v5.2.0
  implementation commit `514e044`, correct final implementation line ranges, and add the bilingual v5.2.1 record.
- `CHANGELOG.md:L5-L60,L143-L147`：新增本条完整记录、回写 v5.2.0 commit，并滚动 Archive 边界；不修改运行代码。
- `CHANGELOG.md:L5-L60,L143-L147`: adds this complete record, records the v5.2.0 commit, and rolls the Archive boundary
  without changing runtime code.

### 关键 Diff / Key Diff

```text
Before: v5.2.0 implementation and validation were recorded with Commit: pending.
After:  implementation commit 514e044 and the pushed branch are explicitly recorded; code and evidence are unchanged.
```

### 验证 / Validation

- `514e044` 已推送到 `origin/feature/long-horizon-workflow`；`git diff --check` 和 UTF-8 日志显示检查通过。
- 本维护提交只包含日志；`.codegraph/`、`.cursor/` 未暂存。

### Git 提交 / Git Commit

- Implementation commit: `514e044`
- Branch: `feature/long-horizon-workflow`

## [v5.2.0] - 2026-09-05

完成 PAOS-first 操作规划收口与第二轮五维代码审查。Skill reducer 现在以 immutable DAG readiness 驱动；replan hint 绑定 node digest；RoboTwin route-readiness 明确适配到独立 route-evaluation contract，并拒绝 release TCP 变换或 phase gripper 语义不一致。PAOS task/revision/SQLite/Verifier/Gateway 权威边界和 no-motion 门禁保持不变。

Closed the PAOS-first manipulation-planning refactor and the second five-dimension code review. The Skill reducer is now driven by immutable DAG readiness; replan hints bind node digests; RoboTwin route-readiness explicitly adapts to the independent route-evaluation contract and rejects inconsistent release-TCP transforms or phase gripper semantics. PAOS task/revision/SQLite/Verifier/Gateway authority and no-motion gates remain unchanged.

### 文件变更详情 / Detailed changes

- `PhyAgentOS/forge/manipulation.py:L1-L314`：移除重叠生命周期并增加带 `node_digest` 的自校验 `ReplanSignal`。
- `examples/forge-skills/pick-place-workflow/src/pick_place_workflow/long_horizon.py:L1-L639`：DAG-ready reducer、immutable references 和恢复状态校验。
- `examples/forge-adapters/robotwin20/src/robotwin20_adapter/route_readiness.py:L95-L591`：route semantic validation、完整 candidate evidence validation 与 `RouteReadinessEvaluationAdapter`。
- `examples/forge-adapters/robotwin20/src/robotwin20_adapter/arm_candidates.py:L1-L583`、`route_generation.py:L1-L335`、`perception_profile.py:L27-L184`：adapter/profile ownership、路线选择和 strict YAML。
- `docs/forge/STATE_FILE_IMPLEMENTATION_REVIEW_20260903.md:L843-L886`、`docs/forge/PAOS_STATE_FILE_ARCHITECTURE_DIAGNOSIS.md:L829-L842`、`changelog/2026-09_part2.md:L2947-L3037`：记录十一个 Major 修复、五维验收和后续门禁。

### 验证 / Validation

- 组合 core/adapter/Skill（排除缺少 NumPy 的 GraspGen collection）→ `616 passed, 2 skipped`；core/adapter `355 passed, 2 skipped`；Skill `261 passed`；根仓库 `168 passed`；route generation/readiness/selection 专项 `36 passed`；开发者指南完整 DAG/route/evidence 专项 `69 passed`。
- `ruff check`、`compileall`、`git diff --check` → 通过。
- 未启动 Gateway、Dora、Action、硬件或仿真运动；真实 readiness、人工批准和抓取放置闭环仍未完成。
- Implementation commit: `514e044` on `feature/long-horizon-workflow`。

## [v5.1.0] - 2026-09-05 (withdrawn)

路线生成草案在实现审查中发现 PAOS 权威边界、frame/transform 语义和配置归属问题，未进入完成、提交或动作接入；未提交草案由 v5.2.0 PAOS-first 重构替代。

The route-generation draft was withdrawn after review found PAOS authority-boundary, frame/transform-semantics, and configuration-ownership issues. It was not completed, committed, or wired to motion; the uncommitted draft was superseded by the v5.2.0 PAOS-first refactor.

### 文件变更详情 / Detailed changes

- `examples/forge-adapters/robotwin20/src/robotwin20_adapter/route_generation.py`：草案保留为后续 adapter 语义参考，未作为独立完成版本发布。
- `docs/forge/STATE_FILE_IMPLEMENTATION_REVIEW_20260903.md`、`docs/forge/PAOS_STATE_FILE_ARCHITECTURE_DIAGNOSIS.md`：记录撤销原因和边界。

### 验证 / Validation

- 未创建 motion wiring、Gateway/Dora invocation 或 readiness approval；该版本不作为完成实现计入。

## [v5.0.0] - 2026-09-05

新增 provider-neutral 语义 Manipulation DAG、双臂候选枚举、完整路线选择和失败重规划契约。公共层只
保存语义依赖、资源/证据绑定、不可变摘要和 no-motion 重规划信号；RoboTwin adapter 保存本体 profile、
候选×手臂展开和完整路线 evaluator/selector。现有 AgentTaskRecord、PlanRevision、SQLite、Runtime、
Evidence、Verifier、Gateway、Dora 和 Action 权威边界未改变，Hephaestus 仅作为设计参考。

Added provider-neutral semantic Manipulation DAG, dual-arm candidate enumeration, complete-route selection,
and failure-replanning contracts. The public layer stores semantic dependencies, resource/evidence bindings,
immutable digests, and no-motion replan signals; the RoboTwin adapter owns embodiment profiles, candidate×arm
expansion, and complete-route evaluation/selection. Existing AgentTaskRecord, PlanRevision, SQLite, Runtime,
Evidence, Verifier, Gateway, Dora, and Action authority boundaries are unchanged; Hephaestus is design reference only.

### 文件变更详情 / Detailed changes

- `PhyAgentOS/forge/manipulation.py`：新增严格 Pydantic DAG/Intent/RouteFailure/Replan contracts；所有运动授权固定为 `false`。
- `examples/forge-adapters/robotwin20/src/robotwin20_adapter/arm_candidates.py`：新增 profile-owned candidate×arm enumeration、完整路线 selector、独立 evaluator/selection schema 和 fail-closed validation。
- `examples/forge-adapters/robotwin20/profiles/robotwin20/manipulation-planning.yaml`：新增 Franka dual-independent profile 与确定性评分策略。
- `docs/forge/MANIPULATION_DAG_DEVELOPER_GUIDE.md`、`docs/forge/PAOS_STATE_FILE_ARCHITECTURE_DIAGNOSIS.md`、`docs/forge/STATE_FILE_IMPLEMENTATION_REVIEW_20260903.md`：记录 PAOS 扩展边界、Hephaestus clean-room 参考、开发规则和五维审查。
- `tests/test_manipulation.py`、`examples/forge-adapters/robotwin20/tests/test_arm_candidates.py`：覆盖 DAG、绑定、拓扑、重规划预算、候选枚举、确定性选择和篡改失败。

### 验证 / Validation

- 专项契约：`16 passed`。
- PAOS/RoboTwin adapter 组合套件：`338 passed, 2 skipped`（跳过缺少 NumPy 的 GraspGen provider collection）。
- 根仓库套件：`171 passed`。
- `ruff`、`compileall`、`git diff --check`：通过。
- 未启动 Gateway、Dora、Action、硬件或 simulation motion；真实 readiness 仍受上一阶段 `not_approved_for_readiness_or_motion_wiring` 门禁约束。
- Git commit: `d09cca5` on `feature/long-horizon-workflow`.

## [v4.12.2] - 2026-09-05

回写 v4.12.1 独立 RoboTwin simulation-probe 实现提交 `f88778a`。实现、真实负证据、五维验收结论与
后续执行门禁均未改变；`.codegraph/`、`.cursor/` 仍为未跟踪的用户目录，未纳入提交。

Recorded the v4.12.1 independent RoboTwin simulation-probe implementation commit `f88778a`. The
implementation, real negative evidence, five-dimension acceptance conclusions, and next execution gate are
unchanged; the user-owned `.codegraph/` and `.cursor/` directories remain untracked and uncommitted.

### 文件变更详情 / Detailed changes

- `changelog/2026-09_part2.md:L310-L403`：新增 v4.12.2 双语维护记录，并将 v4.12.1 的
  `Commit: pending` 更新为 `f88778a`。
- `changelog/2026-09_part2.md:L310-L403`: adds the bilingual v4.12.2 maintenance record and replaces the
  v4.12.1 `Commit: pending` marker with `f88778a`.
- `CHANGELOG.md:L5-L95`：同步根日志最近记录及 v4.12.1 implementation commit；未修改运行代码。
- `CHANGELOG.md:L5-L95`: synchronizes the root recent entry and v4.12.1 implementation commit without
  changing runtime code.

### 关键 Diff / Key Diff

```text
Before: v4.12.1 implementation and validation were recorded with Commit: pending.
After:  implementation commit f88778a and pushed branch are explicitly recorded; code and evidence are unchanged.
```

### 验证 / Validation

- `f88778a` 同时为本地 `HEAD` 和 `origin/feature/long-horizon-workflow`；日志 UTF-8 显示正常。
- `git diff --check` 通过；仅两份日志进入定向提交，未跟踪用户目录未暂存。

### Git 提交 / Git Commit

- Implementation commit: `f88778a`
- Branch: `feature/long-horizon-workflow`

## Archive

- [2026-09 part 3](changelog/2026-09_part3.md)
- [2026-09 part 2](changelog/2026-09_part2.md)
- [2026-09](changelog/2026-09.md)

## [v4.12.1] - 2026-09-05

收紧独立 RoboTwin simulation probe 的真实性门禁：为 block actor 分配唯一身份，首步前保存 before
snapshot，校验实际 backend revision，并要求目标实体在 lift 阶段真实升高至少 1 cm。修复 client 将
“世界曾变化”错误等同于“仍需 reconciliation”的协议问题，以及启动时双 reset 导致的 revision 漂移。

最终复审进一步实体化并执行 joint/stop policy，将 calibration 与 policy 内容摘要绑定进 approval，校验
runtime limit 的有限有序性和规划/观测速度，并将 worker 固定为 single-use；planning/finalization 失败
统一保存不可变诊断并进入 reset 恢复。scene reset 现在也被如实计为仿真世界变化。

Tightened the independent RoboTwin simulation probe's truthfulness gates: assign unique block identities,
persist the before snapshot before the first step, verify the actual backend revision, and require the target
entity to rise by at least 1 cm during lift. Fixed the client protocol conflating prior world change with pending
reconciliation and removed the startup double-reset revision drift.

The final review also materializes and enforces joint/stop policies, binds calibration and policy digests into the
approval, validates finite ordered runtime limits and planned/observed speeds, makes the worker single-use, and
routes planning/finalization failures through immutable diagnostics and reset recovery. Scene reset is now
truthfully counted as a simulation-world change.

### 文件变更详情 / Detailed changes

- `robotwin_simulation_probe_worker.py:L110-L173,L295-L397,L514-L1225`：绑定审批输入摘要，执行实体化
  policy、runtime/速度/真实 lift 门禁，并统一 finalization/failure/reset；worker 固定 single-use。
- `robotwin_simulation_probe_worker.py:L110-L173,L295-L397,L514-L1225`: binds approved input digests,
  enforces materialized policies plus runtime/speed/real-lift gates, unifies finalization/failure/reset, and makes
  the worker single-use.
- `simulation_probe.py:L41-L108` 与 `test_simulation_probe.py:L1-L656`：收紧 client failure/reconciliation
  contract，并覆盖摘要篡改、limits、失败恢复与 revision 生命周期。
- `simulation_probe.py:L41-L108` and `test_simulation_probe.py:L1-L656`: tighten the client
  failure/reconciliation contract and cover digest tampering, limits, recovery, and revision lifecycle.
- `PAOS_STATE_FILE_ARCHITECTURE_DIAGNOSIS.md:L737-L763`、`STATE_FILE_IMPLEMENTATION_REVIEW_20260903.md:L773-L804`
  与 adapter README `L395-L428`：记录最终真实负证据、五维验收和下一门禁。
- The diagnosis `L737-L763`, implementation review `L773-L804`, and adapter README `L395-L428` record the
  final real negative evidence, five-dimension acceptance, and next gate.

### 关键 Diff / Key Diff

```text
Before: approval bound policy references but not their bytes; final evidence failures could escape recovery;
        scene reset could be reported as no world change.
After:  approval binds calibration/joint/stop SHA-256; all post-reset failures persist diagnostics and reset;
        scene reset is a world change, while negative evidence never becomes readiness.
```

### Validation

- Latest real run: `paos-simulation-probe-20260905T020000p0800-policy-v6` returned `unavailable` before a robot
  step because the left arm failed planning and the right arm exceeded the approved `1.0 rad/s` limit; the scene
  reset was recorded as world change, recovery reset completed, and readiness/motion wiring was not approved.
- Focused simulation-probe conformance: `21 passed`; adapter subset: `158 passed, 2 skipped`; repository:
  `164 passed`; ruff, compileall, and diff-check passed.
- Gateway, Dora, Action executor, and hardware remain disconnected. Commit: `f88778a` on
  `feature/long-horizon-workflow`.

## [v4.11.0] - 2026-09-04

新增独立 route-evidence verifier：消费外部授权 simulation probe 产物，校验附着 geometry、planner route、六项 readiness scope、before/after snapshot、semantic verdict、producer identity 和 SHA-256；verifier 与 worker 始终保持 no-motion，不启动 RoboTwin、Dora、Gateway 或硬件。

Added an independent route-evidence verifier that consumes artifacts from an authorized external simulation probe and validates attached geometry, planner route, six readiness scopes, before/after snapshots, semantic verdict, producer identity, and SHA-256. The verifier and worker remain no-motion and never start RoboTwin, Dora, Gateway, or hardware.

### Detailed changes

- Added `examples/forge-adapters/robotwin20/src/robotwin20_adapter/route_evidence.py`, `runtime/robotwin_route_evidence_worker.py`, `profiles/robotwin20/route-evidence.yaml`, and `tests/test_route_evidence.py`.
- Added strict producer/probe execution binding so external world change is explicit and cannot be confused with verifier no-motion.
- Updated PAOS diagnosis, implementation review, and adapter README with the five-dimension acceptance and remaining motion gate.

### Validation

- Verifier focus: `10 passed`; combined route/readiness/action focus: `80 passed`; repository: `164 passed`.
- Ruff, compileall, and `git diff --check` passed. No RoboTwin `play_once`, Dora, Gateway motion, or hardware was started.
- Commit: `3d72b98` on `feature/long-horizon-workflow`.

## [v4.10.0] - 2026-09-05

新增 simulation route-readiness contract、profile-owned bounded JSONL worker 和外部配置。请求绑定附着物体 geometry/digest、八阶段路线、waypoint frame/速度限幅、workspace 与 stop policy；当前 worker 对真实 planner、附着碰撞、接触动力学、stop controller 和语义验收明确返回 unavailable，保持 no-motion。

Added the simulation route-readiness contract, profile-owned bounded JSONL worker, and external configuration. Requests bind attached-object geometry/digests, eight route phases, waypoint frames/speed limits, workspace, and stop policy; the current worker explicitly returns unavailable for the real planner, attached collision, contact dynamics, stop controller, and semantic verification while remaining no-motion.

### Detailed changes

- Added `examples/forge-adapters/robotwin20/src/robotwin20_adapter/route_readiness.py:L1-L344`, `runtime/robotwin_route_readiness_worker.py:L1-L99`, `profiles/robotwin20/route-readiness.yaml:L1-L18`, and `tests/test_route_readiness.py:L1-L166`.
- Exported route readiness APIs from `robotwin20_adapter/__init__.py:L67-L78,L185-L193`.
- Updated architecture diagnosis, implementation review, adapter README, and monthly changelog.

### Validation

- Route readiness: `9 passed`; combined readiness/action/Gateway focus: `81 passed`; repository: `164 passed`.
- Ruff, compileall, and `git diff --check` passed. No RoboTwin `play_once`, Dora, Gateway motion executor, or hardware was started.
- Git commit: `ada59b5` on `feature/long-horizon-workflow`.

## [v4.9.0] - 2026-09-05

新增独立的 simulation-motion authorization profile/schema。`simulation_authorization.py` 严格绑定 runtime/evidence manifest digest、任务/场景/Franka 本体身份、四类 readiness scope、审批记录、停止策略和 before/after semantic snapshot；默认配置为 disabled/no-motion，不启动任何 worker 或动作。

Added an isolated simulation-motion authorization profile/schema. `simulation_authorization.py` binds runtime/evidence-manifest digests, task/scene/Franka identity, four readiness scopes, approval records, stop policy, and before/after semantic snapshots; the checked-in profile is disabled/no-motion and starts no worker or action.

### Detailed changes

- Added `examples/forge-adapters/robotwin20/src/robotwin20_adapter/simulation_authorization.py:L1-L443`, `profiles/robotwin20/simulation-motion.yaml:L1-L47`, and `tests/test_simulation_authorization.py:L1-L238`.
- Exported the schema/profile loader from `robotwin20_adapter/__init__.py:L55-L64,L143-L149`.
- Updated architecture diagnosis, five-dimension review, adapter README, and `changelog/2026-09_part2.md`.

### Validation

- Simulation profile conformance: `10 passed`; readiness/action/Gateway focused suite: `81 passed`; repository: `164 passed`.
- Ruff, compileall, and `git diff --check` passed. No RoboTwin `play_once`, Dora, Gateway motion executor, or hardware was started.
- Git commit: `0447dab` on `feature/long-horizon-workflow`.

## [v4.8.0] - 2026-09-05

将 Action 生命周期改为 invocation-first：先创建 invocation/attempt，再启动 deferred provider；保留失败、取消、超时和 unknown 语义。

Changed the Action lifecycle to invocation-first: allocate invocation/attempt before starting deferred providers while preserving failure, cancel, timeout, and unknown semantics.

### Detailed changes

- Updated `PhyAgentOS/forge/capability_runtime/ports.py:L17-L23`, `runtime.py:L204-L270`, and pick-place endpoints/gateway at `object_acquire.py:L51-L60,L410-L488`, `object_place.py:L56-L65,L487-L565`, `fake_gateway.py:L272-L307,L494-L795`.
- Added provider identity/start-failure/deferred cancel-stop conformance and documented the five-dimension review.

### Validation

- Focused Action/Gateway tests: `58 passed`; repository: `164 passed`; pick-place suite: `256 passed`.
- No simulation motion, Dora, or hardware execution was enabled.

## [v4.7.14] - 2026-09-05

记录仿真 motion executor 的前置阻断，修订顺序为 invocation-first、独立 simulation authorization、完整 readiness、before/after snapshot 与语义验收后再运动。

Recorded simulation motion-executor blockers and revised the order to invocation-first, isolated simulation authorization, complete readiness, before/after snapshots, and semantic verification before motion.

### Detailed changes

- Updated `docs/forge/PAOS_STATE_FILE_ARCHITECTURE_DIAGNOSIS.md:L585-L630` and `docs/forge/STATE_FILE_IMPLEMENTATION_REVIEW_20260903.md:L606-L628`.
- Verified no-motion Action/Gateway `52 passed` and repository `161 passed`; no RoboTwin motion stepping.

## [v4.7.10] - 2026-09-05

回写 v4.7.9 Action readiness gate 实现提交哈希 `83c74ff`；未修改运行逻辑，用户目录 `.codegraph/` 与 `.cursor/` 未纳入提交。

Recorded the v4.7.9 Action readiness-gate implementation commit hash `83c74ff`; runtime logic was unchanged, and user directories `.codegraph/` and `.cursor/` were excluded from the commit.

### Detailed changes

- Updated `changelog/2026-09_part2.md` with the completed maintenance record and exact implementation commit.
- Kept user-owned `.codegraph/` and `.cursor/` directories out of the change.

### Validation

- Verified the working tree contains only the intended changelog/index edits plus pre-existing untracked user directories.
- Git commit: `e6883f8` on `feature/long-horizon-workflow`.

## [v4.7.9] - 2026-09-05

接入已人工审核 readiness evidence 的 Action admission no-motion gate。`object.acquire`/
`object.place` 在创建 Gateway invocation 前校验 manifest/review/evidence SHA-256、同一
scene/candidate-set/frame/calibration、candidate/entity、worker/embodiment identity、三项
readiness checks 和 `motion_authorized=false`；Fake Gateway action context 显式返回 no-motion，
并拒绝 provider 报告的 `world_change_started=true`。manifest/review/artifact 路径由
`profiles/robotwin20/action-readiness.yaml` 和环境变量注入。

Added a no-motion Action-admission gate backed by manually reviewed readiness evidence. Before
allocating a Gateway invocation, `object.acquire`/`object.place` validate manifest/review/evidence
SHA-256, scene/candidate-set/frame/calibration, candidate/entity, worker/embodiment identity, all
readiness checks, and `motion_authorized=false`. Fake Gateway Action contexts explicitly expose
no-motion and reject providers reporting `world_change_started=true`. Manifest/review/artifact
paths are injected through `profiles/robotwin20/action-readiness.yaml` and environment variables.

### Detailed changes

- Added `examples/forge-adapters/robotwin20/src/robotwin20_adapter/action_readiness.py:L1-L274` and `profiles/robotwin20/action-readiness.yaml:L1-L4`.
- Added `examples/forge-adapters/robotwin20/tests/test_action_readiness_gate.py:L1-L273`.
- Updated Skill Action endpoints and Fake Gateway at `examples/forge-skills/pick-place-workflow/src/pick_place_workflow/object_acquire.py:L51-L60,L410-L488`, `object_place.py:L56-L65,L487-L565`, and `fake_gateway.py:L261-L297,L375-L410`.
- Updated architecture diagnosis, five-dimension review, and adapter README.

### Validation

- Focused Action/Gateway/readiness conformance: `52 passed`.
- Ruff and `git diff --check` passed; real Franka manifest gate loaded all `50` evidence candidates.
- No RoboTwin `play_once`, Dora, Action stepping, or hardware motion was invoked.

## [v4.7.6] - 2026-09-04

完成 Franka `blocks_ranking_rgb` 的独立 readiness worker 证据闭环，并将 live worker 接入 adapter 的 bounded JSONL profile seam。相同 `blocks_ranking_rgb-0-1/head_camera` 上生成 12 个 geometry/point-cloud derived artifacts，GraspGen funnel 为 `72→72→71→71`，Curobo no-motion worker 为 `50/71` prepared；50 个 evidence ref 唯一且全部绑定 request、candidate-set、observation、scene、frame、calibration、worker 和 profile digest。

Completed the independent readiness-worker evidence loop for Franka `blocks_ranking_rgb` and wired the live worker through the adapter's bounded JSONL profile seam. On the same `blocks_ranking_rgb-0-1/head_camera`, 12 geometry/point-cloud derived artifacts were verified, GraspGen produced funnel `72→72→71→71`, and the Curobo no-motion worker prepared `50/71`; all 50 evidence refs are unique and bound to request, candidate-set, observation, scene, frame, calibration, worker, and profile digest.

### Detailed changes

- Added `runtime/robotwin_readiness_worker.py` live schema, strict freshness/provenance/pose checks, and per-evidence no-motion bindings.
- Added `profiles/robotwin20/readiness-live.yaml`, `ReadinessLiveClient`, and `build_live_readiness_evaluator`; added schema/motion-drift tests.
- Updated architecture diagnosis, implementation review, and adapter README. Manual review authorizes only the next no-motion Action/Gateway review; no Action, Dora, attached-object transport, or hardware motion is authorized.

### Validation

- Adapter readiness/backend tests: `50 passed`; repository with explicit async plugin: `161 passed`.
- External live profile → worker → PAOS `manipulation.prepare`: `available`, `50 prepared`, all checks `pass`, `motion_authorized=false`.
- Ruff, compileall, and `git diff --check` passed. Evidence manifest: `b0cd2298b84bbc4be0470fb66da4b543928836dd026433ae7e0861cb691fec79`.

## [v4.7.4] - 2026-09-04

完成 Franka `blocks_ranking_rgb` readiness 输入审计：capture 缺少同一 scene revision 的 geometry/candidate，现有 GraspGen 结果不可跨场景复用，因此安全记录 `unavailable`，未启动 IK/碰撞或动作链路。

Completed the Franka `blocks_ranking_rgb` readiness-input audit: the capture lacks same-revision geometry/candidates and the existing GraspGen result cannot be reused across scenes, so the gate safely records `unavailable` without starting IK/collision or motion paths.

详细记录见 [FRANKA_READINESS_INPUT_AUDIT_20260904](docs/forge/FRANKA_READINESS_INPUT_AUDIT_20260904.md)。

## [v4.7.5] - 2026-09-04

回写 v4.7.4 Franka readiness 输入审计提交哈希 `ee2144e`；实现和执行顺序不变。

Recorded the v4.7.4 Franka readiness-input audit commit hash `ee2144e`; implementation and execution order are unchanged.

## [v4.7.1] - 2026-09-04

回写 v4.7.0 本体 profile 与 readiness identity 实现提交哈希 `30bf3ed`；没有修改实现行为。

Recorded the v4.7.0 embodiment-profile and readiness-identity implementation commit hash `30bf3ed`; implementation behavior is unchanged.

## [v4.7.2] - 2026-09-04

readiness profile 现在校验绑定的 runtime profile 文件及 SHA-256，防止 benchmark/本体配置漂移后复用旧 evidence。

The readiness profile now verifies its bound runtime-profile file and SHA-256, preventing stale evidence reuse after benchmark or embodiment drift.

## [v4.7.0] - 2026-09-04

完成 RoboTwin adapter 的可替换 embodiment profile 与 readiness 身份绑定。
Franka `blocks_ranking_rgb`（`[franka-panda, franka-panda, 0.8]`）已通过实际
no-motion preflight/scene capture；未接入 Action、Gateway、Dora 或硬件运动。

Completed replaceable RoboTwin embodiment profiles and readiness identity
bindings. Franka `blocks_ranking_rgb` (`[franka-panda, franka-panda, 0.8]`)
passed real no-motion preflight/scene capture; Action, Gateway, Dora, and
hardware motion remain disconnected.

### Detailed changes

- Backend/preflight now validate native dual-arm versus two-single-arm topology and load `franka-blocks-ranking.yaml`.
- Readiness fixture, evidence manifest, worker response, and immutable replay artifact now require matching robot/gripper/topology/planner/profile-digest bindings.
- Updated architecture diagnosis, execution order, and adapter replacement guidance.

### Validation

- Adapter conformance: `71 passed, 1 skipped`; focused backend/preflight/readiness: `37 passed`; repository: `161 passed` with `pytest_asyncio`.
- RoboTwin20 Franka pair preflight: `ready=true`; no-motion capture produced RGB/depth/state/calibration.
- Ruff, compileall, and `git diff --check` passed.

## [v4.5.4] - 2026-09-05

回写 v4.5.3 GraspGen 验收日志维护提交哈希 `36d940d`，并完成 v4.5.4 索引提交 `0cfcd56`；没有修改实现、测试或执行顺序。

Recorded the v4.5.3 GraspGen acceptance-log maintenance commit hash `36d940d` and completed the v4.5.4 index commit `0cfcd56`; implementation, tests, and execution order are unchanged.

## [v4.5.1] - 2026-09-05

回写 v4.5.0 provider no-motion 真实链路验收提交哈希 `9a2af2e`；没有修改实现、测试或执行顺序。

Recorded the v4.5.0 provider no-motion live-chain acceptance commit hash `9a2af2e`; implementation, tests, and execution order are unchanged.

## [v4.5.2] - 2026-09-05

修复 GraspGen worker 的 JSONL stdout conformance，并通过真实 `entity://red-rectangular-block-1` 点云完成 no-motion `grasp.propose`，返回 24 个 provider-neutral candidates；未进入 readiness、Action 或运动。

Fixed GraspGen worker JSONL stdout conformance and completed a no-motion `grasp.propose` on the real `entity://red-rectangular-block-1` point cloud, returning 24 provider-neutral candidates; readiness, Action, and motion remain gated.

### Validation

- Adapter: `104 passed`; repository: `161 passed`; pick-place: `256 passed`; Ruff and compileall passed.
- Evidence manifest: `a7627a6d8583bf4da502dfe1deaf8c3ec1e978f8f274ede545446614f43ae336`.

## [v4.5.3] - 2026-09-05

回写 v4.5.2 GraspGen live provider seam 实现提交哈希 `aff62a5`；没有修改实现、测试或执行顺序。

Recorded the v4.5.2 GraspGen live provider seam implementation commit hash `aff62a5`; implementation, tests, and execution order are unchanged.

## [v4.5.0] - 2026-09-05

完成已接入 provider 的真实 RoboTwin no-motion 链路验收，并修复 runtime stdout 可审计性；按架构集成、失败路径、权威边界、配置、可维护性五维复审无 Blocker/Major。当前仍未进入 Action/Gateway、Dora 或机器人运动。

Completed the live RoboTwin no-motion chain review for currently integrated providers and fixed runtime stdout auditability; the five-dimension review found no Blocker/Major. Action/Gateway, Dora, and robot motion remain deferred.

### Detailed changes

- `examples/forge-adapters/robotwin20/runtime/robotwin_backend.py:L18,L384-L412`: redirect simulator/runtime stdout noise to stderr and emit one machine-readable JSON document on stdout.
- `examples/forge-adapters/robotwin20/tests/test_robotwin_backend_contract.py:L79-L118`: add stdout/stderr contract coverage.
- `docs/forge/PAOS_STATE_FILE_ARCHITECTURE_DIAGNOSIS.md:L462-L483`, `docs/forge/STATE_FILE_IMPLEMENTATION_REVIEW_20260903.md:L509-L522`, `examples/forge-adapters/robotwin20/README.md:L227-L236`: record the run, intermediate perception artifacts, unavailable providers, motion flags, and final manifest digest.

### Validation

- Isolated adapter tests with explicit async plugin and dependency paths: `103 passed`; repository: `161 passed`; pick-place with required path and async plugin: `256 passed`.
- Ruff, compileall, and `git diff --check` passed.
- Run manifest: `/home/yanxu/robotwin20-runtime/artifacts/paos-real-chain-20260905T0020Z/run_manifest.json`, SHA-256 `da7a81bd2efccbf70312428a3adeef10babe2d465734f63f7c90444297389b46`; all motion flags are `false`.
- GraspGen (`GRASPGEN_PYTHON`) and readiness (`READINESS_FIXTURE`) are unavailable; no `object.acquire`/`object.place` was attempted.

## [v4.4.0] - 2026-09-04

固化独立 readiness worker 的 no-motion projection 为 adapter-local、不可变 canonical replay artifact；保持人工审核门禁，不进入真实 Action/Gateway wiring。

Persisted independently validated readiness worker no-motion projections as immutable adapter-local canonical replay artifacts; retained the manual-review gate and did not enter real Action/Gateway wiring.

### Validation

- Readiness/replay/process: `25 passed`; repository: `161 passed`; dependency-free adapter subset: `16 passed`; pick-place: `256 passed`.
- Ruff, compileall, and `git diff --check` passed. Artifact is not a PAOS EvidenceBundle or motion authorization.

## [v4.4.1] - 2026-09-04

回写 v4.4.0 readiness replay artifact 实现提交哈希 `a2f972a`；没有修改实现、测试或执行顺序。

Recorded the v4.4.0 readiness replay artifact implementation commit hash `a2f972a`; implementation, tests, and execution order were unchanged.

## [v4.3.4] - 2026-09-04

回写 v4.3.3 readiness calibration identity 修复提交哈希 `20c6ad6`；没有修改实现、测试或执行顺序。

Recorded the v4.3.3 readiness calibration-identity fix commit hash `20c6ad6`; implementation, tests, and execution order were unchanged.

## [v4.3.3] - 2026-09-04

修复 readiness replay 中 calibration identity 未完整绑定的问题；fixture、request、manifest 现在三方一致校验。

Fixed incomplete calibration identity binding in readiness replay; fixture, request, and manifest now require three-way consistency.

### Validation

- Readiness/replay/process: `34 passed`; dependency-free adapter subset: `44 passed`.
- Ruff, compileall, and `git diff --check` passed.

## [v4.3.2] - 2026-09-04

回写 v4.3.1 日志维护提交哈希 `8833784`；没有修改实现、测试或执行顺序。

Recorded the v4.3.1 changelog-maintenance commit hash `8833784`; implementation, tests, and execution order were unchanged.

## [v4.3.1] - 2026-09-04

回写 v4.3.0 readiness evidence manifest 实现提交哈希 `23364de`；没有修改实现、测试或执行顺序。

Recorded the v4.3.0 readiness evidence-manifest implementation commit hash `23364de`; implementation, tests, and execution order were unchanged.

## [v4.3.0] - 2026-09-04

完成 readiness replay evidence manifest 的 no-motion 绑定校验，并按架构集成、失败路径、权威边界、配置、可维护性五个维度复审通过。

Implemented no-motion binding validation for the readiness replay evidence manifest and passed review across architecture integration, failure paths, authority boundaries, configuration, and maintainability.

### Detailed changes

- `examples/forge-adapters/robotwin20/runtime/readiness_replay_worker.py`: strict hash-pinned evidence manifest validation for candidate-set, calibration, source, and timezone-aware capture timestamps.
- `examples/forge-adapters/robotwin20/src/robotwin20_adapter/readiness_profile.py`: external manifest path, permission, digest, and duplicate-argument gates.
- `examples/forge-adapters/robotwin20/tests/test_readiness_replay.py`, `profiles/robotwin20/readiness-replay.yaml`: manifest conformance and profile configuration.

### Validation

- Readiness/replay/process tests: `34 passed`; dependency-free adapter subset: `44 passed`; repository: `161 passed`; pick-place: `256 passed`.
- Ruff, compileall, and `git diff --check` passed.
- No real IK, collision engine, Action, Gateway, Dora, hardware, or motion path was started.

## [v4.2.1] - 2026-09-04

回写 v4.2.0 readiness replay 实现提交哈希 `103db24`；没有修改实现、测试或执行顺序。

Recorded the v4.2.0 readiness replay implementation commit hash `103db24`; implementation, tests, and execution order were unchanged.

## [v4.2.0] - 2026-09-04

完成 readiness evidence replay worker/profile 的 no-motion conformance，并按五个维度复审通过；保持 PAOS projection 和动作权限边界不变。

Implemented no-motion conformance for the readiness evidence replay worker/profile and passed the five-dimension review; PAOS projection and motion-authority boundaries remain unchanged.

### Detailed changes

- `examples/forge-adapters/robotwin20/runtime/readiness_replay_worker.py`: hash-pinned fixture replay with complete case identity matching and no-motion output.
- `examples/forge-adapters/robotwin20/src/robotwin20_adapter/readiness_profile.py`: fixture digest/path/permission gates and worker identity validation through the existing JSONL process boundary.
- Existing `PhyAgentOS/forge/capability_runtime/manipulation_prepare.py` mapping normalization remains the final PAOS owner.
- `examples/forge-adapters/robotwin20/tests/test_readiness_replay.py`, `profiles/robotwin20/readiness-replay.yaml`: replay and profile conformance coverage.
- `examples/forge-adapters/robotwin20/src/robotwin20_adapter/readiness.py`: expose explicit readiness adapter teardown for process-backed evaluators.

### Validation

- Replay/readiness/process tests: `28 passed`; dependency-free adapter subset: `38 passed`; repository: `161 passed`; pick-place: `256 passed`.
- Ruff, compileall, and `git diff --check` passed.
- Replay is protocol evidence only; no real IK, collision engine, Action, Gateway, Dora, hardware, or motion path was started.
- Full RoboTwin20 adapter collection remains environment-limited by optional `numpy` and missing pick-place source-path injection; this does not invalidate the dependency-free conformance subset.

## [v4.1.0] - 2026-09-04

完成 RoboTwin20 独立 `ReadinessEvaluator` conformance，并按五个维度复审通过；保持 provider-neutral、dry-run/no-motion。Hephaestus 仅作 clean-room 语义参考，未接入运行时代码。

Implemented the independent RoboTwin20 `ReadinessEvaluator` conformance and passed the five-dimension review; kept provider-neutral, dry-run/no-motion behavior. Hephaestus was used only as a clean-room semantic reference, with no runtime code integrated.

### Detailed changes

- `examples/forge-adapters/robotwin20/src/robotwin20_adapter/readiness.py`: strict request/result binding, evidence validation, evaluator isolation, and fail-closed adapter boundary.
- `PhyAgentOS/forge/capability_runtime/manipulation_prepare.py`: strict normalization of adapter mappings while preserving PAOS ownership of projection and `motion_authorized=false`.
- `examples/forge-adapters/robotwin20/tests/test_readiness.py`: readiness and PAOS integration conformance coverage.
- `examples/forge-adapters/robotwin20/README.md`, `docs/forge/STATE_FILE_IMPLEMENTATION_REVIEW_20260903.md`, `docs/forge/PAOS_STATE_FILE_ARCHITECTURE_DIAGNOSIS.md`: updated implementation order and reference boundary.

### Validation

- Readiness tests: `14 passed`; dependency-free adapter subset: `30 passed`; repository: `161 passed`; pick-place: `256 passed`.
- Ruff, compileall, and `git diff --check` passed.
- No real IK/collision engine, Action, Gateway, Dora, hardware, or motion path was started.

## [v4.1.1] - 2026-09-04

回写 v4.1.0 实现提交哈希；没有修改实现、测试或执行顺序。

Recorded the v4.1.0 implementation commit hash; implementation, tests, and execution order are unchanged.

- Commit: `4b6ab2b`
- Branch: `feature/long-horizon-workflow`

## [v4.1.2] - 2026-09-04

修正 readiness conformance 日志索引中的提交哈希说明；没有修改实现、测试或执行顺序。

Corrected the readiness conformance changelog index's commit-hash note; implementation, tests, and execution order are unchanged.

- Correct maintenance commit for v4.1.1: `68bacaf`
- Branch: `feature/long-horizon-workflow`

## [v4.0.0] - 2026-09-04

完成 `manipulation.prepare` candidate consumer 的协议加固，并按架构集成、失败路径、权威边界、配置、可维护性五个维度复审通过；保持 Query/no-motion。Hephaestus 仅作为 clean-room 行为参考，未接入其运行时代码。

Hardened the `manipulation.prepare` candidate consumer and passed review across architecture integration, failure paths, authority boundaries, configuration, and maintainability; kept Query/no-motion. Hephaestus was used only as a clean-room behavioral reference, with no runtime code integrated.

### Detailed changes

- `PhyAgentOS/forge/capability_runtime/manipulation_prepare.py`: strict observation/candidate-set identity, duplicate prepared-candidate rejection, provider request isolation, and fail-closed readiness projection.
- `examples/forge-skills/pick-place-workflow/tests/test_manipulation_prepare.py`: revision/frame drift, provider mutation, and duplicate-candidate regression coverage.
- `docs/forge/STATE_FILE_IMPLEMENTATION_REVIEW_20260903.md`, `docs/forge/PAOS_STATE_FILE_ARCHITECTURE_DIAGNOSIS.md`: implementation status, five-dimension review, execution order, and Hephaestus reference boundary.

### Validation

- Manipulation-prepare tests: `60 passed`; repository tests: `161 passed`; pick-place tests: `256 passed`.
- Ruff, compileall, and `git diff --check` passed.
- No real IK, collision engine, Gateway, Dora, Action executor, hardware, or motion path was started.

## [v4.0.1] - 2026-09-04

回写 v4.0.0 实现提交哈希；没有修改实现、测试或执行顺序。

Recorded the v4.0.0 implementation commit hash; implementation, tests, and execution order are unchanged.

- Commit: `385eb7a`
- Branch: `feature/long-horizon-workflow`

## [v3.10.8] - 2026-09-04

加固 `scene.understand` 对 `scene.observe` identity 与 artifact lineage 的消费边界，并按架构集成、失败路径、权威边界、配置、可维护性五个维度复审通过；保持 Query/no-motion。

Hardened `scene.understand` consumption of `scene.observe` identity and artifact lineage, passing review across architecture integration, failure paths, authority boundaries, configuration, and maintainability; kept Query/no-motion.

### Detailed changes

- `PhyAgentOS/forge/capability_runtime/understanding.py`: strict observation identity, unique artifact/provenance binding, frame consistency, and provider-request isolation.
- `examples/forge-skills/pick-place-workflow/tests/test_scene_understand.py`: binding, provenance, frame-drift, and mutation regression coverage.
- `docs/forge/STATE_FILE_IMPLEMENTATION_REVIEW_20260903.md`, `docs/forge/PAOS_STATE_FILE_ARCHITECTURE_DIAGNOSIS.md`: stage status and five-dimension review.

### Validation

- Scene-understand tests: `21 passed`; repository tests: `161 passed`; pick-place tests: `250 passed`.
- RoboTwin provider tests: `7 passed, 1 skipped`; Ruff, compileall, and `git diff --check` passed.
- Real model, Gateway/Dora, Action executor, and hardware remain deferred.
- Commit: `2ba3a21` on `feature/long-horizon-workflow`.

## [v3.11.0] - 2026-09-04

加固 `grasp.propose` 对 `scene.understand` geometry artifact 的消费，并按五个维度复审通过；保持 Query/no-motion。

Hardened `grasp.propose` consumption of `scene.understand` geometry artifacts and passed the five-dimension review; kept Query/no-motion.

### Detailed changes

- `PhyAgentOS/forge/capability_runtime/grasp_proposal.py`: strict identity/provenance validation and isolated provider request.
- `examples/forge-skills/pick-place-workflow/tests/test_grasp_propose.py`: binding, provenance, and mutation regressions.
- `docs/forge/STATE_FILE_IMPLEMENTATION_REVIEW_20260903.md`, `docs/forge/PAOS_STATE_FILE_ARCHITECTURE_DIAGNOSIS.md`: stage status and review.

### Validation

- Grasp proposal tests: `61 passed`; repository: `161 passed`; pick-place: `253 passed`.
- Adapter GraspGen live tests remain blocked by missing optional `numpy`; no live checkpoint claim.
- Commit: `88267b4` on `feature/long-horizon-workflow`.

## [v3.10.2] - 2026-09-04

完成 EnvironmentAdapter/provider-neutral `scene.observe` 核心 seam，并按架构集成、失败路径、权威边界、配置、可维护性五个维度复审通过；保持 no-motion，不连接真实机器人、Dora 或硬件。

Completed the EnvironmentAdapter/provider-neutral `scene.observe` core seam and passed review across architecture integration, failure paths, authority boundaries, configuration, and maintainability; kept no-motion with no real robot, Dora, or hardware connected.

### Detailed changes

- `PhyAgentOS/forge/capability_runtime/observation.py`: explicit provider-neutral ToolSpec, strict observation projection, injected clock, and fail-closed provider/sensor errors.
- `PhyAgentOS/forge/capability_runtime/__init__.py`, `examples/forge-adapters/robotwin20/src/robotwin20_adapter/adapter.py`: core export and sanitized adapter boundary.
- `tests/test_environment_adapter_observation.py`: observation contract, failure, and explicit registration coverage.
- `docs/forge/STATE_FILE_IMPLEMENTATION_REVIEW_20260903.md`, `docs/forge/PAOS_STATE_FILE_ARCHITECTURE_DIAGNOSIS.md`, `docs/forge/ROBOTWIN_ADAPTER_REFACTOR_DIAGNOSIS.md`: stage status and five-dimension review.

### Validation

- Repository tests: `161 passed`; observation seam: `10 passed`; RoboTwin dependency-free subset: `16 passed`.
- Ruff, compileall, and `git diff --check` passed.
- Full RoboTwin runtime, real Gateway/Dora, geometry consumer, Action executor, and hardware remain deferred.
- Commit: `c46a35a` on `feature/long-horizon-workflow`.
- Follow-up adapter failure-path fix: `69c00d7` on `feature/long-horizon-workflow`.

## [v3.10.0] - 2026-09-04

完成 provider-neutral 抓取放置协议级证据闭环，并按架构集成、失败路径、权威边界、配置、可维护性五个维度复审通过；不连接真实 Action executor、Dora、机器人或硬件。

Completed the provider-neutral protocol-level pick-and-place evidence closure and passed review across architecture integration, failure paths, authority boundaries, configuration, and maintainability; no real Action executor, Dora, robot, or hardware connected.

### Detailed changes

- `examples/forge-skills/pick-place-workflow/src/pick_place_workflow/long_horizon.py:L24-L27,L78-L89,L194-L231,L301-L316`: terminal-response ref extraction, strict acquire identity equality, destination schema, and post-release evidence gate.
- `examples/forge-skills/pick-place-workflow/tests/test_long_horizon.py:L59-L70,L123-L145`: binding-drift, evidence-missing, and terminal-response replay coverage.
- `docs/forge/STATE_FILE_IMPLEMENTATION_REVIEW_20260903.md`, `docs/forge/PAOS_STATE_FILE_ARCHITECTURE_DIAGNOSIS.md`: stage status and five-dimension review.

### Validation

- Repository tests: `151 passed`; pick-place tests: `245 passed`.
- Ruff, compileall, and `git diff --check` passed.
- Real physical execution and autonomous-evolution promotion remain deferred.
- Commit: `a847cd7` on `feature/long-horizon-workflow`.

## [v3.9.0] - 2026-09-04

完成 Gateway/Dora provider-neutral 无动作 wiring，并按架构集成、失败路径、权威边界、配置、可维护性五个维度完成审查；不连接真实 Dora、Gateway、Action 或硬件。

Completed provider-neutral no-motion Gateway/Dora wiring and reviewed it across architecture integration, failure paths, authority boundaries, configuration, and maintainability; no real Dora, Gateway, Actions, or hardware connected.

### Detailed changes

- `PhyAgentOS/forge/capability_runtime/http_transport.py:L1-L95`: reusable HTTP Gateway transport over `CapabilityRuntime`.
- `PhyAgentOS/forge/capability_runtime/runtime.py:L57-L70,L180-L223,L260-L313`: deadline/unknown and cancel/stop terminal reconciliation; Session timeout rejection.
- `tests/test_gateway_dora_no_motion_conformance.py:L1-L117`: discovery, identity, lifecycle, malformed JSON, cancellation, timeout, and no-POST conformance.
- `docs/forge/STATE_FILE_IMPLEMENTATION_REVIEW_20260903.md`, `docs/forge/PAOS_STATE_FILE_ARCHITECTURE_DIAGNOSIS.md`: five-dimension acceptance and execution-order clarification.

### Validation

- Repository tests: `150 passed`; pick-place tests: `243 passed`; conformance subset: `11 passed`.
- Ruff, compileall, and `git diff --check` passed.
- Real Dora/Gateway, Action executor, hardware motion, pick-place closure, and autonomous-evolution promotion remain deferred.
- Commit: `dd1ee70` on `feature/long-horizon-workflow`.
- Follow-up log commit: `83185bc`.

## [v3.8.3] - 2026-09-04

完成完整 `gpt-5.6-sol/high` held-out + hazard 真实模型语义评估并关闭 Verification 质量门禁；保留一个 replan/inconclusive 残余质量风险，不连接 Gateway、Dora、Action 或硬件。

Completed the full `gpt-5.6-sol/high` held-out + hazard real-model semantic evaluation and closed the Verification quality gate; retained one replan/inconclusive residual quality risk, with no Gateway, Dora, Action, or hardware connected.

### Detailed changes

- `artifacts/evals/verification/20260904T034715.434600Z-42a21625/run_manifest.json`: full 7-case run bound to commit `2722d78d1f21d43f12c0213811376ee8f8bf57a8`, exact custom provider binding, and redacted file credential source.
- `artifacts/evals/verification/20260904T034715.434600Z-42a21625/metrics.json`: `quality_gate_eligible=true`, `quality_gate_passed=true`, contract/criterion/recovery-context `1.0`, false-positive rate `0`, overall verdict accuracy `0.8571428571428571`.
- `docs/forge/VERIFICATION_MODEL_EVALUATION.md`, `docs/forge/STATE_FILE_IMPLEMENTATION_REVIEW_20260903.md`, `docs/forge/PAOS_STATE_FILE_ARCHITECTURE_DIAGNOSIS.md`: recorded per-case review, residual replan error, and the next Gateway/Dora no-motion integration stage.

### Validation

- All 7 held-out/hazard cases completed; no credential or Bearer leakage found in artifacts.
- The held-out `replan_required` case was returned as `inconclusive` (`held_out` accuracy `0.75`), above the configured overall `0.8` threshold but retained as follow-up risk.
- Verification gate closure does not authorize physical execution, pick-place closure, or autonomous-evolution promotion.
- Commit: `bccdd6f` on `feature/long-horizon-workflow`.

## [v3.8.2] - 2026-09-04

回写 v3.8.1 实现提交 `9c1b955`，不修改实现或评估行为。

Recorded v3.8.1 implementation commit `9c1b955`; implementation and evaluation behavior were unchanged.

- Commit: `2722d78` on `feature/long-horizon-workflow`.

## [v3.8.1] - 2026-09-04

将独立 key 文件能力接入 `paos agent` 主配置，修正评估文档与日志中的当前状态，并验证 Agent 配置链路。

Wired the independent key-file capability into the `paos agent` main configuration, corrected the evaluation documentation and changelog state, and verified the Agent configuration path.

### Detailed changes

- `PhyAgentOS/config/credentials.py:L1-L48`: strict owner-only, non-symlink API-key-file reader.
- `PhyAgentOS/config/schema.py:L394-L417,L547-L612`, `PhyAgentOS/config/loader.py:L43-L52`, `PhyAgentOS/cli/commands.py:L285-L337,L1650-L1657`: `apiKeyFile` schema, config-path-relative resolution, runtime provider wiring, and status detection.
- `tests/test_config_api_key_file.py:L1-L52`: success, relative-path, dual-source, symlink, and permission regression tests.
- `README.md:L196-L200`, `docs/zh/04-forge-configuration-reference.md:L70-L76`, `docs/forge/VERIFICATION_MODEL_EVALUATION.md:L42-L101`: configuration and execution-order documentation.

### Validation

- `paos status`: `Custom: ✓`.
- No-tool `paos agent` connectivity check completed successfully with `gpt-5.6-sol/high`.
- Repository tests: `147 passed`; Ruff, compileall, and `git diff --check` passed.
- The LiteLLM SOCKS cost-map warning is non-fatal; no Gateway, Dora, Action, hardware, or motion path was started.
- Commit: `9c1b955` on `feature/long-horizon-workflow`.

## [v3.8.0] - 2026-09-04

接入 Verification 真实模型评估的独立 API key 文件，并完成 `gpt-5.6-sol/high` 单 case 连通性验证；同时保持完整 held-out + hazard 门禁、Gateway/Dora 和抓取放置闭环后置。

Added an independent API-key-file credential source for Verification real-model evaluation and completed a `gpt-5.6-sol/high` single-case connectivity check; full held-out + hazard gating, Gateway/Dora, and pick-place closure remain deferred.

### Detailed changes

- `PhyAgentOS/verification/evaluation.py:L6-L18,L137-L190,L254-L329,L514-L548`: strict file credential loading, redaction, and provider binding.
- `PhyAgentOS/verification/service.py:L64-L68`: explicit recovery-context field guidance in the production prompt.
- `evals/verification/evaluation_config_sol_high_v1.json:L1-L25`, `evals/verification/provider.sol_high.example.json:L1-L13`: versioned `custom`/`gpt-5.6-sol` `/v1` configuration with `allow_custom_provider=true` binding.
- `tests/test_verification_model_evaluation.py:L21-L22,L196-L207,L300-L413`, `tests/test_verifier_semantic_conformance.py:L10,L43-L49`: credential, prompt, and strict-schema regression coverage.
- `docs/forge/VERIFICATION_MODEL_EVALUATION.md:L42-L101`, `docs/forge/STATE_FILE_IMPLEMENTATION_REVIEW_20260903.md:L272-L285`: operating instructions and evidence boundaries.

### Validation

- `gpt-5.6-sol/high --max-cases 1`: completed with contract/verdict/criterion/recovery-context `1.0`; gate eligibility remains `false`.
- Full repository regression after the follow-up configuration wiring: `147 passed`; Ruff, compileall, and `git diff --check` passed.
- No Gateway, Dora, Action, hardware, or motion path was started.

## [v3.7.2] - 2026-09-04

回写 v3.7.1 审计维护提交；没有修改实现、评估配置、运行证据或执行顺序。

Recorded the v3.7.1 audit-maintenance commit; implementation, evaluation configuration, run evidence, and execution order are unchanged.

- Commit: `d88fd3a`
- Branch: `feature/long-horizon-workflow`

## [v3.7.1] - 2026-09-04

维护 v3.7.0 审计记录：回写实现提交，并把真实模型 blocker 更新为提交后的终态 preflight 产物；没有修改评估行为、阈值或执行顺序。

Maintained the v3.7.0 audit record by recording the implementation commit and updating the real-model blocker to the terminal post-commit preflight artifact; evaluation behavior, thresholds, and execution order are unchanged.

- Implementation commit: `8775073`
- Post-commit blocked run: `artifacts/evals/verification/20260903T163926.458050Z-db095983/`
- The manifest binds the run to full commit `8775073eccb26791a5ffd0215794c49fd46f3f82`; no model request or quality score was produced.

## [v3.7.0] - 2026-09-03

建立可复现的 Verification Service 真实模型语义质量评估基础设施，并在代码审查后关闭跨层依赖、非终态错误、fixture 身份冒充和部分 case 误过完整门禁的问题。真实模型凭据当前不可用，因此质量门禁保持 blocked；未连接 Gateway、Dora、Action 或硬件。

Established reproducible real-model semantic-quality evaluation infrastructure for Verification Service, then closed reverse-layer dependencies, non-terminal errors, fixture identity masquerading, and partial-case gate bypasses during code review. Real-model credentials remain unavailable, so the quality gate is blocked; no Gateway, Dora, Action, or hardware was connected.

### Detailed changes

- `PhyAgentOS/verification/evaluation.py:L1-L675`: adds strict dataset/config/provider schemas, immutable provider gate binding, unique UTC run directories, provenance/digests, production subprocess execution, fsynced per-attempt records, metrics, threshold decisions, and terminal blocked/error artifacts.
- `PhyAgentOS/verification/validation.py:L1-L34`, `PhyAgentOS/agent/session_verifier.py:L29-L32,L178-L192`: moves criteria/evidence-reference authority validation into the Verification layer while preserving the Agent-facing error contract.
- `PhyAgentOS/verification/request_builder.py:L35-L52,L389`: shares the production verification prompt envelope with the evaluator.
- `scripts/evaluate_verification_model.py:L1-L37`, `evals/verification/semantic_verifier_v1.json:L1-L299`, `evals/verification/evaluation_config_v1.json:L1-L23`, `evals/verification/provider.openai_codex.example.json:L1-L11`: adds the CLI, 10-case development/held-out/hazard corpus, thresholds, and credential-safe provider example.
- `tests/test_verification_model_evaluation.py:L1-L449`: covers strict loading, production subprocess fixture replay, credential blockers, terminal startup errors, provider identity binding, and partial-case ineligibility.
- `docs/forge/VERIFICATION_MODEL_EVALUATION.md:L1-L75`, `docs/forge/STATE_FILE_IMPLEMENTATION_REVIEW_20260903.md:L214-L250`, `docs/forge/PAOS_STATE_FILE_ARCHITECTURE_DIAGNOSIS.md:L315-L320`: records the quality/evaluation boundary and preserves the approved execution order.

### Key diff

```text
Before: fixture smoke and partial runs could self-declare real_model eligibility; evaluation reused an Agent-private validator; startup failure could leave a running manifest.
After:  a versioned non-custom provider identity and full case set are mandatory; validation is owned by Verification; every blocked/error path writes terminal fail-closed artifacts.
```

### Validation

- Verification/evaluation focused suite: `57 passed`.
- Repository suite: `136 passed`.
- Pick-place workflow and RoboTwin adapter suites: `310 passed` using the existing PAOS packages plus system NumPy; the unmodified PAOS environment alone currently lacks NumPy.
- Ruff, compileall, `git diff --check`, reverse-dependency scan, and credential/artifact review passed.
- Real-model preflight remains blocked by unavailable Codex OAuth credentials; fixture metrics are explicitly not quality-gate evidence.

Git commit: `8775073` on `feature/long-horizon-workflow`.

## [v3.6.0] - 2026-09-03

完成真实 `VerificationServiceProcess` provider-spec 子进程门禁：父进程启动正式子进程，独立 OpenAI-compatible HTTP stub 验证配置传递、私有 readiness、鉴权请求、结构化 verdict、provider 失败、超时和 stop 清理；未连接外部模型、Gateway、Watchdog、Action 或硬件。

Completed the production `VerificationServiceProcess` provider-spec subprocess gate: the parent starts the formal child process, and an independent OpenAI-compatible HTTP stub verifies config transfer, private readiness, authenticated requests, structured verdicts, provider failure, timeout, and stop cleanup; no external model, Gateway, Watchdog, Action, or hardware was connected.

### Detailed changes

- `PhyAgentOS/verification/service.py:L28,L282-L314,L405-L418`: added a stable service identifier and token-protected `/readyz` readiness probe with strict JSON/service identity checks; retained `/healthz` as liveness.
- `tests/test_verification_service_process.py:L1-L230`: covers formal subprocess startup, provider-spec propagation, external HTTP provider stub, failure/timeout mapping, readiness authentication, and process cleanup.
- `docs/forge/STATE_FILE_IMPLEMENTATION_REVIEW_20260903.md:L161-L212`: records implementation review, validation evidence, and remaining gates.

### Validation

- Repository tests: `127 passed`.
- Pick-place example tests: `241 passed`.
- Ruff, compileall, and `git diff --check` passed.
- Real-model semantic quality, Gateway/Dora wiring, and pick-place closure remain pending.

Git commit: `cfef665` on `feature/long-horizon-workflow`.

## [v3.6.1] - 2026-09-03

维护 v3.6.0 实现提交日志，记录 provider-spec 子进程门禁提交 hash。

Maintained the v3.6.0 implementation log and recorded the provider-spec subprocess gate commit hash.

Git commit: `cfef665` on `feature/long-horizon-workflow`.

## [v3.5.2] - 2026-09-03

维护提交日志：回写 v3.5.0/v3.5.1 的实现提交 hash，并核对当前分支。

Commit-log maintenance: recorded the implementation commit hash for v3.5.0/v3.5.1 and verified the current branch.

- Implementation commit: `e4cdac5`
- Branch: `feature/long-horizon-workflow`

## [v3.5.1] - 2026-09-03

完成第三轮五维代码审查并修复 Store、状态协议和 Verification HTTP 边界；未启动真实 provider、外部模型、Gateway、Action 或硬件。

Completed the third five-dimension code review and fixed Store, state-protocol, and Verification HTTP boundaries; no real provider, external model, Gateway, Action, or hardware was started.

Git commit: `e4cdac5` on `feature/long-horizon-workflow`.

### Detailed changes

- `PhyAgentOS/forge/task.py:L83-L125,L182-L262,L381-L411,L417-L463,L571-L586`：finite execution/event payload、完整聚合关系校验、create/update pre-commit validation、`task_id`/`created_at`/origin identity immutability。
- `PhyAgentOS/state_io/protocol.py:L31-L55,L140-L155`：JSON/YAML duplicate-key rejection。
- `PhyAgentOS/verification/service.py:L33-L51,L197-L239,L341-L351,L372-L421`：strict JSON decoding and strict parent constructor types。
- `tests/test_state_file_authority_boundaries.py`、`tests/test_state_file_adapter.py`、`tests/test_verification_service_replay.py`、`tests/test_verification_service_config.py`：真实边界回归覆盖。
- `docs/forge/STATE_FILE_IMPLEMENTATION_REVIEW_20260903.md:L117-L176`：第三轮 review 记录。

### Validation

- Repository tests: `123 passed`.
- Pick-place example tests: `241 passed`.
- Ruff, compileall, and `git diff --check` passed.
- Provider-spec production subprocess, real-model semantic quality, and pick-place closure remain pending.

## [v3.5.0] - 2026-09-03

完成状态文件适配、Evidence、Verifier 与 Verification Service 的边界修复，并完成第二轮代码审查；未启动真实 provider 子进程、外部模型、Gateway、Watchdog、Action 或硬件。

Completed boundary fixes for state-file adapters, Evidence, Verifier, and Verification Service, followed by a second code review; no real provider subprocess, external model, Gateway, Watchdog, Action, or hardware was started.

### Detailed changes

- `PhyAgentOS/forge/task.py:L45-L56,L190-L244,L286-L361,L393-L445,L1193-L1240`：AgentTask approval binding、SQLite origin migration/backfill/index、immutable origin、full aggregate revalidation、terminal retention wiring。
- `PhyAgentOS/state_io/adapters.py:L275-L322,L390-L405,L429-L510,L548-L632`：strict TARGETS/SESSIONS schema、bounded promotion、dedup exception handling。
- `PhyAgentOS/forge/evidence.py:L31-L115,L118-L152,L165-L244,L301-L350,L570-L583`：v2 manifest、writer-owned path、pre-write immutability、strict robot-state JSON、stable bundle identity。
- `PhyAgentOS/verification/request_builder.py:L27-L32,L198-L227,L253-L318`：AgentTask Bundle binding, same-bundle evidence ownership, strict structured JSON and unique paths。
- `PhyAgentOS/verification/service.py:L56-L206,L345-L418`、`PhyAgentOS/config/schema.py:L341-L361`：shared provider/service schema and stable HTTP errors。
- `PhyAgentOS/state_io/__init__.py`：移除无生产 owner 的 generic SKILLRUNTIME/LESSONS renderer 公共导出。
- `tests/test_state_file_authority_boundaries.py:L1-L476`：真实 Store/writer/request/context/retention 边界审查覆盖。
- `docs/forge/STATE_FILE_IMPLEMENTATION_REVIEW_20260903.md:L1-L176`：完整审查发现、修复记录和三轮五维复审结论。

### Key diff

```text
Before: origin migration was incomplete; malformed evidence/provider failures could cross owner boundaries; generic renderers looked production-ready.
After:  origins migrate and remain immutable; evidence/provider requests fail closed; only owned projections are represented as implemented.
```

### Validation

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -p pytest_asyncio.plugin -q tests` → `105 passed`.
- Pick-place example suite → `241 passed`.
- Unguarded pytest is blocked before collection by the system ROS `launch_testing` plugin missing `lark`; validation isolates plugins and explicitly loads `pytest_asyncio.plugin`.
- Ruff, compileall, and `git diff --check` passed.
- Provider-spec production subprocess, real-model semantic quality, and pick-place closure remain pending.

## [v3.4.6] - 2026-09-03

增加 Verification Service HTTP replay/failure conformance：验证授权 token、请求 envelope、重复 replay、
deterministic provider verdict、invalid-response normalization 和 provider failure。测试仅使用进程内
provider，不启动生产验证子进程或连接外部模型。

Added Verification Service HTTP replay/failure conformance for authorization tokens, request envelopes, repeated
replay, deterministic provider verdicts, invalid-response normalization, and provider failures. Tests use only an
in-process provider and do not start the production verification subprocess or connect to external models.

### Detailed changes

- `tests/test_verification_service_replay.py:L1-L117` adds HTTP handler/engine replay and failure tests.
- `docs/forge/PAOS_STATE_FILE_ARCHITECTURE_DIAGNOSIS.md:L285-L296` records service-level conformance and remaining provider-spec/real-model gates.
- `docs/forge/STATE_FILE_ADAPTER_FEATURE_CARD.md:L60-L63` records Verification Service HTTP conformance coverage.

### Key diff

```text
Before: verifier checks were tested locally, but the HTTP service boundary had no deterministic replay matrix.
After:  the real handler + VerificationEngine path validates auth, request schema, normalization, replay, and failure propagation without external side effects.
```

### Validation

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests` → `58 passed`.
- Ruff, compileall, and `git diff --check` passed.
- No production Verification Service, external model, Gateway, Watchdog, Action, or motion authorization was used.

## [v3.4.5] - 2026-09-03

增加 ForgeTaskVerifier 本地 verdict contract conformance：success/replan 不变量、criteria 精确绑定、
unknown evidence、malformed response 和 no-service 边界。该轮不启动 Verification Service，不调用模型或 Gateway。

Added local ForgeTaskVerifier verdict contract conformance for success/replan invariants, exact criterion binding,
unknown evidence, malformed responses, and the no-service boundary. This iteration does not start the Verification
Service or call a model or Gateway.

### Detailed changes

- `tests/test_verifier_semantic_conformance.py:L1-L126` adds deterministic verifier acceptance/rejection tests.
- `docs/forge/PAOS_STATE_FILE_ARCHITECTURE_DIAGNOSIS.md:L280-L290` distinguishes local verdict contract checks from provider-backed semantic quality.
- `docs/forge/STATE_FILE_ADAPTER_FEATURE_CARD.md:L59-L62` records local verifier conformance coverage.

### Key diff

```text
Before: verifier boundary tests covered projection-as-evidence rejection, but not the full verdict contract matrix.
After:  deterministic fixtures validate criteria/evidence/recovery invariants and malformed responses without starting a service.
```

### Validation

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests` → `54 passed`.
- Ruff, compileall, and `git diff --check` passed.
- No Verification Service, model, Gateway, Watchdog, Action, or motion authorization was used.

## [v3.4.4] - 2026-09-03

校正执行顺序文档：明确 `SKILLRUNTIME.md`/`LESSONS.md` 是可选 projection，记录受限 promotion 先于
后续 replay conformance 的历史顺序，并确认抓取放置和自主进化尚未启动。未修改运行时代码。

Corrected execution-order documentation: `SKILLRUNTIME.md`/`LESSONS.md` are optional projections, the historical
ordering of bounded promotion before later replay conformance is recorded, and pick-place plus autonomous evolution
remain unstarted. No runtime code was changed.

### Detailed changes

- `docs/forge/ROBOTWIN_ADAPTER_REFACTOR_DIAGNOSIS.md:L400-L420` aligns required versus optional file adapters and records the bounded-promotion ordering review.
- `docs/forge/PAOS_STATE_FILE_ARCHITECTURE_DIAGNOSIS.md:L275-L283` distinguishes request-level Evidence conformance from remaining semantic/live replay work.

### Validation

- Documentation-only change; `git diff --check` passed.
- No Gateway, Watchdog, Action, AgentTask, or motion authorization was used.

## [v3.4.3] - 2026-09-03

增加 Evidence request-level conformance：不可变 Evidence Bundle 在跨工作区 replay 时重新校验
capture window、必需 kind/source、association、retention、digest/size、媒体类型和结构化 JSON。
该轮不修改 Verifier 语义权威逻辑，也不把 `ENVIRONMENT.md` 变成 Evidence。

Added Evidence request-level conformance: immutable Evidence Bundles are revalidated across workspace replay
for capture windows, required kind/source, association, retention, digest/size, media type, and structured JSON.
This iteration does not change Verifier semantic authority or turn `ENVIRONMENT.md` into Evidence.

### Detailed changes

- `tests/test_evidence_semantic_replay_conformance.py:L1-L184` adds immutable bundle replay and fail-closed request validation tests.
- `docs/forge/PAOS_STATE_FILE_ARCHITECTURE_DIAGNOSIS.md:L280-L287` records request-level Evidence conformance and its remaining limits.
- `docs/forge/STATE_FILE_ADAPTER_FEATURE_CARD.md:L59-L61` records Evidence request conformance coverage.

### Key diff

```text
Before: Evidence boundary had basic projection rejection but no dedicated replay matrix for request consumption.
After:  immutable bundle replay validates identity, window, policy, retention, digest/size, media, and structured data;
        LLM semantic verdict and live Gateway replay remain explicitly out of scope.
```

### Validation

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests` → `48 passed`.
- `PYTHONPATH=examples/forge-skills/pick-place-workflow/src python -m pytest -q examples/forge-skills/pick-place-workflow/tests` → `241 passed`.
- Ruff, compileall, and `git diff --check` passed.
- No real Gateway, Watchdog, Action, or motion authorization was used.

## [v3.4.2] - 2026-09-03

增加状态文件适配的 replay/failure conformance：跨工作区回放保持确定性，未知字段在触及 Store/Gateway
前 fail-closed，Store 编译失败不留下生命周期残留，projection drift 保留原内容，TARGETS/SESSIONS
继续保持 `motion_authorized=false`。`SKILLRUNTIME.md` 与 `LESSONS.md` producer 仍明确为可选 projection。

Added state-file adapter replay/failure conformance: cross-workspace replay remains deterministic, unknown fields
fail closed before Store/Gateway access, Store compilation failures leave no lifecycle residue, projection drift
preserves the prior content, and TARGETS/SESSIONS retain `motion_authorized=false`. `SKILLRUNTIME.md` and
`LESSONS.md` producers remain explicitly optional projections.

### Detailed changes

- `tests/test_state_file_replay_conformance.py:L1-L215` adds replay, Fake Store failure, Gateway no-call sentinel, drift-preservation, and no-motion tests.
- `docs/forge/PAOS_STATE_FILE_ARCHITECTURE_DIAGNOSIS.md:L280-L288` separates required Phase-B boundary conformance from optional Markdown projections.

### Key diff

```text
Before: replay/failure coverage was distributed across adapter tests without an explicit cross-workspace boundary.
After: dedicated conformance tests assert deterministic replay, no partial lifecycle state, drift preservation,
       and no-motion behavior while keeping Markdown non-authoritative.
```

### Validation

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests` → `43 passed`.
- `PYTHONPATH=examples/forge-skills/pick-place-workflow/src python -m pytest -q examples/forge-skills/pick-place-workflow/tests` → `241 passed`.
- Ruff, compileall, and `git diff --check` passed.
- No real Gateway, Watchdog, Action, or motion authorization was used.

## [v3.4.1] - 2026-09-03

增加 Verifier/Evidence boundary conformance：`ENVIRONMENT.md` projection 不能被解析为 Evidence Bundle，
verifier verdict 不能以 projection URI 冒充 evidence reference。未修改 Verifier 的事实源或语义判定逻辑。

Added Verifier/Evidence boundary conformance proving that an `ENVIRONMENT.md` projection cannot be parsed as an
Evidence Bundle and a verifier verdict cannot use a projection URI as an evidence reference. No verifier fact
source or semantic decision logic was changed.

### Detailed changes

- `tests/test_verifier_evidence_boundary.py:L1-L59` adds projection-as-evidence rejection and unknown projection-reference verdict tests.
- `docs/forge/PAOS_STATE_FILE_ARCHITECTURE_DIAGNOSIS.md:L271-L283` records the completed boundary conformance and remaining full semantic/replay work.

### Validation

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests` → `38 passed`.
- Ruff, compileall, and `git diff --check` passed.
- No Gateway, Watchdog, Action, AgentTask, or motion authorization was produced.

## [v3.4.0] - 2026-09-03

增加 `ForgeEvidenceWriter` 到 `EnvironmentProjectionProducer` 的受限关联。writer 校验自身生成的
before/after manifest、phase 和路径，生成稳定 opaque `evidence://` reference，并拒绝同一 phase 的
不同内容覆盖；producer 可自动注入 phase/reference 并拒绝不匹配值。Evidence/Verifier 仍是权威，未增加
Gateway、Watchdog、Action、AgentTask 或运动路径。

Added a bounded association from `ForgeEvidenceWriter` to `EnvironmentProjectionProducer`. The writer validates
its before/after manifests, phase, and path, derives a stable opaque `evidence://` reference, and rejects content
replacement within a phase. The producer injects phase/reference or rejects mismatches. Evidence/Verifier remain
authoritative; no Gateway, Watchdog, Action, AgentTask, or motion path was added.

### Detailed changes

- `PhyAgentOS/forge/evidence.py:L27-L143` adds writer-owned snapshot identity validation, stable evidence URI derivation, and same-phase immutability checks.
- `PhyAgentOS/forge/environment_projection.py:L30-L237` adds `publish_from_evidence_writer()` and the minimal `EvidenceSnapshotStore` seam.
- `PhyAgentOS/forge/__init__.py:L3-L33` exports the evidence association protocol.
- `tests/test_environment_projection_producer.py:L1-L194` covers manifest association, stable URI, overwrite rejection, phase/reference mismatch, and non-writer paths.
- `docs/forge/PAOS_STATE_FILE_ARCHITECTURE_DIAGNOSIS.md:L265-L278` and `docs/forge/STATE_FILE_ADAPTER_FEATURE_CARD.md:L27-L71` record the completed association and remaining Phase-B work.

### Validation

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests` → `36 passed`.
- `PYTHONPATH=examples/forge-skills/pick-place-workflow/src python -m pytest -q examples/forge-skills/pick-place-workflow/tests` → `241 passed`.
- Ruff, compileall, and `git diff --check` passed.
- Full RoboTwin collection remains environment-limited by missing `numpy`/package path; no motion or live verifier run.

## [v3.3.0] - 2026-09-03

增加受限 `EnvironmentProjectionProducer`：从已捕获的 `ObservationSnapshot` 和显式 provenance 生成严格
`ENVIRONMENT.md` projection；before/after 快照必须绑定 `evidence://` URI，可选地与
`EnvironmentAdapter.snapshot()` 的 scene revision 一致性校验。producer 只做原子 projection 写入，
不调用 Gateway、Watchdog、Action，不创建 AgentTask，也不替代 Evidence/Verifier 事实源。

Added a bounded `EnvironmentProjectionProducer` that renders a strict `ENVIRONMENT.md` projection from an
already captured `ObservationSnapshot` and explicit provenance. Before/after snapshots must use an `evidence://`
URI and can be revision-bound to `EnvironmentAdapter.snapshot()`. The producer only performs atomic projection
writes; it does not call Gateway, Watchdog, or Action, create AgentTasks, or replace Evidence/Verifier authority.

### Detailed changes

- `PhyAgentOS/forge/environment_projection.py:L1-L180` adds the producer input contract, adapter revision binding, evidence URI gate, and no-side-effect projection path.
- `PhyAgentOS/forge/__init__.py:L3-L31` exports the producer API.
- `PhyAgentOS/state_io/adapters.py:L553-L601` forwards optional `expected_sha256` to the atomic projection writer.
- `tests/test_environment_projection_producer.py:L1-L144` covers before/after success, idempotency, drift, invalid/empty input, evidence URI, adapter revision, and no-capture boundaries.
- `docs/forge/PAOS_STATE_FILE_ARCHITECTURE_DIAGNOSIS.md:L256-L273` and `docs/forge/STATE_FILE_ADAPTER_FEATURE_CARD.md:L27-L71` record the producer boundary and remaining Phase-B work.

### Validation

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests` → `33 passed`.
- Ruff, compileall, and `git diff --check` passed.
- No live pick-place provider, Gateway invocation, AgentTask, Evidence verdict, or motion authorization was produced.

## [v3.2.0] - 2026-09-03

完成 `ENVIRONMENT.md` 的严格 projection 适配：增加 snapshot/provenance schema、revision 一致性校验，
将 SceneGraph 查询从宽松 loader 切换为严格 parser，并同步模板。缺失、旧版或损坏文件现在返回 bounded
error；Evidence snapshot 仍是唯一语义事实源，未接入动作、Watchdog、Gateway 或硬件。

Completed strict `ENVIRONMENT.md` projection adaptation with snapshot/provenance schema and revision consistency
checks, switched SceneGraph queries from the permissive loader to the strict parser, and aligned the template.
Missing, legacy, or damaged files now return a bounded error. Evidence snapshots remain the sole semantic authority;
no Action, Watchdog, Gateway, or hardware path was added.

### Detailed changes

- `PhyAgentOS/state_io/adapters.py:L88-L148,L330-L344,L563-L574` adds the strict environment schema, parser, and renderer validation.
- `PhyAgentOS/agent/tools/scene_graph.py:L11-L63` consumes only valid environment projections and rejects malformed input.
- `PhyAgentOS/templates/ENVIRONMENT.md:L1-L34` aligns the template with `paos.state-file.v1`.
- `tests/test_state_file_adapter.py:L264-L335,L406-L414` covers provenance, revision, legacy, and fail-closed behavior.

### Validation

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests` → `26 passed`.
- `ruff check ...`, `python -m compileall ...`, and `git diff --check` passed.

## [v3.1.1] - 2026-09-03

完成最近三个 `TARGETS.md` candidate 功能的代码审查与测试。修复 `profile_id` 可包含路径分隔符的问题，
并补充审批 decision/时间戳、非法 profile、baseline 差异批准、输入文件不变和 no-motion 测试。

Completed code review and testing for the three recent `TARGETS.md` candidate features. Fixed path-like
`profile_id` identities and added coverage for approval decision/timestamp, invalid profiles, explicit baseline
differences, input immutability, and no-motion behavior.

### Detailed changes

- `PhyAgentOS/state_io/adapters.py:L180-L190` now rejects path-unsafe `profile_id` values.
- `tests/test_state_file_adapter.py:L82-L180` adds the review and failure-path tests; 18 focused tests pass.
- `docs/forge/STATE_FILE_ADAPTER_FEATURE_CARD.md:L50-L56` and `docs/forge/PAOS_STATE_FILE_ARCHITECTURE_DIAGNOSIS.md:L246-L255` record the review result and remaining Minor risk.

### Validation

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_state_file_adapter.py` → `18 passed`.
- `ruff check ...`, `python -m compileall ...`, and `git diff --check` passed.

## [v3.1.0] - 2026-09-03

新增 `TARGETS.md` 的已验证 Capability Profile candidate：候选必须通过严格 shadow validation，并由
`TargetProfileApproval` 同时绑定源文件 digest 与 baseline digest。candidate 仅用于比较和回放，固定
`motion_authorized=false`，不写 Runtime/Profile 权威配置，不改变 Action admission 或运动限幅。

Added a validated Capability Profile candidate for `TARGETS.md`: candidates must pass strict shadow validation
and carry a `TargetProfileApproval` bound to both source and baseline digests. Candidates are limited to comparison
and replay, always expose `motion_authorized=false`, and cannot write Runtime/Profile authorities or alter Action
admission or motion limits.

### Detailed changes

- `PhyAgentOS/state_io/adapters.py:L24-L145,L253-L300` adds `TargetProfileApproval`, `TargetProfileCandidate`, and `promote_targets_candidate()`.
- `PhyAgentOS/state_io/__init__.py:L3-L42` exports the bounded candidate API.
- `tests/test_state_file_adapter.py:L61-L130` covers approved candidates, baseline drift, and no-motion behavior.
- `docs/forge/STATE_FILE_ADAPTER_FEATURE_CARD.md:L24-L47` and `docs/forge/PAOS_STATE_FILE_ARCHITECTURE_DIAGNOSIS.md:L240-L247` document the non-admission boundary.

### Validation

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_state_file_adapter.py` → `15 passed`.
- `ruff check ...`, `python -m compileall ...`, and `git diff --check` passed.

## [v3.0.0] - 2026-09-03

在人工确认边界内提升 `SESSIONS.md` 输入：新增 digest 绑定审批凭据、单会话幂等编译器，并通过
`AgentTaskCoordinator.create_task()` 写入既有 AgentTask SQLite 事实源；新增 `parent_task_id` 与
`retry_limit` 声明式字段。编译前检查全局非终态任务，重复编译复用既有记录；不直接写 SQLite、不调度
Watchdog、不调用 Gateway、不授权运动。

Promoted `SESSIONS.md` within an explicit human-approval boundary: added digest-bound approval credentials,
single-session idempotent compilation, and writes through the existing `AgentTaskCoordinator.create_task()`
to the AgentTask SQLite authority. Added declarative `parent_task_id` and `retry_limit` fields. Compilation
checks the global non-terminal slot and reuses repeated source/session records; it does not write SQLite directly,
dispatch Watchdog, call Gateway, or authorize motion.

### Detailed changes

- `PhyAgentOS/state_io/adapters.py:L43-L372` adds approval validation, one-session compiler, stable origin identity, parent/active-task checks, and no-motion result semantics.
- `PhyAgentOS/forge/task.py:L153-L181,L300-L315,L420-L527` persists optional parent/retry metadata and adds origin-key lookup used for idempotency.
- `PhyAgentOS/state_io/__init__.py:L3-L39` exports the bounded promotion API.
- `tests/test_state_file_adapter.py:L207-L322` covers approval digest binding, idempotent reuse, active-task and multi-session conflicts, unknown parents, and no-motion.
- `docs/forge/STATE_FILE_ADAPTER_FEATURE_CARD.md:L6-L58` and `docs/forge/PAOS_STATE_FILE_ARCHITECTURE_DIAGNOSIS.md:L228-L244` record the promotion boundary and remaining non-goals.

### Validation

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_state_file_adapter.py` → `13 passed`.
- `ruff check PhyAgentOS/state_io PhyAgentOS/forge/task.py tests/test_state_file_adapter.py` passed.
- `python -m compileall -q PhyAgentOS/state_io PhyAgentOS/forge/task.py tests/test_state_file_adapter.py` and `git diff --check` passed.
- Existing pick-place task tests remain un-runnable in this environment because `pick_place_workflow` is not on `PYTHONPATH`; this is reported separately and is not treated as a pass.

## [v2.9.0] - 2026-09-03

新增 PAOS 状态文件架构诊断文档，汇总 `TARGETS.md`、`SKILLRUNTIME.md`、`SESSIONS.md`、
`ENVIRONMENT.md`、`LESSONS.md` 与现有 AgentTask、Gateway、Evidence、Runtime 和 Experience
权威边界的对应关系；明确 Markdown 不是事务性中间状态的唯一事实源，并提出“先冻结最小上层契约，
再继续抓取放置证据闭环，最后实现文件输入/投影适配”的审核方向。

Added the PAOS state-file architecture diagnosis documenting how `TARGETS.md`, `SKILLRUNTIME.md`,
`SESSIONS.md`, `ENVIRONMENT.md`, and `LESSONS.md` map to the existing AgentTask, Gateway, Evidence,
Runtime, and Experience authorities. It clarifies that Markdown is not the sole source of transactional
intermediate state and proposes “freeze the minimal upper-layer contract, continue the pick-place evidence
closure, then add file input/projection adapters” for review.

### Detailed changes

- `docs/forge/PAOS_STATE_FILE_ARCHITECTURE_DIAGNOSIS.md:L1-L240` adds the bilingual-domain diagnosis, authority table, Markdown input/projection protocol, pick-place impact analysis, autonomous-evolution boundaries, and six review gates.
- `docs/forge/ROBOTWIN_ADAPTER_REFACTOR_DIAGNOSIS.md:L390-L411` records the state-file protocol decision and preserves the provider-neutral pick-place implementation order.
- `docs/README.md:L29,L63` adds Chinese and English index links to the diagnosis.
- `changelog/2026-09_part2.md:L1-L61` records the detailed bilingual change, actual line ranges, key diffs, and validation in the split monthly archive.

### Validation

- `git diff --check` passed.
- Markdown headings, cross-document links, line references, and bilingual changelog entries were inspected.
- No source code, runtime behavior, or execution contract was changed by this documentation decision.

## [v2.9.1] - 2026-09-03

审核并确认“先做受限文件适配、后做抓取放置闭环”符合 PAOS 扩展原则。执行顺序调整为：冻结最小上层与文件契约，
实现只读 projection、`TARGETS.md` shadow validation、`SESSIONS.md` dry-run 及回放验证，人工确认后再提升输入边界，
最后推进抓取放置和受控自主进化。适配层不得拥有 Watchdog、AgentTask 生命周期、Gateway 或 Action admission，
也不得建立 Markdown queue Runtime。

Reviewed and confirmed that “restricted file adapters before the pick-place closure” conforms to PAOS extension principles.
The execution order now freezes the minimal upper-layer and file contracts, implements read-only projections,
`TARGETS.md` shadow validation, `SESSIONS.md` dry-runs, and replay validation, promotes inputs only after human approval,
and then advances pick-place and guarded evolution. Adapters do not own Watchdog, AgentTask lifecycle, Gateway, or Action
admission, and no Markdown queue Runtime is introduced.

### Detailed changes

- `docs/forge/PAOS_STATE_FILE_ARCHITECTURE_DIAGNOSIS.md:L162-L208,L249-L257` records the review conclusion and revised five-stage order.
- `docs/forge/ROBOTWIN_ADAPTER_REFACTOR_DIAGNOSIS.md:L398-L414` synchronizes the RoboTwin execution order and explicitly approves restricted file adapters first.
- `changelog/2026-09_part2.md:L55-L103` records the bilingual plan, actual changes, validation, and commit references.

### Validation

- `git diff --check` passed.
- PAOS extension principles were checked against ownership, provider-neutral boundary, no-second-protocol, projection authority, and no-motion requirements.
- No source code, runtime behavior, hardware IO, or motion authorization changed.

## [v2.10.0] - 2026-09-03

新增 PAOS State File Adapter 第一阶段实现：严格解析 `paos.state-file.v1` Markdown 结构化区块，提供原子 projection 写入、canonical digest drift 检查、`TARGETS.md` capability shadow validation、`SESSIONS.md` 确定性 dry-run 预览，并通过功能引用卡固定其非执行边界。该适配器不写入 AgentTask 生命周期、不调度 Watchdog、不调用 Gateway，也不授权运动。

Added the phase-one PAOS State File Adapter: strict `paos.state-file.v1` Markdown block parsing, atomic projection writes, canonical-digest drift checks, `TARGETS.md` capability shadow validation, and deterministic `SESSIONS.md` dry-run previews. The feature card fixes its non-execution boundary: it does not write AgentTask lifecycle state, schedule Watchdog work, call Gateway, or authorize motion.

### Detailed changes

- `PhyAgentOS/state_io/protocol.py:L1-L224` adds the strict envelope parser, opaque-reference metadata validation, canonical digest, atomic projection writer, and explicit drift error.
- `PhyAgentOS/state_io/adapters.py:L1-L214` adds target shadow validation, deterministic session previews, and projection entry points for Runtime, Environment, and Lessons.
- `PhyAgentOS/state_io/__init__.py:L1-L35` exports the bounded adapter API without adding a Gateway or Runtime route.
- `tests/test_state_file_adapter.py:L1-L198` covers valid/invalid envelopes, limits, drift, projection mode, deterministic dry-run, duplicate/unsafe identities, and no-motion flags.
- `docs/forge/STATE_FILE_ADAPTER_FEATURE_CARD.md:L1-L61` records the normative references, ownership, failure semantics, acceptance gates, and non-goals.
- `docs/forge/PAOS_STATE_FILE_ARCHITECTURE_DIAGNOSIS.md:L162-L228` records the phase-one implementation status and next promotion gate; `docs/README.md:L30,L65` indexes the feature card.

### Validation

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_state_file_adapter.py` → `9 passed`.
- `ruff check PhyAgentOS/state_io tests/test_state_file_adapter.py` passed.
- `python -m compileall -q PhyAgentOS/state_io tests/test_state_file_adapter.py` passed.
- `git diff --check` passed.
- No hardware, simulator, Gateway, Watchdog, AgentTask store, or motion path was invoked.

## [v2.8.17] - 2026-09-03

Implemented the provider-neutral grasp proposal extension: `grasp.propose`
targets may carry observation/revision/frame/calibration-bound geometry
artifacts, while the independent adapter resolves point clouds and invokes an
isolated GraspGen-compatible JSONL worker. Candidate matrices are validated,
converted to normalized pose/approach evidence, filtered with deterministic
SE(3) NMS, and returned with a reconciled funnel; no IK, collision admission,
or motion authorization is added.

实现 provider-neutral 抓取候选扩展：`grasp.propose` target 可携带绑定
observation/revision/frame/calibration 的几何资产；独立 adapter 解析点云并调用隔离的
GraspGen-compatible JSONL worker，校验候选矩阵、转换为归一化位姿/approach 证据，执行确定性
SE(3) NMS 并返回闭合 funnel；没有增加 IK、碰撞准入或运动授权。

### Detailed changes

- `PhyAgentOS/forge/capability_runtime/grasp_proposal.py:L34-L678` adds neutral geometry-artifact binding, mapping normalization, unit quaternion/approach validation, and strict fail-closed projection.
- `examples/forge-adapters/robotwin20/src/robotwin20_adapter/grasp_proposal.py:L1-L383` adds point-cloud resolution, isolated worker request/response mapping, candidate canonicalization, NMS, provenance, and cleanup handling.
- `examples/forge-adapters/robotwin20/runtime/graspgen_worker.py:L1-L129` and `runtime/worker_protocol.py:L12-L72` add the isolated worker entrypoint and versioned JSONL lifecycle.
- `examples/forge-adapters/robotwin20/src/robotwin20_adapter/grasp_profile.py:L1-L75` and `profiles/robotwin20/graspgen.yaml:L1-L29` keep interpreter, checkpoint, and filtering settings outside PAOS.
- `examples/forge-skills/pick-place-workflow/contracts/grasp.propose.tool.yaml:L1-L110` mirrors the public ToolSpec; tests cover mapping normalization, artifact binding, NMS, malformed worker data, and cleanup failure.

### Validation

- Generic PAOS grasp conformance: `57 passed`.
- Isolated adapter grasp/provider/profile tests: `7 passed`.
- Ruff, compileall, and `git diff --check` passed.
- Live GraspGen inference was not claimed: no verified local checkpoint/source environment was found; the worker reports unavailable until an external profile supplies them.
- `.codegraph/` and `.cursor/` remain untracked and are not staged.

## [v2.8.16] - 2026-09-03

Implemented the clean-room, adapter-side single-view perception composition:
semantic entity binding to LocateAnything proposals, bounded proposal-worker
shutdown, SAM2 box segmentation in its separate environment, deterministic
RGB-D localization, transactional derived artifacts, and projection through
the existing provider-neutral `scene.understand` Gateway contract. PAOS and
RoboTwin20 remain free of model-environment dependencies, and every result is
Query evidence with `motion_authorized=false`.

实现 clean-room、adapter-side 单视角感知 composition：语义实体绑定
LocateAnything proposal，关闭 proposal worker 后再在独立环境运行 SAM2 box
segmentation，然后确定性生成 RGB-D 定位和事务式派生资产，最终通过既有
provider-neutral `scene.understand` Gateway 契约投影。PAOS 和 RoboTwin20 不引入模型
环境依赖，所有结果仍是 `motion_authorized=false` 的 Query 证据。

### Detailed changes

- `PhyAgentOS/forge/capability_runtime/understanding.py:L461-L601` binds every derived artifact to the current request's observation, revision, frame, and calibration.
- `examples/forge-adapters/robotwin20/src/robotwin20_adapter/single_view_perception.py:L1-L707` composes proposal, segmentation, localization, artifact materialization, rollback, and ambiguity handling.
- `examples/forge-adapters/robotwin20/src/robotwin20_adapter/process_worker.py:L1-L212` and `perception_profile.py:L1-L153` add bounded JSONL process lifecycle and profile-only environment wiring.
- `examples/forge-adapters/robotwin20/runtime/locateanything_worker.py:L1-L242`, `sam2_worker.py:L1-L186`, and `worker_protocol.py:L1-L60` are adapter-owned entrypoints for the two existing isolated model environments.
- `examples/forge-adapters/robotwin20/profiles/robotwin20/perception.yaml:L1-L56` externalizes interpreters, model revision, checkpoint, CUDA device, caches, artifact roots, and timeouts.
- Adapter/workflow tests cover worker protocol failures, request binding, proposal ambiguity, mask/depth/calibration validation, artifact traversal and rollback, and the no-motion Gateway route.

### Validation

- PAOS/workflow/adapter suite: `281 passed, 2 skipped`; model-side tests skip because PAOS intentionally has no NumPy/Pillow.
- Isolated adapter numerical/worker suite: `27 passed`.
- Real no-motion composition on an existing RoboTwin RGB-D capture returned one LocateAnything proposal, an aligned SAM2 mask, 788 camera-frame points, all three derived artifacts, and `motion_authorized=false`; both worker processes exited.
- Ruff, compileall, and `git diff --check` passed. A system-Python whole-suite attempt was not accepted because that interpreter lacks PAOS `loguru` and asyncio test dependencies.
- `.codegraph/` and `.cursor/` remain untracked and are not staged.

## [v2.8.15] - 2026-09-03

Extended the provider-neutral `scene.understand` Query with auditable derived
perception artifacts for instance masks, object point clouds, and metric
localization. Every artifact is bound to the observation, scene revision,
entity, frame, calibration, source lineage, and root provenance; no Action or
motion authorization was added. The independent RoboTwin adapter forwards only
plain mappings and remains free of PAOS, simulator, Torch, and model imports.

扩展 provider-neutral `scene.understand` Query，增加可审计的实例 mask、目标点云和度量定位
派生资产。每个资产绑定 observation、scene revision、entity、frame、calibration、source
lineage 和 root provenance；没有增加 Action 或运动授权。独立 RoboTwin adapter 只转发普通
mapping，仍不依赖 PAOS、仿真器、Torch 或模型导入。

### Validation

- `268 passed` for the workflow and RoboTwin adapter suites.
- Ruff, compileall, ToolSpec YAML equality, and `git diff --check` passed.
- `.codegraph/` and `.cursor/` remain untracked and were not staged.

## [v2.8.14] - 2026-09-03

整理两条 provider-neutral 感知接入方案：单视角
`LocateAnything → SAM2 → RGB-D localization`，以及多视角
`MultiViewObservationSet → cross-view segmentation/identity/geometry fusion`。
明确多视角不是 RoboTwin Skill 或模型 Tool；融合实体几何可供
`scene.understand` / `grasp.propose`，Global SceneGeometry 仅作为独立可选输出，
所有结果仍须经过 PAOS provenance、frame/calibration 和 fail-closed 门禁。

Consolidated two provider-neutral perception paths: single-view
`LocateAnything → SAM2 → RGB-D localization`, and multi-view
`MultiViewObservationSet → cross-view segmentation/identity/geometry fusion`.
Clarified that multi-view is neither a RoboTwin Skill nor a model Tool; fused
entity geometry may feed `scene.understand` / `grasp.propose`, while Global
SceneGeometry remains a separate optional output under PAOS provenance,
frame/calibration, and fail-closed gates.

### Validation

- `git diff --check` passed.
- Execution document audit confirms no direct Agent-to-model/Dora/SDK path and no implicit camera motion.
- `.codegraph/` and `.cursor/` remain untracked and were not staged.

## [v2.8.13] - 2026-09-03

Fixed the GPT Responses strict JSON schema by declaring `spatial_envelopes.unit`
as a typed string const. Added recursive regression checks because the fake
Responses client does not validate request schemas. Updated the RoboTwin
adapter diagnosis and README to keep recognition, segmentation, metric
localization, grasp-pose proposal, readiness, and execution in their PAOS
use-case boundaries; the current GPT provider remains RGB semantic-only.

修正 GPT Responses strict JSON schema，为 `spatial_envelopes.unit` 补充
`type: string`，并增加递归回归校验，避免 Fake client 遗漏真实 API 的请求阶段错误。
同步更新 RoboTwin adapter 诊断与 README，明确识别、分割、度量定位、抓取位姿、准入和执行的
PAOS 用例归属；当前 GPT provider 仍只负责 RGB 语义理解。

### Validation

- `261 passed` for the adapter/workflow suites.
- Ruff, compileall, and `git diff --check` passed.
- `.codegraph/` and `.cursor/` remain untracked and were not staged.

## [v2.8.12] - 2026-09-03

Added an adapter-side `FilesystemArtifactResolver` for external RoboTwin
observation artifacts. It safely maps opaque RGB artifact references to files
under an explicitly external absolute root, rejects traversal/non-image refs,
and enables the GPT scene-understanding provider to consume real runtime
captures without exposing paths or assets to PAOS.

为外部 RoboTwin observation artifact 增加 adapter 侧 `FilesystemArtifactResolver`。它只在显式外部绝对根目录
下安全解析 opaque RGB artifact 引用，拒绝路径穿越和非图像 refs，使 GPT 场景理解 provider 能消费真实 runtime
capture，同时不向 PAOS 暴露本地路径或资产。

### Validation

- `260 passed in 2.62s` for the adapter/workflow suites.
- Ruff, compileall, and `git diff --check` passed.
- Complete `ForgeToolClient -> Fake Gateway -> generic endpoint -> RoboTwin provider -> GPT client` route is covered by a fake Responses client test.
- No live API call was attempted because `HEPHAESTUS_RELAY_API_KEY` remains absent; no real model result is claimed.
- `.codegraph/` and `.cursor/` remain untracked and were not staged.

## [v2.8.10] - 2026-09-02

Removed the duplicate provider-neutral `RoboTwinUnderstandingSnapshot` from
the adapter. The compatibility name now aliases PAOS's
`UnderstandingSnapshot`, so the adapter only translates inference inputs and
outputs while PAOS remains the sole owner of the public scene-understanding
snapshot contract.

移除 adapter 中重复的 provider-neutral `RoboTwinUnderstandingSnapshot`。兼容名称现在指向 PAOS 的
`UnderstandingSnapshot`，adapter 只负责 inference 输入/输出转换，PAOS 继续作为 scene-understand snapshot
公共契约的唯一所有者。

### Validation

- `251 passed` for the adapter/workflow suites.
- Ruff, compileall, and `git diff --check` passed.
- Provider-specific output remains fail-closed and the ForgeToolClient/Fake Gateway path is unchanged.

## [v2.8.9] - 2026-09-02

Moved the provider-neutral `manipulation.prepare` Query implementation into
the PAOS-owned generic capability runtime. The runtime owns candidate binding,
preparation identity, workspace/kinematic/collision check validation, evidence
projection, stale/empty/unavailable/invalid states, and the fixed
`motion_authorized: false` boundary. The Skill module is now a compatibility
export only; no robot, simulator, or model dependency was added.

将 provider-neutral `manipulation.prepare` Query 实现迁移到 PAOS 自有 generic capability runtime。运行时统一
持有候选绑定、preparation identity、workspace/kinematic/collision 检查校验、证据投影、
stale/empty/unavailable/invalid 状态以及固定的 `motion_authorized: false` 边界。Skill 模块仅保留兼容导出，
未加入机器人、仿真器或模型依赖。

### Validation

- `250 passed` for the adapter/workflow suites.
- Ruff, compileall, and `git diff --check` passed.
- `manipulation.prepare` remains read-only; no Action/Session/motion route is created.

## [v2.8.8] - 2026-09-02

Moved the provider-neutral `grasp.propose` Query implementation into the
PAOS-owned generic capability runtime. The runtime now owns the strict
ToolSpec, observation/frame/calibration binding, candidate and candidate-set
identity, funnel reconciliation, provenance validation, stale/empty/
unavailable/invalid states, and fail-closed provider error projection. The
Skill module is now a compatibility export only, and preparation imports the
shared candidate validator directly from PAOS. No YOLO, GraspGen, RoboTwin,
SAPIEN, Torch, Dora, or Hephaestus dependency was added.

将 provider-neutral `grasp.propose` Query 实现迁移到 PAOS 自有 generic capability runtime。运行时统一持有
严格 ToolSpec、observation/frame/calibration 绑定、候选与候选集身份、funnel 对账、provenance 校验、
stale/empty/unavailable/invalid 状态以及 provider 异常的 fail-closed 投影；Skill 模块仅保留兼容导出，
准备能力直接导入 PAOS 的候选校验器。未加入 YOLO、GraspGen、RoboTwin、SAPIEN、Torch、Dora 或 Hephaestus
依赖。

### Validation

- `249 passed` for the adapter/workflow suites.
- Ruff, compileall, and `git diff --check` passed.
- `grasp.propose` remains Query-only; no Action/Session/motion route is created.

## [v2.8.7] - 2026-09-02

Moved the provider-neutral `scene.understand` contract into the PAOS-owned
generic capability runtime. ToolSpec validation, observation/artifact binding,
scene-graph snapshot validation, stale rejection, provider error projection,
and Query result projection now live under
`PhyAgentOS.forge.capability_runtime.understanding`. The Skill module is only a
compatibility export; no Hephaestus, RoboTwin, SAPIEN, Torch, YOLO, Dora, or
motion dependency was added.

将 provider-neutral `scene.understand` 契约迁移到 PAOS 自有的 generic capability runtime。ToolSpec 校验、
observation/artifact 绑定、场景图 snapshot 校验、stale 拒绝、provider 错误投影和 Query 结果投影均由
`PhyAgentOS.forge.capability_runtime.understanding` 持有；Skill 模块仅保留兼容导出。未加入 Hephaestus、
RoboTwin、SAPIEN、Torch、YOLO、Dora 或运动依赖。

### Validation

- `248 passed in 2.64s` for adapter/workflow tests.
- Ruff, compileall, and `git diff --check` passed.
- Existing Skill imports remain compatible while resolving to the PAOS-owned implementation.

## [v2.8.6] - 2026-09-02

Added the independent RoboTwin adapter seam for the existing provider-neutral
`scene.understand` Query. `RoboTwinSceneUnderstandingProvider` accepts an
injected inference service, forwards only `scene.observe` identity/artifact
references, and rejects provider-specific fields. The generic endpoint now
projects provider failures as explicit `understanding_provider_error` results.
No detector/VLM/YOLO or simulator truth is included.

按 v1.0 扩展原则，在现有 provider-neutral `scene.understand` Query 后增加独立 RoboTwin adapter seam。
`RoboTwinSceneUnderstandingProvider` 只转发 `scene.observe` 身份与 artifact 引用，拒绝 provider 专有字段；
通用 endpoint 将 provider 异常投影为明确的 `understanding_provider_error` 结果。不包含检测器、VLM、YOLO
或仿真真值。

### Validation

- `248 passed in 2.65s` for adapter/workflow tests.
- Ruff, compileall, and `git diff --check` passed.
- No Action/Session/motion route or simulator/model import was added.

## [v2.8.5] - 2026-09-02

Unified Fake Gateway and RoboTwin `scene.observe` results behind the existing
`ForgeToolClient.invoke_query_tool` path. Added a runtime-only
`RoboTwinObservationProvider` that projects camera/depth/state captures into
provider-neutral observation identity, frame, calibration, freshness, and typed
artifact references. The adapter accepts either the external runtime capture
seam or the injected `RoboTwin20Adapter` seam; PAOS remains free of RoboTwin,
SAPIEN, Torch, and model imports. Relaxed the Fake Gateway artifact-reference
validator to accept capture subpaths, and added equality/integration tests.

通过既有 `ForgeToolClient.invoke_query_tool` 路径统一 Fake Gateway 与 RoboTwin 的 `scene.observe` 结果。
新增 runtime-only `RoboTwinObservationProvider`，将 camera/depth/state capture 投影为 provider-neutral 的
observation identity、frame、calibration、freshness 与 typed artifact refs；支持外部 runtime capture seam
和注入式 `RoboTwin20Adapter` seam。PAOS 仍不包含 RoboTwin、SAPIEN、Torch 或模型导入；Fake Gateway
artifact ref 校验支持 capture 子路径，并新增一致性集成测试。

### Validation

- `244 passed in 2.53s` for adapter/workflow tests.
- Ruff, compileall, and `git diff --check` passed.
- External RoboTwin20 `--format scene_observe` smoke returned the expected observation reference and RGB/depth/state artifacts; OIDN CUDA warnings remain a known runtime risk.
- `.codegraph/` and `.cursor/` remain untracked and were not staged.

## [v2.8.4] - 2026-09-02

Fixed the external RoboTwin runtime working-directory boundary in
`examples/forge-adapters/robotwin20/runtime/robotwin_backend.py:L88-L101,L119-L120,L179-L184,L208-L209,L223-L224`.
Official imports, `setup_demo`, `get_obs`, and `close_env` now run under the
runtime checkout and restore the caller's cwd. This removes the real smoke
failure caused by RoboTwin's relative `assets/objects/objaverse/list.json`
lookup when launched from the PAOS root. Added the regression test at
`tests/test_robotwin_backend_contract.py:L55-L65`.

修复独立 RoboTwin runtime 的工作目录边界：官方导入、场景初始化、观测读取和关闭均在外部 runtime checkout
上下文中执行并恢复调用方 cwd，消除从 PAOS 根目录启动时的相对资产路径错误。新增 cwd 回归测试；不改变
PAOS 依赖、ToolSpec 或动作权限。

## [v2.8.3] - 2026-09-02

Added the runtime-only `RoboTwinSensorBackend` at
`examples/forge-adapters/robotwin20/runtime/robotwin_backend.py:L1-L338` and
 contract tests at `tests/test_robotwin_backend_contract.py:L1-L77`. The backend
uses the official task's rendered RGB/depth and joint/end-effector state,
persists calibration and typed external artifacts, and injects through the
provider-neutral `RoboTwin20Adapter`. It rejects simulator truth channels and
never calls action/evaluator APIs. A real `beat_block_hammer/demo_clean` seed-0
capture produced 240x320 RGB/depth artifacts; SAPIEN OIDN CUDA warnings remain a
known runtime risk.

新增 runtime-only `RoboTwinSensorBackend`，通过 provider-neutral `RoboTwin20Adapter` 暴露真实 RGB/depth/state
artifact 与 calibration；不导出 actor/segmentation truth，不调用动作或 evaluator。真实 seed-0 capture 已验证，
但 OIDN CUDA warning 仍是运行时风险。

## [v2.8.2] - 2026-09-02

Added the standard-library fail-closed preflight at
`examples/forge-adapters/robotwin20/src/robotwin20_adapter/preflight.py:L1-L284`,
its tests at `tests/test_preflight.py:L1-L75`, and the `robotwin20-preflight`
entry point in `pyproject.toml:L1-L13`. The user-provided external RoboTwin20
environment passed all 16 checks (`ready=true`), including assets, CUDA
`sm_120`, SAPIEN, Vulkan, and task import, without modifying PAOS dependencies.

新增只使用标准库的 fail-closed preflight 与测试及 console entry point。用户提供的隔离 RoboTwin20 环境 16 项
检查全部通过（`ready=true`），包含官方 assets、CUDA `sm_120`、SAPIEN、Vulkan 与 task import；PAOS 依赖未被污染。

## [v2.8.1] - 2026-09-02

Verified the isolated `RoboTwin20` conda environment and checked out the official RoboTwin 2.0 source with
its pinned `XPolicyLab` submodule under `/home/yanxu/robotwin20-runtime/RoboTwin`. Confirmed the official asset
source is the Hugging Face dataset `TianxingChen/RoboTwin2.0`; only `embodiments.zip` was downloaded and verified.
The large `background_texture.zip` and `objects.zip` archives remain for the user to download. No PAOS dependency,
wheel content, ToolSpec, Hephaestus source, or tracked simulator asset was changed.

已核对隔离 `RoboTwin20` conda 环境，并将官方 RoboTwin 2.0 源码及固定的 `XPolicyLab` 子模块 checkout 到
`/home/yanxu/robotwin20-runtime/RoboTwin`。确认官方资产来源为 Hugging Face 数据集
`TianxingChen/RoboTwin2.0`；本次仅下载并校验 `embodiments.zip`，大型 `background_texture.zip` 与
`objects.zip` 留待用户自行下载。未修改 PAOS 依赖、wheel 内容、ToolSpec、Hephaestus 源码或已跟踪仿真资产。

### Validation

- `RoboTwin20` Python `3.10.21`; SAPIEN/Torch/TorchVision/OpenCV/Gymnasium/Open3D present.
- `embodiments.zip`: `219859313` bytes, SHA-256 `6b87d7d55e106d8ff25917e0538eb1e177fc549280e8a742a8cec3cb9f953fc6`.
- Official sizes: `background_texture.zip` `10970687027` bytes; `objects.zip` `3737778549` bytes.
- `.codegraph/` and `.cursor/` remain untracked and were not staged.

## [v2.8.0] - 2026-09-02

Implemented the first RoboTwin 2.0 adapter slice: an environment-owned lifecycle seam and sensor-only observation
source that can be connected to camera/depth/state outputs without importing RoboTwin into PAOS.

### Changed

- Added an independently packaged `robotwin20` adapter with explicit backend and sensor artifact protocols.
- Requires RGB/depth/state artifacts, frame, calibration, timestamp, and scene revision; rejects missing or
  simulator-ground-truth-only observations.
- Added no-motion tests; no YOLO, SAPIEN, robot SDK, Dora, or actuator dependencies were added to PAOS.

## [v2.7.0] - 2026-09-02

Implemented the simulator-free generic capability runtime foundation for the next integration phase.

### Changed

- Added reusable ToolEndpoint registration, discovery/context, Query dispatch, and bounded Action lifecycle
  primitives under `PhyAgentOS.forge`, with provider ports defined independently of RoboTwin, SAPIEN, YOLO,
  robot SDKs, and hardware.
- Added no-motion conformance tests and documented that this phase does not implement perception models or
  physical execution.

## [v2.6.3] - 2026-09-02

Corrected the documented extension order so the independent generic capability runtime is implemented before
any RoboTwin adapter work.

### Changed

- Added the simulator-free generic ToolEndpoint/provider-port phase to the bilingual user development guides.
- RoboTwin remains a profile-selected EnvironmentAdapter and simulation ground truth remains comparison-only.

## [v2.6.2] - 2026-09-02

Renamed the six-Tool workflow Skill to `pick-place-workflow` and corrected the RoboTwin perception boundary.

### Changed

- The Skill name now describes the complete observe → understand → propose → prepare → acquire → place workflow;
  the six stable Tool IDs are unchanged.
- PAOS v1.0 still requires an independent generic capability runtime. RoboTwin actor/entity truth, segmentation,
  object metadata, internal poses, and `check_success()` are simulation comparison/acceptance facts only; real
  deployment must use sensor artifacts and replaceable perception providers.
- Renamed `examples/forge-skills/scene-observe/` to `examples/forge-skills/pick-place-workflow/` and synchronized
  package imports, tests, manifest, and runtime discovery fixtures.

### Validation

- `220 passed`; `ruff check`; `compileall`; and `git diff --check` passed.
- No Dora, real Gateway server, RoboTwin, hardware, or motion route was started.

## [v2.6.1] - 2026-09-02

Saved and reviewed the RoboTwin adapter refactor diagnosis, separating reusable capability runtime semantics
from environment-specific adapters.

### Added

- Added `docs/forge/ROBOTWIN_ADAPTER_REFACTOR_DIAGNOSIS.md` with ownership boundaries, six-Tool migration seams,
  clean-room reimplementation rules, profile strategy, and acceptance gates.

### Changed

- Added diagnosis links to the Forge contract and documentation index.

### Security

- Documentation-only change; no Hephaestus, PAOS runtime, Gateway implementation, simulator, hardware, or motion path changed.

## [v2.6.0] - 2026-09-02

Clarified the v1.0 PAOS boundary for simulator integration and corrected the RoboTwin execution order.

### Changed

- Skills expose provider-neutral ToolSpecs and workflow guidance; RoboTwin 2.0 remains an independent
  Gateway/ToolEndpoint/Dora/simulator runtime.
- Documented that RoboTwin task, SAPIEN, embodiment, and benchmark configuration belongs in the adapter/profile,
  while a Skill Bundle freezes only runtime wiring and locked artifacts.

### Security

- Documentation-only change; no PAOS runtime, Gateway implementation, simulator, hardware, or motion path changed.

## [v2.5.3] - 2026-09-02

Added a reusable v1.0 feature-reference-card method for planning and reviewing PAOS extensions.

### Added

- Added `docs/forge/FEATURE_REFERENCE_CARDS.md`, linking normative documentation, selected extension points, ownership, failure semantics, implementation modules, tests, and PR traceability.

### Security

- Documentation-only change; no Gateway, Runtime, simulator, hardware, or motion path changed.

## [v2.5.1] - 2026-09-02

Backfilled the v2.5.0 verification-context commit and root index record.

### Changed

- Recorded commit `d6f6a74` and synchronized the bilingual monthly log with the root index.

### Security

- Documentation-only change; no runtime, Gateway, simulator, hardware, or motion path changed.

## [v2.5.0] - 2026-09-02

Added bound AgentTask verification-context integration coverage.

### Added

- Added an integration test that routes bound Query and bounded Action execution facts through
  `VerificationRequestBuilder` into the generic verifier context.
- Verified frozen binding/revision/invocation identity, execution-fact-only capability projections,
  opaque capability artifact references, and the absence of motion authorization in verifier input.

### Security

- The test uses only the Fake Gateway no-motion path and starts no Dora, simulator, hardware, or
  motion route.

## [v2.4.0] - 2026-09-02

Added ExperienceCoordinator recovery-episode integration coverage.

### Added

- Added tests confirming one recovered AgentTask becomes one processed TaskEpisode with preserved
  `replan_required → success` lineage delivered to the analyzer.
- Added assertions that capability facts alone do not create Skill candidates or Lesson clusters.

### Security

- Recovery episode tests execute no real Action, Session, Dora, hardware, or motion route.

## [v2.3.0] - 2026-09-02

Added generic AgentTask verification and recovery coverage.

### Added

- Added deterministic verifier tests for `replan_required`, append-only PlanRevision recovery, and
  final success on the same AgentTask.
- Verified recovered TaskEpisode lineage preserves both the replan-required and successful
  revisions.

### Security

- Recovery tests execute only Fake Gateway Queries and do not create motion, Session, or Dora
  execution.

## [v2.2.0] - 2026-09-02

Added governed execution record coverage after immutable Skill binding.

### Added

- Added a bound Query and bounded Action integration test through `AgentTaskCoordinator` and the
  standard Forge Tool API.
- Verified binding ID, revision ID, ToolSpec digest, invocation/attempt references, and capability
  outcome summary on persisted records.

### Security

- Execution remains on the Fake Gateway no-motion path; no real robot or simulator is invoked.

## [v2.1.0] - 2026-09-02

Added activation-to-AgentTask immutable binding integration coverage for the scene-observe Skill.

### Added

- Added tests connecting `SkillActivationManager`, `ForgeSkillBindingResolver`, and
  `AgentTaskCoordinator` through one primary Skill activation and frozen binding.
- Added fail-closed coverage for Runtime identity drift before governed Query access.

### Security

- The integration performs no Action, Session, Dora, hardware, or motion execution.

## [v2.0.0] - 2026-09-02

Added immutable Forge Skill binding coverage for the provider-neutral scene-observe Bundle.

### Added

- Added preview/freeze tests for manifest, SKILL document, Runtime identity, and all required
  ToolSpec hashes.
- Added fail-closed validation tests for Runtime replacement and ToolSpec tampering after binding.

### Security

- Binding tests execute no Action or Session and do not start Dora, hardware, or motion routes.

## [v1.9.0] - 2026-09-02

Added Runtime controller switch and rollback protection coverage.

### Added

- Added tests that block Skill Runtime switching while an AgentTask is non-terminal.
- Added rollback coverage for failed target startup and atomic active-registry replacement after a
  healthy target check.

### Security

- Tests use fake catalog/manager state only and start no Dora, Gateway, simulator, hardware, or
  motion route.

## [v1.8.0] - 2026-09-02

Added HTTP health-contract coverage for the RuntimeManager's Gateway and required Tool context
checks.

### Added

- Added a localhost-only HTTP fixture exercising real `RuntimeManager.status()` `/tools` and
  required `/context` reads.
- Added fail-closed verification that a missing or unavailable Tool context persists Runtime state
  as `failed` and prevents active-runtime publication.

### Security

- The test starts no Dora flow, hardware process, simulator, or motion route.

## [v1.7.0] - 2026-09-02

Added manifest-v2 Bundle installation and healthy Runtime discovery coverage for the
provider-neutral scene-observe Skill.

### Added

- Added isolated archive install/reload tests through `SkillInstaller` and `SkillCatalog`.
- Added fail-closed discovery tests for a single running runtime with all Tool contexts ready and
  for non-ready runtime states.

### Changed

- Marked the no-binary fake profile as `artifacts.resolver: local`; registry resolution remains
  reserved for Bundles with explicit Node locks.

## [v1.6.0] - 2026-09-02

Added a full no-motion AgentTask workflow integration fixture for the provider-neutral
scene-observe Bundle.

### Added

- Added an end-to-end test using `AgentTaskCoordinator -> ForgeToolClient -> FakeGatewayTransport`
  across observe, understand, propose, prepare, acquire, and place.
- Verified one task/revision, terminal Query/Action records, capability outcome projection, and
  synchronous `ExperienceCoordinator` `TaskEpisode` persistence.
- Covered non-terminal finalization rejection, unknown-action resend blocking, and cancellation
  reconciliation without introducing a second execution protocol or RoboTwin dependency.

## [v1.5.0] - 2026-09-02

Skill candidate support is now partitioned by bounded capability failure-owner scope. Successful
episodes with different scopes create independent candidates and cannot share promotion counts.

### Changed

- Added `capability_failure_owners` to `SkillCandidate`.
- Included owner scope in candidate identity and support matching while preserving legacy empty-scope
  compatibility and existing promotion thresholds.

## [v1.4.0] - 2026-09-02

Active Lesson counterexamples now require an exact capability failure-owner scope match. Mismatched
or scoped/legacy-missing scopes are recorded diagnostically and cannot retire or weaken a Lesson.

### Changed

- Added bounded owner-scope persistence to `ScopedLesson` and exact-scope counterexample checks.
- Preserved legacy behavior when both Lesson and episode have empty owner scopes.

## [v1.3.0] - 2026-09-02

Lesson activation now validates cross-episode capability failure-owner scope. Same-owner
observations may aggregate, while different-owner or scoped/legacy mixtures remain blocked before
synthesis and activation.

### Changed

- Added bounded owner-scope validation to LessonCluster synthesis and direct activation paths.
- Added idempotent `lesson_cluster_attribution_blocked` diagnostics without changing task verdicts,
  Tool API behavior, or Skill promotion thresholds.

## [v1.2.0] - 2026-09-02

Lesson clusters now retain a bounded capability failure-owner scope. Cross-episode observations
with different explicit root-cause owners cannot merge into one reusable Lesson pattern.

### Changed

- Added owner-scope persistence to `FailureObservation` and `LessonCluster`.
- Cluster matching rejects mismatched non-empty capability owner scopes while preserving the
  existing Skill/workflow scope and unique root-task support rules.

## [v0.9.0] - 2026-09-02

Capability outcome facts now flow from verified AgentTask execution records into the experience
and Skill-evolution input without changing task verdict authority or Forge execution boundaries.

### Added

- Added versioned `CapabilityOutcomeFact` and bounded `CapabilityOutcomeErrorFact` records to
  `TaskOutcomeEnvelope`.
- Added AgentTask outcome-source projection with provider-private Tool ID filtering and tests for
  redaction, unknown/failed states, malformed summaries, and diagnostic errors.

### Changed

- Experience analysis now receives only provider-neutral phase/status/owner/world-change/evidence
  facts. Artifact URIs and failure codes remain excluded, and facts/errors cannot authorize
  verdicts, learnability, or Skill/Lesson promotion.

## [v0.8.0] - 2026-09-02

Added a generic verification-layer projection for versioned Forge capability outcomes. The
projection exposes execution facts to AgentTask verification without creating a second execution
protocol or authorizing task success.

### Added

- Added `PhyAgentOS.verification.outcome_projection` for terminal Action summaries, including
  bounded validation of status, capability phase, failure ownership, evidence availability,
  opaque artifact references, metric names, and post-release evidence.
- Added AgentTask verifier-context fields for capability outcome projections and bounded projection
  errors while preserving the existing evidence allowlist and verdict flow.
- Added 14 projection tests covering valid outcomes, malformed summaries, unknown/failure paths,
  post-release evidence, missing summaries, and request-builder integration.

### Changed

- Documented the `execution_fact_only` authority boundary and fixed
  `task_success_authorized=false`; only `TaskVerificationContract` and the generic verifier may
  produce a user-level task verdict.

### Security

- Gateway artifact references remain opaque and are never promoted into `valid_evidence_refs`.
- Projection performs no Gateway calls, motion admission, retry, or PlanRevision mutation.

## [v1.0.0] - 2026-08-30

Initial stable release of PhyAgentOS.

### Security

- Upgraded `@whiskeysockets/baileys` to `7.0.0-rc14` to address
  `CVE-2026-48063` / `GHSA-qvv5-jq5g-4cgg`, and locked the Bridge dependency graph.

## [v0.2.3] - 2026-08-27

PhyAgentOS can run independently distributed Forge Skills through a task-scoped, immutable
Skill/Runtime/ToolSpec binding while keeping Gateway as the execution authority.

### Added

- Added first-class Query, Action, and Session Tool API lifecycles, including Session ownership,
  status/result reconciliation, and owned stop behavior.
- Added activation-time binding previews and task-time frozen bindings containing exact Skill
  version, manifest and workflow hashes, Runtime/Gateway identity, ToolSpec hashes, and Node locks.
- Added crash recovery that reconciles persisted invocation IDs using reads only, plus
  version-scoped Forge experience and Lessons.
- Added deterministic Skill bundle packaging and exact single-executable Node archive locks.
- Added the optional Bundle startup hook
  `bash <bundle>/start.sh <skill-name> <skill-version>` and supplies `PAOS_SKILL_NAME` and
  `PAOS_SKILL_VERSION` to rendered dataflows and Dora process environments.

### Changed

- Forge Gateway selection now comes only from one explicitly started, healthy installed Skill
  Runtime; static `forge.enabled`, `forge.baseUrl`, and `forge.apiVersion` selectors are rejected.
- Runtime state uses schema v2 so Runtime/Gateway identities, Session references, task bindings,
  and force-stop audit records are mandatory and stable across restarts.
- Action admission persists a PAOS-generated caller ID and intent before the remote request.
  Timeouts and unknown results cannot trigger an automatic POST retry.
- Runtime stop and switching account for active invocations, Sessions, and task bindings; forced
  stop records an audit event.
- Resource Registry Skill lookup uses the name endpoint. `paos skill install --version` validates
  the downloaded manifest as a client-side constraint before Node resolution and installation
  commit; schema-v3 static indexes retain version selection.
- Runtime environment identity now covers the selected dataflow path and profile file digests, so
  configuration edits and dataflow-path changes rematerialize the environment.
- Expanded the bilingual integration guide with Bundle packaging, local validation, immutable
  Node/Bundle publication order, and Registry acceptance guidance.

### Fixed

- Forge Node downloads accept Registry responses that omit duplicate digest and size fields. The
  verified Skill lock remains the digest authority, while the direct-download endpoint supplies
  the content length before the archive is downloaded and checked.
- Documented the Dora CLI v0.4.1 and `dora-message` v0.7.0 Forge Skill compatibility baseline,
  version-pinned installation methods, PATH and lifecycle checks, and RuntimeManager's automatic
  local Dora service startup.
- Startup-hook failures, missing Bash, and execution errors now persist a `failed` lifecycle state
  and diagnostic log before Dora can start, rather than leaving stale or unstarted state.
- Start, stop, install/update commit, and removal now use a non-blocking cross-process lock per
  Skill, preventing overlapping lifecycle mutations while allowing automatic release on process
  exit.

### Removed

- Removed the concrete Forge Skill, simulation profile, and remote bundle-fetch helper from the
  PhyAgentOS distribution. Forge Skills and their nodes, models, and assets are installed
  independently when required.

### Security

- Skill and Node downloads require exact size and SHA-256 metadata, archive extraction remains
  bounded and link-safe, and mutations require task ownership plus live binding revalidation.
- Unknown remote effects retain Runtime safety guards until explicit operator resolution.

## [v0.2.2] - 2026-08-21

PhyAgentOS now uses one Forge Query/Action Tool API execution plane while retaining Agent verification, experience, evolution, and the existing general-purpose tool platform.

### Added

- Added the AgentTask lifecycle tools `forge_task_create`, `forge_task_get`, `forge_task_begin_revision`, `forge_task_finalize`, and `forge_task_cancel` with one global non-terminal task, immutable PlanRevisions, bound Query records, Action invocation references, evidence, and aggregate verification.
- Added the Forge Tool API tools `forge_tool_context`, `forge_tool_query`, `forge_tool_start_action`, `forge_tool_action_status`, `forge_tool_action_result`, and `forge_tool_cancel_action` for bound and unbound Query/Action calls.
- Added the manifest-v2 Skill Runtime, catalog, archive validation, transactional installation, persistent runtime state, Resource Registry support, and `paos skill` / `paos forge-node` lifecycle commands.
- Added the built-in `move-arm-by-ee` v0.2 Skill with a MuJoCo profile, relative-pose Query, motion Action, gripper Action, ToolSpecs, and independently locked Forge nodes.
- Added backward-compatible AgentTask, PlanRevision, ToolInvocation, and attempt references to task experience and evolution records.

### Changed

- Robot execution now follows `AgentTask-bound or unbound call → ForgeToolClient → Gateway /tools → ToolInvocation → ToolEndpoint → Dora/robot`; operation `max_concurrency` remains the execution concurrency authority.
- Task verification now aggregates all calls bound to one AgentTask. A recovery verdict appends a bounded PlanRevision to the same task and continues through the existing verification and evolution policies.
- Skill discovery now combines workspace, installed, and built-in Skills. A healthy active Runtime contributes availability and its manifest `gateway_url` takes precedence over `forge.baseUrl`.
- `ForgeConfig` now represents `forge-tool-api.v1`; Resource Registry configuration is available through `resourceRegistry.url` or `PAOS_RESOURCE_REGISTRY_URL` and never triggers an implicit unconfigured download.
- Existing Agent tools, dynamic MCP tools, verification contracts, experience storage, evolution storage, and Skill activation remain available with their existing contracts.

### Removed

- Removed the PAOS Forge Session execution path and the seven Session-specific Agent tools: `forge_execute_task`, `forge_get_session`, `forge_cancel_session`, `forge_get_context`, `forge_reset`, `verify_forge_session`, and `create_replanned_forge_session`.
- Removed the built-in `pipergo2-demo`; `move-arm-by-ee` is the maintained robot Skill example.

### Fixed

- Cancellation acceptance, local timeout, and `unknown` invocation outcomes no longer imply that physical execution stopped and do not trigger blind retries.
- Skill and node installation now verifies SHA-256 metadata, blocks path traversal and unsafe links, validates locked node digests, and rolls back incomplete replacements.

### Security

- Runtime artifacts require verified size and digest metadata before installation; archive extraction is bounded and atomic, and no Registry download occurs without explicit configuration.

## [v0.2.1] - 2026-08-14

PhyAgentOS can turn verified Forge task outcomes into scoped, auditable workflow experience and supply activated Skill Lessons to verification as bounded, non-authoritative advice without changing the Forge execution path.

### Added

- Added explicit `activate_skill(name, role)` activation with one primary Skill, optional supporting Skills, applicable scoped Lessons, and task-to-Skill attribution.
- Added versioned task-outcome, episode, assessment, Skill candidate, failure observation, Lesson cluster, abstraction-validation, and scoped-Lesson contracts.
- Added a crash-safe SQLite WAL experience ledger, asynchronous reflection jobs, structured evolution events, Skill revision history, and generated per-Skill Lesson projections.
- Added guarded Skill creation/update after independent semantic-success support, including managed workflow blocks, workspace overrides for built-in Skills, reload validation, atomic writes, and rollback.
- Added workflow-related failure eligibility, normalized observation clustering, independent root-lineage support, Lesson synthesis, and abstraction validation.

### Changed

- Skill summaries now direct the Agent to activate a matching workflow before tool execution when evolution is enabled; direct `SKILL.md` reads are not treated as activation.
- Learned Lessons are loaded dynamically with the activated Skill. The root `LESSONS.md` remains available as legacy/human-authored material but is no longer injected globally while evolution is enabled.
- Forge verification uses the active scoped Lessons frozen with the root task's explicit Skill activations. Evolution mode never reads root `LESSONS.md` for automatic verification or review, and tasks without an activated Skill receive no learned Lesson context.
- Verifier prompts treat Lessons as untrusted, non-authoritative workflow advice that cannot establish criterion status, replace execution evidence, or appear as evidence references.
- Failures caused by unsatisfiable tasks, verifier/evidence limits, infrastructure, user constraints, or uncertain attribution remain diagnostic-only.
- Built-in Skills remain immutable; promoted revisions are written as workspace overrides and only the PAOS-managed workflow block is replaced on later updates.

### Security

- Experience records redact endpoint-, credential-, path-, executable-ID-, and action-assignment-shaped data and persist only workflow structure, input field names, opaque evidence references, and immutable record references.
- Lesson and Skill policies reject task-specific answers, fixed coordinates/values, credentials, endpoints, Gateway IDs, Action Manifest copies, prompt injection, and instructions that bypass Forge or verification.

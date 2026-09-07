# PAOS Planning Module Design

## Status

This document is the implementation baseline for `PhyAgentOS/planning`. It is
an approved design boundary, not a second task runtime.

## Purpose

The module represents an Agent-composed semantic subtask DAG and evaluates
whether a proposed Tool call is structurally and evidentially admissible. It
does not execute Tools, own a task lifecycle, persist facts, acquire locks, or
authorize motion.

The task-level shape is:

```text
relocate(red)  ─────┐
relocate(blue) ─────┼──> verify
```

Each semantic node may select a different Tool sequence. The old fixed
`observe -> capabilities -> understand -> propose -> prepare -> acquire ->
place` sequence remains a Skill baseline policy only; it is not the only legal
plan.

## Ownership boundary

| Boundary | Owner | Rule |
| --- | --- | --- |
| PlanGraph and Tool-call protocol | `PhyAgentOS/planning` | Immutable Pydantic contracts and pure validation only |
| Task, revision, execution facts | `forge/task.py` and SQLite | The only lifecycle authority |
| Tool transport and invocation | `forge/tool_client.py` / Gateway | The only execution plane |
| Robot capability and readiness | adapter/provider | Physical facts; fail closed |
| Semantic success | Verifier | Task-level verdict authority |
| Policy candidates and promotion | `agent/experience` / Skill Runtime | Review and independent evaluation required |

The planning module must not import Gateway clients, SQLite stores, adapter
providers, or Skill Runtime state.

## Robot/controller capability boundary

`CapabilitySnapshot` and `ArmCapability` are the sole PAOS capability
projection. Robot-specific motion limits are not a second core model: each
arm may carry an opaque `motion_capabilities_ref` to an adapter-owned,
immutable provider artifact. The artifact records per-joint limits,
controller/simulator identity, units, timing, provenance, and whether a limit is
actually enforced by the controller. Planning consumes this projection for
admission and arm assignment; it never imports an SDK or changes a limit.

The RoboTwin20 Franka path is simulation-only. Its local requirements include
SAPIEN, MPlib, and CuRobo but no `libfranka`/`frankx`; the simulation loads
`panda.urdf` and drives SAPIEN articulation targets. No global numeric speed
threshold is defined by PAOS. An adapter must bind provider-owned limits and
their provenance before planning or execution. A hard bound may be advertised
only after a controller-specific qualification artifact proves enforcement and
binds the controller identity/version. Diagnostic measurements remain evidence
only and cannot authorize motion. See `REAL_SPEED_LIMITS_ARCHITECTURE.md` for
the normative route.

Evidence sources: `RoboTwin/scripts/requirements.txt`,
`assets/embodiments/franka-panda/config.yml`,
`assets/embodiments/franka-panda/curobo.yml`, and RoboTwin
`envs/robot/robot.py:set_arm_joints`; the upstream
[libfranka Robot API](https://raw.githubusercontent.com/frankaemika/libfranka/main/include/franka/robot.h)
documents explicit rate-limiting controls and joint-velocity-limit queries.

## Protocols

- `PlanGraph` / `PlanNode`: current task's semantic DAG, bound to a task and
  revision digest. Nodes describe obligations, capabilities, dependencies,
  evidence, resource claims, and retry lineage.
- `ToolSpecPolicy`: planning projection of a ToolSpec. It declares
  preconditions, required/produced evidence, expected effects, resources,
  scene-write behavior, failure classes, and idempotency. It is not a second
  provider configuration source.
- `ToolCallEnvelope`: Agent proposal with task/revision/node identity,
  ToolSpec digest, input-binding digest, scene revision, and idempotency key.
- `ToolResultEnvelope`: execution result projection. `unknown`, `failed`, and
  `cancelled` are distinct; a result never grants motion authority.
- `NodeSettlement`: normalized node fact (`completed`, `failed`, `outcome_unknown`,
  `blocked_by_dependency`, `stale`, or `cancelled_before_start`).
- `ReplanDelta`: preserve/cancel/invalidate/retry instructions and fresh
  evidence requirements. The coordinator, not this module, creates a new
  `PlanRevision`.
- `DecisionTrace`: redacted, attributable record of candidate Tools, selected
  Tool, policy/context digests, and result/evidence references.
- `WorkflowPolicy`: reusable partial-order and Tool-selection policy. It is
  separate from a concrete `PlanGraph`; one successful episode never rewrites a
  policy automatically.

`PlanRevision` stores an immutable `artifact://` graph reference plus graph,
planner-decision, and policy-snapshot digests;
`ToolExecutionRecord` stores node/obligation/input-binding/decision-trace
references when a Tool call is attached to a semantic node. These are optional
for legacy records but become an all-or-nothing binding once any planning field
is supplied. SQLite continues to persist the aggregate; this module only
validates the shape.

## Dynamic Tool admission

The Agent may choose any Tool present in the frozen binding. Admission is
constrained by the ToolSpec projection and current context:

1. The node exists and is ready in the DAG.
2. The proposed Tool matches the node capability and bound ToolSpec digest.
3. Required evidence is present and references the current scene revision.
4. Resource claims do not conflict with currently held resources.
5. Action/session semantics remain subject to Gateway admission; planning only
   returns a decision.

Thus the rule is **not a fixed order, but fixed legality conditions**.

## Evolution boundary

Experience may propose changes to Tool order, optional queries, re-observation,
candidate ranking, arm preference, retry/replan strategy, and semantic
parameter binding. It may not change workspace, joint limits, collision/stop
policy, transforms, readiness, Gateway authority, or Verifier safety rules.

Only a complete attributable AgentTask episode with independent semantic
verification can produce a `WorkflowPolicyCandidate`; replay/matched evaluation
and review are required before Skill promotion.

## Failure semantics

Missing evidence, stale scene, dependency failure, resource conflict, unknown
Tool, and cycle are explicit rejection paths. Timeout/transport uncertainty is
represented as `outcome_unknown`, never as success. Replanning preserves task
identity while the PAOS coordinator owns the new revision and retry budget.

## Migration stages

1. Keep the existing Skill workflow as a deterministic baseline policy.
2. Generate an Agent-composed no-motion semantic DAG for multi-object tasks.
3. Select Tools dynamically through admission checks.
4. Record DecisionTrace and derive reviewed policy candidates.
5. Promote only reviewed, independently evaluated Skill policy versions.

The pick-place Skill exposes these modes explicitly: `baseline` uses the legacy
fixed Tool projection for compatibility/replay; `agent_composed` compiles
Agent-provided semantic subtasks into `PlanGraph` and uses dynamic Tool
candidate admission. The Skill bridge is an adapter over the planning library,
not a second planner runtime.

## Review gates

Every change to this module is reviewed across architecture integration,
failure paths, authority boundaries, configuration/provenance, and
maintainability. Tests must prove the module is pure: no Gateway calls, no
SQLite writes, no locks, and no `motion_authorized=True` output.

## Implementation status (2026-09-05)

The coordinator integration now accepts a concrete `PlanGraph` plus an immutable
`artifact://` reference at task creation and at a new revision. It persists the
graph, planner-decision, and policy-snapshot digests in the authoritative
`PlanRevision`. Planning-driven Query/Action/Session calls may provide one
complete `PlanningExecutionBinding`; the coordinator persists its node,
obligation, input-binding, and redacted DecisionTrace reference in the
`ToolExecutionRecord`. A partial binding is rejected, while calls without a
planning binding remain compatible with legacy tasks. `ReplanDelta` is adapted
through `begin_revision_from_delta`; the planning module still does not mutate
the store or create revisions itself. Redacted decision-trace references are
also carried into the experience outcome projection.

Live ToolSpecs now have an explicit `planning` extension projection through
`project_tool_spec()`. The extension is versioned and strict; missing metadata
does not get guessed from a tool name, endpoint, or implementation, so legacy
ToolSpecs remain executable but unavailable to `agent_composed` admission.
Bound Skill metadata carries the immutable projection when present and
revalidates it on the next binding check. AgentLoop production dispatch is
provided by a read-only `AgentComposedDispatch` bridge, and Experience stores
planning policy candidates plus independent replay receipts with explicit
human-review and callback-gated promotion. No Action/Gateway/Dora motion wiring
is introduced here.

## ToolSpec projection review (2026-09-05)

The live binding path now projects only an explicit versioned `planning`
extension through `project_tool_spec()`. The projection preserves the live
ToolSpec digest and strict planning fields; it never infers a capability from a
provider endpoint or implementation name. Legacy ToolSpecs without the
extension remain valid for ordinary execution but are unavailable to
`agent_composed` admission. If an extension is present but malformed, binding
fails closed, and a previously bound projection is revalidated on the next
ToolSpec check. This closes the configuration/provenance gap without creating a
second Tool registry or execution path.

## AgentLoop dispatch and policy-candidate status (2026-09-05)

`PhyAgentOS.agent.planning_dispatch.AgentComposedDispatch` is the AgentLoop
bridge for an active task. `forge_plan_activate` builds it from the persisted
`PlanRevision.plan_graph`, frozen Skill binding, and an injected trusted
`AdmissionContext` provider. Agent-supplied evidence, settlements, scene
revisions, and condition facts are not accepted. `forge_plan_ready` exposes only
the current ready semantic nodes and their explicit ToolSpec projections. A
registry execution guard checks task-bound Query/Action/Session creation calls
before the existing Forge wrappers run. Missing providers/projections, stale
identities, incomplete planning bindings, and unready nodes return a
structured fail-closed error; status/result/cancel reconciliation remains under
Coordinator ownership.

Experience now stores `WorkflowPolicyCandidate` and immutable independent
`WorkflowPolicyReplayReceipt` records in `experience.sqlite3`. Candidates are
deduplicated by base/proposed policy digests, require support from distinct
episodes and passing independent replay receipts before human approval, and
cannot be promoted without an explicit Skill Runtime callback returning an
`artifact://` receipt. No candidate transition mutates an active AgentTask.

## Collision-world admission boundary (2026-09-07)

`SceneCollisionWorld` is an adapter-owned evidence dependency of
`manipulation.prepare`; it is not a planning Tool, Skill step, or Curobo handle exposed to the
Agent. The planning module may validate its reference, digest, scene/world revision, coverage,
and phase-scoped target exclusion, then return an admission or stale/invalidation result. It
must not build a Curobo `WorldConfig`, call `MotionGen.update_world()`, execute `scene.step()`,
or create a `PlanRevision`.

When a world revision changes, `AgentLoop`/`AgentTaskCoordinator`—not this library—creates the
next revision and rebinds a fresh collision-world artifact. The adapter must update both
`motion_gen` and `motion_gen_batch` from the same world digest. Partial/unknown perception
coverage, missing geometry/provenance, cache-capacity overflow, or update failure remains
fail-closed and cannot be converted into a ready or motion-authorized result.

The RoboTwin provider handles Curobo's fixed OBB cache explicitly. It uses
`MotionGen.update_world()` when both arm planners have capacity for the complete world. If
capacity is insufficient, the runtime port rebuilds warmed `MotionGen` and batch instances from
the existing RoboTwin robot profile and complete `WorldConfig`, then swaps both arm references
only after all replacements succeed. This is provider behavior, not planning-module logic; no
`scene.step()` or motion authorization occurs during rebuild.

## Generic attribute-sorting scenario and execution-loop extension (2026-09-07)

### Scenario fit

The user request "arrange blocks by RGB/color" is a valid instance of a
generic attribute-sorting task, not a request for an RGB-specific workflow.
The request intentionally omits the number of blocks, the set of observed
colors, and their initial locations. Those values must be discovered from the
live observation Skill and represented as evidence; they must not be placed in
the planner, a Skill prompt, or a fixed DAG template.

The intended flow is therefore:

```text
natural-language goal
  -> Agent selects an observation/understanding Skill
  -> live scene observation and scene-graph evidence
  -> Agent decomposes the discovered entities and ordering obligations
  -> generic PlanGraph (one semantic obligation per entity/group)
  -> node-scoped Agent execution through existing Forge Tools
  -> NodeSettlement and evidence update
  -> next ready node, or bounded replay/replan after a failure
```

The decomposition may produce nodes such as `sort-group/<opaque-id>` or
`arrange/<opaque-id>`, but these are planner outputs, not PAOS-owned RGB
semantics. A final verification node joins the discovered obligations. The
graph must remain valid when the scene contains a different number of blocks,
additional colors, duplicate colors, or an empty/partially observed set.

The unknown inventory creates a progressive-planning requirement. The current
task API can create a task with a final graph or with no graph, while
`AgentComposedDispatch` requires a concrete graph and `begin_revision()` is
normally entered after `awaiting_replan`. A production flow therefore needs a
same-`AgentTask` discovery checkpoint: observe and validate the scene first,
then let the planner propose an expanded graph in a new `PlanRevision`, while
preserving the observation evidence. This is a revision/expansion transition,
not a second task and not a fixed RGB graph.

The requested order must be explicit in the task goal or verification
contract. If "RGB" supplies the comparator (for example red, then green, then
blue), the planner can bind discovered entities to that comparator. If the
ordering rule or target layout is ambiguous, the Agent must ask or produce an
unknown verification outcome; it must not infer a layout from a color name.

### Failure cases exposed by the scenario

An object can be dropped during an Action in two observably different ways:

- the Action returns `failed` or `outcome_unknown`; the active node can be
  settled directly and its descendants invalidated;
- the Action returns success, but a later observation/verification supplies
  counterevidence that the object is no longer in the required place. In this
  case the later evidence must mark the affected obligation stale/failed and
  trigger a new revision; the system must not rewrite the historical success.

The second case requires a generic postcondition/observation checkpoint and
an evidence-to-obligation attribution. It cannot be implemented as an
RGB-specific "dropped block" branch. The new revision should preserve only
nodes whose evidence remains valid, invalidate the affected obligation and its
descendants, and carry the counterevidence into the Agent's replan context.

The current `begin_revision_from_delta()` validates task/revision identity and
accepts a replacement graph, but does not itself materialize
`preserve_node_ids`, `invalidate_node_ids`, or `fresh_evidence_requirements`.
The loop adapter must apply those fields when constructing the replacement
revision and when selecting predecessor context; otherwise a replay could
reuse evidence from an invalidated branch.

Each world-changing node may advance the scene revision. Before the next node,
the trusted context provider must refresh the scene/evidence view and reject
stale predecessor facts. A re-observation node or a planner-selected
fresh-evidence requirement is preferable to silently continuing from the
initial scene graph.

### Minimal loop that reuses PAOS authorities

The missing connection is a thin `PlanningLoopAdapter`, not another runtime.
It consumes the persisted `PlanRevision.plan_graph`, calls the existing
`AgentComposedDispatch` for ready-node and Tool admission, and invokes one
node-scoped turn of the existing `AgentLoop`. The loop writes execution facts
through `AgentTaskCoordinator`; it does not write a parallel state file or
invoke a Gateway directly.

For each selected ready node:

1. Build a bounded node prompt from the node declaration and the direct
   predecessor's persisted settlement/evidence summary.
2. Run the normal AgentLoop Tool-call loop with the planning guard enabled.
3. Convert terminal `ToolExecutionRecord` facts to `ToolResultEnvelope`, then
   call the pure `settle_node()` function.
4. Persist the resulting `NodeSettlement` in the active `PlanRevision` and
   refresh the trusted `AdmissionContext`.
5. Call `derive_ready_nodes()` and continue until the graph is complete or a
   non-success settlement requires recovery.

`NodeSettlement` should become a field of the existing `PlanRevision` rather
than a second store. Deriving settlement only from Tool records is acceptable
for an initial experiment, but is ambiguous when one semantic node selects
multiple Tools or has an unknown outcome; durable node settlement is required
for reliable replay and recovery.

### Minimum predecessor-context injection

The first implementation only needs direct-predecessor context. A
`NodeContextProvider` outside the pure planning package can project:

- current `task_id`, `revision_id`, and `node_id`;
- the current node's capability, dependencies, and required evidence;
- each direct predecessor's terminal status;
- opaque `evidence_refs`/`output_refs`, source Tool ID, and failure code;
- preserved constraints from the latest replan decision.

The projection is inserted into the node-scoped Agent turn as data, not as a
new authority. Raw provider payloads, unverified coordinates, controller
parameters, and arbitrary workspace text are excluded. A predecessor result
can therefore tell the current Agent "acquisition completed and produced
evidence X" or "the prior attempt is unknown; re-observe before acting",
without allowing the Agent to assert that the scene is current.

This reuses `ToolExecutionRecord`, `NodeSettlement`, `AgentTaskStore.events()`,
the existing evidence references, and advisory Experience lessons. It does not
require a second memory database or a second prompt protocol.

### Failure, replay, and replan semantics

The physical-drop example is represented as a normal node outcome, not as an
RGB-specific exception:

```text
node action result
  -> failed / outcome_unknown / stale
  -> settle_node()
  -> build_replan_delta()
  -> Agent proposes a replacement graph or bounded retry
  -> coordinator appends a new PlanRevision
  -> adapter resumes from the new revision
```

The Agent may choose the recovery strategy from the failure feedback, but it
cannot mutate the active graph or mark a node successful by assertion.
`ReplanDelta` remains the bounded description of preserved nodes, invalidated
descendants, retry lineage, and fresh evidence requirements;
`AgentTaskCoordinator` remains the owner that accepts a new revision and
enforces the retry budget/deadline.

Replay must be split into two operations:

- **Reducer replay:** replay stored Tool results and settlements without any
  Gateway call. This is safe for diagnosing the DAG and rebuilding ready sets.
- **Execution rerun:** execute a node again. Query reruns may create another
  execution record; Action/Session reruns require a new revision, fresh
  admission, and explicit `retry_of` lineage so a physical side effect is not
  silently duplicated.

The recovery policy is selected by the Agent/Planner Plugin from the failure
feedback. PAOS supplies the facts and gates; it does not hard-code a rule such
as "always retry the dropped block".

### Planner/plugin boundary

The decomposer, node-selection policy, node-context projection, and recovery
policy belong in an installable planner/Skill plugin. The plugin may call
`compose_agent_plan()` and return a `PlanGraph`, but it does not own task state,
Tool transport, Evidence, Verifier semantics, Runtime admission, or motion
authority. PAOS core exposes only the provider-neutral planning contracts and
the existing coordinator/AgentLoop seams.

This preserves the current baseline workflow and allows an attribute-sorting
planner to coexist with other planners. The present repository already has
Skill Runtime installation and ToolSpec planning projections; the remaining
extension is a formal planner-plugin interface/discovery seam, not a second
planner runtime embedded in `PhyAgentOS/planning`.

### Six-dimension acceptance for this extension

| Dimension | Acceptance condition for the attribute-sorting loop |
| --- | --- |
| Architecture integration | Reuse AgentLoop, AgentComposedDispatch, AgentTaskCoordinator, PlanRevision, Forge Tool API, Evidence, and Verifier; no second scheduler/store/execution path |
| Failure paths | Tests cover incomplete observation, empty/duplicate attributes, dependency blocking, failed/unknown/stale/cancelled nodes, dropped-object feedback, replay, replan timeout, and retry-budget exhaustion |
| Authority boundaries | Planning and plugins remain no-motion; Coordinator owns task/revision state; Gateway owns execution; adapters own physical facts; Verifier owns semantic success |
| Configuration/provenance | Discovered entities and prior-node context carry task/revision/node/evidence provenance and reuse existing graph, ToolSpec, and trace identities; Agent-supplied facts are not trusted context |
| Maintainability | One orchestration adapter, one node-context projection, and one plugin interface; existing baseline reducer and Tool wrappers remain usable |
| Anti-OverDefense | Add checks only for observed hazards such as stale predecessor context and duplicate Action side effects; do not add RGB-specific schemas, fixed block counts, speculative hashes, or duplicate gates |

### Completion status and next implementation slice

The scenario is architecturally compatible, but the following pieces are not
yet complete in the current implementation: a general decomposer/plugin seam;
same-task discovery-to-DAG revision expansion; durable `NodeSettlement`
storage; a public node-scoped AgentLoop entry point; automatic
settlement-to-ready progression; bounded Agent-selected replan application;
post-action counterevidence attribution; preserve/invalidate application; and
predecessor-context injection into the node prompt.

The smallest coherent implementation slice is: persist settlements in the
existing `PlanRevision`, add a `NodeContextProvider` that injects one direct
predecessor summary, and add the thin `PlanningLoopAdapter`. Only after that
slice is verified should planner-selected replacement graphs and Action-node
rerun semantics be enabled. The RGB sorting task then becomes a validation
scenario for generic attribute discovery and recovery rather than a new
hard-coded workflow.

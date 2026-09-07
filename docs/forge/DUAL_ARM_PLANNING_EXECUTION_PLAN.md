# PAOS 双臂规划与执行流程

## 1. 目的与审核结论

本文定义 RoboTwin/Franka 双臂任务在 PAOS 中的正确接入方式。它修正了一个容易混淆的说法：当前 probe 能证明机器人 link 与桌面发生了接触，但由于 RoboTwin 两个单臂实体共享 `panda_hand`、`panda_leftfinger`、`panda_rightfinger` link 名称，且 contact entity name 为空，不能仅凭现有 trace 断言“未选中的左臂发生了碰撞”。

正确结论是：失败被正确地 fail-closed，但 provider 的接触身份和双臂初始状态证据还不完整。下一阶段必须先补齐身份、状态和跨臂碰撞投影，再讨论路线或候选优化。

本文不把双臂调度器、Curobo planner 或第二套任务生命周期加入 PAOS Core。双臂协调是当前任务的语义计划与 provider-owned readiness/execution projection；物理执行仍由 Gateway（正式路径）或明确批准的 simulation-only provider（验证路径）负责。

## 2. PAOS 所有权与扩展原则

| 层级 | 双臂职责 | 明确不做的事 |
|---|---|---|
| Agent / Skill | 提出语义子任务、允许的臂、顺序/并行意图和失败替代 | 不直接选择 SAPIEN link、Curobo API 或关节值 |
| `planning` | 校验 PlanGraph、依赖、资源声明、状态证据和 Tool admission | 不调用 Gateway、Curobo、SAPIEN，不持有锁 |
| `forge/task` / Coordinator | 绑定 PlanRevision、DAG artifact、重规划 lineage 和任务事实 | 不执行机械臂 |
| RoboTwin adapter | 生成双臂初始状态、link identity、inter-arm collision projection 和 provider route | 不改变公共 ToolSpec 或 PAOS 生命周期 |
| readiness provider | 对每只臂评估 IK、静态环境、另一只臂、attached object 和完整路线 | 不把 planner 结果变成动作授权 |
| Gateway | 正式 Action/Session 的唯一物理执行面；负责并发、取消和停止 | 不定义用户级语义成功 |
| simulation probe | 在独立批准下执行仿真、记录接触和 before/after evidence | 不接入 Gateway/Dora/Action/hardware |
| Verifier | 根据任务契约判断抓取、放置和整体语义结果 | 不用 `check_success()` 单独替代证据 |
| Experience | 从完整 episode 学习臂分配、Tool 顺序、hold/park 策略 | 不修改碰撞、停止、关节限制或物理真值 |

原则是“策略可进化，物理事实不可由策略改写”：Agent 可以改变臂选择、子任务顺序、是否重新观测和失败重规划；不能改变 workspace、joint limits、collision/stop policy、frame transform 或 readiness 规则。

## 3. 双臂状态语义

### 3.1 初始状态的定义

双臂的规划初始状态不是 URDF 加载瞬间，而是 provider reset 完成后的稳定状态：

```text
reset(seed)
  → homestate drive target
  → provider stabilization
  → capture left/right qpos, drive target, gripper and link poses
  → state_revision = scene_revision + provider state generation
```

`check_stable()` 内部的稳定化步骤属于 provider 初始化事实；它不能被误记为任务路线动作。状态 artifact 至少要描述：

- `scene_revision`、`state_revision`、`frame_id`、calibration/provenance；
- 左右臂 active joint order、qpos、drive target、gripper state；
- 左右臂每个碰撞 link 的 provider-qualified identity 和 pose；
- 当前 `selected_arm`（若尚未选择则为空）；
- 未选中臂策略：`hold`、`park` 或 `static_projection`。

### 3.2 未选中机械臂

“未选中”不等于“没有运动目标”或“从场景删除”。必须在 route contract 中明确一种语义：

- `hold`：每个 provider step 保持绑定的初始 qpos/drive target，并记录偏差；
- `park`：先执行一个 readiness-backed park route，再执行目标臂任务；
- `static_projection`：不驱动该臂，将绑定姿态的 link 几何投影到另一臂 planner，同时验证实际姿态没有漂移。

对于当前 RoboTwin 独立 probe，推荐先实现 `hold` 或 `static_projection`，因为用户已明确“未选中左臂应保持初始姿态”。如果稳定性或桌面间隙不足，readiness 必须拒绝该 hold 方案并要求 `park`，不能静默忽略。

## 4. 双臂碰撞模型

## 4A. 联合规划是核心能力，不是两个单臂结果的拼接

双臂“联合规划”必须同时考虑两只机械臂的状态、几何和时间关系。下面三种模式必须明确区分：

| 模式 | planner 输入 | 能证明的内容 | 当前 RoboTwin/Curobo 状态 |
|---|---|---|---|
| 单臂 + 另一臂静态投影 | 选中臂 q，另一臂固定姿态几何 | 选中臂路线不撞另一臂的固定姿态 | 可作为近期目标，但还未实现完整 arm-qualified projection |
| 顺序双臂 | 第一条路线完成后的新双臂状态 + 第二条路线 | 每一段路线在前一段结果和 hold/park 约束下安全 | 可由 PAOS DAG 表达；每段都必须更新 world/state revision |
| 同步双臂联合规划 | `(q_left(t), q_right(t))` 的统一时间轴和耦合碰撞约束 | 两臂 swept-volume、互撞、共同停止和同步语义 | 当前两个独立 Curobo planner 不具备此证明能力，必须由 provider/Gateway atomic bundle 提供 |

因此，以下做法都不能称为联合规划：

- 分别调用 left/right Curobo，谁成功就选谁；
- 只把方块加入两个 planner，而不加入另一只机械臂；
- 规划时检查另一臂，执行时却不记录另一臂状态；
- 同时向两个独立 Action 发送命令，然后假定它们同步。

### 4A.1 联合状态模型

联合规划的最小状态不是两个独立的 `qpos` 字段，而是一个带同一时间和 revision 的状态：

```text
DualArmPlanningState {
  scene_revision
  state_revision
  frame_id
  left: {qpos, drive_target, gripper, link_poses}
  right: {qpos, drive_target, gripper, link_poses}
  active_route_mode: sequential | synchronized
  held_arm_policy: hold | park | static_projection
}
```

在顺序模式下，第二条路线的起点必须是第一条路线完成并验证后的 `DualArmPlanningState`，不能继续使用 reset 时的旧状态。任何物体移动、夹爪状态改变或另一臂姿态漂移都必须使旧 route 变为 stale。

### 4A.2 防碰撞的三层约束

双臂防碰撞不能只依赖一个 Curobo `world`：

1. **几何层**：每只臂的 planner world 包含 table、非目标物体、另一臂当前 hold/park link geometry，以及当前 attached object；
2. **轨迹层**：对每个离散时间点检查左右臂 link 与环境、目标物体和另一臂 link 的距离/碰撞；同步模式还要检查 swept-volume，而不是只检查 waypoint；
3. **执行层**：SAPIEN/Gateway 实际接触、停止和状态漂移必须独立记录；执行接触不能被 planner 预测替代。

其中几何层由 RoboTwin adapter/provider 投影，轨迹层由 readiness provider 或 atomic route provider 评估，执行层由 simulation probe/Gateway 产生事实。PAOS planning 只负责确认这些证据存在并与当前 revision 绑定。

### 4A.3 两个独立 Curobo planner 的边界

当前左右 Curobo planner 可以分别提供：

- 单臂 IK/轨迹候选；
- 静态 table/object world 中的碰撞结果；
- 在另一臂被投影为静态障碍时的近似顺序规划。

它们不能单独提供：

- 两臂共享时间轴的联合优化；
- 两臂互相移动时的动态碰撞保证；
- 原子取消、共同 stop 和跨臂 trajectory settlement；
- 同步接触动力学或 bimanual semantic verdict。

所以近期实现应优先采用“顺序执行 + 另一臂 hold/park + inter-arm static projection”。只有存在 provider-owned atomic route bundle 后，才开放真正 synchronized bimanual 模式。

## 4A.4 复用现有 planner 能力，不在 PAOS 重造 planner

### Curobo 已能提供的能力

当前 RoboTwin checkout 中的 Curobo `MotionGen` 已提供：

- `plan_single()`：单个机器人模型的 IK/轨迹生成；
- `plan_batch()`、goal-set/environment batch：多候选或多碰撞环境的批量求解；
- `check_start_state()`：关节限制、自碰撞和 world collision 的起始状态检查；
- `WorldConfig`、`update_world()`：更新静态碰撞世界（受初始化 cache capacity 约束）；
- `attach_external_objects_to_robot()` / `detach_object_from_robot()`：附着物体碰撞模型；
- self-collision cost/check、joint limits、轨迹优化和 graph planner。

这些能力足以支撑“单臂 + 另一臂静态投影”的顺序路线，但不能自动产生当前所需的双臂联合规划。当前 RoboTwin 为左右臂分别构造两个 `MotionGen`，每个实例只有一个机器人模型。PAOS 不应重新实现 IK、TrajOpt 或碰撞检测，而应由 adapter 将另一臂的绑定姿态几何投影为 Curobo world obstacle，或在 provider 具备 combined-robot model 时调用其原生联合 planner。

### Curobo 当前不能直接证明的能力

- 两个独立 `MotionGen` 之间的 inter-arm collision；
- 两条同时变化的 `(q_left(t), q_right(t))` 轨迹的 swept-volume collision；
- 双臂统一时间轴、共同取消、原子 stop 和同步 settlement；
- 双臂接触动力学或任务级语义成功。

如果未来为 Curobo 构造一个包含左右臂的 combined robot model，它可以作为新的 provider capability 实现真正联合规划；但这不是把两个现有 planner 简单拼接，也不能由 PAOS Core 负责实现。

### 可替换的其他 provider

| Provider | 可复用能力 | 适用的双臂模式 | PAOS 适配边界 |
|---|---|---|---|
| MoveIt 2 + PlanningScene/OMPL/TrajOpt | 统一 planning scene、attached body、碰撞检查、采样/优化规划 | 可配置 combined robot/group 时支持同步或顺序双臂 | adapter 负责 URDF/SRDF、PlanningScene 和 ros2_control 映射；Gateway 仍负责正式执行 |
| Drake | MultibodyPlant、双臂动力学/几何、trajectory optimization | 适合需要动力学约束和联合时间轨迹的双臂任务 | provider 负责模型、求解器和轨迹导出；不把 Drake 类型放入 PAOS Core |
| Tesseract/TrajOpt | 过程规划、碰撞场景、轨迹优化 | 适合 combined robot 或工业过程路线 | adapter 负责 scene graph、kinematics 和执行桥接 |
| SAPIEN/Bullet/FCL 等碰撞引擎 | 实际接触或几何距离检查 | 只能作为执行事实/碰撞检查 provider | 不能单独替代 planner、Gateway 或 Verifier |

选择 provider 的依据应是 capability artifact，而不是 Agent 直接判断库名：

```text
planner_modes:
  - single_arm_peer_projection
  - sequential_dual_arm
  - synchronized_atomic_dual_arm
collision_scopes:
  - self
  - static_world
  - peer_arm
  - attached_object
  - swept_volume
execution_semantics:
  - independent
  - sequential_hold
  - atomic_bundle
```

planning module 只检查所需 mode/scope 是否由当前 provider capability 声明并有 readiness evidence；实际 planner API 始终留在 adapter/provider。

### 推荐的 PAOS 扩展接口

不新增 `curobo.plan` 这种 provider-specific Tool，而是在 adapter 中实现统一 provider port：

```text
DualArmPlannerPort.plan(request: DualArmPlanRequest)
  → DualArmPlanResult

DualArmPlanRequest {
  planning_state_ref
  collision_projection_ref
  mode: single_arm_peer_projection | sequential_dual_arm | synchronized_atomic_dual_arm
  selected_arm / coordination_group_ref
  candidate_or_goal_refs
}
```

`DualArmPlanResult` 只返回 provider-owned route/readiness artifact 和 capability receipt。planning module 根据其 mode、scene/state revision、资源声明和 evidence 做 admission；它不解析 Curobo、MoveIt 或 Drake payload。

推荐的 provider fallback 是：

```text
atomic combined planner available
  → synchronized_atomic_dual_arm
否则
  → sequential_dual_arm + hold/park + peer projection
否则
  → single_arm_peer_projection
否则
  → unavailable（不得忽略 inter-arm collision）
```

任何 fallback 都必须在 route 中显式记录，不能把能力降级隐藏在 Tool 调用顺序里。

### 4.1 静态和跨臂障碍

当前 collision-world 已包含 table、非目标方块和 attached-object，但每个 Curobo planner 尚未包含另一只机械臂的几何体。正确的 provider projection 是：

```text
left planner  = table + non-target objects + right-arm(initial/park) geometry
right planner = table + non-target objects + left-arm(initial/park) geometry
```

跨臂几何必须来自同一个 `scene_revision`/`state_revision`，并记录 link identity、mesh/primitive 来源和姿态来源。目标物体在 close 后转为 attached geometry；release 后从 attached 集合移除并按新 world revision 重新投影。

### 4.2 同时运动

如果两个臂同时运动，静态投影不够。必须由一个 Gateway-owned atomic route bundle 提供统一时间轴、inter-arm swept-volume 检查、共同取消和单一 evidence bundle。两个独立 Action post 不能被解释为同步双臂执行。

在 atomic bundle 尚未实现前，planning 只能允许：

```text
sequential selected-arm route + explicit hold/park for the other arm
```

## 5. 接触证据要求

provider 不能仅记录 `panda_leftfinger`。必须将 link 映射为稳定的 qualified identity，例如：

```text
left:panda_leftfinger
left:panda_rightfinger
right:panda_leftfinger
right:panda_rightfinger
```

每条 contact record 至少包括：

- `arm_id`、`link_name`、`entity_id`；
- 对端角色：`table`、`target_object`、`non_target_object`、`other_arm`；
- `phase`、`step`、`first_contact_step`、`max_impulse_ns`；
- `selected_arm`、`unselected_arm_policy`；
- `route_attachment_state` 和 contact body roles（不能用全局 attached 布尔值代替）；
- 是否是预期的 grasp/support contact。

`failed_phase` 只能表示失败被结算的阶段，不能代替 `first_contact_phase`。目标物体与 table 的预期支撑接触、夹爪与目标物体的预期 grasp 接触，以及机器人 link 与环境的意外接触必须分开统计。

## 6. 具体执行流程

### 阶段 A：Provider reset 与双臂状态物化（无动作授权）

1. adapter 使用 runtime profile reset 固定 seed；
2. 完成 RoboTwin homestate/stabilization；
3. 采集左右 qpos、drive target、夹爪状态和 qualified link poses；
4. 生成 `DualArmExecutionState` artifact；
5. 检查 scene/state revision、frame 和 calibration；任一缺失则返回 `unavailable`。

### 阶段 B：场景与双臂碰撞投影

1. `scene.observe`/`scene.understand` 提供带 provenance 的物体几何；
2. adapter 构建 table、非目标物体和另一只机械臂几何；
3. 为左右 planner 生成各自 world projection；
4. 记录 obstacle set、arm state refs、world revision 和 provider receipt；
5. 在 no-motion 阶段确认 Curobo cache capacity、实体数量和 frame 转换。

### 阶段 C：任务 DAG 与臂分配

1. Agent 为每个物体生成独立 pick-place 子任务；
2. 每个子任务声明允许的 arm、hold/park 要求和顺序约束；
3. planning module 根据 evidence 和 readiness 计算 ready/admission；
4. adapter/readiness 对每个 candidate × arm 评估完整 approach/contact/close/lift/transport/descent/release/retreat；
5. 选择只产生 no-motion assignment，不产生动作授权；
6. 若选中一只臂而另一只臂需要 park，则把 park 作为 DAG 节点，而不是隐藏在 Tool 顺序中。

### 阶段 D：路线执行前 admission

必须同时满足：

- 双臂初始状态与 route 的 state revision 一致；
- 另一只机械臂几何已进入选中臂的 planner world；
- hold/park 策略有对应 readiness evidence；
- candidate、placement、calibration、collision-world 和 capability 均来自同一 scene revision；
- sequential/atomic execution mode 已明确；
- stop/reset 路径已可用。

任一条件不满足，不得进入仿真 step 或 Gateway Action。

### 阶段 E：执行与实时结算

1. 选中臂通过 provider controller 发送命令；
2. 未选中臂按 hold/park 语义处理；
3. 每个 step 记录 qualified arm contact、qpos 偏差、阶段和 stop 状态；
4. close 后 attach 目标物体，release 后 detach 并增加 world revision；
5. 发现意外接触、状态漂移、stop、timeout 或输入变化时立即停止并 reset；
6. `unknown`/部分执行不能映射成 success。

### 阶段 F：语义验收与重规划

1. 保存 before/after 双臂状态和目标物体状态；
2. 独立 Verifier 判断 grasp、lift、placement、support 和 retreat 语义；
3. 发生失败时输出 `ReplanDelta`：保留/取消/失效节点、需要的新 observation/state/collision evidence；
4. Coordinator 创建新的 PlanRevision；旧 route 不继续复用；
5. Experience 只从完整、可归因且经过语义验证的 episode 学习 arm assignment、Tool 顺序和 hold/park 策略。

## 7. 当前问题与实现顺序

当前 probe 暴露的是证据和双臂建模缺口，不是“再换一个 candidate”或“调速度”的问题。实现顺序应为：

1. 修正 RoboTwin adapter 的 qualified arm/link identity；
2. 物化并绑定 `DualArmExecutionState`；
3. 将另一只机械臂的初始/park 几何加入 Curobo world projection；
4. 增加 hold/park route contract 和 per-arm drift evidence；
5. 重新生成 route-request 与 collision-world；
6. 做 no-motion readiness 和接触归因测试；
7. 生成新的 simulation-only review package 并重新取得人工批准；
8. 运行 probe，确认完整路线和语义 evidence 后，再进入多物体 DAG 评测。

## 8. 审核清单（五维 + 反过度防御）

### 架构集成

- 双臂状态、link geometry 和 inter-arm projection 位于 RoboTwin adapter/provider；
- planning 只校验引用、依赖、资源和 admission；
- Task/Revision 仍由 PAOS Coordinator/SQLite 管理；
- Gateway 仍是正式动作唯一执行面。

### 失败路径

- 初始状态缺失或漂移；
- link identity 无法区分左右臂；
- hold/park readiness 缺失；
- inter-arm collision、table/object contact；
- stale world revision、attach/detach 不一致；
- partial/unknown/stop/timeout 和 reset 失败。

### 权威边界

- observation 是观测事实；
- dual-arm projection 是 provider 计算；
- planner/contact 是 readiness 或执行 evidence；
- Verifier 负责语义 verdict；
- candidate score、DAG 或 contact trace 不授予 motion authority。

### 配置与 provenance

- 初始状态、另一臂 geometry、world revision、frame、calibration 和 route 都可追溯；
- 不把方块坐标、Curobo 参数或臂侧规则写入 PAOS Core/Skill；
- 不复用旧 route approval。

### 可维护性

- provider identity、状态投影、碰撞投影和 contact normalization 分层；
- sequential 与 atomic bimanual 明确区分；
- route contract 可被其他双臂 simulator/provider 实现。

### 防止过度防御编程

- 只为已观察到的具体失败增加验证：左右 link 归因、初始状态漂移、另一臂碰撞；
- 不新增无失败证据支撑的速度常数、重复哈希、第二套 gate 或额外状态机；
- 证据不足时返回明确 `unavailable`，不通过堆叠检查掩盖根因。

## 9. 验收门槛

在以下证据完成前，不能宣称双臂抓取放置路线可用：

1. qualified left/right link contact evidence；
2. reset/stabilization 后双臂初始状态 artifact；
3. 另一只机械臂进入 planner collision world 的 receipt；
4. hold 或 park 的 readiness 与漂移证据；
5. attached-object 与 inter-arm collision evidence；
6. 完整 route 的 lift/transport/descent/release/retreat evidence；
7. before/after snapshot 与独立 semantic verdict；
8. 新 route package 的人工 simulation-only approval。

只有这些条件全部满足，才可以对 blocks-ranking 或后续多物体任务进行正式 DAG 评测。

## 10. 按 PAOS 开发者指南复核后的调整

本方案与 `docs/zh/03-developer-manual.md` 第 12 节和 Manipulation/benchmark 扩展边界逐项对齐：

1. **不新增 provider-specific Agent Tool。** 双臂规划能力由现有 provider-neutral `manipulation.prepare` Query 消费；`DualArmPlannerPort` 是 adapter/provider 内部 port，不暴露 `curobo.plan`、`moveit.plan` 或 `drake.plan` 给 Agent。只有通用 task/Tool API 无法表达的能力，才有理由新增公共 ToolSpec。
2. **不创建第二套执行协议。** PlanGraph/PlanRevision 仍是 PAOS 任务事实；Skill 中的 `WORKFLOW_DAG` 只是只读 policy projection；Gateway ToolSpec、`max_concurrency`、pending/cancel/stop/unknown 和 invocation 仍按现有 Forge API 处理。
3. **仿真器细节留在独立 runtime。** RoboTwin task、SAPIEN actor、Franka embodiment、Curobo/MoveIt/Drake 配置、link identity 和 benchmark 参数只能出现在 EnvironmentAdapter、provider port 和 profile；不能进入 PAOS Core、公共 Skill 或 Agent prompt。
4. **联合规划结果不是动作授权。** readiness provider 只产生 route/collision/capability evidence；正式动作仍必须经 Gateway Action/Session admission。simulation-only probe 是独立验证路径，不代表 Gateway ready。
5. **替换 provider 不改上层语义。** Curobo、MoveIt 2 或 Drake 通过同一组 provider-neutral `DualArmPlanRequest`/result projection 接入；替换 provider 只改变 adapter/profile 和 evidence，不复制 Skill、PlanGraph 或 PAOS lifecycle。
6. **测试顺序遵循开发者指南。** 先做 ToolSpec/Fake Gateway conformance 和 planning pure tests，再做 adapter no-motion projection/readiness，最后在完整 runtime/Tool context ready 且有新 approval 时做 simulation/hardware acceptance。

### 指南约束下的最终分层

```text
Agent
  → provider-neutral Skill / semantic PlanGraph
  → manipulation.prepare Query
  → adapter DualArmPlannerPort
  → Curobo | MoveIt 2 | Drake | other provider
  → readiness evidence
  → planning admission
  → Gateway Action/Session (formal execution only)
```

这里的关键是：Agent 进化的是“何时选择哪种合法规划模式、候选、臂分配和重规划策略”，而不是直接进化 Curobo 参数或绕过 Gateway。PAOS 只新增稳定的 provider port/projection seam，不新增第二个 scheduler、planner runtime 或状态数据库。

## 11. v6.8.6 实现落点与当前边界

本轮已将近期目标落到 RoboTwin provider 侧，未改变 PAOS Core 的任务生命周期或 Gateway 执行协议：

- `robotwin20_adapter.dual_arm_state` 提供不可执行的 `DualArmPlanningState` 与 peer-arm projection 纯模型。它绑定 scene/state revision、world frame、左右 qpos/drive target、夹爪状态和 `left:<link>` / `right:<link>` qualified identity，并提供 hold drift 测量；`motion_authorized` 固定为 `false`。
- `robotwin_curobo_world_port.apply_collision_world` 接收每个选中臂对应的 peer projection，将另一臂碰撞盒转换到该 planner 的 base frame，再复用 Curobo `WorldConfig`/`update_world` 或容量不足时的现有 MotionGen rebuild。该 port 不执行 `scene.step()`，不向 Agent 暴露 Curobo Tool。
- simulation probe 在 reset 后捕获双臂状态；每个 simulator step 检查 held arm 的 drive target 是否漂移；contact trace 对重复的 RoboTwin link 名称使用 qualified arm identity，无法唯一归因时保留 `ambiguous:*`，并继续 fail-closed。
- 选中臂仍按现有 provider route 执行，另一臂当前采用 `hold` 语义；尚未实现 park route、combined-robot synchronized trajectory、inter-arm swept-volume 动态证明或 Gateway atomic bundle。

因此本轮完成的是“顺序双臂的状态绑定 + peer-arm 静态碰撞投影 + 接触归因基础”，不是完整双臂动作成功证明。要进入新的 simulation-only probe，必须重新生成包含双臂状态/peer projection 的 route package 并取得与新 worker 源码绑定的人工批准；既有 approval 不能复用。

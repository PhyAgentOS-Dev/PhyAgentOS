# RoboTwin Adapter Refactor Diagnosis

> 诊断日期：2026-09-02
> 适用基线：PAOS v1.0.0、Forge Tool API、当前 `feature/long-horizon-workflow` 分支

## 1. 结论

Hephaestus 中已有观察、场景理解、抓取候选、几何准入、获取和放置等真实能力，但本次迁移不应把
Hephaestus 源码复制到 PAOS，也不应把六个 ToolEndpoint 全部放入一个 RoboTwin 专属 workspace。

正确目标是：保留 PAOS 的 provider-neutral ToolSpec，在独立的 capability runtime 中实现通用 ToolEndpoint
语义，以抽象 provider port 调用环境实现；RoboTwin 2.0 只是一个可替换的 `EnvironmentAdapter` profile。

```text
ForgeToolClient
  → Generic Gateway Tool API
  → Generic ToolEndpoint
  → Capability Runtime
  → Provider Port
  → EnvironmentAdapter(profile=robotwin20|maniskill|replay|...)
  → Dora
  → robot/simulator
```

这样同一组 ToolSpec、`pick-place-workflow` Skill workflow、AgentTask、verification 和 experience 可以跨 RoboTwin、ManiSkill、
回放或其他环境复用。

这里的“复用”不意味着把仿真器的内部真值当成感知结果。RoboTwin/SAPIEN 的 actor/entity 列表、
segmentation、object metadata、精确 pose 和 `check_success()` 都是仿真内部事实，只能用于仿真调试、
对照或验收证据；它们不能填充面向真实物理世界的 observation/understanding 输出，也不能授予动作准入。
真实世界的观察必须来自相机、深度、力/触觉或其他明确声明的传感器，场景理解必须由独立的 perception
provider 从这些观测 artifacts 推断，并保留传感器 provenance、时间戳、frame 和 calibration。

## 2. 规范依据

- [PAOS framework introduction](../en/01-framework-introduction.md#2-one-physical-execution-plane)：认知规划、
  Gateway 执行、ToolEndpoint/Dora/robot-simulator 物理链路分离；RoboTwin 位于末端 runtime。
- [PAOS developer manual](../en/03-developer-manual.md#12-extension-workflows)：先发布 provider-neutral
  ToolSpec，再实现 ToolEndpoint/Fake Gateway、adapter、Bundle/profile 和仿真验收。
- [Integration development guide](../user_development_guide/README_en.md#1-choose-the-integration-point)：
  机器人能力使用 Gateway Query/Action/Session ToolSpec + ToolEndpoint；仿真器参数留在 adapter/profile。
- [Forge Tool API contract](README.md#1-execution-boundary)：Gateway 是物理执行 owner；PAOS 保存 binding、
  task 和验证语义，不接管物理真值。
- Hephaestus 外部参考：`/home/yanxu/Hephaestus/docs/adr/0003-tool-embodiment-environment-adapter-boundaries.md`
  （当前仍为 proposed）：环境差异由 `CapabilityProfile`/`EmbodimentAdapter`/`EnvironmentManager`
  持有，canonical runtime 保持 admission、safety、execution 和 physical truth 的唯一所有权。

## 3. 术语和所有权

| 概念 | 责任方 | 不应承担的职责 |
|---|---|---|
| Skill (`pick-place-workflow`) | PAOS SkillsLoader/Skill Runtime | 只描述六步通用工作流；不包含 RoboTwin task、SAPIEN API、仿真真值或控制器代码 |
| ToolSpec | PAOS/Forge contract | 不暴露 provider、embodiment 或 benchmark 字段 |
| Generic ToolEndpoint | capability runtime/Gateway | 不直接解析某个仿真器对象 |
| Provider Port | capability runtime | 不拥有 HTTP、AgentTask 或 Skill 生命周期 |
| EnvironmentAdapter | 独立环境 runtime | 只管理环境生命周期和 Port 实现；不得把仿真真值伪装成真实感知或改变公共 ToolSpec/PAOS task/verdict |
| Gateway | 执行面 | 不定义用户级任务成功 |
| AgentTask | PAOS | 不直接执行机器人或仿真器 |
| Verification | PAOS | 不把 simulator `check_success()` 单独当作用户级 verdict |

## 4. 被否定的布局

以下布局不采用：

```text
paos-robotwin-adapter/
└── endpoints/
    ├── scene_observe.py
    ├── scene_understand.py
    ├── grasp_propose.py
    ├── manipulation_prepare.py
    ├── object_acquire.py
    └── object_place.py
```

问题不是目录名称本身，而是六个公共能力的实现边界会被 RoboTwin 任务和 API 牵引，最终产生：

1. `scene.observe` 等公共能力与 RoboTwin 绑定；
2. 未来 ManiSkill、replay、其他 simulator 重复实现相同 ToolEndpoint；
3. Skill、ToolSpec、Gateway 和环境配置发生语义泄漏；
4. 通过修改 tool_id 或 Skill 名称表达环境选择；
5. PAOS Agent 需要知道 provider-specific payload。

## 5. 目标分层

### 5.1 Public contract

保留六个稳定 ToolSpec：

```text
scene.observe          Query
scene.understand       Query
grasp.propose          Query
manipulation.prepare   Query
object.acquire         Action
object.place           Action
```

ToolSpec 只冻结 schema、binding、frame/unit、readiness、错误和生命周期语义。

### 5.2 Generic capability runtime

通用 runtime 可以按能力组织模块，但模块不能导入 RoboTwin 或 SAPIEN：

```text
capability_runtime/
├── observation.py
├── understanding.py
├── grasp_proposal.py
├── manipulation_preparation.py
├── acquire.py
└── place.py
ports/
├── observation_source.py
├── scene_understanding.py
├── grasp_provider.py
├── readiness_evaluator.py
└── manipulation_executor.py
```

这些模块负责公共输入验证、结果投影、provenance、错误分类、Query/Action 生命周期和 no-blind-retry
语义。

### 5.3 Environment adapter

环境适配器只实现 Port 和环境生命周期：

```text
environment_adapters/
├── robotwin20/
│   ├── environment.py
│   ├── observation_source.py
│   ├── scene_state.py
│   ├── embodiment.py
│   └── profile.yaml
├── maniskill/
└── replay/
```

RoboTwin task、SAPIEN scene、embodiment、benchmark、camera 名称和内部句柄都留在
`environment_adapters/robotwin20` 及其 profile。adapter 可以读取这些事实来驱动仿真和产生
对照证据，但公共 `scene.observe`/`scene.understand` 必须经过真实传感器/感知 Port；不得直接把
actor/entity、segmentation 或 object metadata 当作现实感知结果。

## 6. 六个能力的重构 seam

| ToolSpec | 通用 runtime 重新实现 | 环境 Port |
|---|---|---|
| `scene.observe` | freshness、frame、calibration、artifact、scene revision、结果 schema | `ObservationSource.capture()` |
| `scene.understand` | entity/relation schema、confidence、provenance、observation binding | `SceneUnderstandingProvider.understand()` |
| `grasp.propose` | candidate-set identity、候选规范化、绑定和 provenance | `GraspProposalProvider.propose()` |
| `manipulation.prepare` | workspace/kinematic/collision 三项结果编排、prepared 语义 | `ReadinessEvaluator.evaluate()` |
| `object.acquire` | Action admission、invocation、phase summary、cancel/unknown | `ManipulationExecutor.acquire()` |
| `object.place` | destination binding、release/retreat、post-release evidence | `ManipulationExecutor.place()` |

`scene.observe`、`scene.understand`、`grasp.propose`、`manipulation.prepare` 都保持 Query；只有
`object.acquire` 和 `object.place` 创建标准 Action invocation。

## 7. Hephaestus 的使用边界

Hephaestus 代码不作为新 runtime 的依赖，也不直接复制到 PAOS。可使用的只有：

- 已验证行为和输入输出语义；
- failure family、safety gate 和证据要求；
- 现有测试揭示的边界条件；
- RoboTwin/ManiSkill 运行实验作为验收参考。

不得直接依赖或搬运：

- Hephaestus `ToolRegistry`；
- `ManiSkillBackend` 私有执行路径；
- `AcquireObjectExecutor`/`RelocateObjectExecutor` 类实现；
- Hephaestus receipt、state store 或 CLI execution path；
- Hephaestus provider-specific payload。

新实现必须通过 PAOS ToolSpec 和独立 adapter contract 验证，而不是通过“旧代码可运行”证明兼容。

## 8. Skill 和 profile 设计

推荐使用名为 `pick-place-workflow` 的 provider-neutral workflow Skill，内部声明六个 ToolSpec：

```yaml
required_tools:
  - scene.observe
  - scene.understand
  - grasp.propose
  - manipulation.prepare
  - object.acquire
  - object.place
```

环境通过 profile 选择，Skill 名称不随环境变化：

```text
pick-place-workflow + profile=robotwin20
pick-place-workflow + profile=maniskill
pick-place-workflow + profile=replay
```

禁止使用以下模式：

```text
robotwin2-pick-place-workflow
maniskill-pick-place-workflow
robotwin_grasp_propose
```

如果第一阶段只有 `scene.observe`，必须使用 `required_tools: [scene.observe]` 的中性 Bundle/profile，
不能把单能力 runtime 塞进当前声明六个 required Tools 的 Bundle。

## 9. 推荐实施顺序

1. **冻结 ToolSpec**：从现有 PAOS contracts 建立 schema、binding、readiness 和 failure matrix。
2. **先写 Fake Gateway conformance**：覆盖 discovery、context、Query/Action route、identity、unknown、
   cancel/stop、并发和 no-blind-retry。
3. **实现 generic capability runtime**：不连接任何仿真器，先完成六个 ToolEndpoint 的公共生命周期。
4. **定义 EnvironmentAdapter Port**：只包含 reset/seed/snapshot、observation、scene state 和经过验证的
   execution seam，不泄漏 PAOS task 或 provider payload。
5. **实现 RoboTwin20 adapter**：在独立 `RoboTwin20` 环境中接入 task、SAPIEN、camera 和 embodiment；不修改
   PAOS ToolSpec。仿真 actor/entity、segmentation、object metadata 和内部 pose 只作为仿真辅助/对照事实。
6. **先打通真实传感器 observation**：`scene.observe` 只做 Query，验证 camera/depth/state 传感器输出、frame、
   calibration、freshness 和 artifact；不得用仿真 ground truth 代替传感器观测。
7. **依次接入 understand、propose、prepare**：每个能力先 adapter 单测，再真实 Gateway conformance。
8. **最后接入 acquire/place**：沿用标准 Action invocation/status/result/cancel，内部 phase 不暴露给 Agent。
9. **添加 Dora profile 和 locked Node**：Bundle 只冻结 wiring、profile、Node artifact 和 digest。
10. **完整仿真验收**：记录 RoboTwin commit、SAPIEN/Dora 版本、Bundle/Node digest、profile 和环境摘要。

### 9.1 两条感知接入方案的统一决策

前述单视角链路和多视角融合不是两个 Skill，也不是两个 RoboTwin 专属 Tool。它们共享 PAOS 的
`scene.observe`、`scene.understand`、`grasp.propose` 和 `manipulation.prepare` contract；差异只由
adapter/provider profile 和 capability negotiation 表达。Agent 不传 `LocateAnything`、`SAM2`、
`NVBlox` 或具体模型名，也不直接选择摄像头实现。

#### 方案 A：单视角局部感知（默认首个实现）

```text
scene.observe(sensor_ref, max_age_ms)
  -> entity binding / semantic query
  -> LocateAnything proposal (2D boxes)
  -> SAM2 mask materialization (当前 RGB)
  -> depth + intrinsics/extrinsics localization
  -> entity spatial envelope / optional pose artifact
  -> grasp.propose
  -> manipulation.prepare
```

适用条件：目标主要可见、单个 RGB-D 视角足够、需要较低延迟或 GPU 资源有限。它在一个 observation
上完成局部实体证据，输出 `entities`、`relations`、`spatial_envelopes` 和已绑定的
`derived_artifacts`。generic runtime 已冻结 instance mask、object point cloud 和 metric localization
的中性契约；adapter 可以投影这些引用，但不输出仿真 actor identity，不直接产生抓取动作。

adapter 需要实现三个独立 port：

```python
class ProposalProvider(Protocol):
    def propose(self, request: ProposalRequest) -> ProposalBatch: ...

class SegmentationProvider(Protocol):
    def segment(self, request: SegmentationRequest) -> MaskBatch: ...

class MetricLocalizationProvider(Protocol):
    def localize(self, request: LocalizationRequest) -> SpatialEstimate: ...
```

LocateAnything 和 SAM2 的 worker 生命周期、Torch/CUDA、模型 revision、license、临时文件和 cleanup
只在 adapter 中管理。PAOS 只校验 artifact、frame、calibration、provenance 和结果 schema。

#### 方案 B：多视角观测集与几何融合（遮挡/覆盖需要时启用）

```text
scene.observe(observation_set_ref, max_age_ms)
  -> MultiViewObservationSet
  -> per-view proposal/mask (可复用方案 A provider)
  -> cross-view identity / mask correspondence gate
  -> fused entity mask + RGB-D geometry
  -> scene.understand projects entity evidence
  -> grasp.propose consumes fused entity geometry
  -> optional global SceneGeometry for manipulation.prepare
```

适用条件：单视角遮挡、视野覆盖不足、需要更完整的目标分割、实体点云、抓取几何或全局碰撞/unknown-space
几何。多视角不仅可以改善全局地图，也可以直接改善目标分割感知：每个视角可独立产生 proposal/mask，
或由一个视角的已绑定 proposal 投影到其他视角，再通过跨视角 identity/correspondence gate 合并为同一实体
的 mask 与 RGB-D 几何。多视角必须先形成 provider-neutral `MultiViewObservationSet`，每个 view 绑定同一
`scene_revision`、reset/control-step identity、timestamp、camera frame、intrinsics、extrinsics 和 artifact digest。

多视角 provider 至少可以产生两类可分别消费的输出：

| 输出 | 消费者 | 语义 |
|---|---|---|
| `FusedEntityPerceptionArtifact` | `scene.understand`、`grasp.propose` | 某个已绑定实体的跨视角 mask、对应关系和融合 RGB-D 点云；可用于抓取候选，但不能升级为全局碰撞图 |
| `GlobalSceneGeometryReference` | `manipulation.prepare` / planner | 完整 RGB-D 视图积分后的场景几何、自由空间和 unknown-space 证据；不是目标分割结果 |

上述两个名称是 provider-neutral artifact 类型。其中 `scene.understand` 现已发布并校验
`derived_artifacts`；但多视角 `MultiViewObservationSet` 尚未注册，`grasp.propose` 仍只接受带
`spatial_envelope` 的 target，`manipulation.prepare` 也没有 `GlobalSceneGeometryReference` 输入。
因此跨视角融合结果和全局场景几何在对应 generic contract 扩展前不能私自增加请求字段。

多视角感知 provider 可以复用方案 A 的 LocateAnything/SAM2：LocateAnything 仍只产生 proposal，SAM2
仍只产生当前视角 mask；跨视角的实体 correspondence、mask 合并、深度投影和点云融合由 adapter-side
composition provider 负责。不能把每个实体 mask 的并集当成全局 SceneGeometry；全局几何必须消费完整
depth frames 和标定后的射线。provider 需实现有序
`begin_session → process(view_i) → fuse_entity → (optional) freeze_global_snapshot → close_session`
生命周期，任何 view 丢失、revision/calibration 不一致、identity/mask correspondence 不确定、
session/digest/count 不匹配都必须 fail-closed。

#### 方案选择与迁移顺序

1. 先实现方案 A 的 Fake provider 和单视角真实 adapter，验证 proposal、mask、depth localization、
   provenance 和 `scene.understand` 投影。
2. 当单视角在遮挡、分割质量或 coverage gate 上不足时，再增加方案 B 的 `MultiViewObservationSet`
   contract；保持单视角调用兼容，不复制 ToolEndpoint。
3. 先实现跨视角 identity/mask correspondence 和 `FusedEntityPerceptionArtifact`，供
   `scene.understand` / `grasp.propose` 使用；再按需要实现全局 SceneGeometry 供 `manipulation.prepare`
   使用，二者分别验收，不能用一个 artifact 代替另一个。
4. 若多视角需要移动相机或机器人采集新视角，该动作必须另行经过 Gateway/Runtime safety admission；
   provider 不能隐式移动硬件。
5. 两个方案都必须保持 `motion_authorized=false`，直到标准 `manipulation.prepare` 和后续 Action
   admission 完成；模型成功、mask 成功或融合成功本身都不是抓取成功。

#### 方案对照与验收门禁

| 维度 | 方案 A：单视角 | 方案 B：多视角 |
|---|---|---|
| PAOS 对外入口 | 现有 `scene.observe` + `scene.understand` | 未来扩展同一入口为 capability-gated observation set；当前尚未注册多视角字段 |
| 主要结果 | 当前视角实体/mask/空间包络 | 跨视角实体分割/几何 + 可选全局 SceneGeometry |
| 主要风险 | 遮挡、深度空洞、单视角身份歧义 | 跨视角身份漂移、mask correspondence 错配、标定/时间不一致、资源占用 |
| 必须证明 | RGB/depth 对齐、mask shape、frame/calibration/provenance | view identity、顺序、digest、integration count、单次 freeze |
| 失败语义 | provider unavailable/invalid，不能伪造 3D | typed multi-view unavailable/mismatch，不能静默降级单视角 |
| 动作权限 | 始终无动作 | 始终无动作 |

本仓库已按方案 A 实现 adapter-side composition 和三类派生资产投影：GPT provider
提供 RGB 语义实体，LocateAnything 和 SAM2 由各自独立环境通过 profile 指定的 JSONL
worker 协议调用，depth localization 在 adapter 中确定性执行。代码、Fake Gateway、worker 协议和一次
无动作 live composition 均已验收：LocateAnything 在已有 RoboTwin RGB 上返回唯一 `red block`
proposal，SAM2 返回同尺寸 mask，depth localization 生成 788 个 camera-frame 点。本次以固定语义
实体作为 composition 上游，不代表再次验收 GPT 调用，也不代表抓取成功。方案 B 作为同一
provider-neutral contract 上的增量 capability，待单视角 live
证据稳定后再实现。它的第一目标是跨视角分割/实体几何可被 `grasp.propose`
消费，全局 SceneGeometry 是独立后续输出。两者都不应命名为 `robotwin.multiview` 或
`multiview-skill`。

### 9.2 按 PAOS 架构与开发者指南的审核结论

**通过项：**

- 两个方案都沿用 `ForgeToolClient → Gateway Tool API → ToolEndpoint → Dora → adapter/provider`，没有
  direct Agent-to-model、Agent-to-Dora 或 Agent-to-SDK 路径。
- 按开发者指南“只有现有通用 Tool 无法表达能力时才新增 Agent tool”的规则，多视角目前可以表达为
  `scene.observe` 的 capability-gated observation set 和 provider 内部 composition，因此没有新增
  `multiview` ToolSpec 或 Skill。
- 多视角没有被命名为 Skill，也没有把 LocateAnything、SAM2、NVBlox、FoundationPose 写入公共
  `ToolSpec`；环境差异仍由 adapter/profile 和 capability descriptor 表达。
- 单视角和多视角都把感知、几何、准入、执行分开；mask/点云/融合结果只能作为 Query 证据，不能
  跳过 `grasp.propose`、`manipulation.prepare` 或 Action admission。
- 方案 B 明确区分跨视角实体分割/几何与全局 SceneGeometry，前者可以供 `grasp.propose` 生成抓取
  候选，后者才供规划/准入使用；不能互相替代。

**必须先补齐的 contract 缺口：**

1. 当前 `scene.observe` 只接受单个 `sensor_ref`，尚未实现 `MultiViewObservationSet`。在增加多视角
   调用前，应先冻结兼容的 provider-neutral schema（ordered view refs、scene/reset/control-step identity、
   per-view frame/calibration/artifact digests），并通过 Fake Gateway conformance；不能在 adapter 中
   私自增加未注册字段。
2. `scene.understand` 现已增加并校验 provider-neutral `derived_artifacts`（实例 mask、目标点云、度量定位）
   及其 observation/entity/frame/calibration/source/provenance 绑定。多视角 `MultiViewObservationSet` 和
   `GlobalSceneGeometryReference` 仍未注册；融合结果在对应 contract 扩展前不能私自增加请求字段。
3. 当前 `provenance` 正则只接受 `artifact://...`。`calibration://...` 应继续放在顶层
   `calibration_ref` 或一个明确的 calibration artifact ref 中，不能直接塞进现有 spatial-envelope
   provenance，否则会被 PAOS validator 拒绝。示例中的 calibration 绑定必须按此规则实现。
4. `scene.understand`、`grasp.propose` 当前都是 Query；多视角 provider 不得隐式移动相机/机器人。需要
   主动移动采集时，必须另行定义并审核一个有安全准入的 observation Action/Session。
5. 当前 `grasp.propose` 的 target 只允许 `spatial_envelope`，`manipulation.prepare` 没有全局场景几何输入。
   若要让融合实体几何或 `GlobalSceneGeometryReference` 成为公共证据，必须先扩展通用 artifact/reference
   schema、binding、provenance 和 Fake Gateway conformance；否则只能由 adapter 将已验证结果投影为现有
   中性 envelope，且不得把全局几何或 mask 并集冒充目标/碰撞事实。

**实施门禁：**

- 已以 Fake provider 证明单视角派生 artifact：proposal→mask→depth localization 的 lineage 和
  fail-closed 语义；下一步应让 `grasp.propose` 消费正式绑定的几何 artifact。
- 再以 Fake provider 证明多视角：两视角以上、稳定顺序、同一 revision/calibration、跨视角 identity/mask
  correspondence、融合 artifact digest，以及失败时不静默降级为单视角。
- 然后在独立 RoboTwin adapter 环境接入真实 LocateAnything/SAM2 worker；PAOS 环境不安装 Torch、CUDA、
  模型或仿真依赖。
- 只有真实多视角 artifact、provider receipt、资源/cleanup 证据和 Gateway/Dora readiness 全部存在后，
  才能进行仿真验收；任何阶段都保持 `motion_authorized=false`，不把分割或融合成功称为抓取成功。

### 9.3 PAOS 状态文件协议审核与实施方向

近期对 `TARGETS.md`、`SKILLRUNTIME.md`、`SESSIONS.md`、`ENVIRONMENT.md` 和 `LESSONS.md` 的架构诊断已
单独记录在 [`PAOS_STATE_FILE_ARCHITECTURE_DIAGNOSIS.md`](PAOS_STATE_FILE_ARCHITECTURE_DIAGNOSIS.md)。该诊断
与本执行文档的结论一致：PAOS v1.0 没有要求用 Markdown 存储事务性中间状态，并明确将旧的 Markdown queue
Runtime 视为已移除。Markdown 文件可以作为人工输入、工作区上下文或机器事实源的可读 projection，但不得
成为第二套执行状态机或事实源。

因此，RoboTwin 和 `pick-place-workflow` 的后续实现采用以下顺序：

1. 先冻结 Capability Profile、AgentTask、Gateway invocation、Evidence Snapshot、Experience ledger 和
   五类文件的权威边界、身份、revision、provenance、幂等与 unknown/no-blind-retry 语义；
2. 先实现必要的无副作用文件边界：`ENVIRONMENT.md` 严格 projection，`TARGETS.md` shadow validation，
   `SESSIONS.md` parse/validate 与 AgentTask dry-run；`SKILLRUNTIME.md` 无生产 producer，Skill-scoped
   `LESSONS.md` 只由 Experience ledger 生成，均不是 PAOS 核心生命周期的前置条件；
3. 用 Fake Store、Fake Gateway 和回放样例验证未知字段、失败回滚、projection drift、幂等和 no-motion；
4. 只有人工确认且通过幂等校验后，`SESSIONS.md` 才能编译为 AgentTask，`TARGETS.md` 才能作为未来
   Capability Profile/admission 的候选输入；此时仍不得建立 Markdown queue Runtime 或触发物理动作；
5. 再继续实现 `grasp.propose → manipulation.prepare → object.acquire → object.place` 的 provider-neutral
   证据闭环，保持 Query/Action 分层和 `motion_authorized=false` 的 no-motion 门禁；
6. 只有文件适配和抓取放置都产生稳定的 AgentTask、Evidence、VerificationVerdict 和 failure-owner 后，
   才允许 LessonCluster 或 SkillCandidate 的受控晋升。

当前顺序审查状态：`SESSIONS.md` 的人工确认 promotion 和 `TARGETS.md` candidate promotion 已在
`v3.0.0`/阶段 C 落地，晚于它们的 replay/failure conformance 在 `v3.4.2` 才补齐。该历史先后没有
突破权限边界（promotion 仍受 digest、人工凭据、幂等、全局任务占用和 `motion_authorized=false`
约束），但后续不得在 replay/Evidence gate 完整关闭前扩大 promotion 范围。当前第二轮实现审查已记录在
[`STATE_FILE_IMPLEMENTATION_REVIEW_20260903.md`](STATE_FILE_IMPLEMENTATION_REVIEW_20260903.md)，并确认 generic
SKILLRUNTIME/LESSONS renderer 不属于已完成的生产模块。抓取放置步骤 5 和自主
进化步骤 6 当前均未启动。

本节批准“受限文件适配先行”，但不批准新增 Markdown queue Runtime，也不改变 PAOS 当前唯一物理执行路径。若后续实现需要主动移动采集、
新的目标能力约束或多视角输入，必须先扩展相应 provider-neutral contract、Fake Gateway conformance 和
审计证据，再接入具体 adapter。

## 10. 验收门禁

### 公共 contract gate

- ToolSpec 严格 schema 与 binding 通过；
- `/tools`、`/context` 可发现；
- Query/Action/Session 使用 PAOS 标准路由；
- invocation/attempt 与 PAOS task_id 分离；
- timeout/unknown 不盲目重发；
- cancel/stop 不虚构物理停止。

### 环境 gate

- `pick-place-workflow` Skill 名称与 ToolSpec 保持环境无关；RoboTwin 通过 profile 选择；
- RoboTwin task 可以在 `RoboTwin20` 环境启动；
- 需要的 assets 已完整；
- observation source 能读取真实 RGB/depth/state 传感器输出；仿真真值仅作为独立对照，不进入公共感知结果；
- frame、calibration、scene revision 可确定；
- adapter 不向 PAOS 暴露 RoboTwin 私有字段；
- acquire/place 只有显式 Action admission 后才能执行。

### Runtime gate

- Dora flow 可由 RuntimeManager 启动；
- Gateway `/tools` ready；
- 全部 `required_tools` contexts ready；
- Bundle/Node digest 可复核；
- 从干净 PAOS 环境完成 install/start/status/stop；
- 真实仿真结果与 PAOS ToolResult、evidence、verification 记录可对齐。

## 11. 当前审核结论

当前 PAOS 仓库已经具备：

- 六个 provider-neutral ToolSpec；
- 一个职责明确的 `pick-place-workflow` Skill，用于编排六个 Tool，而不是把六个能力误称为六个 Skill；
- Fake Gateway 和 no-motion conformance；
- v1.0 所要求的独立 generic capability runtime 基础实现：ToolEndpoint 注册、发现/context、Query 分发、
  bounded Action invocation bookkeeping 和 provider-port 协议；该实现不依赖仿真器、YOLO、机器人 SDK、Dora
  或硬件，且不执行物理运动；
- `scene.understand` 的 provider-neutral `derived_artifacts` contract：支持 instance mask、object point cloud
  和 metric localization 的类型、绑定、派生 lineage、descriptor 校验与 Fake Gateway conformance；该 Query
  仍不授权运动；
- adapter-side 单视角感知 composition：按语义实体调用 LocateAnything proposal worker，先关闭并
  释放 proposal 进程，再启动 SAM2 box segmentation worker，最后用同帧 depth/intrinsics 生成
  camera-frame point cloud 与 spatial envelope。两个模型保留在独立 Python 环境，路径、revision、
  checkpoint、device 和 timeout 由 `profiles/robotwin20/perception.yaml` 注入；
- adapter-side 已新增独立 `GraspGenProposalProvider`、JSONL worker 入口和 `graspgen.yaml` profile：provider port
  只依赖通用 `PointCloudArtifactResolver`，不依赖 RoboTwin/SAPIEN 类型；RoboTwin adapter 只负责产生并绑定
  observation geometry artifacts。它只消费
  `scene.understand` 产生并绑定到 observation/revision/frame/calibration/entity 的
  `object_point_cloud` 或 `fused_entity_perception` artifact，校验 4x4 矩阵、四元数、approach vector，
  生成 provider-neutral candidate funnel，并通过确定性 SE(3) NMS 投影 `grasp.propose`。这仍是 Query 证据，
  不执行 IK、碰撞准入或动作；模型 checkpoint 和 Torch 环境必须由外部 profile 提供，缺失时 fail-closed。
  当前尚未在本机验证 GraspGen checkpoint 的 live inference，Fake worker 结果不代表真实抓取完成。真实场景理解的
  adapter-side GPT Responses provider 已按 clean-room 方式实现：它只读取外部 observation artifact，
输出闭合的 entities/relations/spatial_envelopes/derived_artifacts/ambiguities schema，并由 PAOS Gateway 做最终校验；
  provider 默认沿用 Hephaestus 已验证的 `gpt-5.6-sol`、Responses API 和 relay base URL，但不导入
  Hephaestus。当前已用外部 `CUSTOM_API_KEY` 完成真实 GPT 路径验收；RGB-only 输入返回了语义实体/关系，
  没有生成 metric spatial envelope，且不确定性标记被保留。由于请求没有 depth/calibration，metric 几何仍按
  contract 不可用，不能把模型的 2D 视觉判断当作 3D 定位。
  strict schema 中 `unit` 也已声明 `type: string`，避免 Responses API 在请求阶段拒绝 schema；
- 独立 `examples/forge-adapters/robotwin20` adapter/runtime：环境 reset/snapshot seam、注入式
  `RoboTwinSensorBackend`、camera/depth/state artifact 校验、`RoboTwinObservationProvider` 和
  provider-neutral `scene.observe` snapshot；外部 RoboTwin20 Python 3.10 runtime 已完成一次无动作
  RGB/depth/state capture。该包不进入 PAOS wheel、不依赖 RoboTwin/SAPIEN/Torch/YOLO，也不复制仿真资产；
- Skill Runtime、Bundle、binding、AgentTask、verification 和 experience 基础；
- 已修正 RoboTwin 不应绑定 Skill 的文档边界。

当前尚未具备：

- generic capability runtime 的 Gateway HTTP/Dora 生产 wiring、持久化 invocation backend 和完整 Action
  executor（当前仅有无仿真依赖的 in-process foundation）；
- RoboTwin20 到真实 Gateway/Dora 的跨进程 provider wiring（当前 runtime-only CLI 和 in-process
  provider conformance 已完成，但尚未启动生产 HTTP Gateway）；
- 真实 Gateway/ToolEndpoint HTTP server；
- RoboTwin 对应 Dora flow、locked Node 和 profile；
- `manipulation.prepare`、`object.acquire`、`object.place` 的真实 provider 接入与六能力 PAOS 端到端验证；
  `grasp.propose` 已完成 provider port、artifact binding、isolated worker protocol、Fake conformance 和 no-motion
  candidate projection，但尚未在本机 verified GraspGen checkpoint 上完成 live inference，也未接入模型碰撞筛选、IK
  或执行链；当前 GPT 语义 provider 与 LocateAnything/SAM2/depth composition 均已分别验收，
  但尚未在同一次调用中运行 GPT 语义到真实 mask/metric localization/grasp 的完整 live 链路。

EnvironmentAdapter 的 reset/snapshot 与 provider-neutral `scene.observe` 核心 seam 已完成代码级接入和 no-motion
边界验收：`ObservationEndpoint`、`OBSERVATION_TOOL_SPEC`、`ObservationSource` 以及 RoboTwin20 adapter 的
camera/depth/state 投影均已通过专项验证；ToolSpec 仍需由部署方显式注册，未隐式连接 Gateway 或硬件。

因此不能声称“六个 RoboTwin Skill 已接入”，也不能把 RoboTwin 的 ground truth 称为真实感知。准确表述是：

> PAOS 公共能力契约、`pick-place-workflow` 编排、generic capability runtime 基础、RoboTwin
> `scene.observe` runtime/provider conformance、adapter-side `scene.understand` GPT provider，以及独立环境
> LocateAnything/SAM2/depth 单视角 composition 的代码与协议验收已完成；GraspGen 目前完成
> provider-neutral adapter/worker conformance，Hephaestus 能力只作为 clean-room 重构的需求/行为参考。
> 当前尚缺 verified GraspGen checkpoint 的 live 证据、模型碰撞/后续准备执行 provider、真实 Gateway HTTP/Dora wiring，
> 以及 `scene.understand` 消费正式 observation/geometry artifact 的跨模块 conformance，必须继续按本文顺序独立实现。

## 12. 识别、分割、定位与抓取位姿的模块归属

这些是实现能力，不是新增 Skill，也不应通过 `robotwin2-*` 命名绑定到仿真环境。PAOS 对外仍只暴露六个
稳定 ToolSpec；模型、相机 SDK、点云库和 RoboTwin/SAPIEN 句柄留在 adapter/provider workspace。

| 后续能力 | 对外 ToolSpec | PAOS generic capability runtime | adapter/provider 实现 |
|---|---|---|---|
| RGB/depth/state 采集 | `scene.observe` | observation identity、freshness、frame、calibration、artifact 绑定 | `ObservationSource` / `EnvironmentAdapter` 读取真实传感器 |
| 目标识别/检测 | `scene.understand` | entity schema、confidence、provenance、observation binding | detector/VLM provider；不能使用 actor truth |
| 实例分割 | `scene.understand` | 校验并投影 opaque mask artifact 与 provenance | 独立 segmentation provider（YOLO/SAM 等），不使用仿真 segmentation truth |
| 3D 定位 | `scene.understand` | frame/unit/calibration 约束和 metric envelope 校验 | depth + calibration + mask/点云 localization provider；缺任一项 fail-closed |
| 多视角分割/实体几何融合 | `scene.understand` → `grasp.propose` | 校验 `MultiViewObservationSet`、跨视角 identity/mask lineage 和派生 artifact 引用 | per-view proposal/segmentation + correspondence/fusion provider；可输出融合 mask、点云和抓取几何 |
| 抓取位姿估计 | `grasp.propose` | candidate schema、候选集 identity、provenance 与 funnel | 独立 grasp proposal provider（可选 YOLO/GraspGen 等），只产候选，不授权动作 |
| IK/碰撞/工作空间准入 | `manipulation.prepare` | readiness 编排与 `motion_authorized=false` 边界 | `ReadinessEvaluator`，必须在执行前完成 |
| 实际抓取/放置 | `object.acquire` / `object.place` | Action admission 与 invocation 生命周期 | `ManipulationExecutor`；仅 Gateway 显式准入后执行 |

当前 GPT provider 仍只做 RGB 语义理解；可信分割和 metric 3D 不由 GPT 凭 RGB 猜测，而由
adapter 中已实现的 LocateAnything proposal、SAM2 box mask 和 depth/calibration localization composition 生成。
该路径已通过 Fake worker/Gateway 契约和真实 LocateAnything/SAM2 无动作 composition 验收；本次
composition 使用固定语义实体，仍需补充同次 GPT 语义全链 live 证据。`grasp.propose` 现在消费显式绑定的
`geometry_artifacts`（单视角或未来多视角融合点云）；抓取位姿不能塞进 `scene.observe` 或
`scene.understand` 的语义输出字段，候选只有在 `manipulation.prepare` 完成 workspace/IK/collision/readiness
后才可能进入 Action admission。

## 13. English summary

The migration must be a clean reimplementation of the capability boundary, not a code copy from Hephaestus.
Keep six stable provider-neutral ToolSpecs under one clearly named `pick-place-workflow` Skill. PAOS v1.0
still requires an independent generic capability runtime: implement generic ToolEndpoint semantics against
abstract provider ports, and place RoboTwin 2.0, SAPIEN, task, embodiment, benchmark, and simulator details in
a separate environment adapter selected by profile. Simulation actor/entity truth, segmentation, metadata, and
`check_success()` are comparison/acceptance facts, not real-world perception. Real deployment must use sensor
artifacts and replaceable perception providers. The same Skill and ToolSpecs must remain usable with RoboTwin,
ManiSkill, replay, or future hardware profiles.

The reviewed execution order deliberately starts with restricted file adapters: freeze the upper-layer and file
contracts, generate read-only projections, run `TARGETS.md` shadow validation, compile `SESSIONS.md` in dry-run mode,
and exercise replay/failure gates. Only after explicit approval and idempotent validation may file input be promoted
to AgentTask or future admission input. The pick-place evidence closure and guarded evolution follow afterwards;
these adapters never become a second execution protocol or a motion authority.

### 9.2 本体替换与当前执行门禁

本体替换属于 RoboTwin adapter profile，而不是公共 PAOS ToolSpec。profile
选择任务、单个原生双臂或两个单臂及间距，并绑定 robot/gripper、拓扑、
planner 和 readiness evidence digest。更换 benchmark 时只新增 profile；
PAOS 的 Skill、任务生命周期、Gateway contract 和经验事实源保持不变。

当前首个 profile 是 `blocks_ranking_rgb` 的双 Franka-Panda。它只允许
scene/observation no-motion 链路。必须先获得真实或独立验证的 readiness
worker evidence 并完成人工审核，才可进入 Action/Gateway wiring；不能因
上游 RoboTwin 支持 Franka 就宣称 PAOS 已完成 Franka policy 或抓取放置闭环。

## 14. SceneCollisionWorld 诊断复核与 provider 协议（2026-09-07）

### 五维审核结论

对“将已观测物体纳入 Curobo 碰撞世界”的诊断复核结果为：无 Blocker/Major，允许进入
协议设计；尚未实现，不构成动作准入。需要保留以下修订：

- 观测实体不是完整覆盖证明。builder 必须输出 coverage/`unknown_space` 状态；未知或
  遮挡区域、缺失 geometry/pose/frame/calibration 时 fail-closed。
- 目标排除是 route-phase 语义，而非永久豁免：approach/contact 使用显式允许接触；
  close 后使用 attached object；release 后 detach 并重新纳入静态世界。
- planning library 只计算 admission/stale/invalidation；`AgentLoop` 或
  `AgentTaskCoordinator` 负责创建新 `PlanRevision`，避免第二套生命周期。
- RoboTwin provider 同时维护 `motion_gen` 和 `motion_gen_batch`；二者必须加载同一
  world digest，不能只更新其中一个实例。

### Provider-owned artifact

建议由 `robotwin20_adapter.collision_world` 生成不可变 JSON artifact：

```yaml
schema_version: paos-robotwin20-collision-world/v1
scene_revision: blocks_ranking_rgb-0-1
world_revision: 3
route_frame_id: world
pose_convention: position_m + orientation_xyzw
source_scene_facts_ref: artifact://scene-facts/...
source_scene_facts_sha256: <sha256>
calibration_ref: artifact://calibration/...
planner_provider: curobo
planner_profile: franka-panda
coverage: complete|partial|unknown
obstacles:
  - entity_ref: entity://block-red-1
    geometry_ref: artifact://geometry/...
    geometry_sha256: <sha256>
    shape: cuboid
    half_extents_m: [.., .., ..]
    world_T_entity: {frame_id: world, position_m: [.., .., ..], orientation_xyzw: [.., .., .., ..]}
    state: static
    provenance: [artifact://...]
excluded_entities: [entity://block-green-1]
target_entity_ref: entity://block-green-1
obstacle_count: 2
cache_capacity: 2  # derived from this artifact's obstacle_count, not a global constant
world_digest: <sha256>
motion_authorized: false
```

The artifact must reject duplicate entity names, non-normalized quaternions, mixed scene or
frame revisions, non-finite dimensions, and a target appearing in both static and attached
sets. `coverage=partial|unknown` is never sufficient for `manipulation.prepare` readiness.

### Adapter implementation seam

```text
robotwin20_adapter/collision_world.py   # pure validation/projection; no Curobo import
runtime/CuroboWorldPort                 # WorldConfig and dual MotionGen update
route_readiness.py                      # artifact/digest/revision admission
robotwin_simulation_probe_worker.py     # scene.step, contacts, detach/reset evidence
PhyAgentOS/planning                     # generic evidence/admission only
```

`CuroboWorldPort` may either initialize MotionGen with the complete world or call
`update_world()` when the preallocated cache capacity is sufficient. It must record an update
receipt for each arm and invalidate routes on `world_revision` drift. The target obstacle is
phase-scoped; after another arm changes the scene, both projections are rebuilt and old
readiness becomes stale.

### English summary

The provider projection is a `manipulation.prepare` dependency, not a new Skill or an Agent-
visible Curobo tool. Unknown-space coverage, phase-scoped target exclusion, synchronized
updates of both MotionGen instances, and revision/digest invalidation are mandatory. PAOS
planning remains provider-neutral and motionless; Gateway remains the sole production execution
authority.

### v6.8.1 cache-capacity implementation update (2026-09-07)

真实 RoboTwin/Curobo no-motion probe 已验证原生 planner 的 collision cache 问题：原始
`CuroboPlanner` 只用 table 初始化，`MotionGen.collision_cache` 在运行时没有足够的 OBB
容量，直接 `update_world()` 加入 red/blue 会抛出 Curobo 的 cache overflow，而不是安全地
忽略障碍物。该失败不能通过换 candidate、调速或放宽碰撞规则解决。

修复位于 `runtime/robotwin_curobo_world_port.py`：provider 先读取两个 arm 的实际 OBB
capacity；容量满足时更新两个 arm 的 `motion_gen` 和 `motion_gen_batch`；容量不足时，
按 RoboTwin 已有的 `yml_path`、插值和 seed 配置，用完整 `WorldConfig` 重建并 warmup 两套
MotionGen，只有两臂替代实例都构造成功后才切换引用。重建失败会保持原 planner 引用，
返回失败而不是伪造 readiness。该过程不执行 `scene.step()`，不改变 PAOS Core 或 Gateway
权限。

本次增加的测试覆盖容量分支、双臂替换和 no-motion 行为；真实环境验证使用 RoboTwin20
Python 3.10、Curobo/SAPIEN，构造 `blocks_ranking_rgb` 场景后更新完整 table+red+blue
世界，结果为两臂均 `operation=rebuild_motion_gen`、cache 按完整 world 的 3 个 cuboid
配置，且
`scene.step`/关节/夹爪命令均为 0。

### 六维验收补充：Anti-OverDefense

除原五维外，新增“防止过度防御编程”维度。仅保留能对应具体失败场景的校验：本次
`world_digest`/artifact 摘要用于跨进程 collision-world 内容漂移会导致错误规划这一可达
失败；`scene_revision`/`world_revision` 用于场景改变后继续使用旧障碍世界；cache capacity
检查用于 Curobo 明确的 OBB overflow。没有新增与该失败无关的冻结 contract、额外 gate 或
重复 hash。普通类型校验和单元测试仍承担本地结构检查。

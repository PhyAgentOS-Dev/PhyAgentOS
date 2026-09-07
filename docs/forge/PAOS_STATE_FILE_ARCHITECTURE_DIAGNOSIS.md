# PAOS 状态文件架构诊断与下一步方向

> 诊断范围：PAOS v1.0 文档、当前 `PhyAgentOS-forge` 源码，以及近期抓取放置 / RoboTwin 接入诊断。
>
> 目的：记录五类报告概念与 PAOS 现行架构的对应关系，明确状态文件是否为权威中间状态，并给出下一步实现方向供审核。本文件只做架构分析，不代表已批准的代码实施。

## 1. 执行结论

PAOS 当前没有规定“中间状态必须使用 Markdown 存储”。v1.0 文档明确将旧的 Markdown queue Runtime 视为已移除；当前权威状态由 AgentTask SQLite、Gateway ToolInvocation、Evidence JSON/artifact、Runtime state store 和 Experience SQLite 分别持有。

Markdown 在 PAOS 中承担三类职责：

1. Agent 工作区上下文和人工说明（例如 `AGENTS.md`、`EMBODIED.md`、`TASK.md`、`SKILL.md`）；
2. 人类可读的输入或运维界面；
3. 由机器事实源生成的 projection（例如 Skill-scoped `references/LESSONS.md`）。

因此，报告中的 `TARGETS.md`、`SKILLRUNTIME.md`、`SESSIONS.md`、`ENVIRONMENT.md`、`LESSONS.md` 可以保留为领域接口或 projection，但不应在 PAOS 核心中形成第二套事实源、状态机或执行协议。

## 2. PAOS 文档中的权威边界

### 2.1 当前持久化布局

PAOS 文档规定的持久化结构是：

```text
<workspace>/
├── .paos/agent_tasks/tasks.sqlite3
├── .paos/evolution/experience.sqlite3
├── .paos/evolution/revisions/<skill>/
├── skills/<skill>/SKILL.md
└── artifacts/agent_tasks/<task_id>/
    ├── before_snapshot.json
    ├── after_snapshot.json
    ├── evidence_bundle.json
    └── evidence/
```

通信架构进一步将 AgentTask、Evidence、Experience、Runtime state 和 Runtime logs 分到各自存储边界。跨边界只共享不透明 reference，不共享执行所有权。

### 2.2 Markdown queue Runtime 已移除

PAOS 总文档明确指出，当前 Skill Runtime 与“已移除的 Markdown queue Runtime”不同。这意味着 Markdown 文件不再是调度队列或执行中间状态的通用替代品。

### 2.3 Session 不是 Markdown 状态协议

当前 Session/Action 生命周期以 Gateway 的 `status/result` 为终态来源，PAOS 侧由 AgentTask 聚合，并通过 `invocation_id`、`attempt_id`、`task_id` 等显式身份关联。`pending`、`unknown`、`cancelled`、`stopped` 具有严格语义，不能由 Markdown 文本推断。

### 2.4 规范依据

- [文档索引的 Runtime 与兼容边界](../README.md#runtime-and-compatibility-boundaries)：当前 Skill Runtime 与已移除的 Markdown queue Runtime 明确分离；
- [框架介绍的持久化章节](../zh/01-framework-introduction.md#10-持久化)：列出 AgentTask、Experience、Skill revision 和 Evidence artifact 的实际存储；
- [通信架构的持久化边界](../user_development_guide/COMMUNICATION.md#10-持久化边界)：规定 AgentTask、Evidence、Experience、Runtime state 和 logs 的所有权；
- [Forge Tool API 契约](README_zh.md#8-agenttask-模型)：规定 AgentTask 状态机、Gateway invocation 终态来源和恢复语义；
- [Agent 经验与 Skill 自进化](../zh/05-agent-experience-and-skill-evolution.md#9-持久化投影与可观测性)：规定 `experience.sqlite3` 为事实源、Skill `LESSONS.md` 为人工审阅 projection。

## 3. 五个报告概念的映射

| 报告概念 | 当前 PAOS 对应 | 推荐定位 | 当前缺口 |
|---|---|---|---|
| `TARGETS.md` | `EMBODIED.md`、ToolSpec、Runtime/Profile、provider readiness | 能力矩阵的输入/可读 projection；结构化 schema 才是约束权威 | 没有统一 capability schema，也没有在所有 Action admission 中统一执行硬件能力否决 |
| `SKILLRUNTIME.md` | `skill.yaml`、manifest-v2、`RuntimeProfile`、`RuntimeManager` | Manifest 的说明性 projection | 不能再增加第二份 profile、Gateway 或 Node 配置源 |
| `SESSIONS.md` | Gateway Session、`AgentTaskRecord`、`AgentTaskStore`、Runtime state | 声明式意图输入，编译成 AgentTask | 没有文件到 AgentTask 的幂等编译器；不能让文件直接成为生命周期事实 |
| `ENVIRONMENT.md` | `load_environment_doc()`、SceneGraph Query、Observation/Evidence Snapshot | 环境知识和快照 projection | 文件尚不是带 revision/provenance 的环境事实源，Verifier 主要消费 Evidence Snapshot |
| `LESSONS.md` | `experience.sqlite3`、ExperienceCoordinator、Skill-scoped projection | 人工审阅和 Skill-scoped projection | 根文件在 evolution 模式下不是全局 Prompt 或 Verifier 输入 |

## 4. 为什么必须分离 Markdown 与机器事实

### 4.1 安全约束不能只存在于 Prompt

硬件关节范围、速度、工作空间和动作权限必须在 Runtime/Profile/Action admission 中确定性校验。Agent 读取 Markdown 后自行判断不能构成物理安全门。

### 4.2 事务状态不能依赖文本覆盖

长程抓取放置会同时涉及 Query、Action、Session、pending、timeout、unknown、cancel、replan 和 recovery。SQLite/WAL、事件记录和显式 invocation identity 比 Markdown 更适合并发、恢复和审计。

### 4.3 环境验收需要不可变证据

“物体是否已被抓取或放置”需要 before/after snapshot、scene revision、frame、calibration、时间戳和 artifact provenance。直接比较两个 Markdown 文件容易丢失这些关联，也容易被错误修改。

### 4.4 自主进化需要稳定的事实链

经验只能从完成且语义验证的 AgentTask 进入：

```text
Skill activation
  → AgentTask / PlanRevision
  → ToolExecutionRecord
  → Evidence + VerificationVerdict
  → redacted TaskEpisode
  → LessonCluster / SkillCandidate
  → guarded promotion
  → Skill/Lesson projection
```

Markdown 修改不能直接算作执行经验，也不能绕过支持门槛、抽象校验、作用域绑定、held-out/hazard 验证或 rollback。

## 5. 推荐的统一协议

### 5.1 输入型文件

`SESSIONS.md`、人工维护的 `TARGETS.md` 或环境说明可以作为声明式输入，但必须经过：

```text
Markdown
  → 解析与 schema 校验
  → 生成稳定 task/reference/revision identity
  → 写入权威 Store
```

解析器必须支持幂等、版本校验、未知字段拒绝和失败不调度。解析失败不能创建半有效任务。

### 5.2 Projection 型文件

`ENVIRONMENT.md` 和 Skill-scoped `LESSONS.md` 可以由机器事实源原子生成；`SKILLRUNTIME.md` 当前没有生产
producer：

```text
Manifest / Evidence / Experience Store
  → bounded projection
  → Markdown
```

人工修改 projection 不改变事实源；下一次同步可以覆盖 projection，或明确报告 drift，但不能静默改变执行语义。

### 5.3 唯一权威源表

| 领域 | 唯一机器权威 |
|---|---|
| 物理能力与动作限制 | validated Capability Profile / target schema |
| Skill Runtime | manifest-v2 + locked Node/Profile |
| 任务生命周期 | `AgentTaskStore` SQLite |
| Gateway 执行事实 | Gateway ToolResult / invocation events |
| 环境验收证据 | immutable before/after Evidence Snapshot |
| Lesson/Evolution | `experience.sqlite3` |
| Markdown | 输入界面或可读 projection |

## 6. 对抓取放置工作流的影响

当前 `pick-place-workflow` 已经具备 provider-neutral 六 Tool 纵向切片：

```text
scene.observe
  → scene.understand
  → grasp.propose
  → manipulation.prepare
  → object.acquire
  → object.place
```

已有 generic capability runtime、Fake Gateway、ToolSpec、证据和经验接口；当前尚缺真实 Gateway/Dora wiring、完整真实 provider、抓取/放置执行器和端到端真实验收。感知部分的单视角 adapter composition 已完成无动作协议验收，但不能等同于抓取成功。

因此，上层设置应先冻结以下最小契约，再继续抓取放置：

1. 能力矩阵字段、版本和 Action admission 归属；
2. `task_id`、`revision_id`、`record_id`、`invocation_id`、`attempt_id` 的身份边界；
3. `scene_revision`、`observation_ref`、`candidate_set_ref`、`preparation_ref` 和 before/after evidence 的关联规则；
4. Query/Action/Session 的状态转移、unknown 和 no-blind-retry 语义；
5. 哪些失败可进入 Experience，哪些只能保留诊断；
6. `motion_authorized=false` 的 no-motion 边界和真实执行的独立审批条件。

不需要先完成五个 Markdown 文件，也不应在此阶段实现独立 Markdown queue Runtime。

## 7. 推荐下一步实现方向（审核后调整）

### 审核结论：先做受限文件适配，符合 PAOS 扩展原则

“文件适配先于抓取放置闭环”本身不违反 PAOS 原则，反而能在低风险阶段暴露上层契约问题。成立的
前提是：适配器只解析、投影、dry-run、shadow validation 和 drift，不拥有 Watchdog、Gateway、
AgentTask 生命周期或 Action admission。Markdown 仍不是第二事实源，也不能直接触发物理执行。

#### 阶段 A：冻结最小上层与文件契约

- 建立权威源和所有权表；
- 固定状态、身份、revision、provenance、幂等和 projection 规则；
- 定义 Capability Profile 的最小 schema，并规定 `TARGETS.md` 只能先做 shadow validation；
- 定义 `SESSIONS.md` 仅作为声明式意图输入，不作为状态事实；
- 定义 `ENVIRONMENT.md` 只能投影带 revision/provenance 的可信 snapshot；
- 确定 Evolution 可修改和不可修改边界。

#### 阶段 B：实现无副作用文件适配与回放验证

- `SKILLRUNTIME.md`：从 manifest/Profile/Runtime 状态生成只读 projection；
- `ENVIRONMENT.md`：从 snapshot/Evidence 引用生成带来源和时间戳的 projection；
- `LESSONS.md`：从 `experience.sqlite3` 按 Skill 作用域生成 projection；
- `TARGETS.md`：解析、schema 校验、单位/范围检查和 Capability Profile shadow 对比，不改变 admission；
- `SESSIONS.md`：先实现 parse/validate 和 AgentTask dry-run preview，不写入生命周期或调度状态；
- 用 Fake Store、Fake Gateway、回放样例覆盖幂等、未知字段、失败回滚、projection drift 和 no-motion；
- 任一解析失败均不得创建任务、更新事实源或启动执行。

#### 阶段 C：提升已验证的输入边界

- 在人工确认和幂等校验后，才允许 `SESSIONS.md` 编译为 `AgentTaskRecord`；
- 只有通过 schema/profile 校验的 `TARGETS.md` 结构化结果，才可作为未来 admission 的候选输入；
- 保持 SQLite、Gateway、Evidence 和 Experience 各自的唯一权威，不把 Markdown 写回为事实源；
- 在此阶段仍不创建 Markdown queue Runtime，也不授权任何物理动作。

#### 阶段 D：继续抓取放置纵向闭环

- 让 `grasp.propose` 消费正式绑定的定位/点云 artifact；
- 让 `manipulation.prepare` 消费能力约束并保持 no-motion；
- 完成 `object.acquire` / `object.place` 的真实 provider-neutral Action admission；
- 将 before/after evidence 与放置语义验收接通；
- 保持 Fake Gateway、无动作和 fail-closed 测试，并将失败分类为 workflow failure 或 diagnostic-only failure。

#### 阶段 E：接入受控自主进化

只有当文件适配和抓取放置都产生稳定的 AgentTask、Evidence、VerificationVerdict 和 failure-owner 后，
才纳入 LessonCluster 或 SkillCandidate 晋升。文件解析成功、projection 更新或 dry-run 预览本身都不能
成为进化证据。

### 7.1 第一阶段实现状态（v2.10.0）

已实现 `PhyAgentOS.state_io` 的受限适配骨架，当前只覆盖文件协议验证和无副作用预览：

- `protocol.py` 要求单一 fenced JSON/YAML state block、固定 `paos.state-file.v1` 元数据、有限 JSON 值，
  并提供原子 projection 写入和基于 canonical data digest 的 drift 拒绝；
- `adapters.py` 提供 `TARGETS.md` 的 capability matrix shadow validation，校验 profile、观测模态、动作空间
  和数值限幅，但固定返回 `motion_authorized=false`；
- `SESSIONS.md` 只生成确定性的 dry-run preview，不创建 `.paos/agent_tasks/tasks.sqlite3`，不调用
  AgentTaskCoordinator，不调度 Watchdog；
- `ENVIRONMENT.md` 由严格的 snapshot/provenance producer 生成，Skill-scoped `LESSONS.md` 继续由
  `experience.sqlite3` 的 Evolution producer 生成；`SKILLRUNTIME.md` 暂无生产 producer，通用 renderer 已不再作为
  `state_io` 公共 API。事实源仍由 RuntimeState、Evidence/Snapshot 和 `experience.sqlite3` 持有；
- 测试覆盖结构化块缺失、未知字段、非法限幅、projection drift、确定性 preview 和 no-motion 边界。

本阶段没有把文件适配器接入 AgentLoop、Watchdog、Gateway 或 Action admission。下一阶段若要允许
`SESSIONS.md` 编译为 `AgentTaskRecord`，必须另行增加人工确认、幂等 compiler、公开 Coordinator 调用和
事务 conformance；不能直接扩展当前 dry-run 函数的副作用。

### 7.2 阶段 C 首个受限 promotion 实现（v3.0.0）

已增加一个仍位于 `state_io` 适配边界内的 promotion 入口：

- `SessionCompileApproval` 是不可变、`extra=forbid` 的人工确认凭据，必须携带源文件 canonical SHA-256、审批人、审批编号和带时区的 ISO-8601 时间；文件 digest 变化会使审批失效。
- `compile_sessions_to_agent_tasks()` 默认只编译一个 session；多 session 文件必须显式选择 `session_id`，从而避免在全局单一非终态 AgentTask 约束下产生部分写入。
- 编译前通过 `AgentTaskStore.active()` 检查全局非终态任务，并以 `statefile+sessions://<digest>/<session_id>` 作为稳定 origin identity；重复编译返回已有记录，不创建重复任务。
- 真正创建只调用 `AgentTaskCoordinator.create_task()`；`parent_task_id` 与 `retry_limit` 作为 AgentTaskRecord 的声明式字段保存，且父任务必须已存在并处于终态。
- 该 promotion 仍不调用 Gateway、Watchdog 或 Action admission，结果固定 `motion_authorized=false`；因此它提升的是“任务意图输入边界”，不是执行权限。

该阶段的 promotion gate 是人工凭据、源 digest、全局活动任务、父任务身份和幂等性测试全部通过。抓取放置动作、证据闭环和自主进化仍保持在后续阶段。

#### TARGETS candidate 边界

阶段 C 同时增加 `promote_targets_candidate()`：它要求 `TARGETS.md` 通过严格 shadow validation，并要求
`TargetProfileApproval` 同时绑定候选源 digest 与当前 baseline digest。返回值只是不可用于 admission 的
Capability Profile candidate，固定 `motion_authorized=false`，不写 Runtime/Profile 权威配置，也不改变任何
Action 限幅。baseline 漂移、审批不匹配或 schema 失败均 fail-closed；真正的 Runtime/Profile admission 仍需
另行设计并审核。

#### 阶段 C candidate 代码审查结论

本轮审查确认：审批 schema 使用 `extra=forbid`、source/baseline digest 双重绑定，candidate promotion 不产生
任何执行副作用；同时补上了 `profile_id` 的 path-safe 校验，避免能力身份被路径语义污染。18 项定向测试覆盖
成功、非法输入、审批 decision/时间戳、baseline drift、显式差异批准、输入文件不变和 no-motion 边界。
candidate 外壳虽为 frozen dataclass，但其中嵌套 `data` 仍是普通映射；它目前只作为非权威比较/replay 结果，
不得被当作可变 Runtime 配置或直接传入 admission。若未来需要跨进程缓存 candidate，应再定义深度不可变/序列化契约。

### 7.3 ENVIRONMENT projection 实现状态（v3.2.0）

本阶段完成的是文件适配层，不是环境事实链的全部接入：

- `EnvironmentProjectionData` 要求 `scene_revision`、opaque `snapshot_ref`、`phase`、带时区的 `captured_at`、`source_id`、`frame`、`calibration_ref` 和结构化 `scene_graph`；`scene_revision` 必须与 envelope 的 `paos.revision` 一致。
- `render_environment_projection()` 和 `parse_environment_projection()` 只接受 `paos.mode=projection` 和上述 schema，错误来源、revision、时间戳或 scene graph 结构均 fail-closed。
- `SceneGraphQueryTool` 已切换到严格 parser；缺失、旧版或损坏的 `ENVIRONMENT.md` 返回 bounded error，不再静默回退为空环境。
- 模板已切换为 `paos.state-file.v1` projection envelope，并明确 Markdown 不是 Evidence、Verifier 或任务生命周期事实源。

已补上受限的 `EnvironmentProjectionProducer`：它只接受已捕获的 `ObservationSnapshot` 与显式
`scene_revision`、`snapshot_ref`、phase、source/frame/calibration 和 scene graph 元数据，并通过
`render_environment_projection()` 原子生成 `ENVIRONMENT.md`。`publish_from_adapter()` 只读取
EnvironmentAdapter 的 sanitized `snapshot()` 身份并校验 revision；不会捕获传感器、调用 Gateway、
创建 AgentTask、调度 Watchdog 或授权动作。producer 仍不把 Markdown 变成 Evidence/Verifier 事实源。

已进一步补上 `ForgeEvidenceWriter` 关联：writer 对 before/after manifest 做版本、phase 和路径校验，
为 writer-owned snapshot 生成稳定 opaque `evidence://` URI；producer 可由该 manifest 自动注入 phase 与
reference，并拒绝调用方提供的不匹配值。writer 现在拒绝同一 phase 的不同内容覆盖，保持 snapshot 不可变。

已增加基础 Verifier/Evidence boundary conformance：`VerificationRequestBuilder` 不能把
`ENVIRONMENT.md` projection 解析为 Evidence Bundle，`ForgeTaskVerifier` 也会拒绝将 projection URI
作为 verdict evidence reference。完整 LLM 语义 verdict、真实 Gateway replay/failure conformance 仍未完成，
因此阶段 B 仍未完全结束，阶段 D 抓取放置闭环暂不启动。

随后补充了 Evidence request-level conformance：完整 bundle 的 capture window、必需 kind/source、
authoritative association、artifact retention、byte size/digest、媒体类型和结构化 JSON 均在
不可变 bundle replay 中被重新校验；跨工作区复制后 artifact identity 与结构化事实保持一致。该测试
验证的是 Evidence 消费边界，不等同于已经完成 LLM 语义 verdict 或真实 Gateway replay。

当前又增加了 `ForgeTaskVerifier` 的本地 verdict contract conformance：验证 success 必须逐条满足
criteria，replan 必须携带 recovery context，criteria 集合和 evidence reference 必须精确绑定，
malformed model response 必须 fail-closed。该 conformance 通过替换模型启动 seam 的确定性 fixture
执行，不启动验证子进程、不调用模型或 Gateway；因此 provider-backed LLM 语义质量和真实服务 replay
仍需单独验收。

随后增加 Verification Service HTTP 层 replay/failure conformance：使用进程内 deterministic provider
验证授权 token、请求 envelope、重复 replay、一致 verdict normalization、invalid model response 和
provider failure。该测试覆盖真实 HTTP handler 与 `VerificationEngine` 的组合，但不启动生产子进程、
不连接外部 provider；因此 `VerificationServiceProcess` 的 provider-spec 启动链和真实模型质量仍需
在独立环境中验收。

本轮进一步补充了文件适配的 Fake Store/Fake Gateway replay、未知字段失败前置、编译失败无残留、
projection drift 保留旧内容和 no-motion conformance。这里的 replay 只证明适配器输入/投影的确定性和
失败边界，不把 Fake Gateway 变成生产执行路径，也不把 Markdown 提升为事实源。

需要明确：阶段 B 清单中的 `SKILLRUNTIME.md` producer 和额外的 `LESSONS.md` producer 是可选的可观测性
projection，不是 PAOS 核心生命周期或执行权限的前置条件。本项目当前不把 generic renderer 暴露为已实现模块，
也不实现第二套 Runtime 或 Experience 配置源；后续只有在运维审阅需求明确时才补充由 manifest/Runtime state 或
`experience.sqlite3` 生成的只读 projection。阶段 B 的必要关闭条件应优先看 Evidence 语义验收和
跨环境 replay/failure 覆盖，而不是“五个 Markdown 文件是否全部有 producer”。

### 7.4 v3.5.0 修复与第二轮审查结论

本轮修复与代码审查的逐文件记录见 [`STATE_FILE_IMPLEMENTATION_REVIEW_20260903.md`](STATE_FILE_IMPLEMENTATION_REVIEW_20260903.md)。
审查已关闭 AgentTask origin/migration/update validation、Evidence manifest/bundle/retention、ENVIRONMENT prompt、TARGETS/SESSIONS schema、
provider/service configuration 和 HTTP failure-path 的已知缺口。验证结果为仓库测试 `105 passed`，并另行通过
pick-place 示例测试 `241 passed`；没有把这些测试中的 Fake Store/provider 当作生产实现证据。

当前仍只实现必要的受限文件边界：`TARGETS.md` 是 shadow candidate，`SESSIONS.md` 是经人工确认后通过
Coordinator 的意图输入，`ENVIRONMENT.md` 是带 provenance 的 projection；`SKILLRUNTIME.md` 没有生产 producer，
Skill-scoped `LESSONS.md` 由 Experience ledger 生成。provider-spec 生产子进程门禁已完成；真实模型语义质量、真实 Gateway 和
抓取放置闭环仍需独立门禁，不能因为文件适配或 fixture smoke 通过而提前启动。

最终复审另外确认：AgentTask 的可变更新现在必须重新通过完整 record schema；robot-state 与 verifier structured JSON
拒绝非标准数值；Evidence retention 只在终态通过持久化 Bundle 身份和 RequestBuilder 已验证路径集合后执行，recovery
中间态保留证据。上述修复不改变 Markdown、Evidence、Runtime、Gateway 和 Experience 各自的事实 owner。

### 不推荐方案：先完整实现五个 Markdown 状态文件

该方案短期看起来结构完整，但会造成：

- Markdown 与 SQLite/Gateway 双重事实源；
- 第二套 Session/Watchdog 状态机；
- 环境文件可被误当作成功证据；
- Skill Runtime manifest 与 Markdown 配置漂移；
- 自主进化消费未经验证的中间文本。

## 8. 自主进化边界

### 可以进化

- Skill 工作流顺序；
- 重新观测和检查点；
- replan 和恢复建议；
- failure pattern 的抽象描述；
- Skill-scoped Lesson；
- 经过验证的 managed workflow block。

### 不可由自主进化直接修改

- 关节、速度、负载和工作空间硬限制；
- Action admission 安全门；
- Gateway 执行事实；
- AgentTask 生命周期和身份规则；
- Evidence 完整性和 provenance 规则；
- Verifier 的基础安全约束；
- Runtime 制品、Gateway identity 和 digest。

这样得到的是“根据真实执行经验改进未来的 Skill-use”，而不是“让模型自行修改物理真相或执行权限”。

## 9. 用户审核闸门

在进入下一轮实现前，请审核以下方向是否成立：

1. 是否同意 Markdown 文件只作为输入界面或 projection，不作为 PAOS 核心的唯一事实源；
2. 是否同意 `AgentTaskStore`、Gateway、Evidence 和 `experience.sqlite3` 分别保留各自权威；
3. 是否同意先冻结最小上层契约，再继续 `pick-place-workflow`；
4. 是否同意 `TARGETS` 的物理限制必须由 schema/profile/admission 确定性执行；
5. 是否同意自主进化只改变 Skill workflow/Lesson，不直接修改安全边界和执行事实；
6. 是否同意先完成受限文件适配（projection、shadow validation、dry-run 和回放验证），再推进
   `grasp.propose → manipulation.prepare → acquire/place` 的证据闭环。

审核通过后，下一阶段应以“上层契约冻结 + 无副作用文件适配验证”为实施目标；抓取放置闭环在该验证
通过后推进，且任何阶段都不创建第二套 Markdown 执行协议。

## 10. v3.8.3 门禁状态更新

完整 `gpt-5.6-sol/high` held-out + hazard 评估已完成并通过正式质量门禁：7 个 case 全部返回合法 verdict，contract、criterion、
recovery-context 均为 `1.0`，`success_false_positive_rate=0`，总体 verdict accuracy 为 `0.8571428571428571`，运行目录为
`artifacts/evals/verification/20260904T034715.434600Z-42a21625/`。其中一个 held-out replan case 被模型判为 `inconclusive`，
held-out accuracy 为 `0.75`，但高于当前总体阈值 `0.8`；该残余风险已记录，不把门禁通过描述为完美语义正确。

因此，Verification 语义质量门禁现在可以关闭。执行顺序仍未跳过物理边界：下一步是 Gateway/Dora 的无动作 wiring、失败/超时/身份
conformance 和代码审查；之后才是抓取放置闭环，最后才是基于可归因执行证据的受控自主进化。该评估没有连接 Gateway、Dora、Action 或硬件，
也没有授予 motion authorization。

## 11. v3.9.0 阶段验收澄清

本阶段“之前五个模块”是五个验收维度：架构集成、失败路径、权威边界、配置、可维护性；不是要求重新实现
`TARGETS.md`、`SKILLRUNTIME.md`、`SESSIONS.md`、`ENVIRONMENT.md`、`LESSONS.md`。这些文件继续遵循各自的
projection/input 与 SQLite、Gateway、Evidence、Runtime、experience ledger 事实源边界。

Gateway/Dora 无动作 wiring 已通过 provider-neutral `CapabilityRuntimeTransport` 接入既有 Runtime/ToolClient，覆盖
discovery/context、Query、Action/Session 生命周期、身份关联、timeout/unknown、cancel/stop、并发和 no-POST recovery。
该结果只证明协议与边界实现，不证明真实 Dora 进程或物理执行可用；抓取放置闭环与受控自主进化仍按顺序后置。

## 12. v3.10.0 抓取放置阶段状态

抓取放置阶段现已完成协议级证据闭环：固定六步 workflow reducer 可从标准 Gateway terminal response 提取
opaque identity，并要求 place 的 `acquire_invocation_ref` 与前一步成功 acquire 一致；成功 place 还必须提供完整
`post_release_evidence` artifact。该阶段仍是 no-motion/replay 语义，未连接真实 Dora、Action executor、机器人或硬件。

完成后按架构集成、失败路径、权威边界、配置、可维护性五个维度复审通过；下一阶段才可在独立 adapter/profile 门禁下讨论真实
环境接入，任何物理动作仍需额外的 Runtime/Profile/Action admission 与硬件安全证据。

## 13. EnvironmentAdapter 阶段状态与下一步

EnvironmentAdapter 接入门禁已按上述顺序启动并完成首个 provider-neutral observation seam。核心
`ObservationEndpoint` 负责 `scene.observe` Query 的输入、freshness、frame、calibration、scene revision、artifact
和错误投影；`ObservationSource` 负责注入式传感器捕获；RoboTwin20 adapter 只负责 profile、reset/snapshot 与
camera/depth/state artifact 投影。`OBSERVATION_TOOL_SPEC` 必须由部署方显式注册到 CapabilityRuntime，不能由
HTTP transport 或 adapter 偷含环境语义。

本阶段五维复审通过：架构集成无第二执行平面，provider 异常/不可用/stale/绑定漂移 fail-closed，RoboTwin actor/entity
truth 不进入 observation，profile/path/calibration 不硬编码到核心 runtime，测试与错误码保持可维护。专项测试 10 passed，
根仓库 161 passed，RoboTwin 无第三方依赖子集 16 passed；完整 RoboTwin 测试因当前 PAOS 环境缺少 `numpy` 与
`pick_place_workflow` 路径未收集，不构成完整真实 adapter 验收。

因此当前可确认的是“核心 observation contract 与 no-motion adapter 边界完成”，不是“真实 RoboTwin/Gateway/Dora 或
硬件完成”。下一步按架构顺序是让 `scene.understand` 消费正式绑定的 observation/geometry artifacts，并以同样五维
标准进行审查；之后才讨论真实 Gateway/Dora provider wiring。多视角 observation、GraspGen live checkpoint、prepare/action
executor 和自主进化 promotion 继续后置。

`scene.understand` 的正式 observation consumer 现已完成边界加固：请求 observation identity、artifact refs、provenance
和 spatial frame 均做确定性绑定，provider 不能修改原始请求绕过校验。该阶段仍是 Query/no-motion；下一步才是让已验证的
geometry artifact 被 `grasp.propose` 消费，随后再考虑真实 Gateway/Dora provider wiring。

`grasp.propose` 现已完成对 `scene.understand` geometry artifact 的 consumer 加固：candidate provenance 必须绑定当前
target 的 observation evidence，candidate-set 与 observation identity 严格一致，provider request 使用隔离副本。该阶段仍
只产生抓取候选证据，不授权 IK、碰撞或动作；下一步进入 `manipulation.prepare` 的正式 candidate consumer。

## 14. manipulation.prepare 阶段结论（2026-09-04）

`manipulation.prepare` 已完成 provider-neutral candidate consumer 的协议加固：observation/candidate-set identity 必须与
scene revision 和 frame 精确一致，prepared candidate 必须唯一且绑定输入 candidate/entity，三项 readiness check 必须全部
通过，provider 请求使用隔离副本，所有失败保持 fail-closed，输出固定 `motion_authorized=false`。这不是五个 Markdown 状态文件的
再次实现，也不是将 Hephaestus executor 接入 PAOS。

Hephaestus 在本阶段只作为 clean-room 行为参考（Query/no-motion、执行前准入、失败语义和证据边界）；PAOS 不复制 Hephaestus
executor、receipt、state store、ToolRegistry、CLI execution path 或 provider payload。权威事实仍由 PAOS 的 Runtime、Gateway、
Evidence、Verifier 和 adapter/profile 分层持有。

五维审查无 Blocker/Major，专项 60 passed、根仓库 161 passed、pick-place 256 passed。该结果仅证明 candidate → readiness 的
协议闭环，不证明真实 IK/碰撞/轨迹/物理可达性或真实 Gateway/Dora/硬件。下一步是独立 adapter `ReadinessEvaluator` conformance，
之后才讨论真实 Action/Gateway wiring，最后才是基于执行证据的受控自主进化。

`robotwin20_adapter.RoboTwinReadinessEvaluator` 现已完成独立 adapter conformance：它以 mapping 形式接收公共 preparation
request，严格复核 observation/candidate-set identity、candidate/entity 绑定和 provider 返回的全通过 checks/evidence，
并通过深拷贝隔离 evaluator 请求。PAOS endpoint 可规范化该 mapping，但仍是唯一的公共 projection 和 no-motion owner。
专项测试 14 passed；没有引入 Hephaestus 运行时依赖，也没有连接 IK/碰撞引擎、Action、Gateway、Dora 或硬件。五维复审无
Blocker/Major；下一步是独立 readiness worker 的真实 evidence/replay 证据，之后才考虑 Action/Gateway wiring。

独立 readiness replay worker 现已完成：profile 对 fixture 和 evidence manifest 执行绝对路径、不可写和 SHA-256 门禁，JSONL
worker 对完整 observation/candidate identity 做精确 case 匹配，并校验证据引用的 revision、frame、calibration、source
和带时区 timestamp；client 校验 worker/schema/no-motion 后才向 PAOS 投影。该阶段证明可重复的协议 evidence，不证明真实
IK、碰撞规划或物理可达性；五维审查无 Blocker/Major，专项 `34 passed`，依赖隔离 adapter 子集 `44 passed`。下一步是对
真实或独立验证的 readiness worker 生成 evidence replay，之后才讨论 Action/Gateway wiring。
当前 adapter 已提供一个受限的 replay artifact 固化接口：它把 worker 已通过
conformance 的 no-motion projection 以不可变 canonical JSON 保存，并绑定 worker、fixture、evidence
manifest、请求和结果 digest。该文件只是 adapter-local audit/replay artifact，不是 PAOS EvidenceBundle，
不会改变 Verifier 的权威边界，也不会授予 Action admission。只有真实或独立验证 worker 的证据完成
人工审核后，才可据此进入真实 Action/Gateway wiring；fixture replay 本身仍不能被描述为真实 IK、碰撞
或物理可达性证据。

## 15. 已接入 no-motion 真实链路自审与运行证据（2026-09-05）

本次按五个维度重新自审，未发现需要阻断当前 no-motion 阶段的 Blocker/Major。文档中较早章节的“下一步”是历史阶段记录，
当前有效门禁仍为：先取得真实/独立 readiness evidence 并人工审核，再进入 Action/Gateway wiring；不能因为 observation、
语义或感知 provider 的单项 live 成功而提前改变顺序。

独立 RoboTwin20 Python 3.10.21 环境真实运行唯一 run `paos-real-chain-20260905T0020Z`，任务为
`beat_block_hammer/demo_clean`、seed `0`、`aloha-agilex`。preflight 的 runtime modules、Torch CUDA、SAPIEN renderer、
Vulkan、task import 全部通过；真实 `scene.observe` 生成 RGB/depth/state/calibration；真实 `gpt-5.6-sol` 生成 4 个
语义实体和 3 个 ambiguity；LocateAnything + SAM2 + RGB-D localization 生成 12 个派生 artifact。每一步的 request/result、
原始 stdout/stderr、源/派生 artifact、profile digest 和版本绑定在：

`/home/yanxu/robotwin20-runtime/artifacts/paos-real-chain-20260905T0020Z/run_manifest.json`

manifest SHA-256 为 `da7a81bd2efccbf70312428a3adeef10babe2d465734f63f7c90444297389b46`，并固定
`motion_authorized=false`、`simulation_motion_requested=false`、`simulation_motion_executed=false`。GraspGen 因
`GRASPGEN_PYTHON` 未配置而 fail-closed 为 unavailable；readiness replay 因 `READINESS_FIXTURE` 未配置而 unavailable；
因此没有伪造后续成功，也没有尝试 `object.acquire`/`object.place`。

五维结论：架构集成保持 adapter/profile 与 PAOS authority 分离；失败路径在 provider 配置缺失时停止；权威边界仍由 PAOS
contract 和 no-motion gate 持有；配置路径、模型和 key 不写入核心代码；中间结果可按 manifest 重放。RoboTwin 当前可用于
传感器与感知 no-motion 验收，不能称为抓取放置动作验收。

## 16. GraspGen live provider seam 验收（2026-09-05）

根据真实链路硬门槛，恢复了独立 GraspGen workspace 的 profile 指向：Python 3.10.21、Torch/CUDA、source checkout、
Panda generator/discriminator checkpoint 和配置均通过存在性检查。首次 adapter 重放暴露第三方 logger 污染 JSONL stdout；
`graspgen_worker.py` 已将模型 load/inference 输出重定向到 stderr，保留 stdout 为逐行 JSON 协议，并增加回归测试。

随后通过 `GraspGenProposalProvider` 对同一真实感知 artifact
`entity://red-rectangular-block-1` 的 `object_point_cloud` 执行 no-motion `grasp.propose`：
`provider_available=true`，返回 24 个 provider-neutral candidates，funnel 为 `24→24→24→24`；候选仅标记
`proposed/low_confidence`，没有 IK、碰撞、Action、Gateway、Dora 或执行授权。

完整证据目录为 `/home/yanxu/robotwin20-runtime/artifacts/paos-graspgen-live-20260905T0040Z/`，包含
adapter request/result、配置摘要、worker clean stdout/stderr、原始 request JSONL 和 manifest。manifest SHA-256 为
`a7627a6d8583bf4da502dfe1deaf8c3ec1e978f8f274ede545446614f43ae336`。

该结果证明真实 grasp provider seam 已可用，不证明抓取位姿经过 IK/碰撞 readiness，也不证明任意抓取或抓取放置闭环；下一道门仍是
真实或独立验证的 readiness worker evidence 及人工审核。GraspGen 配置中的 `random_seed=-1` 使候选具有随机性，后续应在不改变
权限边界的前提下补充可复现 seed 绑定。

## 17. 2026-09-04 自审与执行顺序修订：可替换本体边界

本轮自我审核没有发现需要改变 PAOS 上层架构的 Blocker，但发现并修正了
RoboTwin adapter 的三个 Major 集成缺口：preflight 原先只接受单字符串
embodiment；backend 会把单臂 Panda 静默按共享双臂处理；readiness replay
只绑定 worker/fixture，而没有绑定机器人、夹爪、拓扑和 planner profile。

修订后的权威边界是：PAOS 公共 ToolSpec、Skill、AgentTask、Gateway 和
Evidence schema 不增加 RoboTwin 字段；本体替换由 adapter-owned runtime
profile 完成。profile 可以声明原生双臂或 RoboTwin 官方的
`[left, right, interval]` 双单臂拓扑。preflight/backend 会校验对应
`config.yml` 的 `dual_arm` 声明，防止拓扑误配。readiness worker、evidence
manifest、worker response 和 immutable replay artifact 必须携带一致的
`embodiment_binding`（robot_identity、gripper_identity、
embodiment_topology、planner_profile、profile_digest），否则 fail-closed。

首个 Franka 长程 profile 为 `blocks_ranking_rgb` +
`[franka-panda, franka-panda, 0.8]`；它只推进 no-motion scene setup、
observation 和 readiness 证据，不开启 Action/Gateway/Dora/硬件。获得并
人工审核真实或独立 readiness evidence 之后，才进入 Action/Gateway 无动作
wiring，再做 RoboTwin motion simulation；`stack_blocks_two` 和
`stack_blocks_three` 作为后续复用同一 adapter 的 benchmark。

因此，PAOS 已有可替换的通用 EnvironmentAdapter/Profile seam，但此前没有
完整的 RoboTwin embodiment profile 和 readiness 身份门禁；本轮完成的是
adapter 层补齐，而不是把机器人本体提升为 PAOS 核心事实源。

readiness profile 现在还必须显式指向只读的 runtime profile 文件，并要求
该文件 SHA-256 等于 `embodiment_binding.profile_digest`。因此修改任务、本体、
拓扑或 planner 后，旧 readiness evidence 会在 worker 启动前失效，不能被
静默复用。

## 18. 2026-09-04 Franka readiness 输入审计

按修订后的执行顺序检查首个 `blocks_ranking_rgb` Franka 场景后，当前门禁
结果为 `unavailable`，详见
`docs/forge/FRANKA_READINESS_INPUT_AUDIT_20260904.md`。真实 capture 只包含
RGB/depth/state/calibration；没有同一 `blocks_ranking_rgb-0-1` revision 的
geometry 或 candidate set。已有 GraspGen 结果绑定的是
`beat_block_hammer-0-1/head_camera`，不能跨 revision 复用。由于输入不完整，
本轮没有启动 readiness probe，也没有生成 prepared candidate 或 replay
artifact。下一步必须先完成 Franka geometry localization 和同 revision 的
GraspGen，再恢复外部 IK/collision/workspace worker；人工审核 readiness
evidence 前仍不得进入 Action/Gateway wiring。
## 19. Franka readiness worker evidence 完成（2026-09-04）

已按上述门禁完成首个 Franka 场景的四步 no-motion 证据链：

1. `blocks_ranking_rgb-0-1/head_camera` capture 生成 12 个带 observation、scene revision、frame、calibration 的 derived artifact，其中 3 个 block point-cloud 文件真实存在；
2. GraspGen 在同一 scene revision 上运行，返回 71 个候选，funnel 为 `72→72→71→71`；
3. 独立 RoboTwin20 Python 3.10.21 进程重建双 Franka 场景，使用 Curobo 对 71 个候选执行左右臂 no-motion IK/collision/workspace probe，50 个候选获得 prepared evidence；
4. 50 个 evidence artifact、PAOS `manipulation.prepare` projection、manifest 和人工审核记录均已保存，并通过 request、candidate-set、observation、scene revision、frame、calibration、worker 和 profile digest 的一致性检查。

证据目录为 `/home/yanxu/robotwin20-runtime/artifacts/paos-franka-blocks-ranking-v470-20260904T/`。worker response schema 为 `paos-robotwin20-readiness-live/v1`；response、每个 evidence、preparation、manifest 和人工审核记录均固定 `motion_authorized=false`。人工审核决策为 `approved_readiness_evidence_for_next_no_motion_gate`，只允许进入下一阶段的 Action/Gateway no-motion 集成审查，不允许 Action stepping、Dora、硬件或物理执行。

`profiles/robotwin20/readiness-live.yaml` 与 `build_live_readiness_evaluator` 已将该 worker 接入现有 bounded JSONL process seam；profile 仍要求只读 runtime profile 和一致的 profile digest。

限制仍然有效：Curobo 当前碰撞范围只覆盖 robot self 与 table，未覆盖 attached object、完整 transport/descent/retreat、接触动力学或任务语义成功。因此这不是“任意抓取”或抓取放置闭环完成的证明；下一步是基于已审核 evidence 设计并审查 Action/Gateway 的 no-motion wiring，随后才可进行 RoboTwin 仿真动作接入。

## 20. Action/Gateway no-motion wiring（2026-09-05）

在已审核的 Franka readiness evidence 之上，Action admission 现在增加了 adapter-owned
`ReadinessEvidenceGate`。它读取 manifest、证据 artifact 和人工审核记录，校验 manifest/
review/evidence digest、`scene_revision`、`observation_ref`、`frame_id`、`calibration_ref`、
`candidate_set_ref`、`candidate_ref`、`entity_ref` 以及三项 readiness check；任一身份漂移、
证据缺失、过期或 `motion_authorized` 非 `false` 都在创建 invocation 前 fail-closed。Gate
只做只读校验，不启动 planner、RoboTwin `play_once`、Dora 或硬件。

`object.acquire`/`object.place` 的 provider-neutral Action endpoint 通过可注入 gate 接入
既有 Fake Gateway；Gateway context 显式声明 `motion_authorized=false`，仍使用标准
`invocation_id`/`attempt_id`、status/result、cancel 和 unknown 语义。Action provider 在
本阶段必须保持 `world_change_started=false`；planner/readiness 通过不等同于执行成功。
超时、取消、provider failure 和未知远端状态继续由 Gateway lifecycle owner 处理，不能
自动重试或宣称物理停止。

本阶段五维复审未发现 Blocker/Major：架构集成复用了 Skill Action endpoint 与既有 Gateway
route；失败路径在 provider 前拒绝并保留 unknown；权威边界由人工审核 digest 和 evidence
identity 持有；manifest/review/artifact 路径由 `action-readiness.yaml` 外置；实现没有新增
RoboTwin/模型依赖或第二套生命周期事实源。该 wiring 仍是 no-motion 集成证据，不授权
attached-object transport/descent/retreat、RoboTwin motion stepping、Dora 或硬件执行。

## 21. 仿真 motion executor 阶段的前置阻断与顺序修订（2026-09-05）

按文档进入 RoboTwin 仿真 motion executor 前，重新检查现有 gate、Action 生命周期和
readiness worker，发现以下问题必须先关闭，不能直接接入 `play_once` 或任意 simulator step：

1. **授权边界仍是 no-motion。** `ReadinessEvidenceGate` 要求 manifest/evidence 的
   `motion_authorized=false`，`object.acquire`/`object.place` 还会拒绝 provider 报告的
   `world_change_started=true`。当前人工审核决策只批准下一阶段 no-motion gate，不能被解释
   为仿真运动授权。
2. **Action 生命周期尚未具备真实执行语义。** 当前 endpoint 在 invocation 创建前调用
   provider；如果 provider 在这里启动仿真，动作会先于 `invocation_id`、timeout、cancel/stop
   责任建立，Gateway 无法可靠归属和停止该动作。必须先拆分为
   `validate/readiness → allocate invocation → execute → reconcile`。
3. **attached-object readiness 不存在。** 独立 worker 对每个候选只调用一次左右臂
   `plan_path`，证据中的 `collision_scope` 仍为 `robot_self_and_table`，没有附着物体、夹爪
   接触几何或携物后的联合碰撞模型。
4. **完整路径 readiness 不存在。** 当前没有 approach/contact/close/lift/hold 或
   transport/descent/release/retreat 的连续 waypoint、速度/关节限幅和中途停止证据。
5. **接触动力学与语义验收不存在。** backend 只执行 `setup_demo/get_obs`，不执行动作、
   物理接触或 `check_success`，也没有执行后的不可变环境快照供 Verifier 比较。

因此本阶段的执行顺序修订为：

1. 重构 Action 生命周期，确保 invocation 建立后才可启动 provider，并保留 timeout、cancel、
   stop 和 unknown 的归属语义；
2. 新增独立的 simulation-motion authorization profile/schema，与现有 no-motion readiness
   gate 隔离；
3. 在外部 RoboTwin worker 中加入 attached-object、完整 transport/descent/retreat 和
   workspace/limit/stop 证据；
4. 保存执行前后 observation/environment snapshot，接入语义 Verifier；
5. 完成独立人工审核后，才允许显式配置的 RoboTwin motion stepping；
6. 运动阶段完成后再按架构集成、失败路径、权威边界、配置、可维护性五维复审。

本轮只完成诊断文档更新和 no-motion 复核，不启动仿真运动，不修改
`motion_authorized=false`，也不把现有 readiness evidence 升级为执行成功证据。

本阶段第 1 步已实现为生命周期基础：通用 `CapabilityRuntime` 的
`ActionAdmission.start` 回调在 invocation/attempt 写入后才执行；pick-place endpoint
新增 `validate`/`execute` 分离，Fake Gateway 通过显式 `defer_action_execution=True`
在 invocation 创建后、首次状态/结果轮询时启动 provider。取消或停止发生在首次轮询前时，
provider 不会启动；启动异常会投影为带 invocation/attempt 的终态失败。默认 Fake Gateway
仍保持旧的同步 no-motion fixture 行为，避免无意改变既有回放语义。

该实现关闭了“provider 在 invocation 创建前启动”的生命周期缺口，但不改变运动授权：
现有 readiness gate 仍固定 no-motion，RoboTwin backend 仍不调用 `play_once`。因此它是
仿真执行前的必要基础，不是仿真动作或抓取放置闭环完成证明。

## 22. simulation-motion authorization profile/schema（2026-09-05）

按修订顺序新增了独立的 `paos-robotwin20-simulation-motion/v2` profile loader 和
`profiles/robotwin20/simulation-motion.yaml`。该 profile 与现有 no-motion readiness/action
gate 分离，只声明未来仿真动作需要满足的边界：Franka/task/scene 身份、runtime profile
digest、五类 readiness scope（attached-object collision、完整 transport/descent/retreat、
接触动力学、workspace/joint limits、stop control）、实际 evidence manifest
及其 SHA-256、worker/超时/停止策略以及 before/after snapshot 要求。

loader 严格校验字段集合、绝对非符号链接路径、runtime digest、seed/scene/embodiment
绑定、证据 scope 完整性、停止策略、snapshot 要求和 task-verifier handoff 必选项。默认 profile 为
`state: disabled`、`motion_authorized: false` 且不配置 worker；只有未来独立人工审批记录
满足专用 approval schema、profile identity、完整证据 scope、evidence manifest 摘要和 worker 配置时，profile 才能
被解析为 `approved` 声明。即使如此，loader 也不启动 worker、RoboTwin、Dora，不创建
Gateway invocation，不改变 Action admission；运动权限仍由未来 Gateway/Runtime executor
和执行后 reconciliation 持有。

这一阶段关闭的是“运动授权配置与 no-motion readiness 混用”的边界问题，不代表
attached-object readiness、连续路线、接触动力学、before/after snapshot 或语义成功已经实现。
下一步仍是让外部 worker 产生这些独立证据，之后才可在人工审核后实现受控 simulation
motion executor。

## 25. 独立 RoboTwin simulation-probe producer（2026-09-05）

本阶段实现独立 `robotwin_simulation_probe_worker.py` 与 `simulation_probe.py` profile-owned
client。它们与 PAOS verifier、Gateway、Dora 和硬件保持进程边界；只有专用 approval、producer/profile
摘要、request/candidate/route digest、Franka embodiment 和 stop-file 全部绑定时，外部 probe 才能在
RoboTwin 仿真执行一个候选路线。worker 校验 geometry、calibration、世界 workspace、轨迹/joint
limits、附着模型和接触 impulse，并保存八阶段路线、before/after、失败快照、detach/reset 状态。

`attached_object_collision` 明确记录 attached link、尺寸、采样半径和附着期间 active contact；非目标
环境 active contact fail-closed。`observed_outcome` 只记录单实体位移和选定夹爪释放，不产生任务 verdict，
也不声称完整 benchmark 成功或任意抓取。`stop_control` 只覆盖 worker-local
deadline/stop-file polling；开始世界变化的失败会保存 after-failure snapshot 并尝试 reset，不替代
Gateway kill/reconciliation。

本轮真实 `blocks_ranking_rgb` / Franka / seed 0 probe 在 retreat 检测到 `panda_rightfinger/table`
active collision，返回 `status=unavailable`，保存 failure artifact、contact trace、失败快照和 reset
状态；尚未生成 verifier 可接受的 available readiness evidence，也没有人工批准。这是安全负证据，不得
升级为 readiness pass、抓取放置闭环或硬件就绪。下一步必须依据 failure trace 修正候选路线，并使用
全新 request/artifact root 重跑；五个 readiness scope 全部通过且人工审核后才能申请受控 simulation motion gate。

### 25.1 真实 lift 门禁复审（2026-09-05）

后续以全新 request/artifact root 重跑后发现，旧 contact trace 中三个 block 都使用上游相同的
`box` 名称，且 planner attached model 成功并不能证明 SAPIEN 中的目标实体真实随夹爪运动。严格复审
因此增加三项 fail-closed 约束：probe-local block actor 使用稳定唯一身份；`lift` 结束时目标实体必须
相对 before snapshot 真实升高至少 `0.01 m`；before snapshot 必须在第一个 simulator step 之前持久化，
并随失败证据绑定。worker 初始化也移入真实 `model_load_*` 生命周期，删除启动时的预先 reset，保证
实际 backend generation 与 `blocks_ranking_rgb-0-1` 一致。

最新真实运行位于
`/home/yanxu/robotwin20-runtime/artifacts/paos-simulation-probe-20260905T1100Z`。它使用真实
GraspGen `candidate://block-green-1/2`、Franka seed 0、独立 approval 和全新 route digest；结果为
`status=unavailable`、`failed_phase=lift`、`error_detail=attached object did not lift with the gripper`。
失败前/后快照、route、calibration、geometry、approval、failure manifest 和人工 review 均已保存，
仿真 reset 完成且 `reconciliation_required=false`。因此 verifier 未被调用：它只能消费完整 available
evidence，不能把本负证据投影为 readiness pass。

下一步不再是 Action/Gateway wiring，而是从真实 71 个 GraspGen 候选中选择或生成能够在同一 seed/revision
下完成物理夹持与抬升的候选，再执行完整 transport/descent/release/retreat。只有真实 lift 和五个 readiness scope
全部通过后，才进入 no-motion route-evidence verifier 和人工批准；当前方向未偏离 PAOS 的 fail-closed
扩展原则。

## 23. simulation route-readiness evidence seam（2026-09-05）

按文档顺序新增 `paos-robotwin20-simulation-route-readiness/v1` contract、
`RouteReadinessClient`/profile loader 和独立 `robotwin_route_readiness_worker.py`。请求现在可
严格描述同一 observation/scene/candidate-set/frame 下的附着物体 geometry artifact、完整八阶段
`approach → contact → close → lift → transport → descent → release → retreat`、每个 waypoint
的速度限幅、workspace、joint-limit/stop policy 引用和 provenance。路线 geometry digest、candidate
identity 和 evidence artifact 均可复核，重复 YAML key、非法姿态/变换、workspace 越界、阶段缺失
和身份漂移均 fail-closed。

当前 worker 的实现边界是诚实的 unavailable：它只生成带 `motion_authorized=false`、
`world_change_started=false` 的 route evidence，明确标记 attached-object collision、真实 planner
路线、接触动力学、stop controller 和 semantic verifier 尚未接入；不会调用 `play_once`、不会
step simulator，也不会把结构检查当成 readiness pass。profile-owned client 复用 bounded JSONL
生命周期并拒绝把 unavailable 响应投影为可执行能力。

因此本阶段完成的是完整路线证据协议和安全 worker seam，不是 attached-object/IK/接触 readiness
本身。下一步仍需在同一 contract 下接入真实或独立 planner、附着碰撞模型、停止控制和执行后
语义快照，完成独立人工审核后才可申请 simulation motion。

## 24. 独立 route-evidence verifier（2026-09-04）

按上述顺序新增 `paos-robotwin20-simulation-route-evidence/v1` verifier、profile-owned
`RouteEvidenceClient` 和 bounded JSONL worker。该阶段不把结构化 route request 当成真实
readiness，而是消费外部 planner/仿真探针已经生成的证据：附着物体 geometry digest、完整
trajectory/joint-limit 产物、五个 route-readiness scope、before/after snapshot 以及 bounded observed outcome
verdict。每个 artifact 都要经过 root containment、不可变读取、SHA-256 和同一
request/candidate/scene/frame/calibration 绑定；快照还必须是绑定正确且 state digest 不同的
JSON 记录。

verifier 仅在所有外部证据均为 `pass` 时生成 route-readiness projection；响应和 projection
始终固定 `motion_authorized=false`、`world_change_started=false`，不会启动 RoboTwin、step
仿真、创建 Action/Gateway invocation 或替代人工审批。缺失、损坏、摘要漂移、身份漂移、
重复/越界 artifact 或 before/after 无状态变化均返回 unavailable/fail-closed。

该阶段完成了“真实/独立 evidence 的消费与审计边界”，不等同于已经获得真实 planner、接触
动力学或语义成功证据。外部证据必须声明受控 simulation probe 已获授权并实际发生世界变化，
而 verifier 自身仍保持 no-motion；二者不能混写。当前仓库只验证该协议和 fail-closed seam，
并未生成真实 probe 证据。只有外部独立 worker 生成并人工审核后，才可进入受控 simulation
motion executor。

## 31. simulation-probe policy 与恢复协议收口（2026-09-05）

本轮没有越过文档规定的 readiness 门禁，而是继续收紧独立 simulation probe。joint-limit 与 stop
policy 现在必须是 artifact root 内的实体化 JSON，worker 会校验严格 schema、Curobo runtime
position limits、planner joint velocity、SAPIEN 末端线速度以及每个 grasp/route pose 的 policy 上限。
专用 approval 同时绑定 calibration、joint policy 和 stop policy 的 SHA-256，不能在审批后用同名文件
替换输入。worker 明确为 single-use，避免第二次请求把 backend generation 2/3 冒充 revision 1。

失败恢复覆盖 `_run_candidate` 以及完成路线后的 snapshot、semantic 和 artifact finalization。发生任何
仿真世界变化后，worker 都会尝试 detach、保存 after-failure snapshot、reset，并把
`reconciliation_required` 与 reset 结果分开表达；即使尚未产生 robot-control step，scene reset 本身也
被如实记为 `world_change_started=true`。左右臂 planner 失败原因、有限且有序的 joint limits、唯一 actor
身份和真实目标 lift 仍全部 fail-closed。

最终真实证据目录为
`/home/yanxu/robotwin20-runtime/artifacts/paos-simulation-probe-20260905T020000p0800-policy-v6`。
它绑定真实 GraspGen `candidate://block-green-1/2`、Franka seed 0、实体化 `1.0 rad/s` policy 和完整输入
摘要。结果为 `status=unavailable`：左臂 planner route 失败，右臂轨迹超过 waypoint joint-speed limit；
`simulator_steps=0`，但 scene reset 已发生，因此保存了 before/after-failure snapshot，随后 reset completed，
`reconciliation_required=false`。人工审查结论仍为
`not_approved_for_readiness_or_motion_wiring`，route-evidence verifier 未被调用。

因此代码级五维审查已无 Blocker/Major，但功能 readiness 仍未通过。下一步仍是 candidate
selection/route generation：在不放宽 Franka 已审批速度、workspace、碰撞和真实 lift 门禁的前提下，
生成能够通过 planner 的参数化路线，再验证物体真实 lift 与完整 transport/descent/release/retreat。
只有五个 readiness scope 全部获得真实 available evidence 并人工审核后，才进入 no-motion verifier；不是现在接入
Action/Gateway/Dora。

### 32.3 RoboTwin worker frame-boundary correction（2026-09-05）

复核历史 Franka readiness worker 后发现，GraspGen 输出位于 `head_camera` OpenCV frame，而
SAPIEN `extrinsic_cv` 的语义是 `world_to_camera_cv`。旧 worker 将该矩阵直接当作
camera-to-world 使用，导致 planner 收到错误的 TCP 世界位姿；因此此前的 50 个 preliminary
prepared evidence 不能继续作为坐标正确性的依据。新增 adapter-owned
`grasp_adaptation.py`，要求校准 digest、观察 frame、route frame 和 provider-to-TCP transform
全部显式绑定，并对刚体变换做有限值、正交性和行列式校验；worker 复用同一逆变换逻辑。

修正后的独立 RoboTwin20/Curobo no-motion 运行目录为
`/home/yanxu/robotwin20-runtime/artifacts/paos-franka-readiness-fixed-20260905T1435Z`，
同一 71 个候选中 42 个通过修正后的 IK/workspace preliminary probe。该结果只说明坐标边界
修正改善了候选输入，仍只产生三项 preliminary checks，不包含 attached-object collision、真实
lift、完整 transport/descent/release/retreat 或接触动力学证据；因此不能升级为五项 route readiness。

随后又修正了结果投影边界：preliminary worker 现在始终返回空的 `prepared_candidates`，并将
每个 IK/workspace 候选放入 `preliminary_candidates`，其 `collision` 明确为 `unavailable`。
这样旧的三项 `manipulation.prepare` gate 也不会误把 preliminary 结果当成可执行准备证据。

另发现 RoboTwin20 Python 3.10 直接导入 PAOS Core 会触发 Python 3.11-only API。adapter package
现对 PAOS-coupled `arm_candidates` 使用惰性导出：route worker 可在 Python 3.10 加载纯协议模块，
PAOS 公共规划导出在 Python 3.12 请求时仍保持兼容。核心包的 Python 3.11+ 声明未被降级。

## 32. 语义 DAG、双臂候选枚举、完整路线选择与失败重规划（2026-09-05）

### 32.1 PAOS-first 复审修正（2026-09-05）

复审发现上一版描述把已删除的 core `ManipulationDag/ManipulationDagNode`、资源锁、条件三态和 retry
lineage 误写成当前实现，并把 Hephaestus 参考概念误写成 PAOS 规范；这不是可接受的“通过”。当前修正为：

- 子任务 DAG 由 pick-place Skill 的 `WORKFLOW_DAG`/`WorkflowDag` 提供只读、provider-neutral projection；它
  只验证 `depends_on`、ready nodes 和 digest，不写 SQLite、不创建 revision、不执行 Tool、不持有跨 Tool lease。
- `AgentTaskRecord`、`PlanRevision`、SQLite 和 `AgentTaskCoordinator` 仍是任务生命周期与恢复事实源；
  `ManipulationIntent` 只绑定一个 ready node，core 不再声明第二套 DAG 生命周期。
- observation frame 与 route/workspace frame 已拆开；calibration 只在 proposal→execution-grasp 适配时使用，
  route-frame pose 不得在 probe 中二次变换。
- readiness scope 只包括 attached-object collision、完整 transport/descent/retreat、contact dynamics、
  workspace/joint limits 与 stop control。仿真 probe 只能产生 before/after snapshot 和 bounded
  `observed_outcome`；任务级 verdict 由 `ForgeTaskVerifier` 唯一产生。

因此此前“core DAG 五维通过”的记录应视为撤销；本次修正后的契约测试只证明 no-motion 绑定与 fail-closed，
不证明真实路线、benchmark 成功、任意抓取或动作授权。

本阶段先对设计进行自审，再按 PAOS 拓展原则落地四个 no-motion 功能。Hephaestus 只作为失败案例和
风险清单来源；具体契约重新按 PAOS owner 边界设计。PAOS 不导入 Hephaestus 包、不复制其
Runtime/Planner/DAG 实现，也不改变既有
`AgentTaskRecord`、`PlanRevision`、SQLite、CapabilityRuntime、Evidence、Verifier 或 Gateway owner。

新增的公共 `PhyAgentOS.forge.manipulation` 只定义 provider-neutral projection：`ManipulationIntent`
绑定一个 Skill-ready node 的 task/revision/node digest、entity、observation、scene revision、frame、
calibration 和 candidate set，并固定 `motion_authorized=false`；`RouteFailure` 保存逐候选/逐手臂拒绝原因；
`ReplanCoordinator` 只生成带失败摘要和 preserved constraints 的 `replan_required` signal。语义依赖、
required bindings 和 node/dag digest 位于 Skill 的 `WORKFLOW_DAG`，而不是 core 第二套 DAG。

现有 `AgentTaskCoordinator.begin_revision()` 仍是唯一追加 PAOS `PlanRevision` 的入口。Replan signal 不能
直接改变任务状态、调用 planner、启动 provider 或创建 invocation；调用方必须按现有任务生命周期先进入
`awaiting_replan`，再由 SQLite 事务创建新 revision。

RoboTwin adapter 新增 `arm_candidates.py` 与 profile-owned `manipulation-planning.yaml`：
`enumerate_arm_candidates()` 将 candidate 展开为 `candidate × {left,right}` 的 alternative-arm 选项，或
严格的 single-arm 资源组；所有 option 保留同一 observation/candidate-set/scene/frame/calibration 绑定，
并固定 no-motion。`CompleteRouteSelector` 只通过注入的 readiness evaluator 检查完整八阶段路线、五项
route checks、digest、evidence 和 arm identity，然后按配置的 route length/speed margin 确定性排序。
所有选项失败时返回 `replan_required`，绝不放宽速度、workspace 或碰撞策略。

第一场景 `blocks_ranking_rgb` 使用 `alternative_arm`，即双臂作为可替代资源，而非伪造同步双臂动作。
真正的 bimanual 任务必须在未来由一个原子双臂 route bundle、统一时间轴、共享 scene revision、双臂互碰
检查和单一 evidence bundle 证明；当前公共契约只冻结模式名称，adapter 对其 fail-closed，不宣称已实现。

该设计保持 PAOS 分层：DAG 负责语义目标/依赖/重规划意图，adapter 负责本体 profile 和候选展开，
readiness 负责 IK/碰撞/速度/完整路线，Evidence/Verifier 负责不可变事实，Gateway/Action 仍未连接。
因此这四个功能不会把系统逻辑打乱，也不能把 selector 结果升级为 readiness 或 motion authority。

实现后五维审查进一步收紧了边界：每个 option 和 evaluator result 必须完整复述同一
task/revision/node/node-digest、entity/candidate、observation/candidate-set、scene/frame/calibration
以及 adapter arm profile；任何漂移均作为该 option 的拒绝原因。逐候选 evaluator 使用独立
`paos-robotwin20-route-evaluation/v1`，最终选择投影使用
`paos-robotwin20-route-selection/v1`，避免把 provider evidence 与控制平面选择混为一谈。
非通过结果至少要有一个非 pass check，重复 evidence、非法数值和未配置的 bimanual provider 均
fail-closed。Replan signal 只绑定当前 revision，不自行授权；stale revision、期限和预算继续由现有
`AgentTaskCoordinator.begin_revision()` 校验。

验收结果为专项 `16 passed`、PAOS/RoboTwin adapter 组合套件 `338 passed, 2 skipped`、根仓库
`171 passed`，ruff、compileall 和 `git diff --check` 通过；五个维度无 Blocker/Major 遗留。
这只关闭规划契约与 adapter 选择逻辑门禁，不改变上一节真实 simulation probe 的
`not_approved_for_readiness_or_motion_wiring` 结论。

### 32.2 重构收口与执行顺序确认（2026-09-05）

第二轮五维代码审查修复了十一个 Major：Skill reducer 改为以 DAG dependency readiness 而非 tuple 下标
决定节点准入；工作流 evidence references 改为不可变 mapping；replan hint 改为独立校验 identity、失败
唯一性、node digest 和内容 digest；机器人 adapter profile 统一拒绝重复 YAML key；恢复状态校验 task/revision
与 blocked reason；新增 route-readiness 到 route-evaluation 的 adapter projection；route request 校验
release TCP 变换和 phase gripper 语义；readiness client 完整复核逐 candidate evidence；worker artifact
identity 同时绑定 option request 与 candidate，避免左右臂冲突；evaluation adapter 不再虚构 fallback
evidence ref，worker/client 顶层明确拒绝任何 world change。Skill manifest/package 已同步为 `0.9.0`。
修复后的详细五维验收和命令见 `STATE_FILE_IMPLEMENTATION_REVIEW_20260903.md:32.2`。

执行方向没有偏离：下一阶段仍须在新的真实/独立 probe 中取得可审核的物理 lift、完整路线和五项
readiness evidence，再由人工审核决定是否允许进入 Action/Gateway/Dora wiring。本次 no-motion DAG、
route contract 和文档测试通过不能替代该证据门禁。

### 32.3 GraspGen depth 到 RoboTwin planner frame 修复（2026-09-05）

v4 preflight 的负证据确认，GraspGen 的 `+0.10527314 m` 是从
`gripper_base_link` 重建 canonical contact center 的 provider depth，不是可以
直接加到 RoboTwin `panda_hand` planner pose 的 TCP 偏移。本轮按 PAOS adapter
边界修复为三层不可混淆的契约：

1. `provider_T_contact_center` 将 GraspGen base 转为 canonical contact center；
2. profile 声明的 `robot_target_reference_distance_m=0.12`、`robot_gripper_bias_m=0.08`
   和 RoboTwin `delta_matrix` 将 contact center 转为 `robotwin_gripper` standard target；
3. route/probe 只使用 `robot_target_pose` 与 `object_T_robot_target`，contact center
   仅用于 contact-shell 证据和 round-trip 校验。旧的 `contact_tcp_pose`、
   `object_T_tcp`、`release_tcp_pose` 契约被 v3 route request 拒绝。

专项回归为 `62 passed`；adapter 回归为 `228 passed, 1 skipped`，根仓库回归为
`168 passed`。PAOS 环境现已安装 NumPy `2.5.2`，Ruff、compileall 和
`git diff --check` 均通过。

新的不可覆盖 no-motion route/review package 已写入：
`/home/yanxu/robotwin20-runtime/artifacts/paos-route-inputs-20260905T204500Z/materialized/`。
它绑定 `blocks_ranking_rgb-0-1`、`candidate://block-green-1/1` 和同一 calibration，
route schema 为 `paos-robotwin20-route-request/v3`，route digest 为
`b253fdc0f58a683ca6c73b33853a95f5655af3f0d7af78f8416c03096ed8e85e`，source
manifest digest 为 `9d4f599d703170fb2a4b24b0b4b7bbb68588d39b8f24c5e0ba2bc4e640fd9b93`。
review request 仍是 `pending_human_review`、`motion_authorized=false`；v4 digest
`225151fa...` 和 v4 approval 不可复用。

使用 RoboTwin20 Python 3.10 的连续 no-motion planner preflight 已完成：同一
scene/calibration/candidate-set 绑定成功，右臂八阶段 planner 全部通过，左臂仍
`unavailable`；retiming 保持 endpoint，并使速度满足 profile 的 1.0 rad/s 策略，
robot-control/simulator steps 均为 0。它证明 frame/IK/route/policy seam 可用，不证明
attached-object collision、真实 lift、完整 transport/descent/release/retreat、接触
动力学或语义成功。因此当前停止在新的人工审批边界，未运行 simulation probe、Gateway、
Dora 或硬件。

## 32.4 单 Agent 多执行资源与双臂协同协议自审及实现（2026-09-05）

### 设计自审结论

本轮确认 RoboTwin 的 `x<0 -> left` 只能作为 benchmark 参考策略，不能成为 PAOS
Agent 的 arm assignment 规则。双臂扩展应建模为“一个认知 Agent、一个 AgentTask、一个
Skill DAG、多个具身执行资源”，而不是两个独立 AgentTask 或两套生命周期事实。

DAG 只表达语义依赖、可并行分支、join、park 和失败替代关系；它不拥有资源锁、Gateway
invocation、运动授权或任务 verdict。当前 `blocks_ranking_rgb` 使用
`alternative_resource`（左右臂可替代），未来真正同步双臂动作才使用
`atomic_group`，并要求一个 Gateway-owned 原子 route bundle、统一时间轴、双臂互碰检查、
原子取消和单一 evidence bundle。两次独立 Action POST 不能被视为双臂同步。

### 新增协议边界

- PAOS core 新增 provider-neutral `ResourceRequirement`、`CapabilitySnapshot`、
  `ArmAssignment`、`CoordinationGroup`；它们是不可变投影，均保持 `motion_authorized=false`，
  不创建锁、任务、revision 或 invocation。
- Skill DAG 的 `WorkflowNodeSpec` 可声明符号化资源需求；具体 `arm_id` 只能由 adapter
  profile 和 readiness-backed route selection 产生。
- RoboTwin adapter 的 `manipulation-planning.yaml` v2 为每个 arm 声明 base/tool frame、
  gripper、planner/workspace/joint-limit/park refs 与支持模式；`build_capability_snapshot()`
  生成绑定 scene/observation/calibration/profile digest 的能力快照。
- `manipulation.capabilities` 是只读 Query projection；`project_arm_assignment()` 将完整
  route selection 转换成绑定 capability snapshot、readiness evidence、candidate、route
  digest 和 rejected alternatives 的 assignment。
- `ReplanSignal` 增加 `resource_unavailable`、`coordination_conflict` 和
  `partial_group_failure` 原因；仍由 `AgentTaskCoordinator` 唯一创建新 PlanRevision。

### 自我进化边界

Experience 可以在 Skill/workflow/embodiment 作用域内学习候选排序、arm assignment 偏好、
切换成本和失败后的重规划策略；只有独立、可归因、经过 semantic verification 的 episode
才能形成 Lesson 或 Skill candidate。Evolution 不得修改 workspace、joint limits、collision、
stop、readiness 或 motion authority，也不能把 benchmark 坐标规则写入通用 Skill。

### 协议实现收口

本轮自审发现并修复了一个实际集成缺口：能力快照和 assignment 虽已在 core/adapter
声明，却没有进入 canonical Skill reducer 与 Action schema 的强绑定。现在：

- `object.acquire` 与 `object.place` 的输入和 terminal result 都严格要求
  `capability_snapshot_ref`、`assignment_ref`；reducer 会保持它们的 opaque identity，拒绝
  缺失、非法 scheme 或漂移引用；
- `manipulation.capabilities` 已进入 pick-place Skill manifest、Tool contract 与 Fake
  Gateway discovery/query，provider 异常和 snapshot binding drift 均返回 unavailable；
- canonical Skill DAG 现显式包含 no-motion `capabilities` 节点；`observe` 完成后，
  `capabilities` 与 `understand` 是两个独立 ready Query，`propose` 对两者做显式 join，
  不把 Agent 的 Tool 调用顺序写死。所有后续节点必须复用同一个
  `capability_snapshot_ref`，旧状态通过 DAG digest/version fail-closed；
- 该协议升级为 `pick_and_place_semantic_dag_v4`、`pick_and_place_workflow_v5`，Skill
  manifest 与 Python 包同步为 `0.10.1`，旧 Runtime/Bundle 版本不会被新协议静默接纳；
- Fake Gateway 仅提供确定性的 no-motion replay snapshot，不产生 AgentTask、Gateway
  invocation 或动作授权；RoboTwin 的真实 assignment 仍必须来自 readiness-backed route
  selection；
- `CoordinationGroup` 继续只作为 atomic bimanual 的 fail-closed 协议投影。没有统一时间轴、
  inter-arm collision、atomic cancel 和单一 evidence bundle 时，不能把两个独立 Action
  当作同步双臂执行。

专项、Skill 全量和 RoboTwin adapter 全量测试均需在本轮实现后重新运行，再进行架构集成、
失败路径、权威边界、配置、可维护性五维代码审查；在审查完成前不启动 Gateway、Dora、
Action、仿真动作或硬件。

## 32.5 Planning module coordinator integration review (2026-09-05)

> 历史状态说明：本节早期的后续项已由 v5.7.0/v5.7.1 收口；当前有效状态以 `docs/forge/PLANNING_MODULE_DESIGN.md` 的 Implementation status 和最新五维验收为准。下一步是先获取独立 readiness/simulation evidence 并完成人工审核，再讨论受控 simulation motion。 Historical note: the early follow-up items in this section were closed by v5.7.0/v5.7.1; use the current implementation status and latest five-dimension review as authoritative. The next gate is independent readiness/simulation evidence and human review before controlled simulation motion.

The planning-module documentation review identified and closed the lifecycle
integration gap without turning planning into a second runtime. `PlanGraph` is
now accepted only as a concrete, identity-bound input with an `artifact://`
reference; its graph/planner/policy digests are persisted by the coordinator in
`PlanRevision`. A complete `PlanningExecutionBinding` can accompany Query,
Action, or Session calls and is persisted on `ToolExecutionRecord`; partial
bindings fail closed. `ReplanDelta` is adapted through
`begin_revision_from_delta()`, while the coordinator remains the only revision
writer. Decision-trace references are redacted when projected into Experience.

Five-dimension review: architecture integration, failure paths, authority
boundaries, configuration, and maintainability all pass for this scope. Legacy
tasks without planning metadata remain compatible. The live ToolSpec-to-policy
projection, AgentLoop production dispatch of `agent_composed`, and review-gated
Experience policy-candidate aggregation and promotion were completed in
v5.7.0/v5.7.1; they remain no-motion control-plane features. The active gate is
independent readiness/simulation evidence and human review. No Gateway, Dora,
Action, simulation motion, or hardware path was started.

## 32.6 v3 simulation-only probe result (2026-09-05)

The reviewer approved the immutable v3 route package for one simulation-only
probe using the exact route digest
`b253fdc0f58a683ca6c73b33853a95f5655af3f0d7af78f8416c03096ed8e85e` and source
manifest digest
`9d4f599d703170fb2a4b24b0b4b7bbb68588d39b8f24c5e0ba2bc4e640fd9b93`. The
approval was materialized at
`/home/yanxu/robotwin20-sim-probe-20260905T230500Z/probe/approval.json` with
`reviewer_id=yanxu`; the original route package remains unchanged.

The independent RoboTwin20 worker then ran once from the RoboTwin20 Python
3.10 environment. It initialized and reset the isolated simulator, selected
the right arm after the left-arm planner failed, and persisted before/after
snapshots, contact trace, failure evidence, and completed reset status. The
response is `unavailable` with:

- `failed_phase=contact`;
- `error_detail=simulator motion exceeds waypoint linear-speed limit`;
- `simulator_steps=834`;
- `world_change_started=true`, `world_change_completed=false`;
- `simulation_reset_status=completed`;
- `reconciliation_required=false`.

The probe output is preserved at
`/home/yanxu/robotwin20-sim-probe-20260905T230500Z/probe_response.json`, with
failure artifact
`artifact://simulation-probe/franka-blocks-green1-candidate1-20260905-v6-retimed/block-green-1-1/failure`.
This is a valid negative safety result: the current route does not satisfy the
profile-owned `0.2 m/s` simulator waypoint limit during contact. It does not
prove lift, attached-object transport, release/retreat, contact-dynamics
success, or semantic placement. The single-use worker must not be retried with
the same request or approval.

The next gate is to diagnose and regenerate a fresh, policy-compliant route
artifact (new request and digest), then obtain a new human simulation-only
approval before another probe. Gateway/Dora/Action wiring and hardware remain
blocked.

## 32.7 Contact-phase speed diagnosis and v7 route (2026-09-05)

The v6 negative result is caused by a mismatch between the two velocity gates:
the existing `uniform_time_dilation` retiming constrains Curobo joint samples,
but SAPIEN executes those samples through drive targets and the worker measures
actual end-effector displacement after each `0.004 s` scene step. A route can
therefore satisfy the `1.0 rad/s` joint policy while its Cartesian end-effector
motion exceeds the independent `0.20 m/s` route limit. The failure artifact
records this at `failed_phase=contact` after `834` simulator steps; it is not
evidence that the linear-speed limit is too strict and must not be bypassed.

The adapter fix is profile-owned execution velocity scaling. The materialized
joint-limit policy now carries `execution_velocity_scale=0.25`; the worker
scales only the drive target velocity before stepping, keeps the immutable
`max_linear_speed_mps=0.20` check, and records any measured violation with phase,
step, observed speed, limit, and scale. Route materialization validates this
field as a bounded `(0,1]` value. Joint limits, workspace bounds, simulator
timestep, and motion authority are unchanged.

The worker increments `simulator_steps` immediately after each `scene.step()`.
Consequently, a step that triggers a speed violation is included in the
failure evidence instead of being under-counted; the violation record reports
the one-based executed-step count. This is evidence bookkeeping only and does
not weaken the fail-closed gate.

A fresh v7 route was materialized without modifying v6:

- artifact root: `/home/yanxu/robotwin20-route-inputs-20260905T234000Z/`;
- request id: `franka-blocks-green1-candidate1-20260905-v7-scaled`;
- route digest: `a623f0bc08c36b40f3abf44455ddc652a136c6e09bd672d5375b0f8b6034baa9`;
- source manifest digest: `375bf7019651b6bb00acd1a694721e6f28fd22e0eeca3e89bcdd0c82a132b4b0`;
- status: `pending_human_review`, `motion_authorized=false`.

The v7 package has not been approved or executed. The next gate is a fresh
simulation-only approval for these new digests, followed by one single-use
probe. A passing probe must still demonstrate attached-object collision, lift,
complete transport/descent/release/retreat, contact dynamics, and semantic
before/after evidence before any Action/Gateway/Dora discussion.

## 32.8 v7 probe result and v8 route (2026-09-06)

Reviewer approval for v7 was recorded with route digest
`a623f0bc08c36b40f3abf44455ddc652a136c6e09bd672d5375b0f8b6034baa9` and source
manifest digest `375bf7019651b6bb00acd1a694721e6f28fd22e0eeca3e89bcdd0c82a132b4b0`.
The single-use probe ran under the fresh artifact root
`/home/yanxu/robotwin20-sim-probe-20260906T005500Z/` and returned
`status=unavailable`. It failed in `contact` at simulator step `872` with
observed end-effector speed `0.2025057481391883 m/s` against the immutable
`0.20 m/s` limit. The response and failure artifact record
`world_change_started=true`, `world_change_completed=false`,
`simulation_reset_status=completed`, `reconciliation_required=false`, and
`linear_speed_violation.execution_velocity_scale=0.25`; no complete lift,
transport, release, retreat, contact-dynamics, or semantic success is claimed.

The measured overshoot is approximately 1.25%, so the profile-owned execution
scale was conservatively lowered to `0.20` without changing any physical or
safety limit. A new v8 route was materialized under
`/home/yanxu/robotwin20-route-inputs-20260906T013000Z/` with request id
`franka-blocks-green1-candidate1-20260906-v8-scaled`, route digest
`6315cb3e4cc83e13738876aa32628d86b420e2aa6f80b785832d01db74b9fed3`, and
source manifest digest
`a62f4fbe5849445c821877d000ca8945c80ec94fcdc7ac15724bd43a89427506`.
It remains `pending_human_review` and `motion_authorized=false`; a fresh
approval is required before another single-use probe.

## 32.9 v8 probe result and v9 route (2026-09-06)

The reviewer-approved v8 probe ran once under
`/home/yanxu/robotwin20-sim-probe-20260906T020000Z/` and again returned
`status=unavailable`. The failure remained in `contact`, at simulator step
`876`, with observed end-effector speed `0.20113678709101113 m/s` against the
immutable `0.20 m/s` limit. The right-arm planner passed while the left-arm
planner failed; the object was not attached, reset completed, and no complete
pick-place or semantic success is claimed.

The measured speed improved relative to v7 but remains above the gate, so the
profile-owned execution scale was conservatively lowered to `0.10`. A fresh
v9 route was materialized under
`/home/yanxu/robotwin20-route-inputs-20260906T030000Z/` with request id
`franka-blocks-green1-candidate1-20260906-v9-scaled`, route digest
`438f4ddaba73b32f10586d7a96e9a87b39e5b850de489ced88a854129fbae46f`, and
source manifest digest
`14e686c14e09dd7731c7449397883e16d18841f841d267a3d2e6d5bed4f4c2f9`.
It is `pending_human_review` and has not been executed.

## 32.10 v9 probe diagnosis and position-subdivision direction (2026-09-06)

The reviewer-approved v9 probe ran once under
`/home/yanxu/robotwin20-sim-probe-20260906T040000Z/` and returned
`status=unavailable`. Unlike v7/v8, contact completed and the route reached
`lift`; the failure occurred at simulator step `1038` with observed speed
`0.2034626107917902 m/s`. The object had already been attached, failure
recovery detached it successfully, and simulation reset completed. This proves
that simply lowering the commanded velocity scale is not a monotonic or
sufficient Cartesian-speed control under SAPIEN drive-target dynamics.

The next implementation direction is profile-owned trajectory position
subdivision: interpolate joint targets between planner samples and scale the
per-substep velocity, while retaining the immutable measured `0.20 m/s` gate.
This changes only adapter-side simulation execution sampling; it does not alter
URDF, joint limits, workspace, stop policy, or production motion authority.

A v10 route implementing this policy was materialized under
`/home/yanxu/robotwin20-route-inputs-20260906T050000Z/` with request id
`franka-blocks-green1-candidate1-20260906-v10-subdivided`, route digest
`29450e78db41de37ad4e2dc570508e2de37069f35ad4cb32ec443ec173e1bc4a`, and
source manifest digest
`b476aeacf282ce3091943f4f8ba365e5b744446fa7e46040505a05a18db3f583`.
It remains pending human simulation-only approval.

## 32.11 v10 probe result and simulator-dynamics blocker (2026-09-06)

The reviewer-approved v10 probe ran once under
`/home/yanxu/robotwin20-sim-probe-20260906T072000Z/` and returned
`status=unavailable`. Position subdivision allowed the route to pass contact
and lift and enter transport, but simulator step `4293` measured
`0.2030478779191653 m/s`, above the immutable `0.20 m/s` limit. The object was
attached; recovery detached it successfully and reset completed. The complete
route and semantic placement remain unproven.

RoboTwin's `set_arm_joints()` sets both drive position and velocity targets;
the velocity target is not a hard SAPIEN Cartesian-speed limiter. The v7-v10
results therefore show that scale/subdivision tuning is non-monotonic and is
not sufficient evidence of safe Cartesian execution. This is now recorded as
a simulator-dynamics blocker. No further route tuning should occur until a
profile-owned simulator controller or independent speed-bounded execution
mechanism is specified and validated; the `0.20 m/s` gate remains unchanged.

The worker also rejects any segment whose retimed planner sample count exceeds
`trajectory_retiming.max_samples`, keeping the adapter-side execution budget
bounded and fail-closed.

## 32.12 rollback of unsupported execution tuning (2026-09-06)

The v7-v10 sequence was intended to address repeated simulator waypoint-speed
violations: v8 changed `execution_velocity_scale` from `0.25` to `0.20`, v9
changed it to `0.10`, and v10 added four-way position subdivision. These were
parameter experiments, not independent controller validation. The v10 probe
still measured `0.2030478779191653 m/s` during transport, while RoboTwin's
`set_arm_joints()` drive targets do not impose a hard Cartesian-speed limit.

The unsupported subdivision implementation and its profile/materializer/test
surface have therefore been removed. The profile scale is restored to the
pre-sequence `0.25` advisory value; measured speed remains the only probe gate,
and `uniform_time_dilation` remains the joint-trajectory retiming policy. The
historical v7-v10 artifacts and negative evidence are retained, but no new
route is generated until an independently validated speed-bounded simulator
controller or execution contract exists.

## 32.13 adapter-local speed controller seam (2026-09-06)

The speed-control design passed the five-dimension architecture gate and is
implemented only in the RoboTwin adapter. `trajectory_controller.py` exposes a
provider-local capability contract with two explicit modes:
`diagnostic_measured_guard` and `hard_bounded`. The current SAPIEN
drive-target backend advertises `hard_cartesian_speed_limit=false`; requesting
`hard_bounded` therefore fails before any simulator world change. Diagnostic
mode measures actual end-effector displacement after each step and raises a
structured violation while preserving the existing probe failure artifact.

This seam does not move speed control into PAOS Planning, the Skill, Gateway,
or Experience. A future qualified backend must provide its own controller
identity/version, bind them into the profile/approval artifact, and independently
validate hard-limit semantics before it may use `hard_bounded`; command scaling
and post-step measurement cannot satisfy that requirement. The current
diagnostic trajectory and failure evidence records the adapter controller
identity and mode for attribution, but this is not hard-limit qualification.

## 32.14 controller qualification evidence gate (2026-09-06)

Capability flags alone cannot enable a hard-bounded controller. The adapter
now defines an independent `ControllerQualification` record that must bind
controller and simulator identity, the exact Cartesian speed limit, observed
maximum speed, sample count, an immutable `artifact://` evidence reference,
independence, and approved review status. Missing, pending, over-limit, or
identity-drifted qualification fails closed before hard-mode execution.

This is an adapter/provider evidence gate, not a new PAOS lifecycle or motion
authority. The current RoboTwin/SAPIEN drive-target backend remains
`hard_cartesian_speed_limit=false`; its diagnostic measured guard can produce
negative evidence but cannot satisfy this qualification gate.

## 32.15 controller/SDK capability boundary review (2026-09-06)

结合速度诊断和 RoboTwin 依赖核验，本方案最终复用现有
`CapabilitySnapshot/ArmCapability`，不新增 PAOS Core 的 `MotionLimit` 事实源。
每个 arm 可携带 adapter-owned `motion_capabilities_ref`；详细限制、来源
和执行语义保存在不可变 controller-capability artifact 中，允许左右臂和不
同 embodiment 使用各自的 controller profile。

RoboTwin20 的本地 requirements 只有 SAPIEN、MPlib、CuRobo 等仿真/规划依赖，
Franka 配置加载 `panda.urdf`、`config.yml` 和 `curobo.yml`，执行通过 SAPIEN
`set_drive_target`/`set_drive_velocity_target`。当前 RoboTwin20 Python 环境中
`frankx`、`libfranka`、`franka_ros` 均不可导入，RoboTwin 仿真路径也未导入这
些 SDK。官方 libfranka API 单独提供 rate-limiting 参数和动态关节速度上限
接口，说明真实硬限制必须由未来 Franka hardware/controller adapter 提供，
不能从仿真参数推导。

因此 route profile 的 `0.20 m/s` 保留为
`source_kind=diagnostic_threshold`、`enforcement=measured_diagnostic` 的
RoboTwin probe policy，不代表 PAOS 全局限制、benchmark 硬要求或 Franka SDK
上限。只有具有 controller identity/version、明确来源、实际执行保证和独立
qualification evidence 的 controller 才能声明 `controller_hard`。Planning
只读取能力快照并做准入，Gateway/Controller 负责执行，Evidence 负责实测，
Experience 只能学习路线和工具策略。

本轮实现复用现有能力协议并增加 controller artifact 引用校验，没有新增
生命周期、锁、Gateway 调用或动作授权；RoboTwin 仍保持
`motion_authorized=false`。

## 32.16 MotionCapability v2 superseding decision (2026-09-06)

本节取代 32.13--32.15 中已经撤销的 `trajectory_controller.py`、固定
`0.20 m/s` diagnostic threshold 和 controller-capabilities/v1 作为当前实现的
描述；这些段落仅保留为设计演进记录。当前唯一有效入口是
`ArmCapability.motion_capabilities_ref` 指向 adapter-owned
`paos-robotwin20-motion-capability/v2`。旧 controller-capabilities/v1 模型和
测试已删除，避免形成第二份可手写的速度事实源。

RoboTwin provider projection 从真实 Franka URDF、CuRobo profile、planner、
simulator、drive-target source 和独立 runtime interpreter 导出逐关节限制、
source digest、provider identity 与 timing。独立 source validation 重新导出
并比较完整 canonical document，但其结论固定为
`validated_planner_constraints`；controller period、Cartesian velocity 和
effort enforcement 仍是 unknown，且不授予 motion authority。

route-request/v5 和 route-source-manifest/v3 必须绑定左右臂 capability 与
validation digest。simulation probe 会先验证这些绑定，然后因缺少单独的
controller-enforcement qualification 在任何 world change 前 fail closed。
因此“provider artifact 已完成”与“控制器执行资格未完成”是两个明确且不可
互相替代的状态。

### 32.17 qualification plan milestone (2026-09-06)

`docs/forge/ROBOTWIN_CONTROLLER_QUALIFICATION_EXECUTION_PLAN.md` now records
the next executable milestone. RoboTwin adapter contracts separate a
qualification plan, source manifest, human review request, no-motion
validation, scoped approval, execution evidence, independent validation, and
final qualification. The real v2 capability inputs produced a new immutable
package under
`/home/yanxu/robotwin20-runtime/artifacts/paos-controller-qualification-plan-20260906T1630Z/`.
Cross-artifact verification passed with
`world_change_started=false`; no scene, Gateway, Dora, Action, or hardware was
started. The package is eligible only for human review of isolated
qualification motion. It does not authorize benchmark motion or modify the
existing route approval.

### 32.18 qualification worker implementation result (2026-09-06)

大步 B 已在 RoboTwin adapter 内实现：`QualificationRuntime` provider port、隔离
SAPIEN worker、不可变 test-trace 和独立 evidence validator。worker 每次
`scene.step()` 前检查 approval scope、stop/timeout 以及 plan/source/capability
输入摘要；越限命令必须得到 provider 明确的 `rejected`/`limited`/`fault` 状态，
仅测得低速不算 controller enforcement。provider 缺少 SAPIEN 或 fixture 时，CLI
写入完整 `unavailable` evidence，不打印一个无法审计的“失败”字符串。

本次运行因当前解释器没有 SAPIEN，结果为 `unavailable`，独立 validator 输出
`validated_failure`；这证明失败路径和证据协议可用，但不证明 RoboTwin controller
已通过资格。该结果仍保持 `motion_authorized=false`，不得用于 benchmark、route、
Gateway、Dora、Action 或硬件授权。

### 32.19 capability-bounded provider controller (2026-09-06)

RoboTwin 原生 `set_drive_target`/`set_drive_velocity_target` 的负证据表明，原始
drive-target 路径不会产生可审计的越限拒绝或 stop/error/step 状态。因此没有继续
调小速度参数，而是在 RoboTwin adapter 增加
`CapabilityBoundedDriveController` provider boundary：它从绑定的 MotionCapability
读取逐关节限制，在写入 SAPIEN 前拒绝越限、NaN/Inf、错误状态和未结算 step，并
记录 accepted/rejected/settled 计数与状态迁移。该 controller 的源码摘要进入新的
capability artifact，形成新的 controller identity；旧 approval 不可复用。

这仍不是 PAOS Core 的全局限速器，也不替代真实硬件 SDK。它只提供一个可独立
qualification 的 RoboTwin provider controller；只有新 plan 经人工审批、实际
qualification evidence 经独立 validator 验证后，才可用于后续 route admission。

q3 plan 已在空双 Franka SAPIEN 场景中完成实际 qualification：八项测试全部产生
trace，结果为 `passed`，独立 validator 为 `validated_pass`。其中 over-limit 命令
在 SAPIEN 写入前被 provider controller 拒绝，contact、dropped-step、stop、error
和 reset 路径均有对应证据。随后为修正单臂/空闲臂调度语义更新了 controller source，
因此 q3 digest 不再适用于当前代码；新的 q4 capability/plan 已重新审批并运行通过。
q4 的独立 validator 输出 `validated_pass`，但最终 `approved_pass` 仍需单独人工结果审批。

最终结果审批已完成：q4 `ControllerQualification` 状态为 `approved_pass`，digest
`50ac70982b1dcdeb67ae65cfbd0e3ff3fcc31ebca5b7dd99baa7dcb03f3dc8e6`，且
`motion_authorized=false`。这只关闭 controller qualification 门禁，不关闭 route、
Gateway 或 benchmark motion 门禁。
### 32.20 qualification-to-execution path binding (2026-09-07)

五维复审发现：若 probe 在 controller qualification 之后仍直接写
`task.robot.set_arm_joints()` 并调用 `scene.step()`，q4 evidence 并未证明 route 使用
同一 controller。这是执行路径权威断裂，不是调参问题。现在 provider boundary 在创建
controller 及每一步前验证当前导入 controller 源码摘要、版本和 bounded controller id
与双臂 MotionCapability 一致；轨迹命令必须经过 pre-step/acknowledgement，夹爪使用零
速度 arm-hold，输入 digest 每一步重检，stop/fault/reset 停止所有 controller。native
controller、源码漂移、stale approval 和输入突变均 fail closed。旧 route/approval 必须
重新 materialize 和重新人工审批，之前不得运行 benchmark、Gateway、Dora、Action 或硬件。

### 32.21 fresh v6.7.1 route package (2026-09-07)

按照 32.20 的门禁，使用当前 worker/controller 源码生成了唯一、不可覆盖的
simulation-only route package：

```text
/home/yanxu/robotwin20-runtime/artifacts/paos-route-v6.7.1-20260907T0020Z/
route_geometry_digest=5dc2abfb6b23c322f12816c86e1762d36dde5da47dfd17b996e7eb112a6a0808
source_manifest_sha256=73aed005d1e07c3a11ba50785ee29cb0bb356217bae6c99b55d087f8abcedd2e
```

物化时绑定了 q4 approved qualification、左右臂 capability/validation、当前
simulation-probe worker digest、bounded controller source digest、RoboTwin runtime、
GraspGen transform attestation、scene/calibration、candidate geometry、object transform
和 placement target。只读校验确认所有 route/manifest/artifact digest 一致，且
`robot_control_steps=0`、`simulator_steps=0`、`motion_authorized=false`。

这是新的审批对象，不继承旧 route approval；在人工提供
`I_REVIEWED_AND_APPROVE_SIMULATION_ONLY` 前，不得执行 scene.step、single-object smoke
test、benchmark、Gateway、Dora、Action 或 hardware。

### 32.22 v6.7.2 probe failure diagnosis (2026-09-07)

v6.7.2 probe 先发现 RoboTwin20 Python 3.10 对 qualification artifact 中 RFC3339 `Z`
时间戳的兼容性问题；标准化 parser 修复后重新生成 route/approval。单对象执行 970 个
simulator steps 后，descent 阶段发生 `panda_hand ↔ block-blue-1` 非目标接触，release
阶段发生 `panda_rightfinger ↔ table` 接触；failure artifact 保存 pair、phase、step、
impulse、before/after snapshot、controller stop 和 reset 状态。该证据表明当前 green
candidate 的 attached-object/environment clearance 或 arm-route selection 不满足约束，
不是速度阈值问题；不得通过删除接触、放宽 collision gate 或复用旧 approval 处理。

### 32.23 v6.7.3 candidate-0 route diagnosis (2026-09-07)

对 v6.7.2 失败后的只读审查发现，RoboTwin 的 Curobo provider 在初始化
`MotionGenConfig` 时仅把 table 写入 `world_config`；其它方块虽存在于 SAPIEN 场景，
却未作为 planner obstacle 注册。因此 candidate 的 planner 通过只说明关节/末端目标
可达，不说明 attached object 和其它方块之间的环境 clearance。该适配缺口解释了
candidate-1 在真实 descent 中首次暴露 `panda_hand ↔ block-blue-1` 接触。

本轮没有修改碰撞规则或速度策略，而是从同一 GraspGen 候选集选择
`candidate://block-green-1/0` 生成独立 route package。其 release 点到 blue block 的
水平距离约 `0.1189 m`（candidate-1 约 `0.0565 m`），仅作为候选排序证据。新 package
的 route digest 为
`8a63ba68a9387e80ef8b3b3b67fbb0b469425139b09b621e6a4a0bccefb8f07a`，source manifest
digest 为 `0c70ba501db1a0e2962a5dff3e839fc58b8b1c0dbe0f6cf05d255ad8baee1b8`，当前仍
`pending_human_review` 且 `motion_authorized=false`。v6.7.2 approval 不得复用；只有新
审批后才能验证 candidate-0 的真实接触与语义结果。

## 32.24 已观测实体碰撞世界诊断的五维复核（2026-09-07）

本节对 32.23 的根因诊断和 `SceneCollisionWorld` 方案进行独立复核。复核依据包括：

- RoboTwin Curobo provider 在 `RoboTwin/envs/robot/planner.py:L58-L91` 初始化的
  `world_config` 只有 `table`；同一份配置分别用于 `motion_gen` 与
  `motion_gen_batch`。
- 当前 probe 在 `robotwin_simulation_probe_worker.py:L790-L829` 只通过
  `attach_external_objects_to_robot()` 注册当前目标物体，不能把其它实体变成静态
  planner obstacle。
- Curobo `MotionGen.update_world()`（`motion_gen.py:L1825-L1838`）要求更新后的
  obstacle 数量不超过初始化时的 collision-cache 容量，并会使 graph planner buffer
  失效。

### 审核发现与修订

原诊断没有 Blocker，但有三处必须在方案中明确的语义修订；若不修订，后续实现会产生
错误的“观测完整即碰撞安全”结论：

1. **未知空间边界（Major-risk，已通过文档修订降级为显式门禁）。** 观测到的实体集合
   不是完整世界证明。遮挡、深度空洞、透明/反光物体或传感器视野外区域必须产生
   `unknown_space`/coverage 状态；缺失的 geometry、pose、frame、calibration 或
   coverage 证据时，`manipulation.prepare` 必须返回 unavailable/stale，而不是把
   部分障碍物列表当成完整碰撞世界。仿真 actor truth 只能作为独立对照证据。
2. **目标排除必须按阶段限定（Major-risk，已修订）。** 当前目标可从 approach/contact
   的静态 obstacle 集合排除，但这不是全程排除：close 后必须由 attached-object
   模型表示，release 后必须 detach 并重新加入静态世界；每个 route phase 必须记录
   `excluded_target_entity` 和允许的接触语义，防止把目标排除误解为任意碰撞豁免。
3. **重规划触发者边界（Major-risk，已修订）。** planning library 只返回 admission
   与 stale/invalidation 结果；它不自行“触发” revision。`AgentLoop`/`AgentTaskCoordinator`
   读取结果后创建新的 `PlanRevision`，并重新绑定 collision-world digest。这样不会
   产生第二套 DAG 或任务生命周期。

### 五个维度结论

| 维度 | 结论 | 必须保持的门禁 |
|---|---|---|
| 架构集成 | 通过（无 Blocker/Major） | `SceneCollisionWorldBuilder`、Curobo world port 和 world-update receipt 留在 RoboTwin adapter/provider；PAOS planning 只校验抽象 artifact/readiness，不导入 Curobo、不执行 `scene.step`。 |
| 失败路径 | 通过（实现前置条件） | 缺失/过期/篡改 scene facts、未知空间、frame/calibration 不一致、目标重复注册、cache capacity 不足、任一 `update_world` 失败、world revision 漂移、unknown result 均 fail-closed；左右两套 `MotionGen` 必须一致更新。 |
| 权威边界 | 通过（无越权） | collision-world 是 provider projection；planner 结果只是 readiness evidence；SAPIEN contact/after-semantic 是独立执行事实；Gateway 仍是唯一生产动作 authority；任何 artifact 都保持 `motion_authorized=false`。 |
| 配置与 provenance | 通过（需冻结） | 绑定 `scene_revision`、`world_revision`、source facts/geometry/calibration digest、planner/runtime identity、obstacle 集合、excluded target 和 frame/quaternion convention；cache capacity 由 obstacle 数量和 provider base world 推导，不使用全局常量。不得把方块坐标或 Curobo API 写入 PAOS Core/Skill。 |
| 可维护性 | 通过（模块边界清晰） | 纯 builder 不导入 Curobo；provider port 负责 `WorldConfig`/双 `MotionGen`；route-readiness 负责引用/digest；probe 负责接触和恢复；planning 负责通用 admission；每层均有可重复的 no-motion 测试。 |

复核结论：**诊断方向正确，修订后的方案无 Blocker/Major；但功能尚未实现。** candidate-0
替换只能作为对照，不能关闭上述门禁。下一步仍应先实现并验证 provider-owned
`SceneCollisionWorld` artifact，再重新生成 route、获取全新的 simulation-only approval，
最后以独立 probe 证明 attached-object collision、完整 transport/descent/release/retreat、
接触动力学和语义结果。不得复用 v6.7.2/v6.7.3 approval，也不得在新 approval 前运行
`scene.step`、benchmark、Gateway、Dora、Action 或硬件。

### English review summary

The diagnosis is correct after three explicit clarifications: observed entities do not prove
complete coverage (unknown space is fail-closed), target exclusion is phase-scoped (static
obstacle → attached model → static obstacle), and replanning is requested by AgentLoop/
AgentTaskCoordinator rather than performed by the planning library. All five dimensions pass
without a blocker, but this is a design gate—not implementation or motion evidence. Both
`motion_gen` and `motion_gen_batch` must receive the same provider-owned world projection, and
every world/revision/digest drift must invalidate readiness.

## 32.25 v6.8.1 provider cache-capacity 修复与六维验收（2026-09-07）

独立 RoboTwin20/Curobo no-motion probe 证明：原生 planner 的初始 world 只有 table，
`MotionGen.update_world()` 添加两个 block 时因 OBB cache 不足抛出
`number of OBB is larger than collision cache`。这是 provider 初始化容量问题，不是
candidate、TCP、速度或 PAOS planning 顺序问题。

`robotwin_curobo_world_port.apply_collision_world()` 现在先读取左右
`motion_gen`/`motion_gen_batch` 的实际 capacity；容量足够时将同一 `WorldConfig` 更新到
四个实例；容量不足时沿用 RoboTwin planner 的 robot YAML、原生插值/seed 设置和完整
world 重建并 warmup 两套 MotionGen，只有两臂替代实例全部成功才切换引用。任一失败保持
旧引用并返回错误。该路径仅在 provider runtime，不执行 `scene.step()`，不改变 Gateway、
Action、Dora 或 motion authority。真实 no-motion 结果为两臂
`operation=rebuild_motion_gen`、capacity 覆盖完整 world 的 3 个 cuboid、控制步数 0。

### 六维验收

| 维度 | 结果 | 证据 |
|---|---|---|
| 架构集成 | 通过 | builder 为纯 adapter；Curobo 仅在 runtime port；planning 不执行 provider。 |
| 失败路径 | 通过 | overflow、缺配置、任一 arm 更新/重建失败均 fail-closed，且不半切换。 |
| 权威边界 | 通过 | provider receipt 只是 readiness 输入；Gateway 仍是生产执行权威。 |
| 配置与 provenance | 通过 | route v7 绑定 scene/world revision、world digest、coverage、target/obstacle 集合。 |
| 可维护性 | 通过 | 容量分支集中于一个 provider port；单元测试与真实 no-motion probe 可复现。 |
| 防止过度防御编程 | 通过 | 仅保留与实际 cache overflow、artifact drift、scene/world stale 直接对应的检查，未新增无依据 gate/hash。 |

该结论仅表示 collision-world provider 接入和 no-motion world update 完成，不等于真实
抓取放置、接触动力学、完整 transport/release/retreat 或 Gateway 动作验收。
